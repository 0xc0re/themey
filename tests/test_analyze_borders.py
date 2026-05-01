"""Unit tests for themey.analyze.borders — AST __BORDER block extraction."""
from __future__ import annotations

from themey.etheme.ast import Block, KeyVal
from themey.analyze.borders import (
    build_border,
    extract_button_parts,
    select_default_border,
)


# ---------------------------------------------------------------------------
# Helpers: synthetic AST factories
# ---------------------------------------------------------------------------


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _border_block(name: str | None = None, parts: list[Block] | None = None) -> Block:
    """Build a synthetic __BORDER block with optional named head_values and parts."""
    head: tuple[object, ...] = (name,) if name is not None else ()
    children: list[object] = list(parts or [])
    return Block(keyword="__BORDER", head_values=head, children=tuple(children), line=0)


def _part_block(**kv_kwargs: object) -> Block:
    """Build a synthetic __BORDER_PART block with KeyVal children from kwargs."""
    children: list[KeyVal] = []
    for k, v in kv_kwargs.items():
        keyword = f"__{k.upper()}"
        children.append(_kv(keyword, v))
    return Block(keyword="__BORDER_PART", head_values=(), children=tuple(children), line=0)


# ---------------------------------------------------------------------------
# select_default_border tests
# ---------------------------------------------------------------------------


def test_select_default_picks_named_default() -> None:
    """Block named DEFAULT is chosen over BORDERLESS."""
    default_block = _border_block(name="DEFAULT")
    borderless_block = _border_block(name="BORDERLESS")
    result = select_default_border([default_block, borderless_block])
    assert result is default_block


def test_select_default_falls_back_to_first_with_parts() -> None:
    """No DEFAULT name; first block with a __BORDER_PART child is selected."""
    foo_block = _border_block(name="FOO", parts=[_part_block(ICLASS="SOME_PART")])
    bar_block = _border_block(name="BAR")  # no parts
    result = select_default_border([foo_block, bar_block])
    assert result is foo_block


def test_select_default_empty_returns_none() -> None:
    """Empty list returns None."""
    assert select_default_border([]) is None


def test_select_default_none_when_none_have_parts() -> None:
    """No DEFAULT and no parts → None."""
    foo = _border_block(name="FOO")
    bar = _border_block(name="BAR")
    assert select_default_border([foo, bar]) is None


# ---------------------------------------------------------------------------
# extract_button_parts tests
# ---------------------------------------------------------------------------


def test_extract_button_parts_aclass_captured_with_null_sentinel() -> None:
    """__BORDER_PART with __ICLASS but no __ACLASS → aclass is None (null sentinel)."""
    part = Block(
        keyword="__BORDER_PART",
        head_values=(),
        children=(
            _kv("__ICLASS", "BUTTON_FOO"),
        ),
        line=0,
    )
    border = _border_block(name="DEFAULT", parts=[part])
    result = extract_button_parts(border)
    assert len(result) == 1
    assert result[0].iclass_name == "BUTTON_FOO"
    assert result[0].aclass is None  # null sentinel: "parser saw no __ACLASS"


def test_extract_button_parts_aclass_stored_when_present() -> None:
    """__ACLASS value is preserved when declared."""
    part = Block(
        keyword="__BORDER_PART",
        head_values=(),
        children=(
            _kv("__ICLASS", "BUTTON_KILL"),
            _kv("__ACLASS", "ACTION_KILL"),
        ),
        line=0,
    )
    border = _border_block(name="DEFAULT", parts=[part])
    result = extract_button_parts(border)
    assert result[0].aclass == "ACTION_KILL"


def test_extract_button_parts_full_coords() -> None:
    """Coordinate KeyVals are extracted into ButtonPart fields."""
    part = Block(
        keyword="__BORDER_PART",
        head_values=(),
        children=(
            _kv("__ICLASS", "BUTTON_TEST"),
            _kv("__TOPLEFT_X_PERCENTAGE", 0),
            _kv("__TOPLEFT_X_ABSOLUTE", 11),
            _kv("__TOPLEFT_Y_PERCENTAGE", 0),
            _kv("__TOPLEFT_Y_ABSOLUTE", 0),
            _kv("__BOTTOMRIGHT_X_PERCENTAGE", 0),
            _kv("__BOTTOMRIGHT_X_ABSOLUTE", 27),
            _kv("__BOTTOMRIGHT_Y_PERCENTAGE", 0),
            _kv("__BOTTOMRIGHT_Y_ABSOLUTE", 30),
        ),
        line=0,
    )
    border = _border_block(name="DEFAULT", parts=[part])
    result = extract_button_parts(border)
    assert len(result) == 1
    p = result[0]
    assert p.tl_x_pct == 0
    assert p.tl_x_abs == 11
    assert p.tl_y_pct == 0
    assert p.tl_y_abs == 0
    assert p.br_x_pct == 0
    assert p.br_x_abs == 27
    assert p.br_y_pct == 0
    assert p.br_y_abs == 30


def test_extract_button_parts_empty_when_no_parts() -> None:
    """Border with no __BORDER_PART children → empty tuple."""
    border = _border_block(name="DEFAULT")
    result = extract_button_parts(border)
    assert result == ()


# ---------------------------------------------------------------------------
# build_border tests
# ---------------------------------------------------------------------------


def test_build_border_size_keys() -> None:
    """__BORDER_SIZE_* keys are parsed into BorderSpec fields."""
    border_block = Block(
        keyword="__BORDER",
        head_values=("DEFAULT",),
        children=(
            _kv("__BORDER_SIZE_LEFT", 35),
            _kv("__BORDER_SIZE_RIGHT", 20),
            _kv("__BORDER_SIZE_TOP", 30),
            _kv("__BORDER_SIZE_BOTTOM", 25),
        ),
        line=0,
    )
    result = build_border(border_block)
    assert result.name == "DEFAULT"
    assert result.border_size_left == 35
    assert result.border_size_right == 20
    assert result.border_size_top == 30
    assert result.border_size_bottom == 25


def test_build_border_name_from_head_values() -> None:
    """name comes from head_values[0] when present."""
    border_block = _border_block(name="CUSTOM")
    spec = build_border(border_block)
    assert spec.name == "CUSTOM"


def test_build_border_name_defaults_when_no_head_values() -> None:
    """When no head_values, name defaults to 'DEFAULT'."""
    border_block = _border_block(name=None)
    spec = build_border(border_block)
    assert spec.name == "DEFAULT"
