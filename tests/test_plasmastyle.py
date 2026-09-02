"""Unit tests for generate/plasmastyle.py — the Plasma Style package writer.

Hand-built Themes with tmp PNG art (the ``test_button_svg`` idiom); the
Aliens pipeline canary lives in ``test_pipeline_plasmastyle.py``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PIL import Image

from themey.generate import plasmastyle
from themey.generate.qmldeco.resolver import scale_px
from themey.ir import (
    FILL_TILE,
    BorderSpec,
    IClassSpec,
    Palette,
    TClassSpec,
    Theme,
    TooltipSpec,
)

SVG_NS = "http://www.w3.org/2000/svg"
XLINK = "{http://www.w3.org/1999/xlink}href"

_IC_DEFAULTS: dict[str, None] = {
    "normal": None, "normal_active": None, "hilited": None,
    "hilited_active": None, "clicked": None, "clicked_active": None,
    "normal_sticky": None, "normal_active_sticky": None,
}


def _png(tmp_path: Path, name: str, size=(16, 16), color=(200, 60, 60, 255)) -> Path:
    p = tmp_path / name
    Image.new("RGBA", size, color).save(p, format="PNG")
    return p


def _iclass(name: str, edge=(2, 2, 2, 2), padding=(0, 0, 0, 0), **states) -> IClassSpec:
    return IClassSpec(
        name=name, edge_scaling=edge, padding=padding,
        **{**_IC_DEFAULTS, **states},
    )


def _theme(
    tmp_path: Path,
    iclasses: dict[str, IClassSpec],
    tclasses: dict[str, TClassSpec] | None = None,
    scale: float = 1,
    tooltips: dict[str, TooltipSpec] | None = None,
) -> Theme:
    return Theme(
        name="TestStyle",
        display_name="TestStyle",
        author=None,
        scale=scale,
        asset_root=tmp_path,
        border=BorderSpec(
            name="DEFAULT", border_size_left=4, border_size_right=4,
            border_size_top=18, border_size_bottom=4, parts=(),
        ),
        iclasses=iclasses,
        tclasses=tclasses or {},
        button_codes={},
        left_buttons="",
        right_buttons="",
        palette=Palette(
            titlebar_active=(64, 64, 64), titlebar_inactive=(128, 128, 128),
            text_active=(255, 255, 255), text_inactive=(192, 192, 192),
        ),
        tooltips=tooltips or {},
    )


def _tclass(name: str, fg=(200, 200, 150), fg_active=None) -> TClassSpec:
    return TClassSpec(name=name, fg_normal=fg, fg_active=fg_active)


def _ids(svg: ET.Element) -> set[str]:
    return {e.get("id") for e in svg.iter() if e.get("id")}


# ------------------------------------------------------------------ #
# Panel background
# ------------------------------------------------------------------ #


def test_panel_background_from_art_middle_stretches(tmp_path: Path) -> None:
    """Small-cap opaque bar art becomes a real 9-part panel set with a
    STRETCHED middle — no hint-tile-center anywhere: E16 renders every
    iclass middle by Imlib2 border-scale (caps pinned, middle stretched),
    and tiling repeated HandOfGod's capless cloud photo and
    NorthernLights' 58 px aurora trough across the bar (chris's top-bar
    screenshots, 2026-09-01). Cap-hugging margin hints: 2 px caps −
    4 px smallSpacing floors at the 1 px minimum that keeps the rect
    emitted."""
    png = _png(tmp_path, "dragbar.png")  # solid, 16x16, caps 2/2/2/2
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(2, 2, 2, 2), normal=png
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    ids = _ids(svg)
    assert {"topleft", "top", "topright", "left", "center", "right",
            "bottomleft", "bottom", "bottomright"} <= ids
    assert "hint-tile-center" not in ids
    assert "hint-stretch-borders" in ids
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for side in ("left", "right", "top", "bottom"):
        assert by_id[f"hint-{side}-margin"].get("width") == "1"
    # Real art: embedded images, not tint rects.
    assert any(e.tag.endswith("image") for e in svg.iter())
    assert any(
        "panel background from iclass DESKTOP_DRAGBUTTON_HORIZ" in n
        for n in theme.notes
    )
    # A capless (center-only) set stretches too, same rule.
    capless = _png(tmp_path, "cloud.png", size=(128, 64))
    theme2 = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass(
            "ICONBOX_HORIZONTAL", edge=(0, 0, 0, 0), normal=capless
        ),
    })
    svg2 = plasmastyle.build_panel_background(theme2)
    assert "hint-tile-center" not in _ids(svg2)


def test_panel_margin_hints_hug_the_caps(tmp_path: Path) -> None:
    """The e13 shape: __EDGE_SCALING 5 at scale 2 → 10 px painted caps →
    6 px margin hints (cap − Kirigami smallSpacing), landing Plasma's
    panel padding exactly on the cap art's inner edge. The E16 __PADDING
    is dropped — Panel.qml pads on top of the frame margins, and __PADDING
    + smallSpacing read as an empty trough before the first task button
    (calibrated live on themey_e13, 2026-09-01). A capless axis keeps the
    flat-panel PANEL_MARGIN_REF default at theme scale."""
    png = _png(tmp_path, "iconbox.png", size=(32, 32))
    theme = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass(
            "ICONBOX_HORIZONTAL", edge=(5, 5, 5, 5), padding=(6, 6, 6, 6),
            normal=png,
        ),
    }, scale=2)
    svg = plasmastyle.build_panel_background(theme)
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for side in ("left", "right", "top", "bottom"):
        assert by_id[f"hint-{side}-margin"].get("width") == "6"
    assert any("margin hints hug the cap art" in n for n in theme.notes)
    # Capless top/bottom: PANEL_MARGIN_REF (2 ref px) at scale 2 -> 4 px.
    theme2 = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass(
            "ICONBOX_HORIZONTAL", edge=(5, 5, 0, 0), normal=png
        ),
    }, scale=2)
    svg2 = plasmastyle.build_panel_background(theme2)
    by_id2 = {e.get("id"): e for e in svg2.iter() if e.get("id")}
    assert by_id2["hint-left-margin"].get("width") == "6"
    assert by_id2["hint-top-margin"].get("width") == "4"


def test_panel_background_cap_guard_falls_back_to_tint(tmp_path: Path) -> None:
    """Giant caps on the bar's THICKNESS axis trip the cap guard; with no
    other candidate the panel degrades to the flat tint."""
    png = _png(tmp_path, "dragbar.png", size=(160, 120))  # solid (200, 60, 60)
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(4, 4, 50, 50), normal=png
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    assert not any(e.tag.endswith("image") for e in svg.iter())
    center = next(e for e in svg.iter() if e.get("id") == "center")
    style = center.get("style", "")
    assert "fill:#c83c3c" in style  # dominant of the (200, 60, 60) art
    assert "opacity:0.85" in style
    assert any(
        "rejected for the panel background" in n and "caps" in n
        for n in theme.notes
    )
    assert any("translucent tint" in n for n in theme.notes)


def test_panel_background_shaped_guard_falls_back(tmp_path: Path) -> None:
    """>10%-transparent art is shaped (1-bit E16 mask) — rejected."""
    p = tmp_path / "shaped.png"
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for x in range(16):
        for y in range(6):  # 6/16 opaque rows -> 62% transparent
            im.putpixel((x, y), (10, 200, 10, 255))
    im.save(p, format="PNG")
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", normal=p
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    assert not any(e.tag.endswith("image") for e in svg.iter())
    assert any(
        "rejected for the panel background" in n and "shaped" in n
        for n in theme.notes
    )


def test_panel_background_guard_falls_through_to_next_source(
    tmp_path: Path,
) -> None:
    """Aliens' census shape: dragbar rejected (133+28 length caps past
    PANEL_MAX_REF_LENGTH_CAPS) -> the iconbox trough (small caps) backs the
    panel instead."""
    big = _png(tmp_path, "dragbar.png", size=(216, 23))
    small = _png(tmp_path, "iconbox.png", color=(20, 90, 20, 255))
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(133, 28, 0, 0), normal=big
        ),
        "ICONBOX_HORIZONTAL": _iclass(
            "ICONBOX_HORIZONTAL", edge=(4, 4, 4, 4), normal=small
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    assert any(e.tag.endswith("image") for e in svg.iter())
    assert any(
        "panel background from iclass ICONBOX_HORIZONTAL" in n
        for n in theme.notes
    )


def test_panel_wordmark_caps_go_to_north_south_sets(tmp_path: Path) -> None:
    """AE-style dragbar (edge 50 4 4 4, 32 px thick): the 50 px wordmark
    cap is pinned at the bar's left exactly as E16 drew it — but ONLY in
    the north-/south- sets. The unprefixed set stays cap-free (here: the
    tint) because plasmashell turns its caps into every panel's minimum
    thickness (e13's 60 px caps forced the 60 px iconbox panel to 120 px,
    live 2026-09-01)."""
    png = _png(tmp_path, "dragbar.png", size=(128, 32))
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(50, 4, 4, 4), normal=png
        ),
    })
    spec = theme.iclasses["DESKTOP_DRAGBUTTON_HORIZ"]
    strict = plasmastyle._panel_art_guard(spec)
    assert strict is not None and "shared set" in strict
    assert plasmastyle._panel_art_guard(spec, wordmark=True) is None
    svg = plasmastyle.build_panel_background(theme)
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert by_id["center"].tag.endswith("rect")  # unprefixed = tint
    assert "left" not in by_id or by_id["left"].tag.endswith("rect")
    for prefix in ("north-", "south-"):
        assert by_id[f"{prefix}center"].tag.endswith("g")
        assert by_id[f"{prefix}hint-left-margin"].get("width") == str(50 - 4)
    assert any(
        "horizontal panels wear the DESKTOP_DRAGBUTTON_HORIZ wordmark art" in n
        for n in theme.notes
    )
    assert not any(i.startswith(("west-", "east-")) for i in by_id)


def test_panel_wordmark_caps_rejected_on_thin_bars(tmp_path: Path) -> None:
    """e13's shape: a 6 px-tall dragbar with 60 px wordmark caps plus an
    iconbox trough. A foreign bottom panel stretches the bar to its 60 px
    thickness, smearing the wordmark ten times taller (live 2026-09-01) —
    so no south- set; the trough backs the shared set. (north- is exempt
    since themey's own dragbar panel is 16 ref px thick — see
    test_north_wordmark_accepts_thin_strip.)"""
    thin = _png(tmp_path, "dragbar.png", size=(300, 6))
    small = _png(tmp_path, "iconbox.png", color=(20, 90, 20, 255))
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(60, 60, 0, 0), normal=thin
        ),
        "ICONBOX_HORIZONTAL": _iclass(
            "ICONBOX_HORIZONTAL", edge=(4, 4, 4, 4), normal=small
        ),
    })
    reason = plasmastyle._panel_art_guard(
        theme.iclasses["DESKTOP_DRAGBUTTON_HORIZ"], wordmark=True
    )
    assert reason is not None and "thin" in reason
    svg = plasmastyle.build_panel_background(theme)
    ids = _ids(svg)
    assert not any(i.startswith("south-") for i in ids)
    assert any(
        "panel background from iclass ICONBOX_HORIZONTAL" in n for n in theme.notes
    )


def test_panel_guard_is_axis_aware(tmp_path: Path) -> None:
    """Wordmark mode: length axis (L+R for a horizontal bar, T+B for a
    vertical one) is generous, the thickness axis keeps the strict
    PANEL_MAX_REF_CAPS. Strict mode caps both axes at PANEL_MAX_REF_CAPS."""
    wide = _png(tmp_path, "h.png", size=(300, 120))
    tall = _png(tmp_path, "v.png", size=(120, 300))
    horiz_ok = _iclass("DESKTOP_DRAGBUTTON_HORIZ", edge=(50, 4, 4, 4), normal=wide)
    horiz_thick = _iclass("DESKTOP_DRAGBUTTON_HORIZ", edge=(50, 50, 50, 50), normal=wide)
    horiz_long = _iclass("DESKTOP_DRAGBUTTON_HORIZ", edge=(200, 2, 0, 0), normal=wide)
    vert_ok = _iclass("DESKTOP_DRAGBUTTON_VERT", edge=(4, 4, 50, 4), normal=tall)
    vert_thick = _iclass("DESKTOP_DRAGBUTTON_VERT", edge=(50, 4, 4, 4), normal=tall)
    assert plasmastyle._panel_art_guard(horiz_ok, wordmark=True) is None
    assert plasmastyle._panel_art_guard(vert_ok, wordmark=True) is None
    strict = plasmastyle._panel_art_guard(horiz_ok)
    assert strict is not None and "shared set" in strict
    for spec in (horiz_thick, vert_thick):
        for mode in (False, True):
            reason = plasmastyle._panel_art_guard(spec, wordmark=mode)
            assert reason is not None and "thickness" in reason
    reason = plasmastyle._panel_art_guard(horiz_long, wordmark=True)
    assert reason is not None and str(plasmastyle.PANEL_MAX_REF_LENGTH_CAPS) in reason


def test_panel_background_scheme_fallback_without_art(tmp_path: Path) -> None:
    from themey.analyze.colors import default_scheme

    theme = _theme(tmp_path, {})
    svg = plasmastyle.build_panel_background(theme)
    assert svg is not None  # never skipped — colors-only themes get a tint
    r, g, b = default_scheme().window.background_normal
    center = next(e for e in svg.iter() if e.get("id") == "center")
    assert f"fill:#{r:02x}{g:02x}{b:02x}" in center.get("style", "")
    assert any("the sampled color scheme" in n for n in theme.notes)


def test_panel_background_west_east_sets_from_vertical_art(
    tmp_path: Path,
) -> None:
    """A vertical bar iclass passing the guards adds west-/east- sets so
    the left-edge furniture panels wear the vertical art."""
    h = _png(tmp_path, "h.png")
    v = _png(tmp_path, "v.png", color=(60, 60, 200, 255))
    theme = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass("ICONBOX_HORIZONTAL", normal=h),
        "ICONBOX_VERTICAL": _iclass(
            "ICONBOX_VERTICAL", normal=v, padding=(1, 1, 3, 3)
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    ids = _ids(svg)
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for prefix in ("west-", "east-"):
        assert f"{prefix}center" in ids
        # Cap-hugging: hints come from the 2 px caps (floored at 1), NOT
        # from the iclass __PADDING (1, 1, 3, 3), which is dropped.
        assert by_id[f"{prefix}hint-top-margin"].get("width") == "1"
    # No vertical art -> no west/east sets (the unprefixed set serves all).
    theme2 = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass("ICONBOX_HORIZONTAL", normal=h),
    })
    svg2 = plasmastyle.build_panel_background(theme2)
    assert not any(
        i.startswith(("north-", "south-", "east-", "west-")) for i in _ids(svg2)
    )


def test_zero_edge_scaling_is_center_only(tmp_path: Path) -> None:
    png = _png(tmp_path, "tt.png")
    theme = _theme(tmp_path, {
        "TT_MAIN": _iclass("TT_MAIN", edge=(0, 0, 0, 0), normal=png),
    })
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    assert _ids(svg) == {"center"}


def test_horizontal_only_edges_drop_top_bottom_row(tmp_path: Path) -> None:
    """Aliens-dragbar shape: L R 0 0 → left/center/right only (FrameSvg then
    reports 0 top/bottom borders, which is correct)."""
    png = _png(tmp_path, "menu.png")
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", edge=(6, 3, 0, 0), normal=png),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert _ids(svg) == {"left", "center", "right", "hint-stretch-borders"}


def test_oversized_caps_shrink_to_fit_with_note(tmp_path: Path) -> None:
    """E16 tolerates overlapping caps (e13's dragbar: 70 70 5 5 on a
    121-px image) — shrink proportionally, never stretch the whole image
    (a stretched cap smears its baked-in art across the surface)."""
    png = _png(tmp_path, "menu.png", size=(121, 16))
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", edge=(70, 70, 5, 5), normal=png),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"topleft", "left", "center", "right", "bottomright"} <= ids
    left = next(
        e for e in svg.iter() if e.get("id") == "left"
    )
    assert next(iter(left)).get("width") == "60"  # int(70 * 121/140)
    assert any("caps shrunk" in n for n in theme.notes)


def test_exact_fit_caps_keep_art_but_gain_center(tmp_path: Path) -> None:
    """Caps summing to exactly the image size are authored cap-only art —
    no shrink note fires, but ONE px is shaved off the larger cap so a
    real center survives: FrameSvg's hasElementPrefix checks exactly
    <prefix>center, and a center-less set paints NOTHING (the invisible
    Aliens slider groove, live 2026-08-31)."""
    png = _png(tmp_path, "base.png", size=(8, 8))
    theme = _theme(tmp_path, {
        "TT_MAIN": _iclass("TT_MAIN", edge=(4, 4, 0, 0), normal=png),
    })
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert {"left", "center", "right"} <= by_id.keys()
    assert next(iter(by_id["left"])).get("width") == "3"  # 4 shaved to 3
    assert next(iter(by_id["center"])).get("width") == "1"
    assert next(iter(by_id["right"])).get("width") == "4"
    assert not any("caps shrunk" in n for n in theme.notes)


def test_shave_for_center() -> None:
    assert plasmastyle._shave_for_center(4, 4, 8) == (3, 4)  # larger-first tie
    assert plasmastyle._shave_for_center(5, 5, 10) == (4, 5)
    assert plasmastyle._shave_for_center(4, 4, 16) == (4, 4)  # fits, untouched
    assert plasmastyle._shave_for_center(0, 0, 8) == (0, 0)  # center-only
    assert plasmastyle._shave_for_center(1, 0, 1) == (0, 0)  # degenerate 1px
    assert plasmastyle._shave_for_center(2, 0, 2) == (1, 0)


def test_no_file_ships_tile_center_hint(tmp_path: Path) -> None:
    """E16 stretches iclass middles everywhere (Imlib2 border-scale) — NO
    shipped file may carry hint-tile-center. The panel used to be the one
    exception ("E16 tiles bar troughs") until it repeated HandOfGod's and
    NorthernLights' photographic troughs across the bar (live 2026-09-01).
    Build every file from a maximal synthetic theme and check the census."""
    art = _png(tmp_path, "art.png")
    art2 = _png(tmp_path, "art2.png", color=(40, 40, 200, 255))
    iclasses = {
        name: _iclass(name, normal=art, hilited=art2, normal_active=art2)
        for name in (
            "DESKTOP_DRAGBUTTON_HORIZ", "MENU_BG", "TT_MAIN", "DIALOG_BUTTON",
            "MENU_SEL", "ICONBOX_SCROLLBAR_KNOB_VERTICAL",
            "ICONBOX_ARROW_UP", "ICONBOX_ARROW_DOWN", "ICONBOX_ARROW_LEFT",
            "ICONBOX_ARROW_RIGHT", "DIALOG_WIDGET_CHECK_BUTTON",
            "DIALOG_WIDGET_RADIO_BUTTON",
            "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL",
            "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL",
            "DIALOG_WIDGET_SEPARATOR", "DIALOG_WIDGET_AREA", "PAGER_SEL",
        )
    }
    theme = _theme(tmp_path, iclasses)
    for rel, builder in plasmastyle._BUILDERS:
        svg = builder(theme)
        if svg is None:
            continue
        has_tile = any("tile-center" in i for i in _ids(svg))
        assert not has_tile, f"{rel} must not tile its middle"


# ------------------------------------------------------------------ #
# Dialog background — composite frame from MENU_T/B/L/R (+ corners)
# ------------------------------------------------------------------ #


def test_dialog_composite_frame_from_menu_strips(tmp_path: Path) -> None:
    """Aliens' shape: MENU_T/MENU_B strips + opaque DIALOG center, no L/R
    strips -> top/bottom/center only; corner pieces are dropped (a corner
    paints at leftWidth x topHeight, and with no left strip that is 0 wide)."""
    t = _png(tmp_path, "menu_t.png", size=(115, 6))
    b = _png(tmp_path, "menu_b.png", size=(206, 4))
    tl = _png(tmp_path, "menu_tl.png", size=(11, 23))
    dialog = _png(tmp_path, "bg.png", size=(64, 64), color=(90, 90, 100, 255))
    theme = _theme(tmp_path, {
        "MENU_T": _iclass("MENU_T", normal=t),
        "MENU_B": _iclass("MENU_B", normal=b),
        "MENU_TL": _iclass("MENU_TL", normal=tl),
        "DIALOG": _iclass("DIALOG", edge=(0, 0, 0, 0), normal=dialog),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"top", "bottom", "center"} <= ids
    assert "left" not in ids and "right" not in ids
    assert "topleft" not in ids
    assert "hint-stretch-borders" in ids
    assert any(
        "composed from menu frame pieces" in n for n in theme.notes
    ), theme.notes
    assert any("MENU_TL" in n and "dropped" in n for n in theme.notes)


def test_dialog_composite_corner_with_matching_strips(tmp_path: Path) -> None:
    """A corner ships only when BOTH adjacent strips exist and the corner's
    dims match theirs (FrameSvg stretches the corner to exactly
    leftWidth x topHeight — sectionRect, ksvg 6.24)."""
    t = _png(tmp_path, "menu_t.png", size=(60, 6))
    left = _png(tmp_path, "menu_l.png", size=(6, 60))
    tl = _png(tmp_path, "menu_tl.png", size=(6, 6))
    dialog = _png(tmp_path, "bg.png", size=(64, 64))
    theme = _theme(tmp_path, {
        "MENU_T": _iclass("MENU_T", normal=t),
        "MENU_L": _iclass("MENU_L", normal=left),
        "MENU_TL": _iclass("MENU_TL", normal=tl),
        "DIALOG": _iclass("DIALOG", normal=dialog),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert "topleft" in _ids(svg)


def test_dialog_composite_corner_dropped_on_dim_mismatch(tmp_path: Path) -> None:
    """Aliens' MENU_TL: 23 px tall against a 6 px top strip — squashing it
    to the strip thickness mangles the art, so it is dropped with a note."""
    t = _png(tmp_path, "menu_t.png", size=(60, 6))
    left = _png(tmp_path, "menu_l.png", size=(6, 60))
    tl = _png(tmp_path, "menu_tl.png", size=(11, 23))
    dialog = _png(tmp_path, "bg.png", size=(64, 64))
    theme = _theme(tmp_path, {
        "MENU_T": _iclass("MENU_T", normal=t),
        "MENU_L": _iclass("MENU_L", normal=left),
        "MENU_TL": _iclass("MENU_TL", normal=tl),
        "DIALOG": _iclass("DIALOG", normal=dialog),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert "topleft" not in _ids(svg)
    assert any("MENU_TL" in n and "dropped" in n for n in theme.notes)


def test_dialog_composite_center_mandatory_flat_fallback(tmp_path: Path) -> None:
    """Strips with NO center source still get a center element (a flat
    dominant-color rect) — a center-less set paints NOTHING."""
    t = _png(tmp_path, "menu_t.png", size=(60, 6), color=(10, 120, 10, 255))
    theme = _theme(tmp_path, {
        "MENU_T": _iclass("MENU_T", normal=t),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    ids = _ids(svg)
    assert "center" in ids and "top" in ids
    center = next(e for e in svg.iter() if e.get("id") == "center")
    # Flat rect, not an image.
    assert not any(c.tag.endswith("image") for c in center.iter())


def test_dialog_without_pieces_keeps_single_set_path(tmp_path: Path) -> None:
    """e13's shape: no MENU_T/B/L/R -> the classic one-set emission."""
    menu = _png(tmp_path, "menu.png")
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", edge=(5, 5, 5, 5), normal=menu),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert not any("composed from menu frame pieces" in n for n in theme.notes)


