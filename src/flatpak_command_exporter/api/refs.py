"""Flatpak installation and application-ref helpers."""

import logging
from dataclasses import dataclass

import gi

gi.require_version("Flatpak", "1.0")
from gi.repository import Flatpak, GLib


@dataclass(frozen=True)
class _InstalledRef:
    ref: object
    installation: object
    installation_path: str
    scope: str


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


def _get_installed_refs(*, scope="user", include_system=True):
    if scope not in {"user", "system"}:
        raise ValueError(f"Unknown Flatpak installation scope: {scope!r}")

    installations = []
    if scope == "system":
        installations.append(("system", Flatpak.Installation.new_system))
    else:
        installations.append(("user", Flatpak.Installation.new_user))
        if include_system:
            installations.append(("system", Flatpak.Installation.new_system))

    refs = []
    seen_refs = set()
    for installation_scope, installation_factory in installations:
        try:
            installation = installation_factory()
            if installation is None:
                continue
            installation_path = installation.get_path().get_path()
        except GLib.Error as error:
            logging.warning("Could not access a Flatpak installation: %s", error)
            continue

        for ref in find_refs(installation):
            ref_key = (ref.get_name(), ref.get_arch(), ref.get_branch())
            if ref_key in seen_refs:
                logging.debug(
                    "Ignoring duplicate %s ref %s/%s/%s",
                    installation_scope,
                    *ref_key,
                )
                continue
            seen_refs.add(ref_key)
            refs.append(
                _InstalledRef(
                    ref=ref,
                    installation=installation,
                    installation_path=installation_path,
                    scope=installation_scope,
                )
            )
    return refs
