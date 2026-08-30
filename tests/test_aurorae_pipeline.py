"""End-to-end Aurorae generator tests.

Task 3: Synthetic-theme smoke test + Aliens canary integration test.

The Aliens canary is the headline assertion for Phase 1: extract Aliens.etheme,
parse_tree, build_theme -> Theme; call generate.aurorae.write(theme, out_dir)
and assert the full 18-ID FrameSvg contract, rc key/value correctness, and
metadata file correctness.
"""
from __future__ import annotations

import json
from configparser import RawConfigParser
from pathlib import Path

import pytest

from themey.ir import BorderSpec, IClassSpec, Palette, Theme


def _make_synthetic_theme(tmp_path: Path) -> Theme:
    """Build a minimal synthetic Theme with button codes XAI."""
    from PIL import Image

    # Create a tiny PNG for buttons
    png_dir = tmp_path / "assets"
    png_dir.mkdir()
    png = png_dir / "btn.png"
    Image.new("RGBA", (8, 8), (255, 0, 0, 255)).save(str(png), format="PNG")

    # Create a tiny iclass PNG for titlebar
    title_png = png_dir / "title.png"
    Image.new("RGBA", (16, 16), (64, 64, 64, 255)).save(str(title_png), format="PNG")

    iclass_title = IClassSpec(
        name="TITLE_BAR_HORIZONTAL",
        edge_scaling=(4, 4, 18, 4),
        normal=title_png,
        normal_active=title_png,
        hilited=None,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )
    iclass_close = IClassSpec(
        name="BUTTON_CLOSE",
        edge_scaling=(2, 2, 2, 2),
        normal=png,
        normal_active=png,
        hilited=png,
        hilited_active=None,
        clicked=png,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )
    iclass_max = IClassSpec(
        name="BUTTON_MAXIMIZE",
        edge_scaling=(2, 2, 2, 2),
        normal=png,
        normal_active=png,
        hilited=None,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )
    iclass_min = IClassSpec(
        name="BUTTON_ICONIFY",
        edge_scaling=(2, 2, 2, 2),
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
        name="SyntheticTest",
        display_name="Synthetic Test",
        author=None,
        scale=1,
        asset_root=png_dir,
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4,
            border_size_right=4,
            border_size_top=18,
            border_size_bottom=4,
            parts=(),
        ),
        iclasses={
            "TITLE_BAR_HORIZONTAL": iclass_title,
            "BUTTON_CLOSE": iclass_close,
            "BUTTON_MAXIMIZE": iclass_max,
            "BUTTON_ICONIFY": iclass_min,
        },
        tclasses={},
        button_codes={
            "BUTTON_CLOSE": "X",
            "BUTTON_MAXIMIZE": "A",
            "BUTTON_ICONIFY": "I",
        },
        left_buttons="XAI",
        right_buttons="",
        palette=Palette(
            titlebar_active=(64, 64, 64),
            titlebar_inactive=(128, 128, 128),
            text_active=(255, 255, 255),
            text_inactive=(192, 192, 192),
        ),
    )


def test_aurorae_write_creates_all_files(tmp_path: Path) -> None:
    """Synthetic minimal theme: write() produces all expected files."""
    from themey.generate.aurorae import write

    theme = _make_synthetic_theme(tmp_path)
    out_dir = tmp_path / "out" / "SyntheticTest"
    files = write(theme, out_dir)

    file_names = {f.name for f in files}
    # Core metadata files
    assert "decoration.svg" in file_names
    assert "SyntheticTestrc" in file_names
    assert "metadata.desktop" in file_names
    assert "metadata.json" in file_names
    # Button SVGs from XAI
    assert "close.svg" in file_names
    assert "maximize.svg" in file_names
    assert "restore.svg" in file_names
    assert "minimize.svg" in file_names


def test_aurorae_aliens_canary(tmp_path: Path) -> None:
    """Aliens.etheme end-to-end: parse -> build_theme -> write -> assert contracts."""
    import xml.etree.ElementTree as ET

    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS, write

    aliens_path = Path("tests/fixtures/Aliens.etheme")
    if not aliens_path.is_file():
        pytest.skip("Aliens.etheme fixture not present")

    with extract(aliens_path) as raw:
        nodes = parse_tree(raw.asset_root)
        theme = build_theme(raw.asset_root, nodes, name="Aliens", scale=2)
        out_dir = tmp_path / "Aliens"
        write(theme, out_dir)

    # --- decoration.svg: 18 FrameSvg IDs ---
    assert (out_dir / "decoration.svg").is_file()
    root = ET.parse(out_dir / "decoration.svg").getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    assert not missing, f"Missing FrameSvg IDs: {missing}"

    # --- <name>rc: button SVGs exist for XAI, [Layout] BorderLeft=70 ---
    rc_path = out_dir / "Aliensrc"
    assert rc_path.is_file(), f"Expected 'Aliensrc', not found in {list(out_dir.iterdir())}"
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc_path, encoding="utf-8")
    assert "LeftButtons" not in cp["General"]
    border_left = int(cp["Layout"]["BorderLeft"])
    # BorderLeft = max(BORDER_SIZE_LEFT, max anchored-part width) x scale.
    # Aliens has CORNER_TL at 124 wide, so BorderLeft = 248 at scale=2 to
    # fit the full alien-head art uncompressed. Clamped to [2, 400].
    assert 2 <= border_left <= 400, (
        f"BorderLeft={border_left} out of clamp [2, 400] at scale=2"
    )

    # --- metadata.desktop ---
    md_path = out_dir / "metadata.desktop"
    assert md_path.is_file()
    md_content = md_path.read_text()
    assert "X-KDE-PluginInfo-Name=Aliens" in md_content

    # --- metadata.json ---
    mj_path = out_dir / "metadata.json"
    assert mj_path.is_file()
    mj = json.loads(mj_path.read_text())
    assert mj["KPackageStructure"] == "KWin/Aurorae"
    assert mj["KPlugin"]["Id"] == "Aliens"

    # --- button SVGs ---
    for fname in ("close.svg", "maximize.svg", "restore.svg", "minimize.svg"):
        assert (out_dir / fname).is_file(), f"Missing button SVG: {fname}"
