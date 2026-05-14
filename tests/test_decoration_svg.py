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
    for hint_id in ("hint-top-margin", "hint-bottom-margin", "hint-left-margin", "hint-right-margin"):
        assert hint_id in ids, f"Missing hint margin: {hint_id}"


def test_decoration_svg_no_ns0_prefix(tmp_path: Path) -> None:
    """SVG must NOT contain ns0: prefix — register_namespace must be called."""
    from themey.generate.decoration_svg import write_decoration_svg

    theme = _make_theme_with_iclass(tmp_path / "assets")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    write_decoration_svg(theme, out_dir)

    content = (out_dir / "decoration.svg").read_text()
    assert "ns0:" not in content, "ns0: prefix found — register_namespace not called correctly"
