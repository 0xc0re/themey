"""Tests for analyze/aclasses.py — ``__ACLASS __BGN`` blocks → action verbs.

E16 loads ``actionclasses.cfg``, ``buttons.cfg`` and ``slideouts.cfg``
BEFORE ``borders.cfg`` (config.c:580 ``ThemeConfigLoad``), so a border
part's ``__ACLASS <name>`` reference resolves against action classes the
theme defined itself. ``ConfigFileRead``'s ``CONFIG_CLASSNAME`` case
(aclass.c:321-332) calls ``ActionclassEmpty`` on a name that already
exists and refills it, so the LAST definition of a name wins.

The verb is the ``__A_*`` macro name: themey's preprocessor registers only
function-like macros from the bundled ``definitions``, so the object-like
``#define __A_KILL wop * close`` is never expanded and the AST keeps
``__A_KILL`` verbatim.

Run:  uv run pytest tests/test_analyze_aclasses.py -q
"""
from __future__ import annotations

from pathlib import Path

from themey.analyze.aclasses import build_aclasses, stock_aclasses
from themey.analyze.build_theme import build_theme
from themey.etheme.ast import Block, KeyVal
from themey.etheme.parse import parse_tree

from .conftest import GANYMEDE_BORDERS


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _aclass(*children: KeyVal) -> Block:
    return Block(keyword="__ACLASS", head_values=(), children=children, line=0)


def test_primary_verb_is_the_first_action() -> None:
    """Ganymede's ACTION_GANYMEDE_KILL: btn1 close, btn2 kill, btn3 iconify."""
    blocks = [
        _aclass(
            _kv("__NAME", "ACTION_GANYMEDE_KILL"),
            _kv("__TOOLTIP_TEXT", "Closing/Killing options"),
            _kv("__EVENT", "__MOUSE_RELEASE"),
            _kv("__BUTTON", 1),
            _kv("__ACTION", "__A_KILL"),
            _kv("__NEXT_ACTION"),
            _kv("__BUTTON", 2),
            _kv("__ACTION", "__A_KILL_NASTY"),
            _kv("__NEXT_ACTION"),
            _kv("__BUTTON", 3),
            _kv("__ACTION", "__A_ICONIFY"),
        )
    ]
    assert build_aclasses(blocks) == {"ACTION_GANYMEDE_KILL": "__A_KILL"}


def test_last_definition_of_a_name_wins() -> None:
    """aclass.c:321-332 ActionclassEmpty's the existing class and refills it."""
    blocks = [
        _aclass(_kv("__NAME", "ACTION_MOVE"), _kv("__ACTION", "__A_MOVE")),
        _aclass(_kv("__NAME", "ACTION_MOVE"), _kv("__ACTION", "__A_SHADE")),
    ]
    assert build_aclasses(blocks)["ACTION_MOVE"] == "__A_SHADE"


def test_block_without_an_action_registers_nothing() -> None:
    blocks = [_aclass(_kv("__NAME", "ACTION_NOTHING"), _kv("__TYPE", "__TYPE_NORMAL"))]
    assert build_aclasses(blocks) == {}


# ---------------------------------------------------------------------------
# E16's own config/actionclasses.cfg, bundled verbatim.
#
# ConfigFileLoad("actionclasses.cfg", theme_path, ...) falls back to E16's
# config dir when the theme ships no such file (config.c ConfigFileFind ->
# FindFile), which is how a 2009 theme could bind a border part to
# ACTION_WINDOW_SLIDEOUT without defining it. 100 of the corpus's border
# __ACLASS references are that one name.
# ---------------------------------------------------------------------------


def test_stock_actionclasses_resolve_e16s_own_names() -> None:
    stock = stock_aclasses()
    assert stock["ACTION_KILL"] == "__A_KILL"
    assert stock["ACTION_ICONIFY"] == "__A_ICONIFY"
    assert stock["ACTION_MAXH"] == "__A_MAX_HEIGHT"
    assert stock["ACTION_LOWER"] == "__A_LOWER"
    assert stock["ACTION_WINDOW_SLIDEOUT"] == "__A_SLIDEOUT"


def test_stock_actionclasses_keep_verbs_unexpanded() -> None:
    """Object-like defines are deliberately not expanded (they are E16's
    numeric keyword ids elsewhere), so verbs survive as __A_* names."""
    assert all(v.startswith("__A_") for v in stock_aclasses().values())


# ---------------------------------------------------------------------------
# End to end: __ACLASS blocks from the theme's own cfg files reach the IR.
#
# E16's ThemeConfigLoad order is actionclasses.cfg, buttons.cfg,
# slideouts.cfg, then borders.cfg, so a border part can reference a class
# any of the three registered. Ganymede puts all of its in slideouts.cfg.
# ---------------------------------------------------------------------------

def test_theme_carries_the_resolved_action_class_table(ganymede_tree: Path) -> None:
    theme = build_theme(ganymede_tree, parse_tree(ganymede_tree), name="Ganymede", scale=1)
    assert theme.aclass_verbs["ACTION_GANYMEDE_KILL"] == "__A_KILL"


def test_theme_private_close_button_survives_to_the_ir(ganymede_tree: Path) -> None:
    """The bug: Ganymede shipped with every part button=None."""
    theme = build_theme(ganymede_tree, parse_tree(ganymede_tree), name="Ganymede", scale=1)
    assert theme.button_codes["BORDER_TOPLEFT"] == "X"


def test_resolved_part_is_no_longer_reported_as_unmappable(ganymede_tree: Path) -> None:
    theme = build_theme(ganymede_tree, parse_tree(ganymede_tree), name="Ganymede", scale=1)
    assert not [n for n in theme.notes if "ACTION_GANYMEDE_KILL" in n]


def test_stock_names_resolve_without_the_theme_defining_them(tmp_path: Path) -> None:
    """ACTION_WINDOW_SLIDEOUT comes from E16's config dir, not the archive."""
    (tmp_path / "borders.cfg").write_text(
        GANYMEDE_BORDERS.replace("ACTION_GANYMEDE_KILL", "ACTION_WINDOW_SLIDEOUT")
    )
    theme = build_theme(tmp_path, parse_tree(tmp_path), name="X", scale=1)
    assert theme.button_codes["BORDER_TOPLEFT"] == "M"
