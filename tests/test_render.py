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


def test_style_probe_paints_wide_and_tall_viewitem_cells(tmp_path):
    """The probe must show a viewitem hover cell stretched WIDE and a
    selected cell stretched TALL so an open end or an oversized cap is
    visible in the screenshot."""
    render._write_style_probe(tmp_path)
    qml = (
        tmp_path / "plasma" / "plasmoids" / render._STYLE_PROBE_ID
        / "contents" / "ui" / "main.qml"
    ).read_text()
    cells = dict(render._STYLE_PROBE_CELLS)
    assert cells.get("widgets/viewitem") is not None
    prefixes = {pre for path, pre in render._STYLE_PROBE_CELLS if path == "widgets/viewitem"}
    assert {"hover", "selected"} <= prefixes
    shapes = render._STYLE_PROBE_CELL_SHAPES
    assert shapes[("widgets/viewitem", "hover")] == "wide"
    assert shapes[("widgets/viewitem", "selected")] == "tall"
    assert '"shape": "wide"' in qml and '"shape": "tall"' in qml
    # The grid must hold every cell: rows x columns >= cells.
    assert render._STYLE_PROBE_ROWS * render._STYLE_PROBE_COLUMNS >= len(render._STYLE_PROBE_CELLS)


def _dock_tools_available() -> bool:
    import shutil

    return all(shutil.which(t) for t in (*render.REQUIRED_STYLE_TOOLS, "kdialog"))


@pytest.mark.skipif(
    not _dock_tools_available(),
    reason="dock target needs kwin_wayland+spectacle+plasmoidviewer+kdialog",
)
def test_render_dock_headless(tmp_path):
    out = tmp_path / "e13-dock.png"
    png = render.render_dock(str(FIXTURES / "e13.etheme"), out=out)
    assert png == out and png.is_file()
    assert png.stat().st_size > 5_000
    with Image.open(png) as im:
        assert im.size == (render.SCREEN_W, render.SCREEN_H)


def test_dock_viewer_args_are_a_bottom_edge_panel():
    """The dock target must host the applet in a HORIZONTAL bottom-edge
    panel containment, since the fork's zoom/rise math keys off the panel
    edge."""
    args = render._DOCK_VIEWER_ARGS
    assert args[:2] == ("-c", "org.kde.panel")
    assert "horizontal" in args and "bottomedge" in args
    assert f"{render.SCREEN_W}x" in args[args.index("-s") + 1]


def test_session_script_writes_one_kdialog_per_client(tmp_path):
    """``clients`` is a COUNT: the dock target wants two windows so the
    row shows a focused plate beside an unfocused one."""
    script = render._style_session_script(
        tmp_path, tmp_path / "o.png", tmp_path / "s.log",
        applet="org.themey.dock", clients=2,
    )
    txt = script.read_text()
    assert txt.count("kdialog ") == 2
    script = render._style_session_script(
        tmp_path, tmp_path / "o.png", tmp_path / "s.log",
        applet="org.themey.dock", clients=0,
    )
    assert "kdialog" not in script.read_text()


def test_resolve_plasmoid_dir_prefers_the_converted_package(tmp_path, fake_home):
    from themey.generate.plasmoids import DOCK_ID

    with pytest.raises(render.RenderError):
        render.resolve_plasmoid_dir(DOCK_ID, work=tmp_path)
    converted = tmp_path / "convert" / "plasmoids" / DOCK_ID
    converted.mkdir(parents=True)
    (converted / "metadata.json").write_text("{}", encoding="utf-8")
    assert render.resolve_plasmoid_dir(DOCK_ID, work=tmp_path) == converted


def test_dock_target_converts_with_visible_task_plates(tmp_path, monkeypatch):
    """The dock target must NOT use the pipeline's ``iconbox_frames``
    default: ``off`` ships a near-transparent wash that the nested
    session's black desktop cannot show, so the shot would be empty."""
    assert render._DOCK_RENDER_ICONBOX_FRAMES == "on"
    seen = {}

    def fake_convert(path, **kwargs):
        seen.update(kwargs)
        raise render.RenderError("stop here")

    monkeypatch.setattr(render, "convert", fake_convert)
    with pytest.raises(render.RenderError):
        render.render_dock(str(FIXTURES / "e13.etheme"), out=tmp_path / "d.png")
    assert seen["iconbox_frames"] == "on"
