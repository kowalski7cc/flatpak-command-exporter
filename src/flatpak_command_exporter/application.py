import json
import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import gi

from .config import AliasConfig
from .defaults import COMMAND_TEMPLATE, DEFAULT_EXPORT_COMMANDS

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib

EXPORT_SCHEMA_NAMES = ("x-export-commands", "export-commands")


@dataclass(frozen=True)
class ExportedAlias:
    alias: str
    command: str
    app_id: str
    app_name: str
    arch: str
    branch: str
    installation_path: str
    desktop_id: str
    enabled: bool = True
    configurable: bool = True
    custom: bool = False


@dataclass(frozen=True)
class CommandGroup:
    app_id: str
    app_name: str
    arch: str
    branch: str
    installation_path: str
    commands: dict[str, str]


def load_metainfo(base_path, app_id, arch, branch):
    metainfo_path = os.path.join(
        base_path,
        "app",
        app_id,
        arch,
        branch,
        "active",
        "files",
        "share",
        "metainfo",
        f"{app_id}.metainfo.xml",
    )
    if not os.path.exists(metainfo_path):
        logging.warning("Metainfo file not found for %s at %s.", app_id, metainfo_path)
        return None
    try:
        tree = ET.parse(metainfo_path)
        return tree.getroot()
    except ET.ParseError as error:
        logging.error("Error parsing metainfo for %s: %s", app_id, error)
        return None


def _find_metainfo_child(metainfo, tag):
    return next(
        (child for child in metainfo if child.tag.rsplit("}", 1)[-1] == tag),
        None,
    )


def get_pretty_name_from_metainfo(metainfo):
    if metainfo is None:
        return None
    name_element = _find_metainfo_child(metainfo, "name")
    if name_element is not None and name_element.text:
        return name_element.text.strip()
    return None


def get_desktop_id_from_metainfo(metainfo, app_id):
    if metainfo is None:
        return f"{app_id}.desktop"
    launchable = _find_metainfo_child(metainfo, "launchable")
    if (
        launchable is not None
        and launchable.get("type") == "desktop-id"
        and launchable.text
    ):
        return launchable.text.strip()
    return f"{app_id}.desktop"


def get_version_from_metainfo(metainfo):
    if metainfo is None:
        return None
    releases_element = _find_metainfo_child(metainfo, "releases")
    if releases_element is not None:
        release_element = _find_metainfo_child(releases_element, "release")
        if release_element is not None and release_element.get("version"):
            return release_element.get("version").strip()

    version_element = _find_metainfo_child(metainfo, "version")
    if version_element is not None and version_element.text:
        return version_element.text.strip()
    return None


