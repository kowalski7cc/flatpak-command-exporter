import argparse
from dataclasses import dataclass

from .defaults import DEFAULT_EXPORT_COMMANDS, COMMAND_TEMPLATE
import gi
gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib
import json
import os
import logging
import xml.etree.ElementTree as ET
logging.basicConfig(level=os.environ.get('LOGLEVEL', 'INFO').upper(), format="%(levelname)s: %(message)s")

"""
x-export-commands:
  - putty: putty
  - puttygen: puttygen
  - psftp: psftp
  - pageant: pageant
  - pscp: pscp

"""
EXPORT_SCHEMA_NAMES = [
    "x-export-commands",
    "export-commands"
]


@dataclass(frozen=True)
class ExportedAlias:
    alias: str
    command: str
    app_id: str
    app_name: str
    arch: str
    branch: str
    installation_path: str
    desktop_id: str


def find_user_packages():
    ...


def find_system_packages():
    ...

def load_metainfo(base_path, app_id, arch, branch):
    metainfo_path = os.path.join(
        base_path, "app", app_id, arch, branch, "active", "files", "share", "metainfo", f"{app_id}.metainfo.xml"
    )
    if not os.path.exists(metainfo_path):
        logging.warning(f"Metainfo file not found for {app_id} at {metainfo_path}.")
        return None
    try:
        tree = ET.parse(metainfo_path)
        return tree.getroot()
    except ET.ParseError as e:
        logging.error(f"Error parsing metainfo for {app_id}: {e}")
        return None

def _find_metainfo_child(metainfo, tag):
    return next(
        (child for child in metainfo if child.tag.rsplit("}", 1)[-1] == tag),
        None,
    )


def get_pretty_name_from_metainfo(metainfo):
    if metainfo is None:
        return None
    name_element = _find_metainfo_child(metainfo, "name")
    if name_element is not None and name_element.text:
        return name_element.text.strip()
    return None


def get_desktop_id_from_metainfo(metainfo, app_id):
    if metainfo is None:
        return f"{app_id}.desktop"
    launchable = _find_metainfo_child(metainfo, "launchable")
    if launchable is not None and launchable.get("type") == "desktop-id" and launchable.text:
        return launchable.text.strip()
    return f"{app_id}.desktop"


def get_version_from_metainfo(metainfo):
    if metainfo is None:
        return None
    releases_element = _find_metainfo_child(metainfo, "releases")
    if releases_element is not None:
        release_element = _find_metainfo_child(releases_element, "release")
        if release_element is not None and release_element.get("version"):
            return release_element.get("version").strip()

    version_element = _find_metainfo_child(metainfo, "version")
    if version_element is not None and version_element.text:
        return version_element.text.strip()
    return None

def load_manifest(base_path, app_id, arch, branch):
    manifest_path = os.path.join(
        base_path, "app", app_id, arch, branch, "active", "files", "manifest.json"
    )
    with open(manifest_path, "r") as f:
        return json.load(f)


def find_refs(installation):
    """
    Find all refs of flatpak such as /var/lib/flatpak and /usr/local/share/flatpak.
    """
    try:
        if installation is None:
            return
        yield from installation.list_installed_refs_by_kind(Flatpak.RefKind.APP, None)
    except GLib.Error as e:
        logging.error(f"Error accessing Flatpak API: {e}")
        yield from []


def find_user_refs():
    """
    Find all user refs of flatpak such as /var/lib/flatpak and /usr/local/share/flatpak.
    """
    yield from find_refs(Flatpak.Installation.new_user())


def find_system_refs():
    """
    Find all system refs of flatpak such as /var/lib/flatpak and /usr/local/share/flatpak.
    """
    yield from find_refs(Flatpak.Installation.new_system())


def get_current_ref(installation, app_id, fallback_ref):
    try:
        ref = installation.get_current_installed_app(app_id, None)
    except GLib.Error as error:
        logging.warning(
            "Could not find current ref for %s: %s; using last enumerated ref.",
            app_id,
            error,
        )
        return fallback_ref

    if ref is None:
        logging.warning(
            "No current ref found for %s; using last enumerated ref.",
            app_id,
        )
        return fallback_ref
    return ref


