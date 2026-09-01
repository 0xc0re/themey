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
from themey.ir import BorderSpec, IClassSpec, Palette, TClassSpec, Theme

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
    )


def _tclass(name: str, fg=(200, 200, 150), fg_active=None) -> TClassSpec:
    return TClassSpec(name=name, fg_normal=fg, fg_active=fg_active)


def _ids(svg: ET.Element) -> set[str]:
    return {e.get("id") for e in svg.iter() if e.get("id")}


# ------------------------------------------------------------------ #
# Panel background
# ------------------------------------------------------------------ #


def test_panel_background_from_art_middle_tiled(tmp_path: Path) -> None:
    """Small-cap opaque bar art becomes a real 9-part panel set with a
    TILED middle (hint-tile-center — Breeze's own panel ships it) and the
    default flat-panel margins when the iclass has no __PADDING."""
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
    assert "hint-tile-center" in ids
    assert "hint-stretch-borders" in ids
    assert {"hint-left-margin", "hint-right-margin", "hint-top-margin",
            "hint-bottom-margin"} <= ids
    # Real art: embedded images, not tint rects.
    assert any(e.tag.endswith("image") for e in svg.iter())
    assert any(
        "panel background from iclass DESKTOP_DRAGBUTTON_HORIZ" in n
        and "tiled" in n
        for n in theme.notes
    )


def test_panel_background_cap_guard_falls_back_to_tint(tmp_path: Path) -> None:
    """Wordmark-sized caps (the Aliens dragbar failure mode) trip the cap
    guard; with no other candidate the panel degrades to the flat tint."""
    png = _png(tmp_path, "dragbar.png", size=(160, 16))  # solid (200, 60, 60)
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(133, 2, 0, 0), normal=png
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
    """Aliens' census shape: dragbar rejected (giant cap) -> the iconbox
    trough (small caps) backs the panel instead."""
    big = _png(tmp_path, "dragbar.png", size=(160, 16))
    small = _png(tmp_path, "iconbox.png", color=(20, 90, 20, 255))
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(133, 2, 0, 0), normal=big
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
    for prefix in ("west-", "east-"):
        assert f"{prefix}center" in ids
        assert f"{prefix}hint-top-margin" in ids
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


def test_tile_center_hint_only_in_panel_background(tmp_path: Path) -> None:
    """E16 stretches middles everywhere EXCEPT bar troughs — the tile hint
    is allowed only in widgets/panel-background.svg. Build every file from
    a maximal synthetic theme and check the census."""
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
        if rel == plasmastyle.PANEL_SVG:
            assert has_tile, "art panel must tile its middle"
        else:
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
    svg = plasmastyle.build_tasks(theme)
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
    svg = plasmastyle.build_tasks(theme)
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
    theme = _theme(tmp_path, {})
    assert plasmastyle.build_tasks(theme) is None


def test_tasks_falls_back_to_dock_button(tmp_path: Path) -> None:
    png = _png(tmp_path, "dock.png")
    theme = _theme(tmp_path, {
        "DEFAULT_DOCK_BUTTON": _iclass("DEFAULT_DOCK_BUTTON", normal=png),
    })
    svg = plasmastyle.build_tasks(theme)
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


def test_viewitem_normal_set_when_normal_art_exists(tmp_path: Path) -> None:
    n = _png(tmp_path, "n.png")
    hi = _png(tmp_path, "h.png")
    theme = _theme(tmp_path, {
        "MENU_SEL": _iclass("MENU_SEL", normal=n, hilited=hi),
    })
    svg = plasmastyle.build_viewitem(theme)
    assert svg is not None
    assert "normal-center" in _ids(svg)


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
    """Zero declared edge on pill art → caps at the cross-section radius;
    larger declared caps survive."""
    assert plasmastyle._viewitem_caps((0, 0, 0, 0), 164, 20) == (9, 9, 9, 9)
    assert plasmastyle._viewitem_caps((20, 20, 2, 2), 202, 31) == (20, 20, 14, 14)
    # Tiny art never degenerates below a 1-px cap or above the half-size.
    assert plasmastyle._viewitem_caps((0, 0, 0, 0), 3, 3) == (1, 1, 1, 1)


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
    hi = _png(tmp_path, "sel.png", color=(60, 20, 90, 255))
    theme = _theme(
        tmp_path,
        {"MENU_SEL": _iclass("MENU_SEL", hilited=hi)},
        {"MENU_TEXT": _tclass("MENU_TEXT", fg=(20, 20, 20), fg_active=(255, 255, 200))},
    )
    scheme = plasmastyle.style_scheme(
        theme, shipped=frozenset({plasmastyle.VIEWITEM_SVG})
    )
    assert scheme.selection.background_normal == (60, 20, 90)
    assert scheme.selection.foreground_normal == (255, 255, 200)
    assert any("Selection" in n and "approximated" in n for n in theme.notes)


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


def test_line_thickness_clamped_and_vertical_rotated(tmp_path: Path) -> None:
    """Aliens/e13 point the separator at a ~64 px bevel box E16 squeezed
    into a thin rule — clamp to LINE_MAX_REF_THICKNESS, never render the
    box at its own height."""
    art = _png(tmp_path, "bt2.png", size=(64, 64))
    theme = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass("DIALOG_WIDGET_SEPARATOR", normal=art),
    }, scale=2)
    svg = plasmastyle.build_line(theme)
    assert svg is not None
    by_id = {e.get("id"): e for e in svg.iter() if e.get("id")}
    h_img = next(iter(by_id["horizontal-line"]))
    v_img = next(iter(by_id["vertical-line"]))
    assert h_img.get("height") == str(scale_px(4, 2))
    assert h_img.get("width") == str(scale_px(64, 2))
    # Vertical = same art rotated: dimensions swap.
    assert v_img.get("width") == h_img.get("height")
    assert v_img.get("height") == h_img.get("width")
    assert any("squeezed" in n for n in theme.notes)

    # Authored-thin art (LiteGnome's 120x4 hline) is not squeezed further.
    thin = _png(tmp_path, "hline.png", size=(120, 4))
    theme2 = _theme(tmp_path, {
        "DIALOG_WIDGET_SEPARATOR": _iclass("DIALOG_WIDGET_SEPARATOR", normal=thin),
    }, scale=2)
    svg2 = plasmastyle.build_line(theme2)
    assert svg2 is not None
    assert not any("squeezed" in n for n in theme2.notes)


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
    assert set(style.shipped) == {plasmastyle.PANEL_SVG, plasmastyle.DIALOG_SVG}

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
    assert style.shipped == (plasmastyle.PANEL_SVG,)
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
