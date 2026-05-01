"""Tests for src/themey/images/upscale.py."""
import pytest
from PIL import Image

from themey.images.upscale import upscale_nearest


def _make_2x2_corners() -> Image.Image:
    img = Image.new("RGBA", (2, 2))
    img.putpixel((0, 0), (255, 0, 0, 255))
    img.putpixel((1, 0), (0, 255, 0, 255))
    img.putpixel((0, 1), (0, 0, 255, 255))
    img.putpixel((1, 1), (255, 255, 0, 255))
    return img


def test_upscale_scale_1_identity():
    img = Image.new("RGBA", (8, 8), (1, 2, 3, 255))
    out = upscale_nearest(img, 1)
    assert out.size == (8, 8)


def test_upscale_scale_2_doubles_dimensions():
    img = Image.new("RGBA", (8, 8))
    out = upscale_nearest(img, 2)
    assert out.size == (16, 16)


def test_upscale_scale_3_triples():
    img = Image.new("RGBA", (8, 8))
    out = upscale_nearest(img, 3)
    assert out.size == (24, 24)


def test_upscale_pixel_exact_2x2_to_4x4():
    # NEAREST: each source pixel becomes a 2x2 block of the same color
    img = _make_2x2_corners()
    out = upscale_nearest(img, 2)
    assert out.size == (4, 4)
    # top-left quadrant is red
    for x in (0, 1):
        for y in (0, 1):
            assert out.getpixel((x, y)) == (255, 0, 0, 255), (
                f"NEAREST should preserve red corner; got {out.getpixel((x, y))} at ({x},{y})"
            )
    # top-right quadrant is green
    for x in (2, 3):
        for y in (0, 1):
            assert out.getpixel((x, y)) == (0, 255, 0, 255)
    # bottom-left blue
    for x in (0, 1):
        for y in (2, 3):
            assert out.getpixel((x, y)) == (0, 0, 255, 255)
    # bottom-right yellow
    for x in (2, 3):
        for y in (2, 3):
            assert out.getpixel((x, y)) == (255, 255, 0, 255)


@pytest.mark.parametrize("bad_scale", [0, -1, 4, 100])
def test_upscale_rejects_invalid_scale(bad_scale: int):
    img = Image.new("RGBA", (4, 4))
    with pytest.raises(ValueError):
        upscale_nearest(img, bad_scale)
