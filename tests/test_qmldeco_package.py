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


def _build_package(
    name: str, tmp_path: Path, *, shade_button: str | None = None
) -> tuple[Path, list[str]]:
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
        kwargs = {} if shade_button is None else {"shade_button": shade_button}
        qmldeco.write(theme, pkg, **kwargs)
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
    # Default --shade-button is "maximize": Plasma 6 removed window shading,
    # so e13's dead shade slot becomes the missing maximize/restore button.
    assert by_id["BUTTON_SHADE"]["button"] == "maximizeRestore"
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

    # KWin removed window shading in Plasma 6 (verified against libkwin
    # 6.6.6 symbols, 2026-08-30) — the report must say so, once per shade
    # button, and describe the remap (default --shade-button=maximize).
    shade_notes = [n for n in notes if n.startswith("qmldeco: shade")]
    assert len(shade_notes) == 1
    assert "Plasma 6" in shade_notes[0]
    assert "remapped to maximize" in shade_notes[0]
    assert "--shade-button" in shade_notes[0]


# ---------------------------------------------------------------------------
# --shade-button remap (Phase F / Task 6)

@pytest.mark.parametrize(
    "shade_button,expected_kind",
    [
        ("maximize", "maximizeRestore"),
        ("keepAbove", "keepAbove"),
        ("keepBelow", "keepBelow"),
        ("menu", "menu"),
        ("none", "shade"),
    ],
)
def test_shade_button_remap_kinds(tmp_path, shade_button, expected_kind):
    if not (FIXTURES / "e13.etheme").exists():
        pytest.skip("e13.etheme not available")
    pkg, notes = _build_package("e13", tmp_path, shade_button=shade_button)
    data = _theme_js_data(pkg)
    by_id = {p["id"]: p for p in data["parts"]}
    assert by_id["BUTTON_SHADE"]["button"] == expected_kind

    shade_notes = [n for n in notes if n.startswith("qmldeco: shade button")]
    assert len(shade_notes) == 1
    if shade_button == "none":
        # Today's behavior preserved exactly: the button is inert.
        assert "absorbs clicks" in shade_notes[0]
        assert "remapped" not in shade_notes[0]
    else:
        assert f"remapped to {shade_button}" in shade_notes[0]
        assert "Plasma 6" in shade_notes[0]
        assert "--shade-button" in shade_notes[0]


def test_shade_button_hide_nulls_button_and_images_keeps_indices_stable(tmp_path):
    if not (FIXTURES / "e13.etheme").exists():
        pytest.skip("e13.etheme not available")
    default_pkg, _default_notes = _build_package("e13", tmp_path / "default")
    hide_pkg, hide_notes = _build_package(
        "e13", tmp_path / "hide", shade_button="hide"
    )

    default_data = _theme_js_data(default_pkg)
    hide_data = _theme_js_data(hide_pkg)

    # Part indices/order MUST stay stable — origin chains reference parts
    # by index — so hiding the shade button must not remove or reorder it.
    default_ids = [p["id"] for p in default_data["parts"]]
    hide_ids = [p["id"] for p in hide_data["parts"]]
    assert default_ids == hide_ids

    for d_part, h_part in zip(default_data["parts"], hide_data["parts"], strict=True):
        assert d_part["tlOrigin"] == h_part["tlOrigin"]
        assert d_part["brOrigin"] == h_part["brOrigin"]

    by_id = {p["id"]: p for p in hide_data["parts"]}
    assert by_id["BUTTON_SHADE"]["button"] is None
    assert by_id["BUTTON_SHADE"]["images"] is None

    hide_shade_notes = [n for n in hide_notes if n.startswith("qmldeco: shade button")]
    assert len(hide_shade_notes) == 1
    assert "hidden" in hide_shade_notes[0]
    assert "--shade-button" in hide_shade_notes[0]
    # Hiding must not also emit a "no usable image" note for this part —
    # the blank art is deliberate, not a fidelity gap.
    assert not any(
        "BUTTON_SHADE" in n and "no usable image" in n for n in hide_notes
    )


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


def test_hover_active_falls_back_to_normal_active_hilited(tmp_path):
    """hoverActive resolves __NORMAL_ACTIVE_HILITED when __HILITED_ACTIVE is
    absent (and __HILITED_ACTIVE still wins when both exist — e13's case)."""
    from PIL import Image

    from themey.generate.qmldeco.theme_js import _BUTTON_SLOTS, _resolve_images
    from themey.ir import IClassSpec

    normal = tmp_path / "normal.png"
    nah = tmp_path / "nah.png"
    ha = tmp_path / "ha.png"
    for p in (normal, nah, ha):
        Image.new("RGBA", (4, 4)).save(p)

    def spec(hilited_active):
        return IClassSpec(
            name="BTN",
            edge_scaling=(0, 0, 0, 0),
            normal=normal,
            normal_active=None,
            hilited=None,
            hilited_active=hilited_active,
            clicked=None,
            clicked_active=None,
            normal_sticky=None,
            normal_active_sticky=None,
            normal_active_hilited=nah,
        )

    images = _resolve_images(spec(None), _BUTTON_SLOTS, {})
    assert images is not None
    assert images["hoverActive"] == "../images/btn_normal_active_hilited.png"

    images = _resolve_images(spec(ha), _BUTTON_SLOTS, {})
    assert images is not None
    assert images["hoverActive"] == "../images/btn_hilited_active.png"


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


