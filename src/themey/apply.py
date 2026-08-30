"""Point the live KWin at an installed Aurorae theme (``themey apply``).

Writes ``kwinrc`` ``[org.kde.kdecoration2]`` via ``kwriteconfig6`` and asks
KWin to reconfigure over D-Bus. Both Aurorae plugins clamp the theme's
``BorderLeft/Right/Bottom`` to the System Settings "Border size" bracket,
so unless ``--border-size`` is given the bracket is chosen from the
installed ``<name>rc`` (``render.recommended_border_size``).
``--legacy-plugin`` selects the v1 QML plugin ``org.kde.kwin.aurorae``
(which also reads the text-shadow keys) instead of the default ``.v2``.

Revert with ``themey apply Breeze`` (which selects ``org.kde.breeze``) or via
System Settings → Window Decorations.
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


def apply(name: str, *, legacy_plugin: bool = False, border_size: str | None = None) -> None:
    kw = _which("kwriteconfig6", "kwriteconfig5")
    if border_size is not None and border_size not in BORDER_SIZES:
        raise ApplyError(f"unknown border size {border_size!r}; expected one of {BORDER_SIZES}")
    if name.lower() == "breeze":
        _kwrite(kw, "library", "org.kde.breeze")
        _kwrite(kw, "theme", "Breeze")
    else:
        theme_dir = paths.aurorae_themes() / name
        if not theme_dir.is_dir():
            raise ApplyError(f"{name!r} is not installed under {paths.aurorae_themes()}")
        _kwrite(kw, "library", PLUGINS["legacy" if legacy_plugin else "v2"])
        _kwrite(kw, "theme", f"__aurorae__svg__{name}")
        if border_size is None:
            border_size = border_size_for_installed(theme_dir, name)
    if border_size is not None:
        _kwrite(kw, "BorderSize", border_size)
        _kwrite(kw, "BorderSizeAuto", "false")
    qdbus = _which("qdbus6", "qdbus-qt6", "qdbus")
    subprocess.run([qdbus, "org.kde.KWin", "/KWin", "reconfigure"], check=False)
