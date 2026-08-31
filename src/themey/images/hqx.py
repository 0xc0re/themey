"""Pure-Python hqx-style quality upscaler (hq2x / hq3x) for pixel art.

Contract: opt-in quality path behind ``themey convert --upscale quality``
— NEAREST (images/upscale.py) stays the default. This is a compact
reimplementation of the hqx approach (Maxim Stepin's edge-directed
interpolation), NOT a byte-exact port of the original 256-case tables:
neighbor similarity is thresholded in YUV, and each output subpixel picks
a weighted blend from the LUT-style rules below. The rules that matter
for E16 border art — diagonal edges get rounded, flat areas stay flat,
straight edges stay sharp — hold; golden fixtures in tests/test_hqx.py
pin the exact blends.

Equality and interpolation are RGBA-INCLUSIVE (chris, 2026-08-30): alpha
differences beyond the threshold make pixels "different", and alpha is
interpolated with the same weights as the color channels, so translucent
shaped-border edges anti-alias instead of fringing.

Blend rules per output subpixel of source pixel ``c`` (neighbors clamped
at image edges):

- corner (side neighbors s1, s2; diagonal d):
    * s1 == s2, both != c  → (2*c + s1 + s2) // 4   (diagonal edge)
    * s1 == c == s2, d != c → (3*c + d) // 4        (inner-corner round)
    * otherwise             → c
- hq3x edge midpoint (side neighbor s, its in-row neighbors n1, n2):
    * s != c and (s == n1 or s == n2) → (3*c + s) // 4
    * otherwise                       → c
- hq3x center → c

Determinism: integer arithmetic only after the YUV comparison; no
randomness, no dithering.
"""
from __future__ import annotations

from typing import Literal, cast

from PIL import Image

# hqx reference thresholds (YUV), plus an RGBA-inclusive alpha threshold.
_Y_THRESHOLD = 48
_U_THRESHOLD = 7
_V_THRESHOLD = 6
_A_THRESHOLD = 48

Pixel = tuple[int, int, int, int]


def _different(p: Pixel, q: Pixel) -> bool:
    if p == q:
        return False
    ry, gy, by = p[0] - q[0], p[1] - q[1], p[2] - q[2]
    y = 0.299 * ry + 0.587 * gy + 0.114 * by
    u = -0.169 * ry - 0.331 * gy + 0.5 * by
    v = 0.5 * ry - 0.419 * gy - 0.081 * by
    return (
        abs(y) > _Y_THRESHOLD
        or abs(u) > _U_THRESHOLD
        or abs(v) > _V_THRESHOLD
        or abs(p[3] - q[3]) > _A_THRESHOLD
    )


def _interp2(c: Pixel, a: Pixel, b: Pixel) -> Pixel:
    return (
        (2 * c[0] + a[0] + b[0]) // 4,
        (2 * c[1] + a[1] + b[1]) // 4,
        (2 * c[2] + a[2] + b[2]) // 4,
        (2 * c[3] + a[3] + b[3]) // 4,
    )


def _interp31(c: Pixel, a: Pixel) -> Pixel:
    return (
        (3 * c[0] + a[0]) // 4,
        (3 * c[1] + a[1]) // 4,
        (3 * c[2] + a[2]) // 4,
        (3 * c[3] + a[3]) // 4,
    )


def _corner(c: Pixel, s1: Pixel, s2: Pixel, d: Pixel) -> Pixel:
    if _different(s1, c) and _different(s2, c) and not _different(s1, s2):
        return _interp2(c, s1, s2)
    if not _different(s1, c) and not _different(s2, c) and _different(d, c):
        return _interp31(c, d)
    return c


def _edge_mid(c: Pixel, s: Pixel, n1: Pixel, n2: Pixel) -> Pixel:
    if _different(s, c) and (
        not _different(s, n1) or not _different(s, n2)
    ):
        return _interp31(c, s)
    return c


def hqx(img: Image.Image, factor: Literal[2, 3]) -> Image.Image:
    """Return *img* upscaled by ``factor`` (2 or 3) with hqx-style
    edge-directed interpolation. Always returns a new RGBA image.

    Raises:
        ValueError: If ``factor`` is not 2 or 3.
    """
    if factor not in (2, 3):
        raise ValueError(f"hqx factor must be 2 or 3 (got {factor})")
    src = img.convert("RGBA")
    w, h = src.size
    pix = src.load()
    assert pix is not None
    out = Image.new("RGBA", (w * factor, h * factor))
    out_pix = out.load()
    assert out_pix is not None

    def at(x: int, y: int) -> Pixel:
        # Clamp: edge pixels replicate outward, like the reference hqx.
        if x < 0:
            x = 0
        elif x >= w:
            x = w - 1
        if y < 0:
            y = 0
        elif y >= h:
            y = h - 1
        # cast: RGBA access always yields a 4-tuple; the stub's float
        # covers single-band modes.
        return cast(Pixel, pix[x, y])

    for y in range(h):
        for x in range(w):
            c = at(x, y)
            up, down = at(x, y - 1), at(x, y + 1)
            left, right = at(x - 1, y), at(x + 1, y)
            ul, ur = at(x - 1, y - 1), at(x + 1, y - 1)
            dl, dr = at(x - 1, y + 1), at(x + 1, y + 1)

            tl = _corner(c, up, left, ul)
            tr = _corner(c, up, right, ur)
            bl = _corner(c, down, left, dl)
            br = _corner(c, down, right, dr)

            ox, oy = x * factor, y * factor
            if factor == 2:
                out_pix[ox, oy] = tl
                out_pix[ox + 1, oy] = tr
                out_pix[ox, oy + 1] = bl
                out_pix[ox + 1, oy + 1] = br
            else:
                out_pix[ox, oy] = tl
                out_pix[ox + 2, oy] = tr
                out_pix[ox, oy + 2] = bl
                out_pix[ox + 2, oy + 2] = br
                out_pix[ox + 1, oy] = _edge_mid(c, up, ul, ur)
                out_pix[ox + 1, oy + 2] = _edge_mid(c, down, dl, dr)
                out_pix[ox, oy + 1] = _edge_mid(c, left, ul, dl)
                out_pix[ox + 2, oy + 1] = _edge_mid(c, right, ur, dr)
                out_pix[ox + 1, oy + 1] = c
    return out
