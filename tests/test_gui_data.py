import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flatpak_command_exporter import FlatpakCommandExporter
from flatpak_command_exporter.api import discovery as core
from flatpak_command_exporter.api import exporter as api_exporter
from flatpak_command_exporter.api.refs import _InstalledRef
from flatpak_command_exporter.gui import (
    find_desktop_file,
    get_exported_icon,
    get_project_details,
    main,
)
from flatpak_command_exporter.gui.data import get_app_ref_choices
from flatpak_command_exporter.gui.menu import create_main_menu


class AliasDataTests(unittest.TestCase):
    def test_app_ref_choices_are_unique_and_include_installation_scope(self):
        records = [
            SimpleNamespace(
                app_id="org.example.App",
                app_name="Example",
                arch="x86_64",
                branch="stable",
                installation_scope="system",
                alias="first",
            ),
            SimpleNamespace(
                app_id="org.example.App",
                app_name="Example",
                arch="x86_64",
                branch="stable",
                installation_scope="system",
                alias="second",
            ),
            SimpleNamespace(
                app_id="org.example.App",
                app_name="Example",
                arch="aarch64",
                branch="beta",
                installation_scope="user",
                alias="first",
            ),
        ]
        exporter = SimpleNamespace(
            get_exported_aliases=lambda: records,
        )

        self.assertEqual(
            get_app_ref_choices(exporter),
            [
                (
                    "Example (org.example.App, beta/aarch64, user installation)",
                    "org.example.App",
                ),
                (
                    "Example (org.example.App, stable/x86_64, system installation)",
                    "org.example.App",
                ),
            ],
        )

    def test_current_user_ref_overrides_system_and_system_only_app_remains(self):
        class Ref:
            def __init__(self, app_id, branch="stable"):
                self.app_id = app_id
                self.branch = branch

            def get_name(self):
                return self.app_id

            def get_arch(self):
                return "x86_64"

            def get_branch(self):
                return self.branch

        user_refs = [Ref("app.override"), Ref("app.override", "beta")]
        system_refs = [
            Ref("app.override"),
            Ref("app.override", "beta"),
            Ref("app.system-only"),
        ]
        user_installation = SimpleNamespace()
        system_installation = SimpleNamespace()
        installed_refs = [
            *(
                _InstalledRef(ref, user_installation, "/user", "user")
                for ref in user_refs
            ),
            _InstalledRef(system_refs[-1], system_installation, "/system", "system"),
        ]

        def load_manifest(path, app_id, _arch, branch):
            return {"x-export-commands": {f"{app_id}-{path}-{branch}": "command"}}

        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(
                    core,
                    "_get_installed_refs",
                    return_value=installed_refs,
                ),
                patch.object(core, "_read_manifest_or_empty", side_effect=load_manifest),
                patch.object(core, "load_metainfo", return_value=None),
            ):
                records = FlatpakCommandExporter().get_exported_aliases()

        self.assertEqual(
            [
                (
                    record.app_id,
                    record.branch,
                    record.installation_path,
                    record.installation_scope,
                )
                for record in records
            ],
            [
                ("app.override", "stable", "/user", "user"),
                ("app.override", "beta", "/user", "user"),
                ("app.system-only", "stable", "/system", "system"),
            ],
        )

    def test_explicit_scope_uses_its_configuration(self):
        exporter = FlatpakCommandExporter()

        with patch.object(
            api_exporter, "get_exported_aliases", return_value=[]
        ) as lookup:
            exporter.get_exported_aliases(scope="system")

        config = lookup.call_args.args[0]
        self.assertEqual(config.scope, "system")
        self.assertFalse(lookup.call_args.kwargs["include_system"])
        self.assertEqual(lookup.call_args.kwargs["scope"], "system")

    def test_system_alias_enabled_state_comes_from_system_configuration(self):
        class Ref:
            def get_name(self):
                return "app.system"

            def get_arch(self):
                return "x86_64"

            def get_branch(self):
                return "stable"

        ref = Ref()
        installed_ref = _InstalledRef(ref, SimpleNamespace(), "/system", "system")
        with tempfile.TemporaryDirectory() as data_home:
            config = core.AliasConfig(data_home, scope="system")
            config.set_default_policy("none")
            config.set_custom_alias("app.system", "custom", "custom-command")
            with (
                patch.object(core, "_get_installed_refs", return_value=[installed_ref]),
                patch.object(
                    core,
                    "_read_manifest_or_empty",
                    return_value={"x-export-commands": {"alias": "command"}},
                ),
                patch.object(core, "load_metainfo", return_value=None),
            ):
                records = core.get_exported_aliases(config, scope="system")

        self.assertEqual(len(records), 2)
        custom_record = next(record for record in records if record.alias == "custom")
        self.assertEqual(custom_record.installation_scope, "system")
        self.assertTrue(custom_record.enabled)
        self.assertEqual(custom_record.command, "custom-command")
        self.assertTrue(custom_record.custom)
        manifest_record = next(
            record for record in records if record.alias == "alias"
        )
        self.assertFalse(manifest_record.enabled)


class DesktopIconTests(unittest.TestCase):
    def test_reads_icon_from_flatpak_exported_desktop_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            share_directory = Path(temporary_directory) / "share"
            applications = share_directory / "applications"
            applications.mkdir(parents=True)
            (applications / "app.test.desktop").write_text(
                "[Desktop Entry]\nType=Application\nIcon=app.test-icon\n",
                encoding="utf-8",
            )
            record = SimpleNamespace(
                app_id="app.test",
                desktop_id="app.test.desktop",
                installation_path="/not-used",
            )

            self.assertEqual(
                get_exported_icon(record, [str(Path(temporary_directory))]),
                "app.test-icon",
            )

    def test_missing_desktop_file_has_no_icon(self):
        record = SimpleNamespace(
            app_id="app.missing",
            desktop_id="app.missing.desktop",
            installation_path="/not-used",
        )

        self.assertIsNone(get_exported_icon(record, []))


class ProjectMetadataTests(unittest.TestCase):
    def test_reads_version_and_authors_from_project_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_file = Path(temporary_directory) / "pyproject.toml"
            project_file.write_text(
                '[project]\nversion = "1.2.3"\nauthors = '
                '[{name = "First Author"}, {name = "Second Author"}]\n',
                encoding="utf-8",
            )

            self.assertEqual(
                get_project_details(project_file),
                ("1.2.3", ("First Author", "Second Author")),
            )

    def test_existing_module_keeps_main_and_default_metadata_imports(self):
        project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"

        self.assertTrue(callable(main))
        self.assertEqual(get_project_details(), get_project_details(project_file))

    def test_existing_module_exports_desktop_file_helper(self):
        self.assertTrue(callable(find_desktop_file))


class MainMenuTests(unittest.TestCase):
    def test_settings_and_about_are_direct_menu_items_in_order(self):
        class Menu:
            def __init__(self):
                self.items = []

            def append(self, label, action):
                self.items.append((label, action))

        gio = SimpleNamespace(Menu=Menu)

        menu = create_main_menu(gio)

        self.assertEqual(
            menu.items,
            [("Settings", "app.settings"), ("About", "app.about")],
        )

    def test_module_launcher_calls_gui_main(self):
        with patch("flatpak_command_exporter.gui.main") as main:
            runpy.run_module(
                "flatpak_command_exporter.gui.__main__",
                run_name="__main__",
            )

        main.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()