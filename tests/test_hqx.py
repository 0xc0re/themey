"""Tests for src/themey/images/hqx.py — pure-Python hq2x/hq3x.

Golden values are hand-computed from the documented blend rules (see the
module docstring): a diagonal-edge corner blends (2*c + s1 + s2) // 4.
"""
from __future__ import annotations

import pytest
from PIL import Image

from themey.images.hqx import hqx

W = (255, 255, 255, 255)
B = (0, 0, 0, 255)


def _checkerboard() -> Image.Image:
    img = Image.new("RGBA", (2, 2))
    img.putpixel((0, 0), W)
    img.putpixel((1, 1), W)
    img.putpixel((1, 0), B)
    img.putpixel((0, 1), B)
    return img


@pytest.mark.parametrize("factor", [2, 3])
def test_dimensions(factor: int):
    out = hqx(Image.new("RGBA", (5, 7), W), factor)
    assert out.size == (5 * factor, 7 * factor)
    assert out.mode == "RGBA"


@pytest.mark.parametrize("bad", [0, 1, 4])
def test_rejects_bad_factor(bad: int):
    with pytest.raises(ValueError):
        hqx(Image.new("RGBA", (2, 2)), bad)


@pytest.mark.parametrize("factor", [2, 3])
def test_flat_image_stays_flat(factor: int):
    color = (12, 34, 56, 200)
    out = hqx(Image.new("RGBA", (4, 4), color), factor)
    assert set(out.get_flattened_data()) == {color}


@pytest.mark.parametrize("factor", [2, 3])
def test_deterministic(factor: int):
    img = _checkerboard()
    assert hqx(img, factor).tobytes() == hqx(img, factor).tobytes()


def test_alpha_participates_in_blending():
    """Alpha is interpolated like a color channel (RGBA-inclusive)."""
    opaque = (255, 0, 0, 255)
    clear = (255, 0, 0, 0)
    img = Image.new("RGBA", (2, 2), opaque)
    img.putpixel((1, 0), clear)
    img.putpixel((0, 1), clear)
    out = hqx(img, 2)
    alphas = {px[3] for px in out.get_flattened_data()}
    assert alphas - {0, 255}, "blended corners must carry intermediate alpha"


def test_hq2x_checkerboard_golden():
    """BR subpixel of the white (0,0) pixel: down/right are both black and
    agree with each other → (2*W + B + B) // 4 = 127 per channel; alpha all
    255 → stays 255."""
    out = hqx(_checkerboard(), 2)
    assert out.getpixel((0, 0)) == W  # clamped edge corner: no blend
    assert out.getpixel((1, 1)) == (127, 127, 127, 255)


def test_hq3x_checkerboard_golden():
    """3x block of the white (0,0) pixel: center stays c, BR corner blends
    like hq2x, TL corner (clamped neighbors equal c) stays c."""
    out = hqx(_checkerboard(), 3)
    assert out.getpixel((1, 1)) == W  # center of the (0,0) block
    assert out.getpixel((0, 0)) == W
    assert out.getpixel((2, 2)) == (127, 127, 127, 255)
