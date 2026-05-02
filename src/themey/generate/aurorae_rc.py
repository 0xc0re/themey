"""Aurorae <name>rc INI writer.

``RawConfigParser`` preserves ``%`` characters in values (some KDE color values
use ``%`` in font names via ``BasicInterpolation``). The subclass form
``optionxform = staticmethod(str)`` preserves KDE's case-sensitive keys
(``LeftButtons``, ``BackgroundNormal``, etc.) without tripping pyright basic's
"cannot assign method to instance" error that the bare ``cp.optionxform = str``
form raises.

Layout numerical mapping (fixed in e13 regression — visual-tune iter 1):

    PaddingLeft  = border_size_left  * scale   (total left decoration space)
    PaddingRight = border_size_right * scale
    PaddingTop   = border_size_top   * scale   (total top decoration space)
    PaddingBottom= border_size_bottom* scale

    BorderLeft   = edge_scaling_left  of left-edge iclass  (thin visual frame)
    BorderRight  = edge_scaling_right of right-edge iclass
    BorderBottom = edge_scaling_bottom of bottom-edge iclass
    (BorderTop is omitted — Aurorae uses TitleHeight for the top bar area)

    TitleHeight  = image height of titlebar iclass (FIN/TITLEBAR) at scale

Previous (wrong) formula was ``BorderLeft = border_size_left * scale`` which
produced grotesquely wide left borders (80px for e13 vs. ~6px correct) because
``border_size_left`` in E16 includes the entire interactive zone (buttons +
frame), not just the thin visual frame edge that Aurorae ``BorderLeft`` expects.

These are Open Question A2 from 01-RESEARCH.md — visual-gate-tunable. The
formula block is isolated in ``_layout_values`` so Plan 09's visual gate can
adjust a single function without touching callers.

# visual-tune iter 1: BorderLeft from edge_scaling not border_size; PaddingLeft
# from border_size * scale; TitleHeight from iclass image height.
"""
from __future__ import annotations

import configparser
from pathlib import Path

from PIL import Image

from themey.ir import IClassSpec, Theme


def _format_color_rgba(rgb: tuple[int, int, int]) -> str:
    """Format RGB tuple as ``R,G,B,255`` (full alpha, 4-tuple)."""
    return f"{rgb[0]},{rgb[1]},{rgb[2]},255"


def _get_image_size(p: Path | None) -> tuple[int, int] | None:
    """Return (width, height) in pixels of an image file, or None on failure."""
    if p is None or not p.is_file():
        return None
    try:
        with Image.open(p) as img:
            return img.size
    except Exception:
        return None


_SIDE_PATTERNS: dict[str, list[str]] = {
    "left": ["WIN_SIDE_LEFT", "SIDE_LEFT", "BUTTONL", "WIN_LEFT"],
    "right": ["WIN_SIDE_RIGHT", "SIDE_RIGHT", "BUTTONR", "WIN_RIGHT"],
    "bottom": ["WIN_BOTTOM", "BUTTONB", "BAR_BOTTOM", "BOTTOM"],
    "top": ["TITLE_BAR_HORIZONTAL", "TITLEBAR", "TITLE_BAR", "FIN", "BAR_TOP",
            "WIN_TOP_TITLE", "WIN_TOP"],
}


def _find_iclass(side: str, iclasses: dict[str, IClassSpec]) -> IClassSpec | None:
    """Find the best iclass for a named decoration side by name-pattern matching."""
    upper_names = {name.upper(): name for name in iclasses}
    for pat in _SIDE_PATTERNS.get(side, []):
        if pat in upper_names:
            return iclasses[upper_names[pat]]
    # Substring fallback
    for pat in _SIDE_PATTERNS.get(side, []):
        for up, orig in upper_names.items():
            if pat in up:
                return iclasses[orig]
    return None


def _border_width_from_iclass(
    ic: IClassSpec | None,
    dimension: str,
    fallback: int,
    scale: int,
) -> int:
    """Derive a border thickness from an iclass image dimension.

    For side borders (left/right), use the image WIDTH.
    For the bottom border, use the image HEIGHT.

    Falls back to edge_scaling if the image is missing, then to ``fallback``.

    Args:
        ic: The iclass (may be None).
        dimension: ``"width"`` for left/right borders, ``"height"`` for bottom.
        fallback: Raw pixel value to use when all other sources fail.
        scale: The conversion scale factor.

    Returns:
        Border width in output pixels, at least 2.
    """
    if ic is not None:
        img_path = ic.normal or ic.normal_active
        size = _get_image_size(img_path)
        if size is not None:
            raw = size[0] if dimension == "width" else size[1]
            return max(2, raw * scale)
        # Fallback to edge_scaling
        axis = 0 if dimension == "width" else 3
        raw = ic.edge_scaling[axis]
        if raw > 0:
            return max(2, raw * scale)
    return max(2, fallback * scale)


