"""Tests for src/themey/images/upscale.py."""
import pytest
from PIL import Image

from themey import external
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


# --------------------------------------------------------------------- #
# waifu2x mode
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("scale", "expected"),
    [
        # themey's whole range: everything up to 2.0 fits in one 2x pass,
        # anything above it needs 4x and comes back down with LANCZOS.
        (0.5, 2),
        (0.75, 2),
        (1.5, 2),
        (2, 2),
        (2.5, 4),
        (3, 4),
        # Past themey's range the table stays total rather than raising.
        (4, 4),
        (4.5, 8),
        (8, 8),
        (17, 32),
        (64, 32),
    ],
)
def test_waifu2x_factor_picks_the_smallest_supported_power_of_two(scale, expected):
    from themey.images.upscale import _waifu2x_factor

    assert _waifu2x_factor(scale) == expected


def test_waifu2x_factor_never_returns_an_unsupported_value():
    """waifu2x rejects -s 3 outright ("invalid scale argument"), so the
    picker must never produce it."""
    from themey.images.upscale import _WAIFU2X_FACTORS, _waifu2x_factor

    for tenth in range(5, 31):
        assert _waifu2x_factor(tenth / 10) in _WAIFU2X_FACTORS


def test_upscale_part_waifu2x_scale_1_is_identity_without_the_binary(monkeypatch):
    """Scale 1 short-circuits before the subprocess, as the quality path
    does — nothing to upscale, so no reason to need the tool."""
    from themey.images import upscale as upscale_mod

    def _boom(*args, **kwargs):
        raise AssertionError("waifu2x must not be invoked at scale 1")

    monkeypatch.setattr(upscale_mod, "waifu2x", _boom)
    img = Image.new("RGBA", (8, 8), (1, 2, 3, 255))
    out = upscale_mod.upscale_part(img, 1, "waifu2x")
    assert out.size == (8, 8)
    assert out.tobytes() == img.convert("RGBA").tobytes()


def test_upscale_part_waifu2x_calls_the_scaler_with_the_picked_factor(monkeypatch):
    from themey.images import upscale as upscale_mod

    seen: list[int] = []

    def _fake(img, factor):
        seen.append(factor)
        return Image.new("RGBA", (img.width * factor, img.height * factor))

    monkeypatch.setattr(upscale_mod, "waifu2x", _fake)
    upscale_mod.upscale_part(Image.new("RGBA", (10, 10)), 3, "waifu2x")
    assert seen == [4]


def test_upscale_part_waifu2x_dims_follow_scale_px(monkeypatch):
    """The 4x overshoot must land back on the SAME scale_px target every
    other mode produces, or BorderImage insets stop matching the art."""
    from themey.generate.qmldeco.resolver import scale_px
    from themey.images import upscale as upscale_mod

    monkeypatch.setattr(
        upscale_mod, "waifu2x",
        lambda img, factor: Image.new(
            "RGBA", (img.width * factor, img.height * factor)
        ),
    )
    img = Image.new("RGBA", (13, 7))
    for scale in (1.5, 2, 2.5, 3):
        out = upscale_mod.upscale_part(img, scale, "waifu2x")
        assert out.size == (scale_px(13, scale), scale_px(7, scale))


def test_upscale_part_waifu2x_skips_the_resize_when_the_factor_is_exact(monkeypatch):
    from themey.images import upscale as upscale_mod

    exact = Image.new("RGBA", (16, 16), (9, 9, 9, 255))
    monkeypatch.setattr(upscale_mod, "waifu2x", lambda img, factor: exact)
    out = upscale_mod.upscale_part(Image.new("RGBA", (8, 8)), 2, "waifu2x")
    assert out is exact


def test_upscale_part_waifu2x_propagates_the_missing_binary_error(monkeypatch):
    """upscale_part stays pure and raises: the fallback decision belongs
    to pipeline.convert, which has theme.notes to record it in."""
    from themey.external import WAIFU2X_MODELS_ENV, Waifu2xError
    from themey.images.upscale import upscale_part

    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)
    with pytest.raises(Waifu2xError):
        upscale_part(Image.new("RGBA", (4, 4)), 2, "waifu2x")


def test_upscale_part_declared_mode_without_a_branch_raises(monkeypatch):
    """The dispatch must not fall through. Before 2026-09-02 every mode
    past the `nearest` early-returns silently rendered as hqx, so a new
    mode could ship doing something other than what it said."""
    from themey.images import upscale as upscale_mod

    monkeypatch.setattr(
        upscale_mod, "UPSCALE_MODES", ("nearest", "quality", "waifu2x", "xbrz")
    )
    with pytest.raises(ValueError, match="declared but not implemented"):
        upscale_mod.upscale_part(Image.new("RGBA", (4, 4)), 2, "xbrz")


def test_every_declared_upscale_mode_is_reachable():
    """Each entry in UPSCALE_MODES produces art rather than the
    not-implemented error — the same guard from the other side."""
    from themey.images import upscale as upscale_mod

    img = Image.new("RGBA", (4, 4), (5, 6, 7, 255))
    for mode in upscale_mod.UPSCALE_MODES:
        # scale 1 is the one path no mode delegates to an external tool.
        assert upscale_mod.upscale_part(img, 1, mode).size == (4, 4)


# The binary alone is not enough: upstream ships the models as flat
# siblings and most installs copy only the executable, so gate on both
# (external.waifu2x_available), the way needs_xcursorgen gates on one.
needs_waifu2x = pytest.mark.skipif(
    not external.waifu2x_available(),
    reason="waifu2x-ncnn-vulkan or its model weights not installed",
)


def _art() -> Image.Image:
    """A small hard-edged sprite, the shape of real E16 border art."""
    img = Image.new("RGBA", (12, 9), (0, 0, 0, 255))
    for x in range(12):
        for y in range(9):
            if (x + y) % 3 == 0:
                img.putpixel((x, y), (220, 210, 180, 255))
            elif x < 2 or y < 2:
                img.putpixel((x, y), (120, 120, 140, 255))
    return img


@needs_waifu2x
@pytest.mark.parametrize("scale", [2, 3, 1.5])
def test_waifu2x_output_dims_are_exactly_scale_px(scale):
    from themey.generate.qmldeco.resolver import scale_px
    from themey.images.upscale import upscale_part

    img = _art()
    out = upscale_part(img, scale, "waifu2x")
    assert out.size == (scale_px(12, scale), scale_px(9, scale))
    assert out.mode == "RGBA"


@needs_waifu2x
def test_waifu2x_differs_from_both_nearest_and_hqx():
    """If it matched either, the mode would be dead weight."""
    from themey.images.upscale import upscale_part

    img = _art()
    w = upscale_part(img, 2, "waifu2x")
    n = upscale_part(img, 2, "nearest")
    q = upscale_part(img, 2, "quality")
    assert w.size == n.size == q.size
    assert w.tobytes() != n.tobytes()
    assert w.tobytes() != q.tobytes()


@needs_waifu2x
def test_waifu2x_is_deterministic_across_runs():
    """Two invocations on the same art must agree, or the snapshot tests
    and the batch survey stop being comparable between runs."""
    from themey.images.upscale import upscale_part

    img = _art()
    assert (
        upscale_part(img, 2, "waifu2x").tobytes()
        == upscale_part(img, 2, "waifu2x").tobytes()
    )
