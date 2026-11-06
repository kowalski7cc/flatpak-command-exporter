"""Public Python API for discovering and exporting Flatpak commands."""

from typing import Final

from .discovery import get_command_groups, get_exported_aliases
from .exporter import FlatpakCommandExporter
from .launchers import (
    _launcher_path,
    create_launcher,
    export_commands,
    remove_launcher,
)
from .metadata import (
    EXPORT_SCHEMA_NAMES,
    _read_manifest_or_empty,
    get_desktop_id_from_metainfo,
    get_pretty_name_from_metainfo,
    get_version_from_metainfo,
    load_manifest,
    load_metainfo,
    manifest_exported_commands,
)
from .models import CommandGroup, ExportedAlias
from .refs import find_refs, get_current_ref

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
    "get_desktop_id_from_metainfo",
    "get_pretty_name_from_metainfo",
    "get_version_from_metainfo",
    "find_refs",
    "get_current_ref",
    "EXPORT_SCHEMA_NAMES",
]
