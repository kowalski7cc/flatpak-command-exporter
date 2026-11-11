import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


def _debian_package_stanza(control: str, package: str) -> str:
    for stanza in control.split("\n\n"):
        if stanza.startswith(f"Package: {package}\n"):
            return stanza
    raise AssertionError(f"Missing Debian package stanza: {package}")


def _arch_package_function(build: str, package: str) -> str:
    match = re.search(
        rf"(?ms)^package_{re.escape(package)}\(\) \{{(.*?)(?=^package_|\Z)",
        build,
    )
    if match is None:
        raise AssertionError(f"Missing Arch package function: {package}")
    return match.group(1)


class PackageManifestTests(unittest.TestCase):
    def test_debian_dependencies_and_file_ownership_are_split(self):
        control = (ROOT / "debian" / "control").read_text(encoding="utf-8")
        core = _debian_package_stanza(control, "flatpak-command-exporter-core")
        cli = _debian_package_stanza(control, "flatpak-command-exporter-cli")
        gui = _debian_package_stanza(control, "flatpak-command-exporter-gui")
        service = _debian_package_stanza(
            control, "flatpak-command-exporter-service"
        )
        meta = _debian_package_stanza(control, "flatpak-command-exporter")

        self.assertIn("flatpak-command-exporter-core", cli)
        self.assertIn("flatpak-command-exporter-core", gui)
        self.assertIn("gir1.2-gtk-4.0", gui)
        self.assertIn("gir1.2-adw-1", gui)
        self.assertIn("python3-gi", core)
        self.assertIn("gir1.2-flatpak-1.0", core)
        self.assertIn("flatpak-command-exporter-core", service)
        self.assertNotIn("flatpak-command-exporter-cli", service)
        self.assertNotIn("flatpak-command-exporter-gui", service)
        for component in ("cli", "gui", "service"):
            self.assertIn(f"flatpak-command-exporter-{component}", meta)
        core_files = (
            ROOT / "debian" / "flatpak-command-exporter-core.install"
        ).read_text(encoding="utf-8")
        cli_files = (
            ROOT / "debian" / "flatpak-command-exporter-cli.install"
        ).read_text(encoding="utf-8")
        service_files = (
            ROOT / "debian" / "flatpak-command-exporter-service.install"
        ).read_text(encoding="utf-8")
        gui_files = (
            ROOT / "debian" / "flatpak-command-exporter-gui.install"
        ).read_text(encoding="utf-8")
        not_installed = (ROOT / "debian" / "not-installed").read_text(
            encoding="utf-8"
        )
        self.assertIn("flatpak_command_exporter/api/", core_files)
        self.assertIn(
            "usr/lib/python3.*/dist-packages/flatpak_command_exporter/__init__.py "
            "usr/lib/python3/dist-packages/flatpak_command_exporter/",
            core_files,
        )
        self.assertIn("usr/bin/flatshell", cli_files)
        self.assertIn(
            "usr/lib/python3.*/dist-packages/flatpak_command_exporter/__main__.py "
            "usr/lib/python3/dist-packages/flatpak_command_exporter/",
            cli_files,
        )
        self.assertIn("flatpak_command_exporter/service/", service_files)
        self.assertIn(
            "usr/lib/python3.*/dist-packages/flatpak_command_exporter/service/ "
            "usr/lib/python3/dist-packages/flatpak_command_exporter/",
            service_files,
        )
        self.assertIn("usr/lib/systemd/system/", service_files)
        self.assertIn("usr/bin/flatlink", gui_files)
        self.assertIn(
            "usr/lib/python3.*/dist-packages/flatpak_command_exporter/gui/ "
            "usr/lib/python3/dist-packages/flatpak_command_exporter/",
            gui_files,
        )
        self.assertIn(
            "usr/lib/python3.*/dist-packages/flatpak_command_exporter/__pycache__/",
            not_installed,
        )

    def test_rpm_service_requires_only_core_among_project_packages(self):
        spec = (ROOT / "flatpak-command-exporter.spec").read_text(
            encoding="utf-8"
        )
        meta_section = spec.split("%description\n", 1)[0]
        service_section = spec.split("%package service\n", 1)[1].split(
            "%description service\n", 1
        )[0]
        core_section = spec.split("%package core\n", 1)[1].split(
            "%description core\n", 1
        )[0]
        for component in ("cli", "gui", "service"):
            self.assertIn(f"%{{name}}-{component}", meta_section)
        self.assertIn("Requires:       flatpak-libs", core_section)
        self.assertIn("Requires:       %{name}-core", service_section)
        self.assertNotIn("%{name}-cli", service_section)
        self.assertNotIn("%{name}-gui", service_section)
        self.assertIn("%files service", spec)
        self.assertIn("%{python3_sitelib}/flatpak_command_exporter/service/", spec)
        self.assertIn("%files cli", spec)
        self.assertIn("%files gui", spec)

    def test_arch_dependencies_and_service_files_are_split(self):
        build = (ROOT / "PKGBUILD").read_text(encoding="utf-8")
        service = _arch_package_function(
            build, "flatpak-command-exporter-service"
        )
        cli = _arch_package_function(build, "flatpak-command-exporter-cli")
        gui = _arch_package_function(build, "flatpak-command-exporter-gui")
        meta = _arch_package_function(build, "flatpak-command-exporter")

        self.assertIn("'flatpak-command-exporter-core' 'systemd'", service)
        self.assertNotIn("'flatpak-command-exporter-cli'", service)
        self.assertNotIn("'flatpak-command-exporter-gui'", service)
        self.assertIn("'flatpak-command-exporter-core'", cli)
        self.assertIn("'flatpak-command-exporter-core'", gui)
        self.assertIn("'flatpak-command-exporter-cli'", meta)
        self.assertIn("'flatpak-command-exporter-gui'", meta)
        self.assertIn("'flatpak-command-exporter-service'", meta)
        self.assertIn("flatpak-command-exporter-system.service", service)
        self.assertIn("flatpak-command-exporter-user.service", service)


if __name__ == "__main__":
    unittest.main()
