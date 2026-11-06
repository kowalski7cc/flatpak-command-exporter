import unittest

from flatpak_command_exporter.api.metadata import manifest_exported_commands


class ManifestMetadataTests(unittest.TestCase):
    def test_curated_commands_are_merged_with_manifest_commands(self):
        commands = manifest_exported_commands(
            "uk.org.greenend.chiark.sgtatham.putty",
            {
                "x-export-commands": {
                    "putty": "manifest-putty",
                },
            },
        )

        self.assertEqual(
            commands,
            {
                "putty": "manifest-putty",
                "puttygen": "puttygen",
                "psftp": "psftp",
                "pageant": "pageant",
                "pscp": "pscp",
            },
        )

    def test_curated_commands_are_used_when_manifest_exports_none(self):
        self.assertEqual(
            manifest_exported_commands(
                "org.keepassxc.KeePassXC", {"command": "keepassxc-wrapper"}
            ),
            {
                "keepassxc": "keepassxc-wrapper",
                "keepassxc-cli": "keepassxc-cli",
            },
        )

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
