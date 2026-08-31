"""SVG↔rc invariant: strip thicknesses must agree across decoration.svg and <name>rc.

This is the load-bearing single invariant that catches the entire bug class
of "decoration paints into wrong area" — the bug we fixed in May 2026 where
``decoration_svg.py`` derived strip dims from ``edge_scaling`` (the 9-slice
inset, 3-5 px) while ``aurorae_rc.py`` derived ``BorderTop/TitleHeight`` from
the source image dimensions (12-32 px), causing KWin to paint a sliver of
artwork into a much taller reserved band.

The contract:

    decoration-top    bbox.height == BorderTop
    decoration-left   bbox.width  == BorderLeft
    decoration-right  bbox.width  == BorderRight
    decoration-bottom bbox.height == BorderBottom

    BorderTop == TitleEdgeTop + TitleHeight + TitleEdgeBottom
    (title bar lives inside the top zone, not filling it)

If this test passes for a corpus of wildly different themes (Aliens, e13,
OPENSTEP, Mac3D, LiteGnome — each with different border styles and sizes),
the geometric contract between the two writers holds.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

import pytest

from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"
SVG_NS = "{http://www.w3.org/2000/svg}"

THEMES = [
    "Aliens",
    "e13",
    "OPENSTEP",
    "Mac3D",
    "LiteGnome",
]


def _region_image_attrs(svg_path: Path, region_id: str) -> tuple[float, float]:
    """Return (width, height) of the first <image> inside <g id=region_id>."""
    root = ET.parse(svg_path).getroot()
    for g in root.iter(f"{SVG_NS}g"):
        if g.get("id") == region_id:
            img = g.find(f"{SVG_NS}image")
            assert img is not None, f"<image> missing under {region_id}"
            return float(img.get("width", "0")), float(img.get("height", "0"))
    raise AssertionError(f"no <g id='{region_id}'> in {svg_path}")


def _hint_width(svg_path: Path, hint_id: str) -> int:
    root = ET.parse(svg_path).getroot()
    for r in root.iter(f"{SVG_NS}rect"):
        if r.get("id") == hint_id:
            return int(r.get("width", "0"))
    raise AssertionError(f"no <rect id='{hint_id}'> in {svg_path}")


def _read_layout(rc_path: Path) -> dict[str, int]:
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc_path)
    return {k: int(v) for k, v in cp["Layout"].items() if v.lstrip("-").isdigit()}


@pytest.mark.parametrize("theme_name", THEMES)
def test_svg_strip_dims_match_rc_borders(theme_name: str, fake_home: Path) -> None:
    """Top/bottom strips equal the rc BorderTop/BorderBottom.

    Left/right strips are frame COLUMNS: they equal the hint-left/right-
    margin width and are >= the rc BorderLeft/Right. FrameSvg paints the
    frame at the hint width under the client, so a column wider than the
    (KWin-clamped) border is how folded corner art escapes the clamp.
    """
    result = convert(FIXTURES / f"{theme_name}.etheme", scale=2, backend="svg")
    svg = result.installed_dir / "decoration.svg"
    rc = result.installed_dir / f"{theme_name}rc"

    L = _read_layout(rc)
    _, top_h = _region_image_attrs(svg, "decoration-top")
    left_w, _ = _region_image_attrs(svg, "decoration-left")
    right_w, _ = _region_image_attrs(svg, "decoration-right")
    _, bot_h = _region_image_attrs(svg, "decoration-bottom")

    assert int(top_h) == L["BorderTop"], (
        f"{theme_name}: top strip h={top_h} BorderTop={L['BorderTop']}"
    )
    assert int(left_w) == _hint_width(svg, "decoration-hint-left-margin")
    assert int(left_w) >= L["BorderLeft"], (
        f"{theme_name}: left strip w={left_w} BorderLeft={L['BorderLeft']}"
    )
    assert int(right_w) == _hint_width(svg, "decoration-hint-right-margin")
    assert int(right_w) >= L["BorderRight"], (
        f"{theme_name}: right strip w={right_w} BorderRight={L['BorderRight']}"
    )
    assert int(bot_h) == L["BorderBottom"], (
        f"{theme_name}: bottom strip h={bot_h} BorderBottom={L['BorderBottom']}"
    )
    # Title bar lives inside the top zone (or matches it exactly when the
    # theme has no explicit TITLE_BAR_HORIZONTAL part).
    title_sum = L["TitleEdgeTop"] + L["TitleHeight"] + L["TitleEdgeBottom"]
    assert title_sum == L["BorderTop"], (
        f"{theme_name}: TitleEdgeTop({L['TitleEdgeTop']}) + "
        f"TitleHeight({L['TitleHeight']}) + "
        f"TitleEdgeBottom({L['TitleEdgeBottom']}) != BorderTop({L['BorderTop']})"
    )


@pytest.mark.parametrize("theme_name", THEMES)
def test_corner_dims_match_adjacent_strips(theme_name: str, fake_home: Path) -> None:
    """Corners must match adjacent strip thicknesses (FrameSvg 9-patch contract).

    Corners share the width of their frame column (== the left/right strip
    width, >= the rc BorderLeft/Right) and the height of the adjacent
    top/bottom strip (== BorderTop/BorderBottom).
    """
    result = convert(FIXTURES / f"{theme_name}.etheme", scale=2, backend="svg")
    svg = result.installed_dir / "decoration.svg"
    L = _read_layout(result.installed_dir / f"{theme_name}rc")

    tl_w, tl_h = _region_image_attrs(svg, "decoration-topleft")
    tr_w, tr_h = _region_image_attrs(svg, "decoration-topright")
    bl_w, bl_h = _region_image_attrs(svg, "decoration-bottomleft")
    br_w, br_h = _region_image_attrs(svg, "decoration-bottomright")

    left_w, _ = _region_image_attrs(svg, "decoration-left")
    right_w, _ = _region_image_attrs(svg, "decoration-right")
    assert int(tl_w) == int(left_w) >= L["BorderLeft"] and int(tl_h) == L["BorderTop"]
    assert int(tr_w) == int(right_w) >= L["BorderRight"] and int(tr_h) == L["BorderTop"]
    assert int(bl_w) == int(left_w) and int(bl_h) == L["BorderBottom"]
    assert int(br_w) == int(right_w) and int(br_h) == L["BorderBottom"]


@pytest.mark.parametrize("theme_name", THEMES)
def test_svg_canvas_size_matches_strip_thicknesses(
    theme_name: str, fake_home: Path
) -> None:
    """SVG canvas = left + middle + right by top + middle + bottom."""
    result = convert(FIXTURES / f"{theme_name}.etheme", scale=2, backend="svg")
    svg = result.installed_dir / "decoration.svg"
    L = _read_layout(result.installed_dir / f"{theme_name}rc")

    root = ET.parse(svg).getroot()
    cw = int(root.get("width", "0"))
    ch = int(root.get("height", "0"))

    expected_w = L["BorderLeft"] + L["BorderRight"]
    expected_h = L["BorderTop"] + L["BorderBottom"]
    assert cw > expected_w, f"canvas w={cw} not larger than borders {expected_w}"
    assert ch > expected_h, f"canvas h={ch} not larger than borders {expected_h}"
    # And the middle must be a sane size (≥32 px)
    assert (cw - expected_w) >= 32
    assert (ch - expected_h) >= 32
