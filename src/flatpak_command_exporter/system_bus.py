from gi.repository import Gio, GLib


SERVICE_NAME = "xyz.kowalski7cc.FlatpakCommandExporter"
OBJECT_PATH = "/xyz/kowalski7cc/FlatpakCommandExporter"
INTERFACE_NAME = "xyz.kowalski7cc.FlatpakCommandExporter"

_METHOD_SIGNATURES = {
    "Export": ("()", "()"),
    "SetDefaultPolicy": ("(s)", "()"),
    "SetAppEnabled": ("(sb)", "()"),
    "SetAliasEnabled": ("(ssb)", "()"),
    "AddCustomAlias": ("(sss)", "()"),
    "RemoveCustomAlias": ("(ss)", "(b)"),
    "InstallProfile": ("()", "()"),
}


def _validate_method(method_name):
    if method_name not in _METHOD_SIGNATURES:
        raise ValueError(f"Unknown system operation: {method_name}")
    return _METHOD_SIGNATURES[method_name]


def call_system_method(method_name, *arguments):
    _input_signature, output_signature = _validate_method(method_name)
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    return connection.call_sync(
        SERVICE_NAME,
        OBJECT_PATH,
        INTERFACE_NAME,
        method_name,
        GLib.Variant(_input_signature, arguments),
        GLib.VariantType.new(output_signature),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
    )


def call_system_method_async(method_name, arguments, callback):
    input_signature, output_signature = _validate_method(method_name)
    connection = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    connection.call(
        SERVICE_NAME,
        OBJECT_PATH,
        INTERFACE_NAME,
        method_name,
        GLib.Variant(input_signature, arguments),
        GLib.VariantType.new(output_signature),
        Gio.DBusCallFlags.NONE,
        -1,
        None,
        callback,
    )
