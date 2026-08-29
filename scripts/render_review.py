"""Render a mock window from an installed theme (APPROXIMATION).

This is a hand-rolled approximation of Aurorae's QML layout, not FrameSvg.
It is fast and deterministic but can disagree with KWin (tiling vs
stretching, hint margins, v2 border clamping). ``themey render`` — the
headless nested-KWin harness in ``src/themey/render.py`` — is the truth;
use this only when kwin_wayland/spectacle are unavailable.

Used in the vision-iteration loop: produces a PNG that approximates what
KWin would render with the installed Aurorae theme, at a real-window size
(default 1000x700 — big enough to fit Aliens' 358-tall top border and still
show a usable content area).

Usage:
    uv run python scripts/render_review.py Aliens [W H]

Output:
    /tmp/themey_review/<theme>.png
"""
from __future__ import annotations

import base64
import io
import sys
import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_NS = "{http://www.w3.org/1999/xlink}"


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _load_region_pngs(svg_path: Path) -> dict[str, Image.Image]:
    """Extract the embedded PNGs from decoration.svg, keyed by region id."""
    tree = ET.parse(svg_path)
    out: dict[str, Image.Image] = {}
    for g in tree.getroot().iter(f"{SVG_NS}g"):
        gid = g.get("id", "")
        if not gid.startswith("decoration-") or "inactive" in gid:
            continue
        region = gid.removeprefix("decoration-")
        img_el = g.find(f"{SVG_NS}image")
        if img_el is None:
            continue
        href = img_el.get(f"{XLINK_NS}href") or img_el.get("href") or ""
        if not href.startswith("data:image/png;base64,"):
            continue
        data = base64.b64decode(href.split(",", 1)[1])
        out[region] = Image.open(io.BytesIO(data)).convert("RGBA")
    return out


def _resize(img: Image.Image, w: int, h: int) -> Image.Image:
    if img.size == (w, h):
        return img
    return img.resize((max(1, w), max(1, h)), Image.Resampling.NEAREST)


def _read_layout(rc: Path) -> dict[str, int]:
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc)
    return {k: int(v) for k, v in cp["Layout"].items() if v.lstrip("-").isdigit()}


def _read_general(rc: Path) -> dict[str, str]:
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(rc)
    return dict(cp["General"])


def _load_button_svg(theme_dir: Path, name: str) -> Image.Image | None:
    """Render a button SVG via rsvg-convert to a temp PNG, then load."""
    import shutil
    import subprocess
    import tempfile

    svg = theme_dir / f"{name}.svg"
    if not svg.is_file():
        return None
    rsvg = shutil.which("rsvg-convert")
    if rsvg is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
        png_path = tf.name
    try:
        subprocess.run(
            [rsvg, "-o", png_path, str(svg)],
            check=True,
            capture_output=True,
        )
        return Image.open(png_path).convert("RGBA").copy()
    except Exception:
        return None


_CODE_TO_FILENAME: dict[str, str] = {
    "X": "close",
    "A": "maximize",
    "I": "minimize",
    "S": "alldesktops",
    "L": "shade",
    "F": "keepabove",
    "B": "keepbelow",
}


