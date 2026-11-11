"""Helpers for loading Flatpak's GObject Introspection namespace."""


def require_flatpak_namespace() -> None:
    import gi

    try:
        gi.require_version("Flatpak", "1.0")
    except ValueError as error:
        if "Namespace Flatpak not available" not in str(error):
            raise
        raise ImportError(
            "The Flatpak-1.0 GObject Introspection typelib is missing. "
            "Install the Flatpak GI typelib package for your distribution "
            "(flatpak-libs on Fedora)."
        ) from error
