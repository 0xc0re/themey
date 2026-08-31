"""Structural (majority-opaque) extent measurement on RGBA images.

``themey.images.opaque`` measures how much of an image is *structurally*
opaque — consecutive rows/columns whose opaque-pixel coverage crosses the
majority threshold. e13's titlebar_2.png is opaque rows 0-30 and a shaped
transparent notch below; WIN_SIDE_LEFT is opaque only in cols 24-29. The
guarantees tested here:

- fully opaque art returns the full dimension (no-change guarantee),
- fully transparent art returns zero,
- hairline/sub-majority coverage does not count as structure,
- an inner band is found by ``structural_span`` even when it doesn't touch
  the measured side.
"""
from __future__ import annotations

from PIL import Image

from themey.images.opaque import structural_extent, structural_span


def _img(w: int, h: int) -> Image.Image:
    return Image.new("RGBA", (w, h), (0, 0, 0, 0))


def _fill(img: Image.Image, x0: int, y0: int, x1: int, y1: int, alpha: int = 255) -> None:
    for y in range(y0, y1):
        for x in range(x0, x1):
            img.putpixel((x, y), (200, 100, 50, alpha))


def test_fully_opaque_returns_full_dimension() -> None:
    img = _img(30, 20)
    _fill(img, 0, 0, 30, 20)
    assert structural_extent(img, "top") == 20
    assert structural_extent(img, "bottom") == 20
    assert structural_extent(img, "left") == 30
    assert structural_extent(img, "right") == 30
    assert structural_span(img, "x") == (0, 30)
    assert structural_span(img, "y") == (0, 20)


def test_fully_transparent_returns_zero() -> None:
    img = _img(16, 16)
    assert structural_extent(img, "top") == 0
    assert structural_extent(img, "left") == 0
    assert structural_span(img, "x") == (0, 0)
    assert structural_span(img, "y") == (0, 0)


def test_half_opaque_rows_measured_from_each_side() -> None:
    """Opaque rows 0-9 of a 20-tall image: top extent 10, bottom extent 0."""
    img = _img(12, 20)
    _fill(img, 0, 0, 12, 10)
    assert structural_extent(img, "top") == 10
    assert structural_extent(img, "bottom") == 0
    assert structural_span(img, "y") == (0, 10)


def test_hairline_coverage_is_not_structure() -> None:
    """A 10%-filled row (below the 50% coverage bar) must not count."""
    img = _img(20, 8)
    _fill(img, 0, 0, 20, 4)          # rows 0-3 fully opaque
    _fill(img, 0, 4, 2, 8)           # rows 4-7 only 2/20 = 10% covered
    assert structural_extent(img, "top") == 4
    assert structural_span(img, "y") == (0, 4)


def test_low_alpha_pixels_do_not_count() -> None:
    """Pixels below the alpha threshold (~32) are treated as transparent."""
    img = _img(10, 10)
    _fill(img, 0, 0, 10, 10, alpha=8)
    assert structural_extent(img, "top") == 0
    assert structural_span(img, "y") == (0, 0)


def test_inner_edge_band_found_by_span() -> None:
    """WIN_SIDE_LEFT shape: opaque only in an inner column band (24-29 of 30).

    ``structural_span(img, "x")`` must find the band even though it touches
    neither the left nor the right measurement origin.
    """
    img = _img(30, 60)
    _fill(img, 24, 0, 30, 60)
    # a sub-majority wedge over the rest must not extend the span
    _fill(img, 0, 0, 10, 20)  # cols 0-9 covered 20/60 = 33% < 50%
    assert structural_span(img, "x") == (24, 30)
    assert structural_extent(img, "left") == 0
    assert structural_extent(img, "right") == 6


def test_span_is_union_of_structural_runs() -> None:
    """Disjoint majority-opaque runs measure as one bounding span.

    Shaped side art often pairs an outer 1px frame line with an inner band;
    taking only the longest run would crop the outer line out of the border
    entirely (and collapse hollow outline frames to 1px — see below).
    """
    img = _img(30, 10)
    _fill(img, 0, 0, 4, 10)    # cols 0-3
    _fill(img, 10, 0, 22, 10)  # cols 10-21
    assert structural_span(img, "x") == (0, 22)


def test_hollow_outline_frame_measures_full_extent() -> None:
    """A bevel-outline titlebar (1px opaque frame, transparent interior)
    must measure its full height, not a single row — collapsing it made
    TitleHeight hit the 2*s floor and squashed every button to 4px tall.
    """
    img = _img(40, 20)
    _fill(img, 0, 0, 40, 1)      # top edge line
    _fill(img, 0, 19, 40, 20)    # bottom edge line
    _fill(img, 0, 0, 1, 20)      # left edge (sub-majority per-row: ignored)
    assert structural_span(img, "y") == (0, 20)
