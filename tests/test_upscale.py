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


# ---------------------------------------------------------------------------
# upscale_part — the QML backend's part-art entry point (fractional +
# quality aware; targets scale_px dims so BorderImage insets match).

def test_upscale_part_nearest_int_matches_upscale_nearest():
    from themey.images.upscale import upscale_part

    img = _make_2x2_corners()
    assert upscale_part(img, 2, "nearest").tobytes() == upscale_nearest(img, 2).tobytes()


def test_upscale_part_nearest_fractional_dims_follow_scale_px():
    from themey.generate.qmldeco.resolver import scale_px
    from themey.images.upscale import upscale_part

    img = Image.new("RGBA", (13, 30))
    out = upscale_part(img, 1.5, "nearest")
    assert out.size == (scale_px(13, 1.5), scale_px(30, 1.5)) == (20, 45)


def test_upscale_part_quality_int_uses_hqx():
    from themey.images.hqx import hqx
    from themey.images.upscale import upscale_part

    img = _make_2x2_corners()
    assert upscale_part(img, 2, "quality").tobytes() == hqx(img, 2).tobytes()
    assert upscale_part(img, 3, "quality").tobytes() == hqx(img, 3).tobytes()


def test_upscale_part_quality_scale_1_is_identity():
    from themey.images.upscale import upscale_part

    img = _make_2x2_corners()
    out = upscale_part(img, 1, "quality")
    assert out.tobytes() == img.tobytes()


def test_upscale_part_quality_fractional_dims_follow_scale_px():
    from themey.generate.qmldeco.resolver import scale_px
    from themey.images.upscale import upscale_part

    img = Image.new("RGBA", (13, 30), (10, 20, 30, 255))
    out = upscale_part(img, 1.5, "quality")
    assert out.size == (scale_px(13, 1.5), scale_px(30, 1.5))


def test_upscale_part_nearest_half_scale_dims_follow_scale_px():
    from themey.generate.qmldeco.resolver import scale_px
    from themey.images.upscale import upscale_part

    img = Image.new("RGBA", (13, 30))
    out = upscale_part(img, 0.5, "nearest")
    assert out.size == (
        max(1, scale_px(13, 0.5)), max(1, scale_px(30, 0.5))
    ) == (7, 15)
    # A 1-px source never collapses to zero.
    assert upscale_part(Image.new("RGBA", (1, 1)), 0.5, "nearest").size == (1, 1)


def test_upscale_part_quality_sub_one_goes_hqx2_then_lanczos():
    """hqx has no 1x, so a sub-1 quality scale upsamples via hqx2 first,
    then LANCZOS-downsamples to the exact scale_px target."""
    from themey.generate.qmldeco.resolver import scale_px
    from themey.images.hqx import hqx
    from themey.images.upscale import upscale_part

    img = _make_2x2_corners()
    for scale in (0.75, 0.5):
        target = (
            max(1, scale_px(img.width, scale)),
            max(1, scale_px(img.height, scale)),
        )
        expected = hqx(img, 2).resize(target, resample=Image.Resampling.LANCZOS)
        out = upscale_part(img, scale, "quality")
        assert out.size == target
        assert out.tobytes() == expected.tobytes()


def test_upscale_part_rejects_unknown_mode():
    from themey.images.upscale import upscale_part

    with pytest.raises(ValueError, match="mode"):
        upscale_part(Image.new("RGBA", (2, 2)), 2, "bicubic")
