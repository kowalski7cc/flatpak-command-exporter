import unittest

from flatpak_command_exporter.defaults import DEFAULT_EXPORT_COMMANDS


class DefaultExportCommandTests(unittest.TestCase):
    def test_packages_with_additional_shipped_commands_have_defaults(self):
        expected = {
            "org.keepassxc.KeePassXC": {
                "keepassxc": "keepassxc-wrapper",
                "keepassxc-cli": "keepassxc-cli",
            },
            "org.gnumeric.Gnumeric": {
                "gnumeric": "gnumeric",
                "ssconvert": "ssconvert",
                "ssgrep": "ssgrep",
                "ssindex": "ssindex",
            },
            "org.gnucash.GnuCash": {
                "gnucash": "gnucash",
                "gnucash-cli": "gnucash-cli",
            },
            "org.avidemux.Avidemux": {
                "avidemux": "avidemux3_qt5",
                "avidemux-cli": "avidemux3_cli",
            },
            "io.github.Qalculate": {
                "qalculate-gtk": "qalculate-gtk",
                "qalc": "qalc",
            },
            "org.kicad.KiCad": {
                "kicad": "kicad-startup",
                "eeschema": "eeschema-startup",
                "pcbnew": "pcbnew-startup",
                "kicad-cli": "kicad-cli",
            },
            "org.darktable.Darktable": {
                "darktable": "darktable",
                "darktable-cli": "darktable-cli",
            },
            "org.freecad.FreeCAD": {
                "freecad": "FreeCAD",
                "freecadcmd": "freecadcmd",
            },
            "org.wireshark.Wireshark": {
                "wireshark": "wireshark-wrapper",
                "tshark": "tshark",
                "capinfos": "capinfos",
                "editcap": "editcap",
                "mergecap": "mergecap",
                "reordercap": "reordercap",
                "text2pcap": "text2pcap",
            },
            "com.calibre_ebook.calibre": {
                "calibre": "calibre",
                "ebook-viewer": "ebook-viewer",
                "ebook-edit": "ebook-edit",
                "lrfviewer": "lrfviewer",
                "ebook-convert": "ebook-convert",
                "ebook-meta": "ebook-meta",
                "calibredb": "calibredb",
                "calibre-server": "calibre-server",
                "calibre-smtp": "calibre-smtp",
                "calibre-customize": "calibre-customize",
                "calibre-debug": "calibre-debug",
            },
        }

        for app_id, commands in expected.items():
            with self.subTest(app_id=app_id):
                self.assertEqual(DEFAULT_EXPORT_COMMANDS[app_id], commands)

    def test_gnome_and_kde_apps_use_their_conventional_commands(self):
        expected = {
            "org.gnome.Calculator": {
                "gnome-calculator": "gnome-calculator",
            },
            "org.nongnu.enigma": {
                "enigma": "enigma",
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
