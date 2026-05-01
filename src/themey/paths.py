"""XDG_DATA_HOME-aware install paths.

All install paths derive from XDG_DATA_HOME (or ~/.local/share if unset).
Tests monkeypatch HOME + XDG_DATA_HOME via the fake_home fixture.
"""
from __future__ import annotations

import os
from pathlib import Path


def _xdg_data_home() -> Path:
    v = os.environ.get("XDG_DATA_HOME")
    if v:
        return Path(v)
    return Path(os.environ.get("HOME", "/")).joinpath(".local", "share")


def aurorae_themes() -> Path:
    return _xdg_data_home() / "aurorae" / "themes"


def themey_previews() -> Path:
    return _xdg_data_home() / "themey" / "previews"


def themey_reports() -> Path:
    # Phase 1 ships report.txt next to preview html
    return _xdg_data_home() / "themey" / "previews"
