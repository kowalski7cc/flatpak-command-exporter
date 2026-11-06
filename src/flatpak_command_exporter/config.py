import configparser
import os
from collections.abc import Iterable
from pathlib import Path
import tempfile
from typing import Final

LEGACY_SYSTEM_ALIAS_DIRECTORY: Final[Path] = Path("/usr/lib/flatpak/aliases")


def _get_system_installation_path() -> Path:
    import gi

    gi.require_version("Flatpak", "1.0")
    from gi.repository import Flatpak

    installation = Flatpak.Installation.new_system()
    if installation is None:
        raise RuntimeError("Could not resolve the default system Flatpak installation")
    return Path(installation.get_path().get_path())


class AliasConfigError(ValueError):
    """Raised when alias configuration is invalid or cannot be read."""


class AliasConfig:
    """Read and update the user's Flatpak command alias configuration."""

    def __init__(
        self,
        data_home: str | os.PathLike[str] | None = None,
        *,
        scope: str = "user",
    ) -> None:
        self.scope: str = scope
        self._use_legacy_system_config: bool = (
            data_home is None and scope == "system"
        )
        if data_home is None:
            if scope == "system":
                data_home = _get_system_installation_path()
            else:
                data_home = os.environ.get("XDG_DATA_HOME") or os.path.join(
                    os.path.expanduser("~"), ".local", "share"
                )
        self.data_home: Path = Path(data_home)
        self.directory: Path = (
            self.data_home / "aliases"
            if scope == "system"
            else self.data_home / "flatpak" / "aliases"
        )

    @property
    def export_directory(self) -> Path:
        if self.scope == "system":
            return self.data_home.parent / f"{self.data_home.name}-commands"
        return self.data_home / "flatpak-commands"

    @property
    def is_writable(self) -> bool:
        try:
            candidate = self.directory
            while not candidate.exists():
                parent = candidate.parent
                if parent == candidate:
                    return os.access(candidate, os.W_OK)
                if parent.exists() and parent.is_file():
                    return False
                candidate = parent
            return candidate.is_dir() and os.access(candidate, os.W_OK)
        except OSError:
            return False

    def _ensure_writable(self) -> None:
        if not self.is_writable:
            raise PermissionError(f"{self.directory} is not writable for {self.scope} scope")

    @property
    def global_path(self) -> Path:
        return self.directory / "global"

    def app_path(self, app_id: str) -> Path:
        if (
            not isinstance(app_id, str)
            or not app_id
            or app_id in {".", ".."}
            or "/" in app_id
            or "\\" in app_id
            or "\0" in app_id
        ):
            raise AliasConfigError(f"Invalid Flatpak app ID: {app_id!r}")
        return self.directory / app_id

    def _read(self, path: Path) -> configparser.ConfigParser:
        parser = configparser.ConfigParser(interpolation=None, strict=False)
        parser.optionxform = str
        try:
            with path.open(encoding="utf-8") as config_file:
                parser.read_file(config_file)
        except FileNotFoundError:
            legacy_path = LEGACY_SYSTEM_ALIAS_DIRECTORY / path.name
            if not self._use_legacy_system_config or not legacy_path.exists():
                return parser
            try:
                with legacy_path.open(encoding="utf-8") as config_file:
                    parser.read_file(config_file)
            except (OSError, UnicodeError, configparser.Error) as error:
                raise AliasConfigError(
                    f"Could not read {legacy_path}: {error}"
                ) from error
        except (OSError, UnicodeError, configparser.Error) as error:
            raise AliasConfigError(f"Could not read {path}: {error}") from error
        return parser

    def _write(self, path: Path, parser: configparser.ConfigParser) -> None:
        self._ensure_writable()
        self.directory.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f".{path.name}.", dir=self.directory, text=True
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as config_file:
                parser.write(config_file)
            os.chmod(temporary_path, 0o600)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def default_policy(self) -> str:
        parser = self._read(self.global_path)
        policy = parser.get(
            "core",
            "default-export",
            fallback="none" if self.scope == "system" else "all",
        )
        if policy not in {"all", "none"}:
            raise AliasConfigError(
                f"Invalid default-export value in {self.global_path}: {policy!r}"
            )
        return policy

    def set_default_policy(self, policy: str) -> None:
        if policy not in {"all", "none"}:
            raise AliasConfigError("Default export policy must be 'all' or 'none'")
        parser = self._read(self.global_path)
        if not parser.has_section("core"):
            parser.add_section("core")
        parser.set("core", "default-export", policy)
        self._write(self.global_path, parser)

    def _app_config(self, app_id: str) -> configparser.ConfigParser:
        return self._read(self.app_path(app_id))

    def app_enabled(self, app_id: str) -> bool | None:
        parser = self._app_config(app_id)
        if not parser.has_option("app", "enabled"):
            return None
        try:
            return parser.getboolean("app", "enabled")
        except ValueError as error:
            raise AliasConfigError(
                f"Invalid app enabled value for {app_id}: {error}"
            ) from error

    def app_overrides(self) -> dict[str, bool]:
        try:
            config_paths = list(self.directory.iterdir())
        except FileNotFoundError:
            return {}

        overrides = {}
        for path in config_paths:
            if (
                not path.is_file()
                or path.name == "global"
                or path.name.startswith(".")
            ):
                continue
            enabled = self.app_enabled(path.name)
            if enabled is not None:
                overrides[path.name] = enabled
        return overrides

    def clear_overrides(self) -> None:
        try:
            config_paths = list(self.directory.iterdir())
        except FileNotFoundError:
            return

        for path in config_paths:
            if (
                not path.is_file()
                or path.name == "global"
                or path.name.startswith(".")
            ):
                continue
            parser = self._read(path)
            changed = (
                parser.remove_option("app", "enabled")
                if parser.has_option("app", "enabled")
                else False
            )
            changed = parser.remove_section("aliases") or changed
            if changed:
                self._write(path, parser)

    def set_app_enabled(self, app_id: str, enabled: bool | None) -> None:
        if enabled is not None and not isinstance(enabled, bool):
            raise AliasConfigError("App enabled setting must be true, false, or None")
        parser = self._app_config(app_id)
        if enabled is None:
            if parser.has_option("app", "enabled"):
                parser.remove_option("app", "enabled")
        else:
            if not parser.has_section("app"):
                parser.add_section("app")
            parser.set("app", "enabled", str(bool(enabled)).lower())
        self._write(self.app_path(app_id), parser)

    def alias_enabled(self, app_id: str, alias: str) -> bool | None:
        parser = self._app_config(app_id)
        if not parser.has_option("aliases", alias):
            return None
        try:
            return parser.getboolean("aliases", alias)
        except ValueError as error:
            raise AliasConfigError(
                f"Invalid enabled value for alias {alias!r} in {app_id}: {error}"
            ) from error

    def set_alias_enabled(
        self, app_id: str, alias: str, enabled: bool
    ) -> None:
        self._validate_alias(alias)
        if not isinstance(enabled, bool):
            raise AliasConfigError("Alias enabled setting must be true or false")
        parser = self._app_config(app_id)
        if not parser.has_section("aliases"):
            parser.add_section("aliases")
        parser.set("aliases", alias, str(bool(enabled)).lower())
        self._write(self.app_path(app_id), parser)

    def set_aliases_enabled(
        self, app_id: str, aliases: Iterable[str], enabled: bool
    ) -> None:
        if not isinstance(enabled, bool):
            raise AliasConfigError("Alias enabled setting must be true or false")
        aliases = tuple(dict.fromkeys(aliases))
        for alias in aliases:
            self._validate_alias(alias)
        if not aliases:
            return

        parser = self._app_config(app_id)
        if not parser.has_section("aliases"):
            parser.add_section("aliases")
        value = str(enabled).lower()
        for alias in aliases:
            parser.set("aliases", alias, value)
        self._write(self.app_path(app_id), parser)

    def custom_aliases(self, app_id: str) -> dict[str, str]:
        parser = self._app_config(app_id)
        if parser.has_section("custom-aliases"):
            return dict(parser.items("custom-aliases"))
        return {}

    def set_custom_alias(
        self, app_id: str, alias: str, command: str
    ) -> None:
        self._validate_alias(alias)
        if (
            not isinstance(command, str)
            or not command
            or "\n" in command
            or "\r" in command
        ):
            raise AliasConfigError("Custom alias command must be a non-empty single line")
        parser = self._app_config(app_id)
        if not parser.has_section("custom-aliases"):
            parser.add_section("custom-aliases")
        parser.set("custom-aliases", alias, command)
        if not parser.has_section("aliases"):
            parser.add_section("aliases")
        parser.set("aliases", alias, "true")
        self._write(self.app_path(app_id), parser)

    def remove_custom_alias(self, app_id: str, alias: str) -> bool:
        parser = self._app_config(app_id)
        removed = parser.remove_option("custom-aliases", alias)
        self._write(self.app_path(app_id), parser)
        return removed

    def is_alias_enabled(self, app_id: str, alias: str) -> bool:
        alias_setting = self.alias_enabled(app_id, alias)
        if alias_setting is not None:
            return alias_setting
        app_setting = self.app_enabled(app_id)
        if app_setting is not None:
            return app_setting
        return self.default_policy() == "all"

    @staticmethod
    def _validate_alias(alias: str) -> None:
        if (
            not isinstance(alias, str)
            or not alias
            or alias in {".", ".."}
            or any(character.isspace() for character in alias)
            or "/" in alias
            or "\\" in alias
            or "\0" in alias
            or "=" in alias
            or ":" in alias
        ):
            raise AliasConfigError(f"Invalid command alias: {alias!r}")
