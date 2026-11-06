# Flatpak Command Exporter

**Make command-line tools shipped inside your Flatpaks available from your
terminal.**

Flatpak Command Exporter discovers commands declared by installed Flatpak
applications and creates small launchers in your user data directory. Use
**`flatshell`** to inspect and configure exports, or **Flatlink** to manage
aliases in a graphical interface.

> **Scope:** The exporter supports both user and system scopes. User
> configuration and launchers live under `${XDG_DATA_HOME:-$HOME/.local/share}`
> and system alias configuration lives in the default system Flatpak
> installation's `aliases/` directory (normally `/var/lib/flatpak/aliases/`).
> System launchers are written beside that installation (normally
> `/var/lib/flatpak-commands/`) and require elevated filesystem permissions.
> Flatlink only changes user configuration, including when managing system-app
> refs. System-scope `flatshell` changes operate directly and require elevated
> filesystem permissions; use `--user` for per-user changes.

## What you can do

- Export commands declared in an app's Flatpak manifest, including
  `x-export-commands` and `export-commands`.
- Choose whether aliases are exported by default, then override that choice for
  individual apps or aliases.
- Keep system-wide command export disabled by default; user overrides take
  precedence over system launchers.
- Add your own aliases for commands inside user- or system-installed Flatpaks.
- Search and toggle apps and aliases in Flatlink.
- Refresh user command exports from Flatlink after installing an app.
- Periodically refresh user and system exports with scope-specific systemd timers.
- Keep generated launchers on your `PATH` using the included profile script.

## Quick start

After installing a package, open a new login session so the profile script can
add user and system launcher directories to `PATH`. Then list available aliases
and export them:

```console
flatshell list --all
flatshell export --user
```

Run an exported command by its alias, just as you would run any other command:

```console
gimp
```

Use `flatlink` to browse and toggle aliases with the GUI. Settings changed in
either the GUI or the CLI are saved and the corresponding export scope is
refreshed. The Debian, RPM, and Arch packages also install Bash completion for
`flatshell`; it is loaded automatically when `bash-completion` is enabled.

## Install

### Debian package

The project builds two Debian packages: `flatpak-command-exporter` for the
library, CLI, and profile integration, and `flatpak-command-exporter-gui` for
Flatlink. To build both from a source checkout, install the build dependencies
listed in `debian/control`, then run:

```console
make deb
```

The resulting `.deb` files are written to the parent directory. Install the
core package and, if desired, the GUI package with your package manager. The
core package installs `flatpak-exported-commands.sh` into `/etc/profile.d/`;
start a new login session after installation for the `PATH` change to take
effect. Non-Debian installations can run `flatshell install-profile --user` to
set up shell integration for the current user, or
`sudo flatshell install-profile --system` to install it in `/etc/profile.d/`.
The user installation updates
`~/.profile` and applies to login shells that read that file.

### Fedora RPM

On Fedora 44 or 45, install the RPM build and project dependencies, then build
directly from the source checkout:

```console
sudo dnf install flatpak-devel gtk4 libadwaita make \
  pyproject-rpm-macros python3-devel python3-gobject python3-shtab \
  systemd-rpm-macros \
  python3-pip python3-setuptools rpm-build
make rpm
```

The spec derives its version from `pyproject.toml` and builds a core RPM plus
an optional `flatpak-command-exporter-gui` RPM. `rpmbuild` writes the packages
under `~/rpmbuild/RPMS/noarch/` by default.

### Arch Linux

On Arch Linux, install the packaging tools and dependencies used by both
packages, then build the core package and optional GUI package from a source
checkout:

```console
sudo pacman -S --needed base-devel flatpak git gtk4 hicolor-icon-theme \
  libadwaita python python-gobject python-shtab
make apk
```

The resulting `.pkg.tar.zst` packages are written to the repository root.
Install the core package and, if desired, the GUI package with `pacman -U`.
The PKGBUILD installs the system and user systemd timer units and their
presets. Enable the timers for the scopes you want:

```console
sudo systemctl enable --now flatpak-command-exporter-system.timer
systemctl --user enable --now flatpak-command-exporter-user.timer
```

### Development containers

The `.devcontainer/` directory includes configurations for Fedora 45 RPM in
`.devcontainer/fedora/`, Arch Linux PKGBUILD/makepkg in `.devcontainer/arch/`,
and Debian 13 (trixie) package development in `.devcontainer/debian-trixie/`.
In VS Code, reopen the repository in a container and choose the desired
configuration. The Debian container supports `make deb`; the Arch container
includes `base-devel`, `namcap`, and `python-shtab` for `make apk`.

