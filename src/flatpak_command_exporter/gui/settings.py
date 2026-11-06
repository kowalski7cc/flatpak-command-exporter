def show_settings(
	window,
	global_export_settings,
	global_default_scope,
	update_global_button_style,
	report_error,
	Adw,
):
	preferences_window = Adw.PreferencesWindow(
		transient_for=window,
		modal=True,
	)
	preferences_window.set_title("Settings")
	page = Adw.PreferencesPage()
	group = Adw.PreferencesGroup(title="Global export default")
	scope_row = Adw.SwitchRow(
		title="Apply to system installations",
		subtitle=(
			"Also change the system default when toggling the global "
			"export setting. System changes require authorization."
		),
	)
	scope_row.set_active(global_default_scope[0] == "both")
	group.add(scope_row)
	page.add(group)
	preferences_window.add(page)

	handler_id = [None]

	def update_global_default_scope(row, _property):
		requested_scope = "both" if row.get_active() else "user"
		if requested_scope == global_default_scope[0]:
			return
		try:
			global_export_settings.set_global_default_scope(requested_scope)
		except (OSError, ValueError) as error:
			row.handler_block(handler_id[0])
			row.set_active(global_default_scope[0] == "both")
			row.handler_unblock(handler_id[0])
			report_error("Could not save global export scope", error)
			return

		global_default_scope[0] = requested_scope
		update_global_button_style()

	handler_id[0] = scope_row.connect(
		"notify::active", update_global_default_scope
	)
	preferences_window.present()
