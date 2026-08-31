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


def test_panel_background_is_flat_translucent_tint(tmp_path: Path) -> None:
    png = _png(tmp_path, "dragbar.png")  # solid (200, 60, 60)
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", edge=(2, 2, 2, 2), normal=png
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    ids = _ids(svg)
    assert {"topleft", "top", "topright", "left", "center", "right",
            "bottomleft", "bottom", "bottomright"} <= ids
    assert {"hint-left-margin", "hint-right-margin", "hint-top-margin",
            "hint-bottom-margin"} <= ids
    # A tint, not art: no embedded images anywhere.
    assert not any(e.tag.endswith("image") for e in svg.iter())
    center = next(e for e in svg.iter() if e.get("id") == "center")
    style = center.get("style", "")
    assert "fill:#c83c3c" in style  # dominant of the (200, 60, 60) art
    assert "opacity:0.85" in style
    assert any(
        "translucent tint" in n and "DESKTOP_DRAGBUTTON_HORIZ" in n
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


def test_panel_background_drops_east_west_sets(tmp_path: Path) -> None:
    h = _png(tmp_path, "h.png")
    v = _png(tmp_path, "v.png")
    theme = _theme(tmp_path, {
        "ICONBOX_HORIZONTAL": _iclass("ICONBOX_HORIZONTAL", normal=h),
        "ICONBOX_VERTICAL": _iclass("ICONBOX_VERTICAL", normal=v),
    })
    svg = plasmastyle.build_panel_background(theme)
    ids = _ids(svg)
    # A flat tint has no orientation; every prefix falls back to unprefixed.
    assert not any(
        i.startswith(("north-", "south-", "east-", "west-")) for i in ids
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


def test_exact_fit_caps_stay_cap_only(tmp_path: Path) -> None:
    """Caps summing to exactly the image size are authored cap-only art —
    no middle is emitted and no shrink note fires."""
    png = _png(tmp_path, "base.png", size=(8, 8))
    theme = _theme(tmp_path, {
        "TT_MAIN": _iclass("TT_MAIN", edge=(4, 4, 0, 0), normal=png),
    })
    svg = plasmastyle.build_tooltip(theme)
    assert svg is not None
    assert "center" not in _ids(svg)
    assert {"left", "right"} <= _ids(svg)
    assert not any("caps shrunk" in n for n in theme.notes)


def test_never_emits_tile_center_hint(tmp_path: Path) -> None:
    png = _png(tmp_path, "bar.png")
    theme = _theme(tmp_path, {
        "DESKTOP_DRAGBUTTON_HORIZ": _iclass(
            "DESKTOP_DRAGBUTTON_HORIZ", normal=png, padding=(2, 2, 2, 2)
        ),
    })
    svg = plasmastyle.build_panel_background(theme)
    assert svg is not None
    assert not any("tile-center" in i for i in _ids(svg))


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

    # Byte-identical mirrors for everything EXCEPT the panel, whose
    # solid/opaque variants are re-rendered opaque.
    for rel in style.shipped:
        original = (out / rel).read_bytes()
        for variant in ("solid", "opaque"):
            mirrored = (out / variant / rel).read_bytes()
            if rel == plasmastyle.PANEL_SVG:
                assert mirrored != original
            else:
                assert mirrored == original

    colors = (out / "colors").read_text()
    assert "[Colors:Window]" in colors
    assert "ColorScheme=themey_TestStyle" in colors


def test_write_panel_variants(tmp_path: Path) -> None:
    """Base panel is translucent; solid/ and opaque/ are genuinely opaque
    (AdaptiveTransparency swaps to solid/ when a window touches the panel)."""
    theme = _rich_theme(tmp_path)
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