### Requirements

- Flatpak and Python 3.13 or newer.
- PyGObject and the Flatpak GObject introspection bindings for the CLI and
  exporter.
- systemd for periodic export refresh.
- System-scope CLI operations require elevated filesystem permissions. Debian,
  Fedora, and Arch packages install separate system and user refresh timers.
- GTK 4, libadwaita, and their introspection data to run Flatlink.

### Automatic export refresh

The Debian and RPM packages install and enable separate systemd timers for the
default system and per-user Flatpak installations. Each timer first runs 15
minutes after boot and then once per day. The system service runs the direct
system-scope export as root; each user's service runs `flatshell export --user`
in that user's session. Each service refreshes only its own scope. Arch
packages install the same timer units and presets; enable the timers manually
as described in the Arch Linux installation section.

The timers refresh periodically rather than reacting to individual Flatpak
changes, so a newly installed app may not be exported until the next scheduled
refresh. To disable the system timer:

```console
sudo systemctl disable --now flatpak-command-exporter-system.timer
```

To disable the per-user timer (the package enables it by default for user
sessions):

```console
systemctl --user mask --now flatpak-command-exporter-user.timer
```

Undo the user mask and start the timer again with:

```console
systemctl --user unmask flatpak-command-exporter-user.timer
systemctl --user start flatpak-command-exporter-user.timer
```

## CLI

The supported commands are `flatshell` for the CLI and `flatlink` for the GUI.

### Inspect and export

```console
# List refs for an app across user and system installations
flatshell list org.gimp.GIMP

# List aliases for all discovered user and system refs
flatshell list --all

# Limit listing to refs in one installation
flatshell list --all --user
flatshell list --all --system

# Include the Flatpak command behind each alias
flatshell list --all --complete

# Generate or refresh enabled user launchers for user and system refs
flatshell export --user

# Generate or refresh system launchers (system scope is the default)
sudo flatshell export
```

### Configure defaults and apps

New user configurations enable aliases by default; new system configurations
disable them by default. System scope is the CLI default and requires root;
add `--user` for per-user settings:

```console
sudo flatshell config default-export all
flatshell config default-export none --user
```

Enable or disable every alias for one app, or override a single alias:

```console
# User app-level setting
flatshell enable org.gimp.GIMP --user
flatshell disable org.gimp.GIMP --user

# User alias-level setting
flatshell enable org.gimp.GIMP gimp --user
flatshell disable org.gimp.GIMP gimp --user
```

System settings are the default; pass `--user` to change the current user's
settings. System changes write configuration and launchers directly, so run
`flatshell` with the required elevated permissions.

### Add a custom alias

Custom aliases map a new command name to a command available inside an
installed Flatpak. System scope is the default; use `--user` for user settings.
System changes require elevated permissions:

```console
flatshell add org.gimp.GIMP my-gimp gimp --user
sudo flatshell add org.example.App my-command command
```

Remove a custom alias and disable that alias:

```console
flatshell remove org.gimp.GIMP my-gimp --user
sudo flatshell remove org.example.App my-command
```

### Logging

`flatshell` shows warnings and errors by default. Set `LOGLEVEL` to include
operational details or troubleshooting output:

```console
LOGLEVEL=INFO flatshell list --all
LOGLEVEL=DEBUG flatshell export --user
```

Supported levels are `DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`.
Debug logs include discovery and launcher decisions; command output remains
unchanged.

## Flatlink

Launch the GUI from the terminal with:

```console
flatlink
```

![Flatlink window showing exported Flatpak commands](screenshots/flatlink.png)

The window lists discovered apps in expandable rows, grouped by app and
installation scope. Each app has a switch for its default setting; individual
alias settings take precedence over the app and global defaults. Expand an app
to see each alias, its command, and its enable/disable switch. Use the search
field and the All/User/System filter to narrow the list. Changes to aliases
and app switches are stored as user overrides, including for system-installed
apps, and refresh user launchers without requesting system authorization.

The hamburger menu's **Settings** page controls the global default and lists
enabled and disabled app overrides. Use the plus button to choose an installed
app from a list showing one entry per app with its name and ID; selecting it
applies the override to every ref of that app.
The remove button clears the app override and returns to the global default.
The refresh button exports all user commands, like `flatshell export --user`.
Settings also includes the About window with version and author information
from the project metadata.

## Configuration and files

