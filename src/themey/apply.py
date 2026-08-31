"""Point the live KWin at an installed Aurorae theme (``themey apply``).

Writes ``kwinrc`` ``[org.kde.kdecoration2]`` via ``kwriteconfig6`` and asks
KWin to reconfigure over D-Bus. Both Aurorae plugins clamp the theme's
``BorderLeft/Right/Bottom`` to the System Settings "Border size" bracket,
so unless ``--border-size`` is given the bracket is chosen from the
installed ``<name>rc`` (``render.recommended_border_size``).
``--legacy-plugin`` selects the v1 QML plugin ``org.kde.kwin.aurorae``
(which also reads the text-shadow keys) instead of the default ``.v2``.

Button ORDER is global kwinrc state (``ButtonsOnLeft/Right``) that no theme
file can carry, so ``apply`` also writes the theme's binning from the
installed rc's ``[Themey]`` section — e13 stacks all four buttons on the
left; without this the desktop keeps its previous layout and the theme's
buttons appear on the wrong side. The user's previous layout is recorded
once in a ``ThemeyPrevButtons`` marker key (``@unset`` when a key was
absent) and restored by ``themey apply Breeze``; ``keep_buttons=True``
(CLI ``--keep-buttons``) skips button handling entirely.

Revert with ``themey apply Breeze`` (which selects ``org.kde.breeze``,
restores the recorded button layout) or via System Settings → Window
Decorations.
"""
from __future__ import annotations

import configparser
import shutil
import subprocess
from pathlib import Path

from . import paths
from .kwin import BORDER_SIZES, PLUGINS, recommended_border_size

GROUP = "org.kde.kdecoration2"


class ApplyError(Exception):
    pass


def _which(*names: str) -> str:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    raise ApplyError(f"none of {names} found on PATH")


def _kwrite(kw: str, key: str, value: str) -> None:
    subprocess.run(
        [kw, "--file", "kwinrc", "--group", GROUP, "--key", key, value], check=True
    )


def _kdelete(kw: str, key: str) -> None:
    subprocess.run(
        [kw, "--file", "kwinrc", "--group", GROUP, "--key", key, "--delete"],
        check=True,
    )


def _kread(kr: str, key: str) -> str | None:
    """Current kwinrc value, or None when unset.

    ``kreadconfig6`` prints an empty line for an unset key, which conflates
    "absent" with "explicitly empty". For the pre-themey button snapshot we
    accept that: an empty ButtonsOn* is snapshotted as ``@unset`` and
    restored as a key deletion (KWin defaults) instead of an empty list.
    """
    out = subprocess.run(
        [kr, "--file", "kwinrc", "--group", GROUP, "--key", key],
        capture_output=True,
        text=True,
    )
    v = (out.stdout or "").rstrip("\n")
    return v if v else None


def border_size_for_installed(theme_dir: Path, name: str) -> str | None:
    """Recommended BorderSize from ``<name>rc`` [Layout], or None if unreadable."""
    rc = theme_dir / f"{name}rc"
    if not rc.is_file():
        return None
    cp = configparser.RawConfigParser()
    cp.optionxform = staticmethod(str)  # type: ignore[assignment]
    try:
        cp.read(rc, encoding="utf-8")
        layout = cp["Layout"]
        return recommended_border_size(
            int(layout.get("BorderLeft", "0")),
            int(layout.get("BorderRight", "0")),
            int(layout.get("BorderBottom", "0")),
        )
    except (KeyError, ValueError, configparser.Error):
        return None


_PREV_BUTTONS_KEY = "ThemeyPrevButtons"
_UNSET = "@unset"


def buttons_for_installed(theme_dir: Path, name: str) -> tuple[str, str] | None:
    """(LeftButtons, RightButtons) from the installed rc's [Themey] section.

    None when the rc has no such section — themes converted before button
    binning was persisted, or a non-themey Aurorae theme.
    """
    rc = theme_dir / f"{name}rc"
    if not rc.is_file():
        return None
    cp = configparser.RawConfigParser()
    cp.optionxform = staticmethod(str)  # type: ignore[assignment]
    try:
        cp.read(rc, encoding="utf-8")
        sec = cp["Themey"]
        return (sec.get("LeftButtons", ""), sec.get("RightButtons", ""))
    except (KeyError, configparser.Error):
        return None


def _apply_theme_buttons(kw: str, kr: str, left: str, right: str) -> None:
    """Write the theme's button layout, snapshotting the original once."""
    if _kread(kr, _PREV_BUTTONS_KEY) is None:
        prev_l = _kread(kr, "ButtonsOnLeft") or _UNSET
        prev_r = _kread(kr, "ButtonsOnRight") or _UNSET
        _kwrite(kw, _PREV_BUTTONS_KEY, f"{prev_l}|{prev_r}")
    _kwrite(kw, "ButtonsOnLeft", left)
    _kwrite(kw, "ButtonsOnRight", right)


def _restore_buttons(kw: str, kr: str) -> None:
    """Put the snapshotted pre-themey button layout back (Breeze revert)."""
    marker = _kread(kr, _PREV_BUTTONS_KEY)
    if marker is None or "|" not in marker:
        return
    prev_l, prev_r = marker.split("|", 1)
    for key, prev in (("ButtonsOnLeft", prev_l), ("ButtonsOnRight", prev_r)):
        if prev == _UNSET:
            _kdelete(kw, key)
        else:
            _kwrite(kw, key, prev)
    _kdelete(kw, _PREV_BUTTONS_KEY)


def apply(
    name: str,
    *,
    legacy_plugin: bool = False,
    border_size: str | None = None,
    keep_buttons: bool = False,
) -> None:
    kw = _which("kwriteconfig6", "kwriteconfig5")
    kr = _which("kreadconfig6", "kreadconfig5")
    if border_size is not None and border_size not in BORDER_SIZES:
        raise ApplyError(f"unknown border size {border_size!r}; expected one of {BORDER_SIZES}")
    if name.lower() == "breeze":
        _kwrite(kw, "library", "org.kde.breeze")
        _kwrite(kw, "theme", "Breeze")
        if not keep_buttons:
            _restore_buttons(kw, kr)
    else:
        theme_dir = paths.aurorae_themes() / name
        if not theme_dir.is_dir():
            raise ApplyError(f"{name!r} is not installed under {paths.aurorae_themes()}")
        _kwrite(kw, "library", PLUGINS["legacy" if legacy_plugin else "v2"])
        _kwrite(kw, "theme", f"__aurorae__svg__{name}")
        if border_size is None:
            border_size = border_size_for_installed(theme_dir, name)
        if not keep_buttons:
            btns = buttons_for_installed(theme_dir, name)
            if btns is not None:
                _apply_theme_buttons(kw, kr, btns[0], btns[1])
    if border_size is not None:
        _kwrite(kw, "BorderSize", border_size)
        _kwrite(kw, "BorderSizeAuto", "false")
    qdbus = _which("qdbus6", "qdbus-qt6", "qdbus")
    subprocess.run([qdbus, "org.kde.KWin", "/KWin", "reconfigure"], check=False)
