import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter import profile


class ProfileInstallationTests(unittest.TestCase):
    def test_user_install_adds_idempotent_profile_block(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory)
            config_home = home / "settings"
            profile_file = home / ".profile"
            profile_file.write_text("export EXISTING=value\n", encoding="utf-8")
            with patch.dict(
                os.environ,
                {"HOME": str(home), "XDG_CONFIG_HOME": str(config_home)},
            ):
                destination = profile.install_profile("user")
                first_content = profile_file.read_text(encoding="utf-8")
                profile.install_profile("user")

            self.assertEqual(
                destination,
                config_home
                / "flatpak-command-exporter"
                / "profile.d"
                / "flatpak-exported-commands.sh",
            )
            self.assertEqual(profile_file.read_text(encoding="utf-8"), first_content)
            self.assertIn("export EXISTING=value", first_content)
            self.assertEqual(first_content.count(profile.PROFILE_MARKER_START), 1)
            self.assertEqual(first_content.count(profile.PROFILE_MARKER_END), 1)
            self.assertIn(
                'USER_BASE="${XDG_DATA_HOME:-"$HOME/.local/share"}/flatpak-commands"',
                destination.read_text(encoding="utf-8"),
            )

    def test_system_install_copies_profile_script_to_profile_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            system_profile_directory = Path(temporary_directory) / "profile.d"
            with patch.object(profile, "SYSTEM_PROFILE_DIRECTORY", system_profile_directory):
                destination = profile.install_profile("system")

            self.assertEqual(
                destination,
                system_profile_directory / profile.PROFILE_SCRIPT,
            )
            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                profile.files("flatpak_command_exporter")
                .joinpath(profile.PROFILE_SCRIPT)
                .read_text(encoding="utf-8"),
            )
            self.assertEqual(destination.stat().st_mode & 0o777, 0o644)

    def test_profile_resolves_system_launcher_path_and_prioritizes_user_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            home = Path(temporary_directory)
            flatpak_root = home / "custom-flatpak"
            system_commands = Path(f"{flatpak_root}-commands")
            user_commands = home / "data" / "flatpak-commands"
            helper_directory = home / "bin"
            helper_directory.mkdir()
            system_commands.mkdir()
            user_commands.mkdir(parents=True)
            flatpak_helper = helper_directory / "flatpak"
            flatpak_helper.write_text(
                f"#!/bin/sh\nprintf '%s\\n' {flatpak_root}\n",
                encoding="utf-8",
            )
            flatpak_helper.chmod(0o755)
            script = Path(profile.__file__).parent / profile.PROFILE_SCRIPT
            result = subprocess.run(
                [
                    "sh",
                    "-c",
                    '. "$1"; printf "%s" "$PATH"',
                    "sh",
                    str(script),
                ],
                check=True,
                capture_output=True,
                text=True,
                env={
                    "HOME": str(home),
                    "XDG_DATA_HOME": str(user_commands.parent),
                    "PATH": f"{helper_directory}:{system_commands}:/usr/bin",
                },
            )

        path_entries = result.stdout.split(":")
        self.assertEqual(path_entries[0], str(user_commands))
        self.assertGreater(path_entries.index(str(system_commands)), 0)
        self.assertEqual(path_entries.count(str(user_commands)), 1)
        self.assertEqual(path_entries.count(str(system_commands)), 1)

    def test_system_install_rejects_non_directory_profile_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            system_profile_directory = Path(temporary_directory) / "profile.d"
            system_profile_directory.write_text("this is a file", encoding="utf-8")
            with patch.object(profile, "SYSTEM_PROFILE_DIRECTORY", system_profile_directory):
                with self.assertRaises(NotADirectoryError):
                    profile.install_profile("system")

    def test_invalid_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            profile.install_profile("global")


if __name__ == "__main__":
    unittest.main()
