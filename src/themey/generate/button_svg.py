"""Per-button SVG writer.

Aurorae loads ``close.svg``, ``maximize.svg``, ``restore.svg``, ``minimize.svg``,
``shade.svg``, ``alldesktops.svg``, ``keepabove.svg``, ``keepbelow.svg`` from
the theme directory based on the button codes in ``<name>rc``'s
``LeftButtons``/``RightButtons``.

Each SVG contains three ``<g>`` elements with IDs:
- ``<base_id>``          — default/idle state
- ``<base_id>-hover``    — hovered state (Aurorae button feedback)
- ``<base_id>-pressed``  — pressed state (Aurorae button feedback)

Every ``<image>`` uses ``xlink:href="data:image/png;base64,..."`` and
``preserveAspectRatio="none"`` (same Pitfall 6 rules as decoration.svg).
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

# Aurorae button code → SVG filename(s). Code "A" writes BOTH maximize + restore.
BUTTON_CODE_TO_FILES: dict[str, tuple[str, ...]] = {
    "X": ("close.svg",),
    "A": ("maximize.svg", "restore.svg"),
    "I": ("minimize.svg",),
    "S": ("alldesktops.svg",),
    "L": ("shade.svg",),
    "F": ("keepabove.svg",),
    "B": ("keepbelow.svg",),
}

# Map Aurorae button code → preferred E16 iclass name patterns (case-insensitive
# substring search against iclass_name).
_CODE_TO_ICLASS_PATTERNS: dict[str, tuple[str, ...]] = {
    "X": ("BUTTON_CLOSE", "BUTTON_KILL"),
    "A": ("BUTTON_MAXIMIZE", "BUTTON_MAX"),
    "I": ("BUTTON_ICONIFY", "BUTTON_MINIMIZE"),
    "S": ("BUTTON_STICK",),
    "L": ("BUTTON_SHADE",),
    "F": ("BUTTON_KEEP_ABOVE",),
    "B": ("BUTTON_KEEP_BELOW",),
}


def _png_bytes_from_path(p: Path | None, scale: int) -> bytes | None:
    """Load a PNG at ``p``, convert to RGBA, upscale NEAREST, return bytes."""
    if p is None or not p.is_file():
        return None
    with Image.open(p) as src:
        rgba = src.convert("RGBA")
        scaled = upscale_nearest(rgba, scale)
        buf = io.BytesIO()
        scaled.save(buf, format="PNG")
        return buf.getvalue()


def _find_iclass_for_code(theme: Theme, code: str) -> IClassSpec | None:
    """Return the first IClassSpec whose name matches a pattern for ``code``."""
    for pattern in _CODE_TO_ICLASS_PATTERNS.get(code, ()):
        for ic_name, ic in theme.iclasses.items():
            if pattern in ic_name.upper():
                return ic
    return None


def _build_button_svg(theme: Theme, code: str, base_id: str) -> ET.Element:
    """Build an SVG element tree for one button.

    Three states: default (``base_id``), hover (``base_id-hover``), pressed
    (``base_id-pressed``). Falls back up the state chain if a specific state
    image is absent.
    """
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    ic = _find_iclass_for_code(theme, code)
    scale = theme.scale

    normal = _png_bytes_from_path(
        ic.normal_active if ic else None, scale
    ) or _png_bytes_from_path(ic.normal if ic else None, scale)

    hover = _png_bytes_from_path(
        ic.hilited_active if ic else None, scale
    ) or _png_bytes_from_path(ic.hilited if ic else None, scale) or normal

    pressed = _png_bytes_from_path(
        ic.clicked_active if ic else None, scale
    ) or _png_bytes_from_path(ic.clicked if ic else None, scale) or normal

    # Fallback: 16x16 transparent placeholder
    if normal is None:
        with Image.new("RGBA", (16, 16), (0, 0, 0, 0)) as blank:
            buf = io.BytesIO()
            blank.save(buf, format="PNG")
            normal = buf.getvalue()
        hover = normal
        pressed = normal

    size = 24 * scale
    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": str(size),
            "height": str(size),
            "version": "1.1",
        },
    )

    # Emit three <g> elements: default, hover, pressed.
    for sub_id, png_data in (
        (base_id, normal),
        (f"{base_id}-hover", hover),
        (f"{base_id}-pressed", pressed),
    ):
        g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": sub_id})
        ET.SubElement(
            g,
            f"{{{SVG_NS}}}image",
            {
                f"{{{XLINK_NS}}}href": embed_png_b64(png_data),
                "x": "0",
                "y": "0",
                "width": str(size),
                "height": str(size),
                "preserveAspectRatio": "none",
            },
        )
    return svg


def write_button_svgs(theme: Theme, out_dir: Path) -> list[Path]:
    """Write per-button SVGs for all codes in ``theme.left_buttons`` and
    ``theme.right_buttons`` (plus any codes in ``theme.button_codes.values()``).

    Args:
        theme: Frozen Theme IR.
        out_dir: Directory to write SVG files into. Created if absent.

    Returns:
        List of paths to written SVG files.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Collect all active codes from left/right button strings + button_codes map.
    codes: set[str] = set(theme.left_buttons) | set(theme.right_buttons)
    codes |= set(theme.button_codes.values())

    written: list[Path] = []
    for code in sorted(codes):  # sorted for deterministic output order
        for fname in BUTTON_CODE_TO_FILES.get(code, ()):
            base_id = fname.removesuffix(".svg")  # e.g. "close", "maximize"
            svg = _build_button_svg(theme, code, base_id)
            out_path = out_dir / fname
            ET.ElementTree(svg).write(out_path, xml_declaration=True, encoding="utf-8")
            written.append(out_path)
    return written
