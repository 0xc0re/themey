"""Tests for aurorae_rc.py — Aurorae <name>rc INI writer.

Must use RawConfigParser with optionxform=str to preserve KDE case-sensitive keys.
"""
from __future__ import annotations

from configparser import RawConfigParser
from pathlib import Path

import pytest


def _make_minimal_theme(
    *,
    name: str = "Aliens",
    scale: int = 2,
    left_buttons: str = "XAI",
    right_buttons: str = "",
    text_active: tuple[int, int, int] = (255, 255, 200),
    text_inactive: tuple[int, int, int] = (192, 192, 192),
    border_size_left: int = 35,
    border_size_right: int = 35,
    border_size_top: int = 35,
    border_size_bottom: int = 6,
):
    """Build a minimal synthetic Theme for rc-writer tests."""
    from themey.ir import BorderSpec, Palette, Theme

    border = BorderSpec(
        name="DEFAULT",
        border_size_left=border_size_left,
        border_size_right=border_size_right,
        border_size_top=border_size_top,
        border_size_bottom=border_size_bottom,
        parts=(),
    )
    palette = Palette(
        titlebar_active=(64, 64, 64),
        titlebar_inactive=(128, 128, 128),
        text_active=text_active,
        text_inactive=text_inactive,
    )
    return Theme(
        name=name,
        display_name=name,
        author=None,
        scale=scale,
        asset_root=Path("/tmp/x"),
        border=border,
        iclasses={},
        tclasses={},
        button_codes={},
        left_buttons=left_buttons,
        right_buttons=right_buttons,
        palette=palette,
    )


def _read_rc(path: Path) -> RawConfigParser:
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(path, encoding="utf-8")
    return cp


def test_aurorae_rc_general_section(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(left_buttons="XAI", right_buttons="")
    out = write_aurorae_rc(theme, tmp_path)
    assert out.is_file()
    cp = _read_rc(out)
    assert cp["General"]["LeftButtons"] == "XAI"
    assert cp["General"]["RightButtons"] == ""


def test_aurorae_rc_active_text_color_format(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(text_active=(255, 255, 200))
    out = write_aurorae_rc(theme, tmp_path)
    cp = _read_rc(out)
    assert cp["General"]["ActiveTextColor"] == "255,255,200,255"


def test_aurorae_rc_layout_keys_present(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme()
    out = write_aurorae_rc(theme, tmp_path)
    cp = _read_rc(out)
    required_layout_keys = [
        "BorderLeft",
        "BorderRight",
        "BorderBottom",
        "BorderTop",
        "TitleEdgeTop",
        "TitleEdgeBottom",
        "TitleEdgeLeft",
        "TitleEdgeRight",
        # Extended layout keys matching Edna's rc
        "TitleBorderLeft",
        "TitleBorderRight",
        "TitleHeight",
        "ButtonWidth",
        "ButtonHeight",
        "ButtonSpacing",
        "PaddingTop",
        "PaddingBottom",
        "PaddingLeft",
        "PaddingRight",
    ]
    for key in required_layout_keys:
        assert key in cp["Layout"], f"Missing Layout key: {key}"


def test_aurorae_rc_borderleft_scales_with_theme_scale(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme1 = _make_minimal_theme(scale=1, border_size_left=35)
    theme2 = _make_minimal_theme(scale=2, border_size_left=35)
    out1 = write_aurorae_rc(theme1, tmp_path / "s1")
    (tmp_path / "s1").mkdir(parents=True, exist_ok=True)
    out1 = write_aurorae_rc(theme1, tmp_path / "s1")
    (tmp_path / "s2").mkdir(parents=True, exist_ok=True)
    out2 = write_aurorae_rc(theme2, tmp_path / "s2")
    cp1 = _read_rc(out1)
    cp2 = _read_rc(out2)
    bl1 = int(cp1["Layout"]["BorderLeft"])
    bl2 = int(cp2["Layout"]["BorderLeft"])
    assert bl2 == bl1 * 2, f"scale=2 BorderLeft ({bl2}) should be 2× scale=1 ({bl1})"


def test_aurorae_rc_filename_matches_theme_name(tmp_path: Path) -> None:
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme(name="Aliens")
    out = write_aurorae_rc(theme, tmp_path)
    assert out.name == "Aliensrc", f"Expected 'Aliensrc', got '{out.name}'"


def test_aurorae_rc_keys_case_preserved(tmp_path: Path) -> None:
    """Open written file as raw text; confirm LeftButtons= (capital L) NOT leftbuttons=."""
    from themey.generate.aurorae_rc import write_aurorae_rc

    theme = _make_minimal_theme()
    out = write_aurorae_rc(theme, tmp_path)
    raw = out.read_text(encoding="utf-8")
    assert "LeftButtons=" in raw, "Expected 'LeftButtons=' (capital L) in rc file"
    assert "leftbuttons=" not in raw, "Found lowercase 'leftbuttons=' — optionxform not set"
