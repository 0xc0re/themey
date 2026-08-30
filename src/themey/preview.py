"""HTML preview with an embedded mock-window PNG (PREVIEW-01).

Composes the converted decoration into a fake 640x400 window using Pillow:
corners and strips come from ``composite.compose_region`` so the preview
shows what KWin will render (multi-part composites including the alien-head
corner art, resize-handle decorations, etc.). Title text overlays the title
bar, and button glyphs are drawn on the right side of the title bar so the
user can see the buttons themselves.

The PNG is base64-embedded in the HTML so the preview is self-contained.

All theme-derived strings are html.escape()'d for XSS prevention
(T-08-02 in 01-08-PLAN.md threat model).
"""
from __future__ import annotations

import base64
import html
import io
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .generate.composite import button_dims, compose_region
from .generate.decoration_svg import DEFAULT_MAX_BORDER, strip_thicknesses
from .ir import Theme

_MOCK_W_MIN = 640
_MOCK_H_MIN = 400
_MOCK_INNER_MIN = 240  # min inner (content area) dimension


def _open_region_png(theme: Theme, side: str) -> Image.Image | None:
    """Return the composited region PNG as a Pillow Image, or None if empty."""
    try:
        data = compose_region(
            theme, side, prefer_active=True, max_border_output=DEFAULT_MAX_BORDER
        )
    except Exception:
        return None
    if not data:
        return None
    try:
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


