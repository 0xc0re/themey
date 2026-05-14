"""Tests for aurorae_rc.py — Aurorae <name>rc INI writer.

Must use RawConfigParser with optionxform=str to preserve KDE case-sensitive keys.
"""
from __future__ import annotations

from configparser import RawConfigParser
from pathlib import Path


def _make_minimal_theme(
    *,
    name: str = "Aliens",
    scale: int = 2,
    left_buttons: str = "XAI",
    right_buttons: str = "",
    text_active: tuple[int, int, int] = (255, 255, 200),
    text_inactive: tuple[int, int, int] = (192, 192, 192),
    border_size_left: int = 35,
    border_size_right: int = 35,
    border_size_top: int = 35,
    border_size_bottom: int = 6,
):
    """Build a minimal synthetic Theme for rc-writer tests."""
    from themey.ir import BorderSpec, Palette, Theme

    border = BorderSpec(
        name="DEFAULT",
        border_size_left=border_size_left,
        border_size_right=border_size_right,
        border_size_top=border_size_top,
        border_size_bottom=border_size_bottom,
        parts=(),
    )
    palette = Palette(
        titlebar_active=(64, 64, 64),
        titlebar_inactive=(128, 128, 128),
        text_active=text_active,
        text_inactive=text_inactive,
    )
    return Theme(
        name=name,
        display_name=name,
        author=None,
        scale=scale,
        asset_root=Path("/tmp/x"),
        border=border,
        iclasses={},
        tclasses={},
        button_codes={},
        left_buttons=left_buttons,
        right_buttons=right_buttons,
        palette=palette,
    )


def _read_rc(path: Path) -> RawConfigParser:
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(path, encoding="utf-8")
    return cp


