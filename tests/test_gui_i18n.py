import gettext
import unittest
from pathlib import Path


LOCALE_DIR = (
    Path(__file__).parents[1]
    / "src"
    / "flatpak_command_exporter"
    / "gui"
    / "locale"
)
LANGUAGES = ("it", "fr", "de", "es", "ja", "hu", "pl", "cs")
MESSAGE_COUNT = 60


class GuiLocalizationTests(unittest.TestCase):
    def test_all_requested_locales_have_complete_catalogs(self):
        catalogs = {}
        for language in LANGUAGES:
            catalog_path = (
                LOCALE_DIR
                / language
                / "LC_MESSAGES"
                / "flatpak-command-exporter.mo"
            )
            with self.subTest(language=language):
                self.assertTrue(catalog_path.is_file())
                with catalog_path.open("rb") as catalog_file:
                    catalog = gettext.GNUTranslations(catalog_file)
                translated_messages = {
                    message: translation
                    for message, translation in catalog._catalog.items()
                    if message
                }
                self.assertEqual(len(translated_messages), MESSAGE_COUNT)
                self.assertTrue(all(translated_messages.values()))
                catalogs[language] = set(translated_messages)

        for language in LANGUAGES[1:]:
            self.assertEqual(catalogs[language], catalogs[LANGUAGES[0]])

    def test_localized_messages_and_english_fallback(self):
        french = gettext.translation(
            "flatpak-command-exporter",
            localedir=LOCALE_DIR,
            languages=["fr"],
        )
        self.assertEqual(french.gettext("Settings"), "Paramètres")
        self.assertEqual(
            french.gettext("Exported Commands"),
            "Commandes exportées",
        )

        fallback = gettext.translation(
            "flatpak-command-exporter",
            localedir=LOCALE_DIR,
            languages=["zz"],
            fallback=True,
        )
        self.assertEqual(fallback.gettext("Settings"), "Settings")
