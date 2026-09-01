"""Tests for analyze/menus.py — ``__MENU_STYLE`` blocks → MenuStyleSpec.

E16 (menus.c ``MenuStyleConfigLoad``) reads ``__BG_ICLASS``,
``__ITEM_ICLASS``, ``__SUBMENU_ICLASS``, ``__USE_ITEM_BACKGROUNDS``,
``__BORDER``, ``__TCLASS``. With item backgrounds ON the menu window has
NO background of its own — ``MenuRedraw`` skips ``bg_iclass`` entirely and
every item window wears the item iclass (menus.c:928-950, 976-985), and
the loader even frees a previously named bg_iclass (menus.c:1739-1746).

Run:  uv run pytest tests/test_analyze_menus.py -q
"""
from __future__ import annotations

from themey.analyze.menus import build_menu_styles
from themey.etheme.ast import Block, KeyVal


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _style(name: str, *children: KeyVal, head: tuple[object, ...] = ()) -> Block:
    return Block(
        keyword="__MENU_STYLE",
        head_values=head,
        children=(_kv("__NAME", name), *children) if not head else children,
        line=0,
    )


def test_normal_style_fields() -> None:
    styles = build_menu_styles([
        _style(
            "DEFAULT",
            _kv("__BORDER", "MENU"),
            _kv("__TCLASS", "MENU_TEXT"),
            _kv("__BG_ICLASS", "MENU_BG"),
            _kv("__ITEM_ICLASS", "MENU_SEL"),
            _kv("__SUBMENU_ICLASS", "MENU_SUB"),
            _kv("__USE_ITEM_BACKGROUNDS", "__OFF"),
            _kv("__MAXIMUM_NUMBER_OF_ROWS", 40),
        ),
    ])
    s = styles["DEFAULT"]
    assert s.name == "DEFAULT"
    assert s.border == "MENU"
    assert s.tclass == "MENU_TEXT"
    assert s.bg_iclass == "MENU_BG"
    assert s.item_iclass == "MENU_SEL"
    assert s.submenu_iclass == "MENU_SUB"
    assert s.use_item_bg is False


def test_item_backgrounds_on_drops_bg_iclass() -> None:
    """NeXTSTEP style (OldE): __USE_ITEM_BACKGROUNDS __ON → the menu has no
    background iclass, whatever was named."""
    styles = build_menu_styles([
        _style(
            "DEFAULT",
            _kv("__BG_ICLASS", "MENU_BG"),
            _kv("__ITEM_ICLASS", "MENU_SEL"),
            _kv("__USE_ITEM_BACKGROUNDS", "__ON"),
        ),
    ])
    s = styles["DEFAULT"]
    assert s.use_item_bg is True
    assert s.bg_iclass is None
    assert s.item_iclass == "MENU_SEL"


def test_use_item_backgrounds_numeric_and_head_name() -> None:
    """E16 reads the flag with atoi (menus.c:1740) — ``1`` works too; the
    name may also sit in head_values (``__MENU_STYLE X __BGN``)."""
    styles = build_menu_styles([
        _style("", _kv("__USE_ITEM_BACKGROUNDS", 1), head=("HEADNAME",)),
    ])
    assert styles["HEADNAME"].use_item_bg is True


def test_nameless_block_skipped_and_last_wins() -> None:
    styles = build_menu_styles([
        Block(keyword="__MENU_STYLE", head_values=(), children=(), line=0),
        _style("ROOT", _kv("__BG_ICLASS", "A")),
        _style("ROOT", _kv("__BG_ICLASS", "B")),
    ])
    assert list(styles) == ["ROOT"]
    assert styles["ROOT"].bg_iclass == "B"
