import contextlib
import io
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flatpak_command_exporter import application as core
from flatpak_command_exporter import cli


class ListAllCommandsTests(unittest.TestCase):
    class Ref:
        def __init__(self, app_id, branch):
            self.app_id = app_id
            self.branch = branch

        def get_name(self):
            return self.app_id

        def get_arch(self):
            return "x86_64"

        def get_branch(self):
            return self.branch

    def run_list(self, app_id=None):
        user_ref = self.Ref("app.test", "stable")
        user_beta_ref = self.Ref("app.test", "beta")
        system_ref = self.Ref("app.other", "stable")
        user_installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user")
        )
        system_installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/system")
        )
        installations = SimpleNamespace(
            new_user=lambda: user_installation,
            new_system=lambda: system_installation,
        )
        refs = {
            id(user_installation): [user_ref, user_beta_ref],
            id(system_installation): [system_ref],
        }

        def load_manifest(path, ref_app_id, _arch, branch):
            return {"x-export-commands": {f"{ref_app_id}-{branch}": "command"}}

        output = io.StringIO()
        with (
            patch.object(core, "Flatpak", SimpleNamespace(Installation=installations)),
            patch.object(core, "find_refs", side_effect=lambda installation: refs[id(installation)]),
            patch.object(core, "load_manifest", side_effect=load_manifest),
            patch.object(core, "load_metainfo", return_value=None),
            contextlib.redirect_stdout(output),
        ):
            arguments = ["flatshell", "list", "--all"]
            if app_id is not None:
                arguments.append(app_id)
            arguments.append("--complete")
            with patch.object(sys, "argv", arguments):
                cli.main()
        return output.getvalue()

    def test_lists_every_ref_from_user_and_system_installations(self):
        output = self.run_list()

        self.assertIn("(app.test, stable/x86_64, /user)", output)
        self.assertIn("(app.test, beta/x86_64, /user)", output)
        self.assertIn("(app.other, stable/x86_64, /system)", output)
        self.assertIn("- app.test-stable -> command", output)
        self.assertIn("- app.test-beta -> command", output)
        self.assertIn("- app.other-stable -> command", output)

    def test_app_id_filters_all_installation_refs(self):
        output = self.run_list("app.test")

        self.assertIn("(app.test, stable/x86_64, /user)", output)
        self.assertIn("(app.test, beta/x86_64, /user)", output)
        self.assertNotIn("app.other", output)

    def test_cli_allows_app_id_to_be_omitted_only_with_all(self):
        with (
            patch.object(sys, "argv", ["flatshell", "list", "--all"]),
            patch.object(cli.FlatpakCommandExporter, "get_command_groups") as get_groups,
        ):
            get_groups.return_value = []
            cli.main()

        get_groups.assert_called_once_with(None)

    def test_cli_preserves_existing_app_specific_mode(self):
        with (
            patch.object(sys, "argv", ["flatshell", "list", "app.test"]),
            patch.object(cli.FlatpakCommandExporter, "get_command_groups") as get_groups,
        ):
            get_groups.return_value = []
            cli.main()

        get_groups.assert_called_once_with(
            "app.test", include_system=False, first_only=True
        )

    def test_cli_requires_app_id_without_all(self):
        error = io.StringIO()
        with (
            patch.object(sys, "argv", ["flatshell", "list"]),
            contextlib.redirect_stderr(error),
            self.assertRaises(SystemExit) as exit_info,
        ):
            cli.main()

        self.assertEqual(exit_info.exception.code, 2)
        self.assertIn("app_id is required unless --all is specified", error.getvalue())


if __name__ == "__main__":
    unittest.main()
