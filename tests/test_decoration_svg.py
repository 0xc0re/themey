"""Tests for decoration_svg.py — 18 FrameSvg IDs + hint margins + base64 PNG."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"


def _make_tiny_png(tmp_path: Path, name: str = "test.png", size: tuple[int, int] = (8, 8)) -> Path:
    """Write a tiny RGBA PNG and return its path."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / name
    img = Image.new("RGBA", size, (64, 128, 192, 255))
    img.save(str(p), format="PNG")
    return p


def _make_theme_with_iclass(tmp_path: Path, scale: int = 1):
    """Build a synthetic Theme with one IClassSpec that has a real PNG."""
    from themey.ir import BorderSpec, IClassSpec, Palette, Theme

    png = _make_tiny_png(tmp_path)
    iclass = IClassSpec(
        name="TITLE_BAR_HORIZONTAL",
        edge_scaling=(4, 4, 18, 4),  # (left, right, top, bottom)
        normal=png,
        normal_active=png,
        hilited=None,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )
    return Theme(
        name="Test",
        display_name="Test",
        author=None,
        scale=scale,
        asset_root=tmp_path,
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4,
            border_size_right=4,
            border_size_top=18,
            border_size_bottom=4,
            parts=(),
        ),
        iclasses={"TITLE_BAR_HORIZONTAL": iclass},
        tclasses={},
        button_codes={},
        left_buttons="",
        right_buttons="",
        palette=Palette(
            titlebar_active=(64, 64, 64),
            titlebar_inactive=(128, 128, 128),
            text_active=(255, 255, 255),
            text_inactive=(192, 192, 192),
        ),
    )


def _collect_ids(tree: ET.ElementTree) -> set[str]:
    root = tree.getroot()
    return {e.get("id") for e in root.iter() if e.get("id")}


def test_decoration_svg_writes_file(tmp_path: Path) -> None:
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)
    assert (out_dir / "decoration.svg").is_file()


def test_decoration_svg_18_required_ids_present(tmp_path: Path) -> None:
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)

    tree = ET.parse(out_dir / "decoration.svg")
    present = _collect_ids(tree)
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    assert not missing, f"Missing FrameSvg IDs: {missing}"


def test_decoration_svg_no_relative_image_hrefs(tmp_path: Path) -> None:
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)

    # Parse and check all image elements
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)
    tree = ET.parse(out_dir / "decoration.svg")
    root = tree.getroot()

    images = list(root.iter(f"{{{SVG_NS}}}image"))
    assert len(images) > 0, "Expected at least one <image> element"

    for img in images:
        # Check both xlink:href and href attributes
        href = img.get(f"{{{XLINK_NS}}}href") or img.get("href") or ""
        assert href.startswith("data:image/png;base64,"), (
            f"Image href is not a data URI: {href[:60]!r}"
        )


def test_decoration_svg_preserve_aspect_ratio_none(tmp_path: Path) -> None:
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)

    tree = ET.parse(out_dir / "decoration.svg")
    root = tree.getroot()

    images = list(root.iter(f"{{{SVG_NS}}}image"))
    assert len(images) > 0
    for img in images:
        par = img.get("preserveAspectRatio")
        assert par == "none", (
            f"Expected preserveAspectRatio='none', got {par!r}"
        )


def test_decoration_svg_hint_margins_present(tmp_path: Path) -> None:
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)

    tree = ET.parse(out_dir / "decoration.svg")
    ids = _collect_ids(tree)
    for side in ("top", "bottom", "left", "right"):
        assert f"decoration-hint-{side}-margin" in ids
        assert f"decoration-inactive-hint-{side}-margin" in ids
    # Unprefixed ids are inert in Aurorae — must not be emitted.
    assert "hint-top-margin" not in ids


def test_decoration_svg_stretch_borders_hint(tmp_path: Path) -> None:
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)
    ids = _collect_ids(ET.parse(out_dir / "decoration.svg"))
    assert "decoration-hint-stretch-borders" in ids
    assert "decoration-inactive-hint-stretch-borders" in ids


def test_decoration_svg_maximized_groups(tmp_path: Path) -> None:
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS
    from themey.generate.decoration_svg import SIDES, write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)
    ids = _collect_ids(ET.parse(out_dir / "decoration.svg"))
    for side in SIDES:
        assert f"decoration-maximized-{side}" in ids
        assert f"decoration-maximized-inactive-{side}" in ids
        assert f"decoration-maximized-{side}" in REQUIRED_FRAMESVG_IDS
        assert f"decoration-maximized-inactive-{side}" in REQUIRED_FRAMESVG_IDS
    assert len(REQUIRED_FRAMESVG_IDS) == 36


def test_decoration_svg_maximized_center_carries_title_band(tmp_path: Path) -> None:
    """Aurorae paints decoration-maximized with NoBorder: only ``center`` is
    drawn (stretched over the title band), so it must hold the top-strip art
    and be as tall as BorderTop."""
    from themey.generate.decoration_svg import strip_thicknesses, write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)
    root = ET.parse(out_dir / "decoration.svg").getroot()
    ns = {"s": "http://www.w3.org/2000/svg"}
    top_img = root.find("s:g[@id='decoration-top']/s:image", ns)
    max_img = root.find("s:g[@id='decoration-maximized-center']/s:image", ns)
    assert top_img is not None and max_img is not None
    href = "{http://www.w3.org/1999/xlink}href"
    assert max_img.get(href) == top_img.get(href)
    assert int(max_img.get("height")) == strip_thicknesses(theme)["top"]


def test_side_borders_capped_at_48_top_unclamped() -> None:
    """Aurorae v2 clamps sides to the Oversized bracket (48); the title band is free."""
    from themey.generate.decoration_svg import (
        DEFAULT_MAX_BORDER,
        DEFAULT_MAX_SIDE_BORDER,
    )

    assert DEFAULT_MAX_SIDE_BORDER == 48
    assert DEFAULT_MAX_BORDER > DEFAULT_MAX_SIDE_BORDER


def test_decoration_svg_no_ns0_prefix(tmp_path: Path) -> None:
    """SVG must NOT contain ns0: prefix — register_namespace must be called."""
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)

    content = (out_dir / "decoration.svg").read_text()
    assert "ns0:" not in content, "ns0: prefix found — register_namespace not called correctly"
