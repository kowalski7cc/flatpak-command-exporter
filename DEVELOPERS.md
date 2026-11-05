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
    scope = "user" if alias.configurable else "system"
    state = "enabled" if alias.enabled else "disabled"
    print(f"{alias.app_name}: {alias.alias} -> {alias.command} [{scope}, {state}]")

# Groups contain manifest commands for each discovered ref.
for group in exporter.get_command_groups(include_system=True):
    print(f"{group.app_name} ({group.app_id}, {group.branch}/{group.arch})")
    for name, command in group.commands.items():
        print(f"  {name} -> {command}")
```

`ExportedAlias` records include `alias`, `command`, `app_id`, `app_name`,
`arch`, `branch`, `installation_path`, `desktop_id`, and the `enabled`,
`configurable`, and `custom` flags. A user-installed ref takes precedence over
a system-installed ref with the same app ID in `get_exported_aliases()`.

`get_command_groups()` accepts an optional app ID filter and keyword options.
For example, restrict discovery to user-installed refs:

```python
groups = exporter.get_command_groups(
    "org.gimp.GIMP",
    include_system=False,
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
launchers after installing or updating a Flatpak, call:

```python
exporter.export_commands()
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

### Configuration location

By default, user configuration is stored in
`${XDG_DATA_HOME:-$HOME/.local/share}/flatpak/aliases/` and generated user
launchers are stored in `${XDG_DATA_HOME:-$HOME/.local/share}/flatpak-commands/`.
System-scoped configuration uses `/usr/lib/flatpak/aliases/` and system
launchers use `/usr/share/flatpak-commands/`. System mutations go through the
root-owned system-bus helper, which authorizes each operation through PolicyKit.

For configuration-only tests or tools that need a separate settings directory,
pass an `AliasConfig`:

```python
from flatpak_command_exporter import FlatpakCommandExporter
from flatpak_command_exporter.config import AliasConfig

config = AliasConfig(data_home="/tmp/flatpak-exporter-data")
exporter = FlatpakCommandExporter(config=config)

system_config = AliasConfig(scope="system")
exporter_for_system = FlatpakCommandExporter(config=system_config)
```

Changing the configuration location does not change the launcher's location:
user launchers still use `XDG_DATA_HOME` (or the default user data directory),
while system launchers use the system export path. Set `XDG_DATA_HOME` if a
custom user data directory should be used.

## Shell CLI

Commands that update settings also regenerate launchers for the selected scope:

```bash
flatshell list --all
flatshell list org.gimp.GIMP
flatshell list --all --complete

flatshell config default-export none
flatshell enable org.gimp.GIMP gimp
flatshell disable org.gimp.GIMP

flatshell add org.gimp.GIMP my-gimp gimp
flatshell add --system org.example.App my-command command
flatshell remove org.gimp.GIMP my-gimp
flatshell export
flatshell export --system
flatshell install-profile --user
flatshell install-profile --system
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

## Development checks

Run the unit tests and whitespace validation from the repository root:

```console
python -m unittest discover -s tests -v
git diff --check
```

RPM packaging targets Fedora 44 and 45. Build it from the checkout with:

```console
make rpm
```