def test_menu_sub_and_root_titlebar_noted_not_shipped(tmp_path: Path) -> None:
    menu = _png(tmp_path, "menu.png")
    sub = _png(tmp_path, "sub.png")
    tb = _png(tmp_path, "tb.png")
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", normal=menu),
        "MENU_SUB": _iclass("MENU_SUB", normal=sub),
        "MENU_TITLE_BAR": _iclass("MENU_TITLE_BAR", normal=tb),
    })
    plasmastyle.build_dialog_background(theme)
    assert any("MENU_SUB" in n for n in theme.notes)
    assert any("MENU_TITLE_BAR" in n for n in theme.notes)


# ------------------------------------------------------------------ #
# Tasks — widgets/tasks.svg from the iconbox button art
# ------------------------------------------------------------------ #


def _arrow_iclasses(tmp_path: Path) -> dict[str, IClassSpec]:
    return {
        name: _iclass(name, normal=_png(tmp_path, f"{name}.png", size=(8, 8)))
        for name in (
            "ICONBOX_ARROW_UP", "ICONBOX_ARROW_DOWN",
            "ICONBOX_ARROW_LEFT", "ICONBOX_ARROW_RIGHT",
        )
    }


def test_tasks_all_prefixes_ship_even_from_normal_only_art(
    tmp_path: Path,
) -> None:
    """Per-FILE fallback means a partial prefix set paints nothing for the
    missing states — every prefix ships, reusing normal art."""
    png = _png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png, padding=(2, 2, 2, 2)
        ),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    ids = _ids(svg)
    for prefix in (
        "normal-", "minimized-", "hover-", "attention-", "progress-",
        "focus-",
    ):
        assert f"{prefix}center" in ids, prefix
        assert f"{prefix}hint-left-margin" in ids, prefix
    assert "center" in ids  # unprefixed launcher set
    assert not any("tile-center" in i for i in ids)
    assert any(
        "task frames from iclass DEFAULT_ICON_BUTTON" in n for n in theme.notes
    )


def test_tasks_focus_wears_clicked_art(tmp_path: Path) -> None:
    """The active task wears the depressed button — E16's pressed-in look."""
    normal = _png(tmp_path, "n.png", size=(16, 16))
    clicked = _png(tmp_path, "c.png", size=(24, 24), color=(10, 10, 10, 255))
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=normal, clicked=clicked
        ),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    focus_img = next(iter(by_id["focus-center"]))
    normal_img = next(iter(by_id["normal-center"]))
    # 24x24 art with 2/2 caps vs 16x16: the center widths differ.
    assert focus_img.get("width") != normal_img.get("width")


def test_tasks_group_expanders_from_all_four_arrows(tmp_path: Path) -> None:
    png = _png(tmp_path, "iconbtn.png")
    iclasses = {"DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png)}
    iclasses.update(_arrow_iclasses(tmp_path))
    theme = _theme(tmp_path, iclasses)
    svg = plasmastyle.build_tasks(theme)
    assert svg is not None
    ids = _ids(svg)
    for direction in ("left", "right", "top", "bottom"):
        assert f"group-expander-{direction}" in ids


def test_tasks_group_expanders_omitted_when_partial(tmp_path: Path) -> None:
    png = _png(tmp_path, "iconbtn.png")
    iclasses = {"DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png)}
    arrows = _arrow_iclasses(tmp_path)
    del arrows["ICONBOX_ARROW_LEFT"]
    iclasses.update(arrows)
    theme = _theme(tmp_path, iclasses)
    svg = plasmastyle.build_tasks(theme)
    assert svg is not None
    assert not any(i.startswith("group-expander-") for i in _ids(svg))
    assert any("group expanders" in n for n in theme.notes)


def test_tasks_skipped_without_iconbox_button_art(tmp_path: Path) -> None:
    """Frames ON with no button art: no file, so Breeze paints the frames."""
    theme = _theme(tmp_path, {})
    assert plasmastyle.build_tasks(theme, iconbox_frames="on") is None


def test_tasks_falls_back_to_dock_button(tmp_path: Path) -> None:
    png = _png(tmp_path, "dock.png")
    theme = _theme(tmp_path, {
        "DEFAULT_DOCK_BUTTON": _iclass("DEFAULT_DOCK_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    assert any(
        "task frames from iclass DEFAULT_DOCK_BUTTON" in n for n in theme.notes
    )


# ------------------------------------------------------------------ #
# Button / viewitem / scrollbar / arrows
# ------------------------------------------------------------------ #


def test_button_prefixes_include_focus_and_state_fallback(tmp_path: Path) -> None:
    """Only normal art: hover/pressed/focus sets still ship, reusing it."""
    png = _png(tmp_path, "btn.png")
    theme = _theme(tmp_path, {
        "DIALOG_BUTTON": _iclass("DIALOG_BUTTON", normal=png, padding=(10, 10, 10, 10)),
    })
    svg = plasmastyle.build_button(theme)
    assert svg is not None
    ids = _ids(svg)
    for prefix in ("normal-", "hover-", "pressed-", "focus-"):
        assert f"{prefix}center" in ids
        assert f"{prefix}hint-left-margin" in ids
    assert not any(i.startswith("toolbutton-") for i in ids)


def test_button_prefers_dialog_widget_button(tmp_path: Path) -> None:
    """DIALOG_WIDGET_BUTTON is E16's real push button (dialog.c:844);
    DIALOG_BUTTON dresses the background-chooser thumbnails. 62/229 corpus
    themes author them differently."""
    widget = _png(tmp_path, "widget.png", color=(10, 200, 10, 255))
    chooser = _png(tmp_path, "chooser.png", color=(200, 10, 10, 255))
    theme = _theme(tmp_path, {
        "DIALOG_BUTTON": _iclass("DIALOG_BUTTON", normal=chooser),
        "DIALOG_WIDGET_BUTTON": _iclass("DIALOG_WIDGET_BUTTON", normal=widget),
    })
    svg = plasmastyle.build_button(theme)
    assert svg is not None
    assert _tile_image(svg, "normal-center").getpixel((0, 0))[:3] == (10, 200, 10)
    assert any("widget buttons from iclass DIALOG_WIDGET_BUTTON" in n for n in theme.notes)
    scheme = plasmastyle.style_scheme(theme, shipped=frozenset({plasmastyle.BUTTON_SVG}))
    assert scheme.button.background_normal == (10, 200, 10)
    assert any("colors Button from DIALOG_WIDGET_BUTTON art" in n for n in theme.notes)

    only_chooser = _theme(tmp_path, {
        "DIALOG_BUTTON": _iclass("DIALOG_BUTTON", normal=chooser),
    })
    svg = plasmastyle.build_button(only_chooser)
    assert svg is not None
    assert _tile_image(svg, "normal-center").getpixel((0, 0))[:3] == (200, 10, 10)


def test_viewitem_selected_plus_hover_and_normal_omission(tmp_path: Path) -> None:
    hi = _png(tmp_path, "sel.png")
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", hilited=hi),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"hover-center", "selected-center", "selected+hover-center"} <= ids
    # No normal art → no normal- set (unhovered rows stay chrome-free).
    assert "normal-center" not in ids


def test_viewitem_no_normal_set_even_with_normal_art(tmp_path: Path) -> None:
    """PlasmaExtras.Highlight paints ``normal`` for a current-but-unhovered
    item at 0.6 opacity (Kicker, folder views); E16 painted MENU_SEL's
    normal art on EVERY row. Neither matches, Breeze ships no ``normal``
    prefix — so themey never does either (StarEnli's tan bars over the
    Favorites/Help rows, 2026-09-01)."""
    n = _png(tmp_path, "n.png")
    hi = _png(tmp_path, "h.png")
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", normal=n, hilited=hi),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    ids = _ids(svg)
    assert not any(i.startswith("normal-") for i in ids)
    assert {"hover-center", "selected-center", "selected+hover-center"} <= ids


def _pill_png(tmp_path: Path, name: str, size: tuple[int, int]) -> Path:
    """Opaque rounded-end strip (corners cut by a 1-bit shape mask)."""
    w, h = size
    im = Image.new("RGBA", size, (0, 0, 0, 0))
    r = h // 2
    for y in range(h):
        for x in range(w):
            cx = min(max(x, r), w - 1 - r)
            if (x - cx) ** 2 + (y - r) ** 2 <= r * r:
                im.putpixel((x, y), (220, 120, 80, 255))
    p = tmp_path / name
    im.save(p, format="PNG")
    return p


def test_viewitem_caps_never_outgrow_a_plasma_list_row(tmp_path: Path) -> None:
    """StarEnli's 27 px MENU_SEL pill at 1.5x: 12 ref px caps would scale
    to 18+18 = 36 output px, more than Kickoff's ~30 px row — FrameSvg
    then paints a degenerate sliver. Past VIEWITEM_MAX_ROW_CHROME_PX the
    set stays at source scale (12+12) with a note."""
    pill = _pill_png(tmp_path, "pill.png", (120, 27))
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(64, 14, 2, 2), hilited=pill),
    }, scale=1.5)
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    top = _tile_image(svg, "hover-top")
    bottom = _tile_image(svg, "hover-bottom")
    assert top.height + bottom.height <= plasmastyle.VIEWITEM_MAX_ROW_CHROME_PX
    assert top.height == 12
    assert any("kept at source scale" in n and "36 px of caps" in n for n in theme.notes)

    # A 16 px bevel strip declares 3 px caps → 5+5 output px at 1.5x fits,
    # so it scales like everything else.
    strip = _png(tmp_path, "strip.png", size=(213, 16), color=(150, 90, 60, 255))
    theme2 = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 3, 3), hilited=strip),
    }, scale=1.5)
    svg2 = plasmastyle.build_viewitem(theme2)
    assert svg2 is not None
    assert _tile_image(svg2, "hover-top").height == scale_px(3, 1.5)
    assert _tile_image(svg2, "hover-center").width > 0
    assert not any("kept at source scale" in n for n in theme2.notes)


def test_arrows_all_four_or_skip(tmp_path: Path) -> None:
    pngs = {d: _png(tmp_path, f"ar_{d}.png", size=(8, 8)) for d in "udl"}
    iclasses = {
        "ICONBOX_ARROW_UP": _iclass("ICONBOX_ARROW_UP", normal=pngs["u"]),
        "ICONBOX_ARROW_DOWN": _iclass("ICONBOX_ARROW_DOWN", normal=pngs["d"]),
        "ICONBOX_ARROW_LEFT": _iclass("ICONBOX_ARROW_LEFT", normal=pngs["l"]),
    }
    theme = _theme(tmp_path, iclasses)
    assert plasmastyle.build_arrows(theme) is None  # RIGHT missing → skip file

    iclasses["ICONBOX_ARROW_RIGHT"] = _iclass(
        "ICONBOX_ARROW_RIGHT", normal=_png(tmp_path, "ar_r.png", size=(8, 8))
    )
    theme = _theme(tmp_path, iclasses)
    svg = plasmastyle.build_arrows(theme)
    assert svg is not None
    assert {"up-arrow", "down-arrow", "left-arrow", "right-arrow"} <= _ids(svg)


def test_scrollbar_ids_and_size_hint(tmp_path: Path) -> None:
    knob = _png(tmp_path, "knob.png", size=(6, 14))
    base = _png(tmp_path, "base.png", size=(6, 14))
    theme = _theme(tmp_path, {
        "ICONBOX_SCROLLBAR_KNOB_VERTICAL": _iclass(
            "ICONBOX_SCROLLBAR_KNOB_VERTICAL", normal=knob
        ),
        "ICONBOX_SCROLLBAR_BASE_VERTICAL": _iclass(
            "ICONBOX_SCROLLBAR_BASE_VERTICAL", edge=(1, 1, 4, 4), normal=base
        ),
    }, scale=2)
    svg = plasmastyle.build_scrollbar(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"slider-center", "mouseover-slider-center",
            "background-vertical-center", "hint-scrollbar-size"} <= ids
    assert "background-horizontal-center" not in ids
    hint = next(e for e in svg.iter() if e.get("id") == "hint-scrollbar-size")
    # Knob thickness = the vertical knob's width, scaled.
    assert hint.get("width") == str(scale_px(6, 2))
    assert any("both orientations" in n for n in theme.notes)


def test_scrollbar_size_hint_clamped_for_oversized_knob(tmp_path: Path) -> None:
    """E16 stretched knob art into a slim track — a 28-px-wide knob image
    must not become a 56-px-wide Plasma scrollbar (live e13 regression)."""
    knob = _png(tmp_path, "knob.png", size=(28, 140))
    theme = _theme(tmp_path, {
        "ICONBOX_SCROLLBAR_KNOB_VERTICAL": _iclass(
            "ICONBOX_SCROLLBAR_KNOB_VERTICAL", normal=knob
        ),
    }, scale=2)
    svg = plasmastyle.build_scrollbar(theme)
    assert svg is not None
    hint = next(e for e in svg.iter() if e.get("id") == "hint-scrollbar-size")
    assert hint.get("width") == str(
        scale_px(plasmastyle.SCROLLBAR_MAX_REF_THICKNESS, 2)
    )
    assert any("clamped" in n for n in theme.notes)


