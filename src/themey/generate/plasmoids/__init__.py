"""themey's own Plasma applets — the E16 furniture that stock Plasma
cannot be themed into.

Three ``Plasma/Applet`` KPackages, installed under
``$XDG_DATA_HOME/plasma/plasmoids/<id>/`` (``paths.plasmoids()``):

* ``org.themey.pager`` — E16's pager in LIVE mode: live wallpaper minis,
  one PAGER_WIN-framed rect per window, PAGER_SEL on the current desk
  (``runtime/pager/``).
* ``org.themey.deskbutton`` — one end of E16's desktop dragbar (``desk
  next``/``desk prev``; config ``[General] direction=next|prev``)
  (``runtime/deskbutton/``).
* ``org.themey.dock`` — the icons-only dock (``runtime/dock/``). The one
  VENDORED package: a fork of a third-party macOS-style dock, itself a
  pure-QML fork of KDE's Icons-Only Task Manager, so it is GPL-2.0+ where
  the other two are MIT. Provenance, the licence text and the list of
  themey's changes live in ``runtime/dock/README.md`` and
  ``runtime/dock/COPYING``, both of which travel into the installed
  package.

Contract — THEME-AGNOSTIC BY DESIGN: no package carries any art.
Every glyph and frame comes at runtime from the ACTIVE Plasma Style via
KSvg (``widgets/pager`` ``window-``/``window-active-`` prefixes,
``widgets/themey-dragbar.svg`` and the dock's ``widgets/tasks`` plate, all
written by ``generate/plasmastyle``),
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
    <pkg>/<everything else>            verbatim from ``runtime/<subdir>/``

``metadata.json`` is the ONLY generated file; every other file under
``runtime/<subdir>/`` is copied through byte for byte, whatever its
depth (``runtime_files``). ``contents/ui/main.qml`` and
``contents/config/main.xml`` are the KPackage entry points and their
absence is a :class:`PlasmoidError`, not a package that installs and then
silently fails to load.

``KPlugin.Id == directory name`` is the KPackage lookup contract (the same
one the QML decoration and the Look-and-Feel bundle obey); the panel
scripting ``addWidget('<id>')`` resolves by that Id.

Plasma5Support: the pager and the desk button drive D-Bus (desktop switch
through KWin's readwrite ``VirtualDesktopManager.current``; the pager's
wallpaper read through ``org.kde.PlasmaShell.wallpaper``) via the
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
RUNTIME_VERSION = 2

PAGER_ID = "org.themey.pager"
DESKBUTTON_ID = "org.themey.deskbutton"
DOCK_ID = "org.themey.dock"
PLASMOID_IDS: tuple[str, ...] = (PAGER_ID, DESKBUTTON_ID, DOCK_ID)

#: The KPackage entry points. A package missing either installs cleanly
#: and then does nothing, which is the failure mode worth a hard error.
_ENTRY_POINTS: tuple[str, ...] = (
    "contents/ui/main.qml",
    "contents/config/main.xml",
)


@dataclass(frozen=True)
class _PackageSpec:
    """Everything ``metadata.json`` needs, plus where the files live."""

    subdir: str
    name: str
    description: str
    provides: tuple[str, ...]
    license: str
    icon: str
    authors: tuple[str, ...]


_PACKAGES: dict[str, _PackageSpec] = {
    PAGER_ID: _PackageSpec(
        subdir="pager",
        name="E16 Pager (themey)",
        description=(
            "Enlightenment DR16 pager: live desktop minis with window "
            "rectangles in the active Plasma Style's PAGER_WIN art"
        ),
        provides=("org.kde.plasma.virtualdesktops",),
        license="MIT",
        icon="org.kde.plasma.pager",
        authors=("themey",),
    ),
    DESKBUTTON_ID: _PackageSpec(
        subdir="deskbutton",
        name="E16 Desk Button (themey)",
        description=(
            "One end of the Enlightenment DR16 desktop dragbar: switches to "
            "the next/previous virtual desktop in the active Plasma Style's art"
        ),
        provides=(),
        license="MIT",
        icon="org.kde.plasma.pager",
        authors=("themey",),
    ),
    # VENDORED — see runtime/dock/README.md for the provenance and the
    # full list of themey's changes. GPL-2.0+ is upstream's licence and
    # travels with the fork; COPYING ships inside the package.
    DOCK_ID: _PackageSpec(
        subdir="dock",
        name="E16 Dock (themey)",
        description=(
            "Icons-only dock with macOS-style zoom, painted from the active "
            "Plasma Style's task art (E16's iconbox buttons)"
        ),
        provides=("org.kde.plasma.multitasking",),
        license="GPL-2.0+",
        icon="preferences-system-windows",
        authors=(
            "GridyushkoF (Icons-Only Task Manager 2)",
            "KDE Plasma Task Manager authors",
            "themey",
        ),
    ),
}


class PlasmoidError(Exception):
    """A plasmoid package could not be written."""


def _require_entry_points(plugin_id: str, rels: tuple[str, ...]) -> None:
    """Raise unless *rels* has both KPackage entry points."""
    missing = [rel for rel in _ENTRY_POINTS if rel not in rels]
    if missing:
        raise PlasmoidError(
            f"{plugin_id}: runtime package is missing {', '.join(missing)}"
        )


def runtime_files(plugin_id: str) -> tuple[str, ...]:
    """Every file under ``runtime/<subdir>/``, as sorted POSIX-relative
    paths.

    A recursive walk rather than a fixed list: the vendored dock is 18
    files across four directories, and a hand-maintained manifest that
    silently drops one would ship a package that installs and then fails
    to load. ``importlib.resources`` so the walk works from a wheel too.
    """
    if plugin_id not in _PACKAGES:
        raise PlasmoidError(f"unknown themey plasmoid {plugin_id!r}")
    root = resources.files("themey.generate.plasmoids") / "runtime"
    root = root / _PACKAGES[plugin_id].subdir

    def walk(node, prefix: str) -> list[str]:
        found: list[str] = []
        for child in node.iterdir():
            rel = f"{prefix}{child.name}"
            if child.is_dir():
                found.extend(walk(child, f"{rel}/"))
            else:
                found.append(rel)
        return found

    rels = tuple(sorted(walk(root, "")))
    _require_entry_points(plugin_id, rels)
    return rels


@dataclass(frozen=True)
class PlasmoidPackage:
    """One written applet package."""

    id: str
    dir: Path


def metadata(plugin_id: str) -> dict[str, object]:
    """The ``metadata.json`` document for *plugin_id*."""
    if plugin_id not in _PACKAGES:
        raise PlasmoidError(f"unknown themey plasmoid {plugin_id!r}")
    spec = _PACKAGES[plugin_id]
    meta: dict[str, object] = {
        "KPackageStructure": "Plasma/Applet",
        "KPlugin": {
            "Authors": [{"Name": author} for author in spec.authors],
            "Category": "Windows and Tasks",
            "Description": spec.description,
            "EnabledByDefault": True,
            "Icon": spec.icon,
            "Id": plugin_id,
            "License": spec.license,
            "Name": spec.name,
            "Version": f"1.{RUNTIME_VERSION}",
        },
        "X-Plasma-API-Minimum-Version": "6.0",
        "X-Themey-Runtime": RUNTIME_VERSION,
    }
    if spec.provides:
        meta["X-Plasma-Provides"] = list(spec.provides)
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
    rels = runtime_files(plugin_id)
    runtime_root = (
        resources.files("themey.generate.plasmoids")
        / "runtime"
        / _PACKAGES[plugin_id].subdir
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata(plugin_id), indent=4, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for rel in rels:
        target = out_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Bytes, not text: the vendored dock carries a licence file and
        # translated labels, and re-encoding them is no business of ours.
        source = runtime_root
        for part in rel.split("/"):
            source = source / part
        target.write_bytes(source.read_bytes())
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
