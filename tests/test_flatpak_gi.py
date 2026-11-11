import unittest
from unittest.mock import patch

from flatpak_command_exporter._flatpak_gi import require_flatpak_namespace


class FlatpakGiTests(unittest.TestCase):
    def test_missing_flatpak_namespace_has_actionable_error(self):
        cause = ValueError("Namespace Flatpak not available")

        with patch("gi.require_version", side_effect=cause):
            with self.assertRaisesRegex(ImportError, "Flatpak-1.0") as error:
                require_flatpak_namespace()

        self.assertIn("flatpak-libs on Fedora", str(error.exception))
        self.assertIs(error.exception.__cause__, cause)

    def test_unrelated_version_errors_are_preserved(self):
        cause = ValueError("Flatpak version 1.0 is incompatible")

        with patch("gi.require_version", side_effect=cause):
            with self.assertRaisesRegex(ValueError, "incompatible") as error:
                require_flatpak_namespace()

        self.assertIs(error.exception, cause)


if __name__ == "__main__":
    unittest.main()