def test_viewitem_caps_pin_highlight_cross_section() -> None:
    """Zero declared edge on PILL art → caps at the cross-section radius;
    larger declared caps survive up to VIEWITEM_MAX_REF_CAP."""
    caps, branch = plasmastyle._viewitem_caps((0, 0, 0, 0), 164, 20)
    assert caps == (9, 9, 9, 9) and branch == "pill"
    caps, branch = plasmastyle._viewitem_caps((20, 20, 2, 2), 202, 31)
    assert caps == (12, 12, 12, 12) and branch == "pill"
    # Tiny art never degenerates below a 1-px cap or above the half-size.
    caps, _ = plasmastyle._viewitem_caps((0, 0, 0, 0), 3, 3)
    assert caps == (1, 1, 1, 1)


def test_viewitem_caps_honor_declared_edge_for_menu_backgrounds() -> None:
    """47 corpus themes point MENU_SEL at a whole menu background (64x64 …
    484x400); E16 squished it into a ~30 px row keeping only the declared
    caps crisp. The radius heuristic turned those into 31-199 px caps on a
    Kickoff row — the declared edge is honored instead, clamped to
    VIEWITEM_MAX_REF_CAP."""
    caps, branch = plasmastyle._viewitem_caps((6, 22, 1, 1), 256, 256)
    assert caps == (6, 12, 1, 1) and branch == "declared"
    caps, branch = plasmastyle._viewitem_caps((0, 0, 0, 0), 64, 64)
    assert branch == "declared"
    assert all(c <= plasmastyle.VIEWITEM_MAX_REF_CAP for c in caps)
    # StarEnli: 210x27 pill with a 64 px declared left cap → clamped, symmetric.
    caps, branch = plasmastyle._viewitem_caps((64, 14, 3, 3), 210, 27)
    assert branch == "pill"
    assert caps[0] == caps[1] == plasmastyle.VIEWITEM_MAX_REF_CAP
    # Every cap also stays under half the art on its axis.
    caps, _ = plasmastyle._viewitem_caps((30, 30, 30, 30), 41, 9)
    assert caps[2] <= 4 and caps[3] <= 4


def _tile_image(svg: ET.Element, element_id: str) -> Image.Image:
    """Decode the embedded PNG of one frame element."""
    import base64
    import io

    for el in svg.iter():
        if el.get("id") == element_id:
            img_el = el.find(f"{{{SVG_NS}}}image")
            assert img_el is not None, f"{element_id} has no image"
            data = img_el.get(XLINK)
            assert data is not None
            return Image.open(io.BytesIO(base64.b64decode(data.split(",", 1)[1])))
    raise AssertionError(f"no element {element_id}")


_YELLOW_FILL = (255, 218, 2, 255)
_YELLOW_DARK = (20, 20, 20, 255)
#: Per row of Yellow's m_selected.png: (first opaque column, dark columns
#: from there; None = the whole row is border). Rows 0-1/20-21 are blank.
_YELLOW_ROWS: dict[int, tuple[int, int | None]] = {
    2: (7, None), 3: (4, None), 4: (3, 4), 5: (2, 3), 6: (1, 3), 7: (1, 2),
    8: (1, 2), 9: (0, 2), 10: (0, 2), 11: (0, 2), 12: (0, 2), 13: (1, 2),
    14: (1, 2), 15: (1, 3), 16: (2, 3), 17: (3, 4), 18: (4, None), 19: (7, None),
}


def _yellow_pill(tmp_path: Path) -> Path:
    """Replica of Yellow's ``artwork/menustyles/m_selected.png`` (58x22):
    2 px dark top/bottom rows, a dark ROUNDED left end, a flat OPEN right
    end at x=43 (fill straight to the edge, no rim), then 14 fully
    transparent columns."""
    img = Image.new("RGBA", (58, 22), (0, 0, 0, 0))
    for y, (first, dark) in _YELLOW_ROWS.items():
        for x in range(first, 44):
            is_dark = dark is None or x < first + dark
            img.putpixel((x, y), _YELLOW_DARK if is_dark else _YELLOW_FILL)
    png = tmp_path / "m_selected.png"
    img.save(png)
    return png


def _outer_right_rim_is_dark(tile: Image.Image) -> bool:
    """Every row's RIGHTMOST opaque pixel is dark (a border/rim), and there
    is at least one such pixel."""
    seen = False
    for y in range(tile.height):
        for x in range(tile.width - 1, -1, -1):
            r, g, b, a = tile.getpixel((x, y))
            if a >= 128:
                seen = True
                if (r + g + b) / 3 >= 80:
                    return False
                break
    return seen


def test_viewitem_closes_yellow_open_right_end(tmp_path: Path) -> None:
    """Yellow's MENU_SEL pill has a bordered rounded LEFT end and a flat
    OPEN right end (E16 showed the menu background through the gap). The
    right cap sliced from columns 36-43 is pure fill — the border was
    never painted, not clipped — and the highlight rendered with no right
    border on the desktop (chris, 2026-09-01; the E16-faithful see-through
    gutter shipped before f85b1cf was reported as the same defect). The
    open end is closed with the mirrored left cap and the caps go
    symmetric (10/10)."""
    png = _yellow_pill(tmp_path)
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(10, 18, 5, 5), hilited=png),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    for element_id in ("hover-topright", "hover-right", "hover-bottomright"):
        tile = _tile_image(svg, element_id)
        assert _outer_right_rim_is_dark(tile), f"{element_id} has an open right end"
    left = _tile_image(svg, "hover-left")
    right = _tile_image(svg, "hover-right")
    assert left.size == right.size == (10, right.height)
    assert _tile_image(svg, "hover-topleft").size == _tile_image(svg, "hover-topright").size
    # The set spans the opaque art (44 px), not the padded canvas (58 px).
    xs = [
        int(el.get("x", "0")) + int(el.get("width", "0"))
        for el in svg.iter()
        if el.tag.endswith("image")
    ]
    assert max(xs) == 44
    assert any("trimmed" in n and "MENU_SEL" in n for n in theme.notes)
    assert any(
        "MENU_SEL" in n and "open" in n and "right" in n and "closed" in n
        for n in theme.notes
    )


def test_close_open_edges_mirrors_only_open_trimmed_sides(tmp_path: Path) -> None:
    png = _yellow_pill(tmp_path)
    with Image.open(png) as im:
        src = im.convert("RGBA")
    trimmed = plasmastyle._opaque_trim(src, (10, 18, 5, 5))
    assert trimmed is not None
    img, edge, trims = trimmed
    assert img.size == (44, 18) and trims == (0, 14, 2, 2) and edge == (10, 4, 3, 3)
    caps, _ = plasmastyle._viewitem_caps(edge, 44, 18)
    closed_img, closed_caps, closed = plasmastyle._close_open_edges(img, caps, trims)
    assert closed == ("right",)
    assert closed_caps == (10, 10, caps[2], caps[3])
    from PIL import ImageOps
    left_cap = img.crop((0, 0, 10, 18))
    right_cap = closed_img.crop((34, 0, 44, 18))
    assert right_cap.tobytes() == ImageOps.mirror(left_cap).tobytes()
    # Top/bottom were trimmed too but carry their own border rows: untouched.
    assert closed_img.crop((10, 0, 34, 18)).tobytes() == img.crop((10, 0, 34, 18)).tobytes()
    # Untrimmed art (trims None) is returned as-is.
    same_img, same_caps, none_closed = plasmastyle._close_open_edges(img, caps, None)
    assert same_img is img and same_caps == caps and none_closed == ()


def test_viewitem_full_bbox_bevel_is_not_mirrored(tmp_path: Path) -> None:
    """Pager-style bevel art (dark top/left, light bottom/right, opaque to
    every edge) has no transparent margin — nothing is trimmed, so no side
    is ever 'open' and the asymmetric bevel survives untouched."""
    img = Image.new("RGBA", (24, 12), (140, 140, 140, 255))
    for x in range(24):
        img.putpixel((x, 0), (30, 30, 30, 255))
        img.putpixel((x, 11), (240, 240, 240, 255))
    for y in range(12):
        img.putpixel((0, y), (30, 30, 30, 255))
        img.putpixel((23, y), (240, 240, 240, 255))
    png = tmp_path / "p_sel.png"
    img.save(png)
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(2, 2, 2, 2), hilited=png),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    right = _tile_image(svg, "hover-right")
    assert right.getpixel((right.width - 1, 0))[:3] == (240, 240, 240)
    assert not any("closed" in n for n in theme.notes)
    assert not any("trimmed" in n for n in theme.notes)


def _nebula_bevel(tmp_path: Path) -> Path:
    """Replica of Nebula's menu-item-lit.png (68x20): 2 px transparent
    margins, light fill, a dark RIGHT column and BOTTOM row (drop shadow),
    light top/left (lit edges), top-right/bottom-right corners rounded by
    1 px. A raised bevel — its lit top is not an open end."""
    img = Image.new("RGBA", (68, 20), (0, 0, 0, 0))
    for y in range(1, 19):
        for x in range(2, 66):
            img.putpixel((x, y), (90, 170, 190, 255))
    for y in range(2, 19):
        img.putpixel((66, y), (25, 40, 45, 255))
    for x in range(3, 66):
        img.putpixel((x, 18), (25, 40, 45, 255))
    png = tmp_path / "menu-item-lit.png"
    img.save(png)
    return png


def _detroit_soft_pill(tmp_path: Path) -> Path:
    """Replica of Detroit's mb2_menu.png (29x11): 1 px transparent margin,
    a light rimless pill with 1 px rounded corners and a 4 px dark
    decorative mark on the bottom row."""
    img = Image.new("RGBA", (29, 11), (0, 0, 0, 0))
    for y in range(1, 10):
        x0, x1 = (2, 27) if y in (1, 9) else (1, 28)
        for x in range(x0, x1):
            img.putpixel((x, y), (200, 200, 210, 255))
    for x in range(5, 9):
        img.putpixel((x, 9), (30, 30, 30, 255))
    png = tmp_path / "mb2_menu.png"
    img.save(png)
    return png


@pytest.mark.parametrize("make", [_nebula_bevel, _detroit_soft_pill])
def test_close_open_edges_leaves_bevels_and_soft_pills_alone(tmp_path: Path, make) -> None:
    """Corpus audit 2026-09-01: a looser rule boxed in Nebula's raised
    bevel (dark shadow mirrored onto its lit top) and doubled Detroit's
    decorative mark. Neither is a sliced-open rim."""
    png = make(tmp_path)
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(4, 4, 3, 3), hilited=png),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    assert not any("end was open" in n for n in theme.notes)
    with Image.open(png) as im:
        src = im.convert("RGBA")
    trimmed = plasmastyle._opaque_trim(src, (4, 4, 3, 3))
    assert trimmed is not None
    img, edge, trims = trimmed
    caps, _ = plasmastyle._viewitem_caps(edge, *img.size)
    out, out_caps, closed = plasmastyle._close_open_edges(img, caps, trims)
    assert closed == () and out is img and out_caps == caps


def test_close_open_edges_ignores_large_backgrounds(tmp_path: Path) -> None:
    """EvilJester's 100x150 MENU_SEL background is framed on top/left only;
    it is not a pill and is left alone."""
    img = Image.new("RGBA", (100, 150), (0, 0, 0, 0))
    for y in range(1, 149):
        for x in range(1, 99):
            img.putpixel((x, y), (120, 60, 140, 255))
    for x in range(1, 99):
        img.putpixel((x, 1), (230, 200, 240, 255))
    for y in range(1, 149):
        img.putpixel((1, y), (230, 200, 240, 255))
    trimmed = plasmastyle._opaque_trim(img, (4, 4, 4, 4))
    assert trimmed is not None
    art, edge, trims = trimmed
    caps, branch = plasmastyle._viewitem_caps(edge, *art.size)
    assert branch == "declared"
    assert plasmastyle._close_open_edges(art, caps, trims)[2] == ()


def test_viewitem_fully_transparent_art_not_shipped(tmp_path: Path) -> None:
    """Aphex2/ChromiumNoise/Cronos/Ecdysis/Inferno point MENU_SEL at fully
    transparent art: a shipped-but-blank viewitem.svg blocks the Breeze
    fallback and leaves every list without a selection highlight."""
    png = tmp_path / "blank.png"
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(png)
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(0, 0, 0, 0), hilited=png),
    })
    assert plasmastyle.build_viewitem(theme) is None
    assert any(
        "MENU_SEL" in n and "fully transparent" in n and "not shipped" in n
        for n in theme.notes
    )


def test_tasks_fully_transparent_art_not_shipped(tmp_path: Path) -> None:
    png = tmp_path / "blank.png"
    Image.new("RGBA", (16, 16), (0, 0, 0, 3)).save(png)  # below the 128 cutoff
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
        **_arrow_iclasses(tmp_path),
    })
    assert plasmastyle.build_tasks(theme, iconbox_frames="on") is None


def test_write_skips_fully_transparent_viewitem_and_mirrors(tmp_path: Path) -> None:
    png = tmp_path / "blank.png"
    Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(png)
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(0, 0, 0, 0), hilited=png),
    })
    out = tmp_path / "pkg" / plasmastyle.plugin_id(theme.name)
    style = plasmastyle.write(theme, out)
    assert plasmastyle.VIEWITEM_SVG not in style.shipped
    for variant in ("", "solid", "opaque"):
        assert not (out / variant / plasmastyle.VIEWITEM_SVG).exists()


def test_viewitem_trims_transparent_margins_before_slicing(tmp_path: Path) -> None:
    """Shape-masked art with fully transparent margins is trimmed to its
    opaque box before slicing: sliced untrimmed, an 18 px right cap is cut
    from the blank region and paints nothing."""
    img = Image.new("RGBA", (58, 22), (0, 0, 0, 0))
    for x in range(44):
        for y in range(2, 20):
            img.putpixel((x, y), (255, 218, 2, 255))
    png = tmp_path / "sel.png"
    img.save(png)
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(10, 18, 2, 2), hilited=png),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    for element_id in ("hover-topright", "hover-right", "hover-bottomright"):
        tile = _tile_image(svg, element_id)
        alpha = tile.getchannel("A").tobytes()
        opaque = sum(1 for a in alpha if a >= 128) / len(alpha)
        assert opaque > 0.5, (
            f"{element_id} is {1 - opaque:.0%} transparent — sliced from the "
            "shape-mask margin instead of the opaque art"
        )
    # Borderless on BOTH ends: nothing to mirror, no side is closed.
    assert not any("closed" in n for n in theme.notes)
    assert any("trimmed" in n and "MENU_SEL" in n for n in theme.notes)


def test_viewitem_zero_edge_ships_full_nine_part_set(tmp_path: Path) -> None:
    """MENU_SEL with __EDGE_SCALING 0 0 0 0 (the common case) must NOT be a
    center-only whole-image stretch — that's the live blurry-glow bug."""
    hi = _png(tmp_path, "sel.png", size=(24, 12))
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(0, 0, 0, 0), hilited=hi),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"hover-topleft", "hover-top", "hover-left", "hover-center",
            "hover-right", "hover-bottom", "hover-bottomright"} <= ids


def test_scrollbar_skipped_without_knob_art(tmp_path: Path) -> None:
    base = _png(tmp_path, "base.png")
    theme = _theme(tmp_path, {
        "ICONBOX_SCROLLBAR_BASE_VERTICAL": _iclass(
            "ICONBOX_SCROLLBAR_BASE_VERTICAL", normal=base
        ),
    })
    assert plasmastyle.build_scrollbar(theme) is None


# ------------------------------------------------------------------ #
# Scaling + emission mechanics
# ------------------------------------------------------------------ #


@pytest.mark.parametrize("scale", [2, 1.5])
def test_margin_hints_scale_with_theme_scale(tmp_path: Path, scale: float) -> None:
    png = _png(tmp_path, "tt.png", size=(64, 64))
    theme = _theme(tmp_path, {
        "TT_MAIN": _iclass(
            "TT_MAIN", edge=(6, 6, 7, 8), padding=(6, 6, 7, 8), normal=png
        ),
    }, scale=scale)
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert by_id["hint-left-margin"].get("width") == str(scale_px(6, scale))
    assert by_id["hint-top-margin"].get("height") == str(scale_px(7, scale))
    assert by_id["hint-bottom-margin"].get("height") == str(scale_px(8, scale))


def test_oversized_chrome_renders_at_source_scale(tmp_path: Path) -> None:
    """HandOfGod's tooltip cloud: 249x126 art with 20-25 ref-px caps. E16
    rendered it at 1x; upscaling by theme.scale doubles chrome that already
    dominates the surface. Caps summing past SURFACE_MAX_REF_CHROME on
    either axis pin the art (and its margins) to source scale."""
    png = _png(tmp_path, "cloud.png", size=(249, 126))
    theme = _theme(tmp_path, {
        "TT_MAIN": _iclass(
            "TT_MAIN", edge=(20, 20, 22, 25), padding=(20, 20, 22, 25), normal=png
        ),
    }, scale=2)
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    # Caps and margins at 1x, not 2x.
    assert next(iter(by_id["topleft"])).get("width") == "20"
    assert next(iter(by_id["topleft"])).get("height") == "22"
    assert by_id["hint-left-margin"].get("width") == "20"
    assert by_id["hint-bottom-margin"].get("height") == "25"
    assert any("kept at source scale" in n for n in theme.notes)


def test_small_chrome_still_upscales(tmp_path: Path) -> None:
    """Pixel-art chrome (a few ref px of caps) keeps the theme scale — the
    clamp only fires on art whose chrome already dominates at 1x."""
    png = _png(tmp_path, "tt.png", size=(24, 24))
    theme = _theme(tmp_path, {
        "TT_MAIN": _iclass("TT_MAIN", edge=(4, 4, 4, 4), normal=png),
    }, scale=2)
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert next(iter(by_id["topleft"])).get("width") == "8"
    assert not any("kept at source scale" in n for n in theme.notes)


def test_caps_and_middle_sum_exactly_at_fractional_scale(tmp_path: Path) -> None:
    """Edge-based cap rounding: left' + center' + right' == scaled width."""
    png = _png(tmp_path, "menu.png", size=(21, 9))
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", edge=(5, 7, 0, 0), normal=png),
    }, scale=1.5)
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    widths = {
        e.get("id"): int(next(iter(e)).get("width"))
        for e in svg.iter() if e.get("id") in ("left", "center", "right")
    }
    assert widths["left"] + widths["center"] + widths["right"] == scale_px(21, 1.5)
    assert widths["left"] == scale_px(5, 1.5)


