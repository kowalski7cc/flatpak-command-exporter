import os
import runpy
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

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
from flatpak_command_exporter.gui.accessibility import (
    set_accessible_label,
    set_decorative,
)
from flatpak_command_exporter.gui.data import (
    get_aliases_by_scope,
    get_app_ref_choices,
)
from flatpak_command_exporter.gui.menu import create_main_menu
from flatpak_command_exporter.gui.settings import (
    _configure_responsive_label,
    _handle_app_selection,
    _make_icon_button,
    _make_app_override_row,
    _reset_factory_preferences,
)
from flatpak_command_exporter.gui.application import (
    _app_commands_enabled,
    _group_app_aliases,
    _set_app_commands_enabled,
)


class AliasDataTests(unittest.TestCase):
    def test_aliases_by_scope_use_merged_and_installation_specific_refs(self):
        merged_records = [object()]
        user_records = [object()]
        system_records = [object()]
        calls = []

        def get_exported_aliases(
            *, include_system=True, scope=None, current_only=False
        ):
            calls.append((include_system, scope, current_only))
            if scope == "system":
                return system_records
            if scope == "user" and not include_system:
                return user_records
            return merged_records

        aliases_by_scope = get_aliases_by_scope(
            SimpleNamespace(get_exported_aliases=get_exported_aliases)
        )

        self.assertEqual(
            aliases_by_scope,
            {
                "all": merged_records,
                "user": user_records,
                "system": system_records,
            },
        )
        self.assertEqual(
            calls,
            [
                (True, None, True),
                (False, "user", True),
                (True, "system", True),
            ],
        )

    def test_group_app_aliases_creates_one_row_with_scope_specific_commands(self):
        user_record = SimpleNamespace(
            app_id="org.example.App",
            app_name="Example",
            arch="x86_64",
            branch="stable",
            installation_scope="user",
            alias="app-command",
        )
        system_record = SimpleNamespace(
            app_id="org.example.App",
            app_name="Example",
            arch="x86_64",
            branch="stable",
            installation_scope="system",
            alias="app-command",
        )

        groups = _group_app_aliases({
            "all": [user_record],
            "user": [user_record],
            "system": [system_record],
        })

        self.assertEqual(list(groups), ["org.example.App"])
        group = groups["org.example.App"]
        self.assertIs(group.record, user_record)
        self.assertEqual(group.scopes, {"all", "user", "system"})
        self.assertEqual(
            {
                record.installation_scope: scopes
                for _key, record, scopes in group.records
            },
            {
                "user": {"all", "user"},
                "system": {"system"},
            },
        )

    def test_current_only_aliases_use_preferred_installation_and_current_ref(self):
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

        user_stable = Ref("app.shared", "stable")
        user_beta = Ref("app.shared", "beta")
        system_stable = Ref("app.shared", "stable")
        system_beta = Ref("app.shared", "beta")
        system_only = Ref("app.system-only", "stable")
        user_installation = SimpleNamespace(
            get_current_installed_app=lambda _app_id, _cancellable: None,
        )
        system_installation = SimpleNamespace(
            get_current_installed_app=lambda app_id, _cancellable: (
                system_stable if app_id == "app.shared" else None
            ),
        )
        installed_refs = [
            _InstalledRef(user_stable, user_installation, "/user", "user"),
            _InstalledRef(user_beta, user_installation, "/user", "user"),
            _InstalledRef(system_stable, system_installation, "/system", "system"),
            _InstalledRef(system_beta, system_installation, "/system", "system"),
            _InstalledRef(system_only, system_installation, "/system", "system"),
        ]

        def load_manifest(path, app_id, _arch, branch):
            return {
                "x-export-commands": {
                    f"{app_id}-{path}-{branch}": "command",
                },
            }

        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "_get_installed_refs", return_value=installed_refs),
                patch.object(core, "_read_manifest_or_empty", side_effect=load_manifest),
                patch.object(core, "load_metainfo", return_value=None),
            ):
                merged_records = FlatpakCommandExporter().get_exported_aliases(
                    current_only=True
                )
                system_records = FlatpakCommandExporter().get_exported_aliases(
                    scope="system", current_only=True
                )

        self.assertEqual(
            [
                (record.app_id, record.branch, record.installation_scope)
                for record in merged_records
            ],
            [
                ("app.shared", "beta", "user"),
                ("app.system-only", "stable", "system"),
            ],
        )
        self.assertEqual(
            [
                (record.app_id, record.branch, record.installation_scope)
                for record in system_records
            ],
            [
                ("app.shared", "stable", "system"),
                ("app.system-only", "stable", "system"),
            ],
        )

    def test_app_switch_state_uses_all_command_states(self):
        records = [
            SimpleNamespace(
                app_id="org.example.App",
                alias="first",
                installation_scope="user",
                branch="stable",
            ),
            SimpleNamespace(
                app_id="org.example.App",
                alias="second",
                installation_scope="system",
                branch="beta",
            ),
            SimpleNamespace(
                app_id="org.example.App",
                alias="first",
                installation_scope="system",
                branch="stable",
            ),
        ]
        with tempfile.TemporaryDirectory() as data_home:
            config = core.AliasConfig(data_home)
            config.set_app_enabled("org.example.App", False)
            config.set_alias_enabled("org.example.App", "first", True)
            config.set_alias_enabled("org.example.App", "second", True)

            self.assertTrue(_app_commands_enabled(config, records))
            config.set_alias_enabled("org.example.App", "second", False)
            self.assertFalse(_app_commands_enabled(config, records))

            _set_app_commands_enabled(config, records, True)

            self.assertTrue(_app_commands_enabled(config, records))
            self.assertFalse(config.app_enabled("org.example.App"))

    def test_reset_factory_preferences_clears_app_and_alias_overrides(self):
        with tempfile.TemporaryDirectory() as data_home:
            config = core.AliasConfig(data_home)
            config.set_default_policy("none")
            config.set_app_enabled("org.example.Enabled", True)
            config.set_app_enabled("org.example.Disabled", False)
            config.set_alias_enabled("org.example.App", "command", False)
            config.set_custom_alias("org.example.App", "custom", "custom-command")

            default_policy = _reset_factory_preferences(config)

            self.assertEqual(default_policy, "all")
            self.assertEqual(config.default_policy(), "all")
            self.assertEqual(config.app_overrides(), {})
            self.assertIsNone(config.alias_enabled("org.example.App", "command"))
            self.assertEqual(
                config.custom_aliases("org.example.App"),
                {"custom": "custom-command"},
            )

    def test_reset_factory_preferences_uses_system_default(self):
        with tempfile.TemporaryDirectory() as data_home:
            config = core.AliasConfig(data_home, scope="system")
            config.set_default_policy("all")
            config.set_app_enabled("org.example.App", True)

            default_policy = _reset_factory_preferences(config)

            self.assertEqual(default_policy, "none")
            self.assertEqual(config.default_policy(), "none")
            self.assertEqual(config.app_overrides(), {})

    def test_app_ref_choices_merge_refs_by_app_id(self):
        records = [
            SimpleNamespace(
                app_id="org.example.App",
                app_name="Example",
                arch="x86_64",
                branch="stable",
                installation_scope="system",
                installation_path="/system",
                desktop_id="org.example.App.desktop",
                alias="first",
            ),
            SimpleNamespace(
                app_id="org.example.App",
                app_name="Example",
                arch="x86_64",
                branch="stable",
                installation_scope="system",
                installation_path="/system",
                desktop_id="org.example.App.desktop",
                alias="second",
            ),
            SimpleNamespace(
                app_id="org.example.App",
                app_name="Example",
                arch="aarch64",
                branch="beta",
                installation_scope="user",
                installation_path="/user",
                desktop_id="org.example.App.desktop",
                alias="first",
            ),
            SimpleNamespace(
                app_id="org.example.Other",
                app_name="Another",
                arch="x86_64",
                branch="stable",
                installation_scope="user",
                installation_path="/user",
                desktop_id="org.example.Other.desktop",
                alias="other",
            ),
        ]
        exporter = SimpleNamespace(
            get_exported_aliases=lambda: records,
        )

        choices = get_app_ref_choices(exporter)

        self.assertEqual(
            [label for label, _record in choices],
            [
                "Another (org.example.Other)",
                "Example (org.example.App)",
            ],
        )
        self.assertEqual(
            [
                (
                    record.installation_scope,
                    record.installation_path,
                    record.desktop_id,
                )
                for _label, record in choices
            ],
            [
                ("user", "/user", "org.example.Other.desktop"),
                ("user", "/user", "org.example.App.desktop"),
            ],
        )
        self.assertEqual(
            get_app_ref_choices(SimpleNamespace(
                get_exported_aliases=lambda: list(reversed(records))
            )),
            choices,
        )

    def test_override_row_shows_app_name_id_icon_and_remove_button(self):
        class ActionRow:
            def __init__(self, title, subtitle):
                self.title = title
                self.subtitle = subtitle
                self.prefixes = []
                self.suffixes = []

            def add_prefix(self, widget):
                self.prefixes.append(widget)

            def add_suffix(self, widget):
                self.suffixes.append(widget)

        icon = object()
        remove_button = object()
        adw = SimpleNamespace(ActionRow=ActionRow)

        row = _make_app_override_row(
            adw, "org.example.App", "Example", icon, remove_button
        )

        self.assertEqual(row.title, "Example")
        self.assertEqual(row.subtitle, "org.example.App")
        self.assertEqual(row.prefixes, [icon])
        self.assertEqual(row.suffixes, [remove_button])

    def test_chooser_labels_wrap_for_scalable_text(self):
        class Label:
            def set_xalign(self, value):
                self.xalign = value

            def set_hexpand(self, value):
                self.hexpand = value

            def set_wrap(self, value):
                self.wrap = value

            def set_wrap_mode(self, mode):
                self.wrap_mode = mode

        word_char = object()
        label = Label()

        _configure_responsive_label(
            label, SimpleNamespace(WrapMode=SimpleNamespace(WORD_CHAR=word_char))
        )

        self.assertEqual(label.xalign, 0)
        self.assertTrue(label.hexpand)
        self.assertTrue(label.wrap)
        self.assertIs(label.wrap_mode, word_char)

    def test_accessible_label_sets_the_gtk_label_property(self):
        class Widget:
            def update_property(self, properties, values):
                self.accessible_properties = (properties, values)

        accessible_label = object()
        widget = Widget()

        set_accessible_label(
            widget,
            SimpleNamespace(
                AccessibleProperty=SimpleNamespace(LABEL=accessible_label)
            ),
            "Search apps and commands",
        )

        self.assertEqual(
            widget.accessible_properties,
            ([accessible_label], ["Search apps and commands"]),
        )

    def test_decorative_images_are_hidden_from_the_accessibility_tree(self):
        class Widget:
            def set_accessible_role(self, role):
                self.accessible_role = role

        presentation = object()
        widget = Widget()

        set_decorative(
            widget,
            SimpleNamespace(
                AccessibleRole=SimpleNamespace(PRESENTATION=presentation)
            ),
        )

        self.assertIs(widget.accessible_role, presentation)

    def test_override_action_buttons_use_symbolic_icons_and_accessible_labels(self):
        class Button:
            @classmethod
            def new_from_icon_name(cls, icon_name):
                button = cls()
                button.icon_name = icon_name
                return button

            def set_tooltip_text(self, text):
                self.tooltip = text

            def update_property(self, properties, values):
                self.accessible_properties = (properties, values)

            def set_valign(self, alignment):
                self.alignment = alignment

        accessible_label = object()
        center = object()
        gtk = SimpleNamespace(
            Button=Button,
            AccessibleProperty=SimpleNamespace(LABEL=accessible_label),
            Align=SimpleNamespace(CENTER=center),
        )

        buttons = [
            _make_icon_button(gtk, "list-add-symbolic", "Add app override"),
            _make_icon_button(
                gtk, "list-remove-symbolic", "Remove app override"
            ),
        ]

        self.assertEqual(
            [button.icon_name for button in buttons],
            ["list-add-symbolic", "list-remove-symbolic"],
        )
        self.assertEqual(
            [button.tooltip for button in buttons],
            ["Add app override", "Remove app override"],
        )
        self.assertEqual(
            [button.accessible_properties for button in buttons],
            [
                ([accessible_label], ["Add app override"]),
                ([accessible_label], ["Remove app override"]),
            ],
        )
        self.assertTrue(all(button.alignment is center for button in buttons))

    def test_selecting_app_ref_saves_override_once_and_closes_chooser(self):
        class SelectionMark:
            def set_visible(self, visible):
                self.visible = visible

        selected_row = object()
        other_row = object()
        selected_mark = SelectionMark()
        other_mark = SelectionMark()
        record = SimpleNamespace(app_id="org.example.App")
        save_override = Mock(return_value=True)
        close_chooser = Mock()

        _handle_app_selection(
            selected_row,
            {selected_row: record},
            {
                selected_row: selected_mark,
                other_row: other_mark,
            },
            False,
            save_override,
            close_chooser,
        )

        save_override.assert_called_once_with("org.example.App", False)
        close_chooser.assert_called_once_with()
        self.assertTrue(selected_mark.visible)
        self.assertFalse(other_mark.visible)

    def test_failed_app_override_save_keeps_chooser_open(self):
        selected_row = object()
        save_override = Mock(return_value=False)
        close_chooser = Mock()

        _handle_app_selection(
            selected_row,
            {selected_row: SimpleNamespace(app_id="org.example.App")},
            {selected_row: SimpleNamespace(set_visible=lambda _visible: None)},
            True,
            save_override,
            close_chooser,
        )

        save_override.assert_called_once_with("org.example.App", True)
        close_chooser.assert_not_called()

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