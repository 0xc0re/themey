"""9-patch slice primitive driven by __EDGE_SCALING values.

Field order is L R T B (Pitfall 1, verified against E16 iclass.c:
``sscanf("%i %i %i %i", &l, &r, &t, &b)`` and the
``EImageBorder { left, right, top, bottom }`` struct in eimage.h).

Phase 1 Aurorae generator embeds the WHOLE PNG inside decoration.svg
and lets FrameSvg perform the 9-patch rendering via hint margins. This
primitive is included for completeness, future use (e.g. per-region
color sampling for Phase 2 palette extraction), and as a place to
validate __EDGE_SCALING fits inside image dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass(frozen=True)
class NinePatchRegions:
    """Nine cropped regions from a 9-patch slice operation.

    Ordered: topleft, top, topright, left, center, right, bottomleft, bottom, bottomright.

    Corner dimensions match the requested (left, right, top, bottom) edge values.
    Edge strip dimensions span the image minus the two adjacent corners.
    Center spans the remaining area.
    """

    topleft: Image.Image
    top: Image.Image
    topright: Image.Image
    left: Image.Image
    center: Image.Image
    right: Image.Image
    bottomleft: Image.Image
    bottom: Image.Image
    bottomright: Image.Image


def slice_9patch(
    img: Image.Image,
    left: int,
    right: int,
    top: int,
    bottom: int,
) -> NinePatchRegions:
    """Slice the image into 9 regions per __EDGE_SCALING (L R T B order).

    Args:
        img: Source Pillow Image to slice.
        left: Width of the left edge strip (pixels).
        right: Width of the right edge strip (pixels).
        top: Height of the top edge strip (pixels).
        bottom: Height of the bottom edge strip (pixels).

    Returns:
        :class:`NinePatchRegions` with 9 cropped sub-images.

    Raises:
        ValueError: If ``left + right`` exceeds the image width, or
            ``top + bottom`` exceeds the image height.
    """
    w, h = img.size
    if left + right > w:
        raise ValueError(
            f"left+right ({left}+{right}={left + right}) exceeds image width {w}"
        )
    if top + bottom > h:
        raise ValueError(
            f"top+bottom ({top}+{bottom}={top + bottom}) exceeds image height {h}"
        )
    center_w = w - left - right
    center_h = h - top - bottom

    # Pillow crop boxes are (left_px, upper_px, right_px, lower_px)
    return NinePatchRegions(
        topleft=img.crop((0, 0, left, top)),
        top=img.crop((left, 0, left + center_w, top)),
        topright=img.crop((left + center_w, 0, w, top)),
        left=img.crop((0, top, left, top + center_h)),
        center=img.crop((left, top, left + center_w, top + center_h)),
        right=img.crop((left + center_w, top, w, top + center_h)),
        bottomleft=img.crop((0, top + center_h, left, h)),
        bottom=img.crop((left, top + center_h, left + center_w, h)),
        bottomright=img.crop((left + center_w, top + center_h, w, h)),
    )
