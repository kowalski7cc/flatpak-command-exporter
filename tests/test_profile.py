import os
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
                "share/flatpak-commands",
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

    def test_invalid_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            profile.install_profile("global")


if __name__ == "__main__":
    unittest.main()
