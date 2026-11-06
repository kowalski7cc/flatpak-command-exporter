import logging
import os

from gi.repository import GLib

from .application import FlatpakCommandExporter
from .cli_parser import build_parsers
from .profile import install_profile
from .system_bus import call_system_method


def _configure_logging():
    logging.basicConfig(
        level=os.environ.get("LOGLEVEL", "WARNING").upper(),
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


def _run_system_command(args):
    logging.info("Running system-scope %s operation", args.command)
    logging.debug("Dispatching %s through the system-bus helper", args.command)
    if args.command == "export":
        call_system_method("Export")
    elif args.command == "add":
        call_system_method(
            "AddCustomAlias", args.app_id, args.export, args.alias_command
        )
    elif args.command == "remove":
        call_system_method("RemoveCustomAlias", args.app_id, args.export)
    elif args.command in {"enable", "disable"}:
        if args.all and args.export is not None:
            raise ValueError("--all cannot be combined with an alias")
        enabled = args.command == "enable"
        if args.export is None or args.all:
            call_system_method("SetAppEnabled", args.app_id, enabled)
        else:
            call_system_method(
                "SetAliasEnabled", args.app_id, args.export, enabled
            )
    elif args.command == "config":
        call_system_method("SetDefaultPolicy", args.value)
    elif args.command == "install-profile":
        call_system_method("InstallProfile")
    logging.info("Completed system-scope %s operation", args.command)


def main():
    _configure_logging()
    parser, list_parser = build_parsers()
    args = parser.parse_args()
    if args.command in (None, "help"):
        parser.print_help()
        return
    logging.debug("Parsed CLI command: %s", args.command)
    try:
        system_mutation = args.command in {
            "export",
            "add",
            "remove",
            "enable",
            "disable",
            "config",
            "install-profile",
        } and getattr(args, "system", False)
        if system_mutation:
            _run_system_command(args)
            return

        scope = "system" if getattr(args, "system", False) else "user"
        logging.info("Running %s command for %s scope", args.command, scope)
        logging.debug("Using %s scope for command execution", scope)
        exporter = FlatpakCommandExporter(scope=scope)
        if args.command == "export":
            exporter.export_commands()
        elif args.command == "list":
            if args.all:
                if args.system or args.user:
                    groups = exporter.get_command_groups(
                        args.app_id,
                        include_system=False,
                        scope="system" if args.system else "user",
                    )
                else:
                    groups = exporter.get_command_groups(args.app_id)
                if not groups:
                    if args.app_id is None:
                        print("No installed Flatpak application refs found.")
                    else:
                        print(f"Flatpak application {args.app_id} not found.")
                else:
                    _print_command_groups(groups, args.complete)
                logging.info("Listed %d Flatpak application refs", len(groups))
            elif args.app_id is None:
                list_parser.error("app_id is required unless --all is specified")
            else:
                if args.system or args.user:
                    groups = exporter.get_command_groups(
                        args.app_id,
                        include_system=False,
                        first_only=True,
                        scope="system" if args.system else "user",
                    )
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
            install_profile(scope)
        logging.info("Completed %s command for %s scope", args.command, scope)
    except (OSError, ValueError, GLib.Error) as error:
        logging.error("%s", error)
        raise SystemExit(1) from error
