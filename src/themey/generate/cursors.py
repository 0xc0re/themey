"""E16 ``__CURSOR`` blocks → an installable XCursor pointer theme.

Output layout (byte-verified against an installed Plasma cursor theme):

    <themey_<slug>-cursors>/index.theme     [Icon Theme] Name= + Inherits=
    <themey_<slug>-cursors>/cursors/<name>  XCursor binaries, modern names
    <themey_<slug>-cursors>/cursors/<alias> symlink -> a modern name

Modern names (``default``, ``size_hor``, ...) are canonical on Plasma 6.6
and the legacy X11 names (``left_ptr``, ``sb_h_double_arrow``, ...) are
symlinks pointing AT them — the reverse of the pre-6 convention. Symlinks
are correct here; the zero-symlink rule in the Global-Theme plan applies
to the Look-and-Feel bundle tree, not to cursor themes. Aliases are only
created for shapes this theme actually ships, so ``Inherits=breeze_cursors``
still supplies Breeze art for everything E16 never defined.

Three contracts govern this module:

1. **Polarity.** Each cursor is an X11 bitmap pair, per
   ``XCreatePixmapCursor``: mask bit SET = the pixel is drawn, CLEAR =
   transparent; within a drawn pixel the image bit picks foreground
   (set) or background (clear). E16 ships the mask as a sibling
   ``<file>.xbm.mask`` — ``CursorSpec`` has no field for it, so it is
   derived here. With no mask file the image is foreground over
   transparent. Inverting either polarity ruins every cursor in every
   theme; ``tests/test_cursors_xbm.py`` is the guard.

2. **We parse XBM ourselves, not with Pillow.** CLAUDE.md's stack table
   nominates ``PIL.XbmImagePlugin``, and it cannot read these files.
   Measured on the fixtures: its header regex is anchored at ``#define``
   so Mac3D's GIMP-authored cursors (``/* Made with GIMP */`` on line 1)
   raise UnidentifiedImageError, and its hotspot sub-pattern
   (``[^_]*_x_hot``) cannot match ``resize_h_x_hot``, which is the form
   nearly every fixture uses. Since the hotspot is the one piece of data
   that only the XBM carries (see 3), silently losing it is worse than
   the ~40 lines of parser below.

3. **The hotspot comes from the XBM, not the cfg.** No fixture theme
   sets ``__HOT_X``/``__HOT_Y``; all 41 fixture XBMs carry ``_x_hot`` /
   ``_y_hot`` defines, which is what X itself reads. ``CursorSpec``
   cannot distinguish "declared 0" from "absent", so a nonzero cfg
   hotspot wins (an explicit override) and otherwise the XBM's own value
   is used. Out-of-range values are clamped into the image — Mac3D's
   ``pin.xbm`` really does declare ``y_hot 20`` on a 20px-tall bitmap,
   and xcursorgen rejects that outright.

Scaling: three nominal sizes at x1/x2/x3, NEAREST only. The
``--upscale quality`` hqx path is deliberately ignored here — hqx
interpolates edges between color regions, which is meaningless for 1-bit
art and would soften the one-pixel outlines these cursors are made of.
Nominal size is the scaled art's own larger dimension, so a 16px source
yields 16/32/48 and Mac3D's 25px ``move.xbm`` yields 25/50/75 rather than
being resampled off its pixel grid.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

log = logging.getLogger(__name__)

#: Upscale factors emitted for every cursor; also the nominal-size multipliers.
SCALES: tuple[int, ...] = (1, 2, 3)

#: Cursor art is 16-25 px in practice; anything larger is a malformed or
#: hostile header, not a pointer (same discipline as the wallpaper guard).
MAX_CURSOR_DIM = 512

INHERITS = "breeze_cursors"


class CursorError(Exception):
    """A cursor source could not be read or converted."""


# --------------------------------------------------------------------- #
# XBM reading
# --------------------------------------------------------------------- #

_DEFINE_RE = re.compile(r"#define\s+\S*?_(width|height|x_hot|y_hot)\s+(-?\d+)")
_BITS_RE = re.compile(r"_bits\s*\[\s*\]\s*=\s*\{(.*?)\}", re.DOTALL)
_BYTE_RE = re.compile(r"0[xX]([0-9a-fA-F]{1,2})")


@dataclass(frozen=True)
class Xbm:
    """One X11 bitmap: dimensions, optional hotspot, and its packed bits.

    ``bits`` is row-major with each row padded to a whole number of bytes
    and the least significant bit of each byte leftmost (X11 XBM order).
    """

    width: int
    height: int
    hot_x: int | None
    hot_y: int | None
    bits: bytes

    @property
    def stride(self) -> int:
        return (self.width + 7) // 8

    def bit(self, x: int, y: int) -> bool:
        return bool(self.bits[y * self.stride + (x >> 3)] & (1 << (x & 7)))


def read_xbm(path: Path) -> Xbm:
    """Parse an X11 XBM file. Raises :class:`CursorError` if malformed."""
    try:
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise CursorError(f"cannot read {path}: {exc}") from exc

    fields: dict[str, int] = {
        m.group(1): int(m.group(2)) for m in _DEFINE_RE.finditer(text)
    }
    width = fields.get("width")
    height = fields.get("height")
    if width is None or height is None:
        raise CursorError(f"{path.name}: no _width/_height defines")
    if not 0 < width <= MAX_CURSOR_DIM or not 0 < height <= MAX_CURSOR_DIM:
        raise CursorError(
            f"{path.name}: {width}x{height} is outside 1..{MAX_CURSOR_DIM}"
        )

    body = _BITS_RE.search(text)
    if body is None:
        raise CursorError(f"{path.name}: no _bits[] array")
    bits = bytes(int(m.group(1), 16) for m in _BYTE_RE.finditer(body.group(1)))
    expected = ((width + 7) // 8) * height
    if len(bits) < expected:
        raise CursorError(
            f"{path.name}: expected {expected} bytes of bit data, got {len(bits)}"
        )

    return Xbm(
        width=width,
        height=height,
        hot_x=fields.get("x_hot"),
        hot_y=fields.get("y_hot"),
        bits=bits[:expected],
    )


def rasterize(
    image: Xbm,
    mask: Xbm | None,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
) -> Image.Image:
    """Colorize *image* through *mask* into an RGBA Image.

    Polarity per ``XCreatePixmapCursor`` — see contract 1 in the module
    docstring. With ``mask=None`` set bits are *fg* and clear bits are
    transparent (the background would otherwise paint a solid rectangle
    around the pointer).
    """
    if mask is not None and (mask.width, mask.height) != (image.width, image.height):
        raise CursorError(
            f"mask is {mask.width}x{mask.height} but image is "
            f"{image.width}x{image.height}"
        )
    fg_px = (*fg, 255)
    bg_px = (*bg, 255)
    clear = (0, 0, 0, 0)
    out = Image.new("RGBA", (image.width, image.height), clear)
    pixels = out.load()
    assert pixels is not None
    for y in range(image.height):
        for x in range(image.width):
            if mask is not None and not mask.bit(x, y):
                continue
            on = image.bit(x, y)
            if mask is None:
                if on:
                    pixels[x, y] = fg_px
            else:
                pixels[x, y] = fg_px if on else bg_px
    return out