def create_launcher(app_id, export, command, arch, branch):
    # Store launcher in XDG_DATA_HOME/flatpak-commands/{export} or $HOME/.local/share/flatpak-commands/{export}
    base_path = os.path.join(os.environ.get("XDG_DATA_HOME", os.path.join(os.path.expanduser("~"), ".local", "share")), "flatpak-commands")
    if not os.path.exists(base_path):
        os.makedirs(base_path)
    logging.debug(f"Creating launcher for {app_id} at {os.path.join(base_path, export)} with command: {command} and arch: {arch}, branch: {branch}")
    with open(os.path.join(base_path, export), "w") as f:
        f.write(COMMAND_TEMPLATE.format(
            BRANCH=branch,
            ARCH=arch,
            COMMAND=command,
            APP_ID=app_id
        ))
    os.chmod(os.path.join(base_path, export), 0o755)


def manifest_exported_commands(app_id, manifest: dict) -> dict[str, str]:
    commands: dict[str, str] = {}
    for schema_name in EXPORT_SCHEMA_NAMES:
        c = manifest.get(schema_name, {})
        if not isinstance(c, dict):
            logging.warning(f"{schema_name} in manifest for {app_id} is not a dictionary. Ignoring.")
            continue
        commands.update(c)
    if not commands:
        # Fetch commands from defaults
        return DEFAULT_EXPORT_COMMANDS.get(app_id, {})
    return commands


def get_exported_aliases() -> list[ExportedAlias]:
    """Return aliases from current user and system app refs, preferring user refs."""
    aliases: list[ExportedAlias] = []
    seen_app_ids: set[str] = set()

    installation_factories = (
        Flatpak.Installation.new_user,
        Flatpak.Installation.new_system,
    )
    for installation_factory in installation_factories:
        try:
            installation = installation_factory()
            if installation is None:
                continue
            installation_path = installation.get_path().get_path()
        except GLib.Error as error:
            logging.warning("Could not access a Flatpak installation: %s", error)
            continue

        refs_by_app_id = {}
        for ref in find_refs(installation):
            refs_by_app_id[ref.get_name()] = ref

        for app_id, fallback_ref in refs_by_app_id.items():
            if app_id in seen_app_ids:
                continue
            seen_app_ids.add(app_id)
            ref = get_current_ref(installation, app_id, fallback_ref)
            arch = ref.get_arch()
            branch = ref.get_branch()

            try:
                manifest = load_manifest(installation_path, app_id, arch, branch)
            except FileNotFoundError:
                manifest = {}
            except (OSError, json.JSONDecodeError) as error:
                logging.warning("Could not load manifest for %s: %s", app_id, error)
                continue

            if not isinstance(manifest, dict):
                logging.warning("Manifest for %s is not a dictionary. Ignoring.", app_id)
                continue

            metainfo = load_metainfo(installation_path, app_id, arch, branch)
            app_name = get_pretty_name_from_metainfo(metainfo) or app_id
            desktop_id = get_desktop_id_from_metainfo(metainfo, app_id)
            commands = manifest_exported_commands(app_id, manifest)
            for alias, command in commands.items():
                aliases.append(ExportedAlias(
                    alias=alias,
                    command=command,
                    app_id=app_id,
                    app_name=app_name,
                    arch=arch,
                    branch=branch,
                    installation_path=installation_path,
                    desktop_id=desktop_id,
                ))

    return aliases

def export_commands():
    """
    Export commands for the current ref of each user-installed Flatpak app.
    """
    installation = Flatpak.Installation.new_user()
    if installation is None:
        return
    installation_path = installation.get_path().get_path()
    refs_by_app_id = {}
    for ref in find_refs(installation):
        refs_by_app_id[ref.get_name()] = ref

    for app_id, fallback_ref in refs_by_app_id.items():
        ref = get_current_ref(installation, app_id, fallback_ref)

        manifest = load_manifest(
            installation_path, ref.get_name(), ref.get_arch(), ref.get_branch()
        )
        exported_commands = manifest_exported_commands(ref.get_name(), manifest)
        if exported_commands:
            for export, command in exported_commands.items():
                create_launcher(ref.get_name(), export, command, ref.get_arch(), ref.get_branch())

def list_commands(app_id, complete=False):
    """
    List exported commands for a specific flatpak application.
    """
    for ref in find_user_refs():
        if ref.get_name() == app_id:
            # Get pretty name from manifest if available
            pretty_name = get_pretty_name_from_metainfo(load_metainfo(Flatpak.Installation.new_user().get_path(
            ).get_path(), ref.get_name(), ref.get_arch(), ref.get_branch())) or app_id
            manifest = load_manifest(Flatpak.Installation.new_user().get_path(
            ).get_path(), ref.get_name(), ref.get_arch(), ref.get_branch())
            exported_commands = manifest_exported_commands(ref.get_name(), manifest)
            if exported_commands:
                print(f"Exported commands for {pretty_name} ({app_id}):")
                for export, command in exported_commands.items():
                    if complete:
                        print(f"- {export} -> {command}")
                    else:
                        print(f"- {export}")
            else:
                print(f"No exported commands found for {app_id}.")
            return
    print(f"Flatpak application {app_id} not found.")


