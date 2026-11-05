import tempfile
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flatpak_command_exporter import FlatpakCommandExporter
from flatpak_command_exporter import application as core
from flatpak_command_exporter.gui import get_exported_icon


class AliasDataTests(unittest.TestCase):
    def test_current_user_ref_overrides_system_and_system_only_app_remains(self):
        class Ref:
            def __init__(self, app_id, branch="stable"):
                self.app_id = app_id
                self.branch = branch

            def get_name(self):
                return self.app_id

            def get_arch(self):
                return "x86_64"

            def get_branch(self):
                return self.branch

        user_refs = [Ref("app.override"), Ref("app.override", "beta")]
        system_refs = [
            Ref("app.override"),
            Ref("app.override", "beta"),
            Ref("app.system-only"),
        ]
        user_installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/user"),
            get_current_installed_app=lambda app_id, _cancellable: user_refs[-1],
        )
        system_installation = SimpleNamespace(
            get_path=lambda: SimpleNamespace(get_path=lambda: "/system"),
            get_current_installed_app=lambda app_id, _cancellable: next(
                ref for ref in system_refs if ref.get_name() == app_id
            ),
        )
        installation_api = SimpleNamespace(
            new_user=lambda: user_installation,
            new_system=lambda: system_installation,
        )

        def load_manifest(path, app_id, _arch, branch):
            return {"x-export-commands": {f"{app_id}-{path}-{branch}": "command"}}

        with tempfile.TemporaryDirectory() as data_home:
            with (
                patch.dict(os.environ, {"XDG_DATA_HOME": data_home}),
                patch.object(core, "Flatpak", SimpleNamespace(Installation=installation_api)),
                patch.object(
                    core,
                    "find_refs",
                    side_effect=lambda installation: user_refs if installation is user_installation else system_refs,
                ),
                patch.object(core, "load_manifest", side_effect=load_manifest),
                patch.object(core, "load_metainfo", return_value=None),
            ):
                records = FlatpakCommandExporter().get_exported_aliases()

        self.assertEqual(
            [(record.app_id, record.branch, record.installation_path) for record in records],
            [
                ("app.override", "beta", "/user"),
                ("app.system-only", "stable", "/system"),
            ],
        )


class DesktopIconTests(unittest.TestCase):
    def test_reads_icon_from_flatpak_exported_desktop_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            share_directory = Path(temporary_directory) / "share"
            applications = share_directory / "applications"
            applications.mkdir(parents=True)
            (applications / "app.test.desktop").write_text(
                "[Desktop Entry]\nType=Application\nIcon=app.test-icon\n",
                encoding="utf-8",
            )
            record = SimpleNamespace(
                app_id="app.test",
                desktop_id="app.test.desktop",
                installation_path="/not-used",
            )

            self.assertEqual(
                get_exported_icon(record, [str(Path(temporary_directory))]),
                "app.test-icon",
            )

    def test_missing_desktop_file_has_no_icon(self):
        record = SimpleNamespace(
            app_id="app.missing",
            desktop_id="app.missing.desktop",
            installation_path="/not-used",
        )

        self.assertIsNone(get_exported_icon(record, []))


if __name__ == "__main__":
    unittest.main()