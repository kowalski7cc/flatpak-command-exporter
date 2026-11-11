import unittest
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

from flatpak_command_exporter.gui.settings import _add_user_service_group
from flatpak_command_exporter.gui.systemd import (
    get_user_service_state,
    set_user_service_enabled,
    user_service_is_enabled,
)


class FakeVariant:
    def __init__(self, signature, value):
        self.signature = signature
        self.value = value

    def unpack(self):
        return (self.value,)


class FakeConnection:
    def __init__(self, state="disabled", errors=None):
        self.state = state
        self.errors = errors or {}
        self.calls = []

    def call_sync(self, *args):
        method = args[3]
        parameters = args[4]
        self.calls.append((method, parameters.signature, parameters.value))
        error = self.errors.get(method)
        if isinstance(error, list):
            error = error.pop(0)
        if error is not None:
            raise error
        return FakeVariant("()", self.state)


class UserServiceSystemdTests(unittest.TestCase):
    def setUp(self):
        self.connection = FakeConnection()
        self.gio = SimpleNamespace(
            BusType=SimpleNamespace(SESSION=object()),
            DBusCallFlags=SimpleNamespace(NONE=object()),
            bus_get_sync=Mock(return_value=self.connection),
        )
        self.glib = SimpleNamespace(
            Error=type("FakeGLibError", (Exception,), {}),
            Variant=FakeVariant,
        )

    def test_queries_unit_file_state_from_the_user_manager(self):
        self.connection.state = "enabled"

        state = get_user_service_state(self.gio, self.glib)

        self.assertEqual(state, "enabled")
        self.assertEqual(
            self.connection.calls,
            [
                (
                    "GetUnitFileState",
                    "(s)",
                    ("flatpak-command-exporter-user.service",),
                )
            ],
        )
        self.gio.bus_get_sync.assert_called_once_with(
            self.gio.BusType.SESSION, None
        )

    def test_enablement_state_recognizes_systemd_enabled_variants(self):
        for state in ("enabled", "enabled-runtime", "linked", "linked-runtime"):
            with self.subTest(state=state):
                self.assertTrue(user_service_is_enabled(state))
        for state in ("disabled", "masked", "not-found"):
            with self.subTest(state=state):
                self.assertFalse(user_service_is_enabled(state))

    def test_enabling_unmasks_enables_then_starts_the_user_service(self):
        set_user_service_enabled(self.gio, self.glib, True)

        self.assertEqual(
            self.connection.calls,
            [
                (
                    "UnmaskUnitFiles",
                    "(asb)",
                    (["flatpak-command-exporter-user.service"], False),
                ),
                ("Reload", "()", ()),
                (
                    "EnableUnitFiles",
                    "(asbb)",
                    (["flatpak-command-exporter-user.service"], False, False),
                ),
                (
                    "StartUnit",
                    "(ss)",
                    ("flatpak-command-exporter-user.service", "replace"),
                ),
            ],
        )

    def test_disabling_masks_then_stops_the_user_service(self):
        set_user_service_enabled(self.gio, self.glib, False)

        self.assertEqual(
            self.connection.calls,
            [
                (
                    "MaskUnitFiles",
                    "(asbb)",
                    (["flatpak-command-exporter-user.service"], False, False),
                ),
                ("Reload", "()", ()),
                (
                    "StopUnit",
                    "(ss)",
                    ("flatpak-command-exporter-user.service", "replace"),
                ),
            ],
        )

    def test_settings_only_adds_the_group_when_the_unit_is_present(self):
        self.connection.state = "not-found"
        page = Mock()
        adw = SimpleNamespace(PreferencesGroup=Mock(), SwitchRow=Mock())
        report_error = Mock()

        row = _add_user_service_group(
            page, adw, Mock(), self.gio, self.glib, report_error
        )

        self.assertIsNone(row)
        page.add.assert_not_called()
        adw.SwitchRow.assert_not_called()
        report_error.assert_not_called()

    def test_settings_toggle_uses_dbus_to_enable_the_user_service(self):
        self.connection.state = "disabled"
        page = Mock()
        group = Mock()
        row = Mock()
        adw = SimpleNamespace(
            PreferencesGroup=Mock(return_value=group),
            SwitchRow=Mock(return_value=row),
        )
        report_error = Mock()

        with patch(
            "flatpak_command_exporter.gui.settings.set_accessible_label"
        ):
            result = _add_user_service_group(
                page, adw, Mock(), self.gio, self.glib, report_error
            )

        self.assertIs(result, row)
        row.set_active.assert_called_once_with(False)
        group.add.assert_called_once_with(row)
        page.add.assert_called_once_with(group)
        row.get_active.return_value = True
        row.connect.call_args.args[1](row, None)

        self.assertEqual(
            [method for method, _signature, _parameters in self.connection.calls],
            [
                "GetUnitFileState",
                "UnmaskUnitFiles",
                "Reload",
                "EnableUnitFiles",
                "StartUnit",
            ],
        )
        report_error.assert_not_called()

    def test_settings_toggle_restores_actual_enablement_after_dbus_error(self):
        error = self.glib.Error("could not mask service")
        self.connection.state = "enabled"
        self.connection.errors["MaskUnitFiles"] = error
        page = Mock()
        group = Mock()
        row = Mock()
        adw = SimpleNamespace(
            PreferencesGroup=Mock(return_value=group),
            SwitchRow=Mock(return_value=row),
        )
        report_error = Mock()

        with patch(
            "flatpak_command_exporter.gui.settings.set_accessible_label"
        ):
            _add_user_service_group(
                page, adw, Mock(), self.gio, self.glib, report_error
            )

        row.get_active.return_value = False
        row.connect.call_args.args[1](row, None)

        row.handler_block.assert_called_once_with(row.connect.return_value)
        row.set_active.assert_any_call(True)
        row.handler_unblock.assert_called_once_with(row.connect.return_value)
        report_error.assert_called_once_with(
            "Could not update user service", error
        )

    def test_settings_toggle_disables_switch_if_status_cannot_be_refreshed(self):
        action_error = self.glib.Error("could not mask service")
        status_error = self.glib.Error("could not query unit state")
        self.connection.state = "enabled"
        self.connection.errors["MaskUnitFiles"] = action_error
        self.connection.errors["GetUnitFileState"] = [None, status_error]
        page = Mock()
        group = Mock()
        row = Mock()
        adw = SimpleNamespace(
            PreferencesGroup=Mock(return_value=group),
            SwitchRow=Mock(return_value=row),
        )
        report_error = Mock()

        with patch(
            "flatpak_command_exporter.gui.settings.set_accessible_label"
        ):
            _add_user_service_group(
                page, adw, Mock(), self.gio, self.glib, report_error
            )

        row.get_active.return_value = False
        row.connect.call_args.args[1](row, None)

        row.set_active.assert_any_call(True)
        row.set_sensitive.assert_called_once_with(False)
        self.assertEqual(
            report_error.call_args_list,
            [
                call("Could not check user service status", status_error),
                call("Could not update user service", action_error),
            ],
        )


if __name__ == "__main__":
    unittest.main()