def _title_height(theme: Theme, scale: int) -> int:
    """Derive TitleHeight in output pixels from the titlebar iclass image height.

    Looks up the top-edge iclass (TITLEBAR / FIN / TITLE_BAR_HORIZONTAL) in
    priority order:
    1. FIN (a thin horizontal strip) — most accurate for e13-style themes
    2. TITLEBAR (the full top area artwork)
    3. TITLE_BAR_HORIZONTAL (generic titlebar image)
    4. First matched "top" iclass

    Reads image height (normal_active preferred, normal fallback) and scales
    by ``scale``. Clamps to [12, 80] for KDE layout sanity.
    """
    # Try FIN first — it's the pure titlebar strip in e13-style themes
    for name_pref in ["FIN", "TITLEBAR", "TITLE_BAR_HORIZONTAL"]:
        ic = theme.iclasses.get(name_pref)
        if ic is not None:
            img_path = ic.normal_active or ic.normal
            size = _get_image_size(img_path)
            if size is not None and size[1] > 0:
                return max(12, min(80, size[1] * scale))

    # Generic top-edge iclass
    ic = _find_iclass("top", theme.iclasses)
    if ic is not None:
        img_path = ic.normal_active or ic.normal
        size = _get_image_size(img_path)
        if size is not None and size[1] > 0:
            return max(12, min(80, size[1] * scale))

    # Fallback: use a fraction of border_size_top that won't be grotesque
    raw = max(12, theme.border.border_size_top * scale // 3)
    return min(80, raw)


def _layout_values(theme: Theme) -> dict[str, str]:
    """Compute the [Layout] section from Theme border sizes, iclass edge_scaling, and scale.

    Key formula change (e13 regression fix, visual-tune iter 1):
    - Border{Left,Right,Bottom} = edge_scaling of the corresponding side iclass
      (thin visual frame edge), NOT border_size * scale (which is the full E16
      zone including button stacking areas).
    - Padding{Left,Right,Top,Bottom} = border_size * scale (total decoration
      space, which Aurorae uses for window geometry / shadow region).
    - TitleHeight = iclass image height * scale (actual artwork height).

    Tunable formula block (Open Question A2 — adjust here for visual gate):
    """
    s = theme.scale

    # Padding = total decoration zone per side (border_size * scale)
    pad_l = theme.border.border_size_left * s
    pad_r = theme.border.border_size_right * s
    pad_t = theme.border.border_size_top * s
    pad_b = theme.border.border_size_bottom * s

    # BorderLeft/Right/Bottom = visual frame width from the side iclass image size.
    # Left/right borders: use image WIDTH (the iclass tile is as wide as the border).
    # Bottom border: use image HEIGHT (the tile is as tall as the bottom border).
    # Fallback when no iclass: border_size // 4 (much smaller than border_size itself).
    left_ic = _find_iclass("left", theme.iclasses)
    right_ic = _find_iclass("right", theme.iclasses)
    bottom_ic = _find_iclass("bottom", theme.iclasses)

    bl = _border_width_from_iclass(
        left_ic, "width", max(1, theme.border.border_size_left // 4), s
    )
    br = _border_width_from_iclass(
        right_ic, "width", max(1, theme.border.border_size_right // 4), s
    )
    bb = _border_width_from_iclass(
        bottom_ic, "height", max(1, theme.border.border_size_bottom // 4), s
    )

    # TitleHeight from artwork image height
    th = _title_height(theme, s)

    return {
        "BorderLeft": str(bl),
        "BorderRight": str(br),
        "BorderBottom": str(bb),
        "BorderTop": str(th),
        "TitleEdgeTop": str(2 * s),
        "TitleEdgeBottom": str(2 * s),
        "TitleEdgeLeft": str(4 * s),
        "TitleEdgeRight": str(4 * s),
        "TitleBorderLeft": str(2 * s),
        "TitleBorderRight": str(2 * s),
        "TitleHeight": str(th),
        "ButtonWidth": str(12 * s),
        "ButtonHeight": str(12 * s),
        "ButtonSpacing": str(4 * s),
        "ButtonMarginTop": str(2 * s),
        "ButtonMarginLeft": str(3 * s),
        "ExplicitButtonSpacer": "0",
        "PaddingTop": str(pad_t),
        "PaddingBottom": str(pad_b),
        "PaddingLeft": str(pad_l),
        "PaddingRight": str(pad_r),
    }


class _CaseSensitiveRawConfigParser(configparser.RawConfigParser):
    """RawConfigParser subclass that preserves key case verbatim.

    KDE reads keys like ``LeftButtons`` and ``BackgroundNormal`` case-
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

    cp["General"] = {
        "ActiveTextColor": _format_color_rgba(theme.palette.text_active),
        "InactiveTextColor": _format_color_rgba(theme.palette.text_inactive),
        "TitleAlignment": "Center",
        "TitleVerticalAlignment": "Center",
        "UseTextShadow": "true",
        "ActiveTextShadowColor": "0,0,0,255",
        "InactiveTextShadowColor": "0,0,0,255",
        "TextShadowOffsetX": "0",
        "TextShadowOffsetY": "1",
        "LeftButtons": theme.left_buttons,
        "RightButtons": theme.right_buttons,
        "Shadow": "true",
        "Animation": "1",
    }
    cp["Layout"] = _layout_values(theme)

    out_path = out_dir / f"{theme.name}rc"
    with open(out_path, "w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
    return out_path
