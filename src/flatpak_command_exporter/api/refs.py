"""Flatpak installation and application-ref helpers."""

import logging

import gi

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib


def find_refs(installation):
    """Find all application refs in a Flatpak installation."""
    try:
        if installation is None:
            logging.debug("Skipping unavailable Flatpak installation")
            return
        logging.debug("Enumerating installed Flatpak application refs")
        for ref in installation.list_installed_refs_by_kind(Flatpak.RefKind.APP, None):
            logging.debug(
                "Found Flatpak ref %s/%s/%s",
                ref.get_name(),
                ref.get_arch(),
                ref.get_branch(),
            )
            yield ref
    except GLib.Error as error:
        logging.error("Error accessing Flatpak API: %s", error)


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
    logging.debug(
        "Selected current ref %s/%s/%s",
        ref.get_name(),
        ref.get_arch(),
        ref.get_branch(),
    )
    return ref
