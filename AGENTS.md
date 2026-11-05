# Development guide

This file describes project-specific practices for contributors and coding
agents. Keep changes focused, preserve existing behavior unless a change is
intentional, and update this guide when the project conventions change.

## Project shape

- Python package source lives in `src/flatpak_command_exporter/`; automated
  tests live in `tests/`.
- The package provides the shared Flatpak discovery/export behavior, the
  `flatshell` CLI, and the Flatlink GTK/libadwaita GUI. Keep behavior consistent
  across these surfaces and avoid duplicating configuration or export rules.
- `application.py` contains the reusable `FlatpakCommandExporter` API and
  discovery/export operations. `cli.py` owns argument parsing and terminal
  output; `__main__.py` is only the module launcher. Export public library
  types from `__init__.py`.
- CLI and GUI entry points are declared in `pyproject.toml`. Debian package
  contents are controlled by files in `debian/`; profile integration lives in
  the Python package resources.
- The established application ID and icon prefix is
  `xyz.kowalski7cc`. Preserve it for application identity and installed
  resource names.

## Implementation practices

- Prefer small, readable functions and shared helpers over parallel
  implementations. Keep public behavior explicit and errors visible; do not
  silently turn configuration or filesystem failures into success.
- Preserve type hints where already used. Use standard-library facilities
  unless a dependency is needed for a clear project requirement.
- Configuration and generated launchers support both user and system scopes.
  Resolve user paths with `${XDG_DATA_HOME:-$HOME/.local/share}` and system
  paths with `/usr/lib/flatpak/aliases` for system configuration and
  `/usr/share/flatpak-commands` for generated launchers. Route system mutations
  through the root-owned system-bus helper and authorize each operation with
  PolicyKit.
- User alias settings live under `flatpak/aliases/`; system settings live under
  `/usr/lib/flatpak/aliases/`. Both use INI/GKeyFile-style files.
  Keep global, app, and alias precedence consistent across the CLI, GUI, and
  export flow. Persist settings before refreshing exports, and report refresh
  failures to the caller.
- Validate app IDs and aliases before using them as filenames or launcher
  paths. Be careful when generating shell scripts: preserve argument
  forwarding and safely handle values that could alter shell syntax.
- GUI-only imports should remain lazy so CLI and library use does not require
  GTK at import time. Follow the existing GTK 4/libadwaita patterns and surface
  save/export failures in the interface.
- Keep library operations independent of terminal formatting; the CLI should
  format data returned by the library API.
- Keep Debian install manifests, Python entry points, desktop metadata, icons,
  and profile-script names in sync when changing commands or resources.

## Tests and verification

- Add or update tests for behavior changes, especially config precedence,
  persistence, CLI parsing, launcher creation/removal, and user-versus-system
  scope.
- Prefer isolated tests with temporary directories and mocks for Flatpak,
  filesystem, and GUI dependencies. Do not rely on installed apps or mutate
  the developer's real user configuration.
- Run the full test suite from the repository root:

  ```console
  python -m unittest discover -s tests -v
  ```

- For packaging or install-manifest changes, also build the Debian packages:

  ```console
  make deb
  ```

- Run `git diff --check` before finishing. Mention any validation that could
  not be run and why.

## Documentation and changes

- Update `README.md` when user-facing commands, installation steps,
  configuration, or current behavior changes.
- Keep examples aligned with the actual CLI help and supported scope. Clearly
  label behavior that is planned but not implemented.
- Do not commit generated packages, build output, personal configuration, or
  secrets. Preserve unrelated worktree changes.
