from .data import get_app_ref_choices


def show_settings(
	window,
	exporter,
	refresh_user_controls,
	report_error,
	Adw,
	Gtk,
	GLib,
):
	preferences_window = Adw.PreferencesWindow(
		transient_for=window,
		modal=True,
	)
	preferences_window.set_title("Settings")
	page = Adw.PreferencesPage()

	default_group = Adw.PreferencesGroup(title="Default export")
	default_row = Adw.SwitchRow(
		title="Export new commands by default",
		subtitle="Applies to user commands, including commands from system apps.",
	)
	default_row.set_active(exporter.config.default_policy() == "all")
	default_group.add(default_row)
	page.add(default_group)

	override_groups = {
		True: Adw.PreferencesGroup(title="Enabled app overrides"),
		False: Adw.PreferencesGroup(title="Disabled app overrides"),
	}
	override_rows = {True: [], False: []}
	for group in override_groups.values():
		page.add(group)

	def refresh_override_rows():
		for enabled, group in override_groups.items():
			for row in override_rows[enabled]:
				group.remove(row)
			override_rows[enabled] = []

		for app_id, enabled in sorted(exporter.config.app_overrides().items()):
			row = Adw.ActionRow(
				title=app_id,
				subtitle="Override the global default for this app",
			)
			reset_button = Gtk.Button(label="Reset")
			reset_button.set_valign(Gtk.Align.CENTER)
			row.add_suffix(reset_button)
			override_groups[enabled].add(row)
			override_rows[enabled].append(row)

			def reset_override(_button, app_id=app_id):
				save_app_override(app_id, None)

			reset_button.connect("clicked", reset_override)

	def save_app_override(app_id, enabled):
		try:
			exporter.config.set_app_enabled(app_id, enabled)
		except (OSError, ValueError) as error:
			report_error("Could not save app override", error)
			return

		try:
			exporter.export_commands()
		except (OSError, ValueError, GLib.Error) as error:
			report_error("App override saved, but export failed", error)
		try:
			refresh_override_rows()
		except (OSError, ValueError) as error:
			report_error("App override saved, but settings could not be refreshed", error)
		refresh_user_controls()

	def open_ref_selector(enabled):
		try:
			choices = get_app_ref_choices(exporter)
		except (OSError, ValueError, GLib.Error) as error:
			report_error("Could not load installed app refs", error)
			return
		if not choices:
			report_error(
				"Could not add app override",
				ValueError("No installed Flatpak apps with exported commands were found"),
			)
			return

		dialog = Gtk.Dialog(
			title="Select an installed app",
			transient_for=preferences_window,
			modal=True,
		)
		dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
		dialog.add_button("Add", Gtk.ResponseType.ACCEPT)
		dialog.set_default_response(Gtk.ResponseType.ACCEPT)
		content = dialog.get_content_area()
		content.set_spacing(12)
		content.set_margin_top(18)
		content.set_margin_bottom(18)
		content.set_margin_start(18)
		content.set_margin_end(18)
		content.append(Gtk.Label(label="Choose an installed Flatpak app ref:"))
		selector = Gtk.DropDown.new_from_strings(
			[label for label, _app_id in choices]
		)
		content.append(selector)

		def selected_ref(_dialog, response):
			if response == Gtk.ResponseType.ACCEPT:
				_index = selector.get_selected()
				if _index < len(choices):
					save_app_override(choices[_index][1], enabled)
			dialog.close()

		dialog.connect("response", selected_ref)
		dialog.present()

	for enabled, group in override_groups.items():
		add_row = Adw.ActionRow(
			title="Add an app override",
			subtitle=(
				"Choose an installed app ref; the override applies to all refs "
				"of that app."
			),
		)
		add_button = Gtk.Button(label="Add")
		add_button.set_valign(Gtk.Align.CENTER)
		add_row.add_suffix(add_button)
		group.add(add_row)
		add_button.connect(
			"clicked",
			lambda _button, enabled=enabled: open_ref_selector(enabled),
		)

	default_row_handler = [None]

	def update_default_export(row, _property):
		policy = "all" if row.get_active() else "none"
		try:
			exporter.config.set_default_policy(policy)
		except (OSError, ValueError) as error:
			row.handler_block(default_row_handler[0])
			row.set_active(not row.get_active())
			row.handler_unblock(default_row_handler[0])
			report_error("Could not save default export setting", error)
			return

		try:
			exporter.export_commands()
		except (OSError, ValueError, GLib.Error) as error:
			report_error("Default setting saved, but export failed", error)
		refresh_user_controls()

	default_row_handler[0] = default_row.connect(
		"notify::active", update_default_export
	)
	preferences_window.add(page)
	try:
		refresh_override_rows()
	except (OSError, ValueError) as error:
		report_error("Could not load app overrides", error)
	preferences_window.present()
