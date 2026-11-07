import unittest

from flatpak_command_exporter import CommandGroup, ExportedAlias, FlatpakCommandExporter
from flatpak_command_exporter import application
from flatpak_command_exporter import api
from flatpak_command_exporter import __main__ as cli_module
from flatpak_command_exporter import cli
from flatpak_command_exporter.api import discovery, exporter, launchers, metadata, models


class ApiCompatibilityTests(unittest.TestCase):
    def test_root_and_api_package_export_the_same_public_types(self):
        self.assertIs(api.CommandGroup, CommandGroup)
        self.assertIs(api.ExportedAlias, ExportedAlias)
        self.assertIs(api.FlatpakCommandExporter, FlatpakCommandExporter)

    def test_application_module_preserves_legacy_imports(self):
        self.assertIs(application.CommandGroup, api.CommandGroup)
        self.assertIs(application.ExportedAlias, api.ExportedAlias)
        self.assertIs(application.FlatpakCommandExporter, api.FlatpakCommandExporter)
        self.assertIs(application.get_command_groups, discovery.get_command_groups)
        self.assertIs(application.get_exported_aliases, discovery.get_exported_aliases)
        self.assertIs(application.export_commands, launchers.export_commands)
        self.assertIs(application.load_manifest, metadata.load_manifest)
        self.assertIs(application.CommandGroup, models.CommandGroup)
        self.assertIs(application.export_commands, exporter.export_commands)

    def test_api_is_split_by_responsibility(self):
        self.assertTrue(callable(discovery.get_exported_aliases))
        self.assertTrue(callable(exporter.FlatpakCommandExporter))
        self.assertTrue(callable(launchers.create_launcher))
        self.assertTrue(callable(metadata.load_manifest))

    def test_cli_module_entrypoint_reexports_cli_main(self):
        self.assertIs(cli_module.main, cli.main)


if __name__ == "__main__":
    unittest.main()
