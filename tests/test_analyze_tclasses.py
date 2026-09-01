"""Unit tests for themey.analyze.tclasses — AST __TCLASS block extraction."""
from __future__ import annotations

import pytest

from themey.analyze.tclasses import FG_COLOR_KEYS, build_tclasses, title_tclass
from themey.etheme.ast import Block, KeyVal
from themey.ir import BorderSpec, ButtonPart, TClassSpec

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


def test_tclass_background_color_per_state_is_the_effect_color() -> None:
    """E16 paints shadow/outline in the state's ``bg_col`` (text.c
    TsTextDraw), set by ``__BACKGROUND_COLOR`` after the state keyword
    (tclass.c TEXT_BG_COL). ``__EFFECT_COLOR`` does not exist in E16."""
    block = _tclass_block(
        "T",
        _kv("__NORMAL"),
        _kv("__FORGROUND_COLOR", 1, 2, 3),
        _kv("__BACKGROUND_COLOR", 30, 31, 32),
        _kv("__NORMAL_ACTIVE"),
        _kv("__FORGROUND_COLOR", 4, 5, 6),
        _kv("__BACKGROUND_COLOR", 40, 41, 42),
    )
    tc = build_tclasses([block])["T"]
    assert tc.bg_normal == (30, 31, 32)
    assert tc.bg_active == (40, 41, 42)
    assert tc.effect_color == (30, 31, 32)


def test_tclass_background_color_first_wins_and_needs_a_state() -> None:
    block = _tclass_block(
        "T",
        _kv("__BACKGROUND_COLOR", 9, 9, 9),  # no state yet — ignored like fg
        _kv("__NORMAL_ACTIVE"),
        _kv("__BACKGROUND_COLOR", 40, 41, 42),
        _kv("__BACKGROUND_COLOR", 1, 1, 1),
    )
    tc = build_tclasses([block])["T"]
    assert tc.bg_normal is None
    assert tc.bg_active == (40, 41, 42)
    assert tc.effect_color == (40, 41, 42)  # falls through to the active color


def test_tclass_legacy_effect_color_keyword_is_ignored() -> None:
    block = _tclass_block("T", _kv("__NORMAL"), _kv("__EFFECT_COLOR", 30, 30, 30))
    tc = build_tclasses([block])["T"]
    assert tc.effect_color is None


def test_tclass_defaults_to_none_when_absent() -> None:
    """A tclass with no __JUSTIFICATION / __DRAWING_EFFECT /
    __BACKGROUND_COLOR leaves the fields as None so the writers can fall
    back to their defaults (E16's calloc'ed ``bg_col`` is black)."""
    block = _tclass_block("T", _kv("__NORMAL"), _kv("__FORGROUND_COLOR", 1, 2, 3))
    tc = build_tclasses([block])["T"]
    assert tc.alignment is None
    assert tc.effect is None
    assert tc.effect_color is None
    assert tc.effect_kind == "none"


@pytest.mark.parametrize(
    "token, kind",
    [
        ("__EFFECT_SHADOW", "shadow"),
        ("__EFFECT_OUTLINE", "outline"),
        ("__EFFECT_NONE", "none"),
        ("__EFFECT_NORMAL", "none"),
        ("__NONE", "none"),
        ("__EFFECT_NICE", "none"),  # undefined in E16 → atoi() = 0
        (1, "shadow"),  # config/definitions: __EFFECT_SHADOW 1
        (2, "outline"),  # __EFFECT_OUTLINE 2
        (0, "none"),
        ("2", "outline"),
    ],
)
def test_tclass_effect_kind(token: object, kind: str) -> None:
    block = _tclass_block("T", _kv("__NORMAL"), _kv("__DRAWING_EFFECT", token))
    assert build_tclasses([block])["T"].effect_kind == kind


# ---------------------------------------------------------------------------
# title_tclass — the title part's declared __TCLASS wins over the TEXT1
# convention (OPENSTEP declares __TCLASS TITLEBAR_TEXT and has no TEXT1)
# ---------------------------------------------------------------------------


