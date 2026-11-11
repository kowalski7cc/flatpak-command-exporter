import logging
import os
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from ..api.models import ExportedAlias as _ExportedAlias
from ..config import AliasConfig as _AliasConfig
from .accessibility import set_accessible_label, set_decorative
from .data import _make_app_icon, get_aliases_by_scope, get_project_details
from .i18n import _
from .menu import create_main_menu
from .settings import show_settings


@dataclass(slots=True)
class _AliasRow:
    record: _ExportedAlias
    scopes: set[str]


@dataclass(slots=True)
class _AppGroup:
    record: _ExportedAlias | None
    records: list[
        tuple[tuple[str, str, str, str, str], _ExportedAlias, set[str]]
    ]
    scopes: set[str]


def _app_commands_enabled(
    config: _AliasConfig, records: Sequence[_ExportedAlias]
) -> bool:
	return all(
		config.is_alias_enabled(record.app_id, record.alias)
		for record in records
	)


def _set_app_commands_enabled(
    config: _AliasConfig,
    records: Sequence[_ExportedAlias],
    enabled: bool,
) -> None:
	if not records:
		return
	config.set_aliases_enabled(
		records[0].app_id,
		list(dict.fromkeys(record.alias for record in records)),
		enabled,
	)


def _configure_ellipsized_label(label, text: str, Pango) -> None:
	label.set_xalign(0)
	label.set_hexpand(True)
	label.set_ellipsize(Pango.EllipsizeMode.END)
	label.set_has_tooltip(True)

	def show_full_text(
		_widget, _x: int, _y: int, _keyboard_tooltip: bool, tooltip
	) -> bool:
		if not label.get_layout().is_ellipsized():
			return False
		tooltip.set_text(text)
		return True

	label.connect("query-tooltip", show_full_text)


def _make_search_controls(Gtk, search_text: str, search_visible: bool):
	search_entry = Gtk.SearchEntry()
	search_entry.set_placeholder_text(_("Search apps and commands"))
	set_accessible_label(
		search_entry, Gtk, _("Search apps and commands")
	)
	search_entry.set_hexpand(True)
	search_entry.set_size_request(-1, 40)
	search_entry.set_text(search_text)

	search_button = Gtk.Button.new_from_icon_name(
		"system-search-symbolic"
	)
	search_button.set_tooltip_text(_("Search apps and commands"))
	set_accessible_label(
		search_button, Gtk, _("Search apps and commands")
	)
	search_button.set_size_request(40, 40)
	search_revealer = Gtk.Revealer()
	search_revealer.set_transition_type(
		Gtk.RevealerTransitionType.SLIDE_DOWN
	)
	search_revealer.set_transition_duration(180)
	search_revealer.set_reveal_child(search_visible)
	search_revealer.set_hexpand(True)
	search_revealer.set_child(search_entry)
	if search_visible:
		search_button.set_state_flags(Gtk.StateFlags.CHECKED, True)

	def toggle_search(_button: object) -> None:
		show_search = not search_revealer.get_reveal_child()
		search_revealer.set_reveal_child(show_search)
		if show_search:
			search_button.set_state_flags(Gtk.StateFlags.CHECKED, True)
			search_entry.grab_focus()
		else:
			search_button.unset_state_flags(Gtk.StateFlags.CHECKED)
			search_button.grab_focus()

	search_button.connect("clicked", toggle_search)
	return search_entry, search_button, search_revealer


def _make_scope_filter_controls(Gtk, selected_scope: int):
	scope_button = Gtk.MenuButton()
	scope_button.set_icon_name("view-reveal-symbolic")
	scope_button.set_size_request(40, 40)
	scope_button.set_tooltip_text(_("Filter by Flatpak installation"))
	set_accessible_label(
		scope_button, Gtk, _("Filter by Flatpak installation")
	)
	scope_choices_box = Gtk.Box(
		orientation=Gtk.Orientation.VERTICAL, spacing=4
	)
	scope_choices_box.set_margin_top(8)
	scope_choices_box.set_margin_bottom(8)
	scope_choices_box.set_margin_start(8)
	scope_choices_box.set_margin_end(8)
	scope_choices = []
	for index, label in enumerate(
		[_("All apps"), _("User apps"), _("System apps")]
	):
		choice = Gtk.CheckButton(label=label)
		if scope_choices:
			choice.set_group(scope_choices[0])
		choice.set_active(index == selected_scope)
		scope_choices_box.append(choice)
		scope_choices.append(choice)
	scope_popover = Gtk.Popover()
	scope_popover.set_child(scope_choices_box)
	scope_button.set_popover(scope_popover)
	return scope_button, scope_choices


