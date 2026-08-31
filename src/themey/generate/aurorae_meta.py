"""Aurorae metadata.desktop + metadata.json writers.

Emits BOTH files:
- ``metadata.desktop`` — legacy KF5-compatible plugin descriptor
- ``metadata.json``    — KF6-native JSON plugin descriptor

Edna ships both; emitting both future-proofs against KF5 deprecation at
near-zero extra cost.

``metadata.desktop`` is written via the hand-rolled ``write_desktop`` writer
(NOT configparser — localization keys like ``Name[de]=Foo`` confuse configparser).
"""
from __future__ import annotations

import json
from pathlib import Path

from themey.ir import Theme

from .desktop_writer import write_desktop


def write_metadata_desktop(theme: Theme, out_dir: Path) -> Path:
    """Write ``metadata.desktop`` Aurorae plugin descriptor.

    Args:
        theme: Frozen Theme IR.
        out_dir: Directory to write into.

    Returns:
        Path to the written ``metadata.desktop``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "metadata.desktop"
    write_desktop(
        path,
        {
            "Desktop Entry": {
                "Name": theme.display_name,
                "X-KDE-PluginInfo-Author": theme.author or "themes.effx.us",
                "X-KDE-PluginInfo-Email": "",
                "X-KDE-PluginInfo-Name": theme.name,
                "X-KDE-PluginInfo-Version": "1.0",
                "X-KDE-PluginInfo-Category": "",
                "X-KDE-PluginInfo-Depends": "",
                "X-KDE-PluginInfo-License": "Unknown",
                "X-KDE-PluginInfo-EnabledByDefault": "true",
                "X-KDE-PluginInfo-blur": "false",
            }
        },
    )
    return path


def write_metadata_json(theme: Theme, out_dir: Path) -> Path:
    """Write ``metadata.json`` KF6-native plugin descriptor.

    Args:
        theme: Frozen Theme IR.
        out_dir: Directory to write into.

    Returns:
        Path to the written ``metadata.json``.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "KPackageStructure": "KWin/Aurorae",
        "KPlugin": {
            "Authors": [
                {
                    "Name": theme.author or "themes.effx.us",
                    "Email": "",
                }
            ],
            "Category": "Plasma 6 Window Decorations",
            "ServiceTypes": ["KWin/Aurorae"],
            "EnabledByDefault": True,
            "Name": theme.display_name,
            "Description": (
                f"{theme.display_name} window decoration (converted from E16 by themey)"
            ),
            "Id": theme.name,
            "Version": "1.0",
            "License": "Unknown",
            "X-KDE-PluginInfo-blur": False,
            "X-KPackage-Dependencies": [],
        },
    }
    path = out_dir / "metadata.json"
    path.write_text(json.dumps(data, indent=4), encoding="utf-8")
    return path
