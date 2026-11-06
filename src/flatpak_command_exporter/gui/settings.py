from .data import _make_app_icon, get_app_ref_choices


def _make_icon_button(Gtk, icon_name, accessible_label):
	button = Gtk.Button.new_from_icon_name(icon_name)
	button.set_tooltip_text(accessible_label)
	button.update_property(
		[Gtk.AccessibleProperty.LABEL], [accessible_label]
	)
	button.set_valign(Gtk.Align.CENTER)
	return button


def _handle_app_selection(
	row,
	records_by_row,
	selection_marks,
	enabled,
	save_app_override,
	close_chooser,
):
	if row is None:
		return
	for choice_row, selected_mark in selection_marks.items():
		selected_mark.set_visible(choice_row is row)
	record = records_by_row[row]
	if save_app_override(record.app_id, enabled):
		close_chooser()


def show_settings(
	window,
	exporter,
	refresh_user_controls,
	report_error,
	Adw,
	Gtk,
	Gdk,
	GLib,
	icon_theme,
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
			reset_button = _make_icon_button(
				Gtk, "list-remove-symbolic", "Remove app override"
			)
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
			return False

		try:
			exporter.export_commands()
		except (OSError, ValueError, GLib.Error) as error:
			report_error("App override saved, but export failed", error)
		try:
			refresh_override_rows()
		except (OSError, ValueError) as error:
			report_error("App override saved, but settings could not be refreshed", error)
		refresh_user_controls()
		return True

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

		dialog = Adw.Dialog()
		dialog.set_title("Select an installed app")
		dialog.set_content_width(520)
		dialog.set_content_height(480)
		toolbar = Adw.ToolbarView()
		header = Adw.HeaderBar()
		header.set_title_widget(
			Adw.WindowTitle(title="Select an installed app", subtitle=None)
		)
		cancel_button = Gtk.Button(label="Cancel")
		cancel_button.connect("clicked", lambda _button: dialog.close())
		header.pack_start(cancel_button)
		toolbar.add_top_bar(header)

		list_box = Gtk.ListBox()
		list_box.set_selection_mode(Gtk.SelectionMode.SINGLE)
		list_box.add_css_class("boxed-list")
		list_box.set_margin_top(12)
		list_box.set_margin_bottom(12)
		list_box.set_margin_start(12)
		list_box.set_margin_end(12)

		selection_marks = {}
		records_by_row = {}
		for label, record in choices:
			row = Gtk.ListBoxRow()
			row.set_activatable(True)
			row.update_property(
				[Gtk.AccessibleProperty.LABEL], [label]
			)
			row_content = Gtk.Box(
				orientation=Gtk.Orientation.HORIZONTAL,
				spacing=12,
			)
			row_content.set_margin_top(8)
			row_content.set_margin_bottom(8)
			row_content.set_margin_start(8)
			row_content.set_margin_end(8)
			app_icon = _make_app_icon(record, Gtk, Gdk, GLib, icon_theme)
			app_icon.set_pixel_size(40)
			row_content.append(app_icon)

			labels = Gtk.Box(
				orientation=Gtk.Orientation.VERTICAL,
				spacing=4,
			)
			labels.set_hexpand(True)
			app_name = Gtk.Label(label=record.app_name)
			app_name.set_xalign(0)
			app_name.add_css_class("heading")
			ref_details = Gtk.Label(
				label=(
					f"{record.app_id} | {record.branch}/{record.arch} | "
					f"{record.installation_scope.capitalize()} installation"
				)
			)
			ref_details.set_xalign(0)
			ref_details.add_css_class("dim-label")
			labels.append(app_name)
			labels.append(ref_details)
			row_content.append(labels)

			selected_mark = Gtk.Image.new_from_icon_name(
				"object-select-symbolic"
			)
			selected_mark.set_visible(False)
			row_content.append(selected_mark)
			row.set_child(row_content)
			list_box.append(row)
			selection_marks[row] = selected_mark
			records_by_row[row] = record

		def selected_ref(_list_box, row):
			_handle_app_selection(
				row,
				records_by_row,
				selection_marks,
				enabled,
				save_app_override,
				dialog.close,
			)

		list_box.connect("row-selected", selected_ref)

		scroller = Gtk.ScrolledWindow()
		scroller.set_child(list_box)
		scroller.set_vexpand(True)
		toolbar.set_content(scroller)
		dialog.set_child(toolbar)
		dialog.present(preferences_window)

	for enabled, group in override_groups.items():
		add_row = Adw.ActionRow(
			title="Choose an app",
			subtitle="Set this override for all refs of an installed app.",
		)
		add_button = _make_icon_button(
			Gtk, "list-add-symbolic", "Add app override"
		)
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
