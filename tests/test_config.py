import os
import tempfile
import unittest
from pathlib import Path

from flatpak_command_exporter.config import AliasConfig, AliasConfigError


class AliasConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.config = AliasConfig(self.temporary_directory.name)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def test_default_policy_exports_all_by_default(self):
        self.assertEqual(self.config.default_policy(), "all")
        self.assertTrue(self.config.is_alias_enabled("org.example.App", "example"))

    def test_app_and_alias_overrides_compose_with_default_policy(self):
        self.config.set_default_policy("none")
        self.assertFalse(self.config.is_alias_enabled("org.example.App", "example"))

        self.config.set_app_enabled("org.example.App", True)
        self.assertTrue(self.config.is_alias_enabled("org.example.App", "example"))

        self.config.set_alias_enabled("org.example.App", "example", False)
        self.assertFalse(self.config.is_alias_enabled("org.example.App", "example"))

        self.config.set_alias_enabled("org.example.App", "example", True)
        self.assertTrue(self.config.is_alias_enabled("org.example.App", "example"))

    def test_custom_aliases_round_trip_in_flatpak_keyfile_format(self):
        self.config.set_custom_alias("org.example.App", "myapp", "/app/bin/app")
        self.config.set_alias_enabled("org.example.App", "myapp", True)

        self.assertEqual(
            self.config.custom_aliases("org.example.App"),
            {"myapp": "/app/bin/app"},
        )
        self.assertTrue(self.config.is_alias_enabled("org.example.App", "myapp"))
        self.assertIn("[custom-aliases]", self.config.app_path("org.example.App").read_text())

    def test_remove_custom_alias_reports_whether_an_alias_was_removed(self):
        self.config.set_custom_alias("org.example.App", "myapp", "app")

        self.assertTrue(self.config.remove_custom_alias("org.example.App", "myapp"))
        self.assertFalse(self.config.remove_custom_alias("org.example.App", "myapp"))
        self.assertEqual(self.config.custom_aliases("org.example.App"), {})

    def test_invalid_configuration_values_raise_an_error(self):
        self.config.directory.mkdir(parents=True)
        self.config.global_path.write_text("[core]\ndefault-export = maybe\n")

        with self.assertRaises(AliasConfigError):
            self.config.default_policy()
        with self.assertRaises(AliasConfigError):
            self.config.set_custom_alias("org.example.App", "../unsafe", "command")

    def test_configuration_files_are_private(self):
        self.config.set_default_policy("none")
        self.assertEqual(
            os.stat(self.config.global_path).st_mode & 0o777,
            0o600,
        )

    def test_system_scope_uses_system_flatpak_paths(self):
        config = AliasConfig(self.temporary_directory.name, scope="system")

        self.assertEqual(config.directory, Path(self.temporary_directory.name) / "aliases")
        self.assertEqual(str(config.export_directory), "/usr/share/flatpak-commands")
        self.assertEqual(config.scope, "system")

    def test_default_system_scope_uses_usr_lib_flatpak(self):
        config = AliasConfig(scope="system")

        self.assertEqual(config.directory, Path("/usr/lib/flatpak/aliases"))

    def test_user_and_system_global_defaults_are_independent(self):
        user_config = AliasConfig(Path(self.temporary_directory.name) / "user")
        system_config = AliasConfig(
            Path(self.temporary_directory.name) / "system",
            scope="system",
        )

        user_config.set_default_policy("none")
        system_config.set_default_policy("all")

        self.assertEqual(user_config.default_policy(), "none")
        self.assertEqual(system_config.default_policy(), "all")
        self.assertFalse(user_config.is_alias_enabled("org.example.App", "command"))
        self.assertTrue(system_config.is_alias_enabled("org.example.App", "command"))


if __name__ == "__main__":
    unittest.main()
