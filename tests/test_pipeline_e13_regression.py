"""Regression test: e13 theme layout values must be visually reasonable.

Bug history: an earlier formula derived ``BorderLeft`` from the wrong source,
producing an 80px wide left frame stretched gradient -- the "cream gradient
blob" visual bug. The original fix split strip thickness from full-zone
geometry.

The current formula (post-compositor work, May 2026) restores full E16
``__BORDER_SIZE_*`` semantics now that each region is composited from
multiple parts rather than rendering a single iclass stretched across the
whole zone:

- ``BorderLeft = BORDER_SIZE_LEFT x scale``
- ``BorderTop  = BORDER_SIZE_TOP  x scale``
- ``TitleHeight ≤ BorderTop`` (title bar lives inside the top zone)
- ``Padding* = 0`` (E16 has no shadow concept)

This regression test asserts the layout values stay within sensible ranges
that prevent rendering grotesqueries.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

import pytest

E13_PATH = Path(__file__).parent / "fixtures" / "e13.etheme"


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

    # BorderLeft = BORDER_SIZE_LEFT x scale. e13 has BORDER_SIZE_LEFT=40 so
    # BorderLeft = 80 at scale=2. Acceptable range bounded by the [2, 120]
    # clamp in strip_thicknesses().
    assert border_left <= 120, f"BorderLeft={border_left} above clamp"
    assert border_left >= 4, f"BorderLeft={border_left} too small (< 4)"

    # BorderRight: e13's BORDER_SIZE_RIGHT is small; expect 6-40 at scale=2.
    assert border_right <= 60, f"BorderRight={border_right} too large"
    assert border_right >= 2, f"BorderRight={border_right} too small"

    # TitleHeight must be within the top zone (≤ BorderTop) and at least the
    # minimum readable size. The full-zone semantics allow TitleHeight to
    # equal BorderTop when the title bar part spans the whole top zone.
    border_top = int(layout["BorderTop"])
    assert title_height <= border_top, (
        f"TitleHeight={title_height} exceeds BorderTop={border_top}"
    )
    assert title_height >= 12, f"TitleHeight={title_height} too small"

    # Padding* must be 0 -- E16 has no shadow concept, and the old formula
    # (border_size_* * scale) emitted a huge shadow zone that left the title
    # text floating above the actual frame. See decoration_svg.py docstring.
    assert padding_left == 0, (
        f"PaddingLeft={padding_left} should be 0 (no shadow zone in v1)"
    )
    assert padding_top == 0, (
        f"PaddingTop={padding_top} should be 0 (no shadow zone in v1)"
    )


@pytest.mark.skipif(
    not E13_PATH.exists(),
    reason="e13.etheme not available on this machine",
)
def test_e13_buttons_bound_to_one_side(tmp_path, monkeypatch):
    """e13 buttons must appear in exactly one of LeftButtons/RightButtons.

    Regression: e13's title-bearing part has __ICLASS TITLEBAR (no underscore),
    so the old build_theme.py heuristic ``"TITLE_BAR" in iclass_name`` missed
    it. The titlebar bounds stayed at sentinel (min=800, max=0), and the
    original ``x < min AND x > max`` predicate placed every button into BOTH
    sides, yielding LeftButtons=XILS, RightButtons=XILS.

    With canonical __FLAG_TITLE identification + sentinel fallback in
    bin_left_right, each button appears exactly once.
    """
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
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc_path)

    left = cp["General"].get("LeftButtons", "")
    right = cp["General"].get("RightButtons", "")
    combined = left + right

    # No character appears in both strings — buttons must not duplicate.
    assert set(left).isdisjoint(set(right)), (
        f"buttons duplicated across sides: Left={left!r} Right={right!r}"
    )
    # At least one button should land somewhere (e13 declares close/min/max/shade).
    assert combined, f"e13 produced no LeftButtons or RightButtons: {left!r}/{right!r}"
    # Every code in left+right must be unique (one button → one side).
    assert len(combined) == len(set(combined)), (
        f"duplicate button code in Left+Right combined: {combined!r}"
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