def _title_border(tclass_name: str | None) -> BorderSpec:
    part = ButtonPart(
        iclass_name="TITLEBAR",
        aclass=None,
        tl_x_pct=0,
        tl_x_abs=0,
        tl_y_pct=0,
        tl_y_abs=0,
        br_x_pct=1024,
        br_x_abs=0,
        br_y_pct=0,
        br_y_abs=18,
        flags=("__FLAG_TITLE",),
        tclass_name=tclass_name,
    )
    return BorderSpec(
        name="DEFAULT",
        border_size_left=4,
        border_size_right=4,
        border_size_top=18,
        border_size_bottom=4,
        parts=(part,),
    )


def _spec(name: str) -> TClassSpec:
    return TClassSpec(name=name, fg_normal=(1, 1, 1), fg_active=(2, 2, 2))


def test_title_tclass_declared_name_wins() -> None:

    tclasses = {"TEXT1": _spec("TEXT1"), "TITLEBAR_TEXT": _spec("TITLEBAR_TEXT")}
    result = title_tclass(_title_border("TITLEBAR_TEXT"), tclasses)
    assert result is not None
    assert result.name == "TITLEBAR_TEXT"


def test_title_tclass_falls_back_to_text1() -> None:

    tclasses = {"TEXT1": _spec("TEXT1")}
    # No declared __TCLASS on the title part
    result = title_tclass(_title_border(None), tclasses)
    assert result is not None
    assert result.name == "TEXT1"
    # Declared name not present in tclasses -> TEXT1 fallback too
    result = title_tclass(_title_border("MISSING"), tclasses)
    assert result is not None
    assert result.name == "TEXT1"


def test_title_tclass_none_when_nothing_matches() -> None:

    assert title_tclass(_title_border("MISSING"), {}) is None


# ---------------------------------------------------------------------------
# E16 text-state groups (tclass.c TextclassPopulate), per-state effect,
# __ORIENTATION
# ---------------------------------------------------------------------------


def test_tclass_per_state_effect_and_orientation() -> None:
    """tclass.c:327-329 stores __DRAWING_EFFECT on the CURRENT TextState;
    43 corpus themes shadow only the focused title. __ORIENTATION tokens
    come from config/definitions (RIGHT 0, DOWN 1, UP 2, LEFT 3); an
    undefined token (``__UP``) is atoi 0."""
    block = _tclass_block(
        "TEXT1",
        _kv("__ORIENTATION", "__FONT_TO_UP"),
        _kv("__NORMAL", "*font-default"),
        _kv("__DRAWING_EFFECT", "__EFFECT_NONE"),
        _kv("__FORGROUND_COLOR", 1, 2, 3),
        _kv("__NORMAL_ACTIVE", "*font-default"),
        _kv("__DRAWING_EFFECT", "__EFFECT_SHADOW"),
        _kv("__FORGROUND_COLOR", 4, 5, 6),
    )
    tc = build_tclasses([block])["TEXT1"]
    assert tc.effect_for("normal") == "none"
    assert tc.effect_for("normal_active") == "shadow"
    assert tc.orientation == 2
    numeric = build_tclasses([_tclass_block("A", _kv("__ORIENTATION", 1))])["A"]
    assert numeric.orientation == 1
    undefined = build_tclasses([_tclass_block("B", _kv("__ORIENTATION", "__UP"))])["B"]
    assert undefined.orientation == 0


def test_tclass_sticky_and_hilited_chains() -> None:
    """TextclassPopulate: sticky.normal and sticky_active.normal both fall
    back to norm.normal (NOT active.normal); hilited falls back within its
    group (active.hilited ← active.normal)."""
    block = _tclass_block(
        "TEXT1",
        _kv("__NORMAL"), _kv("__FORGROUND_COLOR", 1, 1, 1),
        _kv("__NORMAL_ACTIVE"), _kv("__FORGROUND_COLOR", 2, 2, 2),
        _kv("__NORMAL_STICKY"), _kv("__FORGROUND_COLOR", 3, 3, 3),
        _kv("__HILITED"), _kv("__FORGROUND_COLOR", 4, 4, 4),
    )
    tc = build_tclasses([block])["TEXT1"]
    assert tc.fg_for("normal") == (1, 1, 1)
    assert tc.fg_for("normal_active") == (2, 2, 2)
    assert tc.fg_for("normal_sticky") == (3, 3, 3)
    assert tc.fg_for("normal_active_sticky") == (1, 1, 1)
    assert tc.fg_for("hilited") == (4, 4, 4)
    assert tc.fg_for("hilited_active") == (2, 2, 2)
    assert tc.fg_for("clicked_sticky") == (3, 3, 3)
