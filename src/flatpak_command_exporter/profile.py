import os
from importlib.resources import files
from pathlib import Path
from typing import Final


PROFILE_SCRIPT: Final[str] = "flatpak-exported-commands.sh"
PROFILE_MARKER_START: Final[str] = "# >>> Flatpak Command Exporter >>>"
PROFILE_MARKER_END: Final[str] = "# <<< Flatpak Command Exporter <<<"
SYSTEM_PROFILE_DIRECTORY: Final[Path] = Path("/etc/profile.d")


def _ensure_writable_directory(directory: Path) -> None:
    if directory.exists() and not directory.is_dir():
        raise NotADirectoryError(f"{directory} is not a directory")

    candidate = directory
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            break
        if parent.exists() and parent.is_file():
            raise NotADirectoryError(f"{parent} is not a directory")
        candidate = parent

    if not candidate.exists() or not candidate.is_dir():
        raise NotADirectoryError(f"{directory} does not resolve to a directory")
    if not os.access(candidate, os.W_OK):
        raise PermissionError(f"{candidate} is not writable")


def install_profile(scope: str = "user") -> Path:
    script = files("flatpak_command_exporter").joinpath(PROFILE_SCRIPT).read_text(
        encoding="utf-8"
    )
    if scope == "system":
        destination = SYSTEM_PROFILE_DIRECTORY / PROFILE_SCRIPT
        _ensure_writable_directory(destination.parent)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(script, encoding="utf-8")
        destination.chmod(0o644)
        return destination
    if scope != "user":
        raise ValueError(f"Unknown profile installation scope: {scope!r}")

    config_home = Path(
        os.environ.get(
            "XDG_CONFIG_HOME",
            os.path.join(os.path.expanduser("~"), ".config"),
        )
    )
    destination = (
        config_home
        / "flatpak-command-exporter"
        / "profile.d"
        / PROFILE_SCRIPT
    )
    _ensure_writable_directory(destination.parent)
    profile_file = Path(os.path.expanduser("~")) / ".profile"
    if profile_file.exists() and not profile_file.is_file():
        raise NotADirectoryError(f"{profile_file} is not a regular file")
    if profile_file.exists() and not os.access(profile_file, os.W_OK):
        raise PermissionError(f"{profile_file} is not writable")
    if not profile_file.exists():
        _ensure_writable_directory(profile_file.parent)
    existing = profile_file.read_text(encoding="utf-8") if profile_file.exists() else ""
    source_path = (
        '"${XDG_CONFIG_HOME:-$HOME/.config}'
        "/flatpak-command-exporter/profile.d/flatpak-exported-commands.sh\""
    )
    block = "\n".join(
        (
            PROFILE_MARKER_START,
            f"if [ -r {source_path} ]; then",
            f"    . {source_path}",
            "fi",
            PROFILE_MARKER_END,
        )
    )
    start = existing.find(PROFILE_MARKER_START)
    end = existing.find(PROFILE_MARKER_END)
    if start == -1 and end == -1:
        updated = f"{existing.rstrip()}\n\n{block}\n" if existing else f"{block}\n"
    elif start == -1 or end < start:
        raise ValueError(f"Malformed Flatpak Command Exporter block in {profile_file}")
    else:
        end += len(PROFILE_MARKER_END)
        updated = f"{existing[:start]}{block}{existing[end:]}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(script, encoding="utf-8")
    destination.chmod(0o644)
    profile_file.write_text(updated, encoding="utf-8")
    return destination