def render(theme_name: str, target_w: int, target_h: int) -> Path:
    theme_dir = Path.home() / ".local/share/aurorae/themes" / theme_name
    if not theme_dir.is_dir():
        raise SystemExit(f"theme not installed: {theme_dir}")
    rc = theme_dir / f"{theme_name}rc"
    decoration_svg = theme_dir / "decoration.svg"
    L = _read_layout(rc)
    G = _read_general(rc)

    bt = L["BorderTop"]
    bb = L["BorderBottom"]
    bl = L["BorderLeft"]
    br = L["BorderRight"]
    title_height = L["TitleHeight"]
    title_edge_top = L["TitleEdgeTop"]
    button_w = L["ButtonWidth"]
    button_h = L["ButtonHeight"]
    button_margin_top = L["ButtonMarginTop"]
    button_margin_left = L["ButtonMarginLeft"]
    button_spacing = L["ButtonSpacing"]
    left_buttons = G.get("LeftButtons", "")
    right_buttons = G.get("RightButtons", "")
    active_text = tuple(int(c) for c in G["ActiveTextColor"].split(",")[:3])

    canvas_w = max(target_w, bl + br + 240)
    canvas_h = max(target_h, bt + bb + 240)

    # Window background
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (245, 245, 245, 255))

    pngs = _load_region_pngs(decoration_svg)

    inner_w = canvas_w - bl - br
    inner_h = canvas_h - bt - bb

    # Edge strips (stretched)
    if "top" in pngs and inner_w > 0:
        canvas.alpha_composite(_resize(pngs["top"], inner_w, bt), (bl, 0))
    if "bottom" in pngs and inner_w > 0:
        canvas.alpha_composite(_resize(pngs["bottom"], inner_w, bb),
                               (bl, canvas_h - bb))
    if "left" in pngs and inner_h > 0:
        canvas.alpha_composite(_resize(pngs["left"], bl, inner_h), (0, bt))
    if "right" in pngs and inner_h > 0:
        canvas.alpha_composite(_resize(pngs["right"], br, inner_h),
                               (canvas_w - br, bt))

    # Corners — resized to slot size (KWin stretches PNG to match SVG <image>
    # width/height with preserveAspectRatio="none").
    for region, pos, size in (
        ("topleft",     (0, 0),                       (bl, bt)),
        ("topright",    (canvas_w - br, 0),           (br, bt)),
        ("bottomleft",  (0, canvas_h - bb),           (bl, bb)),
        ("bottomright", (canvas_w - br, canvas_h - bb), (br, bb)),
    ):
        if region in pngs:
            canvas.alpha_composite(_resize(pngs[region], size[0], size[1]), pos)

    # Title text — QML rule (aurorae.qml ~lines 148-173):
    #   anchors.top = root.top
    #   topMargin = titleEdgeTop  (paddingTop=0 in our themes)
    #   height = max(titleHeight, buttonHeight)
    #   left/right bounded by button groups
    #   verticalAlignment = Center  (TitleVerticalAlignment=Center → AlignVCenter)
    draw = ImageDraw.Draw(canvas)
    text = f"{theme_name} — example window"
    title_band_h = max(title_height, button_h)
    font_size = max(10, min(28, title_band_h - 4))
    font = _font(font_size)
    try:
        tb = draw.textbbox((0, 0), text, font=font)
        tw = tb[2] - tb[0]
        th = tb[3] - tb[1]
    except AttributeError:
        tw, th = (len(text) * font_size // 2, font_size)

    left_buttons_total = (
        len(left_buttons) * button_w
        + max(0, len(left_buttons) - 1) * button_spacing
        if left_buttons
        else 0
    )
    right_buttons_total = (
        len(right_buttons) * button_w
        + max(0, len(right_buttons) - 1) * button_spacing
        if right_buttons
        else 0
    )
    text_left_bound = bl + button_margin_left + left_buttons_total
    text_right_bound = canvas_w - br - button_margin_left - right_buttons_total
    text_band_x0 = max(bl, text_left_bound)
    text_band_x1 = max(text_band_x0 + 1, text_right_bound)
    title_x = text_band_x0 + max(0, (text_band_x1 - text_band_x0 - tw) // 2)
    # Center within band of height title_band_h, anchored at title_edge_top.
    title_y = title_edge_top + max(0, (title_band_h - th) // 2)
    draw.text((title_x + 1, title_y + 1), text, font=font, fill=(0, 0, 0, 200))
    draw.text((title_x, title_y), text, font=font, fill=(*active_text, 255))

    # Buttons — QML rule (AuroraeButtonGroup.qml lines 44-47):
    #   anchors.top = root.top
    #   topMargin = titleEdgeTop + buttonMarginTop  (paddingTop=0)
    def _paint_buttons(codes: str, side: str) -> None:
        if not codes:
            return
        if side == "left":
            x = bl + button_margin_left
        else:
            # Right-edge buttons aligned to right inner edge
            total_w = len(codes) * button_w + max(0, len(codes) - 1) * button_spacing
            x = canvas_w - br - button_margin_left - total_w
        y = title_edge_top + button_margin_top
        for code in codes:
            fname = _CODE_TO_FILENAME.get(code)
            if not fname:
                x += button_w + button_spacing
                continue
            img = _load_button_svg(theme_dir, fname)
            if img is not None:
                img = _resize(img, button_w, button_h)
                canvas.alpha_composite(img, (x, y))
            else:
                # Visible fallback box so we can see if the button SVG was missing
                draw.rectangle(
                    [x, y, x + button_w, y + button_h],
                    outline=(255, 0, 255, 255),
                    width=2,
                )
                draw.text((x + 4, y + 4), code, font=_font(10),
                          fill=(255, 0, 255, 255))
            x += button_w + button_spacing

    _paint_buttons(left_buttons, "left")
    _paint_buttons(right_buttons, "right")

    out_dir = Path("/tmp/themey_review")
    out_dir.mkdir(exist_ok=True)
    out = out_dir / f"{theme_name}.png"
    canvas.save(out)
    return out


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    name = sys.argv[1]
    w = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    h = int(sys.argv[3]) if len(sys.argv) > 3 else 700
    out = render(name, w, h)
    print(out)


if __name__ == "__main__":
    main()
