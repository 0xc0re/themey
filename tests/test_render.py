"""Tests for the headless nested-KWin render harness (themey render).

The end-to-end test is skipped unless kwin_wayland + spectacle + kdialog
are installed; the kwinrc/kwinrulesrc writers are always tested.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from themey import render

FIXTURES = Path(__file__).parent / "fixtures"


def test_write_kwinrc_legacy_and_v2(tmp_path):
    p = render.write_kwinrc(tmp_path, name="Aliens", plugin="legacy", border_size="Normal")
    txt = p.read_text()
    assert "library=org.kde.kwin.aurorae\n" in txt
    assert "theme=__aurorae__svg__Aliens" in txt
    p = render.write_kwinrc(tmp_path, name="Aliens", plugin="v2", border_size="Oversized")
    txt = p.read_text()
    assert "library=org.kde.kwin.aurorae.v2\n" in txt
    assert "BorderSize=Oversized" in txt


def test_write_kwinrc_rejects_bad_args(tmp_path):
    with pytest.raises(render.RenderError):
        render.write_kwinrc(tmp_path, name="x", plugin="v3", border_size="Normal")
    with pytest.raises(render.RenderError):
        render.write_kwinrc(tmp_path, name="x", plugin="v2", border_size="Gigantic")


def test_write_kwinrulesrc_only_when_maximized(tmp_path):
    assert render.write_kwinrulesrc(tmp_path, maximized=False) is None
    p = render.write_kwinrulesrc(tmp_path, maximized=True)
    assert p is not None and "maximizevertrule=3" in p.read_text()


def test_resolve_theme_dir_unknown(tmp_path, fake_home):
    with pytest.raises(render.RenderError):
        render.resolve_theme_dir("definitely-not-installed", scale=2, work=tmp_path)


@pytest.mark.skipif(not render.available(), reason=f"missing: {render.missing_tools()}")
def test_render_aliens_headless(tmp_path):
    out = tmp_path / "aliens.png"
    png = render.render(str(FIXTURES / "Aliens.etheme"), out=out, plugin="legacy")
    assert png == out and png.is_file()
    assert png.stat().st_size > 5_000
    with Image.open(png) as im:
        assert im.size == (render.SCREEN_W, render.SCREEN_H)
        rgba = im.convert("RGBA")
    # A decorated client window should paint a meaningful share of the screen
    # with non-background pixels; sample the centre band where kdialog sits.
    w, h = rgba.size
    band = rgba.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
    px = list(band.getdata())
    bg = px[0]
    differing = sum(1 for p in px if abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 30)
    assert differing / len(px) > 0.05


def _style_tools_available() -> bool:
    import shutil

    return all(shutil.which(t) for t in render.REQUIRED_STYLE_TOOLS)


@pytest.mark.skipif(
    not _style_tools_available(),
    reason="style target needs kwin_wayland+spectacle+plasmoidviewer",
)
def test_render_style_aliens_headless(tmp_path):
    out = tmp_path / "aliens-style.png"
    png = render.render_style(str(FIXTURES / "Aliens.etheme"), out=out)
    assert png == out and png.is_file()
    assert png.stat().st_size > 5_000
    with Image.open(png) as im:
        assert im.size == (render.SCREEN_W, render.SCREEN_H)


def test_resolve_style_dir_unknown(tmp_path, fake_home):
    with pytest.raises(render.RenderError):
        render.resolve_style_dir("definitely-not-installed", scale=2, work=tmp_path)


def test_recommended_border_size_brackets():
    assert render.recommended_border_size(2, 2, 4) == "Tiny"
    assert render.recommended_border_size(6, 6, 5) == "Normal"
    assert render.recommended_border_size(8, 4, 20) == "Huge"
    assert render.recommended_border_size(48, 40, 48) == "Oversized"
    assert render.recommended_border_size(120, 0, 0) == "Oversized"
