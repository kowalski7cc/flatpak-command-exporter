import unittest
from unittest.mock import Mock, patch

from flatpak_command_exporter import system_bus


class SystemBusClientTests(unittest.TestCase):
    def test_calls_only_allowlisted_methods_with_declared_signatures(self):
        connection = Mock()
        with patch.object(system_bus.Gio, "bus_get_sync", return_value=connection):
            system_bus.call_system_method(
                "SetAliasEnabled", "org.example.App", "example", True
            )

        connection.call_sync.assert_called_once()
        call = connection.call_sync.call_args.args
        self.assertEqual(call[:4], (
            system_bus.SERVICE_NAME,
            system_bus.OBJECT_PATH,
            system_bus.INTERFACE_NAME,
            "SetAliasEnabled",
        ))
        self.assertEqual(call[4].get_type_string(), "(ssb)")
        self.assertEqual(call[4].unpack(), ("org.example.App", "example", True))
        self.assertEqual(call[5].dup_string(), "()")

    def test_unknown_method_is_rejected_before_bus_access(self):
        with (
            patch.object(system_bus.Gio, "bus_get_sync") as bus_get,
            self.assertRaises(ValueError),
        ):
            system_bus.call_system_method("RunCommand", "anything")

        bus_get.assert_not_called()

    def test_async_system_call_passes_callback_to_dbus(self):
        connection = Mock()
        callback = Mock()
        with patch.object(system_bus.Gio, "bus_get_sync", return_value=connection):
            system_bus.call_system_method_async(
                "SetAliasEnabled",
                ("org.example.App", "example", True),
                callback,
            )

        connection.call.assert_called_once()
        call = connection.call.call_args.args
        self.assertEqual(call[:4], (
            system_bus.SERVICE_NAME,
            system_bus.OBJECT_PATH,
            system_bus.INTERFACE_NAME,
            "SetAliasEnabled",
        ))
        self.assertEqual(call[4].unpack(), ("org.example.App", "example", True))
        self.assertIs(call[-1], callback)


if __name__ == "__main__":
    unittest.main()
