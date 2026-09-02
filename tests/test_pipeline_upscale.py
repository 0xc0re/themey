"""Tests for pipeline.convert's --upscale handling.

The waifu2x mode is the only scaler that can be unavailable at run time,
so convert decides ONCE — right after build_theme, where theme.notes
exists — and hands the effective mode to both the generator and the
report. These tests pin that: a convert never fails for want of the
binary, the substitution is recorded, and the report can never name a
scaler that did not run.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from themey import external
from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"
E13 = FIXTURES / "e13.etheme"


def _convert(tmp_path: Path, upscale: str):
    return convert(E13, scale=2, backend="qml", upscale=upscale,
                   output_dir=tmp_path / "out")


def _report(result) -> str:
    assert result.report_path is not None
    return result.report_path.read_text()


# --------------------------------------------------------------------- #
# Fallback when the binary (or its models) is missing
# --------------------------------------------------------------------- #


def test_waifu2x_without_the_binary_still_converts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Graceful degradation, mirroring the cursor stage: the conversion
    succeeds and says what it did instead."""
    monkeypatch.setattr(
        external, "waifu2x_unavailable_reason",
        lambda *a, **k: "waifu2x-ncnn-vulkan is not on PATH",
    )
    result = _convert(tmp_path, "waifu2x")
    assert result.qml_installed_dir is not None
    assert any(n.startswith("upscale:") for n in result.notes)


def test_the_fallback_note_names_what_was_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Binary-present-models-missing is the state a fresh install lands
    in, so the note has to send the reader to the models rather than to
    the binary they can already see."""
    monkeypatch.setattr(
        external, "waifu2x_unavailable_reason",
        lambda *a, **k: (
            "waifu2x-ncnn-vulkan is on PATH but its models-cunet weights "
            "are not (looked beside the binary, in /usr/local/share/"
            "waifu2x-ncnn-vulkan/models-cunet)"
        ),
    )
    note = next(
        n for n in _convert(tmp_path, "waifu2x").notes if n.startswith("upscale:")
    )
    assert "models-cunet" in note
    assert "hqx instead" in note


def test_the_report_names_hqx_after_a_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The report line takes the EFFECTIVE mode, so it can never claim a
    scaler that did not run."""
    monkeypatch.setattr(
        external, "waifu2x_unavailable_reason",
        lambda *a, **k: "waifu2x-ncnn-vulkan is not on PATH",
    )
    text = _report(_convert(tmp_path, "waifu2x"))
    assert "with hqx (--upscale quality)." in text
    assert "waifu2x (--upscale waifu2x)" not in text
    assert "upscale: waifu2x-ncnn-vulkan is not on PATH" in text


def test_no_fallback_note_when_waifu2x_is_available(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """With the tool present nothing is substituted and nothing is noted.
    The scaler itself is stubbed so this runs without the binary."""
    monkeypatch.setattr(external, "waifu2x_unavailable_reason", lambda *a, **k: None)
    monkeypatch.setattr(
        "themey.images.upscale.waifu2x",
        lambda img, factor: img.resize(
            (img.width * factor, img.height * factor)
        ).convert("RGBA"),
    )
    result = _convert(tmp_path, "waifu2x")
    assert not any(n.startswith("upscale:") for n in result.notes)
    assert "with waifu2x (--upscale waifu2x)." in _report(result)


def test_nearest_and_quality_are_never_second_guessed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """The availability probe must not run for the in-tree scalers — they
    cannot be missing, and a probe there would be a latent bug."""
    def _boom(*a, **k):
        raise AssertionError("waifu2x availability probed for an in-tree mode")

    monkeypatch.setattr(external, "waifu2x_unavailable_reason", _boom)
    for mode in ("nearest", "quality"):
        result = convert(E13, scale=2, backend="qml", upscale=mode,
                         output_dir=tmp_path / mode)
        assert not any(n.startswith("upscale:") for n in result.notes)


# --------------------------------------------------------------------- #
# The svg guard
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", ["quality", "waifu2x"])
@pytest.mark.parametrize("backend", ["svg", "both"])
def test_svg_backend_rejects_every_smoothing_mode(tmp_path: Path, mode, backend):
    with pytest.raises(ValueError) as exc:
        convert(E13, scale=2, backend=backend, upscale=mode,
                output_dir=tmp_path / "out")
    message = str(exc.value)
    # The message used to hardcode "quality" and so misreported waifu2x.
    assert f"--upscale {mode} is QML-backend-only" in message
    assert "requires upscale 'nearest'" in message


def test_svg_backend_accepts_nearest(tmp_path: Path):
    result = convert(E13, scale=2, backend="svg", upscale="nearest",
                     output_dir=tmp_path / "out")
    assert result.installed_dir is not None
