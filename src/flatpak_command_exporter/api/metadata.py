"""Manifest and metainfo parsing helpers for Flatpak application refs."""

import json
import logging
import os
import xml.etree.ElementTree as ET
from typing import Final

from ..defaults import DEFAULT_EXPORT_COMMANDS

EXPORT_SCHEMA_NAMES: Final[tuple[str, ...]] = (
    "x-export-commands",
    "export-commands",
)


def load_metainfo(
    base_path: str | os.PathLike[str],
    app_id: str,
    arch: str,
    branch: str,
) -> ET.Element | None:
    metainfo_path = os.path.join(
        base_path,
        "app",
        app_id,
        arch,
        branch,
        "active",
        "files",
        "share",
        "metainfo",
        f"{app_id}.metainfo.xml",
    )
    if not os.path.exists(metainfo_path):
        logging.warning("Metainfo file not found for %s at %s.", app_id, metainfo_path)
        return None
    try:
        tree = ET.parse(metainfo_path)
        logging.debug("Loaded metainfo for %s from %s", app_id, metainfo_path)
        return tree.getroot()
    except ET.ParseError as error:
        logging.error("Error parsing metainfo for %s: %s", app_id, error)
        return None


def _find_metainfo_child(
    metainfo: ET.Element, tag: str
) -> ET.Element | None:
    return next(
        (child for child in metainfo if child.tag.rsplit("}", 1)[-1] == tag),
        None,
    )


def get_pretty_name_from_metainfo(
    metainfo: ET.Element | None,
) -> str | None:
    if metainfo is None:
        return None
    name_element = _find_metainfo_child(metainfo, "name")
    if name_element is not None and name_element.text:
        return name_element.text.strip()
    return None


def get_desktop_id_from_metainfo(
    metainfo: ET.Element | None, app_id: str
) -> str:
    if metainfo is None:
        return f"{app_id}.desktop"
    launchable = _find_metainfo_child(metainfo, "launchable")
    if (
        launchable is not None
        and launchable.get("type") == "desktop-id"
        and launchable.text
    ):
        return launchable.text.strip()
    return f"{app_id}.desktop"


def get_version_from_metainfo(metainfo: ET.Element | None) -> str | None:
    if metainfo is None:
        return None
    releases_element = _find_metainfo_child(metainfo, "releases")
    if releases_element is not None:
        release_element = _find_metainfo_child(releases_element, "release")
        if release_element is not None:
            release_version = release_element.get("version")
            if release_version:
                return release_version.strip()

    version_element = _find_metainfo_child(metainfo, "version")
    if version_element is not None and version_element.text:
        return version_element.text.strip()
    return None


def load_manifest(
    base_path: str | os.PathLike[str],
    app_id: str,
    arch: str,
    branch: str,
) -> object:
    manifest_path = os.path.join(
        base_path, "app", app_id, arch, branch, "active", "files", "manifest.json"
    )
    logging.debug("Reading manifest for %s from %s", app_id, manifest_path)
    with open(manifest_path, encoding="utf-8") as manifest_file:
        return json.load(manifest_file)


def _read_manifest_or_empty(
    installation_path: str | os.PathLike[str],
    app_id: str,
    arch: str,
    branch: str,
) -> dict[str, object] | None:
    try:
        manifest = load_manifest(installation_path, app_id, arch, branch)
    except FileNotFoundError:
        logging.debug("No manifest found for %s; using an empty manifest", app_id)
        return {}
    except (OSError, json.JSONDecodeError) as error:
        logging.warning("Could not load manifest for %s: %s", app_id, error)
        return None

    if not isinstance(manifest, dict):
        logging.warning("Manifest for %s is not a dictionary. Ignoring.", app_id)
        return None
    return {str(key): value for key, value in manifest.items()}


def manifest_exported_commands(
    app_id: str, manifest: dict[str, object]
) -> dict[str, str]:
    commands: dict[str, str] = {}
    for schema_name in EXPORT_SCHEMA_NAMES:
        schema_commands = manifest.get(schema_name, {})
        if not isinstance(schema_commands, dict):
            logging.warning(
                "%s in manifest for %s is not a dictionary. Ignoring.",
                schema_name,
                app_id,
            )
            continue
        for alias, command in schema_commands.items():
            if not isinstance(alias, str) or not isinstance(command, str):
                logging.warning(
                    "%s in manifest for %s contains a non-string command. Ignoring.",
                    schema_name,
                    app_id,
                )
                continue
            commands[alias] = command
    if not commands:
        logging.debug("Using built-in command defaults for %s", app_id)
        return DEFAULT_EXPORT_COMMANDS.get(app_id, {})
    return commands
