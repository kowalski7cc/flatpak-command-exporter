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
            patch.object(sys, "argv", ["flatshell", "export", "--user"]),
            patch.object(cli, "FlatpakCommandExporter") as exporter_factory,
            self.assertLogs(level="INFO") as logs,
        ):
            cli.main()

        exporter_factory.return_value.export_commands.assert_called_once()
        self.assertIn("Running export command for user scope", logs.output[0])
        self.assertIn("Completed export command for user scope", logs.output[-1])

    def test_export_command_accepts_an_app_id(self):
        with (
            patch.object(
                sys,
                "argv",
                ["flatshell", "export", "org.example.App", "--user"],
            ),
            patch.object(cli, "FlatpakCommandExporter") as exporter_factory,
        ):
            cli.main()

        exporter_factory.return_value.export_commands.assert_called_once_with(
            "org.example.App"
        )

    def test_config_command_updates_global_default_and_exports(self):
        self.run_cli("config", "default-export", "none", "--user")

        self.assertEqual(AliasConfig().default_policy(), "none")
        api_exporter.export_commands.assert_called_once()

    def test_add_command_creates_and_enables_custom_alias(self):
        self.run_cli("add", "org.example.App", "myapp", "/app/bin/app", "--user")

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

    def test_library_api_filters_export_by_app_id(self):
        exporter = FlatpakCommandExporter(AliasConfig(self.temporary_directory.name))

        exporter.export_commands("org.example.App")

        api_exporter.export_commands.assert_called_once_with(
            exporter.config, app_id="org.example.App"
        )

    def test_system_add_runs_directly_in_system_scope(self):
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
            patch.object(cli, "FlatpakCommandExporter") as exporter_factory,
        ):
            cli.main()

        exporter_factory.assert_called_once_with(scope="system")
        exporter_factory.return_value.add_custom_alias.assert_called_once_with(
            "org.example.App", "myapp", "app"
        )

    def test_user_profile_install_runs_without_escalation(self):
        with (
            patch.object(sys, "argv", ["flatshell", "install-profile", "--user"]),
            patch.object(cli, "install_profile") as install,
        ):
            cli.main()

        install.assert_called_once_with("user")

    def test_system_profile_install_runs_directly(self):
        with (
            patch.object(
                sys, "argv", ["flatshell", "install-profile", "--system"]
            ),
            patch.object(cli, "install_profile") as install,
        ):
            cli.main()

        install.assert_called_once_with("system")

    def test_system_operations_run_directly_with_system_scope(self):
        cases = (
            (
                ["export", "--system"],
                "export_commands",
                (),
            ),
            (
                ["enable", "org.example.App", "example", "--system"],
                "set_alias_enabled",
                ("org.example.App", "example", True),
            ),
            (
                ["disable", "org.example.App", "--system"],
                "set_app_enabled",
                ("org.example.App", False),
            ),
            (
                ["config", "default-export", "none", "--system"],
                "set_default_policy",
                ("none",),
            ),
            (
                [
                    "remove",
                    "org.example.App",
                    "example",
                    "--system",
                ],
                "remove_custom_alias",
                ("org.example.App", "example"),
            ),
        )
        for arguments, method_name, expected_call in cases:
            with (
                self.subTest(arguments=arguments),
                patch.object(sys, "argv", ["flatshell", *arguments]),
                patch.object(cli, "FlatpakCommandExporter") as exporter_factory,
            ):
                cli.main()

            exporter_factory.assert_called_once_with(scope="system")
            getattr(exporter_factory.return_value, method_name).assert_called_once_with(
                *expected_call
            )

    def test_mutations_default_to_system_scope(self):
        with (
            patch.object(
                sys,
                "argv",
                ["flatshell", "config", "default-export", "none"],
            ),
            patch.object(cli, "FlatpakCommandExporter") as exporter_factory,
        ):
            cli.main()

        exporter_factory.assert_called_once_with(scope="system")
        exporter_factory.return_value.set_default_policy.assert_called_once_with("none")


if __name__ == "__main__":
    unittest.main()
