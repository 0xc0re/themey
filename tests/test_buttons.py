"""Unit tests for themey.analyze.buttons — three-tier button classification cascade."""
from themey.analyze.buttons import bin_left_right, classify_button

# ---------------------------------------------------------------------------
# Tier-1 aclass tests
# ---------------------------------------------------------------------------


def test_aclass_close_maps_X() -> None:
    assert classify_button(aclass="ACTION_CLOSE", iclass="BUTTON_FOO") == ("X", "aclass")


def test_aclass_kill_maps_X() -> None:
    assert classify_button("ACTION_KILL", "anything") == ("X", "aclass")


def test_aclass_max_maps_A() -> None:
    assert classify_button("ACTION_MAX", "anything") == ("A", "aclass")


def test_aclass_iconify_maps_I() -> None:
    assert classify_button("ACTION_ICONIFY", "anything") == ("I", "aclass")


def test_aclass_shade_maps_L() -> None:
    assert classify_button("ACTION_SHADE", "anything") == ("L", "aclass")


def test_aclass_stick_maps_S() -> None:
    assert classify_button("ACTION_STICK", "anything") == ("S", "aclass")


# ---------------------------------------------------------------------------
# Drop tests
# ---------------------------------------------------------------------------


def test_aclass_resize_drops() -> None:
    assert classify_button("ACTION_RESIZE", "ANY") == (None, "drop")


def test_aclass_resize_h_drops() -> None:
    assert classify_button("ACTION_RESIZE_H", "ANY") == (None, "drop")


def test_aclass_resize_v_drops() -> None:
    assert classify_button("ACTION_RESIZE_V", "ANY") == (None, "drop")


def test_aclass_move_drops() -> None:
    assert classify_button("ACTION_MOVE", "TITLE_BAR_HORIZONTAL") == (None, "drop")


# ---------------------------------------------------------------------------
# Tier-2 iclass pattern tests (aclass=None)
# ---------------------------------------------------------------------------


def test_iclass_button_close() -> None:
    assert classify_button(None, "BUTTON_CLOSE") == ("X", "iclass")


def test_iclass_button_maximize() -> None:
    assert classify_button(None, "BUTTON_MAXIMIZE") == ("A", "iclass")


def test_iclass_button_max() -> None:
    assert classify_button(None, "BUTTON_MAX") == ("A", "iclass")


def test_iclass_button_iconify() -> None:
    assert classify_button(None, "BUTTON_ICONIFY") == ("I", "iclass")


def test_iclass_button_minimize() -> None:
    assert classify_button(None, "BUTTON_MINIMIZE") == ("I", "iclass")


def test_iclass_button_kill() -> None:
    assert classify_button(None, "BUTTON_KILL") == ("X", "iclass")


def test_iclass_case_insensitive() -> None:
    """Pattern match must be case-insensitive (match against iclass.upper())."""
    assert classify_button(None, "button_close") == ("X", "iclass")


# ---------------------------------------------------------------------------
# Tier-3 fallback tests (no geometry)
# ---------------------------------------------------------------------------


def test_unknown_aclass_unknown_iclass_returns_spatial() -> None:
    assert classify_button(None, "WEIRD_THING") == (None, "spatial")


def test_aclass_takes_precedence_over_iclass() -> None:
    """aclass beats iclass even when they disagree."""
    assert classify_button("ACTION_CLOSE", "BUTTON_MAXIMIZE") == ("X", "aclass")


# ---------------------------------------------------------------------------
# Tier-3 fallback tests (with geometry — spatial center-of-mass)
# ---------------------------------------------------------------------------


def test_spatial_left_third_is_M() -> None:
    """x_center=200 is in left third of [150, 750], assigns menu 'M'."""
    result = classify_button(None, "WEIRD", x_center=200, titlebar_left=150, titlebar_right=750)
    assert result == ("M", "spatial")


def test_spatial_right_third_is_X() -> None:
    """x_center=700 is in right third of [150, 750], assigns close 'X'."""
    result = classify_button(None, "WEIRD", x_center=700, titlebar_left=150, titlebar_right=750)
    assert result == ("X", "spatial")


def test_spatial_middle_third_drops() -> None:
    """x_center=450 is in middle third of [150, 750], ambiguous — returns (None, 'spatial')."""
    result = classify_button(None, "WEIRD", x_center=450, titlebar_left=150, titlebar_right=750)
    assert result == (None, "spatial")


def test_spatial_ignored_when_aclass_matches() -> None:
    """Geometry kwargs ignored when tier-1 aclass matches."""
    result = classify_button(
        "ACTION_CLOSE", "BUTTON_MAX", x_center=10, titlebar_left=100, titlebar_right=700
    )
    assert result == ("X", "aclass")


def test_spatial_ignored_when_iclass_matches() -> None:
    """Geometry kwargs ignored when tier-2 iclass pattern matches."""
    result = classify_button(
        None, "BUTTON_MAXIMIZE", x_center=10, titlebar_left=100, titlebar_right=700
    )
    assert result == ("A", "iclass")


# ---------------------------------------------------------------------------
# Spatial binner tests
# ---------------------------------------------------------------------------


def test_bin_aliens_canary() -> None:
    """Aliens A1 assumption: kill@11, max@118, iconify@140 all left of titlebar [153, 773].

    Produces LeftButtons='XAI', RightButtons='', no overlap.
    """
    buttons = [("X", 11), ("A", 118), ("I", 140)]
    result = bin_left_right(buttons, titlebar_min_x=153, titlebar_max_x=773)
    assert result == ("XAI", "", [])


def test_bin_split_left_right() -> None:
    """One button left, one right, none overlapping."""
    buttons = [("M", 10), ("X", 790)]
    result = bin_left_right(buttons, titlebar_min_x=50, titlebar_max_x=750)
    assert result == ("M", "X", [])


def test_bin_overlap_dropped() -> None:
    """Button whose x_center is inside [titlebar_min, titlebar_max] goes to overlap list."""
    buttons = [("X", 400)]
    result = bin_left_right(buttons, titlebar_min_x=200, titlebar_max_x=600)
    assert result == ("", "", [("X", 400)])


def test_bin_left_sorted_ascending() -> None:
    """Left buttons are sorted ascending by x_center regardless of input order."""
    buttons = [("I", 140), ("A", 118), ("X", 11)]  # out of spatial order
    result = bin_left_right(buttons, titlebar_min_x=200, titlebar_max_x=800)
    assert result == ("XAI", "", [])
