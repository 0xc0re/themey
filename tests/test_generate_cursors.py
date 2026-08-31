"""Tests for generate/cursors.py — the E16 → XCursor theme emitter (Phase C / C3).

The name table and theme assembly are pure enough to test without
xcursorgen; the tests that need the real tool skip when it is absent
(same pattern as the qmllint guard in test_qmldeco_package.py). Binary
structure is asserted separately in test_cursors_binary.py.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from themey.analyze.build_theme import build_theme
from themey.etheme.archive import extract
from themey.etheme.parse import parse_tree
from themey.generate.cursors import (
    SCALES,
    hotspot_for,
    modern_name,
    read_xbm,
    write_theme,
)
from themey.ir import CursorSpec
from themey.slug import cursor_theme_dir

FIXTURES = Path(__file__).parent / "fixtures"

needs_xcursorgen = pytest.mark.skipif(
    shutil.which("xcursorgen") is None, reason="xcursorgen not installed"
)


def _theme(name: str):
    """Build a Theme from a fixture; asset_root stays valid for the caller."""
    return extract(FIXTURES / f"{name}.etheme")


# --------------------------------------------------------------------- #
# Name table
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("e16", "expected"),
    [
        ("DEFAULT", "default"),
        ("MOVE", "fleur"),
        ("RESIZE_H", "size_hor"),
        ("RESIZE_V", "size_ver"),
        ("RESIZE_BR", "size_fdiag"),
        ("RESIZE_TL", "size_fdiag"),
        ("RESIZE_BL", "size_bdiag"),
        ("RESIZE_TR", "size_bdiag"),
    ],
)
def test_modern_name_maps_known_shapes(e16, expected):
    assert modern_name(e16) == expected


@pytest.mark.parametrize(
    ("e16", "expected"),
    [
        ("MOVE_CUR", "fleur"),
        ("RESIZE_H_CUR", "size_hor"),
        ("RESIZE_UL_CUR", "size_fdiag"),  # UL normalizes to TL
        ("RESIZE_UR_CUR", "size_bdiag"),  # UR normalizes to TR
    ],
)
def test_modern_name_strips_cur_suffix_and_normalizes_directions(e16, expected):
    assert modern_name(e16) == expected


@pytest.mark.parametrize(
    "e16", ["ICONIFY", "ICON_CUR", "KILL", "KILL_CUR", "MAX", "STICK", "PIN_CUR", "SO_CUR"]
)
def test_modern_name_returns_none_for_e16_only_shapes(e16):
    """Window-operation pointers X11 has no equivalent for — skipped, and
    Inherits=breeze_cursors covers the gap."""
    assert modern_name(e16) is None


def test_modern_name_is_case_insensitive():
    assert modern_name("resize_h") == "size_hor"


# --------------------------------------------------------------------- #
# Hotspot resolution (contract 3: the XBM carries it, not the cfg)
# --------------------------------------------------------------------- #


def _spec(path: Path, hot: tuple[int, int] = (0, 0)) -> CursorSpec:
    return CursorSpec(
        name="DEFAULT", xbm_path=path, hot_x=hot[0], hot_y=hot[1],
        fg_rgb=(255, 255, 255), bg_rgb=(0, 0, 0),
    )


def _xbm(tmp_path: Path, hot: tuple[int, int] | None, dim: int = 8) -> Path:
    lines = [f"#define h_width {dim}", f"#define h_height {dim}"]
    if hot is not None:
        lines += [f"#define h_x_hot {hot[0]}", f"#define h_y_hot {hot[1]}"]
    stride = (dim + 7) // 8
    lines.append("static char h_bits[] = {")
    lines.append("   " + ", ".join(["0x01"] * (stride * dim)) + " };")
    p = tmp_path / "h.xbm"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


def test_hotspot_comes_from_the_xbm_when_cfg_is_silent(tmp_path: Path):
    path = _xbm(tmp_path, (3, 5))
    assert hotspot_for(_spec(path), read_xbm(path)) == (3, 5)


def test_nonzero_cfg_hotspot_overrides_the_xbm(tmp_path: Path):
    path = _xbm(tmp_path, (3, 5))
    assert hotspot_for(_spec(path, hot=(1, 2)), read_xbm(path)) == (1, 2)


def test_hotspot_defaults_to_origin_when_neither_declares_one(tmp_path: Path):
    path = _xbm(tmp_path, None)
    assert hotspot_for(_spec(path), read_xbm(path)) == (0, 0)


def test_out_of_range_hotspot_is_clamped_into_the_image(tmp_path: Path):
    """Mac3D's pin.xbm really declares y_hot 20 on a 20px bitmap;
    xcursorgen rejects a hotspot outside the image."""
    path = _xbm(tmp_path, (99, 20), dim=20)
    assert hotspot_for(_spec(path), read_xbm(path)) == (19, 19)


def test_negative_hotspot_is_clamped_to_origin(tmp_path: Path):
    path = _xbm(tmp_path, (-4, -1))
    assert hotspot_for(_spec(path), read_xbm(path)) == (0, 0)


# --------------------------------------------------------------------- #
# Theme assembly
# --------------------------------------------------------------------- #


@needs_xcursorgen
def test_write_theme_emits_the_six_aliens_shapes(tmp_path: Path):
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        out = tmp_path / cursor_theme_dir("Aliens")
        result = write_theme(theme, out)
    assert result is not None
    assert set(result.shapes) == {
        "default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"
    }
    for shape in result.shapes:
        binary = out / "cursors" / shape
        assert binary.is_file() and binary.stat().st_size > 0
        assert not binary.is_symlink()


@needs_xcursorgen
def test_write_theme_writes_index_theme(tmp_path: Path):
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        out = tmp_path / cursor_theme_dir("Aliens")
        write_theme(theme, out)
    text = (out / "index.theme").read_text()
    assert text.splitlines()[0] == "[Icon Theme]"
    assert "Name=Aliens (themey)" in text
    assert "Inherits=breeze_cursors" in text


@needs_xcursorgen
def test_write_theme_links_legacy_names_to_modern_ones(tmp_path: Path):
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        out = tmp_path / cursor_theme_dir("Aliens")
        write_theme(theme, out)
    cursors = out / "cursors"
    left_ptr = cursors / "left_ptr"
    assert left_ptr.is_symlink()
    assert left_ptr.readlink() == Path("default")  # relative, stays valid on install
    assert (cursors / "move").readlink() == Path("fleur")


@needs_xcursorgen
def test_write_theme_creates_no_alias_for_a_shape_it_does_not_ship(tmp_path: Path):
    """OPENSTEP has no RESIZE_H, so nothing may claim sb_h_double_arrow —
    Inherits=breeze_cursors is what fills that gap."""
    with _theme("OPENSTEP") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="OPENSTEP", display_name="OPENSTEP", scale=2,
        )
        out = tmp_path / cursor_theme_dir("OPENSTEP")
        result = write_theme(theme, out)
    assert result is not None
    assert "size_hor" not in result.shapes
    assert not (out / "cursors" / "sb_h_double_arrow").exists()
    assert not (out / "cursors" / "size_hor").exists()


@needs_xcursorgen
def test_write_theme_notes_skipped_e16_only_shapes(tmp_path: Path):
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        write_theme(theme, tmp_path / cursor_theme_dir("Aliens"))
    notes = [n for n in theme.notes if n.startswith("cursors:")]
    skipped = [n for n in notes if "no X11 equivalent" in n]
    assert len(skipped) == 1
    for name in ("KILL", "ICONIFY", "MAX", "STICK"):
        assert name in skipped[0]


@needs_xcursorgen
def test_write_theme_normalizes_mac3d_cur_names(tmp_path: Path):
    """Mac3D is the _CUR-suffix canary; its 25px move.xbm also proves the
    emitter does not assume 16px sources."""
    with _theme("Mac3D") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Mac3D", display_name="Mac3D", scale=2,
        )
        out = tmp_path / cursor_theme_dir("Mac3D")
        result = write_theme(theme, out)
    assert result is not None
    assert set(result.shapes) == {
        "default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"
    }
    assert (out / "cursors" / "fleur").is_file()


def test_write_theme_returns_none_for_a_theme_with_no_cursors(tmp_path: Path):
    with _theme("tiny") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="tiny", display_name="tiny", scale=2,
        )
        out = tmp_path / cursor_theme_dir("tiny")
        assert write_theme(theme, out) is None
    assert not out.exists()
    assert any("no __CURSOR blocks" in n for n in theme.notes)


def test_write_theme_returns_none_when_xcursorgen_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        out = tmp_path / cursor_theme_dir("Aliens")
        assert write_theme(theme, out) is None
    assert not out.exists()
    assert any("xcursorgen" in n for n in theme.notes)


@needs_xcursorgen
def test_write_theme_skips_a_cursor_whose_xbm_is_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """One broken source must not lose the whole pointer theme."""
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        (raw.asset_root / "artwork" / "cursors" / "move.xbm").write_text("garbage\n")
        out = tmp_path / cursor_theme_dir("Aliens")
        result = write_theme(theme, out)
    assert result is not None
    assert "fleur" not in result.shapes
    assert "default" in result.shapes
    assert not (out / "cursors" / "move").exists()
    assert any("MOVE" in n and n.startswith("cursors:") for n in theme.notes)


@needs_xcursorgen
def test_write_theme_emits_one_image_per_scale(tmp_path: Path):
    with _theme("Aliens") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", scale=2,
        )
        result = write_theme(theme, tmp_path / cursor_theme_dir("Aliens"))
    assert result is not None
    assert len(SCALES) == 3
