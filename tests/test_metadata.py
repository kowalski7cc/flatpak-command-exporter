import unittest

from flatpak_command_exporter.api.metadata import manifest_exported_commands


class ManifestMetadataTests(unittest.TestCase):
    def test_ignores_non_string_exported_command_entries(self):
        manifest = {
            "x-export-commands": {
                "valid-alias": "valid-command",
                "invalid-command": 42,
                7: "invalid-alias",
            },
        }

        with self.assertLogs(level="WARNING") as logs:
            commands = manifest_exported_commands("org.example.App", manifest)

        self.assertEqual(commands, {"valid-alias": "valid-command"})
        self.assertEqual(len(logs.output), 2)


if __name__ == "__main__":
    unittest.main()
