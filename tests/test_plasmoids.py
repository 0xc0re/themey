"""themey's own applet packages (``generate/plasmoids``) — structure,
KPackage contract, runtime stamp, pipeline placement.

Theme-agnostic packages: metadata is generated, QML/XML copied verbatim.
``org.themey.dock`` is the one vendored package (a GPL-2.0+ fork of a
third-party macOS-style dock); its tests pin the provenance files and the
themey-side fork points as well as the KPackage contract.
qmllint runs only where the tool exists (it is not on this machine's
PATH; ``themey render --target pager`` is the real QML guard).
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from themey import paths
from themey.generate import plasmoids
from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = (
    Path(__file__).resolve().parents[1]
    / "src" / "themey" / "generate" / "plasmoids" / "runtime"
)


@pytest.mark.parametrize("plugin_id", plasmoids.PLASMOID_IDS)
def test_package_layout_and_metadata(tmp_path: Path, plugin_id: str) -> None:
    pkg = plasmoids.write_package(plugin_id, tmp_path / plugin_id)
    assert pkg.id == plugin_id and pkg.dir.name == plugin_id
    meta = json.loads((pkg.dir / "metadata.json").read_text())
    assert meta["KPackageStructure"] == "Plasma/Applet"
    assert meta["KPlugin"]["Id"] == plugin_id == pkg.dir.name
    assert meta["X-Plasma-API-Minimum-Version"] == "6.0"
    assert meta["X-Themey-Runtime"] == plasmoids.RUNTIME_VERSION
    qml = pkg.dir / "contents" / "ui" / "main.qml"
    xml = pkg.dir / "contents" / "config" / "main.xml"
    assert qml.is_file() and xml.is_file()
    ET.parse(xml)  # well-formed kcfg
    assert "import org.kde.plasma.plasmoid" in qml.read_text()
    # Verbatim runtime copy — every file under runtime/<subdir>/.
    subdir = plasmoids._PACKAGES[plugin_id].subdir
    rels = plasmoids.runtime_files(plugin_id)
    assert "contents/ui/main.qml" in rels and "contents/config/main.xml" in rels
    for rel in rels:
        assert (pkg.dir / rel).read_bytes() == (RUNTIME / subdir / rel).read_bytes()


def test_pager_provides_virtualdesktops_and_config_defaults(tmp_path: Path) -> None:
    pkg = plasmoids.write_package(plasmoids.PAGER_ID, tmp_path / plasmoids.PAGER_ID)
    meta = json.loads((pkg.dir / "metadata.json").read_text())
    assert "org.kde.plasma.virtualdesktops" in meta["X-Plasma-Provides"]
    root = ET.parse(pkg.dir / "contents" / "config" / "main.xml").getroot()
    ns = {"k": "http://www.kde.org/standards/kcfg/1.0"}
    entries = {
        e.get("name"): (e.get("type"), (e.findtext("k:default", namespaces=ns) or ""))
        for e in root.iterfind(".//k:entry", ns)
    }
    assert entries == {
        "showOnlyCurrentScreen": ("Bool", "true"),
        "showWindowIcons": ("Bool", "false"),
        "showWallpaper": ("Bool", "true"),
        "wallpaperPollSeconds": ("Int", "20"),
    }


def test_deskbutton_config_direction(tmp_path: Path) -> None:
    pkg = plasmoids.write_package(
        plasmoids.DESKBUTTON_ID, tmp_path / plasmoids.DESKBUTTON_ID
    )
    root = ET.parse(pkg.dir / "contents" / "config" / "main.xml").getroot()
    ns = {"k": "http://www.kde.org/standards/kcfg/1.0"}
    entry = root.find(".//k:entry[@name='direction']", ns)
    assert entry is not None and entry.get("type") == "String"
    assert entry.findtext("k:default", namespaces=ns) == "next"
    qml = (pkg.dir / "contents" / "ui" / "main.qml").read_text()
    # Theme-agnostic art path + the arrows fallback.
    assert "widgets/themey-dragbar" in qml and "widgets/arrows" in qml


def test_pager_qml_reads_style_art_and_runtime_wallpaper() -> None:
    qml = (RUNTIME / "pager" / "contents" / "ui" / "main.qml").read_text()
    assert '"widgets/pager"' in qml
    assert '"window-active", "window"' in qml
    assert "org.kde.PlasmaShell.wallpaper" in qml
    assert "VirtualDesktopManager current" in qml
    assert "requestActivate" in qml
    assert "filterMinimized: true" in qml


DOCK_RUNTIME = RUNTIME / "dock"

#: Upstream commit the dock package was vendored from.
DOCK_UPSTREAM_COMMIT = "8230092"
DOCK_UPSTREAM_URL = "https://github.com/GridyushkoF/MacOS-Like-dock-for-KDE-Plasma"


def test_dock_package_metadata_and_provenance(tmp_path: Path) -> None:
    """The vendored dock ships its own licence and provenance; the two
    themey-authored applets stay MIT."""
    pkg = plasmoids.write_package(plasmoids.DOCK_ID, tmp_path / plasmoids.DOCK_ID)
    meta = json.loads((pkg.dir / "metadata.json").read_text())
    assert meta["KPlugin"]["License"] == "GPL-2.0+"
    assert meta["KPlugin"]["Icon"] == "preferences-system-windows"
    assert meta["X-Plasma-Provides"] == ["org.kde.plasma.multitasking"]
    authors = [a["Name"] for a in meta["KPlugin"]["Authors"]]
    assert "themey" in authors
    assert any("GridyushkoF" in a for a in authors)
    assert any("KDE" in a for a in authors)

    # The two themey-authored applets are unaffected.
    for pid in (plasmoids.PAGER_ID, plasmoids.DESKBUTTON_ID):
        other = plasmoids.write_package(pid, tmp_path / pid)
        other_meta = json.loads((other.dir / "metadata.json").read_text())
        assert other_meta["KPlugin"]["License"] == "MIT"

    # Provenance travels into the installed package.
    copying = (pkg.dir / "COPYING").read_text()
    assert "GNU GENERAL PUBLIC LICENSE" in copying and "Version 2" in copying
    readme = (pkg.dir / "README.md").read_text()
    assert DOCK_UPSTREAM_URL in readme
    assert DOCK_UPSTREAM_COMMIT in readme
    assert "plasma-desktop" in readme


def test_dock_carries_no_upstream_plugin_id() -> None:
    """The fork is ``org.themey.dock`` everywhere — no stale upstream id
    can shadow it in a KPackage lookup. (README.md names it as prose.)"""
    files = [
        p for p in sorted(DOCK_RUNTIME.rglob("*"))
        if p.suffix in (".qml", ".js", ".xml")
    ]
    assert len(files) > 10
    for path in files:
        assert "icontasks2" not in path.read_text(encoding="utf-8"), path


def test_dock_config_has_task_hover_effect() -> None:
    """``taskHoverEffect`` is the key apply writes from the Plasma Style's
    ``X-Themey-TasksHover``."""
    root = ET.parse(DOCK_RUNTIME / "contents" / "config" / "main.xml").getroot()
    ns = {"k": "http://www.kde.org/standards/kcfg/1.0"}
    entry = root.find(".//k:entry[@name='taskHoverEffect']", ns)
    assert entry is not None and entry.get("type") == "Bool"
    assert entry.findtext("k:default", namespaces=ns) == "true"


def test_dock_task_paints_the_style_tasks_art() -> None:
    qml = (DOCK_RUNTIME / "contents" / "ui" / "Task.qml").read_text()
    assert 'imagePath: "widgets/tasks"' in qml
    assert "taskPrefixHovered" in qml
    assert "fixedMargins" in qml
    # Upstream's basePrefix precedence, all five states.
    for prefix in ('""', '"attention"', '"minimized"', '"focus"', '"normal"'):
        assert f"basePrefix: {prefix}" in qml
    # The per-task tooltip is back on.
    assert "PlasmaCore.ToolTipArea" in qml


def test_dock_tasklist_publishes_delegate_geometry() -> None:
    """KWin's minimize animations need each task's on-screen rect; the
    fork had dropped the step with the private C++ backend."""
    qml = (DOCK_RUNTIME / "contents" / "ui" / "TaskList.qml").read_text()
    assert "requestPublishDelegateGeometry" in qml
    assert "mapToGlobal" in qml
    assert 'prefix: TaskTools.taskPrefix("normal"' in qml


def test_dock_tasklist_budgets_zoom_headroom() -> None:
    """A cell equal to the panel thickness is clipped the moment it is
    hovered: Task scales the icon by up to maxZoomFactor."""
    qml = (DOCK_RUNTIME / "contents" / "ui" / "TaskList.qml").read_text()
    assert "Math.round(panelThickness / Math.max(1, zoomFactor))" in qml
    # The no-art path keeps the fork's own formula.
    assert "panelThickness - Kirigami.Units.smallSpacing * 4" in qml


def test_dock_task_tools_prefix_chain() -> None:
    """themey ships no ``south-`` set, so the unprefixed set IS the
    bottom-panel one (``_TASKS_FOCUS_EDGES``)."""
    js = (DOCK_RUNTIME / "contents" / "ui" / "code" / "TaskTools.js").read_text()
    assert '"south-" + prefix' in js
    assert '"north-" + prefix' in js
    assert '"west-" + prefix' in js
    assert '"east-" + prefix' in js
    assert "function taskPrefixHovered" in js


def test_dock_main_probes_the_style_art_and_is_quiet() -> None:
    qml = (DOCK_RUNTIME / "contents" / "ui" / "main.qml").read_text()
    assert 'imagePath: "widgets/tasks"' in qml
    assert 'hasElement("center")' in qml
    assert "onRepaintNeeded" in qml
    assert "Plasmoid.configuration.taskHoverEffect" in qml


def test_dock_qml_has_no_debug_logging() -> None:
    sources = [p for p in sorted(DOCK_RUNTIME.rglob("*")) if p.suffix in (".qml", ".js")]
    assert len(sources) > 10
    for path in sources:
        assert "console.log" not in path.read_text(encoding="utf-8"), path


def test_dock_files_carry_spdx_headers() -> None:
    """Every vendored source keeps its upstream SPDX header; every file
    themey touched additionally names themey."""
    touched = {
        "contents/ui/main.qml",
        "contents/ui/Task.qml",
        "contents/ui/TaskList.qml",
        "contents/ui/code/TaskTools.js",
        "contents/config/main.xml",
    }
    for rel in touched:
        text = (DOCK_RUNTIME / rel).read_text()
        assert "SPDX-License-Identifier: GPL-2.0-or-later" in text, rel
        assert "SPDX-FileCopyrightText: 2026 themey contributors" in text, rel


def test_runtime_files_walks_the_whole_package() -> None:
    rels = plasmoids.runtime_files(plasmoids.DOCK_ID)
    assert rels == tuple(sorted(rels))
    assert "COPYING" in rels and "README.md" in rels
    assert "contents/config/config.qml" in rels
    assert "contents/ui/code/TaskTools.js" in rels
    # Every file on disk is shipped.
    on_disk = {
        str(p.relative_to(DOCK_RUNTIME).as_posix())
        for p in DOCK_RUNTIME.rglob("*")
        if p.is_file()
    }
    assert set(rels) == on_disk
    with pytest.raises(plasmoids.PlasmoidError, match="unknown"):
        plasmoids.runtime_files("org.themey.nope")


def test_runtime_files_requires_the_kpackage_entry_points() -> None:
    """A package missing main.qml/main.xml would install and silently
    fail to load."""
    with pytest.raises(plasmoids.PlasmoidError, match=re.escape("contents/ui/main.qml")):
        plasmoids._require_entry_points("org.themey.x", ("contents/config/main.xml",))
    with pytest.raises(plasmoids.PlasmoidError, match=re.escape("contents/config/main.xml")):
        plasmoids._require_entry_points("org.themey.x", ("contents/ui/main.qml",))


def test_write_package_rejects_mismatched_dir(tmp_path: Path) -> None:
    with pytest.raises(plasmoids.PlasmoidError, match="basename"):
        plasmoids.write_package(plasmoids.PAGER_ID, tmp_path / "wrong")
    with pytest.raises(plasmoids.PlasmoidError, match="unknown"):
        plasmoids.write_package("org.themey.nope", tmp_path / "org.themey.nope")


def test_installed_runtime_version(tmp_path: Path) -> None:
    pkg = plasmoids.write_package(plasmoids.PAGER_ID, tmp_path / plasmoids.PAGER_ID)
    assert plasmoids.installed_runtime_version(pkg.dir) == plasmoids.RUNTIME_VERSION
    assert plasmoids.installed_runtime_version(tmp_path / "absent") is None
    (pkg.dir / "metadata.json").write_text('{"X-Themey-Runtime": "1"}')
    assert plasmoids.installed_runtime_version(pkg.dir) is None


def test_write_all_covers_every_id(tmp_path: Path) -> None:
    pkgs = plasmoids.write_all(tmp_path)
    assert tuple(p.id for p in pkgs) == plasmoids.PLASMOID_IDS
    assert all((p.dir / "metadata.json").is_file() for p in pkgs)


QML_FILES = tuple(sorted(RUNTIME.glob("*/contents/**/*.qml")))


@pytest.mark.skipif(shutil.which("qmllint") is None, reason="qmllint not on PATH")
@pytest.mark.parametrize(
    "qml", QML_FILES, ids=[str(p.relative_to(RUNTIME)) for p in QML_FILES]
)
def test_qmllint(qml: Path) -> None:
    """Every shipped QML file parses.

    The vendored dock is third-party QML and trips qmllint's style
    warnings (unqualified ids above all), so only ``critical`` messages
    fail the test — those are the ones that mean the file will not load.
    """
    proc = subprocess.run(
        ["qmllint", "--json", "-", str(qml)], capture_output=True, text=True
    )
    try:
        report = json.loads(proc.stdout)
    except ValueError:
        assert proc.returncode == 0, proc.stderr or proc.stdout
        return
    critical = [
        w
        for f in report.get("files", [])
        for w in f.get("warnings", [])
        if w.get("type") == "critical"
    ]
    assert not critical, critical


# --- pipeline placement ---------------------------------------------------


def test_convert_installs_plasmoids_under_xdg(fake_home: Path) -> None:
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")
    expected = tuple(paths.plasmoids() / pid for pid in plasmoids.PLASMOID_IDS)
    assert result.plasmoid_dirs == expected
    for d in expected:
        assert (d / "metadata.json").is_file()
        assert (d / "contents" / "ui" / "main.qml").is_file()
    # Re-convert overwrites in place (theme-agnostic, atomic deploy).
    result2 = convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")
    assert result2.plasmoid_dirs == expected
    assert not list(paths.plasmoids().glob("*.themey-old"))


def test_convert_output_dir_writes_plasmoids_subdir(fake_home: Path, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="qml", output_dir=out)
    expected = tuple(out / "plasmoids" / pid for pid in plasmoids.PLASMOID_IDS)
    assert result.plasmoid_dirs == expected
    assert all((d / "metadata.json").is_file() for d in expected)
    assert not (fake_home / ".local" / "share" / "plasma" / "plasmoids").exists()
