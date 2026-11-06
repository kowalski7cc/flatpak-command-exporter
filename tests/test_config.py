import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flatpak_command_exporter.config import (
    AliasConfig,
    AliasConfigError,
)
from flatpak_command_exporter import config as config_module


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

    def test_app_overrides_lists_only_explicit_app_settings(self):
        self.config.set_app_enabled("org.example.Enabled", True)
        self.config.set_app_enabled("org.example.Disabled", False)
        self.config.set_alias_enabled("org.example.AliasOnly", "command", True)

        self.assertEqual(
            self.config.app_overrides(),
            {
                "org.example.Enabled": True,
                "org.example.Disabled": False,
            },
        )

    def test_app_override_can_be_reset_for_a_system_installed_app(self):
        self.config.set_app_enabled("org.example.SystemApp", False)

        self.assertFalse(self.config.app_enabled("org.example.SystemApp"))
        self.config.set_app_enabled("org.example.SystemApp", None)
        self.assertIsNone(self.config.app_enabled("org.example.SystemApp"))
        self.assertEqual(self.config.app_overrides(), {})

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
        system_root = Path(self.temporary_directory.name)
        self.assertEqual(
            config.export_directory,
            system_root.parent / f"{system_root.name}-commands",
        )
        self.assertEqual(config.scope, "system")

    def test_default_system_scope_uses_flatpak_api_path(self):
        installation_path = Path("/var/lib/flatpak")
        with patch.object(
            config_module,
            "_get_system_installation_path",
            return_value=installation_path,
        ):
            config = AliasConfig(scope="system")

        self.assertEqual(config.directory, installation_path / "aliases")

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

    def test_system_scope_resolves_paths_from_flatpak_installation(self):
        installation_path = Path("/custom/var/flatpak")
        with patch.object(
            config_module,
            "_get_system_installation_path",
            return_value=installation_path,
        ):
            config = AliasConfig(scope="system")

        self.assertEqual(config.directory, installation_path / "aliases")
        self.assertEqual(
            config.export_directory,
            installation_path.parent / "flatpak-commands",
        )

    def test_new_system_configuration_disables_exports_by_default(self):
        config = AliasConfig(
            Path(self.temporary_directory.name) / "system",
            scope="system",
        )

        self.assertEqual(config.default_policy(), "none")
        self.assertFalse(config.is_alias_enabled("org.example.App", "example"))

    def test_legacy_system_settings_are_read_and_migrated_on_write(self):
        installation_path = Path(self.temporary_directory.name) / "flatpak"
        legacy_directory = Path(self.temporary_directory.name) / "legacy-aliases"
        legacy_directory.mkdir()
        (legacy_directory / "global").write_text(
            "[core]\ndefault-export = all\n",
            encoding="utf-8",
        )

        with (
            patch.object(
                config_module,
                "_get_system_installation_path",
                return_value=installation_path,
            ),
            patch.object(
                config_module,
                "LEGACY_SYSTEM_ALIAS_DIRECTORY",
                legacy_directory,
            ),
        ):
            config = AliasConfig(scope="system")
            self.assertEqual(config.default_policy(), "all")
            config.set_default_policy("none")

        self.assertEqual(config.default_policy(), "none")
        self.assertTrue(config.global_path.exists())
        self.assertIn("default-export = all", (legacy_directory / "global").read_text())


if __name__ == "__main__":
    unittest.main()
