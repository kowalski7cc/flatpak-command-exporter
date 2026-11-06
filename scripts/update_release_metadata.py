#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import tomllib
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parent.parent
METADATA = (
    ROOT / "resources/xyz.kowalski7cc.flatpak-command-exporter.metainfo.xml"
)
SPEC = ROOT / "flatpak-command-exporter.spec"


def release_date() -> datetime:
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        return datetime.fromtimestamp(int(epoch), timezone.utc)
    return datetime.now(timezone.utc)


def project_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as project_file:
        return tomllib.load(project_file)["project"]["version"]


def update_metainfo(version: str, date: datetime) -> None:
    tree = ET.parse(METADATA)
    releases = tree.getroot().find("releases")
    if releases is None:
        raise ValueError(f"{METADATA} has no <releases> element")
    if any(
        release.get("version") == version
        for release in releases.findall("release")
    ):
        print(f"Metainfo already contains version {version}; unchanged.")
        return

    text = METADATA.read_text()
    opening_tag = "  <releases>\n"
    if text.count(opening_tag) != 1:
        raise ValueError(f"Expected one {opening_tag.strip()!r} in {METADATA}")
    entry = (
        f'    <release version="{version}" date="{date:%Y-%m-%d}">\n'
        f"      <description><p>Release {version}.</p></description>\n"
        "    </release>\n"
    )
    METADATA.write_text(text.replace(opening_tag, opening_tag + entry))


def update_spec(version: str, date: datetime) -> None:
    text = SPEC.read_text()
    marker = "%changelog\n"
    if text.count(marker) != 1:
        raise ValueError(f"Expected one {marker.strip()} section in {SPEC}")

    weekdays = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    months = (
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    header = (
        f"* {weekdays[date.weekday()]} {months[date.month - 1]} {date.day:02d} "
        f"{date.year} Kowalski Dragon <kowalski7cc@users.noreply.github.com> "
        f"- {version}-1\n- Release {version}.\n\n"
    )
    SPEC.write_text(text.replace(marker, marker + header))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", choices=("metainfo", "spec"))
    args = parser.parse_args()
    version = project_version()
    date = release_date()

    if args.target == "metainfo":
        update_metainfo(version, date)
    else:
        update_spec(version, date)


if __name__ == "__main__":
    main()
