import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from flatpak_command_exporter import __main__ as core
from flatpak_command_exporter.config import AliasConfig


class ConfigurationCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"XDG_DATA_HOME": self.temporary_directory.name}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.export = patch.object(core, "export_commands")
        self.export.start()
        self.addCleanup(self.export.stop)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def run_cli(self, *arguments):
        with patch.object(sys, "argv", ["flatshell", *arguments]):
            core.main()

    def test_config_command_updates_global_default_and_exports(self):
        self.run_cli("config", "default-export", "none")

        self.assertEqual(AliasConfig().default_policy(), "none")
        core.export_commands.assert_called_once_with()

    def test_add_command_creates_and_enables_custom_alias(self):
        self.run_cli("add", "org.example.App", "myapp", "/app/bin/app")

        config = AliasConfig()
        self.assertEqual(
            config.custom_aliases("org.example.App"),
            {"myapp": "/app/bin/app"},
        )
        self.assertTrue(config.is_alias_enabled("org.example.App", "myapp"))
        core.export_commands.assert_called_once_with()

    def test_disable_without_alias_sets_app_override(self):
        self.run_cli("disable", "org.example.App", "--user")

        self.assertFalse(
            AliasConfig().is_alias_enabled("org.example.App", "example")
        )
        core.export_commands.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
