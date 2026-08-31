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

    # e13's declared 40-ref left zone hosts its button stack (KILL/ICONIFY/
    # SHADE/STICK); the border trims to WIN_SIDE_LEFT's 7-ref opaque edge
    # → BorderLeft = 14 at scale=2. 80 was the smeared-frame bug.
    assert border_left <= 16, f"BorderLeft={border_left}: side trim regressed"
    assert border_left >= 4, f"BorderLeft={border_left} too small (< 4)"

    # BorderRight: e13's BORDER_SIZE_RIGHT is small; expect 6-40 at scale=2.
    assert border_right <= 60, f"BorderRight={border_right} too large"
    assert border_right >= 2, f"BorderRight={border_right} too small"

    # TitleHeight trims to the titlebar art's opaque rows 0-30 (~31 ref =
    # 62 out); the transparent notch below stays in the 92-tall band.
    border_top = int(layout["BorderTop"])
    assert title_height <= border_top, (
        f"TitleHeight={title_height} exceeds BorderTop={border_top}"
    )
    assert 56 <= title_height <= 64, (
        f"TitleHeight={title_height}: opaque-rows trim regressed"
    )

    # No 80x76 shared button slot anywhere — buttons are per-code sized.
    for key, value in layout.items():
        if key.startswith("ButtonWidth"):
            assert int(value) != 80, f"{key}=80: shared-slot regression"
        if key.startswith("ButtonHeight"):
            assert int(value) != 76, f"{key}=76: shared-slot regression"

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

    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    with extract(E13_PATH) as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root), name="e13",
            display_name="e13", scale=2,
        )
    left = theme.left_buttons
    right = theme.right_buttons
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
def test_e13_bottom_opaque_and_top_notch_survives(tmp_path, monkeypatch):
    """decoration-bottom composites art; decoration-top keeps the notch.

    WIN_BOTTOM's degenerate rect used to fail the y1<=y0 guard → invisible
    bottom border. And the uniform stretch used to paint titlebar caps over
    the shaped transparent notch → a 100%-opaque smeared top band. Both
    must stay fixed: the bottom strip has opaque pixels; the top strip's
    lower third keeps transparent ones (the wallpaper shows through).
    """
    import base64
    import io

    from PIL import Image

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
    root = ET.parse(result.installed_dir / "decoration.svg").getroot()
    SVG_NS = "{http://www.w3.org/2000/svg}"
    XLINK = "{http://www.w3.org/1999/xlink}href"

    def region_png(region_id: str) -> Image.Image:
        for g in root.iter(f"{SVG_NS}g"):
            if g.get("id") == region_id:
                img = g.find(f"{SVG_NS}image")
                assert img is not None
                href = img.get(XLINK, "")
                data = base64.b64decode(href.split(",", 1)[1])
                return Image.open(io.BytesIO(data)).convert("RGBA")
        raise AssertionError(f"no {region_id}")

    bottom = region_png("decoration-bottom")
    bottom_alpha = list(bottom.getchannel("A").getdata())
    assert any(a > 32 for a in bottom_alpha), "bottom strip fully transparent"

    # The notch: e13's band is capsule (rows 0-61 at scale=2), a transparent
    # gap, then the fin's stretched "waterline" bar along the bottom. The
    # gap rows (~0.68h-0.74h) must stay majority-transparent — the uniform
    # stretch painted them 100% opaque.
    top = region_png("decoration-top")
    w, h = top.size
    gap = top.crop((0, int(h * 0.68), w, int(h * 0.74)))
    gap_alpha = list(gap.getchannel("A").getdata())
    transparent = sum(1 for a in gap_alpha if a <= 32)
    assert transparent > len(gap_alpha) // 2, (
        f"notch rows are {100 - 100 * transparent // len(gap_alpha)}% opaque "
        "— the shaped notch was painted shut"
    )


@pytest.mark.skipif(
    not E13_PATH.exists(),
    reason="e13.etheme not available on this machine",
)
def test_e13_report_carries_fidelity_notes(tmp_path, monkeypatch):
    """report.txt documents the three e13 layout decisions.

    Left-zone trim, title-notch trim, and the side-stack button migration
    are approximations the user should be able to read about. A theme with
    no shaped art (Mac3D) must gain none of them.
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

    report = convert(E13_PATH, scale=2).report_path.read_text()
    assert "hosts a button stack; border trimmed" in report, report
    assert "TitleHeight trimmed to the title art's opaque rows" in report
    assert "side-stack button(s) moved to the titlebar" in report

    mac3d = E13_PATH.parent / "Mac3D.etheme"
    if mac3d.exists():
        mac_report = convert(mac3d, scale=2).report_path.read_text()
        for marker in (
            "border trimmed",
            "TitleHeight trimmed",
            "side-stack button(s)",
        ):
            assert marker not in mac_report, (marker, mac_report)


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