def test_every_image_href_is_a_data_uri(tmp_path: Path) -> None:
    png = _png(tmp_path, "btn.png")
    theme = _theme(tmp_path, {
        "DIALOG_BUTTON": _iclass("DIALOG_BUTTON", normal=png, hilited=png, clicked=png),
    })
    svg = plasmastyle.build_button(theme)
    assert svg is not None
    images = [e for e in svg.iter() if e.tag.endswith("image")]
    assert images
    for image in images:
        assert image.get(XLINK, "").startswith("data:image/png;base64,")
        assert image.get("preserveAspectRatio") == "none"


# ------------------------------------------------------------------ #
# Tooltip source resolution (tooltips.cfg DEFAULT block)
# ------------------------------------------------------------------ #


def test_build_tooltip_uses_default_tooltip_iclass(tmp_path: Path) -> None:
    """11 corpus DEFAULT tooltips name an iclass other than TT_MAIN (TT_MINI,
    BAR, COORDS, TT_CLOUD); that art is what E16 showed."""
    bar = _png(tmp_path, "bar.png", color=(90, 10, 10, 255))
    main = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"BAR": _iclass("BAR", normal=bar), "TT_MAIN": _iclass("TT_MAIN", normal=main)},
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="BAR", tclass="COORDS")},
    )
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    assert any("tooltip background from iclass BAR" in n for n in theme.notes)


def test_build_tooltip_without_default_block_uses_tt_main(tmp_path: Path) -> None:
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(tmp_path, {"TT_MAIN": _iclass("TT_MAIN", normal=png)})
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    assert any("tooltip background from iclass TT_MAIN" in n for n in theme.notes)


def test_build_tooltip_artless_tooltip_iclass_falls_back_to_tt_main(
    tmp_path: Path,
) -> None:
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"BAR": _iclass("BAR"), "TT_MAIN": _iclass("TT_MAIN", normal=png)},
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="BAR", tclass="TT_TEXT")},
    )
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    assert any("tooltip background from iclass TT_MAIN" in n for n in theme.notes)


def test_build_tooltip_artless_default_iclass_is_noted(tmp_path: Path) -> None:
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"BAR": _iclass("BAR"), "TT_MAIN": _iclass("TT_MAIN", normal=png)},
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="BAR", tclass="TT_TEXT")},
    )
    assert plasmastyle.build_tooltip(theme) is not None
    assert any(
        "DEFAULT tooltip iclass BAR has no normal art" in n for n in theme.notes
    )


# ------------------------------------------------------------------ #
# style_scheme
# ------------------------------------------------------------------ #


def test_style_scheme_tooltip_override(tmp_path: Path) -> None:
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"TT_MAIN": _iclass("TT_MAIN", normal=png)},
        {"TT_TEXT": _tclass("TT_TEXT", fg=(230, 230, 200))},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.TOOLTIP_SVG})
    )
    assert scheme.tooltip.background_normal == (10, 30, 60)
    assert scheme.tooltip.foreground_normal == (230, 230, 200)
    assert any("colors Tooltip" in n for n in theme.notes)


def test_style_scheme_tooltip_text_from_default_tooltip_tclass(tmp_path: Path) -> None:
    """88 corpus DEFAULT tooltips name a tclass other than TT_TEXT (TEXT1,
    TEXT2, COORDS, ...); E16 paints the tooltip with THAT one."""
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"TT_MAIN": _iclass("TT_MAIN", normal=png)},
        {
            "TT_TEXT": _tclass("TT_TEXT", fg=(230, 230, 200)),
            "TEXT1": _tclass("TEXT1", fg=(200, 240, 255)),
        },
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="TT_MAIN", tclass="TEXT1")},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.TOOLTIP_SVG})
    )
    assert scheme.tooltip.foreground_normal == (200, 240, 255)
    assert any("colors Tooltip" in n and "TEXT1" in n for n in theme.notes)


def test_style_scheme_tooltip_background_from_default_tooltip_iclass(
    tmp_path: Path,
) -> None:
    bar = _png(tmp_path, "bar.png", color=(90, 10, 10, 255))
    main = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"BAR": _iclass("BAR", normal=bar), "TT_MAIN": _iclass("TT_MAIN", normal=main)},
        {"COORDS": _tclass("COORDS", fg=(255, 255, 255))},
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="BAR", tclass="COORDS")},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.TOOLTIP_SVG})
    )
    assert scheme.tooltip.background_normal == (90, 10, 10)
    assert any("colors Tooltip background from BAR art" in n for n in theme.notes)


def test_style_scheme_tooltip_unknown_tclass_falls_back_to_tt_text(
    tmp_path: Path,
) -> None:
    """A DEFAULT tooltip naming a tclass the theme never defines (two corpus
    themes name their iclass) falls back to the TT_TEXT convention."""
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"TT_MAIN": _iclass("TT_MAIN", normal=png)},
        {"TT_TEXT": _tclass("TT_TEXT", fg=(230, 230, 200))},
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="TT_MAIN", tclass="TT_MAIN")},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.TOOLTIP_SVG})
    )
    assert scheme.tooltip.foreground_normal == (230, 230, 200)
    assert any(
        "DEFAULT tooltip names undefined tclass TT_MAIN" in n for n in theme.notes
    )


def test_style_scheme_tooltip_artless_default_iclass_samples_tt_main(
    tmp_path: Path,
) -> None:
    main = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(
        tmp_path,
        {"BAR": _iclass("BAR"), "TT_MAIN": _iclass("TT_MAIN", normal=main)},
        {"TT_TEXT": _tclass("TT_TEXT", fg=(255, 255, 255))},
        tooltips={"DEFAULT": TooltipSpec(name="DEFAULT", iclass="BAR", tclass="TT_TEXT")},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.TOOLTIP_SVG})
    )
    assert scheme.tooltip.background_normal == (10, 30, 60)
    assert any("colors Tooltip background from TT_MAIN art" in n for n in theme.notes)


def test_style_scheme_overrides_gated_on_shipped(tmp_path: Path) -> None:
    png = _png(tmp_path, "tt.png", color=(10, 30, 60, 255))
    theme = _theme(tmp_path, {"TT_MAIN": _iclass("TT_MAIN", normal=png)})
    scheme = plasmastyle.style_scheme(theme, shipped=frozenset())
    # Not shipped → sampled scheme untouched.
    assert scheme.tooltip.background_normal != (10, 30, 60)
    assert not any("colors Tooltip" in n for n in theme.notes)


def test_style_scheme_window_dual_guard_flips_to_black_or_white(
    tmp_path: Path,
) -> None:
    """A text color that clears neither the popup art nor the panel art is
    replaced by whichever of black/white maximizes the minimum contrast."""
    dark = _png(tmp_path, "menu.png", color=(0, 0, 0, 255))
    light = _png(tmp_path, "bar.png", color=(255, 255, 255, 255))
    theme = _theme(
        tmp_path,
        {
            "MENU_BG": _iclass("MENU_BG", normal=dark),
            "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
                "DESKTOP_DRAGBUTTON_HORIZ", normal=light
            ),
        },
        {"MENU_TEXT": _tclass("MENU_TEXT", fg=(128, 128, 128))},
    )
    scheme = plasmastyle.style_scheme(
        theme,
        shipped=frozenset({plasmastyle.DIALOG_SVG, plasmastyle.PANEL_SVG}),
    )
    assert scheme.window.background_normal == (0, 0, 0)
    assert scheme.window.foreground_normal in ((0, 0, 0), (255, 255, 255))
    assert any("forced" in n for n in theme.notes)


def test_style_scheme_window_derived_foregrounds_clear_panel_tint(
    tmp_path: Path,
) -> None:
    """ForegroundInactive/ForegroundActive share the Window group with the
    panel, so they must clear AA against the panel tint too — not just the
    popup art they were dimmed/guarded toward."""
    from themey.analyze.colors import MIN_CONTRAST, contrast_ratio

    dark_menu = _png(tmp_path, "menu.png", color=(30, 30, 40, 255))
    mid_panel = _png(tmp_path, "bar.png", color=(60, 70, 65, 255))
    theme = _theme(
        tmp_path,
        {
            "MENU_BG": _iclass("MENU_BG", normal=dark_menu),
            "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
                "DESKTOP_DRAGBUTTON_HORIZ", normal=mid_panel
            ),
        },
        {"MENU_TEXT": _tclass("MENU_TEXT", fg=(240, 240, 240))},
    )
    scheme = plasmastyle.style_scheme(
        theme,
        shipped=frozenset({plasmastyle.DIALOG_SVG, plasmastyle.PANEL_SVG}),
    )
    assert scheme.window.background_normal == (30, 30, 40)
    for field in ("foreground_normal", "foreground_inactive", "foreground_active"):
        fg = getattr(scheme.window, field)
        for bg in ((30, 30, 40), (60, 70, 65)):
            assert contrast_ratio(fg, bg) >= MIN_CONTRAST, (
                f"{field}={fg} is illegible on {bg}"
            )


def test_style_scheme_selection_from_hover_art(tmp_path: Path) -> None:
    hi = _png(tmp_path, "sel.png", color=(220, 220, 200, 255))
    theme = _theme(
        tmp_path,
        {"MENU_SEL": _iclass("MENU_SEL", hilited=hi)},
        {"MENU_TEXT": _tclass("MENU_TEXT", fg=(20, 20, 20), fg_active=(255, 255, 200))},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.VIEWITEM_SVG})
    )
    assert scheme.selection.background_normal == (220, 220, 200)
    # E16 draws a hovered item with STATE_HILITED, active=0 (menus.c:1000):
    # tclass norm.hilited → norm.normal. __NORMAL_ACTIVE is never consulted.
    assert scheme.selection.foreground_normal == (20, 20, 20)
    assert any("Selection" in n and "hilited" in n for n in theme.notes)


def test_style_scheme_button_fg_fallback_chain(tmp_path: Path) -> None:
    png = _png(tmp_path, "btn.png", color=(240, 240, 240, 255))
    theme = _theme(
        tmp_path,
        {"DIALOG_BUTTON": _iclass("DIALOG_BUTTON", normal=png)},
        {"DIALOG_WIDGET_TEXT": _tclass("DIALOG_WIDGET_TEXT", fg=(90, 10, 10))},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.BUTTON_SVG})
    )
    assert scheme.button.background_normal == (240, 240, 240)
    # No DIALOG_BUTTON tclass → DIALOG_WIDGET_TEXT's color (it clears 4.5:1).
    assert scheme.button.foreground_normal == (90, 10, 10)


# ------------------------------------------------------------------ #
# Pager
# ------------------------------------------------------------------ #

_PAGER_CELLS = (
    "topleft", "top", "topright", "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
)


def test_pager_skipped_without_pager_sel_art(tmp_path: Path) -> None:
    theme = _theme(tmp_path, {})
    assert plasmastyle.build_pager(theme) is None
    assert any("no PAGER_SEL art" in n for n in theme.notes)


def test_pager_three_state_sets_from_art(tmp_path: Path) -> None:
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    bg = _png(tmp_path, "pbg.png", size=(12, 12))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
        "PAGER_BACKGROUND": _iclass(
            "PAGER_BACKGROUND", edge=(2, 2, 2, 2), normal=bg
        ),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    ids = _ids(svg)
    for prefix in ("normal-", "active-", "hover-"):
        for cell in _PAGER_CELLS:
            assert f"{prefix}{cell}" in ids
    assert not any("tile-center" in i for i in ids)
    assert not any("margin" in i for i in ids)


def test_pager_without_background_art_omits_normal_set(tmp_path: Path) -> None:
    """No PAGER_BACKGROUND art -> no normal- set: unselected desks stay
    chrome-free (the panel tint shows through), which IS the no-stale-
    background design."""
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"active-center", "hover-center"} <= ids
    assert not any(i.startswith("normal-") for i in ids)


def test_pager_hover_uses_hilited_art_when_present(tmp_path: Path) -> None:
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    hi = _png(tmp_path, "hi.png", size=(12, 12), color=(90, 200, 90, 255))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(0, 0, 0, 0), normal=sel, hilited=hi),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    active = next(iter(by_id["active-center"])).get(XLINK)
    hover = next(iter(by_id["hover-center"])).get(XLINK)
    assert active != hover


def test_pager_zero_edge_sel_is_whole_stretch_center(tmp_path: Path) -> None:
    """PAGER_SEL with edge 0 0 0 0 stretches whole over the cell — E16
    no-slice semantics, same as every other surface."""
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(0, 0, 0, 0), normal=sel),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    ids = _ids(svg)
    assert "active-center" in ids
    assert "active-topleft" not in ids


def test_stretch_borders_hint_in_art_framed_files(tmp_path: Path) -> None:
    """FrameSvg TILES border elements by default; E16 stretched them, so a
    gradient edge visibly repeats (live HandOfGod pager, 2026-08-31). Every
    file with a sliced-art frame set carries one unprefixed
    hint-stretch-borders (Breeze's own hints are unprefixed file-global)."""
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    assert "hint-stretch-borders" in _ids(svg)

    menu = _png(tmp_path, "menu.png")
    theme = _theme(tmp_path, {"MENU_BG": _iclass("MENU_BG", normal=menu)})
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert "hint-stretch-borders" in _ids(svg)


def test_stretch_borders_hint_absent_without_art_frames(tmp_path: Path) -> None:
    """The flat panel tint has no art borders, and a whole-stretch pager
    set has no border cells - no hint, keep the files minimal."""
    theme = _theme(tmp_path, {})
    assert "hint-stretch-borders" not in _ids(
        plasmastyle.build_panel_background(theme)
    )
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(0, 0, 0, 0), normal=sel),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    assert "hint-stretch-borders" not in _ids(svg)


def _shaped_png(tmp_path: Path, name: str, size=(48, 16)) -> Path:
    """Bone-rod-style art: an opaque band on a mostly transparent canvas
    (the Aliens MENU_BG shape, ~34%+ transparent)."""
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    band = Image.new("RGBA", (size[0], size[1] // 3), (80, 40, 90, 255))
    img.paste(band, (0, size[1] // 3))
    p = tmp_path / name
    img.save(p, format="PNG")
    return p


def test_dialog_background_skips_shaped_menu_bg(tmp_path: Path) -> None:
    """Aliens' bone-rod MENU_BG (34% transparent) stretched over a
    rectangular popup smears huge with wallpaper blurring through the
    holes (live Brightness popup, 2026-08-31) — shaped art falls through
    to the DIALOG iclass."""
    bone = _shaped_png(tmp_path, "bone.png")
    dialog = _png(tmp_path, "dialog_bg.png", size=(32, 32))
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", normal=bone),
        "DIALOG": _iclass("DIALOG", edge=(0, 0, 0, 0), normal=dialog),
    })
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert any("MENU_BG art is shaped" in n for n in theme.notes)
    assert any("DIALOG" in n and "popup/dialog background" in n for n in theme.notes)
    # The shipped art is the opaque dialog texture, not the bone.
    image = next(e for e in svg.iter() if e.tag.endswith("image"))
    from themey.images.embed import image_to_b64_uri
    with Image.open(dialog) as im:
        assert image.get(XLINK) == image_to_b64_uri(im.convert("RGBA"))


def test_dialog_background_skipped_when_all_sources_shaped(tmp_path: Path) -> None:
    bone = _shaped_png(tmp_path, "bone.png")
    theme = _theme(tmp_path, {"MENU_BG": _iclass("MENU_BG", normal=bone)})
    assert plasmastyle.build_dialog_background(theme) is None


def test_dialog_source_keeps_rounded_end_art(tmp_path: Path) -> None:
    """e13's dock1.png is 1.6% transparent (rounded ends) — well under the
    shaped threshold, kept as the popup background."""
    img = Image.new("RGBA", (50, 10), (60, 60, 70, 255))
    for x, y in ((0, 0), (49, 0), (0, 9), (49, 9)):  # 4 corner px = 0.8%
        img.putpixel((x, y), (0, 0, 0, 0))
    p = tmp_path / "dock.png"
    img.save(p, format="PNG")
    theme = _theme(tmp_path, {"MENU_BG": _iclass("MENU_BG", normal=p)})
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert not any("is shaped" in n for n in theme.notes)


def test_style_scheme_window_follows_shaped_fallthrough(tmp_path: Path) -> None:
    """Colors:Window must sample the art actually shipped — the DIALOG
    texture, not the rejected bone — and its note dedupes with the
    builder's."""
    bone = _shaped_png(tmp_path, "bone.png")
    dialog = _png(tmp_path, "dialog_bg.png", size=(32, 32), color=(240, 240, 240, 255))
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", normal=bone),
        "DIALOG": _iclass("DIALOG", normal=dialog),
    })
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.DIALOG_SVG})
    )
    assert scheme.window.background_normal == (240, 240, 240)
    assert sum("MENU_BG art is shaped" in n for n in theme.notes) == 1


# ------------------------------------------------------------------ #
# Dialog widgets — checkmarks / radiobutton / slider / line / frame
# ------------------------------------------------------------------ #


def test_checkmarks_checked_uses_normal_active_art(tmp_path: Path) -> None:
    """__NORMAL_ACTIVE means CHECKED in E16 dialog widgets — the checkbox
    mark must come from the _active art, and a theme with only unchecked
    art gets NO checkmarks file (never an unchecked-art mark)."""
    unchecked = _png(tmp_path, "w0.png", size=(10, 10), color=(20, 20, 20, 255))
    checked = _png(tmp_path, "w1.png", size=(10, 10), color=(220, 220, 40, 255))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_CHECK_BUTTON": _iclass(
            "DIALOG_WIDGET_CHECK_BUTTON", normal=unchecked, normal_active=checked
        ),
    })
    svg = plasmastyle.build_checkmarks(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    checked_href = next(iter(by_id["checkbox"])).get(XLINK)

    # Build a normal-art-only variant: the hrefs must differ, and the
    # builder must return None instead of falling back to unchecked art.
    theme_unchecked_only = _theme(tmp_path, {
        "DIALOG_WIDGET_CHECK_BUTTON": _iclass(
            "DIALOG_WIDGET_CHECK_BUTTON", normal=unchecked
        ),
    })
    assert plasmastyle.build_checkmarks(theme_unchecked_only) is None
    assert any("no checked" in n for n in theme_unchecked_only.notes)

    theme_checked_as_normal = _theme(tmp_path, {
        "DIALOG_WIDGET_CHECK_BUTTON": _iclass(
            "DIALOG_WIDGET_CHECK_BUTTON", normal=unchecked, normal_active=unchecked
        ),
    })
    svg2 = plasmastyle.build_checkmarks(theme_checked_as_normal)
    assert svg2 is not None
    by_id2 = {e.get("id"): e for e in svg2.iter() if e.get("id")}
    assert checked_href != next(iter(by_id2["checkbox"])).get(XLINK)


def test_checkmarks_radiobutton_falls_back_to_check_art(tmp_path: Path) -> None:
    checked = _png(tmp_path, "w1.png", size=(10, 10))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_CHECK_BUTTON": _iclass(
            "DIALOG_WIDGET_CHECK_BUTTON", normal_active=checked
        ),
    })
    svg = plasmastyle.build_checkmarks(theme)
    assert svg is not None
    assert {"checkbox", "radiobutton"} <= _ids(svg)
    assert any("radio mark reuses the check art" in n for n in theme.notes)


