# Developer guide

This guide covers using Flatpak Command Exporter as a Python library and
automating it from Bash. For installation, end-user behavior, and the complete
command reference, see [README.md](./README.md).

## Requirements and installation

The package requires Python 3.13 or newer, Flatpak, PyGObject, and the Flatpak
GObject introspection bindings. GTK 4 and libadwaita are only required for the
Flatlink GUI.

After installing the operating-system packages that provide PyGObject and the
Flatpak introspection bindings, install the project in an active Python
environment:

```console
python -m pip install flatpak-command-exporter
```

For development from a checkout:

```console
python -m pip install -e .
```

To regenerate the static Bash completion after changing the shared
`argparse` definition, install the build-time `shtab` tool and run:

```console
make completion
```

The generated file is written to `build/bash-completion/flatshell`; package
builds install it under `/usr/share/bash-completion/completions/`. It does not
run Python when completing commands interactively.

The installed `flatshell` command is the recommended interface for shell
scripts. From a source checkout, the equivalent entry point is:

```console
python -m flatpak_command_exporter --help
```

## Python API

The package exports `FlatpakCommandExporter`, `ExportedAlias`, and
`CommandGroup` from `flatpak_command_exporter`. Construct an exporter to inspect
installed apps and aliases:

```python
from flatpak_command_exporter import FlatpakCommandExporter

exporter = FlatpakCommandExporter()

# Includes aliases for user-installed and system-installed apps.
for alias in exporter.get_exported_aliases():
    scope = alias.installation_scope
    state = "enabled" if alias.enabled else "disabled"
    print(f"{alias.app_name}: {alias.alias} -> {alias.command} [{scope}, {state}]")

# Groups contain manifest commands for each discovered ref.
for group in exporter.get_command_groups(include_system=True):
    print(f"{group.app_name} ({group.app_id}, {group.branch}/{group.arch})")
    for name, command in group.commands.items():
        print(f"  {name} -> {command}")
```

The implementation is split across `flatpak_command_exporter.api` modules for
models, discovery, metadata, launcher operations, and the exporter facade.
Existing imports from `flatpak_command_exporter.application` remain supported;
new integrations should import the public types from the package root or
`flatpak_command_exporter.api`.

`ExportedAlias` records include `alias`, `command`, `app_id`, `app_name`,
`arch`, `branch`, `installation_path`, `desktop_id`, and the `enabled`,
`configurable`, and `custom` flags. A user-installed ref takes precedence over
a system-installed ref with the same app ID in `get_exported_aliases()`.

`get_command_groups()` accepts an optional app ID filter and keyword options.
The default includes user and system refs, with user refs taking priority when
the same app ID, architecture, and branch are installed in both scopes. Use
`scope`, `arch`, or `branch` to narrow discovery. For example, restrict
discovery to user-installed refs:

```python
groups = exporter.get_command_groups(
    "org.gimp.GIMP",
    include_system=False,
    branch="stable",
)
```

### Changing settings

The exporter methods for changing settings save the configuration and refresh
generated launchers:

```python
exporter.set_default_policy("none")  # "all" or "none"
exporter.set_app_enabled("org.gimp.GIMP", True)
exporter.set_alias_enabled("org.gimp.GIMP", "gimp", True)
exporter.add_custom_alias("org.gimp.GIMP", "my-gimp", "gimp")
```

To remove a custom alias, the API removes it, disables that alias, and refreshes
launchers:

```python
was_custom_alias_removed = exporter.remove_custom_alias(
    "org.gimp.GIMP", "my-gimp"
)
```

`remove_custom_alias()` returns whether the custom alias existed. To refresh
all launchers after installing or updating a Flatpak, call `export_commands()`.
Pass an app ID to reconcile that app's launchers, including stale aliases left
by updates or removal, while leaving unrelated launchers untouched:

```python
exporter.export_commands()
exporter.export_commands("org.gimp.GIMP")
```

The convenience methods can raise `OSError` or `ValueError` for filesystem or
configuration problems. Handle those at the application boundary and report
the failure rather than treating an unsuccessful save or export as success:

```python
try:
    exporter.set_alias_enabled("org.gimp.GIMP", "gimp", True)
except (OSError, ValueError) as error:
    raise SystemExit(f"Could not update Flatpak command exports: {error}") from error
```

