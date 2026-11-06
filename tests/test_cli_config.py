import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from flatpak_command_exporter import FlatpakCommandExporter, cli
from flatpak_command_exporter.api import exporter as api_exporter
from flatpak_command_exporter.config import AliasConfig


class ConfigurationCliTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.environment = patch.dict(
            os.environ, {"XDG_DATA_HOME": self.temporary_directory.name}
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.export = patch.object(api_exporter, "export_commands")
        self.export.start()
        self.addCleanup(self.export.stop)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def run_cli(self, *arguments):
        with patch.object(sys, "argv", ["flatshell", *arguments]):
            cli.main()

    def test_logging_defaults_to_warning(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(cli.logging, "basicConfig") as basic_config,
        ):
            cli._configure_logging()

        basic_config.assert_called_once_with(
            level="WARNING",
            format="%(levelname)s: %(message)s",
        )

    def test_loglevel_environment_variable_selects_logging_verbosity(self):
        with (
            patch.dict(os.environ, {"LOGLEVEL": "DEBUG"}),
            patch.object(cli.logging, "basicConfig") as basic_config,
        ):
            cli._configure_logging()

        basic_config.assert_called_once_with(
            level="DEBUG",
            format="%(levelname)s: %(message)s",
        )

    def test_cli_logs_operation_lifecycle(self):
        with (
            patch.object(sys, "argv", ["flatshell", "export"]),
            patch.object(cli, "FlatpakCommandExporter") as exporter_factory,
            self.assertLogs(level="INFO") as logs,
        ):
            cli.main()

        exporter_factory.return_value.export_commands.assert_called_once()
        self.assertIn("Running export command for user scope", logs.output[0])
        self.assertIn("Completed export command for user scope", logs.output[-1])

    def test_config_command_updates_global_default_and_exports(self):
        self.run_cli("config", "default-export", "none")

        self.assertEqual(AliasConfig().default_policy(), "none")
        api_exporter.export_commands.assert_called_once()

    def test_add_command_creates_and_enables_custom_alias(self):
        self.run_cli("add", "org.example.App", "myapp", "/app/bin/app")

        config = AliasConfig()
        self.assertEqual(
            config.custom_aliases("org.example.App"),
            {"myapp": "/app/bin/app"},
        )
        self.assertTrue(config.is_alias_enabled("org.example.App", "myapp"))
        api_exporter.export_commands.assert_called_once()

    def test_disable_without_alias_sets_app_override(self):
        self.run_cli("disable", "org.example.App", "--user")

        self.assertFalse(
            AliasConfig().is_alias_enabled("org.example.App", "example")
        )
        api_exporter.export_commands.assert_called_once()

    def test_library_api_accepts_config_and_refreshes_after_updates(self):
        config = AliasConfig(self.temporary_directory.name)
        exporter = FlatpakCommandExporter(config)

        exporter.set_default_policy("none")

        self.assertEqual(config.default_policy(), "none")
        api_exporter.export_commands.assert_called_once_with(config)

    def test_system_add_uses_the_system_bus(self):
        with (
            patch.object(
                sys,
                "argv",
                [
                    "flatshell",
                    "add",
                    "org.example.App",
                    "myapp",
                    "app",
                    "--system",
                ],
            ),
            patch.object(cli, "call_system_method") as call,
        ):
            cli.main()

        call.assert_called_once_with(
            "AddCustomAlias", "org.example.App", "myapp", "app"
        )

    def test_user_profile_install_runs_without_escalation(self):
        with (
            patch.object(sys, "argv", ["flatshell", "install-profile", "--user"]),
            patch.object(cli, "install_profile") as install,
        ):
            cli.main()

        install.assert_called_once_with("user")

    def test_system_profile_install_uses_system_bus(self):
        with (
            patch.object(
                sys, "argv", ["flatshell", "install-profile", "--system"]
            ),
            patch.object(cli, "call_system_method") as call,
        ):
            cli.main()

        call.assert_called_once_with("InstallProfile")

    def test_system_operations_use_fixed_dbus_methods(self):
        cases = (
            (
                ["export", "--system"],
                ("Export",),
            ),
            (
                ["enable", "org.example.App", "example", "--system"],
                ("SetAliasEnabled", "org.example.App", "example", True),
            ),
            (
                ["disable", "org.example.App", "--system"],
                ("SetAppEnabled", "org.example.App", False),
            ),
            (
                ["config", "default-export", "none", "--system"],
                ("SetDefaultPolicy", "none"),
            ),
            (
                [
                    "remove",
                    "org.example.App",
                    "example",
                    "--system",
                ],
                ("RemoveCustomAlias", "org.example.App", "example"),
            ),
        )
        for arguments, expected_call in cases:
            with (
                self.subTest(arguments=arguments),
                patch.object(sys, "argv", ["flatshell", *arguments]),
                patch.object(cli, "call_system_method") as call,
            ):
                cli.main()

            call.assert_called_once_with(*expected_call)


if __name__ == "__main__":
    unittest.main()
