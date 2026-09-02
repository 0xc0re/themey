"""themey's own applet packages (``generate/plasmoids``) — structure,
KPackage contract, runtime stamp, pipeline placement.

Theme-agnostic packages: metadata is generated, QML/XML copied verbatim.
qmllint runs only where the tool exists (it is not on this machine's
PATH; ``themey render --target pager`` is the real QML guard).
"""
from __future__ import annotations

import json
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
    # Verbatim runtime copy.
    subdir = plasmoids._PACKAGES[plugin_id][0]
    for rel in plasmoids.RUNTIME_FILES:
        assert (pkg.dir / rel).read_text() == (RUNTIME / subdir / rel).read_text()


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


@pytest.mark.skipif(shutil.which("qmllint") is None, reason="qmllint not on PATH")
@pytest.mark.parametrize("subdir", ("pager", "deskbutton"))
def test_qmllint(subdir: str) -> None:
    qml = RUNTIME / subdir / "contents" / "ui" / "main.qml"
    proc = subprocess.run(["qmllint", str(qml)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


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
