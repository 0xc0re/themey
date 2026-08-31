"""QML decoration package — structure, referenced-asset closure, snapshots.

Structural invariants: metadata KPlugin Id == slug.plugin_id == the kwinrc
``theme=`` value; every image URL in theme.js resolves to an exported file;
referenced fonts are copied; the runtime ships verbatim from package data.
Syrupy snapshots pin theme.js and metadata.json for all five fixture
themes — the QML backend's equivalent of the SVG snapshot suite.

qmllint is not installed on this machine; the render harness
(``themey render --plugin qml``) is the real QML syntax guard. The qmllint
test runs only where the tool exists.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_NAMES = ("Aliens", "e13", "LiteGnome", "Mac3D", "OPENSTEP")

RUNTIME_DIR = (
    Path(__file__).parent.parent
    / "src" / "themey" / "generate" / "qmldeco" / "runtime"
)


def _build_package(name: str, tmp_path: Path) -> tuple[Path, list[str]]:
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree
    from themey.generate import qmldeco
    from themey.slug import plugin_id

    pkg = tmp_path / plugin_id(name)
    with extract(FIXTURES / f"{name}.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root), name=name,
            display_name=name, scale=2,
        )
        qmldeco.write(theme, pkg)
    return pkg, list(theme.notes)


def _theme_js_data(pkg: Path) -> dict:
    src = (pkg / "contents" / "ui" / "theme.js").read_text()
    m = re.search(r"var theme = (\{.*\});", src, re.S)
    assert m, "theme.js does not carry a `var theme = {...};` payload"
    return json.loads(m.group(1))


@pytest.fixture(params=FIXTURE_NAMES)
def fixture_pkg(request, tmp_path):
    name = request.param
    if not (FIXTURES / f"{name}.etheme").exists():
        pytest.skip(f"{name}.etheme not available")
    pkg, notes = _build_package(name, tmp_path)
    return name, pkg, notes


def test_package_tree_and_asset_closure(fixture_pkg):
    name, pkg, _notes = fixture_pkg
    from themey.slug import plugin_id

    meta = json.loads((pkg / "metadata.json").read_text())
    assert meta["KPackageStructure"] == "KWin/Decoration"
    assert meta["KPlugin"]["Id"] == plugin_id(name) == pkg.name

    ui = pkg / "contents" / "ui"
    for fname in ("main.qml", "ThemeyPart.qml", "ThemeyButton.qml",
                  "resolver.js", "theme.js"):
        assert (ui / fname).is_file(), f"{name}: missing {fname}"
    # Runtime ships verbatim.
    for fname in ("main.qml", "ThemeyPart.qml", "ThemeyButton.qml", "resolver.js"):
        assert (ui / fname).read_text() == (RUNTIME_DIR / fname).read_text()

    data = _theme_js_data(pkg)
    assert data["parts"], f"{name}: no parts emitted"
    for part in data["parts"]:
        if part["images"] is None:
            continue
        for slot, url in part["images"].items():
            assert url.startswith("../images/"), (name, part["id"], slot, url)
            target = ui / url
            assert target.resolve().is_file(), (
                f"{name}: {part['id']}.{slot} → {url} not exported"
            )
    for font in data["fonts"]:
        assert (ui / font["source"]).resolve().is_file(), (
            f"{name}: font {font['source']} not copied"
        )


def test_images_are_upscaled(fixture_pkg):
    """Exported art is NEAREST-upscaled: dimensions = source x scale."""
    from PIL import Image

    name, pkg, _notes = fixture_pkg
    data = _theme_js_data(pkg)
    assert data["scale"] == 2
    images = sorted((pkg / "contents" / "images").glob("*.png"))
    assert images, f"{name}: no images exported"
    for img_path in images:
        with Image.open(img_path) as im:
            assert im.width % 2 == 0 and im.height % 2 == 0, img_path


def test_e13_package_specifics(tmp_path):
    if not (FIXTURES / "e13.etheme").exists():
        pytest.skip("e13.etheme not available")
    pkg, notes = _build_package("e13", tmp_path)
    data = _theme_js_data(pkg)

    assert data["borders"] == {"left": 80, "right": 12, "top": 92, "bottom": 12}
    assert (pkg / "contents" / "fonts" / "ariali.ttf").is_file()
    assert data["fonts"][0]["family"] == "Arial"
    assert data["fonts"][0]["italic"] is True

    by_id = {p["id"]: p for p in data["parts"]}
    assert by_id["BUTTON_KILL"]["button"] == "close"
    assert by_id["BUTTON_ICONIFY"]["button"] == "minimize"
    assert by_id["BUTTON_SHADE"]["button"] == "shade"
    assert by_id["BUTTON_STICK"]["button"] == "onAllDesktops"
    assert by_id["FIN"]["button"] is None          # ACTION_MOVE → chrome
    assert by_id["WIN_SIDE_RIGHT"]["button"] is None  # ACTION_RESIZE_H → chrome
    assert by_id["TITLEBAR"]["isTitle"] is True
    assert by_id["TITLEBAR"]["text"]["pixelSize"] == 18  # ariali/9 x scale 2
    assert by_id["TITLEBAR"]["justification"] == 0  # E16 last-wins → flush left
    # FIN's declared __EDGE_SCALING right=129 pins the fin art to the right
    # edge (whole 129px source is the right cap, x2).
    assert by_id["FIN"]["insets"]["right"] == 258

    hidden_notes = [n for n in notes if n.startswith("qmldeco: button")]
    assert len(hidden_notes) == 3  # iconify/shade/stick hidden when maximized

    # Toggle buttons (stick/shade) get toggled art so the pressed-in state
    # is visible: e13 declares __NORMAL_STICKY, so the chain's first member
    # wins.
    stick = by_id["BUTTON_STICK"]["images"]
    assert stick["toggled"] == "../images/button_stick_normal_sticky.png"
    assert (
        stick["toggledActive"]
        == "../images/button_stick_normal_active_sticky.png"
    )

    # Shade is platform-dependent (KWin offers no shading for Wayland-native
    # windows); the report must warn once per shade button.
    shade_notes = [n for n in notes if n.startswith("qmldeco: shade")]
    assert len(shade_notes) == 1
    assert "shadeable" in shade_notes[0]


def test_toggled_falls_back_to_clicked_without_sticky_art(tmp_path):
    """A theme with no sticky art shows the clicked art while toggled —
    sticky art pixel-identical to normal would otherwise leave the toggle
    visually silent."""
    from PIL import Image

    from themey.generate.qmldeco.theme_js import _BUTTON_SLOTS, _resolve_images
    from themey.ir import IClassSpec

    normal = tmp_path / "normal.png"
    clicked = tmp_path / "clicked.png"
    Image.new("RGBA", (4, 4)).save(normal)
    Image.new("RGBA", (4, 4)).save(clicked)
    ic = IClassSpec(
        name="BTN",
        edge_scaling=(0, 0, 0, 0),
        normal=normal,
        normal_active=None,
        hilited=None,
        hilited_active=None,
        clicked=clicked,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )
    images = _resolve_images(ic, _BUTTON_SLOTS, {})
    assert images is not None
    assert images["toggled"] == "../images/btn_clicked.png"
    assert images["toggledActive"] == "../images/btn_clicked.png"


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_theme_js_snapshot(name, tmp_path, snapshot):
    if not (FIXTURES / f"{name}.etheme").exists():
        pytest.skip(f"{name}.etheme not available")
    pkg, _notes = _build_package(name, tmp_path)
    assert (pkg / "contents" / "ui" / "theme.js").read_text() == snapshot


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_metadata_json_snapshot(name, tmp_path, snapshot):
    if not (FIXTURES / f"{name}.etheme").exists():
        pytest.skip(f"{name}.etheme not available")
    pkg, _notes = _build_package(name, tmp_path)
    assert (pkg / "metadata.json").read_text() == snapshot


@pytest.mark.skipif(shutil.which("qmllint") is None, reason="qmllint not installed")
def test_runtime_passes_qmllint():
    result = subprocess.run(
        ["qmllint", str(RUNTIME_DIR / "main.qml")],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
