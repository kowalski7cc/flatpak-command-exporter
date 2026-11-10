"""Generate and remove shell launchers for Flatpak application commands."""

import logging
import shlex
import textwrap
from pathlib import Path
from typing import Final

from ..config import AliasConfig
from .metadata import _read_manifest_or_empty, manifest_exported_commands
from .refs import _get_installed_refs, _get_preferred_app_refs


COMMAND_TEMPLATE: Final[str] = textwrap.dedent("""\
    #!/bin/sh
    for arg do shift
        if [ -e "$arg" ]; then
            set -- "$@" "@@" "$(readlink -f "$arg")" "@@"
        else
            set -- "$@" "$arg"
        fi
    done
    exec /usr/bin/flatpak run --branch={BRANCH} --arch={ARCH} --command={COMMAND} --file-forwarding {APP_ID} "$@"
    """)


def _launcher_path(alias: str, *, scope: str = "user") -> Path:
    AliasConfig._validate_alias(alias)
    config = AliasConfig(scope=scope)
    return config.export_directory / alias


def create_launcher(
    app_id: str,
    export: str,
    command: str,
    arch: str,
    branch: str,
    *,
    scope: str = "user",
) -> None:
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


def remove_launcher(export: str, *, scope: str = "user") -> None:
    path = _launcher_path(export, scope=scope)
    try:
        path.unlink()
    except FileNotFoundError:
        logging.debug("No existing launcher for alias %s at %s", export, path)
        pass
    else:
        logging.info("Removed launcher for alias %s at %s", export, path)


def _create_disabled_launcher(alias: str) -> None:
    path = _launcher_path(alias)
    path.parent.mkdir(parents=True, exist_ok=True)
    message = shlex.quote(
        f"Flatpak command {alias!r} is disabled by the user configuration."
    )
    path.write_text(
        f"#!/bin/sh\nprintf '%s\\n' {message} >&2\nexit 127\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    logging.info("Created user mask for disabled system alias %s at %s", alias, path)


def export_commands(
    config: AliasConfig | None = None,
    *,
    include_system: bool = True,
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

    installed_refs = _get_installed_refs(
        scope=scope_name,
        include_system=include_system,
    )
    refs_by_app_id = _get_preferred_app_refs(installed_refs, scope_name)

    launchers: dict[str, tuple[str, str, str, str]] = {}
    disabled_aliases: set[str] = set()
    logging.info(
        "Preparing launchers for %d installed applications",
        len(refs_by_app_id),
    )

    for app_id, preferred_refs in refs_by_app_id.items():
        for installed_ref in preferred_refs:
            ref = installed_ref.ref
            manifest = _read_manifest_or_empty(
                installed_ref.installation_path,
                ref.get_name(),
                ref.get_arch(),
                ref.get_branch(),
            )
            custom_aliases = config.custom_aliases(app_id)
            if manifest is None and not custom_aliases:
                continue

            exported_commands = manifest_exported_commands(
                ref.get_name(), manifest or {}
            )
            exported_commands = {**exported_commands, **custom_aliases}
            for export, command in exported_commands.items():
                if not config.is_alias_enabled(app_id, export):
                    logging.debug("Skipping disabled alias %s for %s", export, app_id)
                    disabled_aliases.add(export)
                    continue
                logging.debug("Scheduling launcher for alias %s from %s", export, app_id)
                launchers.setdefault(
                    export,
                    (
                        ref.get_name(),
                        command,
                        ref.get_arch(),
                        ref.get_branch(),
                    ),
                )

    removed_count = 0
    system_export_directory = (
        AliasConfig(scope="system").export_directory
        if scope_name == "user" and disabled_aliases
        else None
    )
    for export in disabled_aliases - launchers.keys():
        AliasConfig._validate_alias(export)
        if (
            scope_name == "user"
            and system_export_directory is not None
            and (system_export_directory / export).is_file()
        ):
            _create_disabled_launcher(export)
        elif scope_name == "user":
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
