"""Tests for the frozen Theme IR dataclasses (themey.ir)."""
from __future__ import annotations

import dataclasses
from pathlib import Path


def _make_palette():
    from themey.ir import Palette

    return Palette(
        titlebar_active=(40, 40, 40),
        titlebar_inactive=(60, 60, 60),
        text_active=(255, 255, 255),
        text_inactive=(180, 180, 180),
    )


def _make_iclass(name: str = "TITLE_BAR_HORIZONTAL"):
    from themey.ir import IClassSpec

    return IClassSpec(
        name=name,
        edge_scaling=(1, 2, 3, 4),
        normal=None,
        normal_active=Path("x.png"),
        hilited=None,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )


def _make_button_part():
    from themey.ir import ButtonPart

    return ButtonPart(
        iclass_name="CLOSE",
        aclass=None,
        tl_x_pct=0,
        tl_x_abs=0,
        tl_y_pct=0,
        tl_y_abs=0,
        br_x_pct=0,
        br_x_abs=24,
        br_y_pct=0,
        br_y_abs=24,
    )


def _make_border():
    from themey.ir import BorderSpec

    return BorderSpec(
        name="DEFAULT",
        border_size_left=4,
        border_size_right=4,
        border_size_top=24,
        border_size_bottom=4,
        parts=(_make_button_part(),),
    )


def _make_theme(**kwargs):
    from themey.ir import Theme

    defaults = dict(
        name="TestTheme",
        display_name="Test Theme",
        author="tester",
        scale=2,
        asset_root=Path("/tmp/test"),
        border=_make_border(),
        iclasses={"TITLE_BAR_HORIZONTAL": _make_iclass()},
        tclasses={},
        button_codes={"CLOSE": "X"},
        left_buttons="X",
        right_buttons="",
        palette=_make_palette(),
    )
    defaults.update(kwargs)
    return Theme(**defaults)


def test_theme_is_frozen():
    """Theme is a frozen dataclass — mutating a field raises FrozenInstanceError."""
    theme = _make_theme()
    with __import__("pytest").raises(dataclasses.FrozenInstanceError):
        theme.scale = 3  # type: ignore[misc]


def test_iclass_spec_has_required_fields():
    """IClassSpec constructs with all required fields and stores edge_scaling correctly."""
    spec = _make_iclass("TITLE_BAR_HORIZONTAL")
    assert spec.name == "TITLE_BAR_HORIZONTAL"
    assert spec.edge_scaling == (1, 2, 3, 4)
    assert spec.normal is None
    assert spec.normal_active == Path("x.png")


def test_theme_notes_is_mutable():
    """Theme.notes is a mutable list even though Theme is frozen (list is the field value, not the field)."""
    theme = _make_theme()
    theme.notes.append("hi")
    assert theme.notes == ["hi"]
