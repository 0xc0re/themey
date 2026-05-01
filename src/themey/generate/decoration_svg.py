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


def _select_titlebar_iclass(theme: Theme) -> IClassSpec | None:
    """Prefer TITLE_BAR_HORIZONTAL; fall back to first iclass with any image."""
    if "TITLE_BAR_HORIZONTAL" in theme.iclasses:
        return theme.iclasses["TITLE_BAR_HORIZONTAL"]
    for ic in theme.iclasses.values():
        if ic.normal is not None or ic.normal_active is not None:
            return ic
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


def write_decoration_svg(theme: Theme, out_dir: Path) -> Path:
    """Write ``decoration.svg`` with 18 FrameSvg IDs, hint margins, and base64 PNG.

    The SVG contains:
    - 9 ``<g id="decoration-{side}">`` elements (active state)
    - 9 ``<g id="decoration-inactive-{side}">`` elements (inactive state)
    - 4 ``<rect id="hint-{top,bottom,left,right}-margin">`` hint rects

    Every ``<image>`` uses ``xlink:href="data:image/png;base64,..."`` and
    ``preserveAspectRatio="none"`` to satisfy FrameSvg's rendering contract.

    Raises:
        AssertionError: If any of the 18 required FrameSvg IDs are absent
            in the written file (validated by post-write parse).

    Args:
        theme: Frozen Theme IR. Uses ``theme.iclasses["TITLE_BAR_HORIZONTAL"]``
            (falls back to first iclass) for border imagery.
        out_dir: Directory to write ``decoration.svg`` into.

    Returns:
        Path to the written ``decoration.svg``.
    """
    # Register namespaces BEFORE creating any elements so ET doesn't emit ns0:.
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    out_dir.mkdir(parents=True, exist_ok=True)
    ic = _select_titlebar_iclass(theme)
    scale = theme.scale

    # Resolve PNG bytes for active and inactive states.
    active_bytes = _png_bytes(ic.normal_active if ic else None, scale)
    if active_bytes is None and ic is not None:
        active_bytes = _png_bytes(ic.normal, scale)

    inactive_bytes = _png_bytes(ic.normal if ic else None, scale)
    if inactive_bytes is None:
        inactive_bytes = active_bytes

    # Degraded mode: generate a 1x1 transparent placeholder so the SVG still
    # carries all 18 IDs (analysis stage already logged this via Theme.notes).
    if active_bytes is None:
        with Image.new("RGBA", (1, 1), (0, 0, 0, 0)) as blank:
            buf = io.BytesIO()
            blank.save(buf, format="PNG")
            active_bytes = buf.getvalue()
    if inactive_bytes is None:
        inactive_bytes = active_bytes

    # Canvas dimensions derived from edge_scaling * scale.
    if ic is not None:
        el, er, et, eb = ic.edge_scaling
    else:
        el, er, et, eb = (4, 4, 18, 4)
    el *= scale
    er *= scale
    et *= scale
    eb *= scale

    body_w = max(64, el + er + 32)
    body_h = max(64, et + eb + 32)

    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": str(body_w),
            "height": str(body_h),
            "version": "1.1",
        },
    )

    # Emit 9 active + 9 inactive <g> elements, each containing an <image>.
    for prefix, png_bytes in (
        ("decoration", active_bytes),
        ("decoration-inactive", inactive_bytes),
    ):
        href = embed_png_b64(png_bytes)
        for side in SIDES:
            g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": f"{prefix}-{side}"})
            x, y, rw, rh = _compute_region_bbox(side, body_w, body_h, el, er, et, eb)
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

    # FrameSvg hint-margin rects — invisible rects sized in pixels telling FrameSvg
    # the border thickness in each direction (verified present in Edna decoration.svg).
    for hint_id, dim in (
        ("hint-top-margin", et),
        ("hint-bottom-margin", eb),
        ("hint-left-margin", el),
        ("hint-right-margin", er),
    ):
        ET.SubElement(
            svg,
            f"{{{SVG_NS}}}rect",
            {
                "id": hint_id,
                "x": "0",
                "y": "0",
                "width": str(max(1, dim)),
                "height": str(max(1, dim)),
                "style": "opacity:0",
            },
        )

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
