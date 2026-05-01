"""Unit tests for themey.analyze.fallback — PARSE-05 filename-pattern discovery."""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.analyze.fallback import CANONICAL_FILENAMES, discover_by_filename


# ---------------------------------------------------------------------------
# CANONICAL_FILENAMES constant shape tests
# ---------------------------------------------------------------------------


def test_canonical_filenames_constant_shape() -> None:
    """CANONICAL_FILENAMES has at least 8 keys including all required iclass names."""
    assert isinstance(CANONICAL_FILENAMES, dict)
    assert len(CANONICAL_FILENAMES) >= 8
    required_keys = {
        "TITLE_BAR_HORIZONTAL",
        "BUTTON_CLOSE",
        "BUTTON_MAXIMIZE",
        "BUTTON_ICONIFY",
        "BORDER_TOP",
        "BORDER_BOTTOM",
        "BORDER_LEFT",
        "BORDER_RIGHT",
    }
    for key in required_keys:
        assert key in CANONICAL_FILENAMES, f"Missing required key: {key}"
    # Each value should be a non-empty list of strings
    for iclass_name, candidates in CANONICAL_FILENAMES.items():
        assert isinstance(candidates, list), f"{iclass_name}: value is not a list"
        assert len(candidates) >= 1, f"{iclass_name}: candidates list is empty"
        for cand in candidates:
            assert isinstance(cand, str), f"{iclass_name}: candidate {cand!r} is not a str"


# ---------------------------------------------------------------------------
# discover_by_filename tests
# ---------------------------------------------------------------------------


def test_discover_returns_empty_when_no_files(tmp_path: Path) -> None:
    """Empty asset_root returns empty dict — no PNGs, no matches."""
    result = discover_by_filename(tmp_path)
    assert result == {}


def test_discover_finds_canonical_titlebar(tmp_path: Path) -> None:
    """border_top_default.png in asset_root → TITLE_BAR_HORIZONTAL key in result."""
    (tmp_path / "border_top_default.png").touch()
    result = discover_by_filename(tmp_path)
    assert "TITLE_BAR_HORIZONTAL" in result
    assert result["TITLE_BAR_HORIZONTAL"] == tmp_path / "border_top_default.png"


def test_discover_recurses_subdirs(tmp_path: Path) -> None:
    """PNG in a subdir is found via rglob."""
    artwork = tmp_path / "artwork"
    artwork.mkdir()
    (artwork / "border_topleft_default.png").touch()
    result = discover_by_filename(tmp_path)
    assert "CORNER_TL" in result
    assert result["CORNER_TL"] == artwork / "border_topleft_default.png"


def test_discover_first_match_wins(tmp_path: Path) -> None:
    """When multiple canonical filenames exist, the first in the priority list wins.

    For TITLE_BAR_HORIZONTAL, priority is:
    ["border_top_default.png", "title_default.png", "title.png", "n_title.png"]
    border_top_default.png is first, so it wins even if title_default.png also exists.
    """
    (tmp_path / "border_top_default.png").touch()
    (tmp_path / "title_default.png").touch()
    result = discover_by_filename(tmp_path)
    assert "TITLE_BAR_HORIZONTAL" in result
    # The first match in CANONICAL_FILENAMES list wins
    assert result["TITLE_BAR_HORIZONTAL"].name == "border_top_default.png"


def test_discover_finds_button_close(tmp_path: Path) -> None:
    """button_close_active.png found → BUTTON_CLOSE key in result."""
    (tmp_path / "button_close_active.png").touch()
    result = discover_by_filename(tmp_path)
    assert "BUTTON_CLOSE" in result


def test_discover_only_png_files(tmp_path: Path) -> None:
    """Non-PNG files are ignored even if named canonically."""
    (tmp_path / "border_top_default.xcf").touch()
    (tmp_path / "border_top_default.xpm").touch()
    result = discover_by_filename(tmp_path)
    assert "TITLE_BAR_HORIZONTAL" not in result


def test_discover_no_match_when_no_canonical_name(tmp_path: Path) -> None:
    """A PNG with a non-canonical name doesn't produce any entry."""
    (tmp_path / "totally_random_image.png").touch()
    result = discover_by_filename(tmp_path)
    assert len(result) == 0


def test_discover_multiple_canonical_matches(tmp_path: Path) -> None:
    """Multiple canonical files each produce their own dict entry."""
    (tmp_path / "border_top_default.png").touch()
    (tmp_path / "button_close_active.png").touch()
    (tmp_path / "button_max_active.png").touch()
    result = discover_by_filename(tmp_path)
    # All three should appear in the result
    assert "TITLE_BAR_HORIZONTAL" in result
    assert "BUTTON_CLOSE" in result
    assert "BUTTON_MAXIMIZE" in result
