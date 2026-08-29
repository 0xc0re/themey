"""Point the live KWin at an installed Aurorae theme (``themey apply``).

Writes ``kwinrc`` ``[org.kde.kdecoration2]`` via ``kwriteconfig6`` and asks
KWin to reconfigure over D-Bus. ``--legacy-plugin`` selects
``org.kde.kwin.aurorae`` (honours the theme's ``Border*`` verbatim) instead
of Plasma's default ``org.kde.kwin.aurorae.v2`` (clamps sides to the
System Settings "Border size" bracket).

Revert with ``themey apply Breeze`` (which selects ``org.kde.breeze``) or via
System Settings → Window Decorations.
"""
from __future__ import annotations

import shutil
import subprocess

from . import paths
from .render import BORDER_SIZES, PLUGINS

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


def apply(name: str, *, legacy_plugin: bool = False, border_size: str | None = None) -> None:
    kw = _which("kwriteconfig6", "kwriteconfig5")
    if border_size is not None and border_size not in BORDER_SIZES:
        raise ApplyError(f"unknown border size {border_size!r}; expected one of {BORDER_SIZES}")
    if name.lower() == "breeze":
        _kwrite(kw, "library", "org.kde.breeze")
        _kwrite(kw, "theme", "Breeze")
    else:
        if not (paths.aurorae_themes() / name).is_dir():
            raise ApplyError(f"{name!r} is not installed under {paths.aurorae_themes()}")
        _kwrite(kw, "library", PLUGINS["legacy" if legacy_plugin else "v2"])
        _kwrite(kw, "theme", f"__aurorae__svg__{name}")
    if border_size is not None:
        _kwrite(kw, "BorderSize", border_size)
        _kwrite(kw, "BorderSizeAuto", "false")
    qdbus = _which("qdbus6", "qdbus-qt6", "qdbus")
    subprocess.run([qdbus, "org.kde.KWin", "/KWin", "reconfigure"], check=False)
