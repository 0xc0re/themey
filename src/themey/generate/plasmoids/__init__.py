"""themey's own Plasma applets — the E16 furniture that stock Plasma
cannot be themed into.

Two ``Plasma/Applet`` KPackages, installed under
``$XDG_DATA_HOME/plasma/plasmoids/<id>/`` (``paths.plasmoids()``):

* ``org.themey.pager`` — E16's pager in LIVE mode: live wallpaper minis,
  one PAGER_WIN-framed rect per window, PAGER_SEL on the current desk
  (``runtime/pager/``).
* ``org.themey.deskbutton`` — one end of E16's desktop dragbar (``desk
  next``/``desk prev``; config ``[General] direction=next|prev``)
  (``runtime/deskbutton/``).

Contract — THEME-AGNOSTIC BY DESIGN: neither package carries any art.
Every glyph and frame comes at runtime from the ACTIVE Plasma Style via
KSvg (``widgets/pager`` ``window-``/``window-active-`` prefixes and
``widgets/themey-dragbar.svg``, both written by ``generate/plasmastyle``),
so ONE panel configuration survives re-converts of any theme and the
``apply.py`` panel markers never go stale. The packages are therefore
written identically on every convert and simply overwritten in place
(``install.deploy`` is atomic); ``RUNTIME_VERSION`` is stamped into
``metadata.json`` as ``X-Themey-Runtime`` so ``apply`` can warn when an
installed copy is behind the code (a convert refreshes it).

Layout per package (the ``qmldeco/runtime`` verbatim-copy idiom):

    <pkg>/metadata.json                KPackageStructure "Plasma/Applet",
                                        KPlugin.Id == dir name,
                                        X-Plasma-API-Minimum-Version "6.0",
                                        X-Themey-Runtime == RUNTIME_VERSION
    <pkg>/contents/ui/main.qml         verbatim from package data
    <pkg>/contents/config/main.xml     verbatim from package data

``KPlugin.Id == directory name`` is the KPackage lookup contract (the same
one the QML decoration and the Look-and-Feel bundle obey); the panel
scripting ``addWidget('<id>')`` resolves by that Id.

Plasma5Support: both applets drive D-Bus (desktop switch through KWin's
readwrite ``VirtualDesktopManager.current``; the pager's wallpaper read
through ``org.kde.PlasmaShell.wallpaper``) via the
``org.kde.plasma.plasma5support`` executable ``DataSource`` — deprecated
but shipped on Plasma 6.6, and the only in-stack D-Bus shim applet QML
has. A future Plasma removing it breaks switching/minis, not painting.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

log = logging.getLogger(__name__)

#: Bumped whenever the runtime QML/XML changes in a way apply should notice
#: (``X-Themey-Runtime`` in each package's metadata.json).
RUNTIME_VERSION = 1

PAGER_ID = "org.themey.pager"
DESKBUTTON_ID = "org.themey.deskbutton"
PLASMOID_IDS: tuple[str, ...] = (PAGER_ID, DESKBUTTON_ID)

#: Package id -> (runtime subdir, human name, description, X-Plasma-Provides).
_PACKAGES: dict[str, tuple[str, str, str, tuple[str, ...]]] = {
    PAGER_ID: (
        "pager",
        "E16 Pager (themey)",
        "Enlightenment DR16 pager: live desktop minis with window "
        "rectangles in the active Plasma Style's PAGER_WIN art",
        ("org.kde.plasma.virtualdesktops",),
    ),
    DESKBUTTON_ID: (
        "deskbutton",
        "E16 Desk Button (themey)",
        "One end of the Enlightenment DR16 desktop dragbar: switches to "
        "the next/previous virtual desktop in the active Plasma Style's art",
        (),
    ),
}

#: Files copied verbatim from ``runtime/<subdir>/`` into each package.
RUNTIME_FILES: tuple[str, ...] = (
    "contents/ui/main.qml",
    "contents/config/main.xml",
)


class PlasmoidError(Exception):
    """A plasmoid package could not be written."""


@dataclass(frozen=True)
class PlasmoidPackage:
    """One written applet package."""

    id: str
    dir: Path


def metadata(plugin_id: str) -> dict[str, object]:
    """The ``metadata.json`` document for *plugin_id*."""
    if plugin_id not in _PACKAGES:
        raise PlasmoidError(f"unknown themey plasmoid {plugin_id!r}")
    _subdir, name, description, provides = _PACKAGES[plugin_id]
    meta: dict[str, object] = {
        "KPackageStructure": "Plasma/Applet",
        "KPlugin": {
            "Authors": [{"Name": "themey"}],
            "Category": "Windows and Tasks",
            "Description": description,
            "EnabledByDefault": True,
            "Icon": "org.kde.plasma.pager",
            "Id": plugin_id,
            "License": "MIT",
            "Name": name,
            "Version": f"1.{RUNTIME_VERSION}",
        },
        "X-Plasma-API-Minimum-Version": "6.0",
        "X-Themey-Runtime": RUNTIME_VERSION,
    }
    if provides:
        meta["X-Plasma-Provides"] = list(provides)
    return meta


def write_package(plugin_id: str, out_dir: Path) -> PlasmoidPackage:
    """Write the applet package *plugin_id* under *out_dir*.

    ``out_dir``'s basename MUST equal *plugin_id* (KPackage matches by
    dir name == KPlugin.Id). Any existing content is replaced file by
    file; the caller handles atomic deployment.
    """
    if out_dir.name != plugin_id:
        raise PlasmoidError(
            f"out_dir basename must be {plugin_id!r} (got {out_dir.name!r})"
        )
    subdir = _PACKAGES[plugin_id][0] if plugin_id in _PACKAGES else None
    if subdir is None:
        raise PlasmoidError(f"unknown themey plasmoid {plugin_id!r}")
    runtime_root = resources.files("themey.generate.plasmoids") / "runtime" / subdir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata(plugin_id), indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for rel in RUNTIME_FILES:
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            (runtime_root / rel).read_text(encoding="utf-8"), encoding="utf-8"
        )
    return PlasmoidPackage(id=plugin_id, dir=out_dir)


def write_all(out_root: Path) -> tuple[PlasmoidPackage, ...]:
    """Write every themey applet package as ``out_root/<id>/``."""
    return tuple(write_package(pid, out_root / pid) for pid in PLASMOID_IDS)


def installed_runtime_version(pkg_dir: Path) -> int | None:
    """``X-Themey-Runtime`` from an installed package, or None when the
    package (or the stamp) is absent/unreadable — ``apply`` compares it
    with :data:`RUNTIME_VERSION`."""
    meta = pkg_dir / "metadata.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("X-Themey-Runtime") if isinstance(data, dict) else None
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value
