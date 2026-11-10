"""High-level object-oriented interface to Flatpak command exports."""

import logging

from ..config import AliasConfig
from .discovery import get_command_groups, get_exported_aliases
from .launchers import export_commands, remove_launcher
from .models import CommandGroup, ExportedAlias


class FlatpakCommandExporter:
    """Manage and inspect Flatpak command exports for the current user."""

    def __init__(
        self,
        config: AliasConfig | None = None,
        *,
        scope: str | None = None,
        system: bool = False,
    ) -> None:
        if config is None:
            config = AliasConfig(
                scope=("system" if system else "user") if scope is None else scope
            )
        self.config = config

    def get_exported_aliases(
        self,
        *,
        include_system: bool = True,
        scope: str | None = None,
        current_only: bool = False,
    ) -> list[ExportedAlias]:
        config = self.config
        if scope is not None and scope != getattr(config, "scope", "user"):
            config = AliasConfig(scope=scope)
        if scope == "system":
            include_system = False
        return get_exported_aliases(
            config,
            include_system=include_system,
            scope=scope,
            current_only=current_only,
        )

    def get_command_groups(
        self,
        app_id: str | None = None,
        *,
        include_system: bool = True,
        first_only: bool = False,
        scope: str | None = None,
        system: bool = False,
        arch: str | None = None,
        branch: str | None = None,
    ) -> list[CommandGroup]:
        if scope is None and not system:
            return get_command_groups(
                app_id,
                include_system=include_system,
                first_only=first_only,
                arch=arch,
                branch=branch,
            )
        return get_command_groups(
            app_id,
            include_system=include_system,
            first_only=first_only,
            scope=scope,
            system=system,
            arch=arch,
            branch=branch,
        )

    def export_commands(self, app_id: str | None = None) -> None:
        if app_id is None:
            return export_commands(self.config)
        return export_commands(self.config, app_id=app_id)

    def set_default_policy(self, policy: str) -> None:
        logging.info(
            "Setting default export policy to %s for %s scope",
            policy,
            self.config.scope,
        )
        self.config.set_default_policy(policy)
        self.export_commands()

    def set_app_enabled(self, app_id: str, enabled: bool | None) -> None:
        logging.info(
            "Setting app %s enabled state to %s for %s scope",
            app_id,
            enabled,
            self.config.scope,
        )
        self.config.set_app_enabled(app_id, enabled)
        self.export_commands()

    def set_alias_enabled(self, app_id: str, alias: str, enabled: bool) -> None:
        logging.info(
            "Setting alias %s for %s enabled state to %s in %s scope",
            alias,
            app_id,
            enabled,
            self.config.scope,
        )
        self.config.set_alias_enabled(app_id, alias, enabled)
        self.export_commands()

    def add_custom_alias(self, app_id: str, alias: str, command: str) -> None:
        logging.info(
            "Adding custom alias %s for %s in %s scope",
            alias,
            app_id,
            self.config.scope,
        )
        self.config.set_custom_alias(app_id, alias, command)
        self.export_commands()

    def remove_custom_alias(self, app_id: str, alias: str) -> bool:
        removed = self.config.remove_custom_alias(app_id, alias)
        logging.info(
            "Removed custom alias %s for %s in %s scope: %s",
            alias,
            app_id,
            self.config.scope,
            removed,
        )
        self.config.set_alias_enabled(app_id, alias, False)
        if self.config.scope == "user":
            remove_launcher(alias)
        else:
            remove_launcher(alias, scope=self.config.scope)
        self.export_commands()
        return removed