def _make_header_controls(
	Gtk,
	search_button,
	scope_button,
	menu_button,
):
	controls = Gtk.Box(
		orientation=Gtk.Orientation.HORIZONTAL, spacing=0
	)
	for control in (search_button, scope_button, menu_button):
		controls.append(control)
	return controls


def _make_list_content(Gtk, search_revealer, stack):
	content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
	search_revealer.set_margin_top(12)
	search_revealer.set_margin_bottom(4)
	search_revealer.set_margin_start(12)
	search_revealer.set_margin_end(12)
	search_revealer.set_hexpand(True)
	content.append(search_revealer)
	content.append(stack)
	return content


def _make_custom_alias_remove_button(record: _ExportedAlias, Gtk):
	if not record.custom or not record.configurable:
		return None

	button = Gtk.Button.new_from_icon_name("edit-delete-symbolic")
	button.set_tooltip_text(_("Remove custom alias"))
	button.set_valign(Gtk.Align.CENTER)
	set_accessible_label(button, Gtk, _("Remove custom alias"))
	return button


def _make_custom_alias_add_button(record: _ExportedAlias, Gtk):
	button = Gtk.Button.new_from_icon_name("list-add-symbolic")
	button.set_tooltip_text(_("Add custom command"))
	button.set_valign(Gtk.Align.CENTER)
	set_accessible_label(
		button,
		Gtk,
		_("Add custom command for %(app)s") % {"app": record.app_name},
	)
	return button


def _show_add_custom_alias_dialog(
	parent,
	record: _ExportedAlias,
	exporter,
	on_saved,
	report_error,
	Adw,
	Gtk,
	GLib,
) -> None:
	dialog = Adw.Dialog()
	dialog.set_title(_("Add custom command"))
	dialog.set_content_width(480)

	toolbar = Adw.ToolbarView()
	header = Adw.HeaderBar()
	header.set_title_widget(
		Adw.WindowTitle(title=_("Add custom command"), subtitle=record.app_name)
	)
	cancel_button = Gtk.Button(label=_("Cancel"))
	cancel_button.connect("clicked", lambda _button: dialog.close())
	header.pack_start(cancel_button)
	add_button = Gtk.Button(label=_("Add"))
	add_button.add_css_class("suggested-action")
	header.pack_end(add_button)
	toolbar.add_top_bar(header)

	form = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
	form.set_margin_top(16)
	form.set_margin_bottom(16)
	form.set_margin_start(16)
	form.set_margin_end(16)
	instructions = Gtk.Label(
		label=_("Enter a command and the alias to export it as.")
	)
	instructions.set_xalign(0)
	instructions.set_wrap(True)
	form.append(instructions)

	command_label = Gtk.Label(label=_("Command"))
	command_label.set_xalign(0)
	form.append(command_label)
	command_entry = Gtk.Entry()
	command_entry.set_placeholder_text(_("e.g. /app/bin/tool"))
	command_entry.set_hexpand(True)
	form.append(command_entry)

	alias_label = Gtk.Label(label=_("External alias"))
	alias_label.set_xalign(0)
	form.append(alias_label)
	alias_entry = Gtk.Entry()
	alias_entry.set_placeholder_text(_("e.g. tool"))
	alias_entry.set_hexpand(True)
	form.append(alias_entry)
	error_label = Gtk.Label(label="")
	error_label.set_xalign(0)
	error_label.set_wrap(True)
	error_label.add_css_class("error")
	error_label.set_visible(False)
	form.append(error_label)

	def update_add_sensitivity(*_args: object) -> None:
		add_button.set_sensitive(
			bool(command_entry.get_text().strip())
			and bool(alias_entry.get_text().strip())
		)

	command_entry.connect("changed", update_add_sensitivity)
	alias_entry.connect("changed", update_add_sensitivity)
	update_add_sensitivity()

	def add_custom_alias(_button: object) -> None:
		command = command_entry.get_text()
		alias = alias_entry.get_text()
		try:
			exporter.add_custom_alias(record.app_id, alias, command)
		except (OSError, ValueError, GLib.Error) as error:
			try:
				saved = (
					exporter.config.custom_aliases(record.app_id).get(alias)
					== command
				)
			except (OSError, ValueError) as config_error:
				error_label.set_text(str(config_error))
				error_label.set_visible(True)
				report_error(_("Could not add custom command"), config_error)
				return
			if not saved:
				error_label.set_text(str(error))
				error_label.set_visible(True)
				report_error(_("Could not add custom command"), error)
				return
			dialog.close()
			on_saved(error)
			return

		dialog.close()
		on_saved(None)

	add_button.connect("clicked", add_custom_alias)
	toolbar.set_content(form)
	dialog.set_child(toolbar)
	dialog.present(parent)


