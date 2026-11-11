"""Refresh Flatpak command exports when application deployments change."""

import argparse
import logging
import os
from pathlib import Path
import signal
from typing import Final

from flatpak_command_exporter._flatpak_gi import require_flatpak_namespace

require_flatpak_namespace()
from gi.repository import Flatpak, Gio, GLib

from flatpak_command_exporter import FlatpakCommandExporter


DEBOUNCE_MS: Final[int] = 2500
MAX_WATCH_DEPTH: Final[int] = 3
TARGET_EVENTS: Final[frozenset[Gio.FileMonitorEvent]] = frozenset(
    {
        Gio.FileMonitorEvent.CHANGES_DONE_HINT,
        Gio.FileMonitorEvent.CREATED,
        Gio.FileMonitorEvent.DELETED,
        Gio.FileMonitorEvent.MOVED_IN,
        Gio.FileMonitorEvent.MOVED_OUT,
        Gio.FileMonitorEvent.RENAMED,
    }
)


def _installation_paths(scope: str) -> list[Path]:
    installations = [("system", Flatpak.Installation.new_system)]
    if scope == "user":
        installations.insert(0, ("user", Flatpak.Installation.new_user))

    paths: list[Path] = []
    for installation_scope, factory in installations:
        try:
            installation = factory()
            if installation is None:
                logging.warning(
                    "No %s Flatpak installation is available", installation_scope
                )
                continue
            installation_path = installation.get_path().get_path()
        except GLib.Error as error:
            logging.warning(
                "Could not access the %s Flatpak installation: %s",
                installation_scope,
                error,
            )
            continue
        if installation_path:
            paths.append(Path(installation_path))
    return list(dict.fromkeys(paths))