def test_radiobutton_elements_hint_size_and_omissions(tmp_path: Path) -> None:
    unchecked = _png(tmp_path, "w0.png", size=(10, 10))
    checked = _png(tmp_path, "r1.png", size=(10, 10))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_RADIO_BUTTON": _iclass(
            "DIALOG_WIDGET_RADIO_BUTTON", normal=unchecked, normal_active=checked
        ),
    }, scale=2)
    svg = plasmastyle.build_radiobutton(theme)
    assert svg is not None
    assert _ids(svg) == {"normal", "checked", "hint-size"}  # no hover w/o hilited
    hint = next(e for e in svg.iter() if e.get("id") == "hint-size")
    assert hint.get("width") == str(scale_px(10, 2))
    assert hint.get("height") == str(scale_px(10, 2))

    hover = _png(tmp_path, "w0h.png", size=(10, 10))
    theme2 = _theme(tmp_path, {
        "DIALOG_WIDGET_RADIO_BUTTON": _iclass(
            "DIALOG_WIDGET_RADIO_BUTTON",
            normal=unchecked, normal_active=checked, hilited=hover,
        ),
    }, scale=2)
    svg2 = plasmastyle.build_radiobutton(theme2)
    assert svg2 is not None
    assert _ids(svg2) == {"normal", "checked", "hover", "hint-size"}


def test_radiobutton_requires_both_states(tmp_path: Path) -> None:
    unchecked = _png(tmp_path, "w0.png", size=(10, 10))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_RADIO_BUTTON": _iclass(
            "DIALOG_WIDGET_RADIO_BUTTON", normal=unchecked
        ),
    })
    assert plasmastyle.build_radiobutton(theme) is None
    assert any("widgets/radiobutton left to the Breeze" in n for n in theme.notes)
    # Whole iclass absent → silent skip, no note.
    theme2 = _theme(tmp_path, {})
    assert plasmastyle.build_radiobutton(theme2) is None
    assert not theme2.notes


def test_slider_requires_base_and_knob(tmp_path: Path) -> None:
    base = _png(tmp_path, "slh.png", size=(140, 10))
    knob = _png(tmp_path, "sl1.png", size=(16, 16))
    theme_base_only = _theme(tmp_path, {
        "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL": _iclass(
            "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL", edge=(4, 4, 1, 1), normal=base
        ),
    })
    assert plasmastyle.build_slider(theme_base_only) is None
    assert any("no knob art" in n for n in theme_base_only.notes)

    theme_knob_only = _theme(tmp_path, {
        "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL": _iclass(
            "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL", normal=knob
        ),
    })
    assert plasmastyle.build_slider(theme_knob_only) is None
    assert any("no base art" in n for n in theme_knob_only.notes)


def test_groove_caps_full_cross_section() -> None:
    """Along-axis caps stay declared; cross-axis caps split the full
    cross-section so the authored tube renders whole (Slider.qml sizes
    the groove to exactly the fixed margins)."""
    assert plasmastyle._groove_caps(
        (4, 4, 1, 1), 140, 10, horizontal=True
    ) == (4, 4, 5, 5)
    assert plasmastyle._groove_caps(
        (1, 1, 4, 4), 10, 140, horizontal=False
    ) == (5, 5, 4, 4)
    # Odd cross-section still sums exactly.
    assert plasmastyle._groove_caps(
        (4, 4, 1, 1), 140, 9, horizontal=True
    ) == (4, 4, 4, 5)


def test_slider_ids_hint_and_orientation_reuse(tmp_path: Path) -> None:
    base = _png(tmp_path, "slh.png", size=(140, 10))
    knob = _png(tmp_path, "sl1.png", size=(16, 16))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL": _iclass(
            "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL", edge=(4, 4, 1, 1), normal=base
        ),
        "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL": _iclass(
            "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL", normal=knob
        ),
    }, scale=2)
    svg = plasmastyle.build_slider(theme)
    assert svg is not None
    ids = _ids(svg)
    # Both handles from the one knob; highlight set always ships; the
    # full-cross-section caps get one px shaved into a real center
    # (FrameSvg needs <prefix>center or it paints nothing).
    assert {"horizontal-slider-handle", "vertical-slider-handle",
            "groove-top", "groove-center", "groove-bottom",
            "groove-highlight-top", "groove-highlight-center",
            "groove-highlight-bottom", "hint-handle-size"} <= ids
    assert not any("tile-center" in i for i in ids)
    assert not any("hover" in i for i in ids)  # no hilited art anywhere
    hint = next(e for e in svg.iter() if e.get("id") == "hint-handle-size")
    assert hint.get("width") == str(scale_px(16, 2))
    assert any("one knob serves both orientations" in n for n in theme.notes)
    assert any("fill-highlight" in n for n in theme.notes)


def test_slider_groove_full_cross_section_ships(tmp_path: Path) -> None:
    """The Aliens groove (140x10, edge 4 4 1 1) must ship top/bottom caps
    of 5+5 — the full tube — not the declared 1-px hairlines."""
    base = _png(tmp_path, "slh.png", size=(140, 10))
    knob = _png(tmp_path, "sl1.png", size=(16, 16))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL": _iclass(
            "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL", edge=(4, 4, 1, 1), normal=base
        ),
        "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL": _iclass(
            "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL", normal=knob
        ),
    })
    svg = plasmastyle.build_slider(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    # Full cross-section split (5+5 on the 10-px tube), then the center
    # shave: the first-of-tie top cap yields one px to the center.
    assert next(iter(by_id["groove-topleft"])).get("height") == "4"
    assert next(iter(by_id["groove-center"])).get("height") == "1"
    assert next(iter(by_id["groove-bottomleft"])).get("height") == "5"


def _line_dims(svg: ET.Element) -> tuple[tuple[int, int], tuple[int, int]]:
    """((h_w, h_h), (v_w, v_h)) of the two rule images."""
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    h_img = next(iter(by_id["horizontal-line"]))
    v_img = next(iter(by_id["vertical-line"]))
    return (
        (int(h_img.get("width")), int(h_img.get("height"))),
        (int(v_img.get("width")), int(v_img.get("height"))),
    )


def test_line_thickness_from_padding_like_e16(tmp_path: Path) -> None:
    """dialog.c:1048-1056 sizes a separator from the iclass __PADDING
    (h = pad.t + pad.b) and squeezes the art into it — Aliens/e13 point the
    separator at a ~64 px bevel box that E16 drew 2 px thick."""
    art = _png(tmp_path, "bt2.png", size=(64, 64))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass(
            "DIALOG_WIDGET_SEPARATOR", padding=(1, 1, 1, 1), normal=art,
        ),
    }, scale=2)
    svg = plasmastyle.build_line(theme)
    assert svg is not None
    (h_w, h_h), (v_w, v_h) = _line_dims(svg)
    assert h_h == scale_px(2, 2)
    assert h_w == scale_px(64, 2)
    # Vertical = same art rotated: dimensions swap.
    assert (v_w, v_h) == (h_h, h_w)
    assert any(
        "2 ref px thick from __PADDING, as E16 sized them; art 64 px squeezed" in n
        for n in theme.notes
    )

    # No padding declared (ten corpus themes): the art height, clamped to
    # LINE_MAX_REF_THICKNESS.
    theme2 = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass("DIALOG_WIDGET_SEPARATOR", normal=art),
    }, scale=2)
    svg2 = plasmastyle.build_line(theme2)
    assert svg2 is not None
    (h_w, h_h), _ = _line_dims(svg2)
    assert h_h == scale_px(plasmastyle.LINE_MAX_REF_THICKNESS, 2)
    assert any("no __PADDING; 64 ref px of art squeezed to 4" in n for n in theme2.notes)

    # Authored-thin art (LiteGnome's 120x4 hline), no padding: kept as is.
    thin = _png(tmp_path, "hline.png", size=(120, 4))
    theme3 = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass("DIALOG_WIDGET_SEPARATOR", normal=thin),
    }, scale=2)
    svg3 = plasmastyle.build_line(theme3)
    assert svg3 is not None
    assert _line_dims(svg3)[0] == (scale_px(120, 2), scale_px(4, 2))
    assert not any("squeezed" in n for n in theme3.notes)

    # LCARS declares __PADDING 8 8 8 8: clamped, and the note says what E16 drew.
    theme4 = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass(
            "DIALOG_WIDGET_SEPARATOR", padding=(8, 8, 8, 8), normal=thin,
        ),
    }, scale=1)
    svg4 = plasmastyle.build_line(theme4)
    assert svg4 is not None
    assert _line_dims(svg4)[0][1] == plasmastyle.LINE_MAX_REF_THICKNESS
    assert any("declares 16 ref px, clamped to 4 — E16 drew 16" in n for n in theme4.notes)


def test_line_hairline_art_survives_the_squeeze(tmp_path: Path) -> None:
    """LCARS: widget_separator.png is 1x16 with ONE opaque row (row 7)
    inside __PADDING 2 2 8 8. A NEAREST squeeze of 16 rows into the
    clamped 4 sampled rows 0/4/8/12 and the rule vanished (probe
    2026-09-01). The art is trimmed to its opaque span and centred."""
    im = Image.new("RGBA", (1, 16), (0, 0, 0, 0))
    im.putpixel((0, 7), (255, 153, 0, 255))
    p = tmp_path / "widget_separator.png"
    im.save(p, format="PNG")
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass(
            "DIALOG_WIDGET_SEPARATOR", edge=(0, 0, 0, 0), padding=(2, 2, 8, 8),
            normal=p, clicked=p,
        ),
    })
    svg = plasmastyle.build_line(theme)
    assert svg is not None
    (h_w, h_h), (v_w, v_h) = _line_dims(svg)
    assert (h_w, h_h) == (1, plasmastyle.LINE_MAX_REF_THICKNESS)
    h_img = _tile_image(svg, "horizontal-line")
    assert h_img.getchannel("A").getextrema()[1] == 255
    assert h_img.getpixel((0, 1)) == (255, 153, 0, 255)
    # Vertical: pad.l + pad.r = 4 wide, the 1 px column centred, 16 tall.
    assert (v_w, v_h) == (4, 16)
    assert _tile_image(svg, "vertical-line").getpixel((1, 7)) == (255, 153, 0, 255)
    assert any("clamped to 4 — E16 drew 16; 1 px of art centred in it" in n for n in theme.notes)


def test_line_starenli_both_rules_from_padding(tmp_path: Path) -> None:
    """StarEnli: 46x2 magenta strip, __PADDING 1 1 1 1, __CLICKED the same
    file. Both rules are 2 ref px = 3 px at 1.5x; the vertical rule used
    to take the art's 46 px WIDTH clamped to 4 (6 px, chris's screenshot)."""
    art = _png(tmp_path, "separator.png", size=(46, 2), color=(220, 0, 200, 255))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass(
            "DIALOG_WIDGET_SEPARATOR", padding=(1, 1, 1, 1), normal=art, clicked=art,
        ),
    }, scale=1.5)
    svg = plasmastyle.build_line(theme)
    assert svg is not None
    (h_w, h_h), (v_w, v_h) = _line_dims(svg)
    assert (h_w, h_h) == (scale_px(46, 1.5), 3)
    assert (v_w, v_h) == (3, 3)
    assert _tile_image(svg, "vertical-line").getpixel((0, 0))[:3] == (220, 0, 200)


def test_frame_unprefixed_set_with_margins(tmp_path: Path) -> None:
    art = _png(tmp_path, "indent.png", size=(72, 72))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_AREA": _iclass(
            "DIALOG_WIDGET_AREA", edge=(4, 4, 4, 4), padding=(4, 4, 4, 4),
            normal=art,
        ),
    })
    svg = plasmastyle.build_frame(theme)
    assert svg is not None
    ids = _ids(svg)
    assert {"topleft", "top", "topright", "left", "center", "right",
            "bottomleft", "bottom", "bottomright"} <= ids
    assert {"hint-left-margin", "hint-right-margin", "hint-top-margin",
            "hint-bottom-margin", "hint-stretch-borders"} <= ids
    # Unprefixed only — no plain-/raised-/sunken- variants.
    assert not any(i.startswith(("plain-", "raised-", "sunken-")) for i in ids)
    # Ring only: E16's area window covers the interior (dialog.c:776-783).
    center = _tile_image(svg, "center")
    assert center.getchannel("A").getextrema() == (0, 0)
    assert _tile_image(svg, "top").getchannel("A").getextrema() == (255, 255)
    assert any("ring only" in n for n in theme.notes)


def test_frame_solid_area_art_becomes_a_ring(tmp_path: Path) -> None:
    """StarEnli's DIALOG_WIDGET_AREA is 256x256 solid magenta with
    __EDGE_SCALING 1 1 1 1 / __PADDING 1 1 1 1: E16 showed a 1 px ring,
    themey shipped the whole tile as the GroupBox background."""
    art = _png(tmp_path, "area.png", size=(256, 256), color=(220, 0, 200, 255))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_AREA": _iclass(
            "DIALOG_WIDGET_AREA", edge=(1, 1, 1, 1), padding=(1, 1, 1, 1),
            normal=art,
        ),
    }, scale=1.5)
    svg = plasmastyle.build_frame(theme)
    assert svg is not None
    ring = scale_px(1, 1.5)
    assert _tile_image(svg, "top").height == ring
    assert _tile_image(svg, "left").width == ring
    assert _tile_image(svg, "top").getpixel((0, 0)) == (220, 0, 200, 255)
    assert _tile_image(svg, "center").getchannel("A").getextrema() == (0, 0)

    # Padding wider than the caps widens the ring (the centre element must
    # stay fully transparent — FrameSvg stretches it across the interior).
    theme2 = _theme(tmp_path, {
        "DIALOG_WIDGET_AREA": _iclass(
            "DIALOG_WIDGET_AREA", edge=(1, 1, 1, 1), padding=(3, 3, 3, 3),
            normal=art,
        ),
    })
    svg2 = plasmastyle.build_frame(theme2)
    assert svg2 is not None
    assert _tile_image(svg2, "top").height == 3
    assert _tile_image(svg2, "center").getchannel("A").getextrema() == (0, 0)


def test_frame_falls_back_to_table_iclass(tmp_path: Path) -> None:
    art = _png(tmp_path, "table.png", size=(32, 32))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_TABLE": _iclass("DIALOG_WIDGET_TABLE", normal=art),
    })
    svg = plasmastyle.build_frame(theme)
    assert svg is not None
    assert any("DIALOG_WIDGET_TABLE" in n for n in theme.notes)
    assert plasmastyle.build_frame(_theme(tmp_path, {})) is None


# ------------------------------------------------------------------ #
# write()
# ------------------------------------------------------------------ #


def _rich_theme(tmp_path: Path) -> Theme:
    bar = _png(tmp_path, "bar.png", color=(40, 44, 52, 255))
    menu = _png(tmp_path, "menu.png", color=(30, 34, 40, 255))
    return _theme(
        tmp_path,
        {
            "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
                "DESKTOP_DRAGBUTTON_HORIZ", normal=bar
            ),
            "MENU_BG": _iclass("MENU_BG", normal=menu, padding=(1, 1, 1, 1)),
        },
        {"MENU_TEXT": _tclass("MENU_TEXT", fg=(220, 220, 220))},
    )


def test_write_layout_and_mirrors(tmp_path: Path) -> None:
    import json

    theme = _rich_theme(tmp_path)
    out = tmp_path / "out" / "themey_TestStyle"
    style = plasmastyle.write(theme, out)

    assert style.id == "themey_TestStyle"
    assert style.dir == out
    # tasks.svg always ships: frames-OFF (the default) is E16's own
    # frameless iconbox, and omitting the file restores Breeze's plates.
    assert set(style.shipped) == {
        plasmastyle.PANEL_SVG, plasmastyle.DIALOG_SVG, plasmastyle.TASKS_SVG,
    }

    meta = json.loads((out / "metadata.json").read_text())
    assert meta["KPlugin"]["Id"] == "themey_TestStyle"
    assert meta["KPlugin"]["Name"] == "TestStyle (themey)"
    assert meta["KPlugin"]["EnabledByDefault"] is True
    assert meta["X-Plasma-API"] == "5.0"
    assert meta["KPackageStructure"] == "Plasma/Theme"

    plasmarc = (out / "plasmarc").read_text()
    assert "[AdaptiveTransparency]" in plasmarc
    assert "[ContrastEffect]" in plasmarc
    assert "enabled=true" in plasmarc
    assert "contrast=1.0" in plasmarc
    assert "saturation=1.5" in plasmarc
    assert "enabled=false" not in plasmarc

    # _rich_theme's dragbar art passes the panel guards, so the panel is
    # opaque art and EVERY shipped file mirrors byte-identically (only a
    # tint panel gets the opaque re-render — see test_write_panel_variants).
    for rel in style.shipped:
        original = (out / rel).read_bytes()
        for variant in ("solid", "opaque"):
            assert (out / variant / rel).read_bytes() == original

    colors = (out / "colors").read_text()
    assert "[Colors:Window]" in colors
    assert "ColorScheme=themey_TestStyle" in colors


def test_write_panel_variants(tmp_path: Path) -> None:
    """A TINT panel's base is translucent; solid/ and opaque/ are genuinely
    opaque (AdaptiveTransparency swaps to solid/ when a window touches the
    panel). Artless theme -> the scheme-tint panel exercises this path."""
    theme = _theme(tmp_path, {})
    out = tmp_path / "out" / "themey_TestStyle"
    plasmastyle.write(theme, out)
    def center_style(path: Path) -> str:
        root = ET.parse(path).getroot()
        return next(e for e in root.iter() if e.get("id") == "center").get(
            "style", ""
        )

    assert "opacity:0.85" in center_style(out / plasmastyle.PANEL_SVG)
    for variant in ("solid", "opaque"):
        style = center_style(out / variant / plasmastyle.PANEL_SVG)
        assert "opacity" not in style
        assert style.startswith("fill:#")


