"""decoration.svg writer with 18 FrameSvg IDs + hint margins + base64-embedded raster.

Pitfall 5: 18 IDs verbatim — Aurorae matches by literal ``decoration-`` prefix.
The 9 active IDs are:
  ``decoration-topleft``, ``decoration-top``, ``decoration-topright``,
  ``decoration-left``, ``decoration-center``, ``decoration-right``,
  ``decoration-bottomleft``, ``decoration-bottom``, ``decoration-bottomright``
Plus the same 9 with ``decoration-inactive-`` prefix = 18 total.

Pitfall 6: every ``<image>`` uses ``data:image/png;base64,...`` href and
``preserveAspectRatio="none"``. Relative paths fail after install relocation.

Maximized variants are NOT emitted (Edna ships without them and works;
01-RESEARCH.md Pitfall 5 closing note + assumption A8).

SVG namespace registration:
  ``ET.register_namespace("", SVG_NS)`` is called so ``xml.etree.ElementTree``
  serialises elements without the ``ns0:`` prefix mangling.

Per-region iclass mapping (fix for visual smoke test — e13 regression):
  Each of the 9 Aurorae decoration regions is mapped to the most appropriate
  E16 iclass by name-pattern matching. A single titlebar image stretched across
  all 9 regions causes grossly wrong visual output (the "cream gradient blob"
  bug observed with e13.etheme).
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from themey.images.embed import embed_png_b64
from themey.images.upscale import upscale_nearest
from themey.ir import IClassSpec, Theme

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


def _png_bytes(p: Path | None, scale: int) -> bytes | None:
    """Open a PNG at path, convert to RGBA, upscale NEAREST by scale, return bytes.

    Returns None if the path is absent or the file doesn't exist.
    """
    if p is None or not p.is_file():
        return None
    with Image.open(p) as src:
        rgba = src.convert("RGBA")
        scaled = upscale_nearest(rgba, scale)
        buf = io.BytesIO()
        scaled.save(buf, format="PNG")
        return buf.getvalue()


def _iclass_bytes(ic: IClassSpec | None, scale: int, prefer_active: bool = True) -> bytes | None:
    """Get PNG bytes for an iclass, preferring active or normal state."""
    if ic is None:
        return None
    if prefer_active:
        b = _png_bytes(ic.normal_active, scale)
        if b is None:
            b = _png_bytes(ic.normal, scale)
    else:
        b = _png_bytes(ic.normal, scale)
        if b is None:
            b = _png_bytes(ic.normal_active, scale)
    return b


def _iclass_bytes_inactive(ic: IClassSpec | None, scale: int) -> bytes | None:
    """Get PNG bytes for the inactive (normal) state of an iclass."""
    if ic is None:
        return None
    b = _png_bytes(ic.normal, scale)
    if b is None:
        b = _png_bytes(ic.normal_active, scale)
    return b


# ---------------------------------------------------------------------------
# Per-region iclass selection
# ---------------------------------------------------------------------------

_REGION_PATTERNS: dict[str, list[str]] = {
    # Ordered from most-specific to least-specific. First matching iclass wins.
    "topleft": ["CORNER_TL", "CORNER_TOP_LEFT", "TOPLEFT", "TOP_LEFT"],
    "top": ["TITLE_BAR_HORIZONTAL", "TITLEBAR", "TITLE_BAR", "FIN", "TOP_BAR",
            "BAR_TOP", "WIN_TOP_TITLE", "WIN_TOP"],
    "topright": ["CORNER_TR", "CORNER_TOP_RIGHT", "TOPRIGHT", "TOP_RIGHT"],
    "left": ["WIN_SIDE_LEFT", "SIDE_LEFT", "BUTTONL", "WIN_LEFT", "BAR_LEFT"],
    "center": [],  # transparent fallback — center is window content, not decoration
    "right": ["WIN_SIDE_RIGHT", "SIDE_RIGHT", "BUTTONR", "WIN_RIGHT", "BAR_RIGHT"],
    "bottomleft": ["WIN_CORNER_BL", "CORNER_BL", "CORNER_BOTTOM_LEFT", "BOTTOMLEFT"],
    "bottom": ["WIN_BOTTOM", "BUTTONB", "BAR_BOTTOM", "BOTTOM"],
    "bottomright": ["WIN_CORNER_BR", "CORNER_BR", "CORNER_BOTTOM_RIGHT", "BOTTOMRIGHT"],
}


def _select_region_iclass(
    side: str,
    iclasses: dict[str, IClassSpec],
) -> IClassSpec | None:
    """Select the best iclass for a given Aurorae 9-patch region.

    Tries exact name matches from ``_REGION_PATTERNS[side]`` first, then
    falls back to substring matching (upper-case comparison).

    For the ``center`` region, always returns None (transparent).
    """
    if side == "center":
        return None

    upper_names = {name.upper(): name for name in iclasses}
    patterns = _REGION_PATTERNS.get(side, [])

    # Exact match first
    for pat in patterns:
        if pat in upper_names:
            return iclasses[upper_names[pat]]

    # Substring match — look for any iclass whose upper name contains the pattern
    for pat in patterns:
        for up, orig in upper_names.items():
            if pat in up:
                return iclasses[orig]

    return None


def _select_titlebar_iclass(theme: Theme) -> IClassSpec | None:
    """Prefer TITLE_BAR_HORIZONTAL; fall back to first iclass with any image."""
    # Try per-region patterns for "top" first
    ic = _select_region_iclass("top", theme.iclasses)
    if ic is not None:
        return ic
    for ic_val in theme.iclasses.values():
        if ic_val.normal is not None or ic_val.normal_active is not None:
            return ic_val
    return None


def _compute_region_bbox(
    side: str,
    w: int,
    h: int,
    edge_l: int,
    edge_r: int,
    edge_t: int,
    edge_b: int,
) -> tuple[int, int, int, int]:
    """Return (x, y, width, height) for a 9-patch region inside the canvas."""
    cw = max(0, w - edge_l - edge_r)
    ch = max(0, h - edge_t - edge_b)
    regions: dict[str, tuple[int, int, int, int]] = {
        "topleft": (0, 0, edge_l, edge_t),
        "top": (edge_l, 0, cw, edge_t),
        "topright": (edge_l + cw, 0, edge_r, edge_t),
        "left": (0, edge_t, edge_l, ch),
        "center": (edge_l, edge_t, cw, ch),
        "right": (edge_l + cw, edge_t, edge_r, ch),
        "bottomleft": (0, edge_t + ch, edge_l, edge_b),
        "bottom": (edge_l, edge_t + ch, cw, edge_b),
        "bottomright": (edge_l + cw, edge_t + ch, edge_r, edge_b),
    }
    return regions[side]


def _placeholder_bytes() -> bytes:
    """Return bytes for a 1x1 transparent PNG placeholder."""
    with Image.new("RGBA", (1, 1), (0, 0, 0, 0)) as blank:
        buf = io.BytesIO()
        blank.save(buf, format="PNG")
        return buf.getvalue()


def write_decoration_svg(theme: Theme, out_dir: Path) -> Path:
    """Write ``decoration.svg`` with 18 FrameSvg IDs, hint margins, and base64 PNG.

    The SVG contains:
    - 9 ``<g id="decoration-{side}">`` elements (active state)
    - 9 ``<g id="decoration-inactive-{side}">`` elements (inactive state)
    - 4 ``<rect id="hint-{top,bottom,left,right}-margin">`` hint rects

    Each of the 9 regions uses the most appropriate E16 iclass image
    (matched by name pattern) rather than a single titlebar image stretched
    across all regions. This prevents the "cream gradient blob" rendering bug
    observed when a decorative bar image is used for left/right/bottom regions.

    Hint-margin rects use the correct orientation convention:
    - hint-left-margin:  ``width`` = left border thickness
    - hint-right-margin: ``width`` = right border thickness
    - hint-top-margin:   ``height`` = top border thickness
    - hint-bottom-margin: ``height`` = bottom border thickness

    Every ``<image>`` uses ``xlink:href="data:image/png;base64,..."`` and
    ``preserveAspectRatio="none"`` to satisfy FrameSvg's rendering contract.

    Raises:
        AssertionError: If any of the 18 required FrameSvg IDs are absent
            in the written file (validated by post-write parse).

    Args:
        theme: Frozen Theme IR. Uses iclass name-pattern matching for each region.
        out_dir: Directory to write ``decoration.svg`` into.

    Returns:
        Path to the written ``decoration.svg``.
    """
    # Register namespaces BEFORE creating any elements so ET doesn't emit ns0:.
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    out_dir.mkdir(parents=True, exist_ok=True)
    scale = theme.scale

    # Select a titlebar iclass for canvas dimensions and edge scaling reference.
    titlebar_ic = _select_titlebar_iclass(theme)

    # Canvas edge metrics — from titlebar iclass edge_scaling * scale.
    if titlebar_ic is not None:
        el, er, et, eb = titlebar_ic.edge_scaling
    else:
        el, er, et, eb = (4, 4, 18, 4)
    el *= scale
    er *= scale
    et *= scale
    eb *= scale

    body_w = max(64, el + er + 32)
    body_h = max(64, et + eb + 32)

    placeholder = _placeholder_bytes()

    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": str(body_w),
            "height": str(body_h),
            "version": "1.1",
        },
    )

    # Emit 9 active + 9 inactive <g> elements, each containing an <image>.
    # Each region gets its own iclass image.
    for prefix, prefer_active in (
        ("decoration", True),
        ("decoration-inactive", False),
    ):
        for side in SIDES:
            g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": f"{prefix}-{side}"})
            x, y, rw, rh = _compute_region_bbox(side, body_w, body_h, el, er, et, eb)

            # Select appropriate iclass for this region
            region_ic = _select_region_iclass(side, theme.iclasses)
            if prefer_active:
                png_bytes = _iclass_bytes(region_ic, scale, prefer_active=True)
            else:
                png_bytes = _iclass_bytes_inactive(region_ic, scale)

            # Fallback to titlebar iclass if no specific iclass found for this region
            if png_bytes is None and region_ic is None and titlebar_ic is not None:
                if side == "top":
                    if prefer_active:
                        png_bytes = _iclass_bytes(titlebar_ic, scale, prefer_active=True)
                    else:
                        png_bytes = _iclass_bytes_inactive(titlebar_ic, scale)

            # Final fallback: transparent placeholder
            if png_bytes is None:
                png_bytes = placeholder

            href = embed_png_b64(png_bytes)
            ET.SubElement(
                g,
                f"{{{SVG_NS}}}image",
                {
                    f"{{{XLINK_NS}}}href": href,
                    "x": str(x),
                    "y": str(y),
                    "width": str(max(1, rw)),
                    "height": str(max(1, rh)),
                    "preserveAspectRatio": "none",
                },
            )

    # FrameSvg hint-margin rects — invisible rects telling FrameSvg the border
    # thickness in each direction. Orientation convention (verified from Edna SVG):
    #   hint-left-margin:  width  = left margin thickness
    #   hint-right-margin: width  = right margin thickness
    #   hint-top-margin:   height = top margin thickness
    #   hint-bottom-margin: height = bottom margin thickness
    for hint_id, orient, dim in (
        ("hint-top-margin", "height", et),
        ("hint-bottom-margin", "height", eb),
        ("hint-left-margin", "width", el),
        ("hint-right-margin", "width", er),
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

    # Post-write validation: assert all 18 required IDs are present.
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS  # avoid circular at module load

    root = ET.parse(out_path).getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    if missing:
        raise AssertionError(f"FrameSvg IDs missing in decoration.svg: {missing}")

    return out_path
