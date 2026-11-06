import logging
import os
import sys
from .accessibility import set_accessible_label, set_decorative
from .data import _make_app_icon, get_project_details
from .i18n import _
from .menu import create_main_menu
from .settings import show_settings


def _app_commands_enabled(config, records):
	return all(
		config.is_alias_enabled(record.app_id, record.alias)
		for record in records
	)


def _set_app_commands_enabled(config, records, enabled):
	if not records:
		return
	config.set_aliases_enabled(
		records[0].app_id,
		list(dict.fromkeys(record.alias for record in records)),
		enabled,
	)


def main():
	logging.basicConfig(
		level=os.environ.get("LOGLEVEL", "INFO").upper(),
		format="%(levelname)s: %(message)s",
	)
	try:
		import gi

		gi.require_version("Gtk", "4.0")
		gi.require_version("Adw", "1")
		from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango
	except (ImportError, ValueError) as error:
		raise SystemExit(
			_("The GUI requires PyGObject, GTK 4, and libadwaita with introspection data installed.")
		) from error

	from ..api import FlatpakCommandExporter
	exporter = FlatpakCommandExporter()

	Adw.init()

	class AliasApplication(Adw.Application):
		def __init__(self):
			super().__init__(
				application_id="xyz.kowalski7cc.flatpak-command-exporter",
				flags=Gio.ApplicationFlags.FLAGS_NONE,
			)
			about_action = Gio.SimpleAction.new("about", None)
			about_action.connect("activate", self.show_about)
			self.add_action(about_action)
			self.connect("activate", self.on_activate)

		def show_about(self, *_args):
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

		def on_activate(self, _application):
			all_records = exporter.get_exported_aliases()
			row_records = {}
			row_scopes = {}
			for record in all_records:
				key = (
					record.installation_scope,
					record.app_id,
					record.arch,
					record.branch,
					record.alias,
				)
				row_records[key] = record
				row_scopes.setdefault(key, set()).add("all")
				row_scopes[key].add(record.installation_scope)
			records = sorted(
				row_records.items(),
				key=lambda item: (
					item[1].app_name.casefold(),
					item[1].app_id.casefold(),
					item[1].branch.casefold(),
					item[1].arch.casefold(),
					item[1].alias.casefold(),
					item[1].installation_scope,
				),
			)

			display = Gdk.Display.get_default()
			icon_theme = Gtk.IconTheme.get_for_display(display)
			icon_theme.add_search_path(os.path.join(sys.prefix, "share", "icons"))

			window = Adw.ApplicationWindow(application=self, title="Flatlink")
			window.set_default_size(720, 640)
			#window.set_default_size(1000, 700)
			window.set_icon_name("xyz.kowalski7cc.flatpak-command-exporter")
			self.window = window

			toolbar = Adw.ToolbarView()
			header = Adw.HeaderBar()
			header.set_title_widget(Adw.WindowTitle(title=_("Exported Commands"), subtitle=None))
			export_button = Gtk.Button.new_from_icon_name("view-refresh-symbolic")
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
			header.pack_end(menu_button)
			header.pack_end(export_button)
			search_entry = Gtk.SearchEntry()
			search_entry.set_placeholder_text(_("Search apps and commands"))
			set_accessible_label(
				search_entry, Gtk, _("Search apps and commands")
			)
			search_entry.set_hexpand(True)
			search_entry.set_size_request(-1, 40)
			scope_filter = Gtk.DropDown.new_from_strings(
				[_("All apps"), _("User apps"), _("System apps")]
			)
			scope_filter.set_size_request(-1, 40)
			scope_filter.set_tooltip_text(_("Filter by Flatpak installation"))
			set_accessible_label(
				scope_filter, Gtk, _("Filter by Flatpak installation")
			)
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
			app_groups = {}
			app_commands = {}
			for key, record in records:
				app_commands.setdefault(record.app_id, {})[
					record.alias
				] = record
				group_key = (
					record.app_id,
					record.installation_scope,
					record.branch,
					record.arch,
				)
				if group_key not in app_groups:
					app_groups[group_key] = {
						"record": record,
						"records": [],
						"scopes": set(),
					}
				app_groups[group_key]["records"].append((key, record))
				app_groups[group_key]["scopes"].update(row_scopes[key])

			for group in app_groups.values():
				record = group["record"]
				command_records = [
					command_record for _key, command_record in group["records"]
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
				title.set_xalign(0)
				title.add_css_class("heading")
				scope_name = (
					_("User")
					if record.installation_scope == "user"
					else _("System")
				)
				subtitle_text = _(
					"%(app_id)s - %(branch)s (%(arch)s) - %(scope)s installation"
				) % {
					"app_id": record.app_id,
					"branch": record.branch,
					"arch": record.arch,
					"scope": scope_name,
				}
				subtitle = Gtk.Label(label=subtitle_text)
				subtitle.set_xalign(0)
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
				header.append(app_switch)
				app_switches.append((
					app_switch,
					list(app_commands[record.app_id].values()),
					record,
				))
				expander.set_label_widget(header)

				command_list = Gtk.Box(
					orientation=Gtk.Orientation.VERTICAL, spacing=0
				)
				command_list.set_margin_start(64)
				row._command_rows = []
				for _key, command_record in group["records"]:
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
				row._view_scopes = group["scopes"]
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
			content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
			search_entry.set_margin_top(12)
			search_entry.set_margin_start(12)
			search_entry.set_margin_end(12)
			search_entry.set_margin_bottom(4)
			filter_row = Gtk.Box(
				orientation=Gtk.Orientation.HORIZONTAL, spacing=8
			)
			filter_row.set_margin_start(12)
			filter_row.set_margin_end(12)
			filter_row.set_margin_bottom(4)
			filter_row.append(search_entry)
			filter_row.append(scope_filter)
			content.append(filter_row)
			content.append(stack)
			toolbar.set_content(content)

			def update_search(*_args):
				query = search_entry.get_text().strip().casefold()
				selected_scope = ("all", "user", "system")[
					scope_filter.get_selected()
				]
				visible_count = 0
				for row in rows:
					scope_visible = selected_scope in row._view_scopes
					metadata_matches = not query or query in row._search_metadata
					command_matches = []
					for command_row, command_search_text in row._command_rows:
						command_visible = (
							scope_visible
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
			scope_filter.connect("notify::selected", update_search)
			update_search(search_entry)

			toast_overlay = Adw.ToastOverlay()
			toast_overlay.set_child(toolbar)
			window.set_content(toast_overlay)

			def report_error(message, error):
				logging.error("%s: %s", message, error)
				toast_overlay.add_toast(Adw.Toast.new(f"{message}: {error}"))

			def update_user_control_widgets():
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

			def refresh_user_controls():
				try:
					update_user_control_widgets()
				except (OSError, ValueError) as error:
					report_error(_("Could not refresh user settings"), error)

			for alias_switch, record in alias_switches:
				handler_id = [None]
				saved_state = [alias_switch.get_active()]

				def update_alias(
					toggle,
					_property,
					record=record,
					handler_id=handler_id,
					saved_state=saved_state,
				):
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
					_property,
					command_records=command_records,
					handler_id=handler_id,
					saved_state=saved_state,
				):
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

			def open_settings(_action, _parameter):
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
						GLib,
						icon_theme,
					)
				except (OSError, ValueError, GLib.Error) as error:
					report_error(_("Could not open settings"), error)

			self.remove_action("settings")
			settings_action = Gio.SimpleAction.new("settings", None)
			settings_action.connect("activate", open_settings)
			self.add_action(settings_action)

			def export_user_commands(_button):
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
