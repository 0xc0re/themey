"""Upscale primitives for pixel-art E16 border PNGs.

Borders use NEAREST resampling by default (Pitfall 12 / Anti-Pattern in
01-RESEARCH.md). Pixel-art at 13-30 px source resolution must stay sharp
at 2x/3x; bilinear resampling blurs corners and produces visible scaling
seams.

``upscale_part`` is the QML backend's entry point: it targets
``(scale_px(w), scale_px(h))`` — the SAME rounding the geometry resolver
uses — so BorderImage insets always match the shipped art (mismatched
rounding smears the 9-patch caps). The opt-in ``quality`` mode
(``--upscale quality``) runs the pure-Python hqx port; fractional scales
there go hqx(ceil(scale)) then LANCZOS *down* to target. That LANCZOS
call is the ONLY permitted one under src/themey/images/ — it downsamples
already-smoothed hqx output, never raw pixel art (CLAUDE.md carve-out).

Phase 2 wallpaper module uses a separate file with photographic resampling.
"""
from __future__ import annotations

import math

from PIL import Image

from .hqx import hqx

UPSCALE_MODES = ("nearest", "quality")


def upscale_nearest(img: Image.Image, scale: int) -> Image.Image:
    """Return a new Image of (width*scale, height*scale) using NEAREST resampling.

    Args:
        img: Source Pillow Image.
        scale: Integer scale factor; must be 1, 2, or 3.

    Returns:
        A new Image with dimensions (width*scale, height*scale).

    Raises:
        ValueError: If scale is not in {1, 2, 3}.
    """
    if scale not in (1, 2, 3):
        raise ValueError(f"scale must be 1, 2, or 3 (got {scale})")
    if scale == 1:
        return img.copy()
    new_size = (img.width * scale, img.height * scale)
    return img.resize(new_size, resample=Image.Resampling.NEAREST)


def upscale_part(
    img: Image.Image, scale: float, mode: str = "nearest"
) -> Image.Image:
    """Upscale one part image to ``(scale_px(w), scale_px(h))``.

    Args:
        img: Source Pillow Image.
        scale: Output scale in [1, 3]; may be fractional (e.g. 1.5).
        mode: ``"nearest"`` (default, pixel-art sharp) or ``"quality"``
            (hqx edge-directed smoothing; fractional scales downsample
            hqx(ceil(scale)) output with LANCZOS).

    Raises:
        ValueError: If ``mode`` is unknown.
    """
    # Lazy: importing at module level closes a cycle through
    # generate/qmldeco/__init__ → package → this module. scale_px's
    # canonical home stays resolver.py (lockstep with resolver.js).
    from themey.generate.qmldeco.resolver import scale_px

    if mode not in UPSCALE_MODES:
        raise ValueError(f"upscale mode must be one of {UPSCALE_MODES} (got {mode!r})")
    is_int = scale == int(scale)
    if mode == "nearest" and is_int:
        return upscale_nearest(img, int(scale))
    target = (
        max(1, scale_px(img.width, scale)),
        max(1, scale_px(img.height, scale)),
    )
    if mode == "nearest":
        return img.resize(target, resample=Image.Resampling.NEAREST)
    if scale == 1:
        return img.copy()
    if is_int:
        return hqx(img, int(scale))  # type: ignore[arg-type]  # 2 or 3 here
    big = hqx(img, math.ceil(scale))  # type: ignore[arg-type]  # 2 or 3 here
    return big.resize(target, resample=Image.Resampling.LANCZOS)
