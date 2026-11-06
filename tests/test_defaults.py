import unittest

from flatpak_command_exporter.defaults import DEFAULT_EXPORT_COMMANDS


class DefaultExportCommandTests(unittest.TestCase):
    def test_gnome_and_kde_apps_use_their_conventional_commands(self):
        expected = {
            "org.gnome.Calculator": {
                "gnome-calculator": "gnome-calculator",
            },
            "org.kde.kate": {
                "kate": "kate",
            },
            "org.kde.gcompris-teachers": {
                "gcompris-teachers": "gcompris-teachers",
            },
            "org.kde.okular": {
                "okular": "okular",
            },
            "org.kde.okular.kirigami": {
                "okularkirigami": "okularkirigami",
            },
        }

        for app_id, commands in expected.items():
            with self.subTest(app_id=app_id):
                self.assertEqual(DEFAULT_EXPORT_COMMANDS[app_id], commands)

    def test_launcher_alias_can_differ_from_flatpak_command(self):
        self.assertEqual(
            DEFAULT_EXPORT_COMMANDS["org.kde.kile"],
            {"kile": "kile.sh"},
        )
        self.assertEqual(
            DEFAULT_EXPORT_COMMANDS["org.kde.kontact"],
            {"kontact": "run_kontact.sh"},
        )


if __name__ == "__main__":
    unittest.main()