def load_manifest(base_path, app_id, arch, branch):
    manifest_path = os.path.join(
        base_path, "app", app_id, arch, branch, "active", "files", "manifest.json"
    )
    with open(manifest_path, encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def _read_manifest_or_empty(installation_path, app_id, arch, branch):
    try:
        manifest = load_manifest(installation_path, app_id, arch, branch)
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as error:
        logging.warning("Could not load manifest for %s: %s", app_id, error)
        return None

    if not isinstance(manifest, dict):
        logging.warning("Manifest for %s is not a dictionary. Ignoring.", app_id)
        return None
    return manifest


def find_refs(installation):
    """
    Find all refs of flatpak such as /var/lib/flatpak and /usr/local/share/flatpak.
    """
    try:
        if installation is None:
            return
        yield from installation.list_installed_refs_by_kind(Flatpak.RefKind.APP, None)
    except GLib.Error as error:
        logging.error("Error accessing Flatpak API: %s", error)


def get_current_ref(installation, app_id, fallback_ref):
    try:
        ref = installation.get_current_installed_app(app_id, None)
    except GLib.Error as error:
        logging.warning(
            "Could not find current ref for %s: %s; using last enumerated ref.",
            app_id,
            error,
        )
        return fallback_ref

    if ref is None:
        logging.warning(
            "No current ref found for %s; using last enumerated ref.",
            app_id,
        )
        return fallback_ref
    return ref


def _launcher_path(alias):
    AliasConfig._validate_alias(alias)
    data_home = os.environ.get(
        "XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
    )
    return Path(data_home) / "flatpak-commands" / alias


def create_launcher(app_id, export, command, arch, branch):
    path = _launcher_path(export)
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.debug(
        "Creating launcher for %s at %s with command: %s and arch: %s, branch: %s",
        app_id,
        path,
        command,
        arch,
        branch,
    )
    path.write_text(
        COMMAND_TEMPLATE.format(
            BRANCH=branch,
            ARCH=arch,
            COMMAND=command,
            APP_ID=app_id,
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)


def remove_launcher(export):
    path = _launcher_path(export)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def manifest_exported_commands(app_id, manifest: dict) -> dict[str, str]:
    commands: dict[str, str] = {}
    for schema_name in EXPORT_SCHEMA_NAMES:
        schema_commands = manifest.get(schema_name, {})
        if not isinstance(schema_commands, dict):
            logging.warning(
                "%s in manifest for %s is not a dictionary. Ignoring.",
                schema_name,
                app_id,
            )
            continue
        commands.update(schema_commands)
    if not commands:
        # Fetch commands from defaults
        return DEFAULT_EXPORT_COMMANDS.get(app_id, {})
    return commands


def get_exported_aliases(config: AliasConfig | None = None) -> list[ExportedAlias]:
    """Return aliases from current user and system app refs, preferring user refs."""
    aliases: list[ExportedAlias] = []
    seen_app_ids: set[str] = set()
    if config is None:
        config = AliasConfig()

    installations = (
        (True, Flatpak.Installation.new_user),
        (False, Flatpak.Installation.new_system),
    )
    for is_user_installation, installation_factory in installations:
        try:
            installation = installation_factory()
            if installation is None:
                continue
            installation_path = installation.get_path().get_path()
        except GLib.Error as error:
            logging.warning("Could not access a Flatpak installation: %s", error)
            continue

        refs_by_app_id = {}
        for ref in find_refs(installation):
            refs_by_app_id[ref.get_name()] = ref

        for app_id, fallback_ref in refs_by_app_id.items():
            if app_id in seen_app_ids:
                continue
            seen_app_ids.add(app_id)
            ref = get_current_ref(installation, app_id, fallback_ref)
            arch = ref.get_arch()
            branch = ref.get_branch()

            manifest = _read_manifest_or_empty(
                installation_path, app_id, arch, branch
            )
            if manifest is None:
                continue

            metainfo = load_metainfo(installation_path, app_id, arch, branch)
            app_name = get_pretty_name_from_metainfo(metainfo) or app_id
            desktop_id = get_desktop_id_from_metainfo(metainfo, app_id)
            commands = manifest_exported_commands(app_id, manifest)
            custom_aliases = {}
            if is_user_installation:
                custom_aliases = config.custom_aliases(app_id)
                commands = {**commands, **custom_aliases}
            for alias, command in commands.items():
                aliases.append(
                    ExportedAlias(
                        alias=alias,
                        command=command,
                        app_id=app_id,
                        app_name=app_name,
                        arch=arch,
                        branch=branch,
                        installation_path=installation_path,
                        desktop_id=desktop_id,
                        enabled=(
                            config.is_alias_enabled(app_id, alias)
                            if is_user_installation
                            else True
                        ),
                        configurable=is_user_installation,
                        custom=is_user_installation and alias in custom_aliases,
                    )
                )

    return aliases


def export_commands(config: AliasConfig | None = None) -> None:
    """
    Export commands for the current ref of each user-installed Flatpak app.
    """
    installation = Flatpak.Installation.new_user()
    if installation is None:
        return
    installation_path = installation.get_path().get_path()
    if config is None:
        config = AliasConfig()
    refs_by_app_id = {}
    launchers = {}
    disabled_aliases = set()
    for ref in find_refs(installation):
        refs_by_app_id[ref.get_name()] = ref

    for app_id, fallback_ref in refs_by_app_id.items():
        ref = get_current_ref(installation, app_id, fallback_ref)

        manifest = _read_manifest_or_empty(
            installation_path, ref.get_name(), ref.get_arch(), ref.get_branch()
        )
        if manifest is None:
            continue
        exported_commands = manifest_exported_commands(ref.get_name(), manifest)
        exported_commands = {
            **exported_commands,
            **config.custom_aliases(app_id),
        }
        for export, command in exported_commands.items():
            if config.is_alias_enabled(app_id, export):
                launchers[export] = (
                    ref.get_name(),
                    command,
                    ref.get_arch(),
                    ref.get_branch(),
                )
            else:
                disabled_aliases.add(export)

    for export in disabled_aliases - launchers.keys():
        remove_launcher(export)
    for export, (app_id, command, arch, branch) in launchers.items():
        create_launcher(app_id, export, command, arch, branch)


def get_command_groups(
    app_id: str | None = None,
    include_system: bool = True,
    first_only: bool = False,
) -> list[CommandGroup]:
    """Return exported commands grouped by installed application ref."""
    installation_factories = [Flatpak.Installation.new_user]
    if include_system:
        installation_factories.append(Flatpak.Installation.new_system)

    groups = []
    for installation_factory in installation_factories:
        try:
            installation = installation_factory()
            if installation is None:
                continue
            installation_path = installation.get_path().get_path()
        except GLib.Error as error:
            logging.warning("Could not access a Flatpak installation: %s", error)
            continue

        for ref in find_refs(installation):
            ref_app_id = ref.get_name()
            if app_id is not None and ref_app_id != app_id:
                continue

            arch = ref.get_arch()
            branch = ref.get_branch()
            metainfo = load_metainfo(installation_path, ref_app_id, arch, branch)
            manifest = _read_manifest_or_empty(
                installation_path, ref_app_id, arch, branch
            )
            if manifest is None:
                continue

            groups.append(
                CommandGroup(
                    app_id=ref_app_id,
                    app_name=get_pretty_name_from_metainfo(metainfo) or ref_app_id,
                    arch=arch,
                    branch=branch,
                    installation_path=installation_path,
                    commands=manifest_exported_commands(ref_app_id, manifest),
                )
            )
            if first_only:
                return groups

    return groups


class FlatpakCommandExporter:
    """Manage and inspect Flatpak command exports for the current user."""

    def __init__(self, config: AliasConfig | None = None) -> None:
        self.config = config if config is not None else AliasConfig()

    def get_exported_aliases(self) -> list[ExportedAlias]:
        return get_exported_aliases(self.config)

    def get_command_groups(
        self,
        app_id: str | None = None,
        *,
        include_system: bool = True,
        first_only: bool = False,
    ) -> list[CommandGroup]:
        return get_command_groups(
            app_id, include_system=include_system, first_only=first_only
        )

    def export_commands(self) -> None:
        return export_commands(self.config)

    def set_default_policy(self, policy: str) -> None:
        self.config.set_default_policy(policy)
        self.export_commands()

    def set_app_enabled(self, app_id: str, enabled: bool | None) -> None:
        self.config.set_app_enabled(app_id, enabled)
        self.export_commands()

    def set_alias_enabled(self, app_id: str, alias: str, enabled: bool) -> None:
        self.config.set_alias_enabled(app_id, alias, enabled)
        self.export_commands()

    def add_custom_alias(self, app_id: str, alias: str, command: str) -> None:
        self.config.set_custom_alias(app_id, alias, command)
        self.export_commands()

    def remove_custom_alias(self, app_id: str, alias: str) -> bool:
        removed = self.config.remove_custom_alias(app_id, alias)
        self.config.set_alias_enabled(app_id, alias, False)
        remove_launcher(alias)
        self.export_commands()
        return removed