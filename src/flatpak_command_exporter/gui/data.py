import configparser
from importlib.metadata import metadata as distribution_metadata
import os
import tomllib
from pathlib import Path


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
	except (OSError, configparser.Error):
		return None


def get_project_details(project_file=None):
	project_file = Path(project_file) if project_file else (
		Path(__file__).resolve().parents[3] / "pyproject.toml"
	)
	if project_file.is_file():
		with project_file.open("rb") as project_file_handle:
			project = tomllib.load(project_file_handle)["project"]
		return (
			project["version"],
			tuple(author["name"] for author in project.get("authors", ())),
		)

	project_metadata = distribution_metadata("flatpak-command-exporter")
	return (
		project_metadata["Version"],
		tuple(project_metadata.get_all("Author") or ()),
	)


def get_app_ref_choices(exporter):
	"""Return unique installed app refs and their display labels."""
	refs = {}
	for record in exporter.get_exported_aliases():
		key = (
			record.installation_scope,
			record.app_id,
			record.branch,
			record.arch,
		)
		refs[key] = (
			f"{record.app_name} ({record.app_id}, "
			f"{record.branch}/{record.arch}, "
			f"{record.installation_scope} installation)",
			record,
		)
	return sorted(refs.values(), key=lambda choice: choice[0].casefold())


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