def _resize_if_needed(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    if img.size == (target_w, target_h):
        return img
    return img.resize((target_w, target_h), Image.Resampling.NEAREST)


def _compose_mock_window(theme: Theme) -> Image.Image:
    """Build a mock window PNG using the theme's composited regions.

    The canvas grows when the theme's borders are chunky (Aliens at scale=2
    has BorderTop=358, BorderLeft=248); otherwise minimum is 640x400.
    """
    thick = strip_thicknesses(theme)
    top, bot = thick["top"], thick["bottom"]
    lft, rgt = thick["left"], thick["right"]

    mock_w = max(_MOCK_W_MIN, lft + rgt + _MOCK_INNER_MIN)
    mock_h = max(_MOCK_H_MIN, top + bot + _MOCK_INNER_MIN)

    canvas = Image.new(
        "RGBA", (mock_w, mock_h), (*theme.palette.titlebar_active, 255)
    )

    inner_w = mock_w - lft - rgt
    inner_h = mock_h - top - bot
    # Center fill — a neutral panel that contrasts with the title bar.
    inner = Image.new("RGBA", (inner_w, inner_h), (245, 245, 245, 255))
    canvas.paste(inner, (lft, top))

    # Edge strips — stretched composited slices.
    for side, pos, size in (
        ("top",         (lft, 0),               (inner_w, top)),
        ("bottom",      (lft, mock_h - bot),    (inner_w, bot)),
        ("left",        (0, top),               (lft, inner_h)),
        ("right",       (mock_w - rgt, top),    (rgt, inner_h)),
    ):
        img = _open_region_png(theme, side)
        if img is not None and size[0] > 0 and size[1] > 0:
            canvas.alpha_composite(_resize_if_needed(img, size[0], size[1]), pos)

    # Corners — native sizes (BorderLeft by BorderTop, etc.).
    for side, pos, size in (
        ("topleft",     (0, 0),                           (lft, top)),
        ("topright",    (mock_w - rgt, 0),                (rgt, top)),
        ("bottomleft",  (0, mock_h - bot),                (lft, bot)),
        ("bottomright", (mock_w - rgt, mock_h - bot),     (rgt, bot)),
    ):
        img = _open_region_png(theme, side)
        if img is not None and size[0] > 0 and size[1] > 0:
            canvas.alpha_composite(_resize_if_needed(img, size[0], size[1]), pos)

    # Title text overlay
    _draw_title(canvas, theme, top, mock_w)

    # Button glyphs on the right side of the title bar
    _draw_buttons(canvas, theme, top, rgt, mock_w)

    # Mock content text
    _draw_body(canvas, theme, top, lft)

    return canvas


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Try to load a system sans font; fall back to PIL default."""
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


def _draw_title(canvas: Image.Image, theme: Theme, top: int, mock_w: int) -> None:
    """Draw the title text centered in the top strip."""
    draw = ImageDraw.Draw(canvas)
    text = f"{theme.display_name} - example window"
    # Cap font size at 24 so very chunky borders don't render absurd text.
    font_px = max(10, min(24, top - 6))
    font = _font(font_px)
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
    except AttributeError:
        tw, th = (len(text) * font_px // 2, font_px)
    x = (mock_w - tw) // 2
    y = (top - th) // 2
    fill = (*theme.palette.text_active, 255)
    draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 200))
    draw.text((x, y), text, font=font, fill=fill)


def _load_button_glyph(
    theme: Theme, code: str, w: int, h: int
) -> Image.Image | None:
    """Load the per-button iclass artwork as a (w, h) RGBA Image."""
    from .generate.button_svg import _find_iclass_for_code

    ic = _find_iclass_for_code(theme, code)
    if ic is None:
        return None
    p = ic.normal_active or ic.normal
    if p is None or not p.is_file():
        return None
    try:
        with Image.open(p) as src:
            img = src.convert("RGBA")
        if img.size != (w, h):
            img = img.resize((w, h), Image.Resampling.NEAREST)
        return img
    except Exception:
        return None


def _draw_buttons(
    canvas: Image.Image, theme: Theme, top: int, rgt: int, mock_w: int
) -> None:
    """Draw the right-side button glyphs onto the title bar."""
    if not theme.right_buttons:
        return
    btn_w, btn_h = button_dims(theme)
    margin_top = max(0, (top - btn_h) // 2)
    spacing = 4 * theme.scale
    margin_right = max(3 * theme.scale, rgt // 2)

    codes = list(theme.right_buttons)
    n = len(codes)
    total_w = n * btn_w + max(0, n - 1) * spacing
    x = mock_w - margin_right - total_w
    y = margin_top
    for code in codes:
        glyph = _load_button_glyph(theme, code, btn_w, btn_h)
        if glyph is not None:
            canvas.alpha_composite(glyph, (x, y))
        x += btn_w + spacing


def _draw_body(canvas: Image.Image, theme: Theme, top: int, lft: int) -> None:
    draw = ImageDraw.Draw(canvas)
    font = _font(14)
    msg = (
        f"themey converted '{theme.name}.etheme'\n"
        f"scale: {theme.scale}x\n"
        f"buttons: L={theme.left_buttons or '(none)'}"
        f"  R={theme.right_buttons or '(none)'}\n"
        f"notes:   {len(theme.notes)}"
    )
    draw.multiline_text(
        (lft + 20, top + 20), msg, font=font, fill=(40, 40, 40, 255), spacing=6
    )


def _png_data_uri(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def render(theme: Theme, out_path: Path) -> Path:
    """Write an HTML preview of *theme* to *out_path*. Returns *out_path*."""
    mock = _compose_mock_window(theme)
    mock_w, mock_h = mock.size
    mock_uri = _png_data_uri(mock)

    notes_html = "\n".join(
        f"  <li><code>{html.escape(n)}</code></li>"
        for n in theme.notes[:50]
    )
    more_notes = ""
    if len(theme.notes) > 50:
        more_notes = (
            f"<p><em>... and {len(theme.notes) - 50} more "
            "(see report.txt for full list)</em></p>"
        )

    name_safe = html.escape(theme.display_name)
    plugin_id_safe = html.escape(theme.name)
    skipped_safe = html.escape(
        ", ".join(theme.skipped_borders) if theme.skipped_borders else "none"
    )
    kwrite_cmd = (
        "kwriteconfig6 --file kwinrc --group org.kde.kdecoration2"
        " --key library org.kde.kwin.aurorae\n"
        "kwriteconfig6 --file kwinrc --group org.kde.kdecoration2"
        f" --key theme __aurorae__svg__{plugin_id_safe}\n"
        "qdbus org.kde.KWin /KWin reconfigure"
    )

    doc = f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>themey: {name_safe}</title>
<style>
  body {{ font: 14px sans-serif; max-width: 760px; margin: 2em auto; padding: 1em;
          background: #f0f0f0; }}
  .mock-window {{ display: block; margin: 1em auto; box-shadow: 0 4px 24px rgba(0,0,0,0.25);
                  border-radius: 4px; max-width: 100%; }}
  pre {{ background: #f4f4f4; padding: 0.75em; border-radius: 4px;
         user-select: all; overflow-x: auto; }}
  ul.notes {{ font-size: 12px; color: #555; max-height: 30em; overflow-y: auto;
              background: white; padding: 0.5em 1em 0.5em 2em; border-radius: 4px; }}
  .meta {{ color: #777; font-size: 12px; margin-top: 2em; }}
</style></head><body>
<h1>themey: {name_safe}</h1>
<p>Converted from <code>{plugin_id_safe}.etheme</code> at scale {theme.scale}x.</p>

<img class="mock-window" src="{mock_uri}" alt="Mock window with {name_safe} decoration"
     width="{mock_w}" height="{mock_h}">

<h2>Apply this theme</h2>
<p>Open <strong>System Settings &rarr; Window Decorations</strong> and select
   <strong>{name_safe}</strong> from the list, OR run from a terminal:</p>
<pre>{kwrite_cmd}</pre>
<p><strong>Borders look thin?</strong> Both Aurorae plugins in Plasma 6.6 clamp
   the left/right/bottom borders to the <em>Border size</em> setting (Normal =
   4&ndash;6&nbsp;px, Oversized = 36&ndash;48&nbsp;px); only the title band
   follows the theme, so wide corner art is folded into it. For the fattest
   frame set <em>Border size = Oversized</em> on that page, or run:</p>
<pre>themey apply {plugin_id_safe} --border-size Oversized</pre>
<p>Button order is global (Window Decorations &rarr; Titlebar Buttons), not part
   of the theme.</p>

<h2>Conversion notes ({len(theme.notes)} entries)</h2>
<ul class="notes">
{notes_html}
</ul>
{more_notes}

<p class="meta">Skipped borders: {skipped_safe}.
   Color scheme, wallpaper, cursor, and Look-and-Feel bundle are deferred to later phases.
   See report.txt for full fidelity details.</p>

</body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path
