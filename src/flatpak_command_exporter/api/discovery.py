"""Discover aliases and command groups from installed Flatpak refs."""

import logging

from ..config import AliasConfig
from .metadata import (
    _read_manifest_or_empty,
    get_desktop_id_from_metainfo,
    get_pretty_name_from_metainfo,
    load_metainfo,
    manifest_exported_commands,
)
from .models import CommandGroup, ExportedAlias
from .refs import _get_installed_refs, _get_preferred_app_refs


def get_exported_aliases(
    config: AliasConfig | None = None,
    *,
    include_system: bool = True,
    scope: str | None = None,
    system: bool = False,
    current_only: bool = False,
) -> list[ExportedAlias]:
    """Return aliases, optionally limited to each app's preferred current ref."""
    logging.info("Discovering exported Flatpak aliases")
    aliases: list[ExportedAlias] = []
    if config is None:
        scope_name = "system" if system else (scope or "user")
        config = AliasConfig(scope=scope_name)
    else:
        scope_name = getattr(config, "scope", "user")
        if scope is not None:
            scope_name = scope
        if system:
            scope_name = "system"
        if scope_name != getattr(config, "scope", "user"):
            config = AliasConfig(scope=scope_name)

    system_config = config
    if scope_name != "system" and include_system:
        system_config = AliasConfig(scope="system")

    installed_refs = _get_installed_refs(
        scope=scope_name,
        include_system=include_system,
    )
    if current_only:
        installed_refs = [
            refs[0]
            for refs in _get_preferred_app_refs(installed_refs, scope_name).values()
        ]

    for installed_ref in installed_refs:
        ref = installed_ref.ref
        app_id = ref.get_name()
        installation_config = config if installed_ref.scope == "user" else system_config
        arch = ref.get_arch()
        branch = ref.get_branch()

        manifest = _read_manifest_or_empty(
            installed_ref.installation_path, app_id, arch, branch
        )
        if manifest is None:
            continue

        metainfo = load_metainfo(installed_ref.installation_path, app_id, arch, branch)
        app_name = get_pretty_name_from_metainfo(metainfo) or app_id
        desktop_id = get_desktop_id_from_metainfo(metainfo, app_id)
        commands = manifest_exported_commands(app_id, manifest)
        custom_aliases = installation_config.custom_aliases(app_id)
        commands = {**commands, **custom_aliases}
        logging.debug(
            "Found %d command aliases for %s in %s scope",
            len(commands),
            app_id,
            installed_ref.scope,
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
                    installation_path=installed_ref.installation_path,
                    desktop_id=desktop_id,
                    installation_scope=installed_ref.scope,
                    enabled=installation_config.is_alias_enabled(app_id, alias),
                    configurable=installed_ref.scope == "user",
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
    arch: str | None = None,
    branch: str | None = None,
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
    groups = []
    for installed_ref in _get_installed_refs(
        scope=scope_name,
        include_system=include_system,
    ):
        ref = installed_ref.ref
        ref_app_id = ref.get_name()
        ref_arch = ref.get_arch()
        ref_branch = ref.get_branch()
        if app_id is not None and ref_app_id != app_id:
            continue
        if arch is not None and ref_arch != arch:
            continue
        if branch is not None and ref_branch != branch:
            continue

        metainfo = load_metainfo(
            installed_ref.installation_path,
            ref_app_id,
            ref_arch,
            ref_branch,
        )
        manifest = _read_manifest_or_empty(
            installed_ref.installation_path,
            ref_app_id,
            ref_arch,
            ref_branch,
        )
        if manifest is None:
            continue

        groups.append(
            CommandGroup(
                app_id=ref_app_id,
                app_name=get_pretty_name_from_metainfo(metainfo) or ref_app_id,
                arch=ref_arch,
                branch=ref_branch,
                installation_path=installed_ref.installation_path,
                commands=manifest_exported_commands(ref_app_id, manifest),
            )
        )
        if first_only:
            logging.info("Found a command group for %s", ref_app_id)
            return groups

    logging.info("Found %d Flatpak command groups", len(groups))
    return groups
