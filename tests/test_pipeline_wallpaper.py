"""Tests for pipeline.convert's wallpaper package install (Phase B / B4)."""
from __future__ import annotations

import json
from pathlib import Path

from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"


def test_pipeline_installs_one_wallpaper_package_per_image(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert len(result.wallpaper_dirs) == 4
    for d in result.wallpaper_dirs:
        assert d.is_dir()
        assert d.parent == fake_home / ".local/share/wallpapers"
        assert (d / "metadata.json").is_file()
        images = list((d / "contents" / "images").glob("*"))
        assert len(images) == 1


def test_pipeline_wallpaper_metadata_has_fill_mode_and_id(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert result.wallpaper_dirs
    d = result.wallpaper_dirs[0]
    meta = json.loads((d / "metadata.json").read_text())
    assert meta["X-Themey-FillMode"] in ("tiled", "scaled")
    assert meta["KPlugin"]["Id"] == d.name
    assert d.name.startswith("themey_Aliens_")


def test_pipeline_theme_with_no_wallpapers_installs_none(fake_home):
    result = convert(FIXTURES / "OPENSTEP.etheme", scale=2, backend="svg")
    assert result.wallpaper_dirs == ()
    assert not (fake_home / ".local/share/wallpapers").exists()


def test_pipeline_output_dir_mode_writes_wallpaper_packages(tmp_path, fake_home):
    out = tmp_path / "out"
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg", output_dir=out)
    assert len(result.wallpaper_dirs) == 4
    for d in result.wallpaper_dirs:
        assert d.parent == out
        assert (d / "metadata.json").is_file()
    # Non-installing mode must not touch XDG paths.
    assert not (fake_home / ".local/share/wallpapers").exists()


def test_pipeline_report_mentions_wallpaper_packages(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    text = result.report_path.read_text()
    assert "Plasma wallpaper packages" in text


def test_pipeline_report_no_wallpapers_case(fake_home):
    result = convert(FIXTURES / "OPENSTEP.etheme", scale=2, backend="svg")
    text = result.report_path.read_text()
    assert "no background images found" in text


def test_pipeline_idempotent_rerun_reinstalls_wallpapers(fake_home):
    r1 = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    r2 = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert len(r1.wallpaper_dirs) == len(r2.wallpaper_dirs) == 4
    for d in r2.wallpaper_dirs:
        assert d.is_dir()
        backup = d.with_name(f"{d.name}.themey-old")
        assert not backup.exists()
