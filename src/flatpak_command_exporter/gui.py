import configparser
import logging
import os
import sys


def find_desktop_file(record, data_dirs=None):
	"""Find the exported desktop entry for a Flatpak alias record."""
	application_dirs = []
	installation_path = getattr(record, "installation_path", None)
	if installation_path:
		application_dirs.append(os.path.join(
			installation_path, "exports", "share", "applications"
		))

	if data_dirs is None:
		data_home = os.environ.get(
			"XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")
		)
		data_dirs = [os.path.join(data_home, "flatpak", "exports", "share")]
		data_dirs.extend(filter(None, os.environ.get(
			"XDG_DATA_DIRS", "/usr/local/share:/usr/share"
		).split(os.pathsep)))
		data_dirs.extend((
			"/var/lib/flatpak/exports/share",
			"/usr/local/share/flatpak/exports/share",
		))

	for data_dir in data_dirs:
		if os.path.basename(data_dir) == "share":
			application_dirs.append(os.path.join(data_dir, "applications"))
		else:
			application_dirs.append(os.path.join(data_dir, "share", "applications"))

	desktop_ids = [getattr(record, "desktop_id", None), f"{record.app_id}.desktop"]
	for desktop_id in dict.fromkeys(filter(None, desktop_ids)):
		for application_dir in dict.fromkeys(application_dirs):
			desktop_file = os.path.join(application_dir, desktop_id)
			if os.path.isfile(desktop_file):
				return desktop_file
	return None


def get_exported_icon(record, data_dirs=None):
	desktop_file = find_desktop_file(record, data_dirs)
	if desktop_file is None:
		return None

	desktop_entry = configparser.ConfigParser(interpolation=None, strict=False)
	try:
		with open(desktop_file, encoding="utf-8") as desktop_file_handle:
			desktop_entry.read_file(desktop_file_handle)
		return desktop_entry.get("Desktop Entry", "Icon", fallback=None)
	except (OSError, configparser.Error) as error:
		return None


def _make_app_icon(record, Gtk, Gdk, GLib, icon_theme):
	icon_name = get_exported_icon(record)
	installation_path = getattr(record, "installation_path", None)
	if installation_path:
		icon_theme.add_search_path(os.path.join(
			installation_path, "exports", "share", "icons"
		))

	if icon_name and os.path.isabs(icon_name) and os.path.isfile(icon_name):
		try:
			texture = Gdk.Texture.new_from_filename(icon_name)
			return Gtk.Image.new_from_paintable(texture)
		except GLib.Error:
			pass

	if icon_name:
		candidate_names = [icon_name]
		if os.path.splitext(icon_name)[1]:
			candidate_names.append(os.path.splitext(icon_name)[0])
		for candidate_name in candidate_names:
			if icon_theme.has_icon(candidate_name):
				paintable = icon_theme.lookup_icon(
					candidate_name,
					None,
					48,
					1,
					Gtk.TextDirection.NONE,
					Gtk.IconLookupFlags.FORCE_REGULAR,
				)
				return Gtk.Image.new_from_paintable(paintable)

	return Gtk.Image.new_from_icon_name("application-x-executable-symbolic")


