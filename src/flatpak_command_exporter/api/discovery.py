"""Discover aliases and command groups from installed Flatpak refs."""

import logging

import gi

from ..config import AliasConfig
from .metadata import (
    _read_manifest_or_empty,
    get_desktop_id_from_metainfo,
    get_pretty_name_from_metainfo,
    load_metainfo,
    manifest_exported_commands,
)
from .models import CommandGroup, ExportedAlias
from .refs import find_refs, get_current_ref

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib


def get_exported_aliases(
    config: AliasConfig | None = None,
    *,
    include_system: bool = True,
    scope: str | None = None,
    system: bool = False,
) -> list[ExportedAlias]:
    """Return aliases from current user and system app refs, preferring user refs."""
    logging.info("Discovering exported Flatpak aliases")
    aliases: list[ExportedAlias] = []
    seen_app_ids: set[str] = set()
    if config is None:
        config = AliasConfig(scope=("system" if system else "user") if scope is None else scope)

    scope_name = getattr(config, "scope", "user")
    if scope is not None:
        scope_name = scope
    if system:
        scope_name = "system"

    system_config = config
    if scope_name != "system" and include_system:
        system_config = AliasConfig(scope="system")

    installations: list[tuple[bool, object]] = []
    if scope_name == "system":
        installations = [(False, Flatpak.Installation.new_system)]
    else:
        installations = [(True, Flatpak.Installation.new_user)]
        if include_system:
            installations.append((False, Flatpak.Installation.new_system))

    for is_user_installation, installation_factory in installations:
        installation_scope = "user" if is_user_installation else "system"
        logging.debug("Inspecting %s Flatpak installation", installation_scope)
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
            installation_config = config if is_user_installation else system_config
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
            custom_aliases = installation_config.custom_aliases(app_id)
            commands = {**commands, **custom_aliases}
            logging.debug(
                "Found %d command aliases for %s in %s scope",
                len(commands),
                app_id,
                installation_scope,
            )
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
                        installation_scope=(
                            "user" if is_user_installation else "system"
                        ),
                        enabled=installation_config.is_alias_enabled(app_id, alias),
                        configurable=is_user_installation,
                        custom=alias in custom_aliases,
                    )
                )

    logging.info("Discovered %d exported Flatpak aliases", len(aliases))
    return aliases


def get_command_groups(
    app_id: str | None = None,
    include_system: bool = True,
    first_only: bool = False,
    *,
    scope: str | None = None,
    system: bool = False,
) -> list[CommandGroup]:
    """Return exported commands grouped by installed application ref."""
    scope_name = "system" if system else (scope or "user")
    logging.info("Listing Flatpak command groups for %s scope", scope_name)
    logging.debug(
        "Command-group filters: app_id=%r, include_system=%s, first_only=%s",
        app_id,
        include_system,
        first_only,
    )
    installation_factories = [Flatpak.Installation.new_user]
    if scope_name == "system":
        installation_factories = [Flatpak.Installation.new_system]
    elif include_system:
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
                logging.info("Found a command group for %s", ref_app_id)
                return groups

    logging.info("Found %d Flatpak command groups", len(groups))
    return groups
