"""decoration.svg writer with 18 FrameSvg IDs + hint margins + base64-embedded raster.

The 18 required FrameSvg IDs are emitted verbatim:
  ``decoration-{topleft,top,topright,left,center,right,bottomleft,bottom,bottomright}``
plus the same 9 with the ``decoration-inactive-`` prefix.

Each region's PNG is *composited* from the E16 ``__BORDER_PART`` entries that
overlap the region's bbox. See ``composite.py`` for the layout math and
overlap-clipping rules. Interactive button iclasses (close/min/max/etc.) are
omitted — Aurorae renders those on top via the rc's ``LeftButtons``/
``RightButtons`` strings.

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
"""Default cap (in output pixels) per border side.

Grown borders that would render the full corner art (Aliens'
CORNER_TL is 179x124 source = 358x248 at scale=2) can exceed what KWin
displays gracefully — the chrome ends up looking like a separate banner
rather than a frame around the content. 120 output px keeps the chrome
visually framing the content while still showing a clipped but
recognizable portion of the corner art (~half the alien head).

Override with the CLI ``--max-border N`` flag for users who want
bigger chrome at the cost of usable content area.
"""


def strip_thicknesses(theme: Theme, max_border: int = DEFAULT_MAX_BORDER) -> dict[str, int]:
    """Compute the four strip thicknesses (in output pixels) for *theme*.

    Single source of truth — the rc writer imports this. Returns a dict
    with keys ``top``, ``bottom``, ``left``, ``right``.

    Rule (user-confirmed "match the E16 look" semantics):

    For each side, take the max of:
      1. ``__BORDER_SIZE_<side>`` (the E16 chrome zone), and
      2. the extent of any non-interactive ``__BORDER_PART`` anchored to
         that edge — so corner art renders uncompressed.

    Each result is clamped to ``[2, max_border]`` after scaling. The upper
    bound prevents Aurorae from getting a chrome zone so large it looks
    disconnected from the window content; corner art that wouldn't fit
    is clipped on the inside edge by the compositor.
    """
    s = theme.scale
    ext = required_border_extents(theme)
    return {
        "top": max(2, min(max_border, ext["top"] * s)),
        "bottom": max(2, min(max_border, ext["bottom"] * s)),
        "left": max(2, min(max_border, ext["left"] * s)),
        "right": max(2, min(max_border, ext["right"] * s)),
    }


# ---------------------------------------------------------------------------
# Canvas + region layout
# ---------------------------------------------------------------------------

# Middle stretchable region width/height. KWin tiles/stretches this, so the
# exact value mostly doesn't matter — match composite.MIDDLE_REF so the
# composited PNGs are 1:1 in output pixels (x scale).
_MIDDLE_REF = MIDDLE_REF


def _region_bbox(
    side: str, top: int, bot: int, lft: int, rgt: int, mw: int, mh: int
) -> tuple[int, int, int, int]:
    """Return (x, y, w, h) for a 9-patch region within the SVG canvas."""
    regions = {
        "topleft": (0, 0, lft, top),
        "top": (lft, 0, mw, top),
        "topright": (lft + mw, 0, rgt, top),
        "left": (0, top, lft, mh),
        "center": (lft, top, mw, mh),
        "right": (lft + mw, top, rgt, mh),
        "bottomleft": (0, top + mh, lft, bot),
        "bottom": (lft, top + mh, mw, bot),
        "bottomright": (lft + mw, top + mh, rgt, bot),
    }
    return regions[side]


def _placeholder_bytes() -> bytes:
    with Image.new("RGBA", (1, 1), (0, 0, 0, 0)) as blank:
        buf = io.BytesIO()
        blank.save(buf, format="PNG")
        return buf.getvalue()


def write_decoration_svg(theme: Theme, out_dir: Path) -> Path:
    """Write ``decoration.svg`` with 18 FrameSvg IDs, hint margins, and base64 PNG.

    Strip thicknesses come from ``strip_thicknesses(theme)`` — the same function
    ``aurorae_rc.py`` reads. Each region's PNG comes from
    ``composite.compose_region``.

    Raises:
        AssertionError: If any required FrameSvg ID is missing post-write.
    """
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    out_dir.mkdir(parents=True, exist_ok=True)
    s = theme.scale

    thick = strip_thicknesses(theme)
    top = thick["top"]
    bot = thick["bottom"]
    lft = thick["left"]
    rgt = thick["right"]
    mw, mh = _MIDDLE_REF * s, _MIDDLE_REF * s
    canvas_w = lft + mw + rgt
    canvas_h = top + mh + bot

    placeholder = _placeholder_bytes()

    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {"width": str(canvas_w), "height": str(canvas_h), "version": "1.1"},
    )

    for prefix, prefer_active in (
        ("decoration", True),
        ("decoration-inactive", False),
    ):
        for side in SIDES:
            g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": f"{prefix}-{side}"})
            x, y, rw, rh = _region_bbox(side, top, bot, lft, rgt, mw, mh)

            png = compose_region(
                theme, side,
                prefer_active=prefer_active,
                max_border_output=DEFAULT_MAX_BORDER,
            )
            if not png:
                png = placeholder

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

    # FrameSvg hint-margin rects. Width or height = the corresponding strip
    # thickness — same value the rc declares. This makes the SVG bounding-box-
    # detected margins consistent with the rc.
    for hint_id, orient, dim in (
        ("hint-top-margin", "height", top),
        ("hint-bottom-margin", "height", bot),
        ("hint-left-margin", "width", lft),
        ("hint-right-margin", "width", rgt),
    ):
        attrs: dict[str, str] = {
            "id": hint_id,
            "x": "0",
            "y": "0",
            "style": "opacity:0",
        }
        if orient == "width":
            attrs["width"] = str(max(1, dim))
            attrs["height"] = "1"
        else:
            attrs["width"] = "1"
            attrs["height"] = str(max(1, dim))
        ET.SubElement(svg, f"{{{SVG_NS}}}rect", attrs)

    out_path = out_dir / "decoration.svg"
    ET.ElementTree(svg).write(out_path, xml_declaration=True, encoding="utf-8")

    # Post-write validation: all 18 IDs must be present.
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS

    root = ET.parse(out_path).getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    if missing:
        raise AssertionError(f"FrameSvg IDs missing in decoration.svg: {missing}")

    return out_path
