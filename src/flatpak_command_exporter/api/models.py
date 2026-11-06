"""Data models returned by the public Flatpak command API."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExportedAlias:
    alias: str
    command: str
    app_id: str
    app_name: str
    arch: str
    branch: str
    installation_path: str
    desktop_id: str
    enabled: bool = True
    configurable: bool = True
    custom: bool = False
    installation_scope: str = "user"


@dataclass(frozen=True)
class CommandGroup:
    app_id: str
    app_name: str
    arch: str
    branch: str
    installation_path: str
    commands: dict[str, str]