@pytest.mark.parametrize("mode", ["nearest", "quality"])
def test_exported_image_dims_follow_scale_px_at_fractional_scale(tmp_path, mode):
    """Art dims and BorderImage insets use the SAME rounding (scale_px) —
    mismatched rounding smears the 9-patch caps."""
    from PIL import Image

    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree
    from themey.generate import qmldeco
    from themey.generate.qmldeco.resolver import scale_px
    from themey.generate.qmldeco.theme_js import build_theme_data

    if not (FIXTURES / "e13.etheme").exists():
        pytest.skip("e13.etheme not available")
    pkg = tmp_path / "themey_e13"
    with extract(FIXTURES / "e13.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root), name="e13",
            display_name="e13", scale=1.5,
        )
        _data, manifest, _fonts = build_theme_data(theme)
        sources = {
            relname: Image.open(src).size for relname, src in manifest.items()
        }
        qmldeco.write(theme, pkg, upscale=mode)
    for relname, (sw, sh) in sources.items():
        with Image.open(pkg / "contents" / "images" / relname) as out:
            assert out.size == (scale_px(sw, 1.5), scale_px(sh, 1.5)), relname


def test_slot_insets_follow_per_state_edge_scaling(tmp_path):
    """E16's __EDGE_SCALING is per image state (iclass.c ICLASS_LRTB writes
    is->border on the state last opened): a hover state sliced 6/6/6/6
    must ship 6-px insets while the normal state keeps its 2/2/2/2 —
    one shared inset set would slice the hover art with the wrong caps."""
    from PIL import Image

    from themey.generate.qmldeco.theme_js import _BUTTON_SLOTS, _clamped_insets
    from themey.ir import IClassSpec

    normal = tmp_path / "normal.png"
    hilited = tmp_path / "hilited.png"
    Image.new("RGBA", (20, 20)).save(normal)
    Image.new("RGBA", (20, 20)).save(hilited)
    ic = IClassSpec(
        name="BTN",
        edge_scaling=(6, 6, 6, 6),  # last-wins iclass-wide value
        normal=normal,
        normal_active=None,
        hilited=hilited,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
        edge_by_state={"normal": (2, 2, 2, 2), "hilited": (6, 6, 6, 6)},
    )
    assert _clamped_insets(ic, 2, "normal") == {
        "left": 4, "right": 4, "top": 4, "bottom": 4
    }
    assert _clamped_insets(ic, 2, "hilited") == {
        "left": 12, "right": 12, "top": 12, "bottom": 12
    }
    # pressed has no clicked art → falls back to normal art AND normal's edge
    assert _clamped_insets(ic, 2, "clicked") == _clamped_insets(ic, 2, None)
    assert "pressed" in _BUTTON_SLOTS


def test_theme_js_text_effect_and_colors(tmp_path):
    """Caption effect vocabulary: __DRAWING_EFFECT __EFFECT_OUTLINE renders
    as ``effect: "outline"`` painted in the state's __BACKGROUND_COLOR
    (E16 text.c TsTextDraw draws the effect in bg_col); the active state
    carries its own colour; undeclared bg is E16's calloc'ed black."""
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree
    from themey.generate.qmldeco.theme_js import build_theme_data
    from themey.ir import TClassSpec

    with extract(FIXTURES / "e13.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root), name="e13",
            display_name="e13", scale=2,
        )
        title = next(p for p in theme.border.parts if "__FLAG_TITLE" in p.flags)
        name = title.tclass_name or "TEXT1"
        old = theme.tclasses[name]
        theme.tclasses[name] = TClassSpec(
            name=old.name, fg_normal=(1, 2, 3), fg_active=(4, 5, 6),
            effect="__EFFECT_OUTLINE", bg_normal=(10, 20, 30), bg_active=None,
            justification_q10=1024, font_normal=old.font_normal,
            font_active=old.font_active, font_alias=old.font_alias,
        )
        data, _manifest, _fonts = build_theme_data(theme)
    part = next(p for p in data["parts"] if p["isTitle"])
    assert part["justification"] == 1024
    assert part["text"]["effect"] == "outline"
    assert part["text"]["effectColorNormal"] == "#0a141e"
    assert part["text"]["effectColorActive"] == "#0a141e"  # falls back to normal
    assert part["text"]["colorActive"] == "#040506"
    assert "shadow" not in part["text"]


def test_theme_js_keep_on_top_and_slot_tile(tmp_path):
    """Tier-2 geometry fields: ``keepOnTop`` (E16 __KEEP_ON_TOP __OFF parts
    stack under every on-top part) and ``slotTile`` (E16 __FILLRULE per
    image state: null | "h" | "v" | "both")."""
    import dataclasses

    from PIL import Image

    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree
    from themey.generate.qmldeco.theme_js import build_theme_data

    with extract(FIXTURES / "e13.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root), name="e13",
            display_name="e13", scale=2,
        )
        part0 = theme.border.parts[0]
        ic = theme.iclasses[part0.iclass_name]
        Image.new("RGBA", (8, 8)).save(tmp_path / "tile.png")
        theme.iclasses[part0.iclass_name] = dataclasses.replace(
            ic, hilited=tmp_path / "tile.png",
            fill_by_state={"normal": "tile", "hilited": "tile-h"},
        )
        parts = list(theme.border.parts)
        parts[0] = dataclasses.replace(part0, keep_on_top=False)
        parts[1] = dataclasses.replace(parts[1], keep_on_top=True)
        theme = dataclasses.replace(
            theme, border=dataclasses.replace(theme.border, parts=tuple(parts))
        )
        data, _manifest, _fonts = build_theme_data(theme)
    assert data["parts"][0]["keepOnTop"] is False
    assert data["parts"][1]["keepOnTop"] is True
    tiles = data["parts"][0]["slotTile"]
    assert tiles["normal"] == "both"
    assert tiles["hover"] == "h"
    assert data["parts"][1]["slotTile"]["normal"] is None
