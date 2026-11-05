import unittest
from unittest.mock import Mock

import gi

gi.require_version("Polkit", "1.0")
from gi.repository import Gio, Polkit

from flatpak_command_exporter.system_service import (
    ACTION_ID,
    INTROSPECTION_XML,
    SystemOperationService,
)
from flatpak_command_exporter.system_bus import _METHOD_SIGNATURES


class SystemOperationServiceTests(unittest.TestCase):
    class Authorized:
        def get_is_authorized(self):
            return True

    class Denied:
        def get_is_authorized(self):
            return False

    class Parameters:
        def __init__(self, *values):
            self.values = values

        def unpack(self):
            return self.values

    class Invocation:
        def __init__(self):
            self.result = None
            self.error = None

        def return_value(self, value):
            self.result = value

        def return_dbus_error(self, name, message):
            self.error = name, message

    def test_authorizes_system_alias_change_before_dispatch(self):
        authority = Mock()
        authority.check_authorization_sync.return_value = self.Authorized()
        exporter = Mock()
        service = SystemOperationService(
            authority=authority,
            exporter_factory=lambda **_kwargs: exporter,
        )
        invocation = self.Invocation()

        service.on_method_call(
            None,
            ":1.42",
            None,
            None,
            "SetAliasEnabled",
            self.Parameters("org.example.App", "example", False),
            invocation,
        )

        authority.check_authorization_sync.assert_called_once()
        authorization_args = authority.check_authorization_sync.call_args.args
        self.assertEqual(authorization_args[1], ACTION_ID)
        self.assertEqual(
            authorization_args[3],
            Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
        )
        exporter.set_alias_enabled.assert_called_once_with(
            "org.example.App", "example", False
        )
        self.assertIsNone(invocation.error)
        self.assertEqual(invocation.result.get_type_string(), "()")

    def test_denied_authorization_does_not_dispatch_operation(self):
        authority = Mock()
        authority.check_authorization_sync.return_value = self.Denied()
        exporter_factory = Mock()
        service = SystemOperationService(
            authority=authority,
            exporter_factory=exporter_factory,
        )
        invocation = self.Invocation()

        service.on_method_call(
            None,
            ":1.42",
            None,
            None,
            "Export",
            self.Parameters(),
            invocation,
        )

        exporter_factory.assert_not_called()
        self.assertIn("NotAuthorized", invocation.error[0])

    def test_rejects_unknown_operation_in_service(self):
        service = SystemOperationService(
            authority=Mock(),
            exporter_factory=Mock(),
        )

        with self.assertRaises(ValueError):
            service.dispatch("RunCommand", ("arbitrary",))
        service.exporter_factory.assert_not_called()

    def test_filesystem_permission_error_is_not_reported_as_auth_denial(self):
        authority = Mock()
        authority.check_authorization_sync.return_value = self.Authorized()
        exporter = Mock()
        exporter.export_commands.side_effect = PermissionError("read-only system")
        service = SystemOperationService(
            authority=authority,
            exporter_factory=lambda **_kwargs: exporter,
        )
        invocation = self.Invocation()

        service.on_method_call(
            None,
            ":1.42",
            None,
            None,
            "Export",
            self.Parameters(),
            invocation,
        )
        self.assertIn(".Failed", invocation.error[0])
        self.assertIn(".Failed", invocation.error[0])

    def test_dbus_interface_exposes_only_fixed_system_operations(self):
        node = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
        interface = node.interfaces[0]

        signatures = {
            method.name: (
                "(" + "".join(arg.signature for arg in method.in_args) + ")",
                "(" + "".join(arg.signature for arg in method.out_args) + ")",
            )
            for method in interface.methods
        }
        self.assertEqual(signatures, _METHOD_SIGNATURES)

    def test_remove_returns_boolean_result(self):
        authority = Mock()
        authority.check_authorization_sync.return_value = self.Authorized()
        exporter = Mock()
        exporter.remove_custom_alias.return_value = True
        service = SystemOperationService(
            authority=authority,
            exporter_factory=lambda **_kwargs: exporter,
        )
        invocation = self.Invocation()

        service.on_method_call(
            None,
            ":1.42",
            None,
            None,
            "RemoveCustomAlias",
            self.Parameters("org.example.App", "example"),
            invocation,
        )

        self.assertEqual(invocation.result.get_type_string(), "(b)")
        self.assertEqual(invocation.result.unpack(), (True,))


if __name__ == "__main__":
    unittest.main()
