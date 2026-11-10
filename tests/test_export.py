import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import call, patch

from gi.repository import GLib

from flatpak_command_exporter.api import launchers as core
from flatpak_command_exporter.api.refs import _InstalledRef


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

    def run_export(self, refs, current_ref, configure=None, app_id=None):
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
            get_current_installed_app=current_ref,
        )
        installed_refs = [
            _InstalledRef(ref, installation, "/user", "user") for ref in refs
        ]
        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=installed_refs),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    return_value={"x-export-commands": {"alias": "command"}},
                ),
                patch.object(core, "create_launcher") as create_launcher,
                patch.object(core, "remove_launcher") as remove_launcher,
            ):
                if configure is not None:
                    configure(core.AliasConfig())
                core.export_commands(app_id=app_id)
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

    def test_export_logs_scope_and_launcher_summary(self):
        with self.assertLogs(level="INFO") as logs:
            self.run_export(
                [self.Ref("app.test", "stable")],
                lambda app_id, _cancellable: self.Ref(app_id, "stable"),
            )

        self.assertIn("Exporting Flatpak commands for user scope", logs.output[0])
        self.assertIn("Exported 1 launchers", logs.output[-1])

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
            raise GLib.Error("current ref unavailable")

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

    def test_custom_alias_is_exported_without_a_manifest(self):
        ref = self.Ref("app.test", "stable")
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
            get_current_installed_app=lambda _app_id, _cancellable: None,
        )
        installed_ref = _InstalledRef(ref, installation, "/user", "user")
        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=[installed_ref]),
                patch.object(core, "_read_manifest_or_empty", return_value=None),
                patch.object(core, "create_launcher") as create_launcher,
                patch.object(core, "remove_launcher"),
            ):
                config = core.AliasConfig()
                config.set_default_policy("none")
                config.set_custom_alias(
                    "app.test", "custom", "custom-command"
                )
                config.set_alias_enabled("app.test", "custom", True)

                core.export_commands(config)

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

    def test_app_export_only_updates_that_apps_launchers(self):
        refs = [
            self.Ref("app.target", "stable"),
            self.Ref("app.other", "stable"),
        ]
        manifests = {
            "app.target": {"x-export-commands": {"target-alias": "target-command"}},
            "app.other": {"x-export-commands": {"other-alias": "other-command"}},
        }

        with tempfile.TemporaryDirectory() as data_home:
            installation = SimpleNamespace(
                get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
                get_current_installed_app=lambda _app_id, _cancellable: None,
            )
            installed_refs = [
                _InstalledRef(ref, installation, "/user", "user") for ref in refs
            ]
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=installed_refs),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    side_effect=lambda _path, app_id, _arch, _branch: manifests[app_id],
                ),
                patch.object(core, "create_launcher") as create_launcher,
                patch.object(core, "remove_launcher") as remove_launcher,
            ):
                config = core.AliasConfig()
                config.set_alias_enabled("app.other", "other-alias", False)
                core.export_commands(config, app_id="app.target")

        create_launcher.assert_called_once_with(
            "app.target", "target-alias", "target-command", "x86_64", "stable"
        )
        remove_launcher.assert_not_called()

    def test_app_export_preserves_active_alias_from_another_app(self):
        refs = [
            self.Ref("app.target", "stable"),
            self.Ref("app.other", "stable"),
        ]
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
            get_current_installed_app=lambda _app_id, _cancellable: None,
        )
        installed_refs = [
            _InstalledRef(ref, installation, "/user", "user") for ref in refs
        ]
        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=installed_refs),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    side_effect=lambda _path, app_id, _arch, _branch: {
                        "x-export-commands": {"shared-alias": "command"}
                    },
                ),
                patch.object(core, "create_launcher") as create_launcher,
                patch.object(core, "remove_launcher") as remove_launcher,
            ):
                config = core.AliasConfig()
                config.set_alias_enabled("app.target", "shared-alias", False)
                core.export_commands(config, app_id="app.target")

        create_launcher.assert_not_called()
        remove_launcher.assert_not_called()

    def test_disabled_system_alias_removes_system_launcher(self):
        ref = self.Ref("app.test", "stable")
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/system"),
            get_current_installed_app=lambda _app_id, _cancellable: ref,
        )

        with tempfile.TemporaryDirectory() as data_home:
            config = core.AliasConfig(data_home, scope="system")
            config.set_default_policy("none")
            with (
                patch.object(
                    core,
                    "_get_installed_refs",
                    return_value=[
                        _InstalledRef(ref, installation, "/system", "system")
                    ],
                ),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    return_value={"x-export-commands": {"alias": "command"}},
                ),
                patch.object(core, "create_launcher") as create_launcher,
                patch.object(core, "remove_launcher") as remove_launcher,
            ):
                core.export_commands(config)

        create_launcher.assert_not_called()
        remove_launcher.assert_called_once_with("alias", scope="system")

    def test_enabled_system_custom_alias_is_exported(self):
        ref = self.Ref("app.test", "stable")
        installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/system"),
            get_current_installed_app=lambda _app_id, _cancellable: ref,
        )
        with tempfile.TemporaryDirectory() as data_home:
            config = core.AliasConfig(data_home, scope="system")
            config.set_default_policy("none")
            config.set_custom_alias("app.test", "custom", "custom-command")
            with (
                patch.object(
                    core,
                    "_get_installed_refs",
                    return_value=[
                        _InstalledRef(ref, installation, "/system", "system")
                    ],
                ),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    return_value={"x-export-commands": {"manifest-alias": "command"}},
                ),
                patch.object(core, "create_launcher") as create_launcher,
                patch.object(core, "remove_launcher"),
            ):
                core.export_commands(config)

        create_launcher.assert_called_once_with(
            "app.test",
            "custom",
            "custom-command",
            "x86_64",
            "stable",
            scope="system",
        )

    def test_user_export_merges_system_refs_and_prefers_user_alias_collision(self):
        user_ref = self.Ref("app.user", "stable")
        system_ref = self.Ref("app.system", "stable")
        user_installation = SimpleNamespace(
            get_current_installed_app=lambda _app_id, _cancellable: user_ref,
        )
        system_installation = SimpleNamespace(
            get_current_installed_app=lambda _app_id, _cancellable: system_ref,
        )
        installed_refs = [
            _InstalledRef(user_ref, user_installation, "/user", "user"),
            _InstalledRef(system_ref, system_installation, "/system", "system"),
        ]

        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=installed_refs),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    side_effect=lambda _path, app_id, _arch, _branch: {
                        "x-export-commands": {
                            "shared": app_id,
                            f"{app_id}-command": app_id,
                        }
                    },
                ),
                patch.object(core, "create_launcher") as create_launcher,
            ):
                core.export_commands()

        create_launcher.assert_has_calls(
            [
                call(
                    "app.user",
                    "shared",
                    "app.user",
                    "x86_64",
                    "stable",
                ),
                call(
                    "app.user",
                    "app.user-command",
                    "app.user",
                    "x86_64",
                    "stable",
                ),
                call(
                    "app.system",
                    "app.system-command",
                    "app.system",
                    "x86_64",
                    "stable",
                ),
            ],
            any_order=True,
        )
        self.assertEqual(create_launcher.call_count, 3)

    def test_user_export_visits_all_branches_and_prefers_the_current_ref(self):
        stable_ref = self.Ref("app.test", "stable")
        beta_ref = self.Ref("app.test", "beta")
        installation = SimpleNamespace(
            get_current_installed_app=lambda _app_id, _cancellable: beta_ref,
        )
        installed_refs = [
            _InstalledRef(stable_ref, installation, "/user", "user"),
            _InstalledRef(beta_ref, installation, "/user", "user"),
        ]

        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=installed_refs),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    side_effect=lambda _path, _app_id, _arch, branch: {
                        "x-export-commands": (
                            {
                                "shared": "beta-command",
                                "beta-only": "beta-command",
                            }
                            if branch == "beta"
                            else {
                                "shared": "stable-command",
                                "stable-only": "stable-command",
                            }
                        )
                    },
                ),
                patch.object(core, "create_launcher") as create_launcher,
            ):
                core.export_commands()

        self.assertEqual(create_launcher.call_count, 3)
        create_launcher.assert_has_calls(
            [
                call(
                    "app.test",
                    "shared",
                    "beta-command",
                    "x86_64",
                    "beta",
                ),
                call(
                    "app.test",
                    "beta-only",
                    "beta-command",
                    "x86_64",
                    "beta",
                ),
                call(
                    "app.test",
                    "stable-only",
                    "stable-command",
                    "x86_64",
                    "stable",
                ),
            ],
            any_order=True,
        )

    def test_disabled_user_override_masks_system_export(self):
        ref = self.Ref("app.test", "stable")
        installation = SimpleNamespace(
            get_current_installed_app=lambda _app_id, _cancellable: ref,
        )
        installed_ref = _InstalledRef(ref, installation, "/user", "user")

        with tempfile.TemporaryDirectory() as data_home:
            system_export_directory = Path(data_home) / "system-commands"
            system_export_directory.mkdir()
            (system_export_directory / "alias").write_text("# system launcher\n")
            config = core.AliasConfig(data_home)
            config.set_default_policy("none")
            real_config = core.AliasConfig

            def config_factory(data_home=None, *, scope="user"):
                if scope == "system":
                    return SimpleNamespace(export_directory=system_export_directory)
                return real_config(data_home, scope=scope)

            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "AliasConfig", side_effect=config_factory),
                patch.object(core, "_get_installed_refs", return_value=[installed_ref]),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    return_value={"x-export-commands": {"alias": "command"}},
                ),
            ):
                core.export_commands(config)

            mask_path = Path(data_home) / "flatpak-commands" / "alias"
            result = subprocess.run(
                [str(mask_path)],
                capture_output=True,
                check=False,
                text=True,
            )

        self.assertEqual(result.returncode, 127)
        self.assertIn("is disabled by the user configuration", result.stderr)


if __name__ == "__main__":
    unittest.main()
