"""Aurorae <name>rc INI writer.

Layout values are derived from ``decoration_svg.strip_thicknesses(theme)`` so
the rc and the SVG see one source of truth. The invariants the SVG writer
documents hold:

    BorderTop    == decoration-top strip height
    BorderLeft   == decoration-left strip width
    BorderRight  == decoration-right strip width
    BorderBottom == decoration-bottom strip height
    TitleHeight  <= BorderTop  (title-text band lives WITHIN the top zone)

``TitleHeight`` was historically equal to ``BorderTop`` (single-iclass-strip
themes); since the compositor + chrome-growth work, ``BorderTop`` can grow
to fit corner art while ``TitleHeight`` stays at the title-bearing part's
canonical span. When the title is small relative to the grown chrome, it is
centered vertically via ``TitleEdgeTop``.

``Padding*`` is 0. E16 has no shadow concept, and emitting a large shadow
zone here paints the title text into an empty area above the actual frame.
The shadow becomes a Phase-2 enhancement if wanted.

``RawConfigParser`` preserves ``%`` (some KDE values use it) and
``optionxform = staticmethod(str)`` keeps KDE's case-sensitive keys intact.
"""
from __future__ import annotations

import configparser
import io
from pathlib import Path
from typing import cast

from PIL import Image

from themey.analyze.buttons import title_part
from themey.generate.composite import (
    BUTTON_CODE_TO_RC_SUFFIX,
    REFERENCE_H,
    REFERENCE_W,
    button_layout,
    button_widths_by_code,
    compose_region,
    resolve_parts,
    title_opaque_rows_ref,
)
from themey.generate.decoration_svg import (
    DEFAULT_MAX_BORDER,
    DEFAULT_MAX_SIDE_BORDER,
    strip_thicknesses,
)
from themey.ir import Theme

# Luminance difference (0..1) below which we treat text and bg as too close
# in brightness to be readable. 0.2 ≈ 50 / 255 in 8-bit terms, per the plan.
_MIN_LUMINANCE_DIFF: float = 0.2


def _format_color_rgba(rgb: tuple[int, int, int]) -> str:
    """Format RGB tuple as ``R,G,B,255``."""
    return f"{rgb[0]},{rgb[1]},{rgb[2]},255"


def _luminance(rgb: tuple[int, int, int]) -> float:
    """Rec. 709 relative luminance in 0..1 (gamma-uncorrected)."""
    r, g, b = (c / 255.0 for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _sample_top_bg_rgb(
    theme: Theme, *, prefer_active: bool
) -> tuple[int, int, int] | None:
    """Average opaque pixel RGB of the composited top region, or None.

    Used to detect when the configured title-text color would be illegible
    against the rendered title-bar background — e.g. white text on a
    near-white background.
    """
    try:
        data = compose_region(
            theme,
            "top",
            prefer_active=prefer_active,
            max_border_output=DEFAULT_MAX_BORDER,
            max_side_output=DEFAULT_MAX_SIDE_BORDER,
        )
    except Exception:
        return None
    try:
        with Image.open(io.BytesIO(data)) as im:
            rgba = im.convert("RGBA")
    except Exception:
        return None
    # Pillow's getdata() stub is untyped-ish (float | tuple | None); an RGBA
    # image always yields 4-tuples.
    pixels = cast("list[tuple[int, int, int, int]]", rgba.getdata())
    opaque = [px for px in pixels if px[3] > 32]
    if not opaque:
        return None
    n = len(opaque)
    return (
        sum(px[0] for px in opaque) // n,
        sum(px[1] for px in opaque) // n,
        sum(px[2] for px in opaque) // n,
    )


def _contrast_corrected_text_rgb(
    text_rgb: tuple[int, int, int],
    bg_rgb: tuple[int, int, int] | None,
) -> tuple[tuple[int, int, int], bool]:
    """Return (text_rgb_to_emit, swapped). When ``bg_rgb`` is provided and
    luminance contrast is below ``_MIN_LUMINANCE_DIFF``, swap text to pure
    black or white based on bg brightness.
    """
    if bg_rgb is None:
        return (text_rgb, False)
    if abs(_luminance(text_rgb) - _luminance(bg_rgb)) >= _MIN_LUMINANCE_DIFF:
        return (text_rgb, False)
    return (((0, 0, 0) if _luminance(bg_rgb) > 0.5 else (255, 255, 255)), True)


def _title_bar_part(theme: Theme) -> tuple[int, int, int, int] | None:
    """Return the resolved bbox of the title-bearing part, or None.

    Canonical E16 grammar: the title region is the part flagged
    ``__FLAGS __FLAG_TITLE``. We look up that part by flag, then return its
    resolved bbox at the reference window size.
    """
    tp = title_part(theme.border.parts)
    if tp is None:
        return None
    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)
    idx = theme.border.parts.index(tp)
    return bboxes.get(idx)


