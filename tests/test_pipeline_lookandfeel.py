"""Tests for pipeline.convert's Look-and-Feel bundle assembly (Phase D / D3)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from themey.pipeline import convert
from themey.slug import cursor_theme_dir, plugin_id

FIXTURES = Path(__file__).parent / "fixtures"

needs_xcursorgen = __import__("pytest").mark.skipif(
    shutil.which("xcursorgen") is None, reason="xcursorgen not installed"
)


def test_pipeline_installs_the_bundle_under_look_and_feel(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    assert result.lnf_id == plugin_id("Aliens")
    assert result.lnf_dir is not None
    assert result.lnf_dir == fake_home / ".local/share/plasma/look-and-feel" / plugin_id(
        "Aliens"
    )
    assert (result.lnf_dir / "metadata.json").is_file()
    assert (result.lnf_dir / "contents" / "defaults").is_file()


def test_bundle_metadata_id_equals_dirname(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    meta = json.loads((result.lnf_dir / "metadata.json").read_text())
    assert meta["KPackageStructure"] == "Plasma/LookAndFeel"
    assert meta["KPlugin"]["Id"] == result.lnf_dir.name == result.lnf_id


def test_bundle_defaults_reference_colors_and_wallpaper(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    assert result.color_scheme_path is not None
    assert result.wallpaper_dirs
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert f"ColorScheme={result.color_scheme_path.stem}" in text
    assert "[Wallpaper]" in text
    # The referenced Image= id must be one of the ACTUALLY installed
    # wallpaper packages, never a leftover from analysis alone.
    installed_ids = {d.name for d in result.wallpaper_dirs}
    ref = next(ln for ln in text.splitlines() if ln.startswith("Image="))
    assert ref.split("=", 1)[1] in installed_ids


def test_bundle_defaults_deco_group_matches_qml_package(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert "[kwinrc][org.kde.kdecoration2]" in text
    assert "library=org.kde.kwin.aurorae\n" in text
    assert f"theme={result.qml_plugin_id}" in text


def test_bundle_defaults_deco_group_matches_svg_theme_when_svg_only(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert "library=org.kde.kwin.aurorae.v2" in text
    assert "theme=__aurorae__svg__Aliens" in text


def test_bundle_omits_wallpaper_group_for_theme_with_none(fake_home):
    # tiny.etheme has no backgrounds; OPENSTEP now ships a solid wallpaper.
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")
    assert result.wallpaper_dirs == ()
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert "[Wallpaper]" not in text


def test_bundle_omits_cursor_key_for_theme_with_none(fake_home):
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")
    assert result.cursor_theme_dir is None
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert "[kcminputrc][Mouse]" not in text


@needs_xcursorgen
def test_bundle_references_installed_cursor_theme(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    assert result.cursor_theme_dir is not None
    text = (result.lnf_dir / "contents" / "defaults").read_text()
    assert f"cursorTheme={cursor_theme_dir('Aliens')}" in text


def test_bundle_zero_symlinks(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    assert not any(p.is_symlink() for p in result.lnf_dir.rglob("*"))


def test_pipeline_idempotent_rerun_reinstalls_bundle(fake_home):
    r1 = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    r2 = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    assert r1.lnf_dir == r2.lnf_dir
    assert r2.lnf_dir.is_dir()
    backup = r2.lnf_dir.with_name(f"{r2.lnf_dir.name}.themey-old")
    assert not backup.exists()


def test_output_dir_mode_writes_bundle_without_colliding_with_qml_package(
    tmp_path, fake_home
):
    out = tmp_path / "out"
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml", output_dir=out)
    assert result.qml_installed_dir == out / plugin_id("Aliens")
    assert result.qml_installed_dir.is_dir()
    assert result.lnf_dir == out / "look-and-feel" / plugin_id("Aliens")
    assert (result.lnf_dir / "metadata.json").is_file()
    # Both trees survive distinctly -- no file from one clobbered the other.
    assert (result.qml_installed_dir / "contents" / "ui" / "theme.js").is_file()
    assert (result.lnf_dir / "contents" / "defaults").is_file()
    assert not (fake_home / ".local/share/plasma").exists()


def test_report_mentions_the_global_theme(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="qml")
    text = result.report_path.read_text()
    assert result.lnf_id in text
    assert "themey apply Aliens" in text
    assert "--deco-only" in text


def test_cli_prints_global_theme_line(fake_home, monkeypatch):
    from typer.testing import CliRunner

    from themey.cli import app

    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(app, [str(FIXTURES / "Aliens.etheme")])
    assert result.exit_code == 0, result.output
    assert f"Global theme: {plugin_id('Aliens')} — apply: themey apply Aliens" in result.output
