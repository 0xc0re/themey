"""Tests for themey.report.write — report.txt scaffold."""
from __future__ import annotations

from pathlib import Path

from themey.report import write


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


def test_report_no_longer_defers_the_bundle(tmp_path: Path) -> None:
    """The Phase D bundle shipped; the old "deferred to later phase" /
    BUNDLE-01 placeholder must be gone."""
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    assert "deferred to later phase" not in text
    assert "BUNDLE-01" not in text


def test_report_mentions_the_bundle_when_lnf_id_given(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out, lnf_id="themey_TestTheme", lnf_dir=tmp_path / "themey_TestTheme")
    text = out.read_text()
    preserved = text.split("## Approximated")[0]
    assert "themey_TestTheme" in preserved
    assert "Global Theme" in preserved
    apply_section = text.split("## Apply")[1]
    assert "themey apply TestTheme" in apply_section
    assert "themey_TestTheme" in apply_section
    assert "--deco-only" in apply_section


def test_report_omits_bundle_lines_when_lnf_id_is_none(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    assert "Global Theme" not in text


def test_report_svg_only_backend_does_not_recommend_bare_full_apply(
    tmp_path: Path,
) -> None:
    """backend='svg' never installs the QML deco package apply_full()
    requires, so the report must not point at bare `themey apply NAME`."""
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(
        theme, out, backend="svg",
        lnf_id="themey_TestTheme", lnf_dir=tmp_path / "themey_TestTheme",
    )
    text = out.read_text()
    apply_section = text.split("## Apply")[1]
    assert "applies the full Global Theme" not in apply_section
    assert "themey apply TestTheme --deco-only --backend svg" in apply_section
    assert "themey_TestTheme" in apply_section


def test_report_svg_border_size_advice_uses_deco_only(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    text = write(theme, tmp_path / "r.txt", backend="svg").read_text()
    assert "themey apply TestTheme --deco-only --backend svg" in text


def test_report_preserves_the_color_scheme(tmp_path: Path) -> None:
    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    preserved = out.read_text().split("## Approximated")[0]
    assert "Color scheme sampled" in preserved
    assert "Test Theme (themey)" in preserved


def test_report_surfaces_colors_notes_before_the_state_bucket(tmp_path: Path) -> None:
    """``colors:`` notes are layout decisions, not dropped-state noise.

    The state-drop bucket truncates at 20 entries, so a colors note binned
    into it could be silently cut from the report.
    """
    note = "colors: desktop backgrounds tinted from iclass BORDER_LEFT (normal)"
    theme = _make_theme(notes=[note, *[f"drop {i}" for i in range(30)]])
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    assert note in text
    assert text.index(note) < text.index("8-state image model collapsed")


def test_report_includes_scale_note(tmp_path: Path) -> None:
    from themey.report import write

    theme = _make_theme()
    out = tmp_path / "report.txt"
    write(theme, out)
    text = out.read_text()
    # Scale quality note should mention fractional scales
    assert "fractional" in text.lower() or "1.25" in text or "1.5" in text


def test_report_apply_section_mentions_border_size_clamp(tmp_path: Path) -> None:
    theme = _make_theme()
    text = write(theme, tmp_path / "r.txt").read_text()
    assert "## Apply" in text
    assert "Oversized" in text
    assert "Border size =" in text and "themey apply" in text
