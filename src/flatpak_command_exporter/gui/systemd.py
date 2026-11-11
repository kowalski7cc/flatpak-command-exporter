_SERVICE_NAME = "flatpak-command-exporter-user.service"
_MANAGER_NAME = "org.freedesktop.systemd1"
_MANAGER_PATH = "/org/freedesktop/systemd1"
_MANAGER_INTERFACE = "org.freedesktop.systemd1.Manager"
_ENABLED_STATES = {
	"enabled",
	"enabled-runtime",
	"linked",
	"linked-runtime",
}


def _call_manager(Gio, GLib, method: str, signature: str, parameters: tuple):
	connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
	return connection.call_sync(
		_MANAGER_NAME,
		_MANAGER_PATH,
		_MANAGER_INTERFACE,
		method,
		GLib.Variant(signature, parameters),
		None,
		Gio.DBusCallFlags.NONE,
		5000,
		None,
	)


def get_user_service_state(Gio, GLib) -> str:
	reply = _call_manager(
		Gio,
		GLib,
		"GetUnitFileState",
		"(s)",
		(_SERVICE_NAME,),
	)
	return reply.unpack()[0]


def user_service_is_enabled(state: str) -> bool:
	return state in _ENABLED_STATES


def set_user_service_enabled(Gio, GLib, enabled: bool) -> None:
	if enabled:
		_call_manager(
			Gio,
			GLib,
			"UnmaskUnitFiles",
			"(asb)",
			([_SERVICE_NAME], False),
		)
		_call_manager(Gio, GLib, "Reload", "()", ())
		_call_manager(
			Gio,
			GLib,
			"EnableUnitFiles",
			"(asbb)",
			([_SERVICE_NAME], False, False),
		)
		_call_manager(
			Gio,
			GLib,
			"StartUnit",
			"(ss)",
			(_SERVICE_NAME, "replace"),
		)
		return

	_call_manager(
		Gio,
		GLib,
		"MaskUnitFiles",
		"(asbb)",
		([_SERVICE_NAME], False, False),
	)
	_call_manager(Gio, GLib, "Reload", "()", ())
	_call_manager(
		Gio,
		GLib,
		"StopUnit",
		"(ss)",
		(_SERVICE_NAME, "replace"),
	)
