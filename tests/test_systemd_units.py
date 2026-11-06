import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter import system_export

RESOURCES = Path(__file__).parents[1] / "resources"


class SystemdUnitTests(unittest.TestCase):
    def test_system_watcher_is_limited_to_system_flatpak_exports(self):
        path_unit = (RESOURCES / "flatpak-command-exporter-system.path").read_text(
            encoding="utf-8"
        )
        service_unit = (
            RESOURCES / "flatpak-command-exporter-system.service"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "PathChanged=/var/lib/flatpak/exports/share/applications",
            path_unit,
        )
        self.assertNotIn("%h/", path_unit)
        self.assertIn(
            "ExecStart=/usr/bin/python3 -m flatpak_command_exporter.system_export",
            service_unit,
        )
        self.assertNotIn("ExecStart=/usr/bin/flatshell export\n", service_unit)

    def test_user_watcher_is_limited_to_user_flatpak_exports(self):
        path_unit = (RESOURCES / "flatpak-command-exporter-user.path").read_text(
            encoding="utf-8"
        )
        service_unit = (
            RESOURCES / "flatpak-command-exporter-user.service"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "PathChanged=%h/.local/share/flatpak/exports/share/applications",
            path_unit,
        )
        self.assertNotIn("/var/lib/flatpak/", path_unit)
        self.assertIn("ExecStart=/usr/bin/flatshell export\n", service_unit)
        self.assertNotIn("--system", service_unit)

    def test_scope_units_are_enabled_by_package_presets(self):
        system_preset = (
            RESOURCES / "flatpak-command-exporter-system.preset"
        ).read_text(encoding="utf-8")
        user_preset = (
            RESOURCES / "flatpak-command-exporter-user.preset"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            system_preset.strip(),
            "enable flatpak-command-exporter-system.path",
        )
        self.assertEqual(
            user_preset.strip(),
            "enable flatpak-command-exporter-user.path",
        )

    def test_system_service_entrypoint_exports_only_system_scope(self):
        with patch.object(system_export, "FlatpakCommandExporter") as exporter_class:
            system_export.main()

        exporter_class.assert_called_once_with(scope="system")
        exporter_class.return_value.export_commands.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
