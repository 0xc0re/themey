"""Upscale primitives for pixel-art E16 border PNGs.

Borders use NEAREST resampling by default. Pixel-art at 13-30 px source
resolution must stay sharp at 2x/3x; bilinear resampling blurs corners and
produces visible scaling seams.

``upscale_part`` is the QML backend's entry point: it targets
``(scale_px(w), scale_px(h))`` — the SAME rounding the geometry resolver
uses — so BorderImage insets always match the shipped art (mismatched
rounding smears the 9-patch caps). It dispatches per mode with an
explicit branch each and no shared tail: a mode that forgets to return
raises rather than silently becoming hqx, which is what the old
fall-through did to any mode past the ``nearest`` early-returns.

Two opt-in modes smooth instead:

``quality`` (``--upscale quality``) runs the pure-Python hqx port;
fractional scales go hqx(max(2, ceil(scale))) then LANCZOS *down* to
target (hqx has no 1x, so sub-1 scales upsample via hqx2 first).

``waifu2x`` (``--upscale waifu2x``) shells out to waifu2x-ncnn-vulkan, a
CNN trained on this exact task. It scales by powers of two ONLY, so
``_waifu2x_factor`` picks the smallest supported factor at or above the
requested scale and the surplus comes back off with LANCZOS — scale 3
goes 4x down, 1.5 goes 2x down, 2 is exact. Unlike hqx it is optional and
external: ``pipeline.convert`` checks ``external.waifu2x_available()``
once and substitutes ``quality`` with an ``upscale:`` note when the
binary or its model weights are missing, so THIS module can stay pure and
simply raise ``Waifu2xError`` if called anyway. The layering is: pipeline
decides, upscale executes.

Those two LANCZOS calls are the ONLY ones permitted under
src/themey/images/ (CLAUDE.md carve-out). Both downsample output that is
already smooth — hqx's, and the CNN's — never raw pixel art.

Wallpapers never come through here: ``generate/wallpaper.py`` copies them
at their real dimensions, and the one photographic LANCZOS in the tree is
``lookandfeel.write_preview``'s thumbnail.
"""
from __future__ import annotations

import math

from PIL import Image

from .hqx import hqx
from .waifu2x import waifu2x

UPSCALE_MODES = ("nearest", "quality", "waifu2x")

# waifu2x-ncnn-vulkan's -s vocabulary, verified against the binary: 1, 2,
# 4, 8, 16, 32 are accepted and 3 is rejected outright ("invalid scale
# argument"), on all three shipped models. 1 is left out because scale 1
# never reaches the scaler at all.
_WAIFU2X_FACTORS = (2, 4, 8, 16, 32)


def _waifu2x_factor(scale: float) -> int:
    """Smallest supported waifu2x factor >= *scale* (never below 2).

    themey's scale range is [0.5, 3], so in practice this is 2 for
    everything up to and including 2.0 and 4 above it; the rest of the
    table exists so the function stays total. A scale past the largest
    supported factor gets that factor and a LANCZOS *up* — outside
    themey's range, but better than an exception.
    """
    for factor in _WAIFU2X_FACTORS:
        if factor >= scale:
            return factor
    return _WAIFU2X_FACTORS[-1]


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
        scale: Output scale in [0.5, 3]; may be fractional (e.g. 1.5 or
            0.5 — NEAREST decimation is the pixel-art-honest downscale).
        mode: ``"nearest"`` (default, pixel-art sharp), ``"quality"``
            (hqx edge-directed smoothing) or ``"waifu2x"`` (CNN, external
            binary). Both smoothing modes overshoot to a supported factor
            and LANCZOS back down when the scale is not one they hit
            exactly.

    Raises:
        ValueError: If ``mode`` is unknown.
        external.Waifu2xError: In ``waifu2x`` mode when the binary or its
            model weights are unusable. Callers that want a fallback ask
            ``external.waifu2x_available()`` first, as pipeline does.
    """
    # Lazy: importing at module level closes a cycle through
    # generate/qmldeco/__init__ → package → this module. scale_px's
    # canonical home stays resolver.py (lockstep with resolver.js).
    from themey.generate.qmldeco.resolver import scale_px

    if mode not in UPSCALE_MODES:
        raise ValueError(f"upscale mode must be one of {UPSCALE_MODES} (got {mode!r})")
    is_int = scale == int(scale)
    target = (
        max(1, scale_px(img.width, scale)),
        max(1, scale_px(img.height, scale)),
    )

    if mode == "nearest":
        if is_int:
            return upscale_nearest(img, int(scale))
        return img.resize(target, resample=Image.Resampling.NEAREST)

    if mode == "quality":
        if scale == 1:
            return img.copy()
        if is_int:
            return hqx(img, int(scale))  # type: ignore[arg-type]  # 2 or 3 here
        # max(2, ...): hqx has no 1x, and ceil of a sub-1 scale is 1 — a
        # 0.75 target goes hqx2 then LANCZOS down, staying in the carve-out.
        big = hqx(img, max(2, math.ceil(scale)))  # type: ignore[arg-type]  # 2 or 3
        return big.resize(target, resample=Image.Resampling.LANCZOS)

    if mode == "waifu2x":
        if scale == 1:
            return img.copy()
        big = waifu2x(img, _waifu2x_factor(scale))
        if big.size == target:
            return big
        return big.resize(target, resample=Image.Resampling.LANCZOS)

    # Unreachable while UPSCALE_MODES and the branches above agree — and
    # that is the point: adding a mode to the tuple without a branch here
    # fails loudly instead of quietly rendering as hqx.
    raise ValueError(f"upscale mode {mode!r} is declared but not implemented")
