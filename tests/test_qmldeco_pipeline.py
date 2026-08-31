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
    assert "arrow over every themed button" in report
    assert "resize shape over side-border" not in report
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


# ---------------------------------------------------------------------------
# Fractional scale (QML-backend-only)

def _theme_js(pkg: Path) -> dict:
    import re

    src = (pkg / "contents" / "ui" / "theme.js").read_text()
    m = re.search(r"var theme = (\{.*\});", src, re.S)
    assert m
    return json.loads(m.group(1))


@needs_e13
def test_convert_fractional_scale_qml(tmp_path):
    from themey.generate.qmldeco.resolver import scale_px
    from themey.pipeline import convert

    out = tmp_path / "out"
    convert(E13, scale=1.5, output_dir=out, backend="qml")
    data = _theme_js(out / "themey_e13")
    assert data["scale"] == 1.5
    # e13 ref borders 40/6/46/6 through scale_px at 1.5.
    assert data["borders"] == {"left": 60, "right": 9, "top": 69, "bottom": 9}
    by_id = {p["id"]: p for p in data["parts"]}
    # FIN's declared right edge_scaling 129 → scale_px(129, 1.5) = 194.
    assert by_id["FIN"]["insets"]["right"] == scale_px(129, 1.5) == 194
    # All insets and pixel sizes are ints (QML border.* wants ints).
    for p in data["parts"]:
        assert all(isinstance(v, int) for v in p["insets"].values()), p["id"]
        if p["text"] is not None:
            assert isinstance(p["text"]["pixelSize"], int)


@needs_e13
@pytest.mark.parametrize("backend", ["svg", "both"])
def test_convert_fractional_scale_rejected_for_svg(tmp_path, backend):
    from themey.pipeline import convert

    with pytest.raises(ValueError, match="integer"):
        convert(E13, scale=1.5, output_dir=tmp_path / "out", backend=backend)


@needs_e13
@pytest.mark.parametrize("scale", [0.5, 0.99, 3.5, 4])
def test_convert_scale_out_of_range_rejected(tmp_path, scale):
    from themey.pipeline import convert

    with pytest.raises(ValueError, match="scale"):
        convert(E13, scale=scale, output_dir=tmp_path / "out", backend="qml")


@needs_e13
def test_convert_scale_quantized_and_int_normalized(tmp_path):
    from themey.pipeline import convert

    out = tmp_path / "out"
    convert(E13, scale=1.4999999, output_dir=out, backend="qml")
    assert _theme_js(out / "themey_e13")["scale"] == 1.5

    out2 = tmp_path / "out2"
    convert(E13, scale=2.0, output_dir=out2, backend="qml")
    # Integer-valued floats normalize to int so theme.js stays byte-stable
    # (json emits 2, not 2.0 — round-tripping yields an int).
    scale = _theme_js(out2 / "themey_e13")["scale"]
    assert scale == 2 and isinstance(scale, int)


# ---------------------------------------------------------------------------
# --upscale quality (QML-backend-only)

@needs_e13
def test_convert_upscale_quality_qml(tmp_path):
    from themey.pipeline import convert

    out = tmp_path / "out"
    convert(E13, scale=1.5, output_dir=out, backend="qml", upscale="quality")
    imgs = list((out / "themey_e13" / "contents" / "images").glob("*.png"))
    assert imgs


@needs_e13
@pytest.mark.parametrize("backend", ["svg", "both"])
def test_convert_upscale_quality_rejected_for_svg(tmp_path, backend):
    from themey.pipeline import convert

    with pytest.raises(ValueError, match="upscale"):
        convert(
            E13, scale=2, output_dir=tmp_path / "o", backend=backend,
            upscale="quality",
        )


@needs_e13
def test_convert_rejects_unknown_upscale(tmp_path):
    from themey.pipeline import convert

    with pytest.raises(ValueError, match="upscale"):
        convert(E13, scale=2, output_dir=tmp_path / "o", upscale="bicubic")


# ---------------------------------------------------------------------------
# --shade-button remap (Phase F / Task 6)

@needs_e13
def test_convert_shade_button_threaded_to_qml_package(tmp_path):
    from themey.pipeline import convert

    out = tmp_path / "out"
    convert(E13, scale=2, output_dir=out, backend="qml", shade_button="keepAbove")
    data = _theme_js(out / "themey_e13")
    by_id = {p["id"]: p for p in data["parts"]}
    assert by_id["BUTTON_SHADE"]["button"] == "keepAbove"


@needs_e13
def test_convert_shade_button_default_is_maximize(tmp_path):
    from themey.pipeline import convert

    out = tmp_path / "out"
    convert(E13, scale=2, output_dir=out, backend="qml")
    data = _theme_js(out / "themey_e13")
    by_id = {p["id"]: p for p in data["parts"]}
    assert by_id["BUTTON_SHADE"]["button"] == "maximizeRestore"


@needs_e13
def test_convert_rejects_unknown_shade_button(tmp_path):
    from themey.pipeline import convert

    with pytest.raises(ValueError, match="shade_button"):
        convert(
            E13, scale=2, output_dir=tmp_path / "o", shade_button="bogus"
        )


@needs_e13
def test_convert_shade_button_svg_backend_untouched(tmp_path):
    """The flag is QML-backend-only: an svg-only convert must not error on
    any --shade-button value, and the SVG theme output is identical
    regardless of the flag (it never consumes it)."""
    from themey.pipeline import convert

    out_default = tmp_path / "default"
    out_hide = tmp_path / "hide"
    convert(E13, scale=2, output_dir=out_default, backend="svg")
    convert(
        E13, scale=2, output_dir=out_hide, backend="svg", shade_button="hide"
    )
    default_rc = (out_default / "e13" / "e13rc").read_text()
    hide_rc = (out_hide / "e13" / "e13rc").read_text()
    assert default_rc == hide_rc
