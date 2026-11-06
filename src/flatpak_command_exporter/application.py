"""Compatibility exports for the public API now organized in :mod:`api`.

The package root and this module retain their historical import paths.
"""

from typing import Final

import gi

from .api import (
    CommandGroup,
    ExportedAlias,
    FlatpakCommandExporter,
    _launcher_path,
    _read_manifest_or_empty,
    create_launcher,
    export_commands,
    find_refs,
    get_command_groups,
    get_current_ref,
    get_desktop_id_from_metainfo,
    get_exported_aliases,
    get_pretty_name_from_metainfo,
    get_version_from_metainfo,
    load_manifest,
    load_metainfo,
    manifest_exported_commands,
    remove_launcher,
)
from .api.metadata import EXPORT_SCHEMA_NAMES, _find_metainfo_child
from .api.refs import Flatpak, GLib
from .config import AliasConfig
from .defaults import COMMAND_TEMPLATE, DEFAULT_EXPORT_COMMANDS

__all__: Final[list[str]] = [
    "CommandGroup",
    "ExportedAlias",
    "FlatpakCommandExporter",
    "get_command_groups",
    "get_exported_aliases",
    "export_commands",
    "create_launcher",
    "remove_launcher",
    "load_manifest",
    "load_metainfo",
    "manifest_exported_commands",
    "find_refs",
    "get_current_ref",
    "COMMAND_TEMPLATE",
    "DEFAULT_EXPORT_COMMANDS",
    "AliasConfig",
]