def test_write_rejects_wrong_basename(tmp_path: Path) -> None:
    theme = _rich_theme(tmp_path)
    with pytest.raises(plasmastyle.PlasmaStyleError, match="basename"):
        plasmastyle.write(theme, tmp_path / "out" / "wrong-name")


def test_write_artless_theme_ships_scheme_tint_panel_only(tmp_path: Path) -> None:
    """No iclass art → still a valid package: the panel tint (scheme
    fallback) plus the colors file; everything else falls back to Breeze."""
    theme = _theme(tmp_path, {})
    out = tmp_path / "out" / "themey_TestStyle"
    style = plasmastyle.write(theme, out)
    assert set(style.shipped) == {plasmastyle.PANEL_SVG, plasmastyle.TASKS_SVG}
    assert (out / "colors").is_file()
    assert (out / "metadata.json").is_file()


def test_write_bad_image_skips_one_file_with_note(tmp_path: Path) -> None:
    theme = _rich_theme(tmp_path)
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"\x89PNG not really")
    theme.iclasses["TT_MAIN"] = _iclass("TT_MAIN", normal=corrupt)
    out = tmp_path / "out" / "themey_TestStyle"
    style = plasmastyle.write(theme, out)
    assert plasmastyle.TOOLTIP_SVG not in style.shipped
    assert plasmastyle.PANEL_SVG in style.shipped
    assert any(
        n.startswith("plasmastyle: skipped widgets/tooltip.svg") for n in theme.notes
    )


def test_write_rmtree_on_failure(tmp_path: Path, monkeypatch) -> None:
    theme = _rich_theme(tmp_path)
    out = tmp_path / "out" / "themey_TestStyle"

    def boom(*a, **k):
        raise RuntimeError("colors exploded")

    monkeypatch.setattr(plasmastyle, "build_sections", boom)
    with pytest.raises(plasmastyle.PlasmaStyleError, match="colors exploded"):
        plasmastyle.write(theme, out)
    assert not out.exists()


# ------------------------------------------------------------------ #
# Snapshots — the byte contracts KDE parses
# ------------------------------------------------------------------ #


def test_metadata_json_snapshot(tmp_path: Path, snapshot) -> None:
    theme = _rich_theme(tmp_path)
    out = tmp_path / "out" / "themey_TestStyle"
    plasmastyle.write(theme, out)
    assert (out / "metadata.json").read_text() == snapshot


def test_plasmarc_snapshot(tmp_path: Path, snapshot) -> None:
    theme = _rich_theme(tmp_path)
    out = tmp_path / "out" / "themey_TestStyle"
    plasmastyle.write(theme, out)
    assert (out / "plasmarc").read_text() == snapshot


def test_colors_snapshot(tmp_path: Path, snapshot) -> None:
    theme = _rich_theme(tmp_path)
    out = tmp_path / "out" / "themey_TestStyle"
    plasmastyle.write(theme, out)
    assert (out / "colors").read_text() == snapshot


def test_frame_group_tile_center_hint_only_for_tiling_fill_rules() -> None:
    """``hint-tile-center`` is emitted ONLY when E16 itself tiled the
    middle (``__FILLRULE __TILE*``); stretched E16 middles never get it
    (tiling repeated photographic troughs across whole bars, verified
    live 2026-09-01)."""
    img = Image.new("RGBA", (12, 12), (10, 20, 30, 255))
    canvas = plasmastyle._Canvas()
    plasmastyle._frame_group(canvas, "a-", img, (2, 2, 2, 2))
    plasmastyle._frame_group(canvas, "b-", img, (2, 2, 2, 2), tile_center=True)
    root = canvas.finish()
    ids = {el.get("id") for el in root.iter() if el.get("id")}
    assert "b-hint-tile-center" in ids
    assert "a-hint-tile-center" not in ids
    assert "b-center" in ids


def test_emit_set_tiles_center_for_tile_fill_rule(tmp_path: Path) -> None:
    art = tmp_path / "tile.png"
    Image.new("RGBA", (12, 12), (10, 20, 30, 255)).save(art)
    spec = IClassSpec(
        name="X", edge_scaling=(2, 2, 2, 2), normal=art, normal_active=None,
        hilited=None, hilited_active=None, clicked=None, clicked_active=None,
        normal_sticky=None, normal_active_sticky=None,
        fill_by_state={"normal": "tile"},
    )
    theme = _theme(tmp_path, iclasses={"X": spec})
    canvas = plasmastyle._Canvas()
    plasmastyle._emit_set(theme, canvas, "p-", spec, "normal")
    ids = {el.get("id") for el in canvas.finish().iter() if el.get("id")}
    assert "p-hint-tile-center" in ids


def test_panel_west_east_prefer_iconbox_art_over_vertical_dragbar(
    tmp_path: Path,
) -> None:
    """The west-/east- sets dress themey's left-edge furniture (E16's
    iconbox/pager), so ICONBOX_VERTICAL leads and the vertical dragbar
    (knob/wordmark caps meant for a screen-edge drag bar) is only the
    fallback — e13's 12 px dragbar stretched over a 60 px iconbox panel
    read as a smeared rotated E (live 2026-09-01)."""
    h = _png(tmp_path, "h.png")
    v = _png(tmp_path, "v.png", color=(60, 60, 200, 255))
    d = _png(tmp_path, "d.png", color=(200, 60, 60, 255))
    theme = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass("ICONBOX_HORIZONTAL", normal=h),
        "DESKTOP_DRAGBUTTON_VERT": _iclass("DESKTOP_DRAGBUTTON_VERT", normal=d),
        "ICONBOX_VERTICAL": _iclass("ICONBOX_VERTICAL", normal=v),
    })
    plasmastyle.build_panel_background(theme)
    assert any(
        "vertical panels from ICONBOX_VERTICAL" in n for n in theme.notes
    )
    theme2 = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass("ICONBOX_HORIZONTAL", normal=h),
        "DESKTOP_DRAGBUTTON_VERT": _iclass("DESKTOP_DRAGBUTTON_VERT", normal=d),
    })
    plasmastyle.build_panel_background(theme2)
    assert any(
        "vertical panels from DESKTOP_DRAGBUTTON_VERT" in n for n in theme2.notes
    )


# ------------------------------------------------------------------ #
# Popup background from the E16 menu style
# ------------------------------------------------------------------ #


def _with_menu_style(theme: Theme, **fields) -> Theme:
    from dataclasses import replace

    from themey.ir import MenuStyleSpec

    spec = MenuStyleSpec(name=fields.pop("name", "DEFAULT"), **fields)
    return replace(theme, menu_styles={spec.name: spec})


def _center_rgb(svg: ET.Element) -> tuple[int, int, int]:
    import base64
    import io

    for e in svg.iter():
        if e.get("id") != "center":
            continue
        img = e if e.tag.endswith("image") else next(
            (c for c in e.iter() if c.tag.endswith("image")), None
        )
        if img is not None:
            data = base64.b64decode(img.get(XLINK).split(",", 1)[1])
            return Image.open(io.BytesIO(data)).convert("RGB").getpixel((1, 1))
        style = e.get("style", "")
        hexv = style.split("fill:")[1][:7]
        return tuple(int(hexv[i:i + 2], 16) for i in (1, 3, 5))  # type: ignore[return-value]
    raise AssertionError("no center element")


def test_dialog_source_uses_menu_style_bg_iclass_over_conventional_names(
    tmp_path: Path,
) -> None:
    """The DEFAULT menu style's __BG_ICLASS is what E16 painted the menu
    window with (menus.c MenuRedraw) — whatever it is named. It outranks
    the MENU_BG/DIALOG name convention."""
    custom = _png(tmp_path, "custom.png", size=(32, 32), color=(10, 200, 10, 255))
    dialog = _png(tmp_path, "dialog.png", size=(32, 32), color=(0, 0, 0, 255))
    theme = _theme(tmp_path, {
        "MY_MENU_BACK": _iclass("MY_MENU_BACK", edge=(2, 2, 2, 2), normal=custom),
        "DIALOG": _iclass("DIALOG", edge=(0, 0, 0, 0), normal=dialog),
    })
    theme = _with_menu_style(theme, bg_iclass="MY_MENU_BACK", item_iclass="MENU_SEL")
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert _center_rgb(svg) == (10, 200, 10)
    assert any("from iclass MY_MENU_BACK" in n for n in theme.notes)


def _bevel_strip(path: Path, size=(64, 16), body=(40, 40, 40), rim=(200, 200, 200)) -> Path:
    """A menu-row strip: *body* grain with a 1-px *rim* on every edge."""
    im = Image.new("RGBA", size, (*body, 255))
    w, h = size
    for x in range(w):
        im.putpixel((x, 0), (*rim, 255))
        im.putpixel((x, h - 1), (*rim, 255))
    for y in range(h):
        im.putpixel((0, y), (*rim, 255))
        im.putpixel((w - 1, y), (*rim, 255))
    im.save(path, format="PNG")
    return path


def test_dialog_item_backgrounds_flat_center_in_strip_bevel(tmp_path: Path) -> None:
    """OldE: NeXTSTEP style, __USE_ITEM_BACKGROUNDS __ON. E16 drew no menu
    background at all — every row wore MENU_SEL's normal art — so the popup
    wears that strip's bevel around a FLAT center in the strip's dominant
    color (repeating the strip striped a tall Kickoff with its bevel rows,
    live 2026-09-01), never the DIALOG art and never hint-tile-center."""
    item = _bevel_strip(tmp_path / "item.png")
    dialog = _png(tmp_path, "dialog.png", size=(32, 32), color=(0, 0, 0, 255))
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 3, 3), normal=item),
        "DIALOG": _iclass("DIALOG", edge=(0, 0, 0, 0), normal=dialog),
    })
    theme = _with_menu_style(theme, bg_iclass=None, item_iclass="MENU_SEL", use_item_bg=True)
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    ids = _ids(svg)
    assert "hint-tile-center" not in ids
    assert _center_rgb(svg) == (40, 40, 40)
    # The strip's own rim survives as the popup frame.
    assert _corner_rgb(svg, "topleft") == (200, 200, 200)
    assert any("item backgrounds" in n and "flat center" in n for n in theme.notes)


def _corner_rgb(svg: ET.Element, element: str) -> tuple[int, int, int]:
    import base64
    import io

    for e in svg.iter():
        if e.get("id") != element:
            continue
        img = e if e.tag.endswith("image") else next(
            (c for c in e.iter() if c.tag.endswith("image")), None
        )
        assert img is not None
        data = base64.b64decode(img.get(XLINK).split(",", 1)[1])
        return Image.open(io.BytesIO(data)).convert("RGB").getpixel((0, 0))
    raise AssertionError(f"no {element} element")


def test_dialog_menu_style_shaped_bg_falls_through(tmp_path: Path) -> None:
    """A shaped menu-style background is rejected like a shaped MENU_BG."""
    shaped = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    for x in range(32):
        for y in range(8):
            shaped.putpixel((x, y), (200, 0, 0, 255))
    p = tmp_path / "shaped.png"
    shaped.save(p)
    dialog = _png(tmp_path, "dialog.png", size=(32, 32), color=(0, 0, 0, 255))
    theme = _theme(tmp_path, {
        "SHAPED_BG": _iclass("SHAPED_BG", edge=(0, 0, 0, 0), normal=p),
        "DIALOG": _iclass("DIALOG", edge=(0, 0, 0, 0), normal=dialog),
    })
    theme = _with_menu_style(theme, bg_iclass="SHAPED_BG", item_iclass="MENU_SEL")
    svg = plasmastyle.build_dialog_background(theme)
    assert svg is not None
    assert _center_rgb(svg) == (0, 0, 0)
    assert any("SHAPED_BG art is shaped" in n for n in theme.notes)


def test_style_scheme_window_color_follows_menu_style_bg(tmp_path: Path) -> None:
    """The colors file's Window group samples the same source, so Kickoff's
    header/footer strips match the popup body."""
    custom = _png(tmp_path, "custom.png", size=(32, 32), color=(10, 200, 10, 255))
    dialog = _png(tmp_path, "dialog.png", size=(32, 32), color=(0, 0, 0, 255))
    theme = _theme(tmp_path, {
        "MY_MENU_BACK": _iclass("MY_MENU_BACK", edge=(2, 2, 2, 2), normal=custom),
        "DIALOG": _iclass("DIALOG", edge=(0, 0, 0, 0), normal=dialog),
    })
    theme = _with_menu_style(theme, bg_iclass="MY_MENU_BACK", item_iclass="MENU_SEL")
    out = tmp_path / "themey_TestStyle"
    style = plasmastyle.write(theme, out)
    colors = (style.dir / "colors").read_text()
    window = colors.split("[Colors:Window]")[1].split("[")[0]
    assert "BackgroundNormal=10,200,10" in window


# ------------------------------------------------------------------ #
# Viewitem: rectangular bevel strips honor their declared caps
# ------------------------------------------------------------------ #


def test_viewitem_caps_rectangular_strip_honors_declared_edge() -> None:
    """OldE's MENU_SEL is an opaque 213x16 bevel strip declaring
    __EDGE_SCALING 3 3 3 3. The radius pin (7/7) left a 2-row middle
    that Kickoff stretched ten times taller into a flat band (chris,
    2026-09-01); E16 kept exactly the 3 px bevels crisp and stretched the
    10-row texture. A zero-declared axis still gets the radius pin (E16
    would have stretched the whole strip)."""
    caps, branch = plasmastyle._viewitem_caps((3, 3, 3, 3), 213, 16, rounded=False)
    assert caps == (3, 3, 3, 3) and branch == "bevel"
    caps, branch = plasmastyle._viewitem_caps((0, 0, 0, 0), 164, 20, rounded=False)
    assert caps == (9, 9, 9, 9) and branch == "pill"
    # A rounded pill keeps the radius pin whatever it declares.
    caps, branch = plasmastyle._viewitem_caps((2, 2, 2, 2), 202, 31, rounded=True)
    assert caps == (12, 12, 12, 12) and branch == "pill"


def test_viewitem_rectangular_art_note_and_rounded_art_pin(tmp_path: Path) -> None:
    rect = _png(tmp_path, "rect.png", size=(64, 16), color=(120, 70, 40, 255))
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 3, 3), hilited=rect),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    assert any("3/3/3/3 (L/R/T/B)" in n and "rectangular" in n for n in theme.notes)

    pill = Image.new("RGBA", (64, 16), (120, 70, 40, 255))
    for x, y in ((0, 0), (63, 0), (0, 15), (63, 15)):
        pill.putpixel((x, y), (0, 0, 0, 0))
    p = tmp_path / "pill.png"
    pill.save(p)
    theme2 = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 3, 3), hilited=p),
    })
    svg2 = plasmastyle.build_viewitem(theme2)
    assert svg2 is not None
    assert any("pinned at the art's cross-section radius" in n for n in theme2.notes)


def _noise_png(tmp_path: Path, name: str, size=(64, 16)) -> Path:
    import random

    rnd = random.Random(7)
    im = Image.new("RGBA", size)
    for y in range(size[1]):
        for x in range(size[0]):
            v = rnd.randint(40, 200)
            im.putpixel((x, y), (v, v // 2, v // 3, 255))
    p = tmp_path / name
    im.save(p)
    return p


def _gradient_png(tmp_path: Path, name: str, size=(64, 16)) -> Path:
    im = Image.new("RGBA", size)
    for y in range(size[1]):
        v = 20 + y * 12
        for x in range(size[0]):
            im.putpixel((x, y), (v, v, v, 255))
    p = tmp_path / name
    im.save(p)
    return p


def _sheen_png(tmp_path: Path, name: str, size=(64, 16)) -> Path:
    """Smooth LEFT-TO-RIGHT metal sheen — ShinyMetal's bar_horizontal_2/_3.

    Constant down every column, so the within-row spread the pre-residual
    classifier measured is large while the art carries no grain at all.
    """
    im = Image.new("RGBA", size)
    w = size[0]
    for x in range(w):
        v = 70 + int(150 * (1 - abs(2 * x / (w - 1) - 1)))
        for y in range(size[1]):
            im.putpixel((x, y), (v, v, v, 255))
    p = tmp_path / name
    im.save(p)
    return p


def test_middle_is_textured_grain_vs_gradient(tmp_path: Path) -> None:
    """Synthetic ends of the range. The one calibration case these cannot
    reach is art sitting JUST under ``_TEXTURE_MIN_GRAIN`` with every other
    condition passing — that is Aliens' real MENU_SEL normal art, pinned in
    ``test_pipeline_plasmastyle.py``."""
    noise = Image.open(_noise_png(tmp_path, "n.png")).convert("RGBA")
    grad = Image.open(_gradient_png(tmp_path, "g.png")).convert("RGBA")
    flat = Image.new("RGBA", (64, 16), (90, 60, 40, 255))
    assert plasmastyle._middle_is_textured(noise, (3, 3, 3, 3)) is True
    assert plasmastyle._middle_is_textured(grad, (3, 3, 3, 3)) is False
    assert plasmastyle._middle_is_textured(flat, (3, 3, 3, 3)) is False
    # ShinyMetal's bar_horizontal_2/_3: a HORIZONTAL gradient. The band's
    # within-row spread is huge but it is drift, not grain — repeating it
    # seams across a wide Kickoff row, and E16 stretched menu-item art
    # horizontally anyway.
    sheen = Image.open(_sheen_png(tmp_path, "s.png")).convert("RGBA")
    assert plasmastyle._middle_is_textured(sheen, (3, 3, 2, 2)) is False


def _streaked_png(
    tmp_path: Path, name: str, streak: float, grain: float, size=(120, 16)
) -> Path:
    """Grain over a random per-column offset — texture with visible
    vertical streaking, as opposed to a smooth left-to-right ramp.
    Greyscale so *streak* and *grain* land on the luminance measurements
    unscaled."""
    import random

    rnd = random.Random(11)
    im = Image.new("RGBA", size)
    for x in range(size[0]):
        offset = rnd.gauss(0, streak)
        for y in range(size[1]):
            v = max(0, min(255, int(120 + offset + rnd.gauss(0, grain))))
            im.putpixel((x, y), (v, v, v, 255))
    p = tmp_path / name
    im.save(p)
    return p


def test_middle_is_textured_tolerates_streaky_grain(tmp_path: Path) -> None:
    """Horizontal drift is only disqualifying when it DOMINATES the grain.
    OldE's rust strip (grain 10.4, drift_v 4.0, drift_h 10.2) is streaky
    texture, and chris confirmed live on 2026-09-01 that stretching it
    smeared it; Metallique's sheen (grain 21, drift_h 33) is a gradient
    with grain sprinkled on top and still has to stretch."""
    rust = Image.open(
        _streaked_png(tmp_path, "rust.png", streak=10, grain=10)
    ).convert("RGBA")
    metal = Image.open(
        _streaked_png(tmp_path, "metal.png", streak=33, grain=18)
    ).convert("RGBA")
    assert plasmastyle._middle_is_textured(rust, (3, 3, 3, 3)) is True
    assert plasmastyle._middle_is_textured(metal, (3, 3, 3, 3)) is False
    # Aliens' glow: heavy grain OVER a strong vertical gradient — repeating
    # it bands, so the absolute drift ceiling keeps it stretching.
    import random

    rnd = random.Random(3)
    glow = Image.new("RGBA", (64, 32))
    for y in range(32):
        base = 20 + (y if y < 16 else 31 - y) * 6
        for x in range(64):
            v = max(0, min(255, base + rnd.randint(-40, 40)))
            glow.putpixel((x, y), (v, v, v, 255))
    assert plasmastyle._middle_is_textured(glow, (2, 2, 2, 2)) is False


def test_viewitem_textured_strip_repeats_middle(tmp_path: Path) -> None:
    """OldE's MENU_SEL hover art is a 16 px grain strip. E16 rows were the
    art's own height, so the grain was never stretched; a Kickoff row is
    twice as tall and stretching smeared it (chris, 2026-09-01). A
    textured rectangular strip repeats its middle; a gradient one (Aliens'
    glow) still stretches — tiling a gradient shows seams."""
    noise = _noise_png(tmp_path, "n.png")
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 3, 3), hilited=noise),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    assert "hover-hint-tile-center" in _ids(svg)
    assert any("repeated" in n for n in theme.notes)

    grad = _gradient_png(tmp_path, "g.png")
    theme2 = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 3, 3), hilited=grad),
    })
    svg2 = plasmastyle.build_viewitem(theme2)
    assert svg2 is not None
    assert "hover-hint-tile-center" not in _ids(svg2)