def test_aurorae_rc_general_section(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(left_buttons="XAI", right_buttons="")
    out = write_aurorae_rc(theme, tmp_path)
    assert out.is_file()
    cp = _read_rc(out)
    assert cp["General"]["LeftButtons"] == "XAI"
    assert cp["General"]["RightButtons"] == ""


def test_aurorae_rc_active_text_color_format(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(text_active=(255, 255, 200))
    out = write_aurorae_rc(theme, tmp_path)
    cp = _read_rc(out)
    assert cp["General"]["ActiveTextColor"] == "255,255,200,255"


def test_aurorae_rc_layout_keys_present(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme()
    out = write_aurorae_rc(theme, tmp_path)
    cp = _read_rc(out)
    required_layout_keys = [
        "BorderLeft",
        "BorderRight",
        "BorderBottom",
        "BorderTop",
        "TitleEdgeTop",
        "TitleEdgeBottom",
        "TitleEdgeLeft",
        "TitleEdgeRight",
        # Extended layout keys matching Edna's rc
        "TitleBorderLeft",
        "TitleBorderRight",
        "TitleHeight",
        "ButtonWidth",
        "ButtonHeight",
        "ButtonSpacing",
        "PaddingTop",
        "PaddingBottom",
        "PaddingLeft",
        "PaddingRight",
    ]
    for key in required_layout_keys:
        assert key in cp["Layout"], f"Missing Layout key: {key}"


def test_aurorae_rc_borderleft_scales_with_theme_scale(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme1 = _make_minimal_theme(scale=1, border_size_left=35)
    theme2 = _make_minimal_theme(scale=2, border_size_left=35)
    out1 = write_aurorae_rc(theme1, tmp_path / "s1")
    (tmp_path / "s1").mkdir(parents=True, exist_ok=True)
    out1 = write_aurorae_rc(theme1, tmp_path / "s1")
    (tmp_path / "s2").mkdir(parents=True, exist_ok=True)
    out2 = write_aurorae_rc(theme2, tmp_path / "s2")
    cp1 = _read_rc(out1)
    cp2 = _read_rc(out2)
    bl1 = int(cp1["Layout"]["BorderLeft"])
    bl2 = int(cp2["Layout"]["BorderLeft"])
    assert bl2 == bl1 * 2, f"scale=2 BorderLeft ({bl2}) should be 2x scale=1 ({bl1})"


def test_aurorae_rc_filename_matches_theme_name(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(name="Aliens")
    out = write_aurorae_rc(theme, tmp_path)
    assert out.name == "Aliensrc", f"Expected 'Aliensrc', got '{out.name}'"


def test_aurorae_rc_keys_case_preserved(tmp_path: Path) -> None:
    """Open written file as raw text; confirm LeftButtons= (capital L) NOT leftbuttons=."""
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme()
    out = write_aurorae_rc(theme, tmp_path)
    raw = out.read_text(encoding="utf-8")
    assert "LeftButtons=" in raw, "Expected 'LeftButtons=' (capital L) in rc file"
    assert "leftbuttons=" not in raw, "Found lowercase 'leftbuttons=' — optionxform not set"


# ---------------------------------------------------------------------------
# Adaptive title centering — when the title-bearing part is small relative to
# the grown chrome (e.g. Aliens grows BorderTop to 120 to fit the alien-head
# corner art; title bar is only 26 tall), the title text should be CENTERED
# vertically rather than pinned to the top.
# ---------------------------------------------------------------------------


def test_aliens_title_text_centered_in_capped_chrome(tmp_path: Path, monkeypatch) -> None:
    """Aliens: BorderTop is grown to fit corner art; the 26-tall title text
    must be centered within the 120-tall chrome (not pinned to y=6).

    Pre-fix: TitleEdgeTop=6 placed the title at the top of a 120-tall band,
    visually disconnected from the chrome center. Post-fix: TitleEdgeTop ≈
    (BorderTop − TitleHeight) / 2 ≈ 47.
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

    aliens = Path(__file__).parent / "fixtures" / "Aliens.etheme"
    if not aliens.exists():
        import pytest

        pytest.skip("Aliens.etheme fixture not available")
    result = convert(aliens, scale=2)

    cp = _read_rc(result.installed_dir / "Aliensrc")
    layout = cp["Layout"]
    border_top = int(layout["BorderTop"])
    title_height = int(layout["TitleHeight"])
    title_edge_top = int(layout["TitleEdgeTop"])
    title_edge_bottom = int(layout["TitleEdgeBottom"])

    # Sanity preconditions: Aliens chrome must actually be the "small-title-in-
    # big-chrome" case for this test to be meaningful. (BorderTop grows to
    # accommodate the 179-tall CORNER_TL alien-head.)
    assert title_height < border_top * 0.6, (
        f"Test premise broken: title_height={title_height} not small vs "
        f"border_top={border_top} (centering should fire)"
    )

    # Centered: TitleEdgeTop ≈ (BorderTop - TitleHeight) / 2, ±2 px.
    expected_top = (border_top - title_height) // 2
    assert abs(title_edge_top - expected_top) <= 2, (
        f"TitleEdgeTop={title_edge_top} not centered "
        f"(expected ≈ {expected_top}, BorderTop={border_top}, "
        f"TitleHeight={title_height})"
    )

    # Layout invariant: edges + height must sum to BorderTop.
    assert title_edge_top + title_height + title_edge_bottom == border_top, (
        f"layout doesn't tile: top={title_edge_top} + height={title_height} "
        f"+ bottom={title_edge_bottom} != BorderTop={border_top}"
    )


def test_e13_title_canonical_placement_when_fills_chrome(
    tmp_path: Path, monkeypatch
) -> None:
    """e13: title bar fills the entire top zone (46 tall ÷ 46 chrome = 100%).

    When the title spans most of the chrome, canonical positioning wins —
    we keep TitleEdgeTop at the part's reference y (which is 0 for e13).
    Centering should NOT fire.
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

    e13 = Path(__file__).parent / "fixtures" / "e13.etheme"
    if not e13.exists():
        import pytest

        pytest.skip("e13.etheme fixture not available")
    result = convert(e13, scale=2)

    cp = _read_rc(result.installed_dir / "e13rc")
    layout = cp["Layout"]
    border_top = int(layout["BorderTop"])
    title_height = int(layout["TitleHeight"])
    title_edge_top = int(layout["TitleEdgeTop"])

    # Canonical placement when title fills chrome: top edge is at 0 (or near).
    assert title_edge_top <= 4, (
        f"e13 TitleEdgeTop={title_edge_top}: expected canonical "
        f"placement (~0), not centered (title fills chrome)"
    )
    # And title should fill most of the chrome.
    assert title_height >= border_top * 0.6, (
        f"e13 title_height={title_height} < 0.6*border_top={border_top}; "
        f"premise of this test broken"
    )
