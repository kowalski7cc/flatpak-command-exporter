import argparse
import logging
import os

from gi.repository import GLib

from .application import FlatpakCommandExporter

logging.basicConfig(
    level=os.environ.get("LOGLEVEL", "INFO").upper(),
    format="%(levelname)s: %(message)s",
)


def _print_command_groups(groups, complete):
    for group in groups:
        print(
            f"Exported commands for {group.app_name} "
            f"({group.app_id}, {group.branch}/{group.arch}, {group.installation_path}):"
        )
        if not group.commands:
            print(f"No exported commands found for {group.app_id}.")
            continue
        for alias, command in group.commands.items():
            print(f"- {alias} -> {command}" if complete else f"- {alias}")


def main():
    parser = argparse.ArgumentParser(
        description="Export Flatpak commands to the user's PATH.",
        prog="flatshell",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    subparsers.add_parser(
        "export",
        help="Export commands for all user-installed flatpak applications.",
    )

    list_parser = subparsers.add_parser(
        "list",
        help="List exported commands for an application or all installed refs.",
    )
    list_parser.add_argument("app_id", nargs="?")
    list_parser.add_argument(
        "--complete", action="store_true", help="Show complete command information."
    )
    list_parser.add_argument(
        "--all",
        action="store_true",
        help="List exports for all installed refs (optionally filtered by app ID).",
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Add or replace a custom command alias for a user-installed Flatpak app.",
    )
    add_parser.add_argument("app_id")
    add_parser.add_argument("export")
    add_parser.add_argument("alias_command")
    add_parser.add_argument("--user", action="store_true")

    remove_parser = subparsers.add_parser(
        "remove", help="Disable an alias and remove any matching custom alias."
    )
    remove_parser.add_argument("app_id")
    remove_parser.add_argument("export")
    remove_parser.add_argument("--user", action="store_true")

    for command_name in ("enable", "disable"):
        command_parser = subparsers.add_parser(
            command_name,
            help=f"{command_name.capitalize()} an app or alias for the user installation.",
        )
        command_parser.add_argument("app_id")
        command_parser.add_argument("export", nargs="?")
        command_parser.add_argument(
            "--all",
            action="store_true",
            help="Set the app-level override (same as omitting alias).",
        )
        command_parser.add_argument("--user", action="store_true")

    profile_parser = subparsers.add_parser(
        "install-profile",
        help="Install the profile.d script to enable exported commands in the user's shell.",
    )
    profile_scope = profile_parser.add_mutually_exclusive_group()
    profile_scope.add_argument("--system", action="store_true")
    profile_scope.add_argument("--user", action="store_true")

    config_parser = subparsers.add_parser(
        "config",
        help="Configure global export behavior for the user installation.",
    )
    config_parser.add_argument("setting", choices=("default-export",))
    config_parser.add_argument("value", choices=("all", "none"))
    config_parser.add_argument("--user", action="store_true")

    subparsers.add_parser("help", help="Show help message.")

    args = parser.parse_args()
    if args.command in (None, "help"):
        parser.print_help()
        return
    try:
        exporter = FlatpakCommandExporter()
        if args.command == "export":
            exporter.export_commands()
        elif args.command == "list":
            if args.all:
                groups = exporter.get_command_groups(args.app_id)
                if not groups:
                    if args.app_id is None:
                        print("No installed Flatpak application refs found.")
                    else:
                        print(f"Flatpak application {args.app_id} not found.")
                else:
                    _print_command_groups(groups, args.complete)
            elif args.app_id is None:
                list_parser.error("app_id is required unless --all is specified")
            else:
                groups = exporter.get_command_groups(
                    args.app_id, include_system=False, first_only=True
                )
                if not groups:
                    print(f"Flatpak application {args.app_id} not found.")
                else:
                    group = groups[0]
                    print(f"Exported commands for {group.app_name} ({group.app_id}):")
                    if group.commands:
                        for alias, command in group.commands.items():
                            print(f"- {alias} -> {command}" if args.complete else f"- {alias}")
                    else:
                        print(f"No exported commands found for {args.app_id}.")
        elif args.command in {"enable", "disable"}:
            if args.all and args.export is not None:
                parser.error("--all cannot be combined with an alias")
            enabled = args.command == "enable"
            if args.export is None or args.all:
                exporter.set_app_enabled(args.app_id, enabled)
            else:
                exporter.set_alias_enabled(args.app_id, args.export, enabled)
        elif args.command == "add":
            exporter.add_custom_alias(args.app_id, args.export, args.alias_command)
        elif args.command == "remove":
            exporter.remove_custom_alias(args.app_id, args.export)
        elif args.command == "config":
            exporter.set_default_policy(args.value)
        elif args.command == "install-profile":
            parser.error("install-profile is managed by the Debian package.")
    except (OSError, ValueError, GLib.Error) as error:
        logging.error("%s", error)
        raise SystemExit(1) from error