### Full API reference and advanced usage

The package root exports `FlatpakCommandExporter`, `ExportedAlias`, and
`CommandGroup`. The functions below are available from
`flatpak_command_exporter.api`:

```python
from flatpak_command_exporter.api import (
    EXPORT_SCHEMA_NAMES,
    create_launcher,
    export_commands,
    find_refs,
    get_command_groups,
    get_current_ref,
    get_desktop_id_from_metainfo,
    get_exported_aliases,
    get_pretty_name_from_metainfo,
    get_version_from_metainfo,
    load_manifest,
    load_metainfo,
    manifest_exported_commands,
    remove_launcher,
)
```

#### Scope-aware discovery

Use the module-level discovery functions when you want to call one operation
without keeping an exporter object. They return the same frozen result models
as the object methods:

```python
groups = get_command_groups(
    app_id="org.gimp.GIMP",
    include_system=False,
    arch="x86_64",
    branch="stable",
)
aliases = get_exported_aliases(current_only=True)
```

`get_command_groups()` accepts an optional app ID, `include_system`,
`first_only`, `scope`, `system`, `arch`, and `branch`. By default it checks
both installations and prefers user refs when the same app, architecture, and
branch exist in both. `include_system=False` limits it to user refs;
`scope="system"` (or `system=True`) limits it to the system installation.
`scope="user"` preserves the default behavior, including system refs unless
`include_system=False` is also passed. `first_only=True` returns the first
matching group rather than all matches.

`get_exported_aliases()` accepts `include_system`, `scope`, `system`, and
`current_only`. By default it applies the current user's alias settings and
includes system-installed apps. `scope="system"` returns system aliases using
system configuration; `current_only=True` returns only each app's preferred
current ref. Each `ExportedAlias` also reports the installation scope via
`installation_scope`; `configurable` is a settings capability flag, not a
scope identifier.

#### Settings and configuration

Construct `FlatpakCommandExporter(scope="system")` to use system configuration
for settings and exports. Alternatively, pass an `AliasConfig` from
`flatpak_command_exporter.config`. Its `data_home` parameter is useful for
isolated user configuration and also sets the corresponding launcher
directory:

```python
from flatpak_command_exporter import FlatpakCommandExporter
from flatpak_command_exporter.config import AliasConfig

config = AliasConfig(data_home="/tmp/flatpak-exporter-data")
exporter = FlatpakCommandExporter(config=config)
```

`set_default_policy()` accepts only `"all"` or `"none"`. App-level overrides
accept `True`, `False`, or `None` (`None` clears the override); alias-level
overrides accept `True` or `False`. `add_custom_alias()` stores a non-empty
single-line command and enables the alias. These exporter methods save their
changes and refresh launchers. `remove_custom_alias()` returns whether the
custom definition existed; it removes the definition, disables the alias, and
refreshes. `export_commands()` refreshes launchers without changing settings.

For applications that need to manage configuration separately from launcher
refresh, `AliasConfig` is also usable directly. It exposes `default_policy()`,
`set_default_policy()`, `app_enabled()`, `set_app_enabled()`,
`alias_enabled()`, `set_alias_enabled()`, `set_aliases_enabled()`,
`custom_aliases()`, `set_custom_alias()`, `remove_custom_alias()`, and
`is_alias_enabled()`. Writes can raise `OSError` or `AliasConfigError`
(`ValueError`); direct `AliasConfig` writes do not refresh launchers, so call
`exporter.export_commands()` after changing settings.

System-scope configuration and launcher writes generally require elevated
filesystem permissions. A custom user `data_home` changes the user settings
and launcher paths, but does not redirect Flatpak discovery to another
installation.

#### Manifest and metainfo helpers

The examples below use a discovered command group. Check that discovery
returned a result before selecting one:

```python
groups = get_command_groups("org.gimp.GIMP")
if not groups:
    raise RuntimeError("No command group found for org.gimp.GIMP")
group = groups[0]
```

`load_manifest(base_path, app_id, arch, branch)` reads the installed ref's
`manifest.json` and returns the decoded JSON value. It can raise
`FileNotFoundError`, other `OSError`s, or `json.JSONDecodeError`; validate the
decoded shape before passing it to `manifest_exported_commands()`:

