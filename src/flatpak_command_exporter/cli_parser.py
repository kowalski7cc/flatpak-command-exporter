import argparse


def build_parsers() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        description=(
            "Export Flatpak commands to PATH-accessible directories. "
            "Changes use the system installation by default; use --user "
            "for per-user changes."
        ),
        prog="flatshell",
    )
    subparsers = parser.add_subparsers(dest="command", help="Subcommands")
    export_parser = subparsers.add_parser(
        "export",
        help="Export commands for the selected Flatpak installation.",
    )
    export_scope = export_parser.add_mutually_exclusive_group()
    export_scope.add_argument(
        "--system",
        action="store_true",
        help="Use the system installation (default; requires elevated permissions).",
    )
    export_scope.add_argument(
        "--user",
        action="store_true",
        help="Use the per-user installation.",
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
    list_scope = list_parser.add_mutually_exclusive_group()
    list_scope.add_argument(
        "--system",
        action="store_true",
        help="List system refs only (default is merged user and system refs).",
    )
    list_scope.add_argument(
        "--user",
        action="store_true",
        help="List user refs only (default is merged user and system refs).",
    )

    add_parser = subparsers.add_parser(
        "add",
        help="Add or replace a custom alias for an app in the selected installation.",
    )
    add_parser.add_argument("app_id")
    add_parser.add_argument("export")
    add_parser.add_argument("alias_command")
    add_scope = add_parser.add_mutually_exclusive_group()
    add_scope.add_argument(
        "--system",
        action="store_true",
        help="Use the system installation (default; requires elevated permissions).",
    )
    add_scope.add_argument(
        "--user",
        action="store_true",
        help="Use the per-user installation.",
    )

    remove_parser = subparsers.add_parser(
        "remove", help="Disable an alias and remove any matching custom alias."
    )
    remove_parser.add_argument("app_id")
    remove_parser.add_argument("export")
    remove_scope = remove_parser.add_mutually_exclusive_group()
    remove_scope.add_argument(
        "--system",
        action="store_true",
        help="Use the system installation (default; requires elevated permissions).",
    )
    remove_scope.add_argument(
        "--user",
        action="store_true",
        help="Use the per-user installation.",
    )

    for command_name in ("enable", "disable"):
        command_parser = subparsers.add_parser(
            command_name,
            help=f"{command_name.capitalize()} an app or alias in the selected installation.",
        )
        command_parser.add_argument("app_id")
        command_parser.add_argument("export", nargs="?")
        command_parser.add_argument(
            "--all",
            action="store_true",
            help="Set the app-level override (same as omitting alias).",
        )
        command_scope = command_parser.add_mutually_exclusive_group()
        command_scope.add_argument(
            "--system",
            action="store_true",
            help="Use the system installation (default; requires elevated permissions).",
        )
        command_scope.add_argument(
            "--user",
            action="store_true",
            help="Use the per-user installation.",
        )

    profile_parser = subparsers.add_parser(
        "install-profile",
        help="Install shell integration for exported commands.",
    )
    profile_scope = profile_parser.add_mutually_exclusive_group()
    profile_scope.add_argument(
        "--system",
        action="store_true",
        help="Install system shell integration (default; requires root).",
    )
    profile_scope.add_argument(
        "--user",
        action="store_true",
        help="Install shell integration for the current user.",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="Configure global export behavior for the selected installation.",
    )
    config_parser.add_argument("setting", choices=("default-export",))
    config_parser.add_argument("value", choices=("all", "none"))
    config_scope = config_parser.add_mutually_exclusive_group()
    config_scope.add_argument(
        "--system",
        action="store_true",
        help="Use the system installation (default; requires elevated permissions).",
    )
    config_scope.add_argument(
        "--user",
        action="store_true",
        help="Use the per-user installation.",
    )

    subparsers.add_parser("help", help="Show help message.")
    return parser, list_parser


def build_parser() -> argparse.ArgumentParser:
    return build_parsers()[0]