def _title_bar_y_range(theme: Theme) -> tuple[int, int]:
    """Return (y_top, y_bottom) of the title bar in reference coords.

    NOT clamped to ``border_size_top`` — when the chrome is grown to fit
    corner art, callers need the title's *canonical* y in reference coords
    so they can decide whether to center it within the grown chrome.
    """
    bb = _title_bar_part(theme)
    if bb is None:
        return (0, theme.border.border_size_top)
    y_top = max(0, bb[1])
    y_bot = bb[3]
    if y_bot > y_top:
        return (y_top, y_bot)
    return (0, theme.border.border_size_top)


def _title_bar_x_range(theme: Theme) -> tuple[int, int]:
    """Return (x_left_offset, x_right_offset) of the title bar from inner edges."""
    bsl = theme.border.border_size_left
    bsr = theme.border.border_size_right
    bb = _title_bar_part(theme)
    if bb is None:
        return (0, 0)
    left_off = max(0, bb[0] - bsl)
    right_off = max(0, (REFERENCE_W - bsr) - bb[2])
    return (left_off, right_off)


def _layout_values(theme: Theme) -> dict[str, str]:
    """Build the [Layout] section.

    Border sizes come from ``strip_thicknesses`` (full E16 zone x scale).
    Title positioning uses the resolved bbox of the title-bearing part.

    Adaptive centering: when the title-bearing part fills < 60% of the
    output ``BorderTop`` (e.g. Aliens grows BorderTop to 120 to fit the
    179-tall CORNER_TL alien-head, leaving the 13-tall title floating at
    the top of a 60-tall reference band), the title text is vertically
    centered within the chrome. When the title fills most of the chrome
    (e.g. e13's TITLEBAR is 46 tall in a 46 tall top zone), canonical
    placement is honored. A note is appended to ``theme.notes`` when
    centering fires so ``report.txt`` documents the decision.
    """
    s = int(theme.scale)  # SVG backend is integer-scale by contract
    thick = strip_thicknesses(theme)
    top, bot = thick["top"], thick["bottom"]
    lft, rgt = thick["left"], thick["right"]

    # Canonical title y range in reference coords (NOT clamped to BST —
    # we need the source value before deciding whether to center).
    y_top_ref, y_bot_ref = _title_bar_y_range(theme)
    canonical_title_height_ref = max(1, y_bot_ref - y_top_ref)
    # Shaped titlebars (e13's transparent notch below row 30) must not count
    # transparency as title: clamp to the image's structural rows. BorderTop
    # keeps the full zone — the notch stays in the band and shows wallpaper.
    opaque_rows = title_opaque_rows_ref(theme)
    if 0 < opaque_rows < canonical_title_height_ref:
        note = (
            f"aurorae_rc: TitleHeight trimmed to the title art's opaque rows "
            f"({opaque_rows * s} of {canonical_title_height_ref * s} output "
            "px); the shaped transparent notch stays in the band and shows "
            "the wallpaper"
        )
        if note not in theme.notes:
            theme.notes.append(note)
        canonical_title_height_ref = opaque_rows
    title_height = max(2 * s, canonical_title_height_ref * s)
    # Cap title_height inside the (possibly grown) chrome.
    title_height = min(title_height, max(2 * s, top))

    canonical_top_output = max(0, y_top_ref * s)
    centered = False
    if title_height < int(top * 0.6):
        # Centering fires: title is small relative to grown chrome.
        title_edge_top = max(0, (top - title_height) // 2)
        centered = True
        # Idempotent: a single rc-writer invocation per theme is the norm,
        # but if a future code path regenerates the rc it must not duplicate
        # this note.
        if not any(
            n.startswith("aurorae_rc: title centered vertically")
            for n in theme.notes
        ):
            theme.notes.append(
                f"aurorae_rc: title centered vertically "
                f"(title_height={title_height} < 60% of BorderTop={top}); "
                f"canonical y_top={canonical_top_output} preserved as "
                "report-only context"
            )
    else:
        title_edge_top = min(canonical_top_output, max(0, top - title_height))
    title_edge_bottom = max(0, top - title_edge_top - title_height)

    # KWin needs at least 1-2 px of padding at top and bottom for the text
    # baseline; without it the title vanishes (LiteGnome's title-bearing
    # part spans the full top zone → canonical TitleEdgeTop=0). Clamp both
    # edges to max(1, scale) and trim title_height to keep the layout
    # tiling — total padding + height must equal BorderTop.
    min_pad = max(1, s)
    if title_edge_top < min_pad:
        title_edge_top = min_pad
    if title_edge_bottom < min_pad:
        title_edge_bottom = min_pad
    if title_edge_top + title_height + title_edge_bottom > top:
        title_height = max(2 * s, top - title_edge_top - title_edge_bottom)
    # If trimming still doesn't fit, give up on the clamp on the side that
    # has slack — preserve title_height >= 2*s above all.
    if title_edge_top + title_height + title_edge_bottom > top:
        title_edge_bottom = max(0, top - title_edge_top - title_height)
    if title_edge_top + title_height + title_edge_bottom > top:
        title_edge_top = max(0, top - title_height - title_edge_bottom)

    # Title bar x offsets relative to the inner edges of the left/right zones.
    x_left_off, x_right_off = _title_bar_x_range(theme)
    title_edge_left = max(0, x_left_off * s)
    title_edge_right = max(0, x_right_off * s)

    btn = button_layout(theme)
    button_w = btn["ButtonWidth"]
    button_h = btn["ButtonHeight"]
    button_spacing = btn["ButtonSpacing"]
    # Aurorae's ButtonMarginTop is measured from titleEdgeTop, not chrome top.
    # Canonical position: button_y_top_ref - title_y_top_ref (clamped to >= 0).
    raw_margin_top = btn["ButtonMarginTop"]  # button_y_top_ref * s (legacy form)
    button_margin_top = max(0, raw_margin_top - canonical_top_output)
    # When centered, keep the buttons centered with the title rather than
    # floating above — preserve their canonical offset relative to title_top.
    # (No additional adjustment needed: button_margin_top above is already
    # the y delta between title-top-ref and button-top-ref, scaled.)
    _ = centered  # silence unused-warning; the flag's effect lives in notes

    layout = {
        "BorderLeft": str(lft),
        "BorderRight": str(rgt),
        "BorderBottom": str(bot),
        "BorderTop": str(top),
        "TitleEdgeTop": str(title_edge_top),
        "TitleEdgeBottom": str(title_edge_bottom),
        "TitleEdgeLeft": str(title_edge_left),
        "TitleEdgeRight": str(title_edge_right),
        # Maximized windows keep the same title band geometry.
        "TitleEdgeTopMaximized": str(title_edge_top),
        "TitleEdgeBottomMaximized": str(title_edge_bottom),
        "TitleEdgeLeftMaximized": str(title_edge_left),
        "TitleEdgeRightMaximized": str(title_edge_right),
        "TitleBorderLeft": str(2 * s),
        "TitleBorderRight": str(2 * s),
        "TitleHeight": str(title_height),
        "ButtonWidth": str(button_w),
        "ButtonHeight": str(button_h),
        "ButtonSpacing": str(button_spacing),
        "ButtonMarginTop": str(button_margin_top),
        "ButtonMarginTopMaximized": str(button_margin_top),
        "ExplicitButtonSpacer": "0",
        "PaddingTop": "0",
        "PaddingBottom": "0",
        "PaddingLeft": "0",
        "PaddingRight": "0",
    }
    # Per-button widths from each part's own bbox (E16 buttons are often
    # different sizes; Aurorae reads ButtonWidth<Suffix> per button).
    for code, width in button_widths_by_code(theme).items():
        layout[f"ButtonWidth{BUTTON_CODE_TO_RC_SUFFIX[code]}"] = str(width)
    return layout


class _CaseSensitiveRawConfigParser(configparser.RawConfigParser):
    """RawConfigParser subclass that preserves key case verbatim.

    KDE reads keys like ``TitleAlignment`` and ``BackgroundNormal`` case-
    sensitively. The default ``optionxform = str.lower`` silently mangles them.

    Pyright basic flags the bare ``cp.optionxform = str`` form as
    "cannot assign method to instance"; the class-level ``staticmethod``
    form is the canonical fix from the configparser docs.
    """

    optionxform = staticmethod(str)  # type: ignore[assignment]


def write_aurorae_rc(theme: Theme, out_dir: Path) -> Path:
    """Write ``<theme.name>rc`` INI file into ``out_dir``.

    Follows the ``Ednarc`` format exactly: ``[General]`` + ``[Layout]`` sections,
    ``space_around_delimiters=False`` so KDE's parser sees ``Key=Value``.

    Args:
        theme: Frozen Theme IR.
        out_dir: Directory to write into. Created if absent.

    Returns:
        Path to the written ``<name>rc`` file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = _CaseSensitiveRawConfigParser()

    active_bg = _sample_top_bg_rgb(theme, prefer_active=True)
    inactive_bg = _sample_top_bg_rgb(theme, prefer_active=False)
    active_text, active_swapped = _contrast_corrected_text_rgb(
        theme.palette.text_active, active_bg
    )
    inactive_text, inactive_swapped = _contrast_corrected_text_rgb(
        theme.palette.text_inactive, inactive_bg
    )
    if active_swapped:
        note = (
            f"aurorae_rc: ActiveTextColor swapped "
            f"{theme.palette.text_active} → {active_text} for contrast "
            f"against title-bar bg {active_bg}"
        )
        if note not in theme.notes:
            theme.notes.append(note)
    if inactive_swapped:
        note = (
            f"aurorae_rc: InactiveTextColor swapped "
            f"{theme.palette.text_inactive} → {inactive_text} for contrast "
            f"against title-bar bg {inactive_bg}"
        )
        if note not in theme.notes:
            theme.notes.append(note)

    # Map TEXT1's __JUSTIFICATION / __DRAWING_EFFECT into Aurorae values
    # where the theme expresses an opinion. The text-shadow keys are read
    # by the v1 plugin (org.kde.kwin.aurorae, themeconfig.cpp) and ignored
    # by v2 — harmless there, faithful on v1.
    text1 = theme.tclasses.get("TEXT1")
    title_alignment = "Center"
    use_text_shadow = "true"
    active_shadow_color = "0,0,0,255"
    inactive_shadow_color = "0,0,0,255"
    if text1 is not None:
        if text1.alignment is not None:
            title_alignment = text1.alignment
        if text1.effect is not None:
            use_text_shadow = "true" if text1.effect == "__EFFECT_SHADOW" else "false"
        if text1.effect_color is not None:
            active_shadow_color = _format_color_rgba(text1.effect_color)
            inactive_shadow_color = active_shadow_color

    # Only keys Aurorae (Plasma 6.6, v1 or v2) actually reads. Button ORDER
    # comes from kwinrc ButtonsOnLeft/Right, so LeftButtons/RightButtons are
    # not emitted; ButtonMarginLeft is likewise unread. Shadow defaults to
    # true in v1 and is not read by v2.
    cp["General"] = {
        "ActiveTextColor": _format_color_rgba(active_text),
        "InactiveTextColor": _format_color_rgba(inactive_text),
        "TitleAlignment": title_alignment,
        "TitleVerticalAlignment": "Center",
        "UseTextShadow": use_text_shadow,
        "ActiveTextShadowColor": active_shadow_color,
        "InactiveTextShadowColor": inactive_shadow_color,
        "TextShadowOffsetX": "0",
        "TextShadowOffsetY": "1",
        "Animation": "1",
    }
    cp["Layout"] = _layout_values(theme)
    # Themey-private section (Aurorae ignores unknown groups): the theme's
    # L/R button binning. KWin's button ORDER is global kwinrc state that no
    # theme file can set, so ``themey apply`` reads this to reproduce the
    # E16 layout (e13 stacks all four buttons on the left).
    cp["Themey"] = {
        "LeftButtons": theme.left_buttons,
        "RightButtons": theme.right_buttons,
    }

    out_path = out_dir / f"{theme.name}rc"
    with open(out_path, "w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
    return out_path