def test_viewitem_horizontal_sheen_stretches(tmp_path: Path) -> None:
    """ShinyMetal's MENU_SEL is a 64x16 strip whose middle is a smooth
    left-to-right metal sheen. Tiling it repeated the sweep ~4x down a
    Kickoff grid cell and seamed across a wide row (chris, 2026-09-01)."""
    sheen = _sheen_png(tmp_path, "bar_horizontal_2.png")
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", edge=(3, 3, 2, 2), hilited=sheen),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    assert "hover-hint-tile-center" not in _ids(svg)
    assert not any("middle repeated" in n for n in theme.notes)


def test_viewitem_selected_plus_hover_lightens_the_clicked_art(tmp_path: Path) -> None:
    """Kickoff paints ``selected+hover`` only while the mouse is DOWN on a
    hovered item; ``selected`` alone is the byte-identical fallback E16 had
    no state for. With real __CLICKED art the pressed-and-hovered set is
    that art lightened, so the two are told apart."""
    hi = _png(tmp_path, "hi.png", color=(120, 120, 120, 255))
    cl = _png(tmp_path, "cl.png", color=(100, 100, 100, 255))
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", hilited=hi, clicked=cl),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    sel = _tile_image(svg, "selected-center").convert("RGBA").getpixel((0, 0))
    both = _tile_image(svg, "selected+hover-center").convert("RGBA").getpixel((0, 0))
    assert sel[:3] == (100, 100, 100)
    assert both[:3] > sel[:3]
    assert both[3] == sel[3] == 255
    assert any("selected+hover" in n and "lightened" in n for n in theme.notes)

    # No clicked art: nothing to distinguish, the sets stay identical.
    plain = _theme(tmp_path, {"MENU_SEL": _iclass("MENU_SEL", hilited=hi)})
    svg2 = plasmastyle.build_viewitem(plain)
    assert svg2 is not None
    assert (
        _tile_image(svg2, "selected-center").convert("RGBA").getpixel((0, 0))
        == _tile_image(svg2, "selected+hover-center").convert("RGBA").getpixel((0, 0))
    )
    assert not any("lightened" in n for n in plain.notes)


def test_style_scheme_selection_uses_menu_text_hilited_and_style_tclass(tmp_path: Path) -> None:
    from dataclasses import replace

    from themey.ir import MenuStyleSpec

    hi = _png(tmp_path, "sel.png", color=(220, 220, 200, 255))
    menu_text = TClassSpec(
        name="MENU_TEXT", fg_normal=(20, 20, 20), fg_active=(250, 250, 250),
        fg_by_state={"normal": (20, 20, 20), "normal_active": (250, 250, 250),
                     "hilited": (9, 9, 9)},
    )
    other = TClassSpec(
        name="MENU", fg_normal=(30, 30, 30), fg_active=None,
        fg_by_state={"normal": (30, 30, 30), "hilited": (5, 5, 5)},
    )
    theme = _theme(tmp_path, {"MENU_SEL": _iclass("MENU_SEL", hilited=hi)},
                   {"MENU_TEXT": menu_text, "MENU": other})
    shipped = frozenset({plasmastyle.VIEWITEM_SVG})
    scheme = plasmastyle.style_scheme(theme, shipped=shipped)
    assert scheme.selection.foreground_normal == (9, 9, 9)
    # A menu style naming its own tclass ("MENU", 6 corpus blocks) wins.
    style = MenuStyleSpec(name="DEFAULT", tclass="MENU")
    theme2 = replace(theme, menu_styles={"DEFAULT": style})
    scheme2 = plasmastyle.style_scheme(theme2, shipped=shipped)
    assert scheme2.selection.foreground_normal == (5, 5, 5)


def test_style_scheme_selection_from_the_pressed_art(tmp_path: Path) -> None:
    """Kickoff paints Selection ONLY while the mouse is down, and the art it
    paints then is MENU_SEL's __CLICKED state. Sampling the hover art left
    ShinyMetal washing a 119-grey pressed plate toward a 137-grey Selection
    background — a muddy icon under a black label."""
    hi = _png(tmp_path, "hi.png", color=(220, 220, 200, 255))
    cl = _png(tmp_path, "cl.png", color=(150, 150, 130, 255))
    menu_text = TClassSpec(
        name="MENU_TEXT", fg_normal=(20, 20, 20), fg_active=None,
        fg_by_state={"normal": (20, 20, 20), "hilited": (9, 9, 9),
                     "clicked": (4, 4, 4)},
    )
    theme = _theme(
        tmp_path,
        {"MENU_SEL": _iclass("MENU_SEL", hilited=hi, clicked=cl)},
        {"MENU_TEXT": menu_text},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.VIEWITEM_SVG})
    )
    assert scheme.selection.background_normal == (150, 150, 130)
    assert scheme.selection.foreground_normal == (4, 4, 4)
    assert any("MENU_SEL clicked art" in n for n in theme.notes)


def test_style_scheme_selection_text_never_loses_the_pressed_plate(
    tmp_path: Path,
) -> None:
    """The label is guarded against the hover plate too, but a theme whose
    two plates sit at opposite ends of the range (near-white hover, near-
    black clicked) has no colour legible on both. The plate the label is
    actually painted on wins — Kickoff draws ``selected+hover`` OVER the
    hover set."""
    from themey.analyze.colors import MIN_CONTRAST, contrast_ratio

    hi = _png(tmp_path, "hi.png", color=(250, 250, 250, 255))
    cl = _png(tmp_path, "cl.png", color=(20, 20, 20, 255))
    menu_text = TClassSpec(
        name="MENU_TEXT", fg_normal=(128, 128, 128), fg_active=None,
        fg_by_state={"normal": (128, 128, 128), "clicked": (128, 128, 128)},
    )
    theme = _theme(
        tmp_path,
        {"MENU_SEL": _iclass("MENU_SEL", hilited=hi, clicked=cl)},
        {"MENU_TEXT": menu_text},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.VIEWITEM_SVG})
    )
    assert scheme.selection.background_normal == (20, 20, 20)
    assert contrast_ratio(
        scheme.selection.foreground_normal, (20, 20, 20)
    ) >= MIN_CONTRAST


def test_style_scheme_view_follows_the_popup_surface(tmp_path: Path) -> None:
    """The sampled ladder put View 0.07 away from mid-grey off the BORDER
    tint, which on ShinyMetal meant a near-black search field inside a
    148-grey Kickoff. When the popup surface is art-derived, View is one
    ladder step from THAT."""
    from themey.analyze.colors import _lightness

    bg = _png(tmp_path, "menubg.png", color=(148, 148, 148, 255))
    hi = _png(tmp_path, "sel.png", color=(200, 200, 200, 255))
    theme = _theme(tmp_path, {
        "MENU_BG": _iclass("MENU_BG", normal=bg),
        "MENU_SEL": _iclass("MENU_SEL", hilited=hi),
    })
    scheme = plasmastyle.style_scheme(
        theme,
        shipped=frozenset({plasmastyle.DIALOG_SVG, plasmastyle.VIEWITEM_SVG}),
    )
    window = scheme.window.background_normal
    view = scheme.view.background_normal
    assert window == (148, 148, 148)
    assert _lightness(view) > _lightness(window)
    assert abs(_lightness(view) - _lightness(window)) < 0.12
    assert any("View from the popup surface" in n for n in theme.notes)


def test_style_scheme_focus_rings_follow_selection_on_neutral_themes(
    tmp_path: Path,
) -> None:
    """``analyze/colors`` falls back to Breeze blue when the border art has
    no saturated cluster; every focus/hover decoration in a grey or brown
    theme then read as stock Plasma."""
    from dataclasses import replace

    from themey.analyze.colors import default_scheme

    hi = _png(tmp_path, "hi.png", color=(200, 190, 170, 255))
    theme = _theme(tmp_path, {"MENU_SEL": _iclass("MENU_SEL", hilited=hi)})
    shipped = frozenset({plasmastyle.VIEWITEM_SVG})
    scheme = plasmastyle.style_scheme(theme, shipped=shipped)
    sel_bg = scheme.selection.background_normal
    assert sel_bg == (200, 190, 170)
    for group in (scheme.view, scheme.window, scheme.button, scheme.selection,
                  scheme.tooltip, scheme.complementary, scheme.header,
                  scheme.header_inactive):
        assert group.decoration_focus == sel_bg
        assert group.decoration_hover == sel_bg
    assert any("focus rings" in n and "Breeze blue" in n for n in theme.notes)

    # A theme whose art DID yield an accent keeps it.
    sampled = replace(default_scheme(), accent_fallback=False)
    kept = replace(theme, scheme=sampled, notes=[])
    scheme2 = plasmastyle.style_scheme(kept, shipped=shipped)
    assert scheme2.window.decoration_focus == sampled.window.decoration_focus
    assert not any("focus rings" in n for n in kept.notes)


def test_line_vertical_uses_clicked_art(tmp_path: Path) -> None:
    """dialog.c:1380-1383: a vertical separator is drawn with STATE_CLICKED,
    the horizontal one with STATE_NORMAL (107 corpus themes ship both)."""
    import base64
    import io

    h = _png(tmp_path, "h.png", size=(32, 4), color=(200, 0, 0, 255))
    v = _png(tmp_path, "v.png", size=(4, 32), color=(0, 0, 200, 255))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass(
            "DIALOG_WIDGET_SEPARATOR", padding=(1, 1, 2, 2), normal=h, clicked=v,
        ),
    }, scale=2)
    svg = plasmastyle.build_line(theme)
    assert svg is not None
    for e in svg.iter():
        if e.get("id") == "vertical-line":
            img = e if e.tag.endswith("image") else next(
                c for c in e.iter() if c.tag.endswith("image")
            )
            data = base64.b64decode(img.get(XLINK).split(",", 1)[1])
            px = Image.open(io.BytesIO(data)).convert("RGB").getpixel((1, 1))
            assert px == (0, 0, 200)
            # Width = pad.l + pad.r (E16's vertical separator width), the
            # clicked art's height scaled.
            assert int(img.get("width")) == scale_px(1 + 1, 2)
            assert int(img.get("height")) == scale_px(32, 2)
            break
    else:
        raise AssertionError("no vertical-line")
    assert _line_dims(svg)[0][1] == scale_px(2 + 2, 2)
    assert any("vertical rule from the __CLICKED art" in n for n in theme.notes)


# ------------------------------------------------------------------ #
# Furniture applets: pager window rects, dragbar desk buttons
# ------------------------------------------------------------------ #


def test_pager_window_set_from_pager_win(tmp_path: Path) -> None:
    """``window-`` is PAGER_WIN's normal art — E16's window-rect art in
    the LIVE pager, painted by themey's own pager applet per window."""
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    win = _png(tmp_path, "win.png", size=(10, 8), color=(30, 30, 200, 255))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
        "PAGER_WIN": _iclass("PAGER_WIN", edge=(2, 2, 2, 2), normal=win),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    ids = _ids(svg)
    for cell in _PAGER_CELLS:
        assert f"window-{cell}" in ids
    assert "window-active-center" not in ids
    assert any("pager window rects from iclass PAGER_WIN" in n for n in theme.notes)
    # No PAGER_WIN art: the applet falls back to the stock-style rects.
    theme2 = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
    })
    svg2 = plasmastyle.build_pager(theme2)
    assert svg2 is not None
    assert not any(i.startswith("window-") for i in _ids(svg2))


def test_pager_window_active_only_with_hilited_art(tmp_path: Path) -> None:
    sel = _png(tmp_path, "sel.png", size=(12, 12))
    win = _png(tmp_path, "win.png", size=(10, 8))
    hi = _png(tmp_path, "winhi.png", size=(10, 8), color=(200, 200, 30, 255))
    theme = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
        "PAGER_WIN": _iclass("PAGER_WIN", edge=(0, 0, 0, 0), normal=win, hilited=hi),
    })
    svg = plasmastyle.build_pager(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert "window-active-center" in by_id
    normal = next(iter(by_id["window-center"])).get(XLINK)
    active = next(iter(by_id["window-active-center"])).get(XLINK)
    assert normal != active
    # hilited_active alone is the checked-semantics trap: not a hover.
    theme2 = _theme(tmp_path, {
        "PAGER_SEL": _iclass("PAGER_SEL", edge=(2, 2, 2, 2), normal=sel),
        "PAGER_WIN": _iclass(
            "PAGER_WIN", edge=(0, 0, 0, 0), normal=win, hilited_active=hi
        ),
    })
    svg2 = plasmastyle.build_pager(theme2)
    assert svg2 is not None
    assert "window-active-center" not in _ids(svg2)


def test_dragbar_elements_from_raise_lower(tmp_path: Path) -> None:
    """E16's default dragbar ordering (desktops.c, ordering 1): the RAISE
    button sits at the LEFT end and runs ``desk next``; the LOWER button
    at the RIGHT end runs ``desk prev``. Elements are named by ACTION so
    the deskbutton applet reads ``next-``/``prev-`` directly."""
    raise_png = _png(tmp_path, "raise.png", size=(16, 16), color=(10, 200, 10, 255))
    raise_hi = _png(tmp_path, "raise_hi.png", size=(16, 16), color=(40, 230, 40, 255))
    raise_cl = _png(tmp_path, "raise_cl.png", size=(16, 16), color=(0, 120, 0, 255))
    lower_png = _png(tmp_path, "lower.png", size=(16, 16), color=(200, 10, 10, 255))
    theme = _theme(tmp_path, {
        "DESKTOP_RAISEBUTTON_HORIZ": _iclass(
            "DESKTOP_RAISEBUTTON_HORIZ", normal=raise_png, hilited=raise_hi,
            clicked=raise_cl,
        ),
        "DESKTOP_LOWERBUTTON_HORIZ": _iclass(
            "DESKTOP_LOWERBUTTON_HORIZ", normal=lower_png
        ),
    }, scale=2)
    svg = plasmastyle.build_dragbar(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for direction in ("next", "prev"):
        for state in ("normal", "hover", "pressed"):
            assert f"{direction}-horiz-{state}" in by_id
    assert not any(i.startswith(("next-vert", "prev-vert")) for i in by_id)
    hrefs = {
        s: next(iter(by_id[f"next-horiz-{s}"])).get(XLINK)
        for s in ("normal", "hover", "pressed")
    }
    assert len(set(hrefs.values())) == 3  # three distinct RAISE states
    # LOWER has normal art only: hover/pressed reuse it (E16 fallback).
    lower = {
        s: next(iter(by_id[f"prev-horiz-{s}"])).get(XLINK)
        for s in ("normal", "hover", "pressed")
    }
    assert len(set(lower.values())) == 1
    img = next(iter(by_id["next-horiz-normal"]))
    assert img.get("width") == "32" and img.get("height") == "32"  # scale 2
    assert any(
        "dragbar desk buttons from iclass DESKTOP_RAISEBUTTON_HORIZ+"
        "DESKTOP_LOWERBUTTON_HORIZ" in n
        for n in theme.notes
    )


def test_dragbar_skipped_without_horizontal_art(tmp_path: Path) -> None:
    theme = _theme(tmp_path, {})
    assert plasmastyle.build_dragbar(theme) is None
    assert any("no DESKTOP_RAISEBUTTON_HORIZ/DESKTOP_LOWERBUTTON_HORIZ art" in n
               for n in theme.notes)
    # A vertical-only theme still skips: the dragbar panel is horizontal.
    vert = _png(tmp_path, "rv.png")
    theme2 = _theme(tmp_path, {
        "DESKTOP_RAISEBUTTON_VERT": _iclass("DESKTOP_RAISEBUTTON_VERT", normal=vert),
    })
    assert plasmastyle.build_dragbar(theme2) is None


def test_dragbar_one_horizontal_button_ships_alone(tmp_path: Path) -> None:
    """Only RAISE has art: ship its trio; the applet's missing-element
    fallback (widgets/arrows) covers the other end."""
    raise_png = _png(tmp_path, "raise.png")
    theme = _theme(tmp_path, {
        "DESKTOP_RAISEBUTTON_HORIZ": _iclass("DESKTOP_RAISEBUTTON_HORIZ", normal=raise_png),
    })
    svg = plasmastyle.build_dragbar(theme)
    assert svg is not None
    ids = _ids(svg)
    assert "next-horiz-normal" in ids
    assert "prev-horiz-normal" not in ids


def test_dragbar_vert_optional(tmp_path: Path) -> None:
    raise_png = _png(tmp_path, "raise.png")
    lower_png = _png(tmp_path, "lower.png")
    raise_v = _png(tmp_path, "raise_v.png", size=(16, 20))
    lower_v = _png(tmp_path, "lower_v.png", size=(16, 20))
    theme = _theme(tmp_path, {
        "DESKTOP_RAISEBUTTON_HORIZ": _iclass("DESKTOP_RAISEBUTTON_HORIZ", normal=raise_png),
        "DESKTOP_LOWERBUTTON_HORIZ": _iclass("DESKTOP_LOWERBUTTON_HORIZ", normal=lower_png),
        "DESKTOP_RAISEBUTTON_VERT": _iclass("DESKTOP_RAISEBUTTON_VERT", normal=raise_v),
        "DESKTOP_LOWERBUTTON_VERT": _iclass("DESKTOP_LOWERBUTTON_VERT", normal=lower_v),
    })
    svg = plasmastyle.build_dragbar(theme)
    assert svg is not None
    ids = _ids(svg)
    for direction in ("next", "prev"):
        for orient in ("horiz", "vert"):
            for state in ("normal", "hover", "pressed"):
                assert f"{direction}-{orient}-{state}" in ids


def test_dragbar_registered_in_builders() -> None:
    assert plasmastyle.DRAGBAR_SVG == "widgets/themey-dragbar.svg"
    assert any(rel == plasmastyle.DRAGBAR_SVG for rel, _ in plasmastyle._BUILDERS)


def test_north_wordmark_accepts_thin_strip(tmp_path: Path) -> None:
    """e13's 6 px dragbar with 60 px wordmark caps: the ``north-`` set now
    ships it — themey's dragbar panel is exactly ``scale_px(16)`` thick,
    so the stretch is E16's own — while ``south-`` (foreign bottom bars,
    stretched to 40-60 px) keeps the thickness guard."""
    thin = _png(tmp_path, "dragbar.png", size=(300, 6))
    small = _png(tmp_path, "iconbox.png", color=(20, 90, 20, 255))
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(60, 60, 0, 0), normal=thin
        ),
        "ICONBOX_HORIZONTAL": _iclass(
            "ICONBOX_HORIZONTAL", edge=(4, 4, 4, 4), normal=small
        ),
    })
    spec = theme.iclasses["DESKTOP_DRAGBUTTON_HORIZ"]
    assert plasmastyle._panel_art_guard(spec, wordmark=True, thin_ok=True) is None
    reason = plasmastyle._panel_art_guard(spec, wordmark=True)
    assert reason is not None and "thin" in reason
    svg = plasmastyle.build_panel_background(theme)
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert by_id["north-center"].tag.endswith("g")
    assert by_id["north-hint-left-margin"].get("width") == str(60 - 4)
    assert not any(i.startswith("south-") for i in by_id)
    assert by_id["center"].tag.endswith("g")  # shared set = iconbox trough
    assert any(
        "top panels wear the DESKTOP_DRAGBUTTON_HORIZ wordmark art (north- set" in n
        for n in theme.notes
    )


