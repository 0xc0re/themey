"""Pipeline / install / CLI wiring for the QML decoration backend."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
E13 = FIXTURES / "e13.etheme"

needs_e13 = pytest.mark.skipif(not E13.exists(), reason="e13.etheme unavailable")


@needs_e13
def test_convert_backend_qml_installs_package(fake_home):
    from themey import paths
    from themey.pipeline import convert

    result = convert(E13, scale=2, backend="qml")
    assert result.qml_plugin_id == "themey_e13"
    pkg = paths.kwin_decorations() / "themey_e13"
    assert result.qml_installed_dir == pkg == result.installed_dir
    assert (pkg / "metadata.json").is_file()
    assert (pkg / "contents" / "ui" / "main.qml").is_file()
    # SVG theme must NOT be emitted on backend="qml" (chris's decision).
    assert not (paths.aurorae_themes() / "e13").exists()
    report = result.report_path.read_text()
    assert "Backend: qml" in report
    assert "resize shape over side-border buttons" in report
    assert "org.kde.kwin.aurorae" in report


@needs_e13
def test_convert_backend_both_installs_both(fake_home):
    from themey import paths
    from themey.pipeline import convert

    result = convert(E13, scale=2, backend="both")
    assert result.installed_dir == paths.aurorae_themes() / "e13"
    assert result.qml_installed_dir == paths.kwin_decorations() / "themey_e13"
    assert (result.installed_dir / "decoration.svg").is_file()
    assert (result.qml_installed_dir / "contents" / "ui" / "theme.js").is_file()


@needs_e13
def test_convert_backend_svg_unchanged(fake_home):
    from themey.pipeline import convert

    result = convert(E13, scale=2, backend="svg")
    assert result.qml_installed_dir is None
    assert result.qml_plugin_id is None
    assert (result.installed_dir / "decoration.svg").is_file()


@needs_e13
def test_convert_output_dir_qml(tmp_path):
    from themey.pipeline import convert

    out = tmp_path / "out"
    result = convert(E13, scale=2, output_dir=out, backend="qml")
    assert not result.installed
    pkg = out / "themey_e13"
    assert result.qml_installed_dir == pkg
    meta = json.loads((pkg / "metadata.json").read_text())
    assert meta["KPlugin"]["Id"] == "themey_e13"


def test_convert_rejects_unknown_backend(tmp_path):
    from themey.pipeline import convert

    with pytest.raises(ValueError, match="backend"):
        convert(E13, backend="gtk")


def test_deploy_target_root(tmp_path, fake_home):
    from themey import install, paths

    src = tmp_path / "stage" / "pkg"
    src.mkdir(parents=True)
    (src / "metadata.json").write_text("{}")
    target_root = paths.kwin_decorations()
    final = install.deploy("themey_x", src, target_root=target_root)
    assert final == target_root / "themey_x"
    assert (final / "metadata.json").is_file()


@needs_e13
def test_cli_backend_flag(tmp_path):
    from typer.testing import CliRunner

    from themey.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app, ["convert", str(E13), "--backend", "qml", "-o", str(tmp_path / "o"), "--no-open"]
    )
    assert result.exit_code == 0, result.output
    assert "themey_e13" in result.output
