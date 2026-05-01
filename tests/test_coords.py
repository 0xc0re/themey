"""Unit tests for themey.analyze.coords — E16 coordinate resolver."""
from themey.analyze.coords import REFERENCE_WINDOW_WIDTH, resolve


def test_resolve_pure_percentage() -> None:
    """50% of 1000 = 500."""
    assert resolve(percentage=512, absolute=0, window_dim=1000) == 500


def test_resolve_pure_absolute() -> None:
    """Pure absolute offset (pct=0) returns absolute unchanged."""
    assert resolve(percentage=0, absolute=140, window_dim=800) == 140


def test_resolve_full_percentage() -> None:
    """100% (pct=1024) of 800 = 800."""
    assert resolve(percentage=1024, absolute=0, window_dim=800) == 800


def test_resolve_right_anchored_negative_offset() -> None:
    """Aliens TITLE_BAR_HORIZONTAL right edge: pct=1024, abs=-27 at width 800 = 773."""
    assert resolve(percentage=1024, absolute=-27, window_dim=800) == 773


def test_resolve_negative_offset_with_zero_pct() -> None:
    """Negative absolute with pct=0 yields a negative result — never abs() the value."""
    assert resolve(percentage=0, absolute=-5, window_dim=800) == -5


def test_resolve_does_not_call_abs() -> None:
    """Verify that negative absolute is preserved as-is (not abs()d).

    If abs() were called: resolve(0, -100, 200) would return 100 instead of -100.
    """
    # With abs(): resolve(0, -100, 200) would be 100 (wrong)
    assert resolve(percentage=0, absolute=-100, window_dim=200) == -100
    # Another check: resolve(1024, -100, 200) = 200 - 100 = 100 (correct either way)
    # But: resolve(0, -100, 200) == -100 proves abs() is NOT called
    assert resolve(percentage=1024, absolute=-100, window_dim=200) == 100


def test_reference_window_width_is_800() -> None:
    """REFERENCE_WINDOW_WIDTH must be exactly 800 (Aliens canary constant)."""
    assert REFERENCE_WINDOW_WIDTH == 800
