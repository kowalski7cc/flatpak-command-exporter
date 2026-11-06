from .accessibility import set_accessible_label, set_decorative
from .data import _make_app_icon, get_app_ref_choices
from .i18n import _


def _make_icon_button(Gtk, icon_name, accessible_label):
	button = Gtk.Button.new_from_icon_name(icon_name)
	button.set_tooltip_text(accessible_label)
	set_accessible_label(button, Gtk, accessible_label)
	button.set_valign(Gtk.Align.CENTER)
	return button


def _configure_responsive_label(label, Pango):
	label.set_xalign(0)
	label.set_hexpand(True)
	label.set_wrap(True)
	label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)


def _make_app_override_row(Adw, app_id, app_name, app_icon, remove_button):
	row = Adw.ActionRow(title=app_name, subtitle=app_id)
	row.add_prefix(app_icon)
	row.add_suffix(remove_button)
	return row


def _reset_factory_preferences(config):
	config.clear_overrides()
	default_policy = "none" if config.scope == "system" else "all"
	config.set_default_policy(default_policy)
	return default_policy


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
	Pango,
	GLib,
	icon_theme,
):
	preferences_window = Adw.PreferencesWindow(
		transient_for=window,
		modal=True,
	)
	preferences_window.set_title(_("Settings"))
	page = Adw.PreferencesPage()

	default_group = Adw.PreferencesGroup(title=_("Default export"))
	default_row = Adw.SwitchRow(
		title=_("Export new commands by default"),
		subtitle=_("Applies to user commands, including commands from system apps."),
	)
	default_row.set_active(exporter.config.default_policy() == "all")
	default_group.add(default_row)
	page.add(default_group)

	reset_row = Adw.ActionRow(
		title=_("Reset to factory defaults"),
		subtitle=_("Restore the default export policy and clear app overrides."),
	)
	reset_button = Gtk.Button(label=_("Reset"))
	reset_button.set_valign(Gtk.Align.CENTER)
	reset_row.add_suffix(reset_button)
	default_group.add(reset_row)

	override_groups = {
		True: Adw.PreferencesGroup(title=_("Enabled app overrides")),
		False: Adw.PreferencesGroup(title=_("Disabled app overrides")),
	}
	override_rows = {True: [], False: []}
	for group in override_groups.values():
		page.add(group)

	def refresh_override_rows():
		choices_by_app_id = {
			record.app_id: record for _label, record in get_app_ref_choices(exporter)
		}
		for enabled, group in override_groups.items():
			for row in override_rows[enabled]:
				group.remove(row)
			override_rows[enabled] = []

		app_overrides = exporter.config.app_overrides()
		for app_id, enabled in sorted(
			app_overrides.items(),
			key=lambda item: (
				choices_by_app_id[item[0]].app_name.casefold()
				if item[0] in choices_by_app_id
				else item[0].casefold(),
				item[0].casefold(),
			),
		):
			record = choices_by_app_id.get(app_id)
			app_name = record.app_name if record else app_id
			app_icon = (
				_make_app_icon(record, Gtk, Gdk, GLib, icon_theme)
				if record
				else Gtk.Image.new_from_icon_name(
					"application-x-executable-symbolic"
				)
			)
			set_decorative(app_icon, Gtk)
			app_icon.set_pixel_size(32)
			reset_button = _make_icon_button(
				Gtk, "list-remove-symbolic", _("Remove app override")
			)
			row = _make_app_override_row(
				Adw, app_id, app_name, app_icon, reset_button
			)
			override_groups[enabled].add(row)
			override_rows[enabled].append(row)

			def reset_override(_button, app_id=app_id):
				save_app_override(app_id, None)

			reset_button.connect("clicked", reset_override)

	def save_app_override(app_id, enabled):
		try:
			exporter.config.set_app_enabled(app_id, enabled)
		except (OSError, ValueError) as error:
			report_error(_("Could not save app override"), error)
			return False

		try:
			exporter.export_commands()
		except (OSError, ValueError, GLib.Error) as error:
			report_error(_("App override saved, but export failed"), error)
		try:
			refresh_override_rows()
		except (OSError, ValueError, GLib.Error) as error:
			report_error(_("App override saved, but settings could not be refreshed"), error)
		refresh_user_controls()
		return True

	def open_ref_selector(enabled):
		try:
			choices = get_app_ref_choices(exporter)
		except (OSError, ValueError, GLib.Error) as error:
			report_error(_("Could not load installed app refs"), error)
			return
		if not choices:
			report_error(
				_("Could not add app override"),
				ValueError(_("No installed Flatpak apps with exported commands were found")),
			)
			return

		dialog = Adw.Dialog()
		dialog.set_title(_("Select an installed app"))
		dialog.set_content_height(480)
		toolbar = Adw.ToolbarView()
		header = Adw.HeaderBar()
		header.set_title_widget(
			Adw.WindowTitle(title=_("Select an installed app"), subtitle=None)
		)
		cancel_button = Gtk.Button(label=_("Cancel"))
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
			set_accessible_label(row, Gtk, label)
			row_content = Gtk.Box(
				orientation=Gtk.Orientation.HORIZONTAL,
				spacing=12,
			)
			row_content.set_hexpand(True)
			row_content.set_margin_top(8)
			row_content.set_margin_bottom(8)
			row_content.set_margin_start(8)
			row_content.set_margin_end(8)
			app_icon = _make_app_icon(record, Gtk, Gdk, GLib, icon_theme)
			set_decorative(app_icon, Gtk)
			app_icon.set_pixel_size(40)
			row_content.append(app_icon)

			labels = Gtk.Box(
				orientation=Gtk.Orientation.VERTICAL,
				spacing=4,
			)
			labels.set_hexpand(True)
			app_name = Gtk.Label(label=record.app_name)
			_configure_responsive_label(app_name, Pango)
			app_name.add_css_class("heading")
			app_id = Gtk.Label(label=record.app_id)
			_configure_responsive_label(app_id, Pango)
			app_id.add_css_class("dim-label")
			labels.append(app_name)
			labels.append(app_id)
			row_content.append(labels)

			selected_mark = Gtk.Image.new_from_icon_name(
				"object-select-symbolic"
			)
			set_accessible_label(selected_mark, Gtk, _("Selected"))
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
			title=_("Choose an app"),
			subtitle=_("Set this override for all refs of an installed app."),
		)
		add_button = _make_icon_button(
			Gtk, "list-add-symbolic", _("Add app override")
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
			report_error(_("Could not save default export setting"), error)
			return

		try:
			exporter.export_commands()
		except (OSError, ValueError, GLib.Error) as error:
			report_error(_("Default setting saved, but export failed"), error)
		refresh_user_controls()

	default_row_handler[0] = default_row.connect(
		"notify::active", update_default_export
	)

	def reset_settings():
		try:
			default_policy = _reset_factory_preferences(exporter.config)
		except (OSError, ValueError) as error:
			report_error(_("Could not reset settings"), error)
			return

		try:
			exporter.export_commands()
		except (OSError, ValueError, GLib.Error) as error:
			report_error(_("Settings reset, but export failed"), error)

		default_row.handler_block(default_row_handler[0])
		default_row.set_active(default_policy == "all")
		default_row.handler_unblock(default_row_handler[0])
		try:
			refresh_override_rows()
		except (OSError, ValueError, GLib.Error) as error:
			report_error(_("Settings reset, but overrides could not be refreshed"), error)
		refresh_user_controls()

	def confirm_reset(_button):
		dialog = Adw.AlertDialog(
			heading=_("Reset settings?"),
			body=(
				_("This restores the default export policy and clears app overrides. "
				"Alias-specific settings and custom aliases are not changed.")
			),
		)
		dialog.add_response("cancel", _("Cancel"))
		dialog.add_response("reset", _("Reset"))
		dialog.set_response_appearance(
			"reset", Adw.ResponseAppearance.DESTRUCTIVE
		)
		dialog.set_default_response("cancel")
		dialog.set_close_response("cancel")

		def reset_response(alert_dialog, result):
			try:
				response = alert_dialog.choose_finish(result)
			except GLib.Error as error:
				report_error(_("Could not confirm settings reset"), error)
				return
			if response == "reset":
				reset_settings()

		dialog.choose(preferences_window, None, reset_response)

	reset_button.connect("clicked", confirm_reset)

	preferences_window.add(page)
	try:
		refresh_override_rows()
	except (OSError, ValueError, GLib.Error) as error:
		report_error(_("Could not load app overrides"), error)
	preferences_window.present()