```python
manifest = load_manifest(
    group.installation_path, group.app_id, group.arch, group.branch
)
if not isinstance(manifest, dict):
    raise ValueError("Flatpak manifest must contain a JSON object")
commands = manifest_exported_commands(group.app_id, manifest)
```

`manifest_exported_commands(app_id, manifest)` returns the commands selected
from the manifest and the application's built-in defaults. The recognized
manifest keys are in `EXPORT_SCHEMA_NAMES`.

`load_metainfo(base_path, app_id, arch, branch)` parses the installed XML
metainfo and returns its root element, or `None` when the file is absent or
cannot be parsed. The accessors accept that optional element:

```python
metainfo = load_metainfo(
    group.installation_path, group.app_id, group.arch, group.branch
)
name = get_pretty_name_from_metainfo(metainfo) or group.app_id
desktop_id = get_desktop_id_from_metainfo(metainfo, group.app_id)
version = get_version_from_metainfo(metainfo)
```

The display-name and version accessors return `str | None`. The desktop-ID
accessor returns the metainfo launchable desktop ID when present, otherwise
`<app_id>.desktop`.

#### Launcher and Flatpak ref helpers

`create_launcher(app_id, export, command, arch, branch, *, scope="user")`
creates an executable launcher; `remove_launcher(export, *, scope="user")`
removes it. These operate directly on launcher files and do not update
configuration. Use `export_commands(config, ...)` for the normal operation
that applies configured policies and refreshes the selected scope:

```python
exporter.export_commands()
exporter.export_commands("org.gimp.GIMP")
export_commands(app_id="org.gimp.GIMP")
# Direct launcher operations are available when deliberately managing a file:
create_launcher("org.gimp.GIMP", "my-gimp", "gimp", "x86_64", "stable")
remove_launcher("my-gimp")
```

Both launcher functions accept `scope="system"` to target system launchers.
Creating a system launcher requires appropriate permissions. Quote and validate
values through the launcher helper rather than constructing shell scripts
yourself: it validates alias names and safely quotes the command arguments.
Only use custom commands you trust.

`find_refs(installation)` and `get_current_ref(installation, app_id,
fallback_ref)` are lower-level helpers for callers already working with a
Flatpak installation object. They require the Flatpak introspection bindings:

```python
import gi

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak

installation = Flatpak.Installation.new_user()
if installation is None:
    raise RuntimeError("Could not open the user Flatpak installation")
refs = list(find_refs(installation))
if refs:
    current_ref = get_current_ref(
        installation, refs[0].get_name(), refs[0]
    )
```

`find_refs()` yields installed application refs, and `get_current_ref()`
returns the current installed ref for an app or the supplied fallback. Most
integrations should prefer `get_command_groups()` or
`get_exported_aliases()` instead.

In Flatlink, the main-window app switch enables or disables all discovered
commands for that app together by writing per-alias settings. It does not
change the app-level override. The Settings factory reset restores the default
export policy and clears app-level and per-alias enable/disable settings;
custom alias definitions are preserved.

### Configuration location

By default, user configuration is stored in
`${XDG_DATA_HOME:-$HOME/.local/share}/flatpak/aliases/` and generated user
launchers are stored in `${XDG_DATA_HOME:-$HOME/.local/share}/flatpak-commands/`.
System-scoped configuration uses the default system Flatpak installation path
reported by `Flatpak.Installation.new_system()` (normally
`/var/lib/flatpak/aliases/`); system launchers are stored in the sibling
`flatpak-commands/` directory (normally `/var/lib/flatpak-commands/`).
System-scope CLI operations use the system installation by default and write
directly to its configuration and launcher paths, so run them with elevated
filesystem permissions. Use `--user` to limit CLI changes to the current user;
Flatlink always stores changes in user configuration.

For tests or tools that need a separate user configuration and launcher
directory, pass an `AliasConfig`:

```python
from flatpak_command_exporter import FlatpakCommandExporter
from flatpak_command_exporter.config import AliasConfig

config = AliasConfig(data_home="/tmp/flatpak-exporter-data")
exporter = FlatpakCommandExporter(config=config)

system_config = AliasConfig(scope="system")
exporter_for_system = FlatpakCommandExporter(config=system_config)
```