User configuration is stored below:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/flatpak/aliases/
├── global
└── <app_id>
```

System configuration is stored under the default system Flatpak installation,
resolved through the Flatpak API (normally):

```text
/var/lib/flatpak/aliases/
├── global
└── <app_id>
```

The files use an INI/GKeyFile-style format. For example:

```ini
# global
[core]
default-export = none
```

```ini
# <app_id>
[app]
enabled = true

[aliases]
gimp = true
gimp-console = false

[custom-aliases]
my-gimp = gimp
```

Settings are resolved from most specific to least specific:

1. An alias setting in the app file.
2. The app-level `enabled` setting.
3. The global `default-export` policy.

`all` enables aliases by default; `none` disables them by default. New system
configurations default to `none`, while new user configurations default to
`all`. An explicit app or alias setting takes precedence over the
less-specific setting.

Generated launcher scripts are stored in:

```text
${XDG_DATA_HOME:-$HOME/.local/share}/flatpak-commands/
/var/lib/flatpak-commands/
```

The profile script resolves the system installation dynamically and adds both
launcher directories to `PATH`, with the user directory first. If a user
override disables a command that has a system launcher, a user-side mask
prevents the system command from taking effect.
Debian installs it in `/etc/profile.d/`; `flatshell install-profile --user`
installs a user copy and sources it from `~/.profile`.

## How it works

1. The exporter enumerates installed Flatpak app refs and reads their
   `files/manifest.json` command declarations. A built-in command map supplies
   aliases for known apps whose manifests do not declare them.
   The map includes GNOME and KDE Flathub apps with conventional host commands.
2. The API and list commands retain each distinct branch and architecture,
   preferring the user installation when the same ref exists in both scopes.
   Export tries the current ref first and falls back to the last enumerated ref
   when resolving launcher name collisions.
3. For each selected ref, it combines declared commands with custom aliases
   and applies the selected configuration. User exports include system refs;
   system exports are disabled by default.
4. For enabled aliases, it writes an executable launcher that invokes
   `flatpak run` with the app ID, branch, architecture, and command. User
   launchers take precedence over system launchers; disabled user aliases mask
   system launchers with the same name.
5. The profile script exposes the directories on `PATH`, so commands can be
   started directly from a terminal.

Flatlink and `flatshell` use the same configuration and export implementation,
so changing a setting in either interface produces the same result.

## Python library

The package can also be used from Python. `FlatpakCommandExporter` provides
methods to inspect aliases and command groups, refresh generated launchers, and
update export settings:

```python
from flatpak_command_exporter import FlatpakCommandExporter

exporter = FlatpakCommandExporter()
aliases = exporter.get_exported_aliases()
groups = exporter.get_command_groups(include_system=True)
exporter.set_alias_enabled("org.gimp.GIMP", "gimp", True)
```

The public types are available from `flatpak_command_exporter` or
`flatpak_command_exporter.api`. Existing imports from
`flatpak_command_exporter.application` remain supported.

The `set_*` and `add_custom_alias` methods save settings and refresh generated
launchers. `remove_custom_alias` removes the custom alias, disables it, and
refreshes exports. A custom `AliasConfig` can be passed to the constructor to
control the configuration location. The library requires Flatpak and
PyGObject with Flatpak introspection bindings; GTK is only needed for Flatlink.

## Development

Run the test suite from a source checkout:

```console
python -m unittest discover -s tests -v
```

Build the Debian packages with `make deb`. The test suite covers configuration
precedence and persistence, CLI compatibility, launcher generation, library
operations, and Flatpak alias discovery.

Update the Debian, RPM spec, and AppStream release changelogs together with
`make release`. The individual `make changelog`, `make spec`, and
`make metainfo` targets can also be run separately. Set `SOURCE_DATE_EPOCH` to
choose a reproducible date for new entries.

## Recent changes

- Added per-user global and per-app alias configuration in
  `flatpak/aliases/`.
- Added app and alias enable/disable settings, default export policies, and
  custom aliases.
- Added the `flatshell` CLI configuration commands and Flatlink controls,
  including app-level defaults, user-only app and alias overrides, a Settings
  page, export refresh, and About window.
- Updated Debian packaging to install the renamed profile script
  automatically.
- Replaced Flatpak path watchers with boot-plus-daily system and user refresh
  timers.
- Kept the existing application ID prefix, `xyz.kowalski7cc`, and standardized
  the GUI command name as lowercase `flatlink`.

## License

Flatpak Command Exporter is distributed under the MIT License. See
[LICENSE](LICENSE) for the full text.
