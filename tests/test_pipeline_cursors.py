"""Tests for pipeline.convert's XCursor theme install (Phase C / C5)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from themey.pipeline import convert
from themey.slug import cursor_theme_dir

FIXTURES = Path(__file__).parent / "fixtures"

needs_xcursorgen = pytest.mark.skipif(
    shutil.which("xcursorgen") is None, reason="xcursorgen not installed"
)


@needs_xcursorgen
def test_convert_installs_the_cursor_theme_under_icons(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert result.cursor_theme_dir is not None
    assert result.cursor_theme_dir == (
        fake_home / ".icons" / cursor_theme_dir("Aliens")
    )
    assert (result.cursor_theme_dir / "index.theme").is_file()
    assert (result.cursor_theme_dir / "cursors" / "default").is_file()


@needs_xcursorgen
def test_installed_index_theme_names_the_theme_and_inherits_breeze(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert result.cursor_theme_dir is not None
    text = (result.cursor_theme_dir / "index.theme").read_text()
    assert "[Icon Theme]" in text
    assert "Name=Aliens (themey)" in text
    assert "Inherits=breeze_cursors" in text


@needs_xcursorgen
def test_legacy_symlinks_survive_the_atomic_install(fake_home):
    """install.deploy renames the staged dir, so relative links stay valid."""
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert result.cursor_theme_dir is not None
    link = result.cursor_theme_dir / "cursors" / "left_ptr"
    assert link.is_symlink()
    assert link.resolve().is_file()


@needs_xcursorgen
def test_convert_is_idempotent_for_cursors(fake_home):
    r1 = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    r2 = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert r1.cursor_theme_dir == r2.cursor_theme_dir
    assert r2.cursor_theme_dir is not None
    assert (r2.cursor_theme_dir / "cursors" / "default").is_file()
    backup = r2.cursor_theme_dir.with_name(f"{r2.cursor_theme_dir.name}.themey-old")
    assert not backup.exists()


@needs_xcursorgen
def test_output_dir_mode_writes_cursors_without_touching_xdg(tmp_path, fake_home):
    out = tmp_path / "out"
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg", output_dir=out)
    assert result.cursor_theme_dir == out / cursor_theme_dir("Aliens")
    assert (result.cursor_theme_dir / "cursors" / "default").is_file()
    assert not (fake_home / ".icons").exists()


@needs_xcursorgen
def test_report_lists_the_converted_shapes(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    text = result.report_path.read_text()
    assert "Pointer theme: 6 cursor shape(s)" in text
    assert "size_fdiag" in text
    # The E16-only skips are a layout note, not dropped-state noise, so
    # they must appear above the truncated state bucket.
    approximated = text.split("## Skipped")[0]
    assert "cursors: 4 E16-only pointer(s)" in approximated


def test_theme_without_cursors_installs_none(fake_home):
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="svg")
    assert result.cursor_theme_dir is None
    assert not (fake_home / ".icons").exists()
    text = result.report_path.read_text()
    assert "Pointer theme: not installed" in text
    assert "cursors: no __CURSOR blocks" in text


# --------------------------------------------------------------------- #
# Graceful degradation (C5): xcursorgen missing
# --------------------------------------------------------------------- #


def test_missing_xcursorgen_skips_the_stage_and_notes_it(
    fake_home, tmp_path, monkeypatch: pytest.MonkeyPatch
):
    """The whole cursor stage is optional: no xcursorgen, no failure."""
    monkeypatch.setenv("PATH", str(tmp_path / "no-tools"))
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert result.cursor_theme_dir is None
    assert not (fake_home / ".icons").exists()
    # Everything else still converted.
    assert result.installed_dir.is_dir()
    assert result.color_scheme_path is not None
    text = result.report_path.read_text()
    assert "xcursorgen is not on PATH" in text
    assert "Pointer theme: not installed" in text
