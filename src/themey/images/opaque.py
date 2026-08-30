"""Structural (majority-opaque) extent measurement for shaped E16 art.

E16 themes use shaped (``__CHANGES_SHAPE``) images whose *declared* rect is
much larger than the visible art: e13's titlebar_2.png is 46 rows tall but
opaque only in rows 0-30 (rows below are a shaped transparent notch), and its
WIN_SIDE_LEFT is a 30-col image opaque only in cols 24-29. Geometry derived
from declared rects (TitleHeight, BorderLeft) then over-reserves by the
transparent remainder. This module measures where the *structure* actually is.

A row/column counts as structural when the fraction of its pixels with
``alpha >= ALPHA_THRESHOLD`` is at least ``COVERAGE_THRESHOLD``:

- ``ALPHA_THRESHOLD = 32``: matches the >32 opacity test used elsewhere in
  the pipeline (aurorae_rc bg sampling, visual snapshot opacity counts);
  antialiased fringe pixels stay ignored.
- ``COVERAGE_THRESHOLD = 0.5``: majority vote. Measured margins on the
  corpus canaries are comfortable — e13 title rows 0-30 sit at ~0.95
  coverage vs ~0.47 in the notch; WIN_SIDE_LEFT's real edge is 1.0 vs a
  <=0.46 decorative wedge.

Guarantee: fully opaque art measures the full dimension, so themes without
shaped imagery are byte-for-byte unaffected by callers that trim to these
measurements.
"""
from __future__ import annotations

from PIL import Image

ALPHA_THRESHOLD: int = 32
COVERAGE_THRESHOLD: float = 0.5


def _line_coverage(img: Image.Image, axis: str) -> list[float]:
    """Per-line opaque coverage. ``axis="x"`` → columns, ``axis="y"`` → rows."""
    rgba = img if img.mode == "RGBA" else img.convert("RGBA")
    alpha = rgba.getchannel("A")
    w, h = alpha.size
    data = alpha.tobytes()
    if axis == "x":
        counts = [0] * w
        for y in range(h):
            row = data[y * w : (y + 1) * w]
            for x in range(w):
                if row[x] >= ALPHA_THRESHOLD:
                    counts[x] += 1
        return [c / h for c in counts] if h else []
    counts = [0] * h
    for y in range(h):
        row = data[y * w : (y + 1) * w]
        counts[y] = sum(1 for a in row if a >= ALPHA_THRESHOLD)
    return [c / w for c in counts] if w else []


def _structural(coverage: list[float]) -> list[bool]:
    return [c >= COVERAGE_THRESHOLD for c in coverage]


def structural_extent(img: Image.Image, side: str) -> int:
    """Consecutive structural rows/cols starting at *side*.

    ``side`` is one of ``"left"``, ``"right"``, ``"top"``, ``"bottom"``.
    Returns the run length in pixels; the full dimension for fully opaque
    art, 0 when the first line at that side is already sub-majority.
    """
    axis = "x" if side in ("left", "right") else "y"
    lines = _structural(_line_coverage(img, axis))
    if side in ("right", "bottom"):
        lines = lines[::-1]
    n = 0
    for ok in lines:
        if not ok:
            break
        n += 1
    return n


def structural_span(img: Image.Image, axis: str) -> tuple[int, int]:
    """Longest consecutive structural run along *axis* (``"x"`` or ``"y"``).

    Returns a half-open ``(start, end)`` pixel range — ``(0, dim)`` for fully
    opaque art, ``(0, 0)`` when no line is structural. Finds inner bands that
    touch neither edge (WIN_SIDE_LEFT's cols 24-29).
    """
    lines = _structural(_line_coverage(img, axis))
    best = (0, 0)
    start: int | None = None
    for i, ok in enumerate(lines):
        if ok and start is None:
            start = i
        elif not ok and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    if start is not None and len(lines) - start > best[1] - best[0]:
        best = (start, len(lines))
    return best
