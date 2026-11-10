import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter import system_export

RESOURCES = Path(__file__).parents[1] / "resources"


class SystemdUnitTests(unittest.TestCase):
    def test_system_timer_runs_after_boot_and_daily(self):
        timer_unit = (
            RESOURCES / "flatpak-command-exporter-system.timer"
        ).read_text(encoding="utf-8")
        service_unit = (
            RESOURCES / "flatpak-command-exporter-system.service"
        ).read_text(encoding="utf-8")

        self.assertIn("OnBootSec=15min", timer_unit)
        self.assertIn("OnUnitActiveSec=1d", timer_unit)
        self.assertIn(
            "Unit=flatpak-command-exporter-system.service",
            timer_unit,
        )
        self.assertIn("WantedBy=timers.target", timer_unit)
        self.assertIn(
            "ExecStart=/usr/bin/python3 -m flatpak_command_exporter.system_export",
            service_unit,
        )
        self.assertNotIn("ExecStart=/usr/bin/flatshell export", service_unit)
        self.assertNotIn("--user", service_unit)

    def test_user_timer_runs_after_boot_and_daily_for_user_exports(self):
        timer_unit = (
            RESOURCES / "flatpak-command-exporter-user.timer"
        ).read_text(encoding="utf-8")
        service_unit = (
            RESOURCES / "flatpak-command-exporter-user.service"
        ).read_text(encoding="utf-8")

        self.assertIn("OnBootSec=15min", timer_unit)
        self.assertIn("OnUnitActiveSec=1d", timer_unit)
        self.assertIn("Unit=flatpak-command-exporter-user.service", timer_unit)
        self.assertIn("WantedBy=timers.target", timer_unit)
        self.assertIn(
            "ExecStart=/usr/bin/flatshell export --user\n",
            service_unit,
        )
        self.assertNotIn("--system", service_unit)

    def test_scope_timers_are_disabled_by_package_presets(self):
        system_preset = (
            RESOURCES / "flatpak-command-exporter-system.preset"
        ).read_text(encoding="utf-8")
        user_preset = (
            RESOURCES / "flatpak-command-exporter-user.preset"
        ).read_text(encoding="utf-8")

        self.assertEqual(
            system_preset.strip(),
            "disable flatpak-command-exporter-system.timer",
        )
        self.assertEqual(
            user_preset.strip(),
            "disable flatpak-command-exporter-user.timer",
        )

    def test_debian_package_does_not_enable_or_start_system_timer(self):
        debian_rules = (RESOURCES.parent / "debian" / "rules").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "dh_installsystemd --no-enable --no-start "
            "-pflatpak-command-exporter flatpak-command-exporter-system.timer",
            debian_rules,
        )

    def test_system_service_entrypoint_exports_only_system_scope(self):
        with patch.object(system_export, "FlatpakCommandExporter") as exporter_class:
            system_export.main()

        exporter_class.assert_called_once_with(scope="system")
        exporter_class.return_value.export_commands.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