`AliasConfig(data_home=...)` changes both user configuration and launcher
locations. Without a custom `data_home`, the user paths use
`${XDG_DATA_HOME:-$HOME/.local/share}`. System-scope paths are derived from the
default system Flatpak installation.

### Automatic Flatpak export refresh

Debian, RPM, and Arch packages install system and user systemd watcher services.
The watcher code lives in `src/flatpak_command_exporter/service/`; unit sources
live in the top-level `service/` directory. Package manifests install the
system watcher to run as root and the user watcher in each user's session.
They monitor Flatpak app, architecture, and branch directories and debounce
deployment events before exporting the affected app ID through the Python API.
The system service writes system-scope exports only. The user service writes
that user's exports and also watches system deployments so user overrides for
system-installed apps stay current. App-scoped export reconciliation removes
stale aliases after updates and removals while preserving aliases supplied by
other apps.

Service presets enable both watchers by default. Do not reintroduce the old
periodic timer units. Keep watcher code, unit files, package manifests,
documentation, and service regression tests synchronized when changing this
integration.

## Shell CLI

Commands that update settings also regenerate launchers for the selected scope:

```bash
flatshell list --all
flatshell list org.gimp.GIMP
flatshell list --all --complete

flatshell config default-export none --user
flatshell enable org.gimp.GIMP gimp --user
flatshell disable org.gimp.GIMP --user

flatshell add org.gimp.GIMP my-gimp gimp --user
flatshell remove org.gimp.GIMP my-gimp --user
flatshell export --user
sudo flatshell export
flatshell install-profile --user
sudo flatshell install-profile --system
```

Use `flatshell --help` and `flatshell COMMAND --help` for current command
options. Listing output is designed for people; it is not a stable
machine-readable format. For structured data, use the Python API rather than
parsing `flatshell list` output.

## Bash script example

This script takes an app ID, exported alias, and Flatpak command, then adds or
replaces that custom alias. Arguments are quoted so spaces and shell
metacharacters are not re-interpreted by Bash:

```bash
#!/usr/bin/env bash
set -euo pipefail

if (($# != 3)); then
    printf 'Usage: %s APP_ID ALIAS FLATPAK_COMMAND\n' "$0" >&2
    exit 2
fi

app_id=$1
alias_name=$2
flatpak_command=$3

if ! command -v flatshell >/dev/null 2>&1; then
    printf 'flatshell is not installed or is not on PATH\n' >&2
    exit 127
fi

if ! flatshell add "$app_id" "$alias_name" "$flatpak_command"; then
    printf 'Could not add alias %s for %s\n' "$alias_name" "$app_id" >&2
    exit 1
fi

printf 'Added and exported %s for %s\n' "$alias_name" "$app_id"
```

Save it as `add-flatpak-alias`, make it executable with
`chmod +x add-flatpak-alias`, then run:

```console
./add-flatpak-alias org.gimp.GIMP my-gimp gimp
```

The command passed as `FLATPAK_COMMAND` is written into a generated launcher;
only use commands you trust. Use `flatshell export` to explicitly refresh all
enabled launchers after installing a Flatpak. Check the command's exit status
to detect errors; do not infer success solely from its output.

## Typing

The package requires Python 3.13 or newer and publishes inline annotations
through its partial PEP 561 marker. Use built-in collection generics and union
syntax, and prefer concrete types or `object` over `Any`. Reserve `Any` for
dynamic PyGObject/Flatpak boundaries where the dependency provides no resolvable
static type; leave a boundary unannotated rather than guessing at GTK or
Flatpak contracts.

## Development checks

For GUI changes, provide accessible names for icon-only controls, preserve
keyboard and focus behavior, and add regression tests for interactions when
possible. Keep README.md and both contributor guides aligned with changes to
user workflows or development conventions.

Run the unit tests and whitespace validation from the repository root:

```console
python -m unittest discover -s tests -v
git diff --check
```

RPM packaging targets Fedora 44 and 45. Build it from the checkout with:

```console
make rpm
```

Prepare release changelog entries for Debian, RPM, and AppStream with:

```console
make release
```

The individual `make changelog`, `make spec`, and `make metainfo` targets are
available as well. Set `SOURCE_DATE_EPOCH` to use a reproducible date when
creating new entries.