class FlatpakChangeWatcher:
    def __init__(
        self,
        exporter: FlatpakCommandExporter,
        scope: str,
        installation_paths: list[Path],
    ) -> None:
        self.exporter = exporter
        self.scope = scope
        self.installation_paths = installation_paths
        self._monitors: dict[Path, Gio.FileMonitor] = {}
        self._pending_app_ids: set[str] = set()
        self._known_app_ids = {
            path: self._installed_app_ids(path) for path in installation_paths
        }
        self._timeout_id = 0
        self._main_loop = GLib.MainLoop()

    def start(self) -> None:
        self._sync_monitors()
        if not self._monitors:
            raise RuntimeError("Could not monitor any Flatpak installation directories")
        self.exporter.export_commands()
        logging.info("Watching Flatpak application changes for %s scope", self.scope)
        self._main_loop.run()

    def stop(self) -> None:
        if self._timeout_id:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = 0
        for monitor in self._monitors.values():
            monitor.cancel()
        self._monitors.clear()
        self._main_loop.quit()

    def _sync_monitors(self) -> None:
        wanted_paths: set[Path] = set()
        for installation_path in self.installation_paths:
            app_directory = installation_path / "app"
            ancestor = installation_path
            while not ancestor.is_dir() and ancestor.parent != ancestor:
                ancestor = ancestor.parent
            wanted_paths.add(ancestor)
            if app_directory.is_dir():
                wanted_paths.add(app_directory)
                self._add_ref_directory_paths(
                    app_directory, depth=0, wanted_paths=wanted_paths
                )

        for path in self._monitors.keys() - wanted_paths:
            self._monitors.pop(path).cancel()
        for path in wanted_paths - self._monitors.keys():
            try:
                monitor = self._create_monitor(path)
            except GLib.Error as error:
                logging.error("Could not monitor Flatpak directory %s: %s", path, error)
                continue
            monitor.connect(
                "changed",
                lambda active_monitor, file, other_file, event, watched_path=path: (
                    self._on_changed(
                        active_monitor, file, other_file, event, watched_path
                    )
                ),
            )
            self._monitors[path] = monitor

    @staticmethod
    def _create_monitor(path: Path) -> Gio.FileMonitor:
        return Gio.File.new_for_path(str(path)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None
        )

    def _add_ref_directory_paths(
        self, directory: Path, *, depth: int, wanted_paths: set[Path]
    ) -> None:
        if depth >= MAX_WATCH_DEPTH:
            return
        try:
            children = list(directory.iterdir())
        except OSError as error:
            logging.warning("Could not inspect Flatpak directory %s: %s", directory, error)
            return
        for child in children:
            if child.is_dir():
                wanted_paths.add(child)
                self._add_ref_directory_paths(
                    child, depth=depth + 1, wanted_paths=wanted_paths
                )

    @staticmethod
    def _installed_app_ids(installation_path: Path) -> set[str]:
        try:
            return {
                path.name
                for path in (installation_path / "app").iterdir()
                if path.is_dir()
            }
        except FileNotFoundError:
            return set()
        except OSError as error:
            logging.warning(
                "Could not enumerate applications in %s: %s", installation_path, error
            )
            return set()

    def _update_app_id_snapshot(self) -> set[str]:
        changed_app_ids: set[str] = set()
        for installation_path in self.installation_paths:
            app_ids = self._installed_app_ids(installation_path)
            changed_app_ids.update(
                app_ids.symmetric_difference(
                    self._known_app_ids.get(installation_path, set())
                )
            )
            self._known_app_ids[installation_path] = app_ids
        return changed_app_ids

    def _on_changed(
        self,
        _monitor: Gio.FileMonitor,
        file: Gio.File,
        other_file: Gio.File | None,
        event: Gio.FileMonitorEvent,
        watched_path: Path,
    ) -> None:
        if event not in TARGET_EVENTS:
            return

        changed_app_ids = self._update_app_id_snapshot()
        self._sync_monitors()
        changed_paths = [file.get_path()]
        if other_file is not None:
            changed_paths.append(other_file.get_path())

        for app_id in changed_app_ids:
            self._queue_app_id(app_id)

        for changed_path in changed_paths:
            if changed_path is None:
                continue
            app_id = self._app_id_for_path(Path(changed_path))
            if app_id is not None:
                logging.debug(
                    "Detected Flatpak %s event for %s under %s",
                    event.value_nick,
                    app_id,
                    watched_path,
                )
                self._queue_app_id(app_id)

        if self._pending_app_ids:
            if self._timeout_id:
                GLib.source_remove(self._timeout_id)
            self._timeout_id = GLib.timeout_add(DEBOUNCE_MS, self._flush_pending)

    def _queue_app_id(self, app_id: str) -> None:
        try:
            self.exporter.config.app_path(app_id)
        except ValueError:
            logging.warning("Ignoring invalid Flatpak app directory %r", app_id)
            return
        self._pending_app_ids.add(app_id)

    def _app_id_for_path(self, changed_path: Path) -> str | None:
        for installation_path in self.installation_paths:
            app_directory = installation_path / "app"
            try:
                relative_path = changed_path.relative_to(app_directory)
            except ValueError:
                continue
            if not relative_path.parts:
                continue
            return relative_path.parts[0]
        return None

    def _flush_pending(self) -> bool:
        app_ids = sorted(self._pending_app_ids)
        self._pending_app_ids.clear()
        self._timeout_id = 0
        for app_id in app_ids:
            try:
                logging.info("Refreshing command exports for %s", app_id)
                self.exporter.export_commands(app_id)
            except (OSError, GLib.Error, ValueError):
                logging.exception(
                    "Could not refresh command exports for %s in %s scope",
                    app_id,
                    self.scope,
                )
        return GLib.SOURCE_REMOVE


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=("system", "user"), required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(
        level=os.environ.get("LOGLEVEL", "INFO").upper(),
        format="%(levelname)s: %(message)s",
    )
    arguments = _build_parser().parse_args(argv)
    installation_paths = _installation_paths(arguments.scope)
    if not installation_paths:
        raise RuntimeError(
            f"No Flatpak installations are available for {arguments.scope} scope"
        )

    watcher = FlatpakChangeWatcher(
        FlatpakCommandExporter(scope=arguments.scope),
        arguments.scope,
        installation_paths,
    )

    def stop_watcher(_signum: int, _frame: object) -> None:
        watcher.stop()

    signal.signal(signal.SIGINT, stop_watcher)
    signal.signal(signal.SIGTERM, stop_watcher)
    try:
        watcher.start()
    finally:
        watcher.stop()


if __name__ == "__main__":
    main()
