"""Unit tests for themey.analyze.buttons — three-tier button classification cascade."""
from themey.analyze.buttons import bin_left_right, classify_button, title_part
from themey.ir import ButtonPart

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


# ---------------------------------------------------------------------------
# Sentinel fallback — when titlebar bounds are missing
# ---------------------------------------------------------------------------


def test_bin_left_right_sentinel_falls_back_to_midpoint() -> None:
    """When titlebar_max <= titlebar_min (no title bar identified), bin around
    REFERENCE_WINDOW_WIDTH/2.

    The e13 regression: titlebar bounds were left at the inversion sentinel
    (min=800, max=0), and the existing `x < min AND x > max` predicate made
    every button satisfy BOTH conditions, so each got duplicated into Left
    AND Right (e.g. LeftButtons=XILS, RightButtons=XILS). With the fallback,
    buttons in the left half of the reference window go left; right half go
    right.
    """
    # x=100 should bin left, x=700 should bin right.
    buttons = [("X", 100), ("A", 700)]
    left, right, overlap = bin_left_right(buttons, titlebar_min_x=800, titlebar_max_x=0)
    assert left == "X"
    assert right == "A"
    assert overlap == []


def test_bin_left_right_sentinel_no_duplicate_assignment() -> None:
    """A button must not appear in BOTH left and right strings.

    Reproduces the e13 LeftButtons=XILS, RightButtons=XILS bug. Each input
    button must end up in exactly one of (left, right, overlap).
    """
    buttons = [("X", 100), ("I", 150), ("L", 200), ("S", 250)]
    left, right, overlap = bin_left_right(buttons, titlebar_min_x=800, titlebar_max_x=0)
    # Total characters across both strings + overlap entries == total buttons.
    assert len(left) + len(right) + len(overlap) == len(buttons)
    # And no character appears in both.
    assert set(left).isdisjoint(set(right))


# ---------------------------------------------------------------------------
# title_part() — canonical __FLAG_TITLE identification
# ---------------------------------------------------------------------------


def _part(**kw: object) -> ButtonPart:
    """ButtonPart factory for tests with sensible coord defaults."""
    defaults: dict[str, object] = {
        "iclass_name": "FOO",
        "aclass": None,
        "tl_x_pct": 0,
        "tl_x_abs": 0,
        "tl_y_pct": 0,
        "tl_y_abs": 0,
        "br_x_pct": 0,
        "br_x_abs": 0,
        "br_y_pct": 0,
        "br_y_abs": 0,
    }
    defaults.update(kw)
    return ButtonPart(**defaults)  # type: ignore[arg-type]


def test_title_part_picks_flag_title_member() -> None:
    """title_part() returns the part whose flags include __FLAG_TITLE."""
    other = _part(iclass_name="CORNER_TL")
    title = _part(iclass_name="TITLEBAR", flags=("__FLAG_TITLE",))
    result = title_part((other, title))
    assert result is title


def test_title_part_none_when_no_flag_title() -> None:
    """Returns None when no part has __FLAG_TITLE."""
    p = _part(iclass_name="TITLE_BAR_HORIZONTAL")  # name match but no flag
    assert title_part((p,)) is None


def test_title_part_works_with_short_iclass_name() -> None:
    """e13 uses __ICLASS TITLEBAR (no underscore) — the old substring 'TITLE_BAR'
    match misses it, but canonical __FLAG_TITLE matches.
    """
    p = _part(iclass_name="TITLEBAR", flags=("__FLAG_TITLE",))
    assert title_part((p,)) is p


# ---------------------------------------------------------------------------
# Step 9: ACLASS vocabulary expansion
# ---------------------------------------------------------------------------


def test_aclass_keep_above_maps_F() -> None:
    assert classify_button("ACTION_KEEP_ABOVE", "anything") == ("F", "aclass")


def test_aclass_keep_below_maps_B() -> None:
    assert classify_button("ACTION_KEEP_BELOW", "anything") == ("B", "aclass")


def test_aclass_menu_drops() -> None:
    assert classify_button("ACTION_MENU", "anything") == (None, "drop")


def test_aclass_desktop_next_drops() -> None:
    assert classify_button("ACTION_DESKTOP_NEXT", "anything") == (None, "drop")


def test_aclass_exec_drops() -> None:
    assert classify_button("ACTION_EXEC", "anything") == (None, "drop")


def test_unknown_aclass_returns_unknown_source() -> None:
    """An ACTION_* aclass we don't speak short-circuits iclass-pattern
    fallback so build_theme can log it instead of silently using a
    questionable pattern match.
    """
    code, source = classify_button("ACTION_SOMETHING_NEW", "BUTTON_CLOSE")
    assert (code, source) == (None, "unknown_aclass")


def test_unknown_aclass_logged_in_notes(tmp_path) -> None:
    """End-to-end: an unknown ACLASS produces a notes entry mentioning it."""
    from themey.analyze.build_theme import build_theme
    from themey.etheme.ast import Block, KeyVal

    def kv(k, *v):
        return KeyVal(keyword=k, values=tuple(v), line=0)

    # Synthesize a minimal cfg: one __BORDER block with a __BORDER_PART whose
    # __ACLASS is something we don't speak.
    part = Block(
        keyword="__BORDER_PART",
        head_values=(),
        children=(
            kv("__ICLASS", "ZAP_BTN"),
            kv("__ACLASS", "ACTION_BLOOP"),
            kv("__TOPLEFT_X_PERCENTAGE", 0),
            kv("__TOPLEFT_X_ABSOLUTE", 4),
            kv("__TOPLEFT_Y_PERCENTAGE", 0),
            kv("__TOPLEFT_Y_ABSOLUTE", 4),
            kv("__BOTTOMRIGHT_X_PERCENTAGE", 0),
            kv("__BOTTOMRIGHT_X_ABSOLUTE", 20),
            kv("__BOTTOMRIGHT_Y_PERCENTAGE", 0),
            kv("__BOTTOMRIGHT_Y_ABSOLUTE", 20),
        ),
        line=0,
    )
    border = Block(
        keyword="__BORDER",
        head_values=("DEFAULT",),
        children=(
            kv("__BORDER_SIZE_LEFT", 4),
            kv("__BORDER_SIZE_RIGHT", 4),
            kv("__BORDER_SIZE_TOP", 24),
            kv("__BORDER_SIZE_BOTTOM", 4),
            part,
        ),
        line=0,
    )
    theme = build_theme(tmp_path, [border], name="X", scale=1)
    assert any(
        "ACTION_BLOOP" in n for n in theme.notes
    ), f"unknown ACLASS not logged; notes={theme.notes}"