def main():
	logging.basicConfig(
		level=os.environ.get("LOGLEVEL", "INFO").upper(),
		format="%(levelname)s: %(message)s",
	)
	try:
		import gi

		gi.require_version("Gtk", "4.0")
		gi.require_version("Adw", "1")
		from gi.repository import Adw, Gdk, Gio, GLib, Gtk
	except (ImportError, ValueError) as error:
		raise SystemExit(
			"The GUI requires PyGObject, GTK 4, and libadwaita with introspection data installed."
		) from error

	from . import FlatpakCommandExporter

	exporter = FlatpakCommandExporter()

	Adw.init()

	class AliasApplication(Adw.Application):
		def __init__(self):
			super().__init__(
				application_id="xyz.kowalski7cc.flatpak-command-exporter",
				flags=Gio.ApplicationFlags.FLAGS_NONE,
			)
			self.connect("activate", self.on_activate)

		def on_activate(self, _application):
			records = sorted(
				exporter.get_exported_aliases(),
				key=lambda record: (
					record.app_name.casefold(),
					record.app_id.casefold(),
					record.alias.casefold(),
					record.branch.casefold(),
					record.arch.casefold(),
				),
			)

			display = Gdk.Display.get_default()
			icon_theme = Gtk.IconTheme.get_for_display(display)
			icon_theme.add_search_path(os.path.join(sys.prefix, "share", "icons"))

			window = Adw.ApplicationWindow(application=self, title="Flatlink")
			window.set_default_size(720, 640)
			window.set_icon_name("xyz.kowalski7cc.flatpak-command-exporter")

			toolbar = Adw.ToolbarView()
			header = Adw.HeaderBar()
			header.set_title_widget(Adw.WindowTitle(title="Exported Commands", subtitle=None))
			global_export_switch = Gtk.Switch()
			global_export_switch.set_active(exporter.config.default_policy() == "all")
			global_export_switch.set_valign(Gtk.Align.CENTER)
			global_export_switch.set_tooltip_text("Export all aliases by default")
			global_export_control = Gtk.Box(
				orientation=Gtk.Orientation.HORIZONTAL, spacing=8
			)
			global_export_control.append(Gtk.Label(label="Export by default"))
			global_export_control.append(global_export_switch)
			header.pack_end(global_export_control)
			search_entry = Gtk.SearchEntry()
			search_entry.set_placeholder_text("Search aliases")
			search_entry.set_size_request(220, -1)
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
			for record in records:
				row = Gtk.ListBoxRow()
				row.set_selectable(False)
				row.set_activatable(False)
				row_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
				row_content.set_margin_top(8)
				row_content.set_margin_bottom(8)
				row_content.set_margin_start(8)
				row_content.set_margin_end(8)

				app_icon = _make_app_icon(record, Gtk, Gdk, GLib, icon_theme)
				app_icon.set_pixel_size(48)
				row_content.append(app_icon)

				labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
				labels.set_valign(Gtk.Align.CENTER)
				labels.set_hexpand(True)
				title = Gtk.Label(label=f"{record.app_name} - {record.alias}")
				title.set_xalign(0)
				title.add_css_class("heading")
				subtitle_text = f"{record.app_id} - {record.branch} ({record.arch})"
				subtitle = Gtk.Label(label=subtitle_text)
				subtitle.set_xalign(0)
				subtitle.add_css_class("dim-label")
				labels.append(title)
				labels.append(subtitle)
				row_content.append(labels)

				alias_switch = Gtk.Switch()
				alias_switch.set_active(record.enabled)
				alias_switch.set_valign(Gtk.Align.CENTER)
				alias_switch.set_sensitive(record.configurable)
				row_content.append(alias_switch)
				alias_switches.append((alias_switch, record))
				row.set_child(row_content)

				row._search_text = " ".join((
					record.app_name,
					record.app_id,
					record.alias,
					record.branch,
					record.arch,
				)).casefold()
				rows.append(row)
				list_box.append(row)

			scroller = Gtk.ScrolledWindow()
			scroller.set_child(list_box)
			scroller.set_vexpand(True)

			empty_page = Adw.StatusPage(
				icon_name="application-x-executable-symbolic",
				title="No exported aliases",
			)
			stack = Gtk.Stack()
			stack.add_named(scroller, "list")
			stack.add_named(empty_page, "empty")
			content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
			search_entry.set_margin_top(12)
			search_entry.set_margin_start(12)
			search_entry.set_margin_end(12)
			search_entry.set_margin_bottom(4)
			content.append(search_entry)
			content.append(stack)
			toolbar.set_content(content)

			def update_search(entry):
				query = entry.get_text().strip().casefold()
				visible_count = 0
				for row in rows:
					visible = not query or query in row._search_text
					row.set_visible(visible)
					visible_count += visible

				if visible_count:
					stack.set_visible_child_name("list")
				else:
					empty_page.set_title("No aliases found" if query else "No exported aliases")
					stack.set_visible_child_name("empty")

			search_entry.connect("search-changed", update_search)
			update_search(search_entry)

			toast_overlay = Adw.ToastOverlay()
			toast_overlay.set_child(toolbar)
			window.set_content(toast_overlay)

			def report_error(message, error):
				logging.error("%s: %s", message, error)
				toast_overlay.add_toast(Adw.Toast.new(f"{message}: {error}"))

			for alias_switch, record in alias_switches:
				handler_id = [None]
				saved_state = [record.enabled]

				def update_alias(
					toggle,
					_property,
					record=record,
					handler_id=handler_id,
					saved_state=saved_state,
				):
					try:
						exporter.config.set_alias_enabled(
							record.app_id, record.alias, toggle.get_active()
						)
					except (OSError, ValueError) as error:
						toggle.handler_block(handler_id[0])
						toggle.set_active(saved_state[0])
						toggle.handler_unblock(handler_id[0])
						report_error("Could not save alias setting", error)
						return

					saved_state[0] = toggle.get_active()
					try:
						exporter.export_commands()
					except (OSError, ValueError, GLib.Error) as error:
						report_error("Alias setting saved, but export failed", error)

				handler_id[0] = alias_switch.connect(
					"notify::active", update_alias
				)

			global_switch_state = [global_export_switch.get_active()]
			global_switch_handler = [None]

			def update_global_export(toggle, _property):
				new_state = toggle.get_active()
				try:
					exporter.config.set_default_policy(
						"all" if new_state else "none"
					)
				except (OSError, ValueError) as error:
					toggle.handler_block(global_switch_handler[0])
					toggle.set_active(global_switch_state[0])
					toggle.handler_unblock(global_switch_handler[0])
					report_error("Could not save global export setting", error)
					return

				global_switch_state[0] = new_state
				try:
					exporter.export_commands()
				except (OSError, ValueError, GLib.Error) as error:
					report_error("Global setting saved, but export failed", error)

			global_switch_handler[0] = global_export_switch.connect(
				"notify::active", update_global_export
			)
			window.present()

	AliasApplication().run(sys.argv)
