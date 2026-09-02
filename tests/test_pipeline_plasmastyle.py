"""Tests for pipeline.convert's Plasma Style (desktop theme) assembly.

Aliens is the canary: it carries every mapped iclass (dragbar, MENU_BG,
TT_MAIN, DIALOG_BUTTON, MENU_SEL, ICONBOX scrollbar + arrows), so the full
SVG set ships. Unit-level builder behavior lives in ``test_plasmastyle.py``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

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
    plasmastyle.PAGER_SVG,  # Aliens has PAGER_SEL/PAGER_BACKGROUND art
    plasmastyle.DRAGBAR_SVG,  # DESKTOP_RAISE/LOWERBUTTON_HORIZ desk buttons
    # Dialog-widget art: Aliens carries every source iclass (check/radio
    # w/ checked _ACTIVE art, slider bases + knobs, separator, AREA).
    plasmastyle.CHECKMARKS_SVG,
    plasmastyle.RADIOBUTTON_SVG,
    plasmastyle.SLIDER_SVG,
    plasmastyle.LINE_SVG,
    plasmastyle.FRAME_SVG,
    plasmastyle.TASKS_SVG,  # DEFAULT_ICON_BUTTON / DEFAULT_DOCK_BUTTON art
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
    # Aliens' panel is real art (its ICONBOX_HORIZONTAL passes the guards
    # after the wordmark-capped dragbar is rejected), so even the panel
    # mirrors byte-identically; only a tint panel gets re-rendered opaque.
    for rel in shipped:
        original = (style_dir / rel).read_bytes()
        for variant in ("solid", "opaque"):
            mirrored = (style_dir / variant / rel).read_bytes()
            if rel == plasmastyle.PANEL_SVG:
                assert b"<image" in original  # art, not tint
            assert mirrored == original


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


def test_pager_ships_from_art_without_wallpapers(fake_home, tmp_path):
    """OPENSTEP carries no backgrounds but does have PAGER_SEL art — the
    pager is pure theme art now (no baked wallpaper minis), so it ships
    regardless of wallpapers."""
    out = tmp_path / "out"
    result = convert(
        FIXTURES / "OPENSTEP.etheme", scale=2, backend="qml", output_dir=out
    )
    style_dir = out / "desktoptheme" / plugin_id("OPENSTEP")
    assert result.desktop_theme_dir == style_dir
    assert (style_dir / plasmastyle.PAGER_SVG).is_file()
    assert (style_dir / plasmastyle.PANEL_SVG).is_file()


def test_style_failure_is_non_fatal_with_note(fake_home, tmp_path, monkeypatch):
    from themey import pipeline

    def boom(theme, out_dir, **kwargs):
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


def test_install_mode_clears_stale_style_cache(fake_home, monkeypatch, tmp_path):
    """A re-convert without a re-apply must not keep painting the previous
    conversion's panel art from the Version-keyed kcache."""
    cache = tmp_path / "xdg-cache"
    cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    stale = cache / f"plasma_theme_{plugin_id('Aliens')}_v1.0.kcache"
    stale.write_bytes(b"stale")
    other = cache / "plasma_theme_themey_e13_v1.0.kcache"
    other.write_bytes(b"keep")
    convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    assert not stale.exists()
    assert other.exists()  # other themes' caches are left alone


def test_output_dir_mode_leaves_style_cache_alone(fake_home, monkeypatch, tmp_path):
    cache = tmp_path / "xdg-cache"
    cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    stale = cache / f"plasma_theme_{plugin_id('Aliens')}_v1.0.kcache"
    stale.write_bytes(b"stale")
    convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml",
        output_dir=tmp_path / "out",
    )
    assert stale.exists()


def test_aliens_viewitem_caps_clamped(fake_home, tmp_path):
    """Aliens' MENU_SEL hover art (n_menu_h.png) is an opaque 203x31
    rectangle — a vertical glow gradient — declaring __EDGE_SCALING
    2 2 2 2. It is a rectangular strip, not a rounded pill, so the
    declared 2 px caps are honored (E16 kept exactly those crisp and
    stretched the glow to the row) rather than the cross-section radius
    pin; every cap stays under VIEWITEM_MAX_REF_CAP."""
    import xml.etree.ElementTree as ET

    from themey.generate.qmldeco.resolver import scale_px

    out = tmp_path / "out"
    result = convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml", output_dir=out
    )
    assert result.desktop_theme_dir is not None
    root = ET.parse(result.desktop_theme_dir / plasmastyle.VIEWITEM_SVG).getroot()
    ns = "{http://www.w3.org/2000/svg}"
    dims = {
        g.get("id"): (int(img.get("width", "0")), int(img.get("height", "0")))
        for g in root.iter(f"{ns}g")
        if (img := g.find(f"{ns}image")) is not None
    }
    limit = scale_px(plasmastyle.VIEWITEM_MAX_REF_CAP, 2)
    declared = scale_px(2, 2)
    assert dims["hover-left"][0] == dims["hover-right"][0] == declared <= limit
    assert dims["hover-top"][1] == dims["hover-bottom"][1] == declared <= limit


def test_convert_rejects_bad_iconbox_frames(fake_home, tmp_path):
    with pytest.raises(ValueError, match="iconbox_frames"):
        convert(
            FIXTURES / "Aliens.etheme", scale=2, backend="qml",
            output_dir=tmp_path / "out", iconbox_frames="bogus",
        )


def test_convert_iconbox_frames_off_ships_blank_tasks(fake_home, tmp_path):
    import json

    out = tmp_path / "out"
    result = convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml", output_dir=out,
        iconbox_frames="off",
    )
    assert result.desktop_theme_dir is not None
    tasks = result.desktop_theme_dir / "widgets" / "tasks.svg"
    assert "opacity:0" in tasks.read_text()
    assert any("task frames OFF" in n for n in result.notes)
    meta = json.loads((result.desktop_theme_dir / "metadata.json").read_text())
    assert isinstance(meta["X-Themey-TasksHover"], bool)


def test_convert_default_iconbox_frames_is_off(fake_home, tmp_path):
    """The convert default flipped to E16's own frameless iconbox
    (container.c draw_icon_base = 0) — a plate under every icon on the
    bottom bar was Plasma's look, not E16's."""
    import json

    result = convert(
        FIXTURES / "Aliens.etheme", scale=2, backend="qml",
        output_dir=tmp_path / "out",
    )
    assert result.desktop_theme_dir is not None
    tasks = result.desktop_theme_dir / "widgets" / "tasks.svg"
    text = tasks.read_text()
    assert "task frames OFF" in "\n".join(result.notes)
    # The synthesized states survive frames-OFF: a white hover wash and
    # the scheme-coloured accent bar on the active task.
    assert 'id="hover-center"' in text and "fill:#ffffff" in text
    assert 'class="ColorScheme-Highlight"' in text
    assert 'id="current-color-scheme"' in text
    meta = json.loads((result.desktop_theme_dir / "metadata.json").read_text())
    assert meta["X-Themey-TasksHover"] is True