def _confirm_custom_alias_removal(
    parent,
    record: _ExportedAlias,
    exporter,
    on_removed,
    report_error,
    Adw,
    GLib,
) -> None:
	dialog = Adw.AlertDialog(
		heading=_("Remove custom alias?"),
		body=_("This permanently removes the custom alias %(alias)s.") % {
			"alias": record.alias,
		},
	)
	dialog.add_response("cancel", _("Cancel"))
	dialog.add_response("remove", _("Remove"))
	dialog.set_response_appearance(
		"remove", Adw.ResponseAppearance.DESTRUCTIVE
	)
	dialog.set_default_response("cancel")
	dialog.set_close_response("cancel")

	def remove_response(alert_dialog, result: object) -> None:
		try:
			response = alert_dialog.choose_finish(result)
		except GLib.Error as error:
			report_error(_("Could not confirm custom alias removal"), error)
			return
		if response != "remove":
			return

		try:
			exporter.remove_custom_alias(record.app_id, record.alias)
		except (OSError, ValueError, GLib.Error) as error:
			on_removed(error)
			return
		on_removed(None)

	dialog.choose(parent, None, remove_response)


def _group_app_aliases(
    aliases_by_scope: Mapping[str, Sequence[_ExportedAlias]],
) -> dict[str, _AppGroup]:
	rows_by_ref = {}
	for filter_scope, scope_records in aliases_by_scope.items():
		for record in scope_records:
			key = (
				record.installation_scope,
				record.app_id,
				record.arch,
				record.branch,
				record.alias,
			)
			row = rows_by_ref.setdefault(
				key, _AliasRow(record=record, scopes=set())
			)
			row.scopes.add(filter_scope)

	app_groups = {}
	for key, row in sorted(
		rows_by_ref.items(),
		key=lambda item: (
			item[1].record.app_name.casefold(),
			item[1].record.app_id.casefold(),
			item[1].record.branch.casefold(),
			item[1].record.arch.casefold(),
			item[1].record.alias.casefold(),
			item[1].record.installation_scope,
		),
	):
		record = row.record
		group = app_groups.setdefault(
			record.app_id,
			_AppGroup(record=None, records=[], scopes=set()),
		)
		group.records.append((key, record, row.scopes))
		group.scopes.update(row.scopes)
		if "all" in row.scopes:
			group.record = record

	return app_groups


