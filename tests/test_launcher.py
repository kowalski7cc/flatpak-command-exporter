import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter.application import (
    COMMAND_TEMPLATE,
    create_launcher,
    remove_launcher,
)
from flatpak_command_exporter.api import COMMAND_TEMPLATE as API_COMMAND_TEMPLATE
from flatpak_command_exporter.api import launchers as launcher_api


class LauncherTests(unittest.TestCase):
    def test_api_exposes_launcher_script_template(self):
        self.assertEqual(API_COMMAND_TEMPLATE, COMMAND_TEMPLATE)

    def test_create_and_remove_launcher(self):
        with tempfile.TemporaryDirectory() as data_home:
            path = Path(data_home) / "flatpak-commands" / "example"
            with patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
                create_launcher(
                    "org.example.App", "example", "command", "x86_64", "stable"
                )

                self.assertEqual(
                    path.read_text(encoding="utf-8"),
                    COMMAND_TEMPLATE.format(
                        BRANCH="stable",
                        ARCH="x86_64",
                        COMMAND="command",
                        APP_ID="org.example.App",
                    ),
                )
                self.assertTrue(path.stat().st_mode & stat.S_IXUSR)

                remove_launcher("example")
                remove_launcher("example")
                self.assertFalse(path.exists())

    def test_launcher_alias_is_validated(self):
        with self.assertRaises(ValueError):
            create_launcher("org.example.App", "../unsafe", "command", "x86_64", "stable")

    def test_launcher_quotes_command_values_for_the_shell(self):
        with tempfile.TemporaryDirectory() as data_home:
            path = Path(data_home) / "flatpak-commands" / "example"
            command = 'tool"; touch /tmp/unexpected; echo "'
            with patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
                create_launcher(
                    "org.example.App",
                    "example",
                    command,
                    "x86_64",
                    "stable",
                )

            self.assertIn("--command='tool\"; touch /tmp/unexpected; echo \"'", path.read_text())

    def test_disabled_user_alias_masks_existing_system_launcher(self):
        with tempfile.TemporaryDirectory() as data_home:
            path = Path(data_home) / "flatpak-commands" / "example"
            with patch.dict(os.environ, {"XDG_DATA_HOME": data_home}):
                launcher_api._create_disabled_launcher("example")

            self.assertTrue(path.stat().st_mode & stat.S_IXUSR)
            result = subprocess.run(
                [str(path)],
                capture_output=True,
                check=False,
                text=True,
            )
            self.assertEqual(result.returncode, 127)
            self.assertIn(
                "is disabled by the user configuration",
                result.stderr,
            )


if __name__ == "__main__":
    unittest.main()
