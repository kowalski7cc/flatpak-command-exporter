import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter.application import (
    COMMAND_TEMPLATE,
    create_launcher,
    remove_launcher,
)


class LauncherTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
