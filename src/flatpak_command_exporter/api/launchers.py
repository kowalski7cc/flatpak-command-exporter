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
    content = COMMAND_TEMPLATE.format(
        BRANCH=shlex.quote(branch),
        ARCH=shlex.quote(arch),
        COMMAND=shlex.quote(command),
        APP_ID=shlex.quote(app_id),
    )
    logging.debug(
        "Creating launcher for %s alias %s at %s (arch: %s, branch: %s)",
        app_id,
        export,
        path,
        arch,
        branch,
    )
    _write_launcher(path, content)


def _write_launcher(path: Path, content: str) -> None:
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        logging.debug("Launcher at %s is already up to date", path)
    else:
        path.write_text(content, encoding="utf-8")
        logging.info("Wrote launcher at %s", path)
    path.chmod(0o755)


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
    _write_launcher(path, f"#!/bin/sh\nprintf '%s\\n' {message} >&2\nexit 127\n")
    logging.info("Created user mask for disabled system alias %s at %s", alias, path)


def _launcher_is_for_app(path: Path, app_id: str) -> bool:
    expected_suffix = f" --file-forwarding {shlex.quote(app_id)} \"$@\""
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeError:
        logging.warning("Ignoring non-text launcher at %s", path)
        return False
    return content.startswith("#!/bin/sh\n") and any(
        line.startswith("exec /usr/bin/flatpak run --branch=")
        and line.endswith(expected_suffix)
        for line in content.splitlines()
    )


def _get_app_launcher_aliases(directory: Path, app_id: str) -> set[str]:
    try:
        paths = list(directory.iterdir())
    except FileNotFoundError:
        return set()

    return {
        path.name
        for path in paths
        if path.is_file()
        and not path.is_symlink()
        and _launcher_is_for_app(path, app_id)
    }


def export_commands(
    config: AliasConfig | None = None,
    *,
    app_id: str | None = None,
    include_system: bool = True,
    scope: str | None = None,
    system: bool = False,
) -> None:
    """Export commands, reconciling stale launchers for an optional app ID."""
    if config is None:
        config = AliasConfig(
            scope="system" if system or scope == "system" else "user"
        )

    scope_name = getattr(config, "scope", "user")
    if scope is not None:
        scope_name = scope
    if system:
        scope_name = "system"
    if app_id is not None:
        config.app_path(app_id)
    logging.info("Exporting Flatpak commands for %s scope", scope_name)

    installed_refs = _get_installed_refs(
        scope=scope_name,
        include_system=include_system,
    )
    refs_by_app_id = _get_preferred_app_refs(installed_refs, scope_name)

    launchers: dict[str, tuple[str, str, str, str]] = {}
    disabled_aliases: set[str] = set()
    app_disabled_aliases: set[str] = set()
    app_aliases: set[str] = set()
    logging.info(
        "Preparing launchers for %d installed applications",
        len(refs_by_app_id),
    )

    for current_app_id, preferred_refs in refs_by_app_id.items():
        for installed_ref in preferred_refs:
            ref = installed_ref.ref
            manifest = _read_manifest_or_empty(
                installed_ref.installation_path,
                ref.get_name(),
                ref.get_arch(),
                ref.get_branch(),
            )
            custom_aliases = config.custom_aliases(current_app_id)
            if manifest is None and not custom_aliases:
                continue

            exported_commands = manifest_exported_commands(
                ref.get_name(), manifest or {}
            )
            exported_commands = {**exported_commands, **custom_aliases}
            for export, command in exported_commands.items():
                if current_app_id == app_id:
                    app_aliases.add(export)
                if not config.is_alias_enabled(current_app_id, export):
                    logging.debug(
                        "Skipping disabled alias %s for %s", export, current_app_id
                    )
                    disabled_aliases.add(export)
                    if current_app_id == app_id:
                        app_disabled_aliases.add(export)
                    continue
                launcher = (
                    current_app_id,
                    command,
                    ref.get_arch(),
                    ref.get_branch(),
                )
                logging.debug(
                    "Scheduling launcher for alias %s from %s", export, current_app_id
                )
                launchers.setdefault(export, launcher)
    removed_count = 0
    app_export_directory = (
        config.export_directory
        if getattr(config, "scope", "user") == scope_name
        else AliasConfig(scope=scope_name).export_directory
    )
    previous_app_aliases = (
        set()
        if app_id is None
        else _get_app_launcher_aliases(app_export_directory, app_id)
    )
    if app_id is None:
        aliases_to_remove = disabled_aliases - launchers.keys()
        aliases_to_mask = aliases_to_remove
        launchers_to_create = launchers
    else:
        affected_aliases = previous_app_aliases | app_aliases
        aliases_to_remove = (
            previous_app_aliases | app_disabled_aliases
        ) - launchers.keys()
        aliases_to_mask = app_disabled_aliases - launchers.keys()
        launchers_to_create = {
            alias: launchers[alias]
            for alias in affected_aliases
            if alias in launchers
            and (
                alias in previous_app_aliases
                or launchers[alias][0] == app_id
            )
        }
    system_export_directory = (
        AliasConfig(scope="system").export_directory
        if scope_name == "user" and aliases_to_remove
        else None
    )
    for export in aliases_to_remove:
        AliasConfig._validate_alias(export)
        if (
            scope_name == "user"
            and export in aliases_to_mask
            and system_export_directory is not None
            and (system_export_directory / export).is_file()
        ):
            _create_disabled_launcher(export)
        elif scope_name == "user":
            remove_launcher(export)
        else:
            remove_launcher(export, scope=scope_name)
        removed_count += 1
    for export, (launcher_app_id, command, arch, branch) in launchers_to_create.items():
        if scope_name == "user":
            create_launcher(launcher_app_id, export, command, arch, branch)
        else:
            create_launcher(
                launcher_app_id, export, command, arch, branch, scope=scope_name
            )
    logging.info(
        "Exported %d launchers and processed %d disabled aliases for %s scope",
        len(launchers_to_create),
        removed_count,
        scope_name,
    )
