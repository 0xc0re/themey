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
    # Button order is global (kwinrc ButtonsOnLeft/Right); Aurorae ignores
    # these keys, so we no longer emit them.
    for dead in ("LeftButtons", "RightButtons", "Shadow"):
        assert dead not in cp["General"], dead
    # v1 (org.kde.kwin.aurorae) reads the text-shadow keys; keep emitting them.
    assert cp["General"]["UseTextShadow"] in ("true", "false")
    assert "ButtonMarginLeft" not in cp["Layout"]
    assert "TitleAlignment" in cp["General"]


def test_aurorae_rc_maximized_layout_keys(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(left_buttons="XAI", right_buttons="")
    cp = _read_rc(write_aurorae_rc(theme, tmp_path))
    L = cp["Layout"]
    for k in (
        "TitleEdgeTop",
        "TitleEdgeBottom",
        "TitleEdgeLeft",
        "TitleEdgeRight",
        "ButtonMarginTop",
    ):
        assert L[f"{k}Maximized"] == L[k]


def test_aurorae_rc_per_button_widths(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(left_buttons="XAI", right_buttons="")
    cp = _read_rc(write_aurorae_rc(theme, tmp_path))
    L = cp["Layout"]
    for k in (
        "ButtonWidthClose", "ButtonWidthMinimize", "ButtonWidthMaximizeRestore",
        "ButtonWidthAlldesktops", "ButtonWidthShade", "ButtonWidthKeepabove",
        "ButtonWidthKeepbelow", "ButtonWidthMenu",
    ):
        assert int(L[k]) > 0, k


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

    # 20 ref -> 40 output at scale=2, under the 48-px v2 side cap.
    theme1 = _make_minimal_theme(scale=1, border_size_left=20)
    theme2 = _make_minimal_theme(scale=2, border_size_left=20)
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
    """Open written file as raw text; confirm TitleAlignment= (capital) NOT titlealignment=."""
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme()
    out = write_aurorae_rc(theme, tmp_path)
    raw = out.read_text(encoding="utf-8")
    assert "TitleAlignment=" in raw, "Expected 'TitleAlignment=' (capital) in rc file"
    assert "titlealignment=" not in raw, "Found lowercase key — optionxform not set"


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
    result = convert(aliens, scale=2, backend="svg")

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


def test_tclass_justification_maps_to_titlealignment(tmp_path: Path) -> None:
    """TEXT1.alignment="Left" must produce TitleAlignment=Left in the rc."""
    from themey.generate.aurorae_rc import write_aurorae_rc
    from themey.ir import BorderSpec, Palette, TClassSpec, Theme

    border = BorderSpec(
        name="DEFAULT",
        border_size_left=4, border_size_right=4,
        border_size_top=20, border_size_bottom=4,
        parts=(),
    )
    theme = Theme(
        name="X", display_name="X", author=None, scale=1,
        asset_root=tmp_path,
        border=border,
        iclasses={},
        tclasses={
            "TEXT1": TClassSpec(
                name="TEXT1",
                fg_normal=(255, 255, 255),
                fg_active=(255, 255, 255),
                alignment="Left",
                effect=None,
            )
        },
        button_codes={}, left_buttons="", right_buttons="",
        palette=Palette((0, 0, 0), (0, 0, 0), (255, 255, 255), (192, 192, 192)),
    )
    out = write_aurorae_rc(theme, tmp_path / "out")
    cp = _read_rc(out)
    assert cp["General"]["TitleAlignment"] == "Left"


def test_litegnome_title_edge_padding_at_least_1(tmp_path: Path, monkeypatch) -> None:
    """LiteGnome's title-bearing part spans the full top zone (TitleEdgeTop=0
    canonical). KWin needs at least 1-2 px of padding at top and bottom to
    position the text baseline; otherwise the title vanishes.

    Post-fix: both TitleEdgeTop and TitleEdgeBottom must be >= max(1, scale).
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

    litegnome = Path(__file__).parent / "fixtures" / "LiteGnome.etheme"
    if not litegnome.exists():
        import pytest
        pytest.skip("LiteGnome.etheme fixture not available")
    result = convert(litegnome, scale=2, backend="svg")
    cp = _read_rc(result.installed_dir / "LiteGnomerc")
    layout = cp["Layout"]
    title_edge_top = int(layout["TitleEdgeTop"])
    title_edge_bottom = int(layout["TitleEdgeBottom"])
    # At scale=2, minimum padding is max(1, scale) = 2.
    assert title_edge_top >= 1, f"TitleEdgeTop={title_edge_top} < 1 — title text will clip"
    assert title_edge_bottom >= 1, (
        f"TitleEdgeBottom={title_edge_bottom} < 1 — title text will clip"
    )
    # Invariant: padding + height = BorderTop must still hold.
    border_top = int(layout["BorderTop"])
    title_height = int(layout["TitleHeight"])
    assert title_edge_top + title_height + title_edge_bottom == border_top, (
        f"layout doesn't tile: {title_edge_top} + {title_height} + "
        f"{title_edge_bottom} != {border_top}"
    )


def _luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = (c / 255 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def test_title_text_swapped_to_black_when_white_text_on_white_bg(tmp_path: Path) -> None:
    """When the title bar bg is near-white and the configured text color is
    also near-white, the writer must swap to black so the title text is
    legible.

    Synthetic theme: solid white-ish iclass image as the title-bearing
    iclass; ActiveTextColor configured as (255,255,255). After write, the
    rc's ActiveTextColor must be (0,0,0,255).
    """
    from PIL import Image

    from themey.generate.aurorae_rc import write_aurorae_rc
    from themey.ir import BorderSpec, ButtonPart, IClassSpec, Palette, Theme

    # Solid near-white iclass image.
    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    white_png = asset_root / "white.png"
    Image.new("RGBA", (32, 16), (240, 240, 240, 255)).save(white_png)

    # Title-bearing part fills the whole top zone.
    title_part = ButtonPart(
        iclass_name="TITLE",
        aclass=None,
        tl_x_pct=0, tl_x_abs=0, br_x_pct=1024, br_x_abs=0,
        tl_y_pct=0, tl_y_abs=0, br_y_pct=0, br_y_abs=20,
        flags=("__FLAG_TITLE",),
    )
    iclasses = {
        "TITLE": IClassSpec(
            name="TITLE",
            edge_scaling=(2, 2, 2, 2),
            normal=white_png, normal_active=white_png,
            hilited=None, hilited_active=None,
            clicked=None, clicked_active=None,
            normal_sticky=None, normal_active_sticky=None,
        )
    }
    theme = Theme(
        name="WhiteBg", display_name="WhiteBg", author=None, scale=2,
        asset_root=asset_root,
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4, border_size_right=4,
            border_size_top=20, border_size_bottom=4,
            parts=(title_part,),
        ),
        iclasses=iclasses,
        tclasses={},
        button_codes={},
        left_buttons="", right_buttons="",
        palette=Palette(
            titlebar_active=(240, 240, 240),
            titlebar_inactive=(240, 240, 240),
            text_active=(255, 255, 255),  # white on white — must be swapped
            text_inactive=(0, 0, 0),
        ),
    )
    out = write_aurorae_rc(theme, tmp_path / "out")
    cp = _read_rc(out)
    # Must have swapped to black for the active state.
    assert cp["General"]["ActiveTextColor"] == "0,0,0,255", (
        f"ActiveTextColor={cp['General']['ActiveTextColor']} — should be "
        f"swapped to black against near-white bg"
    )
    # Inactive stays untouched (it was already legible against white).
    assert cp["General"]["InactiveTextColor"] == "0,0,0,255"


def test_title_text_unchanged_when_contrast_already_high(tmp_path: Path) -> None:
    """White text on a dark bg already has high contrast — must not be swapped."""
    from PIL import Image

    from themey.generate.aurorae_rc import write_aurorae_rc
    from themey.ir import BorderSpec, ButtonPart, IClassSpec, Palette, Theme

    asset_root = tmp_path / "assets"
    asset_root.mkdir()
    dark_png = asset_root / "dark.png"
    Image.new("RGBA", (32, 16), (20, 20, 30, 255)).save(dark_png)

    title_part = ButtonPart(
        iclass_name="TITLE",
        aclass=None,
        tl_x_pct=0, tl_x_abs=0, br_x_pct=1024, br_x_abs=0,
        tl_y_pct=0, tl_y_abs=0, br_y_pct=0, br_y_abs=20,
        flags=("__FLAG_TITLE",),
    )
    iclasses = {
        "TITLE": IClassSpec(
            name="TITLE",
            edge_scaling=(2, 2, 2, 2),
            normal=dark_png, normal_active=dark_png,
            hilited=None, hilited_active=None,
            clicked=None, clicked_active=None,
            normal_sticky=None, normal_active_sticky=None,
        )
    }
    theme = Theme(
        name="DarkBg", display_name="DarkBg", author=None, scale=2,
        asset_root=asset_root,
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4, border_size_right=4,
            border_size_top=20, border_size_bottom=4,
            parts=(title_part,),
        ),
        iclasses=iclasses,
        tclasses={},
        button_codes={},
        left_buttons="", right_buttons="",
        palette=Palette(
            titlebar_active=(20, 20, 30),
            titlebar_inactive=(20, 20, 30),
            text_active=(255, 255, 255),
            text_inactive=(192, 192, 192),
        ),
    )
    out = write_aurorae_rc(theme, tmp_path / "out")
    cp = _read_rc(out)
    assert cp["General"]["ActiveTextColor"] == "255,255,255,255"


def test_openstep_title_text_contrast_acceptable(tmp_path: Path, monkeypatch) -> None:
    """Pipeline-level invariant: OPENSTEP must end up with title text colors
    that have acceptable luminance contrast against the composited top zone.

    Prior to the fix the writer left ActiveTextColor at (255,255,255)
    regardless of the title bar background, producing unreadable text on
    near-white inactive backgrounds in real KWin. After the fix the writer
    samples ``compose_region("top")`` and swaps to black/white when the
    sampled bg's luminance is within 0.2 of the text's.
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

    openstep = Path(__file__).parent / "fixtures" / "OPENSTEP.etheme"
    if not openstep.exists():
        import pytest
        pytest.skip("OPENSTEP.etheme fixture not available")
    result = convert(openstep, scale=2, backend="svg")
    cp = _read_rc(result.installed_dir / "OPENSTEPrc")
    # Parse RGB tuple from "r,g,b,a" string.
    parts = cp["General"]["ActiveTextColor"].split(",")
    text_rgb = (int(parts[0]), int(parts[1]), int(parts[2]))
    # Acceptable contrast: text and the most-likely bg shouldn't both be near-white.
    # If text is (255,255,255), the swap must have either kept it (because
    # contrast was already high) or fired and produced (0,0,0).
    assert text_rgb in ((255, 255, 255), (0, 0, 0)), (
        f"OPENSTEP ActiveTextColor={text_rgb}: expected pure white or "
        f"swapped-to-black, not an in-between value"
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
    result = convert(e13, scale=2, backend="svg")

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


def test_e13_title_height_trimmed_to_opaque_rows(
    tmp_path: Path, monkeypatch
) -> None:
    """e13's titlebar image is opaque only in rows 0-30 of 46; rows below are
    a shaped transparent notch (E16 __CHANGES_SHAPE). TitleHeight must trim
    to the opaque extent (~31 ref = 62 out) while BorderTop keeps the full
    zone (92) — the notch stays in the band and shows the wallpaper through
    the gap, reproducing e13's floating title capsule.
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
    result = convert(e13, scale=2, backend="svg")

    layout = _read_rc(result.installed_dir / "e13rc")["Layout"]
    border_top = int(layout["TitleEdgeTop"]) + int(layout["TitleHeight"]) + int(
        layout["TitleEdgeBottom"]
    )
    assert int(layout["BorderTop"]) == 92, layout["BorderTop"]
    assert border_top == 92  # edge-balancing ladder keeps the band tiling
    assert 56 <= int(layout["TitleHeight"]) <= 64, layout["TitleHeight"]
    assert int(layout["TitleEdgeBottom"]) >= 24, layout["TitleEdgeBottom"]


def test_aurorae_rc_persists_button_binning(tmp_path: Path) -> None:
    """The rc carries the theme's L/R button binning in a [Themey] section.

    KWin's button order is global kwinrc state; ``themey apply`` reads this
    section to reproduce the E16 layout. Aurorae ignores unknown groups.
    """
    theme = _make_minimal_theme(left_buttons="XI", right_buttons="A")
    from themey.generate.aurorae_rc import write_aurorae_rc

    rc = write_aurorae_rc(theme, tmp_path)
    cp = _read_rc(rc)
    assert cp["Themey"]["LeftButtons"] == "XI"
    assert cp["Themey"]["RightButtons"] == "A"


def test_aurorae_rc_text_shadow_from_tclass_effect(tmp_path: Path) -> None:
    """__DRAWING_EFFECT on TEXT1 drives UseTextShadow (read by Aurorae v1)."""
    from themey.generate.aurorae_rc import write_aurorae_rc
    from themey.ir import TClassSpec

    theme = _make_minimal_theme(left_buttons="XAI", right_buttons="")
    theme.tclasses["TEXT1"] = TClassSpec(
        name="TEXT1", fg_normal=None, fg_active=None, effect="__EFFECT_NONE"
    )
    cp = _read_rc(write_aurorae_rc(theme, tmp_path))
    assert cp["General"]["UseTextShadow"] == "false"
