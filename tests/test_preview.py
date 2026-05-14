"""Tests for themey.preview.render — HTML preview generator."""
from __future__ import annotations

from pathlib import Path


def _make_theme(
    notes: list[str] | None = None,
    skipped_borders: tuple[str, ...] = (),
    display_name: str = "Test Theme",
):
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
        display_name=display_name,
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


def test_preview_writes_valid_html(tmp_path: Path) -> None:
    from themey.preview import render

    theme = _make_theme()
    out = tmp_path / "preview.html"
    render(theme, out)
    text = out.read_text().lower()
    assert out.stat().st_size > 0
    assert "<!doctype html>" in text
    assert "</html>" in text


def test_preview_includes_theme_name(tmp_path: Path) -> None:
    from themey.preview import render

    theme = _make_theme(display_name="My Cool Theme")
    out = tmp_path / "preview.html"
    render(theme, out)
    text = out.read_text()
    assert "My Cool Theme" in text


def test_preview_includes_activation_instructions(tmp_path: Path) -> None:
    from themey.preview import render

    theme = _make_theme()
    out = tmp_path / "preview.html"
    render(theme, out)
    text = out.read_text()
    assert "System Settings" in text
    assert "Window Decorations" in text


def test_preview_escapes_html_in_notes(tmp_path: Path) -> None:
    from themey.preview import render

    theme = _make_theme(notes=["<script>alert(1)</script>"])
    out = tmp_path / "preview.html"
    render(theme, out)
    text = out.read_text()
    # Raw script tag should NOT appear
    assert "<script>alert(1)</script>" not in text
    # Escaped form should appear
    assert "&lt;script&gt;" in text


def test_preview_includes_qdbus_reload_command(tmp_path: Path) -> None:
    from themey.preview import render

    theme = _make_theme()
    out = tmp_path / "preview.html"
    render(theme, out)
    text = out.read_text()
    assert "qdbus org.kde.KWin /KWin reconfigure" in text


def test_preview_includes_notes_count(tmp_path: Path) -> None:
    from themey.preview import render

    notes = ["note one", "note two", "note three"]
    theme = _make_theme(notes=notes)
    out = tmp_path / "preview.html"
    render(theme, out)
    text = out.read_text()
    assert "3" in text
