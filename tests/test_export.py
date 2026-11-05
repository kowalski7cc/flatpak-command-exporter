import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flatpak_command_exporter import __main__ as core


class ExportCommandsTests(unittest.TestCase):
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

    def run_export(self, refs, current_ref):
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
            get_current_installed_app=current_ref,
        )
        with (
            patch.object(
                core,
                "Flatpak",
                SimpleNamespace(Installation=SimpleNamespace(new_user=lambda: installation)),
            ),
            patch.object(core, "find_refs", return_value=refs),
            patch.object(
                core,
                "load_manifest",
                return_value={"x-export-commands": {"alias": "command"}},
            ),
            patch.object(core, "create_launcher") as create_launcher,
        ):
            core.export_commands()
        return create_launcher

    def test_exports_current_ref_when_app_has_multiple_branches(self):
        stable_ref = self.Ref("app.test", "stable")
        beta_ref = self.Ref("app.test", "beta")

        create_launcher = self.run_export(
            [stable_ref, beta_ref],
            lambda app_id, _cancellable: beta_ref,
        )

        create_launcher.assert_called_once_with(
            "app.test", "alias", "command", "x86_64", "beta"
        )

    def test_falls_back_to_last_enumerated_ref_when_current_is_missing(self):
        stable_ref = self.Ref("app.test", "stable")
        beta_ref = self.Ref("app.test", "beta")

        create_launcher = self.run_export(
            [stable_ref, beta_ref],
            lambda _app_id, _cancellable: None,
        )

        create_launcher.assert_called_once_with(
            "app.test", "alias", "command", "x86_64", "beta"
        )

    def test_falls_back_to_last_enumerated_ref_when_lookup_fails(self):
        stable_ref = self.Ref("app.test", "stable")
        beta_ref = self.Ref("app.test", "beta")

        def lookup_error(_app_id, _cancellable):
            raise core.GLib.Error("current ref unavailable")

        create_launcher = self.run_export(
            [stable_ref, beta_ref],
            lookup_error,
        )

        create_launcher.assert_called_once_with(
            "app.test", "alias", "command", "x86_64", "beta"
        )


if __name__ == "__main__":
    unittest.main()
