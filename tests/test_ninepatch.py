"""Tests for src/themey/images/ninepatch.py."""
import pytest
from PIL import Image

from themey.images.ninepatch import NinePatchRegions, slice_9patch


def _make_gradient_image(width: int, height: int) -> Image.Image:
    """Build an image where each pixel color encodes its (x, y) coordinates.

    Pixel at (x, y) has RGBA = (x, y, 0, 255).
    Allows verifying which source pixel ended up in each cropped region.
    """
    img = Image.new("RGBA", (width, height))
    for y in range(height):
        for x in range(width):
            img.putpixel((x, y), (x, y, 0, 255))
    return img


def test_slice_9patch_dimensions():
    img = Image.new("RGBA", (100, 100), (128, 128, 128, 255))
    r = slice_9patch(img, left=10, right=10, top=20, bottom=20)

    assert isinstance(r, NinePatchRegions)
    assert r.topleft.size == (10, 20)
    assert r.top.size == (80, 20)  # width = 100 - 10 - 10; height = top = 20
    assert r.topright.size == (10, 20)
    assert r.left.size == (10, 60)  # height = 100 - 20 - 20 = 60
    assert r.center.size == (80, 60)
    assert r.right.size == (10, 60)
    assert r.bottomleft.size == (10, 20)
    assert r.bottom.size == (80, 20)
    assert r.bottomright.size == (10, 20)


def test_slice_9patch_pixel_content_corners():
    # 10x10 image; pixel (x, y) is (x, y, 0, 255)
    img = _make_gradient_image(10, 10)
    r = slice_9patch(img, left=2, right=2, top=2, bottom=2)

    # Topleft is 2x2; top-left pixel of source is (0, 0) → (0, 0, 0, 255)
    assert r.topleft.size == (2, 2)
    assert r.topleft.getpixel((0, 0)) == (0, 0, 0, 255)
    assert r.topleft.getpixel((1, 1)) == (1, 1, 0, 255)

    # Bottomright corner covers source pixels (8..9, 8..9)
    # bottomright.getpixel((1,1)) == source (9, 9)
    assert r.bottomright.size == (2, 2)
    assert r.bottomright.getpixel((1, 1)) == (9, 9, 0, 255)


def test_slice_9patch_zero_scaling_returns_full_center():
    img = Image.new("RGBA", (100, 100), (200, 200, 200, 255))
    r = slice_9patch(img, left=0, right=0, top=0, bottom=0)

    # All edge regions are zero-area
    assert r.topleft.size == (0, 0)
    assert r.top.size == (100, 0)
    assert r.topright.size == (0, 0)
    assert r.left.size == (0, 100)
    assert r.center.size == (100, 100)
    assert r.right.size == (0, 100)
    assert r.bottomleft.size == (0, 0)
    assert r.bottom.size == (100, 0)
    assert r.bottomright.size == (0, 0)


def test_slice_9patch_rejects_oversized_edges():
    img = Image.new("RGBA", (50, 50))
    with pytest.raises(ValueError, match="left\\+right"):
        slice_9patch(img, left=30, right=30, top=10, bottom=10)


def test_slice_9patch_rejects_oversized_top_bottom():
    img = Image.new("RGBA", (50, 50))
    with pytest.raises(ValueError, match="top\\+bottom"):
        slice_9patch(img, left=0, right=0, top=30, bottom=30)