# ------------------------------------------------------------------ #
# Iconbox faithfulness: --iconbox-frames, hover prefixes, TasksHover
# ------------------------------------------------------------------ #

_TASKS_ALL_PREFIXES = (
    "normal-", "minimized-", "", "hover-", "attention-", "progress-", "focus-",
)


def test_tasks_frames_off_ships_blank_sets_with_trough_margins(tmp_path: Path) -> None:
    """E16's iconbox default (container.c draw_icon_base = 0): no plate.
    Every prefix (hover-on-state ones too) is a transparent 1 px
    center-only set, margins from the iconbox trough __PADDING scaled, so
    Breeze's plates never come back and the icons keep E16's spacing."""
    png = _png(tmp_path, "iconbtn.png")
    trough = _png(tmp_path, "trough.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png, hilited=png, padding=(2, 2, 2, 2)
        ),
        "ICONBOX_VERTICAL": _iclass(
            "ICONBOX_VERTICAL", normal=trough, padding=(3, 3, 4, 4)
        ),
        **_arrow_iclasses(tmp_path),
    }, scale=2)
    svg = plasmastyle.build_tasks(theme, iconbox_frames="off")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for prefix in (*_TASKS_ALL_PREFIXES, "launcher-hover-", "focus-hover-"):
        center = by_id[f"{prefix}center"]
        assert center.tag.endswith("rect") and "opacity:0" in center.get("style", "")
        assert center.get("width") == "1"
        assert by_id[f"{prefix}hint-left-margin"].get("width") == "6"   # 3 × 2
        assert by_id[f"{prefix}hint-top-margin"].get("width") == "8"    # 4 × 2
        assert f"{prefix}topleft" not in by_id
    assert not any(e.tag.endswith("image") and "center" in (e.get("id") or "")
                   for e in svg.iter())
    for direction in ("left", "right", "top", "bottom"):
        assert f"group-expander-{direction}" in by_id  # expanders retained
    assert any("task frames OFF" in n and "from the iconbox trough" in n for n in theme.notes)


def test_tasks_frames_off_without_button_art_still_ships(tmp_path: Path) -> None:
    """Off mode needs no button art at all (nothing is painted); the
    trough padding falls back to E16's 2 px default."""
    theme = _theme(tmp_path, {})
    svg = plasmastyle.build_tasks(theme, iconbox_frames="off")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert "normal-center" in by_id
    assert by_id["normal-hint-left-margin"].get("width") == "2"
    assert any("(E16 default)" in n for n in theme.notes)


def test_tasks_frames_on_notes_e16_frameless_default(tmp_path: Path) -> None:
    png = _png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    assert any("draws NO per-icon plate" in n for n in theme.notes)
    with pytest.raises(plasmastyle.PlasmaStyleError, match="iconbox_frames"):
        plasmastyle.build_tasks(theme, iconbox_frames="bogus")


def test_tasks_launcher_and_focus_hover_only_with_hilited_art(tmp_path: Path) -> None:
    png = _png(tmp_path, "iconbtn.png")
    hi = _png(tmp_path, "iconbtn_hi.png", color=(90, 200, 90, 255))
    cl = _png(tmp_path, "iconbtn_cl.png", color=(20, 20, 20, 255))
    plain = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(plain, iconbox_frames="on")
    assert svg is not None
    ids = _ids(svg)
    assert "launcher-hover-center" not in ids and "focus-hover-center" not in ids

    lit = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png, hilited=hi, clicked=cl
        ),
    })
    svg2 = plasmastyle.build_tasks(lit, iconbox_frames="on")
    assert svg2 is not None
    by_id = {e.get("id"): e for e in svg2.iter() if e.get("id")}
    assert "launcher-hover-center" in by_id and "focus-hover-center" in by_id
    assert "launcher-hover-hint-left-margin" not in by_id  # padding 0 → no hints
    # launcher-hover wears the hilited art, focus-hover the clicked art.
    launcher = next(iter(by_id["launcher-hover-center"])).get(XLINK)
    focus_hover = next(iter(by_id["focus-hover-center"])).get(XLINK)
    hover = next(iter(by_id["hover-center"])).get(XLINK)
    focus = next(iter(by_id["focus-center"])).get(XLINK)
    assert launcher == hover and focus_hover == focus and launcher != focus_hover


def test_write_metadata_carries_tasks_hover_and_iconbox_frames(tmp_path: Path) -> None:
    import json

    png = _png(tmp_path, "iconbtn.png")
    hi = _png(tmp_path, "iconbtn_hi.png", color=(90, 200, 90, 255))
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png, hilited=hi),
    })
    out = tmp_path / "themey_TestStyle"
    style = plasmastyle.write(theme, out, iconbox_frames="off")
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["X-Themey-TasksHover"] is True
    assert plasmastyle.TASKS_SVG in style.shipped
    svg = ET.parse(out / plasmastyle.TASKS_SVG).getroot()
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert by_id["normal-center"].tag.endswith("rect")  # blank set shipped
    for variant in ("solid", "opaque"):
        assert (out / variant / plasmastyle.TASKS_SVG).read_bytes() == (
            out / plasmastyle.TASKS_SVG
        ).read_bytes()
    with pytest.raises(plasmastyle.PlasmaStyleError, match="iconbox_frames"):
        plasmastyle.write(theme, out, iconbox_frames="bogus")


# ------------------------------------------------------------------ #
# Tasks — synthesized states (WP2): E16 authors only __NORMAL on most
# iconbox buttons, so hover/focus/minimized/attention are derived.
# ------------------------------------------------------------------ #


def _bevel_png(tmp_path: Path, name: str, size=(16, 16)) -> Path:
    """A plate with a light top edge and a dark bottom one — the E16
    bevel the synthesized ``focus`` state flips."""
    img = Image.new("RGBA", size, (120, 120, 120, 255))
    for x in range(size[0]):
        img.putpixel((x, 0), (220, 220, 220, 255))
        img.putpixel((x, size[1] - 1), (40, 40, 40, 255))
    img.save(tmp_path / name, format="PNG")
    return tmp_path / name


def _href(by_id: dict[str, ET.Element], element: str) -> str:
    """The base64 art of a frame element's embedded image."""
    return next(iter(by_id[element])).get(XLINK) or ""


def _set_art(by_id: dict[str, ET.Element], prefix: str) -> str:
    """Every slice of one 9-part set, joined — the whole plate, not just
    the stretched middle (an E16 bevel lives in the caps)."""
    return "|".join(
        _href(by_id, f"{prefix}{name}")
        for name in ("topleft", "top", "topright", "left", "center", "right",
                     "bottomleft", "bottom", "bottomright")
        if f"{prefix}{name}" in by_id
    )


def test_tasks_default_mode_is_frames_off(tmp_path: Path) -> None:
    """E16's own iconbox draws no per-icon plate — that is the default now."""
    png = _png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert by_id["normal-center"].tag.endswith("rect")  # no plate art
    assert any("task frames OFF" in n for n in theme.notes)
    assert plasmastyle.ICONBOX_FRAME_MODES[0] == "off"


def test_tasks_synthesized_states_are_distinct_frames_on(tmp_path: Path) -> None:
    """A __NORMAL-only iconbox button used to give seven byte-identical
    plates; hover/attention/minimized/focus are now derived from it."""
    png = _bevel_png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png, padding=(2, 2, 2, 2)
        ),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    art = {
        p: _set_art(by_id, p)
        for p in ("normal-", "hover-", "attention-", "minimized-", "focus-",
                  "progress-", "")
    }
    assert art["normal-"] == art[""]          # launcher wears the normal plate
    assert art["hover-"] == art["progress-"]  # progress mirrors hover
    distinct = {art["normal-"], art["hover-"], art["attention-"],
                art["minimized-"], art["focus-"]}
    assert len(distinct) == 5
    for prefix in ("hover-", "attention-", "minimized-", "focus-"):
        assert f"{prefix}hint-left-margin" in by_id, prefix
    assert any(
        "synthesized" in n and "minimized" in n and "focus" in n
        for n in theme.notes
    )


def test_tasks_focus_bar_is_a_stylesheet_element(tmp_path: Path) -> None:
    """The focus accent follows the ACTIVE colour scheme: KSvg rewrites the
    ``current-color-scheme`` sheet, so the bar is a classed rect, not baked
    pixels. One set per panel edge, bar on the panel-adjacent side."""
    png = _png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    style = svg.find(f"{{{SVG_NS}}}style")
    assert style is not None and style.get("id") == "current-color-scheme"
    assert ".ColorScheme-Highlight" in (style.text or "")
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for prefix, side in (
        ("focus-", "bottom"), ("north-focus-", "top"),
        ("west-focus-", "left"), ("east-focus-", "right"),
    ):
        group = by_id[f"{prefix}{side}"]
        bars = [c for c in group if c.get("class") == "ColorScheme-Highlight"]
        assert len(bars) == 1, prefix
        assert bars[0].get("style") == "fill:currentColor"
        thick = "height" if side in ("top", "bottom") else "width"
        assert bars[0].get(thick) == str(plasmastyle.TASKS_FOCUS_BAR_PX)


def test_tasks_frames_off_synthesizes_tints_and_focus_bar(tmp_path: Path) -> None:
    """Frames OFF still tells the states apart: a white wash for
    hover/attention and the highlight bar for the active task."""
    theme = _theme(tmp_path, {})
    svg = plasmastyle.build_tasks(theme, iconbox_frames="off")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    assert by_id["hover-center"].get("style") == "fill:#ffffff;opacity:0.12"
    assert by_id["progress-center"].get("style") == "fill:#ffffff;opacity:0.12"
    assert by_id["attention-center"].get("style") == "fill:#ffffff;opacity:0.25"
    for prefix in ("normal-", "minimized-", ""):
        assert by_id[f"{prefix}center"].get("style") == "opacity:0"
    bar = by_id["focus-bottom"]
    assert bar.get("class") == "ColorScheme-Highlight"
    assert bar.get("height") == str(plasmastyle.TASKS_FOCUS_BAR_PX)
    assert by_id["west-focus-left"].get("width") == str(
        plasmastyle.TASKS_FOCUS_BAR_PX
    )
    assert svg.find(f"{{{SVG_NS}}}style") is not None


def test_tasks_real_state_art_is_never_synthesized(tmp_path: Path) -> None:
    """Authored hilited/clicked art wins — synthesis fills gaps only."""
    png = _png(tmp_path, "n.png", color=(120, 120, 120, 255))
    hi = _png(tmp_path, "hi.png", color=(90, 200, 90, 255))
    cl = _png(tmp_path, "cl.png", color=(20, 20, 20, 255))
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png, hilited=hi, clicked=cl
        ),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    # focus wears the clicked art, so it carries no synthesized accent bar.
    assert not any(
        c.get("class") == "ColorScheme-Highlight" for c in by_id["focus-center"]
    )
    assert "north-focus-center" not in by_id
    assert _href(by_id, "hover-center") == _href(by_id, "attention-center")
    # minimized has no E16 counterpart at all — always synthesized.
    assert _href(by_id, "minimized-center") != _href(by_id, "normal-center")
    assert any("minimized" in n and "synthesized" in n for n in theme.notes)


def test_tasks_hover_true_once_hover_is_synthesized(tmp_path: Path) -> None:
    """taskHoverEffect now has something to show even without hilited art."""
    png = _png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    assert plasmastyle.tasks_hover(theme, iconbox_frames="on") is True
    assert plasmastyle.tasks_hover(theme, iconbox_frames="off") is True
    # No art and frames ON: no tasks.svg ships, so Breeze paints the frames.
    assert plasmastyle.tasks_hover(_theme(tmp_path, {}), iconbox_frames="on") is False
    assert plasmastyle.tasks_hover(_theme(tmp_path, {}), iconbox_frames="off") is True


def test_tasks_synthesized_sets_keep_the_e16_fill_rule(tmp_path: Path) -> None:
    """A `__FILLRULE __TILE*` iclass tiles its center. The synthesized
    states come from the same art, so they must tile too — a tiled
    `normal-` beside a stretched `hover-` changes the frame's texture the
    moment the mouse touches it."""
    png = _bevel_png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png,
            fill_by_state={"normal": FILL_TILE},
        ),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    ids = _ids(svg)
    for prefix in ("normal-", "hover-", "attention-", "minimized-", "focus-",
                   "progress-", "", "north-focus-", "west-focus-"):
        assert f"{prefix}hint-tile-center" in ids, prefix
    # And a stretched iclass (E16's default) tiles nothing anywhere.
    plain = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    stretched = plasmastyle.build_tasks(plain, iconbox_frames="on")
    assert stretched is not None
    assert not any("tile-center" in i for i in _ids(stretched))


def test_tasks_every_set_reports_the_same_margins(tmp_path: Path) -> None:
    """The focus set's bar edge is 2 px thicker than every other set's, and
    FrameSvg reads an unhinted side's margin off the border thickness — so
    a padding-less iclass would inset the active task's icon further than
    the rest and the icon would jump on focus. Explicit hints pin them."""
    png = _bevel_png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass("DEFAULT_ICON_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}

    def margins(prefix: str) -> dict[str, tuple[str | None, str | None]]:
        return {
            side: (
                by_id[f"{prefix}hint-{side}-margin"].get("width"),
                by_id[f"{prefix}hint-{side}-margin"].get("height"),
            )
            for side in ("left", "right", "top", "bottom")
        }

    baseline = margins("normal-")
    for prefix in ("hover-", "attention-", "minimized-", "progress-", "",
                   "focus-", "north-focus-", "west-focus-", "east-focus-"):
        assert margins(prefix) == baseline, prefix


def test_tasks_declared_padding_still_drives_the_margins(tmp_path: Path) -> None:
    """With a real __PADDING the hints come from E16, scaled — the
    uniform-margin fallback only fills in for a padding-less iclass."""
    png = _bevel_png(tmp_path, "iconbtn.png")
    theme = _theme(tmp_path, {
        "DEFAULT_ICON_BUTTON": _iclass(
            "DEFAULT_ICON_BUTTON", normal=png, padding=(3, 3, 3, 3)
        ),
    }, scale=2)
    svg = plasmastyle.build_tasks(theme, iconbox_frames="on")
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    for prefix in ("normal-", "hover-", "focus-", "north-focus-"):
        assert by_id[f"{prefix}hint-left-margin"].get("width") == "6"  # 3 x 2


def test_tasks_attention_is_lighter_than_hover(tmp_path: Path) -> None:
    """attention = the HOVER plate lightened again, not the normal one:
    25% off normal lands only 13% above hover and the two states read
    the same on a panel."""
    plate = Image.new("RGBA", (8, 8), (100, 100, 100, 255))
    states = plasmastyle._synth_task_states(plate)
    normal = plate.getpixel((4, 4))
    hover = states["hover"].getpixel((4, 4))
    attention = states["attention"].getpixel((4, 4))
    assert isinstance(normal, tuple) and isinstance(hover, tuple)
    assert isinstance(attention, tuple)
    # 100 -> 12% toward white = 118 -> another 25% of what is left = 152.
    assert (normal[0], hover[0], attention[0]) == (100, 118, 152)
    # The attention step must be the bigger one, or the two states read
    # alike on a panel — the whole point of stacking it on hover.
    assert attention[0] - hover[0] > hover[0] - normal[0]
    assert states["minimized"].getpixel((4, 4))[3] == round(
        255 * plasmastyle.TASKS_MINIMIZED_ALPHA
    )
