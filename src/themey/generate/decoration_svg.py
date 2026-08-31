"""decoration.svg writer with 36 FrameSvg IDs + hint rects + base64-embedded raster.

The required FrameSvg IDs are emitted verbatim:
  ``decoration-{topleft,top,topright,left,center,right,bottomleft,bottom,bottomright}``
plus the same 9 with the ``decoration-inactive-``, ``decoration-maximized-``
and ``decoration-maximized-inactive-`` prefixes (36 total). Without the
maximized groups Aurorae paints a blank title bar on maximized windows.

Hint rects (``decoration-hint-*-margin``, ``decoration-hint-stretch-borders``
and their ``decoration-inactive-`` twins) must carry the ``decoration-``
prefix — unprefixed ``hint-*`` ids are silently ignored by Aurorae.

Each region's PNG is *composited* from the E16 ``__BORDER_PART`` entries that
overlap the region's bbox. See ``composite.py`` for the layout math and
overlap-clipping rules. Interactive button iclasses (close/min/max/etc.) are
omitted — Aurorae renders those on top from the per-button SVGs. Button
ORDER is global (kwinrc ``ButtonsOnLeft``/``ButtonsOnRight``), not per
theme; the theme only decides which button SVGs exist.

Strip thicknesses follow the user-confirmed full-E16-zone rule:

    BorderTop    == TitleHeight == decoration-top strip height = BORDER_SIZE_TOP x scale
    BorderLeft   == decoration-left strip width                = BORDER_SIZE_LEFT x scale
    BorderRight  == decoration-right strip width               = BORDER_SIZE_RIGHT x scale
    BorderBottom == decoration-bottom strip height             = BORDER_SIZE_BOTTOM x scale

``aurorae_rc.py`` imports ``strip_thicknesses`` so the rc and the SVG see one
source of truth. The corner regions inherit ``Border*`` dimensions on each
axis (e.g., topleft.w = BorderLeft, topleft.h = BorderTop), preserving the
9-patch invariants asserted by ``test_svg_rc_invariant.py``.
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from themey.generate.composite import (
    MIDDLE_REF,
    compose_region,
    corner_extents,
    folded_corner_widths,
    required_border_extents,
)
from themey.images.embed import embed_png_b64
from themey.ir import Theme

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

SIDES: tuple[str, ...] = (
    "topleft",
    "top",
    "topright",
    "left",
    "center",
    "right",
    "bottomleft",
    "bottom",
    "bottomright",
)


# ---------------------------------------------------------------------------
# Strip thickness derivation — single source of truth shared with aurorae_rc.py
# ---------------------------------------------------------------------------


DEFAULT_MAX_BORDER: int = 120
"""Default cap (in output pixels) for the TOP band.

Grown borders that would render the full corner art (Aliens'
CORNER_TL is 179x124 source = 358x248 at scale=2) can exceed what KWin
displays gracefully — the chrome ends up looking like a separate banner
rather than a frame around the content. 120 output px keeps the chrome
visually framing the content while still showing a clipped but
recognizable portion of the corner art (~half the alien head).

Override with the CLI ``--max-border N`` flag for users who want
bigger chrome at the cost of usable content area.
"""

DEFAULT_MAX_SIDE_BORDER: int = 48
"""Cap (output px) for left/right/bottom.

