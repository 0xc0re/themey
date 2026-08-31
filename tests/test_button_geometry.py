"""Per-code button geometry: aspect-true, title-fitted, rc↔SVG agreement.

``composite.button_geometry`` is the single source of truth for button
sizing. e13 stacks four differently-sized buttons down its left border zone
(KILL 40x38, ICONIFY 31x43, SHADE 31x21, STICK 31x38); they migrate to the
Aurorae title row with per-code widths, uniformly scaled DOWN to fit under
the opaque-trimmed title band — never up, never distorted. The old shared
80x76 slot stretched shade art 1.81x tall.
"""
from __future__ import annotations

import base64
import io
import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from contextlib import contextmanager
from pathlib import Path

import pytest
from PIL import Image

FIXTURES = Path(__file__).parent / "fixtures"
SVG_NS = "{http://www.w3.org/2000/svg}"

pytestmark = pytest.mark.skipif(
    not (FIXTURES / "e13.etheme").exists(),
    reason="e13.etheme not available on this machine",
)


@contextmanager
def _theme_ctx(name: str):
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    with extract(FIXTURES / f"{name}.etheme") as raw:
        yield build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name=name, display_name=name, scale=2,
        )


def test_e13_per_code_geometry_aspect_true() -> None:
    """Each e13 button keeps its own aspect; tall art scales down to fit."""
    from themey.generate.composite import button_geometry

    with _theme_ctx("e13") as theme:
        geo = button_geometry(theme)
        assert geo["X"] == (63, 60), geo  # KILL 80x76 → x60/76
        assert geo["I"] == (43, 60), geo  # ICONIFY 62x86 → x60/86
        assert geo["L"] == (62, 42), geo  # SHADE fits: untouched
        assert geo["S"] == (48, 60), geo  # STICK 62x76 → x60/76
        # No 80/76 anywhere — the shared-slot distortion is gone.
        for code, (w, h) in geo.items():
            assert (w, h) != (80, 76), (code, w, h)


def test_e13_button_height_fits_title_band() -> None:
    """Shared ButtonHeight <= the opaque-trimmed TitleHeight."""
    from themey.generate.composite import button_dims, title_opaque_rows_ref

    with _theme_ctx("e13") as theme:
        _, btn_h = button_dims(theme)
        title_out = title_opaque_rows_ref(theme) * theme.scale
        assert btn_h <= title_out, (btn_h, title_out)


def _rc_layout(rc_path: Path) -> dict[str, str]:
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc_path)
    return dict(cp["Layout"])


_FILE_TO_CODE = {
    "close.svg": "X",
    "minimize.svg": "I",
    "maximize.svg": "A",
    "restore.svg": "A",
    "alldesktops.svg": "S",
    "shade.svg": "L",
    "keepabove.svg": "F",
    "keepbelow.svg": "B",
    "menu.svg": "M",
}

_CODE_TO_SUFFIX = {
    "X": "Close",
    "I": "Minimize",
    "A": "MaximizeRestore",
    "S": "Alldesktops",
    "L": "Shade",
    "F": "Keepabove",
    "B": "Keepbelow",
    "M": "Menu",
}


def test_e13_rc_and_svg_button_widths_agree(fake_home: Path) -> None:
    """ButtonWidth<Suffix> in the rc == the SVG canvas width, per code."""
    from themey.pipeline import convert

    result = convert(FIXTURES / "e13.etheme", scale=2)
    layout = _rc_layout(result.installed_dir / "e13rc")
    for fname, code in _FILE_TO_CODE.items():
        svg_path = result.installed_dir / fname
        if not svg_path.exists():
            continue
        svg_w = int(ET.parse(svg_path).getroot().get("width", "0"))
        rc_w = int(layout[f"ButtonWidth{_CODE_TO_SUFFIX[code]}"])
        assert svg_w == rc_w, (fname, svg_w, rc_w)
        svg_h = int(ET.parse(svg_path).getroot().get("height", "0"))
        assert svg_h == int(layout["ButtonHeight"]), (fname, svg_h)


def test_e13_rc_per_code_widths_differ(fake_home: Path) -> None:
    """e13's per-code widths must not collapse to one shared value."""
    from themey.pipeline import convert

    result = convert(FIXTURES / "e13.etheme", scale=2)
    layout = _rc_layout(result.installed_dir / "e13rc")
    close_w = int(layout["ButtonWidthClose"])
    min_w = int(layout["ButtonWidthMinimize"])
    assert min_w < close_w, (min_w, close_w)
    assert int(layout["ButtonHeight"]) <= int(layout["TitleHeight"])


def _embedded_png(svg_path: Path) -> Image.Image:
    root = ET.parse(svg_path).getroot()
    for img in root.iter(f"{SVG_NS}image"):
        href = img.get("{http://www.w3.org/1999/xlink}href", "")
        if href.startswith("data:image/png;base64,"):
            data = base64.b64decode(href.split(",", 1)[1])
            return Image.open(io.BytesIO(data)).convert("RGBA")
    raise AssertionError(f"no embedded PNG in {svg_path}")


def test_menu_glyph_outline_with_transparent_interior(fake_home: Path) -> None:
    """menu.svg's fallback glyph is an outline, not a filled white block."""
    from themey.pipeline import convert

    result = convert(FIXTURES / "e13.etheme", scale=2)
    png = _embedded_png(result.installed_dir / "menu.svg")
    w, h = png.size
    centre = png.getpixel((w // 2, h // 2))
    assert centre[3] == 0, f"menu glyph interior not transparent: {centre}"
    # Some pixel on the outline ring is opaque.
    ring_y = h // 4 + 1
    opaque_on_ring = any(
        png.getpixel((x, ring_y))[3] == 255 for x in range(w)
    )
    assert opaque_on_ring, "menu glyph outline missing"
