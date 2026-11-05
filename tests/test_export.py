import os
import tempfile
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

    def run_export(self, refs, current_ref, configure=None):
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
            get_current_installed_app=current_ref,
        )
        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
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
                patch.object(core, "remove_launcher") as remove_launcher,
            ):
                if configure is not None:
                    configure(core.AliasConfig())
                core.export_commands()
        return create_launcher, remove_launcher

    def test_exports_current_ref_when_app_has_multiple_branches(self):
        stable_ref = self.Ref("app.test", "stable")
        beta_ref = self.Ref("app.test", "beta")

        create_launcher, _remove_launcher = self.run_export(
            [stable_ref, beta_ref],
            lambda app_id, _cancellable: beta_ref,
        )

        create_launcher.assert_called_once_with(
            "app.test", "alias", "command", "x86_64", "beta"
        )

    def test_falls_back_to_last_enumerated_ref_when_current_is_missing(self):
        stable_ref = self.Ref("app.test", "stable")
        beta_ref = self.Ref("app.test", "beta")

        create_launcher, _remove_launcher = self.run_export(
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

        create_launcher, _remove_launcher = self.run_export(
            [stable_ref, beta_ref],
            lookup_error,
        )

        create_launcher.assert_called_once_with(
            "app.test", "alias", "command", "x86_64", "beta"
        )

    def test_disabled_alias_removes_an_existing_launcher(self):
        create_launcher, remove_launcher = self.run_export(
            [self.Ref("app.test", "stable")],
            lambda _app_id, _cancellable: None,
            configure=lambda config: config.set_default_policy("none"),
        )

        create_launcher.assert_not_called()
        remove_launcher.assert_called_once_with("alias")

    def test_enabled_custom_alias_is_exported(self):
        def configure(config):
            config.set_default_policy("none")
            config.set_custom_alias("app.test", "custom", "custom-command")
            config.set_alias_enabled("app.test", "custom", True)

        create_launcher, _remove_launcher = self.run_export(
            [self.Ref("app.test", "stable")],
            lambda _app_id, _cancellable: None,
            configure=configure,
        )

        create_launcher.assert_called_once_with(
            "app.test", "custom", "custom-command", "x86_64", "stable"
        )

    def test_disabled_alias_does_not_remove_another_apps_enabled_alias(self):
        create_launcher, remove_launcher = self.run_export(
            [
                self.Ref("app.disabled", "stable"),
                self.Ref("app.enabled", "stable"),
            ],
            lambda _app_id, _cancellable: None,
            configure=lambda config: config.set_alias_enabled(
                "app.disabled", "alias", False
            ),
        )

        create_launcher.assert_called_once_with(
            "app.enabled", "alias", "command", "x86_64", "stable"
        )
        remove_launcher.assert_not_called()


if __name__ == "__main__":
    unittest.main()