def list_all_commands(app_id=None, complete=False):
    """List exported commands for every installed ref, optionally filtered by app ID."""
    found_ref = False

    for installation_factory in (Flatpak.Installation.new_user, Flatpak.Installation.new_system):
        try:
            installation = installation_factory()
            if installation is None:
                continue
            installation_path = installation.get_path().get_path()
        except GLib.Error as error:
            logging.warning("Could not access a Flatpak installation: %s", error)
            continue

        for ref in find_refs(installation):
            ref_app_id = ref.get_name()
            if app_id is not None and ref_app_id != app_id:
                continue
            found_ref = True

            arch = ref.get_arch()
            branch = ref.get_branch()
            metainfo = load_metainfo(installation_path, ref_app_id, arch, branch)
            pretty_name = get_pretty_name_from_metainfo(metainfo) or ref_app_id

            try:
                manifest = load_manifest(installation_path, ref_app_id, arch, branch)
            except FileNotFoundError:
                manifest = {}
            except (OSError, json.JSONDecodeError) as error:
                logging.warning("Could not load manifest for %s: %s", ref_app_id, error)
                continue

            if not isinstance(manifest, dict):
                logging.warning("Manifest for %s is not a dictionary. Ignoring.", ref_app_id)
                continue

            exported_commands = manifest_exported_commands(ref_app_id, manifest)
            print(
                f"Exported commands for {pretty_name} "
                f"({ref_app_id}, {branch}/{arch}, {installation_path}):"
            )
            if exported_commands:
                for export, command in exported_commands.items():
                    if complete:
                        print(f"- {export} -> {command}")
                    else:
                        print(f"- {export}")
            else:
                print(f"No exported commands found for {ref_app_id}.")

    if not found_ref:
        if app_id is None:
            print("No installed Flatpak application refs found.")
        else:
            print(f"Flatpak application {app_id} not found.")


def main():
    parser = argparse.ArgumentParser(description="Export Flatpak commands to the user's PATH.", prog="flatpak-command-exporter")
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    subparsers.add_parser("export", help="Export commands for all user-installed flatpak applications.")

    list_parser = subparsers.add_parser(
        "list",
        help="List exported commands for an application or all installed refs.",
    )
    list_parser.add_argument("app_id", nargs="?")
    list_parser.add_argument("--complete", action="store_true", help="Show complete command information.")
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="List exports for all installed refs (optionally filtered by app_id).",
    )

    add_parser = subparsers.add_parser("add", help="Add a new exported command for a specific flatpak application.")
    add_parser.add_argument("app_id")
    add_parser.add_argument("export")
    add_parser.add_argument("command")

    remove_parser = subparsers.add_parser("remove", help="Remove an exported command for a specific flatpak application.")
    remove_parser.add_argument("app_id")
    remove_parser.add_argument("export")

    for command_name in ("enable", "disable"):
        command_parser = subparsers.add_parser(
            command_name,
            help=f"{command_name.capitalize()} exported commands for a specific flatpak application.",
        )
        command_parser.add_argument("app_id")
        command_parser.add_argument("export", nargs="?")
        command_parser.add_argument("--all", action="store_true")

    profile_parser = subparsers.add_parser(
        "install-profile",
        help="Install the profile.d script to enable exported commands in the user's shell.",
    )
    profile_scope = profile_parser.add_mutually_exclusive_group()
    profile_scope.add_argument("--system", action="store_true")
    profile_scope.add_argument("--user", action="store_true")

    config_parser = subparsers.add_parser("config", help="Configure settings for the exporter.")
    config_parser.add_argument("setting")
    config_parser.add_argument("value")

    subparsers.add_parser("help", help="Show help message.")

    args = parser.parse_args()
    if args.command in (None, "help"):
        parser.print_help()
    elif args.command == "export":
        export_commands()
    elif args.command == "list":
        if args.all:
            list_all_commands(args.app_id, complete=args.complete)
        elif args.app_id is None:
            list_parser.error("app_id is required unless --all is specified")
        else:
            list_commands(args.app_id, complete=args.complete)
    else:
        parser.error(f"the {args.command!r} command is not implemented yet")

if __name__ == "__main__":
    main()