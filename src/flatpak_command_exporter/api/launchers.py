"""Generate and remove shell launchers for Flatpak application commands."""

import logging
import shlex

import gi

from ..config import AliasConfig
from ..defaults import COMMAND_TEMPLATE
from .metadata import _read_manifest_or_empty, manifest_exported_commands
from .refs import find_refs, get_current_ref

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib


def _launcher_path(alias, *, scope="user"):
    AliasConfig._validate_alias(alias)
    config = AliasConfig(scope=scope)
    return config.export_directory / alias


def create_launcher(app_id, export, command, arch, branch, *, scope="user"):
    path = _launcher_path(export, scope=scope)
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.debug(
        "Creating launcher for %s alias %s at %s (arch: %s, branch: %s)",
        app_id,
        export,
        path,
        arch,
        branch,
    )
    path.write_text(
        COMMAND_TEMPLATE.format(
            BRANCH=shlex.quote(branch),
            ARCH=shlex.quote(arch),
            COMMAND=shlex.quote(command),
            APP_ID=shlex.quote(app_id),
        ),
        encoding="utf-8",
    )
    path.chmod(0o755)
    logging.info("Created launcher for alias %s at %s", export, path)


def remove_launcher(export, *, scope="user"):
    path = _launcher_path(export, scope=scope)
    try:
        path.unlink()
    except FileNotFoundError:
        logging.debug("No existing launcher for alias %s at %s", export, path)
        pass
    else:
        logging.info("Removed launcher for alias %s at %s", export, path)


def export_commands(
    config: AliasConfig | None = None,
    *,
    include_system: bool = False,
    scope: str | None = None,
    system: bool = False,
) -> None:
    """Export commands for the current ref of each installed Flatpak app."""
    if config is None:
        config = AliasConfig(
            scope="system" if system or scope == "system" else "user"
        )

    scope_name = getattr(config, "scope", "user")
    if scope is not None:
        scope_name = scope
    if system:
        scope_name = "system"
    logging.info("Exporting Flatpak commands for %s scope", scope_name)

    installation_factories: list[object] = []
    if scope_name == "system":
        installation_factories = [Flatpak.Installation.new_system]
    else:
        installation_factories = [Flatpak.Installation.new_user]
        if include_system:
            installation_factories.append(Flatpak.Installation.new_system)

    refs_by_app_id: dict[str, object] = {}
    launchers: dict[str, tuple[str, str, str, str]] = {}
    disabled_aliases: set[str] = set()

    for installation_factory in installation_factories:
        logging.debug("Collecting refs from a Flatpak installation")
        installation = installation_factory()
        if installation is None:
            continue
        for ref in find_refs(installation):
            refs_by_app_id[ref.get_name()] = ref
    logging.info(
        "Preparing launchers for %d installed applications",
        len(refs_by_app_id),
    )

    for app_id, fallback_ref in refs_by_app_id.items():
        install_factory = (
            Flatpak.Installation.new_system
            if scope_name == "system"
            else Flatpak.Installation.new_user
        )
        installation = install_factory()
        if installation is None:
            continue
        installation_path = installation.get_path().get_path()
        ref = get_current_ref(installation, app_id, fallback_ref)

        manifest = _read_manifest_or_empty(
            installation_path, ref.get_name(), ref.get_arch(), ref.get_branch()
        )
        if manifest is None:
            continue

        exported_commands = manifest_exported_commands(ref.get_name(), manifest)
        exported_commands = {**exported_commands, **config.custom_aliases(app_id)}
        for export, command in exported_commands.items():
            if not config.is_alias_enabled(app_id, export):
                logging.debug("Skipping disabled alias %s for %s", export, app_id)
                disabled_aliases.add(export)
                continue
            logging.debug("Scheduling launcher for alias %s from %s", export, app_id)
            launchers[export] = (
                ref.get_name(),
                command,
                ref.get_arch(),
                ref.get_branch(),
            )

    removed_count = 0
    for export in disabled_aliases - launchers.keys():
        if scope_name == "user":
            remove_launcher(export)
        else:
            remove_launcher(export, scope=scope_name)
        removed_count += 1
    for export, (app_id, command, arch, branch) in launchers.items():
        if scope_name == "user":
            create_launcher(app_id, export, command, arch, branch)
        else:
            create_launcher(app_id, export, command, arch, branch, scope=scope_name)
    logging.info(
        "Exported %d launchers and processed %d disabled aliases for %s scope",
        len(launchers),
        removed_count,
        scope_name,
    )