def main() -> None:
	logging.basicConfig(
		level=os.environ.get("LOGLEVEL", "INFO").upper(),
		format="%(levelname)s: %(message)s",
	)
	try:
		import gi

		gi.require_version("Gtk", "4.0")
		gi.require_version("Adw", "1")
		from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango # pyright: ignore[reportAttributeAccessIssue]
	except (ImportError, ValueError) as error:
		raise SystemExit(
			_("The GUI requires PyGObject, GTK 4, and libadwaita with introspection data installed.")
		) from error

	from ..api import FlatpakCommandExporter
	exporter = FlatpakCommandExporter()

	Adw.init()

	class AliasApplication(Adw.Application):
		def __init__(self) -> None:
			super().__init__(
				application_id="xyz.kowalski7cc.flatpak-command-exporter",
				flags=Gio.ApplicationFlags.FLAGS_NONE,
			)
			about_action = Gio.SimpleAction.new("about", None)
			about_action.connect("activate", self.show_about)
			self.add_action(about_action)
			self.connect("activate", self.on_activate)

		def show_about(self, *_args: object) -> None:
			version, authors = get_project_details()
			about_window = Adw.AboutWindow(
				application_name="Flatlink",
				application_icon="xyz.kowalski7cc.flatpak-command-exporter",
				version=version,
				developer_name=authors[0] if authors else "",
				developers=list(authors),
				license_type=Gtk.License.MIT_X11,
			)
			about_window.set_transient_for(self.window)
			about_window.present()

		def on_activate(self, _application: object) -> None:
			aliases_by_scope = get_aliases_by_scope(exporter)
			app_groups = _group_app_aliases(aliases_by_scope)
			window = getattr(self, "window", None)
			search_text = (
				self.search_entry.get_text()
				if hasattr(self, "search_entry")
				else ""
			)
			selected_scope = (
				self.selected_scope
				if hasattr(self, "selected_scope")
				else 0
			)
			search_visible = (
				self.search_revealer.get_reveal_child()
				if hasattr(self, "search_revealer")
				else False
			)

			display = Gdk.Display.get_default()
			icon_theme = Gtk.IconTheme.get_for_display(display)
			icon_theme.add_search_path(os.path.join(sys.prefix, "share", "icons"))

			if window is None:
				window = Adw.ApplicationWindow(
					application=self, title="Flatlink"
				)
			window.set_default_size(720, 640)
			window.set_icon_name("xyz.kowalski7cc.flatpak-command-exporter")
			self.window = window

			toolbar = Adw.ToolbarView()
			header = Adw.HeaderBar()
			header.set_title_widget(Adw.WindowTitle(title=_("Exported Commands"), subtitle=None))
			export_button = Gtk.Button.new_with_label(_("Export"))
			export_button.add_css_class("suggested-action")
			export_button.set_tooltip_text(_("Export all user commands"))
			set_accessible_label(
				export_button, Gtk, _("Export all user commands")
			)

			menu_model = create_main_menu(Gio)
			menu_button = Gtk.MenuButton()
			menu_button.set_icon_name("open-menu-symbolic")
			menu_button.set_menu_model(menu_model)
			menu_button.set_tooltip_text(_("Main Menu"))
			set_accessible_label(menu_button, Gtk, _("Main Menu"))
			header.pack_start(export_button)
			search_entry, search_button, search_revealer = (
				_make_search_controls(Gtk, search_text, search_visible)
			)
			self.search_entry = search_entry
			self.search_revealer = search_revealer

			scope_button, scope_choices = _make_scope_filter_controls(
				Gtk, selected_scope
			)
			header.pack_end(
				_make_header_controls(
					Gtk,
					search_button,
					scope_button,
					menu_button,
				)
			)
			self.selected_scope = selected_scope
			toolbar.add_top_bar(header)

			list_box = Gtk.ListBox()
			list_box.set_selection_mode(Gtk.SelectionMode.NONE)
			list_box.add_css_class("boxed-list")
			list_box.set_margin_top(12)
			list_box.set_margin_bottom(12)
			list_box.set_margin_start(12)
			list_box.set_margin_end(12)

			rows = []
			alias_switches = []
			alias_switch_handlers = {}
			alias_saved_states = {}
			app_switches = []
			app_switch_handlers = {}
			app_saved_states = {}
			app_commands = {}
			for app_id, group in app_groups.items():
				for _key, record, _scopes in group.records:
					app_commands.setdefault(app_id, {})[record.alias] = record

			for group in app_groups.values():
				record = group.record or group.records[0][1]
				command_records = [
					command_record
					for _key, command_record, _scopes in group.records
				]
				row = Gtk.ListBoxRow()
				row.set_selectable(False)
				row.set_activatable(False)
				expander = Gtk.Expander()
				expander.set_expanded(False)
				set_accessible_label(
					expander,
					Gtk,
					_("Show commands for %(app)s") % {"app": record.app_name},
				)

				app_icon = _make_app_icon(record, Gtk, Gdk, GLib, icon_theme)
				set_decorative(app_icon, Gtk)
				app_icon.set_pixel_size(48)

				labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
				labels.set_valign(Gtk.Align.CENTER)
				labels.set_hexpand(True)
				title = Gtk.Label(label=record.app_name)
				_configure_ellipsized_label(title, record.app_name, Pango)
				title.add_css_class("heading")
				subtitle = Gtk.Label(label=record.app_id)
				_configure_ellipsized_label(subtitle, record.app_id, Pango)
				subtitle.add_css_class("dim-label")
				labels.append(title)
				labels.append(subtitle)
				header = Gtk.Box(
					orientation=Gtk.Orientation.HORIZONTAL, spacing=12
				)
				header.set_margin_top(8)
				header.set_margin_bottom(8)
				header.set_margin_start(8)
				header.set_margin_end(8)
				header.append(app_icon)
				header.append(labels)

				app_setting = _app_commands_enabled(
					exporter.config,
					list(app_commands[record.app_id].values()),
				)
				app_switch = Gtk.Switch()
				app_switch.set_active(app_setting)
				app_switch.set_valign(Gtk.Align.CENTER)
				app_switch.set_tooltip_text(
					_("Enable or disable every exported command in this app")
				)
				set_accessible_label(
					app_switch,
					Gtk,
					_("Export commands for %(app)s") % {"app": record.app_name},
				)
				add_custom_alias_button = _make_custom_alias_add_button(
					record, Gtk
				)
				header.append(add_custom_alias_button)
				header.append(app_switch)
				app_switches.append((
					app_switch,
					list(app_commands[record.app_id].values()),
					record,
				))

				def open_add_custom_alias_dialog(
					_button: object,
					record: _ExportedAlias = record,
				) -> None:
					_show_add_custom_alias_dialog(
						window,
						record,
						exporter,
						lambda error: refresh_main_window(
							error,
							_("Custom command saved, but export failed"),
						),
						report_error,
						Adw,
						Gtk,
						GLib,
					)

				add_custom_alias_button.connect(
					"clicked", open_add_custom_alias_dialog
				)
				expander.set_label_widget(header)

				command_list = Gtk.Box(
					orientation=Gtk.Orientation.VERTICAL, spacing=0
				)
				command_list.set_margin_start(64)
				row._command_rows = []
				for _key, command_record, command_scopes in group.records:
					command_row = Gtk.Box(
						orientation=Gtk.Orientation.HORIZONTAL, spacing=12
					)
					command_row.set_margin_top(6)
					command_row.set_margin_bottom(6)
					command_row.set_margin_start(8)
					command_row.set_margin_end(8)

					command_labels = Gtk.Box(
						orientation=Gtk.Orientation.VERTICAL, spacing=4
					)
					command_labels.set_valign(Gtk.Align.CENTER)
					command_labels.set_hexpand(True)
					alias_label = Gtk.Label(label=command_record.alias)
					alias_label.set_xalign(0)
					alias_label.add_css_class("heading")
					command_label = Gtk.Label(label=command_record.command)
					command_label.set_xalign(0)
					command_label.set_wrap(True)
					command_label.set_selectable(True)
					command_label.add_css_class("dim-label")
					command_labels.append(alias_label)
					command_labels.append(command_label)
					command_row.append(command_labels)

					remove_button = _make_custom_alias_remove_button(
						command_record, Gtk
					)
					if remove_button is not None:
						command_row.append(remove_button)

						def confirm_custom_alias_removal(
							_button: object,
							record: _ExportedAlias = command_record,
						) -> None:
							_confirm_custom_alias_removal(
								window,
								record,
								exporter,
								refresh_main_window,
								report_error,
								Adw,
								GLib,
							)

						remove_button.connect(
							"clicked",
							confirm_custom_alias_removal,
						)

					alias_switch = Gtk.Switch()
					alias_switch.set_active(
						exporter.config.is_alias_enabled(
							command_record.app_id, command_record.alias
						)
					)
					alias_switch.set_valign(Gtk.Align.CENTER)
					alias_switch.set_sensitive(True)
					set_accessible_label(
						alias_switch,
						Gtk,
						_("Export %(alias)s from %(app)s") % {
							"alias": command_record.alias,
							"app": record.app_name,
						},
					)
					command_row.append(alias_switch)
					alias_switches.append((alias_switch, command_record))
					command_list.append(command_row)

					row._command_rows.append((
						command_row,
						" ".join((
							command_record.alias,
							command_record.command,
						)).casefold(),
						command_scopes,
					))

				expander.set_child(command_list)
				row.set_child(expander)

				row._search_metadata = " ".join((
					record.app_name,
					record.app_id,
					record.branch,
					record.arch,
					record.installation_scope,
				)).casefold()
				row._view_scopes = group.scopes
				rows.append(row)
				list_box.append(row)

			scroller = Gtk.ScrolledWindow()
			scroller.set_child(list_box)
			scroller.set_vexpand(True)

			empty_page = Adw.StatusPage(
				icon_name="application-x-executable-symbolic",
				title=_("No exported aliases"),
			)
			stack = Gtk.Stack()
			stack.add_named(scroller, "list")
			stack.add_named(empty_page, "empty")
			content = _make_list_content(Gtk, search_revealer, stack)
			toolbar.set_content(content)

			def update_search(*_args: object) -> None:
				query = search_entry.get_text().strip().casefold()
				selected_scope = ("all", "user", "system")[
					self.selected_scope
				]
				visible_count = 0
				for row in rows:
					scope_visible = selected_scope in row._view_scopes
					metadata_matches = not query or query in row._search_metadata
					command_matches = []
					for (
						command_row,
						command_search_text,
						command_scopes,
					) in row._command_rows:
						command_visible = (
							selected_scope in command_scopes
							and (
								not query
								or metadata_matches
								or query in command_search_text
							)
						)
						command_row.set_visible(command_visible)
						command_matches.append(command_visible)

					group_visible = scope_visible and (
						metadata_matches or any(command_matches)
					)
					row.set_visible(group_visible)
					visible_count += group_visible

				if visible_count:
					stack.set_visible_child_name("list")
				else:
					if query:
						empty_page.set_title(_("No aliases found"))
					else:
						empty_page.set_title({
							"all": _("No exported aliases"),
							"user": _("No user aliases"),
							"system": _("No system aliases"),
						}[selected_scope])
					stack.set_visible_child_name("empty")

			search_entry.connect("search-changed", update_search)
			for index, choice in enumerate(scope_choices):
				def update_scope(
					button: Gtk.CheckButton,
					_scope_index: int = index,
				) -> None:
					if button.get_active():
						self.selected_scope = _scope_index
						update_search()

				choice.connect("toggled", update_scope)

			update_search(search_entry)

			toast_overlay = Adw.ToastOverlay()
			self.toast_overlay = toast_overlay
			toast_overlay.set_child(toolbar)
			window.set_content(toast_overlay)

			def report_error(message: str, error: Exception) -> None:
				logging.error("%s: %s", message, error)
				self.toast_overlay.add_toast(Adw.Toast.new(f"{message}: {error}"))

			def refresh_main_window(
				error: Exception | None = None,
				error_message: str = _("Could not remove custom alias"),
			) -> None:
				self.on_activate(self)
				if error is not None:
					report_error(error_message, error)

			def update_user_control_widgets() -> None:
				for alias_switch, record in alias_switches:
					handler_id = alias_switch_handlers[
						(
							record.installation_scope,
							record.app_id,
							record.arch,
							record.branch,
							record.alias,
						)
					]
					state = exporter.config.is_alias_enabled(
						record.app_id, record.alias
					)
					alias_switch.handler_block(handler_id)
					try:
						alias_switch.set_active(state)
						alias_saved_states[
							(
								record.installation_scope,
								record.app_id,
								record.arch,
								record.branch,
								record.alias,
							)
						][0] = state
					finally:
						alias_switch.handler_unblock(handler_id)
				for app_switch, command_records, switch_record in app_switches:
					handler_id = app_switch_handlers[
						(
							switch_record.installation_scope,
							switch_record.app_id,
							switch_record.branch,
							switch_record.arch,
						)
					]
					app_setting = _app_commands_enabled(
						exporter.config, command_records
					)
					app_switch.handler_block(handler_id)
					try:
						app_switch.set_active(app_setting)
						app_saved_states[
							(
								switch_record.installation_scope,
								switch_record.app_id,
								switch_record.branch,
								switch_record.arch,
							)
						][0] = app_setting
					finally:
						app_switch.handler_unblock(handler_id)

			def refresh_user_controls() -> None:
				try:
					update_user_control_widgets()
				except (OSError, ValueError) as error:
					report_error(_("Could not refresh user settings"), error)

			for alias_switch, record in alias_switches:
				handler_id = [None]
				saved_state = [alias_switch.get_active()]

				def update_alias(
					toggle,
					_property: object,
					record: _ExportedAlias = record,
					handler_id: Sequence[int | None] = handler_id,
					saved_state: list[bool] = saved_state,
				) -> None:
					requested_state = toggle.get_active()
					try:
						exporter.config.set_alias_enabled(
							record.app_id, record.alias, requested_state
						)
					except (OSError, ValueError) as error:
						toggle.handler_block(handler_id[0])
						toggle.set_active(saved_state[0])
						toggle.handler_unblock(handler_id[0])
						report_error(_("Could not save alias setting"), error)
						return

					saved_state[0] = requested_state
					try:
						exporter.export_commands()
					except (OSError, ValueError, GLib.Error) as error:
						report_error(_("Alias setting saved, but export failed"), error)
					refresh_user_controls()

				handler_id[0] = alias_switch.connect(
					"notify::active", update_alias
				)
				alias_switch_handlers[
					(
						record.installation_scope,
						record.app_id,
						record.arch,
						record.branch,
						record.alias,
					)
				] = handler_id[0]
				alias_saved_states[
					(
						record.installation_scope,
						record.app_id,
						record.arch,
						record.branch,
						record.alias,
					)
				] = saved_state

			for app_switch, command_records, switch_record in app_switches:
				handler_id = [None]
				saved_state = [app_switch.get_active()]

				def update_app(
					toggle,
					_property: object,
					command_records: list[_ExportedAlias] = command_records,
					handler_id: Sequence[int | None] = handler_id,
					saved_state: list[bool] = saved_state,
				) -> None:
					requested_state = toggle.get_active()
					try:
						_set_app_commands_enabled(
							exporter.config, command_records, requested_state
						)
					except (OSError, ValueError) as error:
						toggle.handler_block(handler_id[0])
						toggle.set_active(saved_state[0])
						toggle.handler_unblock(handler_id[0])
						report_error(_("Could not save app command settings"), error)
						return

					saved_state[0] = requested_state
					try:
						exporter.export_commands()
					except (OSError, ValueError, GLib.Error) as error:
						report_error(
							_("App command settings saved, but export failed"),
							error,
						)
					refresh_user_controls()

				handler_id[0] = app_switch.connect(
					"notify::active", update_app
				)
				app_switch_handlers[
					(
						switch_record.installation_scope,
						switch_record.app_id,
						switch_record.branch,
						switch_record.arch,
					)
				] = handler_id[0]
				app_saved_states[
					(
						switch_record.installation_scope,
						switch_record.app_id,
						switch_record.branch,
						switch_record.arch,
					)
				] = saved_state

			def open_settings(_action: object, _parameter: object) -> None:
				try:
					show_settings(
						window,
						exporter,
						refresh_user_controls,
						report_error,
						Adw,
						Gtk,
						Gdk,
						Pango,
						Gio,
						GLib,
						icon_theme,
					)
				except (OSError, ValueError, GLib.Error) as error:
					report_error(_("Could not open settings"), error)

			self.remove_action("settings")
			settings_action = Gio.SimpleAction.new("settings", None)
			settings_action.connect("activate", open_settings)
			self.add_action(settings_action)

			def export_user_commands(_button: object) -> None:
				try:
					exporter.export_commands()
				except (OSError, ValueError, GLib.Error) as error:
					report_error(_("Could not export user commands"), error)
				else:
					toast_overlay.add_toast(Adw.Toast.new(_("User commands exported")))

			export_button.connect("clicked", export_user_commands)
			window.present()

	AliasApplication().run(sys.argv)

if __name__ == "__main__":
	main()
