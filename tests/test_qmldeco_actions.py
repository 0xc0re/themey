"""Tests for generate/qmldeco/actions.py — E16 part action → QML button kind.

Mirrors the SVG backend's four-tier binning (analyze/buttons.py): the stock
``__ACLASS`` name table first, then the name resolved through the
``__ACLASS __BGN`` block that defined it, then the iclass-name pattern.

Run:  uv run pytest tests/test_qmldeco_actions.py -q
"""
from __future__ import annotations

from pathlib import Path

from themey.analyze.build_theme import build_theme
from themey.etheme.parse import parse_tree
from themey.generate.qmldeco.actions import button_kind
from themey.generate.qmldeco.theme_js import build_theme_data
from themey.ir import ButtonPart


def _part(iclass: str, aclass: str | None) -> ButtonPart:
    return ButtonPart(
        iclass_name=iclass,
        aclass=aclass,
        tl_x_pct=0, tl_x_abs=0, tl_y_pct=0, tl_y_abs=0,
        br_x_pct=0, br_x_abs=22, br_y_pct=0, br_y_abs=23,
    )


def test_stock_aclass_name_still_maps() -> None:
    assert button_kind(_part("BUTTON_CLOSE", "ACTION_CLOSE")) == "close"


def test_theme_private_aclass_resolves_through_its_verb() -> None:
    """Ganymede's close button — the whole point of the verb tier."""
    kind = button_kind(
        _part("BORDER_TOPLEFT", "ACTION_GANYMEDE_KILL"),
        aclass_verbs={"ACTION_GANYMEDE_KILL": "__A_KILL"},
    )
    assert kind == "close"


def test_slideout_verb_becomes_the_window_menu() -> None:
    kind = button_kind(
        _part("BORDER_MIDDLE", "ACTION_WINDOW_SLIDEOUT"),
        aclass_verbs={"ACTION_WINDOW_SLIDEOUT": "__A_SLIDEOUT"},
    )
    assert kind == "menu"


def test_chrome_verb_stays_chrome() -> None:
    kind = button_kind(
        _part("BORDER_TITLE", "ACTION_MOVE_ONLY"),
        aclass_verbs={"ACTION_MOVE_ONLY": "__A_MOVE"},
    )
    assert kind is None


def test_unresolvable_aclass_stays_chrome() -> None:
    assert button_kind(_part("BORDER_TOPLEFT", "ACTION_GANYMEDE_KILL")) is None


# ---------------------------------------------------------------------------
# The generated theme.js must carry the resolved button through — this is
# what KWin actually reads.
# ---------------------------------------------------------------------------


def test_theme_js_gives_a_theme_private_aclass_its_button(ganymede_tree: Path) -> None:
    theme = build_theme(
        ganymede_tree, parse_tree(ganymede_tree), name="Ganymede", scale=1
    )
    data, _manifest, _fonts = build_theme_data(theme)
    by_id = {p["id"]: p for p in data["parts"]}
    assert by_id["BORDER_TOPLEFT"]["button"] == "close"
