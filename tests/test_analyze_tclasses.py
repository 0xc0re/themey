"""Unit tests for themey.analyze.tclasses — AST __TCLASS block extraction."""
from __future__ import annotations

from themey.analyze.tclasses import FG_COLOR_KEYS, build_tclasses
from themey.etheme.ast import Block, KeyVal

# ---------------------------------------------------------------------------
# Helpers: synthetic AST factories
# ---------------------------------------------------------------------------


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _tclass_block(name: str, *children: KeyVal) -> Block:
    """Build a synthetic __TCLASS block with head_values=(name,)."""
    return Block(keyword="__TCLASS", head_values=(name,), children=children, line=0)


# ---------------------------------------------------------------------------
# FG_COLOR_KEYS constant test
# ---------------------------------------------------------------------------


def test_tclass_FG_COLOR_KEYS_constant() -> None:
    """FG_COLOR_KEYS tuple order must match E16's primary misspelling first."""
    assert FG_COLOR_KEYS == ("__FORGROUND_COLOR", "__FOREGROUND_COLOR", "__COLOR")


# ---------------------------------------------------------------------------
# Misspelled FORGROUND tests (primary E16 form)
# ---------------------------------------------------------------------------


def test_tclass_misspelled_FORGROUND() -> None:
    """E16's misspelling __FORGROUND_COLOR is the primary form and must be honored."""
    block = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"),
        _kv("__FORGROUND_COLOR", 200, 200, 150),
        _kv("__NORMAL_ACTIVE"),
        _kv("__FORGROUND_COLOR", 255, 255, 200),
    )
    tclasses = build_tclasses([block])
    tc = tclasses["TEXT1"]
    assert tc.fg_normal == (200, 200, 150)
    assert tc.fg_active == (255, 255, 200)


# ---------------------------------------------------------------------------
# Correct spelling and alias tests
# ---------------------------------------------------------------------------


def test_tclass_correct_FOREGROUND_spelling() -> None:
    """__FOREGROUND_COLOR (correct spelling) is also honored as a fallback."""
    block = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"),
        _kv("__FOREGROUND_COLOR", 200, 200, 150),
        _kv("__NORMAL_ACTIVE"),
        _kv("__FOREGROUND_COLOR", 255, 255, 200),
    )
    tclasses = build_tclasses([block])
    tc = tclasses["TEXT1"]
    assert tc.fg_normal == (200, 200, 150)
    assert tc.fg_active == (255, 255, 200)


def test_tclass_short_alias_COLOR() -> None:
    """__COLOR is honored as an alternate alias for the foreground color."""
    block = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"),
        _kv("__COLOR", 200, 200, 150),
        _kv("__NORMAL_ACTIVE"),
        _kv("__COLOR", 255, 255, 200),
    )
    tclasses = build_tclasses([block])
    tc = tclasses["TEXT1"]
    assert tc.fg_normal == (200, 200, 150)
    assert tc.fg_active == (255, 255, 200)


# ---------------------------------------------------------------------------
# Missing-state tests
# ---------------------------------------------------------------------------


def test_tclass_missing_active_returns_none_for_active() -> None:
    """When only __NORMAL state is declared, fg_active is None."""
    block = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"),
        _kv("__FORGROUND_COLOR", 200, 200, 150),
        # no __NORMAL_ACTIVE block
    )
    tclasses = build_tclasses([block])
    tc = tclasses["TEXT1"]
    assert tc.fg_normal == (200, 200, 150)
    assert tc.fg_active is None


def test_tclass_no_states_both_none() -> None:
    """Tclass with no state declarations has fg_normal and fg_active as None."""
    block = _tclass_block("TEXT1")
    tclasses = build_tclasses([block])
    tc = tclasses["TEXT1"]
    assert tc.name == "TEXT1"
    assert tc.fg_normal is None
    assert tc.fg_active is None


# ---------------------------------------------------------------------------
# Multi-tclass tests
# ---------------------------------------------------------------------------


def test_tclass_multiple_blocks() -> None:
    """Multiple __TCLASS blocks produce separate dict entries."""
    block1 = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"),
        _kv("__FORGROUND_COLOR", 200, 200, 150),
    )
    block2 = _tclass_block(
        "TEXT2",
        _kv("__NORMAL"),
        _kv("__FORGROUND_COLOR", 100, 100, 100),
    )
    tclasses = build_tclasses([block1, block2])
    assert "TEXT1" in tclasses
    assert "TEXT2" in tclasses
    assert tclasses["TEXT1"].fg_normal == (200, 200, 150)
    assert tclasses["TEXT2"].fg_normal == (100, 100, 100)


def test_tclass_state_context_resets_between_blocks() -> None:
    """State context from one tclass block does not bleed into the next."""
    block1 = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"),
        _kv("__FORGROUND_COLOR", 10, 20, 30),
    )
    block2 = _tclass_block(
        "TEXT2",
        # No state marker — color without context should be ignored
        _kv("__FORGROUND_COLOR", 50, 60, 70),
    )
    tclasses = build_tclasses([block1, block2])
    # TEXT2 had a color but no state context — fg_normal should be None
    assert tclasses["TEXT2"].fg_normal is None


# ---------------------------------------------------------------------------
# Step 8: __JUSTIFICATION, __DRAWING_EFFECT, __EFFECT_COLOR
# ---------------------------------------------------------------------------


def test_tclass_justification_numeric_left() -> None:
    """E16 __JUSTIFICATION 0 = left → Aurorae TitleAlignment 'Left'."""
    block = _tclass_block("T", _kv("__JUSTIFICATION", 0))
    assert build_tclasses([block])["T"].alignment == "Left"


def test_tclass_justification_numeric_center() -> None:
    """E16 __JUSTIFICATION 512 = center → Aurorae TitleAlignment 'Center'."""
    block = _tclass_block("T", _kv("__JUSTIFICATION", 512))
    assert build_tclasses([block])["T"].alignment == "Center"


def test_tclass_justification_numeric_right() -> None:
    block = _tclass_block("T", _kv("__JUSTIFICATION", 1024))
    assert build_tclasses([block])["T"].alignment == "Right"


def test_tclass_justification_symbolic_tokens() -> None:
    """Some themes use literal tokens (__LEFT etc.) instead of integers."""
    for token, expected in [("__LEFT", "Left"), ("__CENTER", "Center"), ("__RIGHT", "Right")]:
        block = _tclass_block("T", _kv("__JUSTIFICATION", token))
        assert build_tclasses([block])["T"].alignment == expected, token


def test_tclass_drawing_effect_shadow_captured() -> None:
    block = _tclass_block(
        "T",
        _kv("__DRAWING_EFFECT", "__EFFECT_SHADOW"),
    )
    assert build_tclasses([block])["T"].effect == "__EFFECT_SHADOW"


def test_tclass_effect_color_captured() -> None:
    block = _tclass_block(
        "T",
        _kv("__EFFECT_COLOR", 30, 30, 30),
    )
    assert build_tclasses([block])["T"].effect_color == (30, 30, 30)


def test_tclass_defaults_to_none_when_absent() -> None:
    """A tclass with no __JUSTIFICATION / __DRAWING_EFFECT / __EFFECT_COLOR
    leaves all three fields as None so the writer can fall back to its
    defaults."""
    block = _tclass_block("T", _kv("__NORMAL"), _kv("__FORGROUND_COLOR", 1, 2, 3))
    tc = build_tclasses([block])["T"]
    assert tc.alignment is None
    assert tc.effect is None
    assert tc.effect_color is None
