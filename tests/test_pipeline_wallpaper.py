"""Tests for pipeline.convert's wallpaper package install (Phase B / B4)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import themey.pipeline as pipeline_mod
from themey.analyze.wallpaper import FILL_MODES
from themey.generate.wallpaper import WallpaperError
from themey.generate.wallpaper import write_package as real_write_package
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
    assert meta["X-Themey-FillMode"] in FILL_MODES
    assert meta["KPlugin"]["Id"] == d.name
    assert d.name.startswith("themey_Aliens_")


def test_pipeline_theme_with_no_wallpapers_installs_none(fake_home):
    # tiny.etheme has no desktops.cfg backgrounds at all. (OPENSTEP now
    # yields a solid-only wallpaper from its SET_SOLID.)
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="svg")
    assert result.wallpaper_dirs == ()
    assert not (fake_home / ".local/share/wallpapers").exists()


def test_pipeline_openstep_solid_wallpaper_installed(fake_home):
    """OPENSTEP's SET_SOLID("200 200 200") becomes its one (default)
    wallpaper package instead of zero-wallpaper output."""
    result = convert(FIXTURES / "OPENSTEP.etheme", scale=2, backend="svg")
    assert len(result.wallpaper_dirs) == 1
    meta = json.loads((result.wallpaper_dirs[0] / "metadata.json").read_text())
    assert meta["X-Themey-FillMode"] == "stretch"


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
    result = convert(FIXTURES / "tiny.etheme", scale=2, backend="svg")
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


# --------------------------------------------------------------------- #
# WallpaperError mid-pipeline (review fix round 1, Important #1)
# --------------------------------------------------------------------- #


def _fail_one_wallpaper(failing_stem: str):
    """A write_wallpaper_package stand-in that fails for one spec, and
    otherwise delegates to the real writer."""

    def _flaky(theme, spec, pkg_dir):
        if spec.path.stem == failing_stem:
            raise WallpaperError("synthetic failure for test")
        return real_write_package(theme, spec, pkg_dir)

    return _flaky


def test_pipeline_wallpaper_error_installed_count_matches_wallpaper_dirs(
    fake_home, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        pipeline_mod, "write_wallpaper_package", _fail_one_wallpaper("giger045")
    )
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert len(result.wallpaper_dirs) == 3
    for d in result.wallpaper_dirs:
        assert d.is_dir()


def test_pipeline_wallpaper_error_report_reflects_actual_installed_count(
    fake_home, monkeypatch: pytest.MonkeyPatch
):
    """The Preserved-section count must match what's actually on disk, not
    the full set discovered at analysis time (review finding Important #1)."""
    monkeypatch.setattr(
        pipeline_mod, "write_wallpaper_package", _fail_one_wallpaper("giger045")
    )
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    text = result.report_path.read_text()
    assert len(result.wallpaper_dirs) == 3
    assert "3 of 4" in text
    assert "- Wallpaper: 4 background image(s) installed" not in text
    assert "wallpaper: skipped giger045" in text


def test_pipeline_wallpaper_error_all_fail_report_says_none_converted(
    fake_home, monkeypatch: pytest.MonkeyPatch
):
    def _always_fail(theme, spec, pkg_dir):
        raise WallpaperError("synthetic failure for test")

    monkeypatch.setattr(pipeline_mod, "write_wallpaper_package", _always_fail)
    result = convert(FIXTURES / "Aliens.etheme", scale=2, backend="svg")
    assert result.wallpaper_dirs == ()
    text = result.report_path.read_text()
    assert "none could be converted" in text
    assert "installed as Plasma wallpaper packages" not in text
