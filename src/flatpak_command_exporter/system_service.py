import logging

import gi

gi.require_version("Polkit", "1.0")
from gi.repository import Gio, GLib, Polkit

from .api import FlatpakCommandExporter
from .profile import install_profile
from .system_bus import (
    OBJECT_PATH,
    SERVICE_NAME,
)


ACTION_ID = "xyz.kowalski7cc.flatpak-command-exporter.manage-system-aliases"


class AuthorizationDenied(Exception):
    pass


INTROSPECTION_XML = """
<node>
  <interface name="xyz.kowalski7cc.FlatpakCommandExporter">
    <method name="Export"/>
    <method name="SetDefaultPolicy">
      <arg name="policy" type="s" direction="in"/>
    </method>
    <method name="SetAppEnabled">
      <arg name="app_id" type="s" direction="in"/>
      <arg name="enabled" type="b" direction="in"/>
    </method>
    <method name="SetAliasEnabled">
      <arg name="app_id" type="s" direction="in"/>
      <arg name="alias" type="s" direction="in"/>
      <arg name="enabled" type="b" direction="in"/>
    </method>
    <method name="AddCustomAlias">
      <arg name="app_id" type="s" direction="in"/>
      <arg name="alias" type="s" direction="in"/>
      <arg name="command" type="s" direction="in"/>
    </method>
    <method name="RemoveCustomAlias">
      <arg name="app_id" type="s" direction="in"/>
      <arg name="alias" type="s" direction="in"/>
      <arg name="removed" type="b" direction="out"/>
    </method>
    <method name="InstallProfile"/>
  </interface>
</node>
"""


class SystemOperationService:
    def __init__(self, authority=None, exporter_factory=FlatpakCommandExporter):
        self.authority = authority or Polkit.Authority.get_sync(None)
        self.exporter_factory = exporter_factory

    def authorize(self, sender):
        subject = Polkit.SystemBusName.new(sender)
        result = self.authority.check_authorization_sync(
            subject,
            ACTION_ID,
            None,
            Polkit.CheckAuthorizationFlags.ALLOW_USER_INTERACTION,
            None,
        )
        if not result.get_is_authorized():
            raise AuthorizationDenied("System operation was not authorized")

    def dispatch(self, method_name, arguments):
        if method_name == "InstallProfile":
            install_profile("system")
            return None

        if method_name not in {
            "Export",
            "SetDefaultPolicy",
            "SetAppEnabled",
            "SetAliasEnabled",
            "AddCustomAlias",
            "RemoveCustomAlias",
        }:
            raise ValueError(f"Unknown system operation: {method_name}")

        exporter = self.exporter_factory(scope="system")
        if method_name == "Export":
            exporter.export_commands()
            return None
        if method_name == "SetDefaultPolicy":
            exporter.set_default_policy(*arguments)
            return None
        if method_name == "SetAppEnabled":
            exporter.set_app_enabled(*arguments)
            return None
        if method_name == "SetAliasEnabled":
            exporter.set_alias_enabled(*arguments)
            return None
        if method_name == "AddCustomAlias":
            exporter.add_custom_alias(*arguments)
            return None
        if method_name == "RemoveCustomAlias":
            return exporter.remove_custom_alias(*arguments)
        raise ValueError(f"Unknown system operation: {method_name}")

    def on_method_call(
        self,
        _connection,
        sender,
        _object_path,
        _interface_name,
        method_name,
        parameters,
        invocation,
    ):
        try:
            self.authorize(sender)
            result = self.dispatch(method_name, parameters.unpack())
        except AuthorizationDenied as error:
            invocation.return_dbus_error(
                "xyz.kowalski7cc.FlatpakCommandExporter.NotAuthorized",
                str(error),
            )
        except (OSError, ValueError, GLib.Error) as error:
            invocation.return_dbus_error(
                "xyz.kowalski7cc.FlatpakCommandExporter.Failed",
                str(error),
            )
        else:
            if method_name == "RemoveCustomAlias":
                invocation.return_value(GLib.Variant("(b)", (result,)))
            else:
                invocation.return_value(GLib.Variant("()", ()))


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    service = SystemOperationService()
    introspection = Gio.DBusNodeInfo.new_for_xml(INTROSPECTION_XML)
    registration_id = connection.register_object(
        OBJECT_PATH,
        introspection.interfaces[0],
        service.on_method_call,
        None,
        None,
    )
    if not registration_id:
        raise RuntimeError(f"Could not register D-Bus object at {OBJECT_PATH}")

    loop = GLib.MainLoop()

    def name_lost(_connection, _name):
        logging.error("Lost ownership of D-Bus name %s", SERVICE_NAME)
        loop.quit()

    owner_id = Gio.bus_own_name_on_connection(
        connection,
        SERVICE_NAME,
        Gio.BusNameOwnerFlags.NONE,
        None,
        name_lost,
    )
    try:
        loop.run()
    finally:
        Gio.bus_unown_name(owner_id)
        connection.unregister_object(registration_id)


if __name__ == "__main__":
    main()
