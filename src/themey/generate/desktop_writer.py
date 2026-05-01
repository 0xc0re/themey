"""Hand-rolled .desktop INI writer.

DO NOT use configparser — localized keys like ``Name[de]=Foo`` look like
section headers to configparser's regex.

Usage::

    write_desktop(path, {
        "Desktop Entry": {
            "Name": "My Theme",
            "Name[de]": "Mein Thema",
            "X-KDE-PluginInfo-Name": "my-theme",
        }
    })
"""
from __future__ import annotations

from pathlib import Path


def write_desktop(path: Path, sections: dict[str, dict[str, str]]) -> None:
    """Write a .desktop / .service INI file with verbatim key and section names.

    Args:
        path: Destination path to write.
        sections: Ordered dict of section-name → {key: value} entries.
            Keys are written verbatim — no case folding, no interpolation.
            Multiple sections are separated by a blank line.
    """
    with open(path, "w", encoding="utf-8") as f:
        first = True
        for section, entries in sections.items():
            if not first:
                f.write("\n")
            f.write(f"[{section}]\n")
            for k, v in entries.items():
                f.write(f"{k}={v}\n")
            first = False
