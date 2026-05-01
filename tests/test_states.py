"""Unit tests for themey.analyze.states — E16-to-Aurorae image-state collapse."""
from pathlib import Path

from themey.analyze.states import (
    BUTTON_STATE_MAP,
    DECORATION_STATE_MAP,
    DROPPED_STATES,
    collapse_image_states,
)

# ---------------------------------------------------------------------------
# Constant tests
# ---------------------------------------------------------------------------


def test_decoration_active_chain() -> None:
    assert DECORATION_STATE_MAP["decoration-active"] == ["__NORMAL_ACTIVE", "__NORMAL"]


def test_decoration_inactive_chain() -> None:
    """Exactly one element; must never fall back to active."""
    assert DECORATION_STATE_MAP["decoration-inactive"] == ["__NORMAL"]


def test_button_hover_chain() -> None:
    assert BUTTON_STATE_MAP["button-hover"] == ["__HILITED_ACTIVE", "__HILITED"]


def test_button_pressed_chain() -> None:
    assert BUTTON_STATE_MAP["button-pressed"] == ["__CLICKED_ACTIVE", "__CLICKED"]


def test_dropped_states_includes_sticky() -> None:
    assert "__NORMAL_STICKY" in DROPPED_STATES
    assert "__NORMAL_ACTIVE_STICKY" in DROPPED_STATES


def test_dropped_states_includes_disabled() -> None:
    assert "__DISABLED" in DROPPED_STATES


# ---------------------------------------------------------------------------
# Function tests: collapse_image_states
# ---------------------------------------------------------------------------


def test_collapse_picks_first_present() -> None:
    """When both chain members present, first one wins."""
    state_dict = {
        "__NORMAL_ACTIVE": Path("a.png"),
        "__NORMAL": Path("n.png"),
    }
    notes: list[str] = []
    result = collapse_image_states(state_dict, "decoration-active", notes, "X")
    assert result == Path("a.png")
    assert notes == []  # no dropped states


def test_collapse_falls_back() -> None:
    """When first chain member absent, falls back to second."""
    state_dict = {"__NORMAL": Path("n.png")}
    notes: list[str] = []
    result = collapse_image_states(state_dict, "decoration-active", notes, "X")
    assert result == Path("n.png")


def test_collapse_returns_none_when_no_chain_member() -> None:
    """Empty state_dict -> None."""
    state_dict: dict[str, Path | None] = {}
    notes: list[str] = []
    result = collapse_image_states(state_dict, "decoration-active", notes, "X")
    assert result is None


def test_collapse_logs_dropped_states() -> None:
    """Each dropped state gets a note mentioning both state name and context_label."""
    state_dict = {
        "__NORMAL": Path("n.png"),
        "__NORMAL_STICKY": Path("ns.png"),
        "__DISABLED": Path("d.png"),
    }
    notes: list[str] = []
    collapse_image_states(state_dict, "decoration-active", notes, "TITLE_BAR_HORIZONTAL")
    # Notes must mention both dropped states and the context label
    notes_combined = " ".join(notes)
    assert "__NORMAL_STICKY" in notes_combined
    assert "__DISABLED" in notes_combined
    assert "TITLE_BAR_HORIZONTAL" in notes_combined


def test_collapse_inactive_does_not_use_active() -> None:
    """decoration-inactive chain is ['__NORMAL'] only; never falls back to __NORMAL_ACTIVE."""
    state_dict = {"__NORMAL_ACTIVE": Path("a.png")}  # only active, no normal
    notes: list[str] = []
    result = collapse_image_states(state_dict, "decoration-inactive", notes, "X")
    assert result is None
