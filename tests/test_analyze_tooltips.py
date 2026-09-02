"""Tests for analyze/tooltips.py — ``__TOOLTIP`` blocks → TooltipSpec.

E16 (tooltips.c ``TooltipConfigLoad``) reads ``__NAME``, ``__ICLASS``,
``__BUBBLE1_ICLASS``..``__BUBBLE4_ICLASS``, ``__TCLASS``, ``__DISTANCE``
and ``__TOOLTIP_HELP_ICON``; a block is only created when name, iclass AND
tclass are all set, and a name that already exists makes the loader skip
the whole block (``TooltipFind`` at the ``__NAME`` line) — FIRST wins,
unlike menu styles. ``TooltipShow`` looks up ``DEFAULT`` for everything but
the iconbox/pager, which use ``ICONBOX``/``PAGER``.

Run:  uv run pytest tests/test_analyze_tooltips.py -q
"""
from __future__ import annotations

from themey.analyze.tooltips import build_tooltips
from themey.etheme.ast import Block, KeyVal


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _tooltip(*children: KeyVal, head: tuple[object, ...] = ()) -> Block:
    return Block(keyword="__TOOLTIP", head_values=head, children=children, line=0)


def _define_tooltip(name: str, iclass: str, tclass: str, *extra: KeyVal) -> Block:
    """The shape ``DEFINE_TOOLTIP(...)`` from ``config/definitions`` expands to."""
    return _tooltip(
        _kv("__NAME", name),
        _kv("__ICLASS", iclass),
        _kv("__BUBBLE1_ICLASS", "TT_CLOUD1"),
        _kv("__BUBBLE2_ICLASS", "TT_CLOUD2"),
        _kv("__BUBBLE3_ICLASS", "TT_CLOUD3"),
        _kv("__BUBBLE4_ICLASS", "TT_CLOUD4"),
        _kv("__TOOLTIP_HELP_ICON", "DO_HELP_BUTTON"),
        _kv("__TCLASS", tclass),
        _kv("__DISTANCE", 64),
        *extra,
    )


def test_define_tooltip_fields() -> None:
    tips = build_tooltips([_define_tooltip("DEFAULT", "TT_MAIN", "TEXT1")])
    t = tips["DEFAULT"]
    assert t.name == "DEFAULT"
    assert t.iclass == "TT_MAIN"
    assert t.tclass == "TEXT1"
    assert t.bubbles == ("TT_CLOUD1", "TT_CLOUD2", "TT_CLOUD3", "TT_CLOUD4")
    assert t.help_icon == "DO_HELP_BUTTON"
    assert t.distance == 64


def test_simple_tooltip_has_no_bubbles_or_logo() -> None:
    tips = build_tooltips([
        _tooltip(
            _kv("__NAME", "DEFAULT"),
            _kv("__ICLASS", "BAR"),
            _kv("__TCLASS", "COORDS"),
            _kv("__DISTANCE", "16"),
        ),
    ])
    t = tips["DEFAULT"]
    assert t.iclass == "BAR"
    assert t.tclass == "COORDS"
    assert t.bubbles == ()
    assert t.help_icon is None
    assert t.distance == 16


def test_name_in_head_values() -> None:
    tips = build_tooltips([
        _tooltip(_kv("__ICLASS", "TT_MAIN"), _kv("__TCLASS", "TT_TEXT"), head=("PAGER",)),
    ])
    assert tips["PAGER"].iclass == "TT_MAIN"


def test_first_definition_wins() -> None:
    """tooltips.c:170 skips a block whose name already exists."""
    tips = build_tooltips([
        _define_tooltip("DEFAULT", "TT_MAIN", "TT_TEXT"),
        _define_tooltip("DEFAULT", "TT_MINI", "TEXT2"),
    ])
    assert tips["DEFAULT"].iclass == "TT_MAIN"
    assert tips["DEFAULT"].tclass == "TT_TEXT"


def test_incomplete_blocks_are_dropped() -> None:
    """``_TtCreate`` runs only when name, iclass and tclass are all set."""
    tips = build_tooltips([
        _tooltip(_kv("__NAME", "DEFAULT"), _kv("__ICLASS", "TT_MAIN")),
        _tooltip(_kv("__NAME", "ICONBOX"), _kv("__TCLASS", "TT_TEXT")),
        _tooltip(_kv("__ICLASS", "TT_MAIN"), _kv("__TCLASS", "TT_TEXT")),
        _define_tooltip("PAGER", "TT_MINI", "TT_TEXT"),
    ])
    assert list(tips) == ["PAGER"]


def test_blank_bubbles_are_kept_in_slot_order() -> None:
    """Bubbles are positional (cloud 1..4); an unset middle slot stays empty
    so later slots keep their index."""
    tips = build_tooltips([
        _tooltip(
            _kv("__NAME", "DEFAULT"),
            _kv("__ICLASS", "TT_MAIN"),
            _kv("__BUBBLE1_ICLASS", "C1"),
            _kv("__BUBBLE3_ICLASS", "C3"),
            _kv("__TCLASS", "TT_TEXT"),
        ),
    ])
    assert tips["DEFAULT"].bubbles == ("C1", "", "C3")


def test_undefined_iclass_block_is_dropped_and_later_name_wins() -> None:
    """tooltips.c:102 ``ImageclassAlloc(ic0, 0)`` has no fallback: a block
    naming an unknown iclass creates nothing, so ``TooltipFind`` lets a later
    block of the same name through."""
    notes: list[str] = []
    tips = build_tooltips(
        [
            _define_tooltip("DEFAULT", "TT_GHOST", "TT_TEXT"),
            _define_tooltip("DEFAULT", "TT_MAIN", "TEXT1"),
        ],
        iclasses={"TT_MAIN"},
        notes=notes,
    )
    assert tips["DEFAULT"].iclass == "TT_MAIN"
    assert tips["DEFAULT"].tclass == "TEXT1"
    assert len(notes) == 1
    assert notes[0].startswith("tooltips: __TOOLTIP DEFAULT names undefined iclass TT_GHOST")


def test_without_iclasses_no_existence_check() -> None:
    tips = build_tooltips([_define_tooltip("DEFAULT", "TT_GHOST", "TT_TEXT")])
    assert tips["DEFAULT"].iclass == "TT_GHOST"