Both Aurorae plugins in Plasma 6.6 (v1 ``org.kde.kwin.aurorae`` and the
default ``.v2``) clamp ``BorderLeft/Right/Bottom`` to the bracket selected
by System Settings "Border size"; 48 is the "Oversized" ceiling, so nothing
we emit can be squashed by more than that bracket. Only the title band
(``TitleHeight + TitleEdgeTop/Bottom``) is theme-controlled, so corner art
wider than a side is folded into the top corners
(``composite.folded_corner_widths``) and the left/right frame columns —
which FrameSvg paints at the hint-margin width, under the client — carry it.
"""


def strip_thicknesses(
    theme: Theme,
    max_border: int = DEFAULT_MAX_BORDER,
    max_side_border: int = DEFAULT_MAX_SIDE_BORDER,
) -> dict[str, int]:
    """Compute the four strip thicknesses (in output pixels) for *theme*.

    Single source of truth — the rc writer imports this. Returns a dict
    with keys ``top``, ``bottom``, ``left``, ``right``.

    Rule (user-confirmed "match the E16 look" semantics):

    For each side, take the max of:
      1. ``__BORDER_SIZE_<side>`` (the E16 chrome zone), and
      2. the extent of any non-interactive ``__BORDER_PART`` anchored to
         that edge — so corner art renders uncompressed.

    The top is clamped to ``[2, max_border]`` and the sides/bottom to
    ``[2, max_side_border]`` after scaling. Corner art that wouldn't fit a
    side is folded into the (unclamped) top corners instead.
    """
    # round(): the preview calls this at fractional (QML-only) scales;
    # identical to plain multiplication at the SVG backend's int scales.
    s = theme.scale
    ext = required_border_extents(theme)
    return {
        "top": max(2, min(max_border, round(ext["top"] * s))),
        "bottom": max(2, min(max_side_border, round(ext["bottom"] * s))),
        "left": max(2, min(max_side_border, round(ext["left"] * s))),
        "right": max(2, min(max_side_border, round(ext["right"] * s))),
    }


def _fold_note(theme: Theme) -> None:
    """Append an idempotent ``composite:`` note when sides were clamped."""
    s = int(theme.scale)  # SVG backend is integer-scale by contract
    req = required_border_extents(theme)
    thick = strip_thicknesses(theme)
    clamped = [
        f"{side}={req[side] * s}->{thick[side]}"
        for side in ("left", "right", "bottom")
        if req[side] * s > thick[side]
    ]
    if not clamped:
        return
    corner = corner_extents(theme)
    fold = ", ".join(
        f"{side} corner art {corner[side] * s}px wide kept in the title band"
        for side in ("left", "right")
        if corner[side] * s > thick[side]
    )
    msg = (
        "composite: side borders capped to "
        f"{DEFAULT_MAX_SIDE_BORDER}px (KWin 'Oversized' bracket ceiling): "
        + ", ".join(clamped)
        + (f"; {fold}" if fold else "")
    )
    if not any(n.startswith("composite: side borders capped") for n in theme.notes):
        theme.notes.append(msg)


# ---------------------------------------------------------------------------
# Canvas + region layout
# ---------------------------------------------------------------------------

# Middle stretchable region width/height. KWin tiles/stretches this, so the
# exact value mostly doesn't matter — match composite.MIDDLE_REF so the
# composited PNGs are 1:1 in output pixels (x scale).
_MIDDLE_REF = MIDDLE_REF


def _region_bbox(
    side: str,
    top: int,
    bot: int,
    lft: int,
    rgt: int,
    mw: int,
    mh: int,
    tlw: int | None = None,
    trw: int | None = None,
) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) for a 9-patch region within the SVG canvas.

    ``tlw``/``trw`` are the *frame* column widths (>= ``lft``/``rgt``): when
    corner art is folded into the title band the whole left/right column
    (corner, strip, bottom corner) is that wide. FrameSvg paints the frame
    at the hint-margin width regardless of KWin's clamped ``BorderLeft``, so
    the inner part of a wide column simply sits under the client window.
    """
    tlw = lft if tlw is None else max(lft, tlw)
    trw = rgt if trw is None else max(rgt, trw)
    regions = {
        "topleft": (0, 0, tlw, top),
        "top": (tlw, 0, mw, top),
        "topright": (tlw + mw, 0, trw, top),
        "left": (0, top, tlw, mh),
        "center": (tlw, top, mw, mh),
        "right": (tlw + mw, top, trw, mh),
        "bottomleft": (0, top + mh, tlw, bot),
        "bottom": (tlw, top + mh, mw, bot),
        "bottomright": (tlw + mw, top + mh, trw, bot),
    }
    return regions[side]


def _placeholder_bytes() -> bytes:
    with Image.new("RGBA", (1, 1), (0, 0, 0, 0)) as blank:
        buf = io.BytesIO()
        blank.save(buf, format="PNG")
        return buf.getvalue()


