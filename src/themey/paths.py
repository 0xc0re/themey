"""XDG_DATA_HOME-aware install paths.

All install paths derive from XDG_DATA_HOME (or ~/.local/share if unset).
Snap-launched shells (e.g. VS Code's terminal) point XDG_DATA_HOME into the
snap sandbox; KWin only reads the real ~/.local/share, so such values are
ignored with a warning — otherwise convert installs where KWin can't see and
apply blanks every window border. Tests monkeypatch HOME + XDG_DATA_HOME via
the fake_home fixture.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def _xdg_data_home() -> Path:
    v = os.environ.get("XDG_DATA_HOME")
    if v and "/snap/" in v:
        log.warning(
            "XDG_DATA_HOME=%s is a snap sandbox KWin never reads; using ~/.local/share", v
        )
        v = None
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
