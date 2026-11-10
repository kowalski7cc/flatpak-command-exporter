import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter import system_export

ROOT = Path(__file__).parents[1]
SERVICE_DIR = ROOT / "service"


class SystemdUnitTests(unittest.TestCase):
    def test_system_watcher_runs_system_scope_and_is_enabled_by_default(self):
        service_unit = (
            SERVICE_DIR / "flatpak-command-exporter-system.service"
        ).read_text(encoding="utf-8")
        preset = (
            SERVICE_DIR / "flatpak-command-exporter-system.preset"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "ExecStart=/usr/bin/python3 -m "
            "flatpak_command_exporter.service.watcher --scope system",
            service_unit,
        )
        self.assertIn("WantedBy=multi-user.target", service_unit)
        self.assertIn("Restart=on-failure", service_unit)
        self.assertEqual(preset.strip(), "enable flatpak-command-exporter-system.service")

    def test_user_watcher_runs_user_scope_and_is_enabled_by_default(self):
        service_unit = (
            SERVICE_DIR / "flatpak-command-exporter-user.service"
        ).read_text(encoding="utf-8")
        preset = (
            SERVICE_DIR / "flatpak-command-exporter-user.preset"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "ExecStart=/usr/bin/python3 -m "
            "flatpak_command_exporter.service.watcher --scope user",
            service_unit,
        )
        self.assertIn("WantedBy=default.target", service_unit)
        self.assertEqual(preset.strip(), "enable flatpak-command-exporter-user.service")

    def test_packages_install_watcher_and_no_longer_install_periodic_timers(self):
        debian_install = (
            ROOT / "debian" / "flatpak-command-exporter.install"
        ).read_text(encoding="utf-8")
        rpm_spec = (ROOT / "flatpak-command-exporter.spec").read_text(
            encoding="utf-8"
        )
        arch_build = (ROOT / "PKGBUILD").read_text(encoding="utf-8")
        debian_rules = (ROOT / "debian" / "rules").read_text(encoding="utf-8")

        self.assertIn(
            "flatpak_command_exporter/service/", debian_install
        )
        self.assertIn("flatpak_command_exporter", rpm_spec)
        self.assertIn("service/flatpak-command-exporter.install", arch_build)
        self.assertIn(
            "dh_installsystemd -pflatpak-command-exporter "
            "flatpak-command-exporter-system.service",
            debian_rules,
        )
        for package_file in (debian_install, rpm_spec, arch_build):
            self.assertNotIn(".timer", package_file)

        for path in SERVICE_DIR.glob("*.timer"):
            self.fail(f"Unexpected timer unit: {path}")

    def test_system_service_entrypoint_exports_only_system_scope(self):
        with patch.object(system_export, "FlatpakCommandExporter") as exporter_class:
            system_export.main()

        exporter_class.assert_called_once_with(scope="system")
        exporter_class.return_value.export_commands.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
