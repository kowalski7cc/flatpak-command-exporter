import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gi.repository import Gio

from flatpak_command_exporter.config import AliasConfig
from flatpak_command_exporter.service import watcher


class FlatpakChangeWatcherTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.installation_path = Path(self.temporary_directory.name) / "installation"
        self.exporter = SimpleNamespace(
            config=AliasConfig(str(Path(self.temporary_directory.name) / "data")),
            export_commands=Mock(),
        )
        self.watcher = watcher.FlatpakChangeWatcher(
            self.exporter, "user", [self.installation_path]
        )

    def test_debounced_event_refreshes_only_the_affected_app(self):
        changed_file = Gio.File.new_for_path(
            str(
                self.installation_path
                / "app"
                / "org.example.App"
                / "x86_64"
                / "stable"
                / "active"
            )
        )
        with (
            patch.object(self.watcher, "_sync_monitors"),
            patch.object(watcher.GLib, "timeout_add", return_value=42) as timeout_add,
            patch.object(watcher.GLib, "source_remove"),
        ):
            self.watcher._on_changed(
                Mock(),
                changed_file,
                None,
                Gio.FileMonitorEvent.CHANGES_DONE_HINT,
                self.installation_path / "app" / "org.example.App",
            )

            timeout_add.assert_called_once_with(
                watcher.DEBOUNCE_MS, self.watcher._flush_pending
            )
            self.assertEqual(self.watcher._timeout_id, 42)
            self.assertEqual(self.watcher._pending_app_ids, {"org.example.App"})
            self.watcher._flush_pending()

        self.exporter.export_commands.assert_called_once_with("org.example.App")

    def test_app_directory_addition_and_removal_are_detected(self):
        app_directory = self.installation_path / "app" / "org.example.App"
        app_directory.mkdir(parents=True)
        self.watcher._known_app_ids[self.installation_path] = set()

        self.assertEqual(
            self.watcher._update_app_id_snapshot(),
            {"org.example.App"},
        )

        app_directory.rmdir()
        self.assertEqual(
            self.watcher._update_app_id_snapshot(),
            {"org.example.App"},
        )

    def test_monitoring_includes_app_arch_and_branch_directories(self):
        branch_directory = (
            self.installation_path
            / "app"
            / "org.example.App"
            / "x86_64"
            / "stable"
        )
        branch_directory.mkdir(parents=True)
        (branch_directory / "active").symlink_to("commit")
        monitors = set()

        class FakeMonitor:
            def connect(self, *_args):
                return 1

            def cancel(self):
                pass

        def create_monitor(path):
            monitors.add(path)
            monitor = FakeMonitor()
            return monitor

        with patch.object(self.watcher, "_create_monitor", side_effect=create_monitor):
            self.watcher._sync_monitors()

        self.assertIn(self.installation_path, monitors)
        self.assertIn(self.installation_path / "app", monitors)
        self.assertIn(self.installation_path / "app" / "org.example.App", monitors)
        self.assertIn(
            self.installation_path / "app" / "org.example.App" / "x86_64",
            monitors,
        )
        self.assertIn(branch_directory, monitors)
        self.assertNotIn(branch_directory / "commit", monitors)

    def test_events_outside_app_tree_are_ignored(self):
        changed_file = Gio.File.new_for_path(
            str(self.installation_path / "repo" / "objects" / "object")
        )
        with (
            patch.object(self.watcher, "_sync_monitors"),
            patch.object(watcher.GLib, "timeout_add") as timeout_add,
        ):
            self.watcher._on_changed(
                Mock(),
                changed_file,
                None,
                Gio.FileMonitorEvent.CHANGES_DONE_HINT,
                self.installation_path,
            )

        timeout_add.assert_not_called()
        self.assertEqual(self.watcher._pending_app_ids, set())


if __name__ == "__main__":
    unittest.main()
