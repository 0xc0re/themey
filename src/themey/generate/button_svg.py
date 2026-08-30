"""Per-button SVG writer.

Aurorae loads ``close.svg``, ``maximize.svg``, ``restore.svg``, ``minimize.svg``,
``shade.svg``, ``alldesktops.svg``, ``keepabove.svg``, ``keepbelow.svg`` and
``menu.svg`` from the theme directory. Which buttons SHOW, and in what
order, is global — kwinrc ``[org.kde.kdecoration2] ButtonsOnLeft`` /
``ButtonsOnRight`` — not per theme. The theme only decides which SVGs
exist; a button present in kwinrc but missing here renders as nothing.
``menu.svg`` (code ``M``) is therefore always written: E16 has no menu
button iclass, so it gets a small placeholder glyph.

Each SVG contains three ``<g>`` elements whose IDs are FrameSvg 9-patch
prefixes, so KSvg / Aurorae's ``hasElementPrefix("active"|"hover"|"pressed")``
checks succeed:

- ``active-center``  — default/idle state
- ``hover-center``   — hovered state
- ``pressed-center`` — pressed state

(``AuroraeButton.qml`` instantiates one ``KSvg.FrameSvg`` per state with
``imagePath`` set to this SVG; if it can't find the prefix the per-state
group falls back to ``imagePath: ""`` and the button is hidden.)

Every ``<image>`` uses ``xlink:href="data:image/png;base64,..."`` and
``preserveAspectRatio="none"`` (same Pitfall 6 rules as decoration.svg).
"""
from __future__ import annotations

import io
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

from themey.analyze.buttons import ACLASS_TO_BUTTON
from themey.generate.composite import button_dims
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
    "M": ("menu.svg",),
}

# Fallback only — used when an E16 theme omits __ACLASS on its button parts.
# Canonical button identification routes through ``__ACLASS`` via
# ``ACLASS_TO_BUTTON``; this map is consulted only when that fails.
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
    """Return the IClassSpec the theme uses to render Aurorae button ``code``.

    Canonical (tier-1): walk ``theme.border.parts`` and pick the part whose
    ``__ACLASS`` maps to ``code`` via ``ACLASS_TO_BUTTON``. The part's
    ``iclass_name`` is the asset reference Aurorae should use.

    Fallback (tier-2): scan ``theme.iclasses`` for a name matching a known
    button pattern. Only fires for themes that omit ``__ACLASS`` on their
    button parts.
    """
    # Tier 1 — canonical: __ACLASS on a __BORDER_PART pinpoints the asset.
    for part in theme.border.parts:
        if part.aclass and ACLASS_TO_BUTTON.get(part.aclass) == code:
            ic = theme.iclasses.get(part.iclass_name)
            if ic is not None:
                return ic

    # Tier 2 — fallback: iclass-name pattern.
    for pattern in _CODE_TO_ICLASS_PATTERNS.get(code, ()):
        for ic_name, ic in theme.iclasses.items():
            if pattern in ic_name.upper():
                return ic
    return None


def _placeholder_glyph(theme: Theme, code: str) -> bytes:
    """PNG for a button with no source art.

    ``M`` (menu) gets a small filled square in the theme's active title
    text colour (three-quarter size, centred) so a kwinrc ``ButtonsOnLeft=M``
    shows a visible, clickable target. Every other code is transparent.
    """
    w, h = button_dims(theme)
    w, h = max(1, w), max(1, h)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if code == "M":
        r, g, b = theme.palette.text_active
        inset_x = max(1, w // 4)
        inset_y = max(1, h // 4)
        for y in range(inset_y, h - inset_y):
            for x in range(inset_x, w - inset_x):
                img.putpixel((x, y), (r, g, b, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_button_svg(theme: Theme, code: str) -> ET.Element:
    """Build an SVG element tree for one button.

    Three FrameSvg-prefixed states: ``active-center`` (idle), ``hover-center``
    (hovered), ``pressed-center`` (pressed). Falls back up the state chain
    when a specific state image is absent.
    """
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", XLINK_NS)

    ic = _find_iclass_for_code(theme, code)
    scale = theme.scale

    normal_raw = _png_bytes_from_path(
        ic.normal_active if ic else None, scale
    ) or _png_bytes_from_path(ic.normal if ic else None, scale)

    hover_raw = _png_bytes_from_path(
        ic.hilited_active if ic else None, scale
    ) or _png_bytes_from_path(ic.hilited if ic else None, scale) or normal_raw

    pressed_raw = _png_bytes_from_path(
        ic.clicked_active if ic else None, scale
    ) or _png_bytes_from_path(ic.clicked if ic else None, scale) or normal_raw

    # Resolve to guaranteed non-None bytes. Fallback: a placeholder glyph
    # for the menu button (no E16 equivalent), transparent otherwise.
    if normal_raw is None:
        normal_raw = _placeholder_glyph(theme, code)
    normal: bytes = normal_raw
    hover: bytes = hover_raw if hover_raw is not None else normal
    pressed: bytes = pressed_raw if pressed_raw is not None else normal

    btn_w, btn_h = button_dims(theme)
    svg = ET.Element(
        f"{{{SVG_NS}}}svg",
        {
            "width": str(btn_w),
            "height": str(btn_h),
            "version": "1.1",
        },
    )

    # Emit three FrameSvg 9-patch groups: active-center, hover-center, pressed-center.
    for prefix, png_data in (
        ("active", normal),
        ("hover", hover),
        ("pressed", pressed),
    ):
        g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": f"{prefix}-center"})
        ET.SubElement(
            g,
            f"{{{SVG_NS}}}image",
            {
                f"{{{XLINK_NS}}}href": embed_png_b64(png_data),
                "x": "0",
                "y": "0",
                "width": str(btn_w),
                "height": str(btn_h),
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
    # "M" is always included: kwinrc's default ButtonsOnLeft is "M".
    codes: set[str] = set(theme.left_buttons) | set(theme.right_buttons)
    codes |= set(theme.button_codes.values())
    codes.add("M")

    written: list[Path] = []
    for code in sorted(codes):  # sorted for deterministic output order
        for fname in BUTTON_CODE_TO_FILES.get(code, ()):
            svg = _build_button_svg(theme, code)
            out_path = out_dir / fname
            ET.ElementTree(svg).write(out_path, xml_declaration=True, encoding="utf-8")
            written.append(out_path)
    return written
