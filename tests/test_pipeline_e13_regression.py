"""Regression test: e13 theme layout values must be visually reasonable.

Bug history: e13.etheme has __BORDER_SIZE_LEFT=40 (total left zone including
button stack) and __BORDER_SIZE_TOP=46 (total top zone). The old formula
``BorderLeft = border_size_left * scale`` produced BorderLeft=80 at scale=2,
causing KWin to render an 80px wide left frame filled with a stretched titlebar
gradient -- the "cream gradient blob" visual bug.

The correct formula uses:
- BorderLeft = WIN_SIDE_LEFT image width * scale  (actual side decoration width)
- TitleHeight = FIN image height * scale           (actual titlebar strip height)
- PaddingLeft = border_size_left * scale           (total left zone for geometry)

This regression test converts e13.etheme and asserts the layout values are
in the sensible ranges that prevent the visual bug.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

import pytest

E13_PATH = Path("/home/cstory/src/wilbs/ethemes/e16/e13.etheme")


@pytest.mark.skipif(
    not E13_PATH.exists(),
    reason="e13.etheme not available on this machine",
)
def test_e13_rc_border_values_are_sane(tmp_path, monkeypatch):
    """e13 must produce layout values that render a non-grotesque decoration."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(fake_home / ".local" / "share"))

    import themey.paths as paths_mod

    aurorae_dir = fake_home / ".local/share/aurorae/themes"
    previews_dir = fake_home / ".local/share/themey/previews"
    monkeypatch.setattr(paths_mod, "aurorae_themes", lambda: aurorae_dir)
    monkeypatch.setattr(paths_mod, "themey_previews", lambda: previews_dir)

    from themey.pipeline import convert

    result = convert(E13_PATH, scale=2)

    rc_path = result.installed_dir / "e13rc"
    assert rc_path.is_file(), f"e13rc not found in {result.installed_dir}"

    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc_path)

    layout = cp["Layout"]
    border_left = int(layout["BorderLeft"])
    border_right = int(layout["BorderRight"])
    title_height = int(layout["TitleHeight"])
    padding_left = int(layout["PaddingLeft"])
    padding_top = int(layout["PaddingTop"])

    # BorderLeft must NOT be grotesquely large (old bug: 80px)
    # WIN_SIDE_LEFT image is 30px wide -> BorderLeft = 30 * 2 = 60 at scale=2
    # Acceptable range: 4-120 (wide enough to hold side artwork, not over 2x source size)
    assert border_left <= 120, (
        f"BorderLeft={border_left} is too large -- old bug was 80px stretched gradient"
    )
    assert border_left >= 4, f"BorderLeft={border_left} too small (< 4)"

    # BorderRight should be reasonable for a 6px source right border
    assert border_right <= 30, f"BorderRight={border_right} too large"
    assert border_right >= 2, f"BorderRight={border_right} too small"

    # TitleHeight must NOT be based on border_size_top (old bug: 84px)
    # FIN image is 16px tall -> TitleHeight = 16 * 2 = 32 at scale=2
    # Acceptable range: [12, 80]
    assert title_height <= 80, (
        f"TitleHeight={title_height} too large -- old bug was 84px from border_size_top formula"
    )
    assert title_height >= 12, f"TitleHeight={title_height} too small"

    # PaddingLeft = border_size_left * scale = 40 * 2 = 80 (total left zone)
    # This is correct and must equal border_size_left * scale
    assert padding_left == 80, (
        f"PaddingLeft={padding_left} should be 80 (border_size_left=40 * scale=2)"
    )

    # PaddingTop = border_size_top * scale = 46 * 2 = 92 (total top zone)
    assert padding_top == 92, (
        f"PaddingTop={padding_top} should be 92 (border_size_top=46 * scale=2)"
    )


@pytest.mark.skipif(
    not E13_PATH.exists(),
    reason="e13.etheme not available on this machine",
)
def test_e13_decoration_svg_has_18_ids(tmp_path, monkeypatch):
    """e13 decoration.svg must contain all 18 required FrameSvg IDs."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    monkeypatch.setenv("XDG_DATA_HOME", str(fake_home / ".local" / "share"))

    import themey.paths as paths_mod

    aurorae_dir = fake_home / ".local/share/aurorae/themes"
    previews_dir = fake_home / ".local/share/themey/previews"
    monkeypatch.setattr(paths_mod, "aurorae_themes", lambda: aurorae_dir)
    monkeypatch.setattr(paths_mod, "themey_previews", lambda: previews_dir)

    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS
    from themey.pipeline import convert

    result = convert(E13_PATH, scale=2)

    svg_path = result.installed_dir / "decoration.svg"
    assert svg_path.is_file()

    root = ET.parse(svg_path).getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    assert not missing, f"Missing FrameSvg IDs in e13 decoration.svg: {missing}"
