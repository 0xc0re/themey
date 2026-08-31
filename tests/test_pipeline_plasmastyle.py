"""Tests for pipeline.convert's Plasma Style (desktop theme) assembly.

Aliens is the canary: it carries every mapped iclass (dragbar, MENU_BG,
TT_MAIN, DIALOG_BUTTON, MENU_SEL, ICONBOX scrollbar + arrows), so the full
SVG set ships. Unit-level builder behavior lives in ``test_plasmastyle.py``.
"""
from __future__ import annotations

from pathlib import Path

from themey.generate import plasmastyle
from themey.pipeline import convert
from themey.slug import plugin_id

FIXTURES = Path(__file__).parent / "fixtures"

ALIENS_EXPECTED_SVGS = {
    plasmastyle.PANEL_SVG,
    plasmastyle.DIALOG_SVG,
    plasmastyle.TOOLTIP_SVG,
    plasmastyle.BUTTON_SVG,
    plasmastyle.VIEWITEM_SVG,
    plasmastyle.SCROLLBAR_SVG,
    plasmastyle.ARROWS_SVG,
}


def test_output_dir_mode_writes_style_under_desktoptheme(fake_home, tmp_path):
    out = tmp_path / "out"
    result = convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml", output_dir=out
    )
    style_dir = out / "desktoptheme" / plugin_id("Aliens")
    assert result.desktop_theme_dir == style_dir
    assert result.desktop_theme_id == plugin_id("Aliens")
    assert (style_dir / "metadata.json").is_file()
    assert (style_dir / "plasmarc").is_file()
    assert (style_dir / "colors").is_file()
    shipped = {
        str(p.relative_to(style_dir))
        for p in style_dir.rglob("*.svg")
        if p.relative_to(style_dir).parts[0] not in ("solid", "opaque")
    }
    assert shipped == ALIENS_EXPECTED_SVGS
    # Mirrors: every shipped SVG is byte-identical under solid/ + opaque/.
    for rel in shipped:
        original = (style_dir / rel).read_bytes()
        assert (style_dir / "solid" / rel).read_bytes() == original
        assert (style_dir / "opaque" / rel).read_bytes() == original


def test_output_dir_defaults_reference_the_style(fake_home, tmp_path):
    out = tmp_path / "out"
    result = convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml", output_dir=out
    )
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert "[plasmarc][Theme]" in text
    assert f"name={plugin_id('Aliens')}" in text


def test_install_mode_deploys_style_to_xdg(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    expected = (
        fake_home / ".local/share/plasma/desktoptheme" / plugin_id("Aliens")
    )
    assert result.desktop_theme_dir == expected
    assert (expected / "metadata.json").is_file()
    assert (expected / "colors").is_file()


def test_style_failure_is_non_fatal_with_note(fake_home, tmp_path, monkeypatch):
    from themey import pipeline

    def boom(theme, out_dir):
        raise plastyle_err

    plastyle_err = plasmastyle.PlasmaStyleError("style exploded")
    monkeypatch.setattr(pipeline, "write_plasma_style", boom)
    out = tmp_path / "out"
    result = convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml", output_dir=out
    )
    assert result.desktop_theme_dir is None
    assert result.desktop_theme_id is None
    report = result.report_path.read_text()
    assert "plasmastyle: skipped: style exploded" in report
    # The bundle must not reference a style that never installed.
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert "[plasmarc][Theme]" not in text