def write_decoration_svg(theme: Theme, out_dir: Path) -> Path:
    """Write ``decoration.svg`` with 36 FrameSvg IDs, hint rects, and base64 PNG.

    Strip thicknesses come from ``strip_thicknesses(theme)`` — the same function
    ``aurorae_rc.py`` reads. Each region's PNG comes from
    ``composite.compose_region``.

    Raises:
        AssertionError: If any required FrameSvg ID is missing post-write.
    """
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    out_dir.mkdir(parents=True, exist_ok=True)
    s = int(theme.scale)  # SVG backend is integer-scale by contract

    thick = strip_thicknesses(theme)
    top = thick["top"]
    bot = thick["bottom"]
    lft = thick["left"]
    rgt = thick["right"]
    cw = folded_corner_widths(theme, DEFAULT_MAX_BORDER, DEFAULT_MAX_SIDE_BORDER)
    tlw = max(lft, cw["left"] * s)
    trw = max(rgt, cw["right"] * s)
    mw, mh = _MIDDLE_REF * s, _MIDDLE_REF * s
    canvas_w = tlw + mw + trw
    canvas_h = top + mh + bot
    _fold_note(theme)

    placeholder = _placeholder_bytes()

    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {"width": str(canvas_w), "height": str(canvas_h), "version": "1.1"},
    )

    # Composite each (side, active) once; the maximized groups reuse them.
    cache: dict[tuple[str, bool], bytes] = {}

    def _png(side: str, prefer_active: bool) -> bytes:
        key = (side, prefer_active)
        if key not in cache:
            data = compose_region(
                theme,
                side,
                prefer_active=prefer_active,
                max_border_output=DEFAULT_MAX_BORDER,
                max_side_output=DEFAULT_MAX_SIDE_BORDER,
            )
            cache[key] = data or placeholder
        return cache[key]

    # Maximized windows: both Aurorae plugins paint ``decoration-maximized``
    # with ``FrameSvg::NoBorder`` — i.e. ONLY the ``center`` element,
    # stretched over the whole title band. So the title-band art (the
    # stretchable top strip) goes into ``*-maximized-center``; every other
    # maximized element is a 1x1 placeholder that is never painted.
    for prefix, prefer_active, maximized in (
        ("decoration", True, False),
        ("decoration-inactive", False, False),
        ("decoration-maximized", True, True),
        ("decoration-maximized-inactive", False, True),
    ):
        for side in SIDES:
            g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": f"{prefix}-{side}"})
            x, y, rw, rh = _region_bbox(side, top, bot, lft, rgt, mw, mh, tlw, trw)
            if maximized and side == "center":
                png = _png("top", prefer_active)
                rh = top
            elif maximized:
                png = placeholder
                rw = rh = 1
            else:
                png = _png(side, prefer_active)

            ET.SubElement(
                g,
                f"{{{SVG_NS}}}image",
                {
                    f"{{{XLINK_NS}}}href": embed_png_b64(png),
                    "x": str(x),
                    "y": str(y),
                    "width": str(max(1, rw)),
                    "height": str(max(1, rh)),
                    "preserveAspectRatio": "none",
                },
            )

    # FrameSvg hint rects. Top/bottom margin hints = the rc's BorderTop/
    # BorderBottom. Left/right hints = the frame COLUMN widths (folded corner
    # width when wider than the rc's BorderLeft/Right): FrameSvg sizes the
    # corners by these margins and paints the frame under the client, so a
    # wide hint is how corner art escapes the KWin side clamp. ``stretch-borders`` makes
    # KWin stretch (not tile) the side strips so the 256-ref slice carries a
    # continuous gradient with no repeating seam. Aurorae only honours the
    # ``decoration-`` prefixed forms.
    for hint_prefix in ("decoration-hint", "decoration-inactive-hint"):
        for suffix, orient, dim in (
            ("top-margin", "height", top),
            ("bottom-margin", "height", bot),
            ("left-margin", "width", tlw),
            ("right-margin", "width", trw),
            ("stretch-borders", "none", 1),
        ):
            attrs: dict[str, str] = {
                "id": f"{hint_prefix}-{suffix}",
                "x": "0",
                "y": "0",
                "style": "opacity:0",
            }
            if orient == "width":
                attrs["width"] = str(max(1, dim))
                attrs["height"] = "1"
            elif orient == "height":
                attrs["width"] = "1"
                attrs["height"] = str(max(1, dim))
            else:
                attrs["width"] = "1"
                attrs["height"] = "1"
            ET.SubElement(svg, f"{{{SVG_NS}}}rect", attrs)

    out_path = out_dir / "decoration.svg"
    ET.ElementTree(svg).write(out_path, xml_declaration=True, encoding="utf-8")

    # Post-write validation: all 36 IDs must be present.
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS

    root = ET.parse(out_path).getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    if missing:
        raise AssertionError(f"FrameSvg IDs missing in decoration.svg: {missing}")

    return out_path
