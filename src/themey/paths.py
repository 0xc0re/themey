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


def _is_snap_sandbox(v: str | None) -> bool:
    return bool(v) and "/snap/" in str(v)


def _xdg_data_home() -> Path:
    v = os.environ.get("XDG_DATA_HOME")
    if _is_snap_sandbox(v):
        log.warning(
            "XDG_DATA_HOME=%s is a snap sandbox KWin never reads; using ~/.local/share", v
        )
        v = None
    if v:
        return Path(v)
    return Path(os.environ.get("HOME", "/")).joinpath(".local", "share")


def subprocess_env() -> dict[str, str]:
    """Environment for the external Plasma tools (``plasma-apply-*``,
    ``kwriteconfig6``, ``qdbus6``): the current one minus a snap-sandbox
    ``XDG_DATA_HOME``.

    Those tools search KPackages through KDE's own XDG lookup, so an
    inherited ``XDG_DATA_HOME=~/snap/code/NNN/.local/share`` (the VS Code
    snap's terminal) makes ``plasma-apply-lookandfeel -a themey_<slug>``
    report "Unable to find the theme" even though :func:`_xdg_data_home`
    installed it under ``~/.local/share`` — seen live 2026-09-01. Dropping
    the variable makes the tools fall back to the same default themey
    already uses.
    """
    env = dict(os.environ)
    if _is_snap_sandbox(env.get("XDG_DATA_HOME")):
        env.pop("XDG_DATA_HOME", None)
    return env


def aurorae_themes() -> Path:
    return _xdg_data_home() / "aurorae" / "themes"


def kwin_decorations() -> Path:
    """QML decoration KPackages (KWin/Decoration) — the QML backend's home."""
    return _xdg_data_home() / "kwin" / "decorations"


def color_schemes() -> Path:
    """KColorScheme ``.colors`` files — read by System Settings → Colors."""
    return _xdg_data_home() / "color-schemes"


def wallpapers() -> Path:
    """Plasma wallpaper packages (one directory per image)."""
    return _xdg_data_home() / "wallpapers"


def cursor_themes() -> Path:
    """XCursor pointer themes: ``~/.icons/<theme>/cursors/``.

    Deliberately NOT under ``_xdg_data_home()``: cursor lookup goes through
    libXcursor's compiled-in search path, and Kubuntu's build (hence
    Plasma's cursor KCM and ``plasma-apply-cursortheme`` on it) scans
    ``~/.icons`` and ``/usr/share/icons`` but never
    ``$XDG_DATA_HOME/icons`` — a theme installed there simply doesn't
    exist as far as System Settings is concerned (verified live
    2026-08-31; every third-party cursor theme on the reference machine
    installs to ``~/.icons`` for the same reason). Still per-user and
    reversible: uninstall = delete ``~/.icons/themey_<slug>-cursors``.
    """
    return Path(os.environ.get("HOME", "/")) / ".icons"


def desktop_themes() -> Path:
    """Plasma Style (desktop theme) packages — panel/popup/tooltip chrome."""
    return _xdg_data_home() / "plasma" / "desktoptheme"


def look_and_feel() -> Path:
    """Plasma Global Theme (Look-and-Feel) packages."""
    return _xdg_data_home() / "plasma" / "look-and-feel"


def plasmoids() -> Path:
    """Plasma applet (``Plasma/Applet``) packages — themey's own pager and
    desk-button applets (``generate/plasmoids``); scanned by plasmashell
    and ``kpackagetool6 --type Plasma/Applet --list`` (verified live
    2026-09-01)."""
    return _xdg_data_home() / "plasma" / "plasmoids"


def themey_previews() -> Path:
    return _xdg_data_home() / "themey" / "previews"


def themey_reports() -> Path:
    # report.txt lives next to the preview html
    return _xdg_data_home() / "themey" / "previews"
