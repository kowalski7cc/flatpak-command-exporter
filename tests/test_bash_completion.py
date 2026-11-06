import os
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BashCompletionTests(unittest.TestCase):
    def generate_completion(self):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [
                "shtab",
                "--shell=bash",
                "-u",
                "flatpak_command_exporter.cli_parser.build_parser",
            ],
            check=True,
            capture_output=True,
            cwd=ROOT,
            env=environment,
            text=True,
        ).stdout

    def test_completion_covers_cli_commands_options_and_choices(self):
        completion = self.generate_completion()

        for token in (
            "export",
            "list",
            "add",
            "remove",
            "enable",
            "disable",
            "install-profile",
            "config",
            "help",
            "--system",
            "--user",
            "--all",
            "--complete",
            "--help",
            "default-export",
            "none",
        ):
            with self.subTest(token=token):
                self.assertIn(token, completion)
        self.assertRegex(completion, r"_config_pos_1_choices=\(all none\)")

    def test_completion_generation_is_repeatable_and_valid_bash(self):
        first = self.generate_completion()
        second = self.generate_completion()

        self.assertEqual(first, second)
        subprocess.run(["bash", "-n"], input=first, check=True, text=True)


if __name__ == "__main__":
    unittest.main()
