"""NEAREST upscale primitive for pixel-art E16 border PNGs.

Borders MUST use NEAREST resampling (Pitfall 12 / Anti-Pattern in 01-RESEARCH.md).
Pixel-art at 13-30 px source resolution must stay sharp at 2x/3x; bilinear
resampling blurs corners and produces visible scaling seams.

Phase 2 wallpaper module uses a separate file with photographic resampling.
"""
from __future__ import annotations

from PIL import Image


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
