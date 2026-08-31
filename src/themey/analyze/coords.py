"""E16 hybrid coord resolution: final = (window_dim * pct/1024) + absolute.

`pct` is Q10 fixed point (1024 == 100%). `absolute` is signed pixel offset
that may be negative (e.g. pct=1024 + abs=-27 means '27 px from right edge').
NEVER negate or take the absolute value of a coordinate.

Aliens default.cfg TITLE_BAR_HORIZONTAL has __BOTTOMRIGHT_X_PERCENTAGE 1024
+ __BOTTOMRIGHT_X_ABSOLUTE -27 — at width 800 this resolves to 773.
"""
from __future__ import annotations


def resolve(percentage: int, absolute: int, window_dim: int) -> int:
    """Resolve an E16 coord to a concrete pixel value at a given window dim."""
    return int(window_dim * percentage / 1024) + absolute


# Reference dims for spatial-fallback button binning.
# Aliens default border verified to bin correctly at 800px.
REFERENCE_WINDOW_WIDTH: int = 800
REFERENCE_WINDOW_HEIGHT: int = 600
