"""Tests for themey.report.write — report.txt scaffold."""
from __future__ import annotations

from pathlib import Path


def _make_theme(notes: list[str] | None = None, skipped_borders: tuple[str, ...] = ()):
    """Build a minimal Theme for testing."""
    from themey.ir import BorderSpec, IClassSpec, Palette, Theme

    palette = Palette(
        titlebar_active=(30, 30, 80),
        titlebar_inactive=(50, 50, 50),
        text_active=(255, 255, 255),
        text_inactive=(200, 200, 200),
    )
    iclass = IClassSpec(
        name="TITLE_BAR_HORIZONTAL",
        edge_scaling=(4, 4, 4, 4),
        normal=None,
        normal_active=None,
        hilited=None,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )
    border = BorderSpec(
        name="DEFAULT",
        border_size_left=4,
        border_size_right=4,
        border_size_top=20,
        border_size_bottom=4,
        parts=(),
    )
    return Theme(
        name="TestTheme",
        display_name="Test Theme",
        author=None,
        scale=1,
        asset_root=Path("/tmp"),
        border=border,
        iclasses={"TITLE_BAR_HORIZONTAL": iclass},
        tclasses={},
        button_codes={},
        left_buttons="X",
        right_buttons="A",
        palette=palette,
        notes=notes or [],
        skipped_borders=skipped_borders,
    )


def test_report_three_sections(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text().lower()
    assert "preserved" in text
    assert "approximated" in text
    assert "skipped" in text


def test_report_includes_skipped_borders(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme(skipped_borders=("BORDERLESS", "FIXED_SIZE"))
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    assert "BORDERLESS" in text
    assert "FIXED_SIZE" in text


def test_report_includes_notes_in_approximated(tmp_path: Path) -> None:
    from themey.report import write

    note = "TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped"
    theme = _make_theme(notes=[note])
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    assert note in text


def test_report_phase1_scaffold_section_for_phase2_3(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    # Should mention that color/wallpaper/cursor is deferred to later phases
    assert any(kw in text for kw in ("Phase 2", "Phase 3", "later phase"))


def test_report_includes_scale_note(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    # Scale quality note should mention fractional scales
    assert "fractional" in text.lower() or "1.25" in text or "1.5" in text
