"""Tests for external.py — the xdg-open, xcursorgen and waifu2x wrappers."""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from themey.external import (
    WAIFU2X_ATTEMPTS,
    WAIFU2X_GPU_ENV,
    WAIFU2X_MODEL,
    WAIFU2X_MODELS_ENV,
    Waifu2xError,
    XcursorgenError,
    open_preview_unless_headless,
    run_waifu2x,
    run_xcursorgen,
    waifu2x_available,
    waifu2x_models_dir,
    waifu2x_unavailable_reason,
    xcursorgen_available,
)


def test_open_returns_false_when_ssh_connection_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("SSH_CONNECTION", "1.2.3.4 22 5.6.7.8 443")
    monkeypatch.setenv("DISPLAY", ":0")  # display present, but SSH wins
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert open_preview_unless_headless(tmp_path / "x.html") is False
    popen.assert_not_called()


def test_open_returns_false_when_no_display_no_wayland(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert open_preview_unless_headless(tmp_path / "x.html") is False
    popen.assert_not_called()


def test_open_returns_false_when_xdg_open_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shutil as _sh

    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(_sh, "which", lambda x: None)
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    assert open_preview_unless_headless(tmp_path / "x.html") is False
    popen.assert_not_called()


def test_open_returns_true_when_display_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shutil as _sh

    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(
        _sh, "which", lambda x: "/usr/bin/xdg-open" if x == "xdg-open" else None
    )
    popen = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    html = tmp_path / "x.html"
    html.write_text("<html></html>")
    assert open_preview_unless_headless(html) is True
    popen.assert_called_once()
    # Verify the args contain the path
    args, _kwargs = popen.call_args
    assert args[0] == ["/usr/bin/xdg-open", str(html)]


def test_open_uses_popen_not_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shutil as _sh

    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.setenv("DISPLAY", ":0")
    monkeypatch.setattr(
        _sh, "which", lambda x: "/usr/bin/xdg-open" if x == "xdg-open" else None
    )
    popen = MagicMock()
    run = MagicMock()
    monkeypatch.setattr(subprocess, "Popen", popen)
    monkeypatch.setattr(subprocess, "run", run)
    html = tmp_path / "x.html"
    html.write_text("<html></html>")
    open_preview_unless_headless(html)
    popen.assert_called_once()
    run.assert_not_called()


# --------------------------------------------------------------------- #
# xcursorgen wrapper (Phase C / C1)
# --------------------------------------------------------------------- #


def _fake_xcursorgen(bin_dir: Path, body: str) -> Path:
    """Install a fake ``xcursorgen`` shell script into *bin_dir*."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / "xcursorgen"
    exe.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def _on_path(monkeypatch: pytest.MonkeyPatch, bin_dir: Path) -> None:
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ["PATH"])


def _config(tmp_path: Path) -> tuple[Path, Path]:
    """A minimal xcursorgen config plus the image dir it references."""
    images = tmp_path / "images"
    images.mkdir(exist_ok=True)
    (images / "x_1.png").write_bytes(b"not-really-a-png")
    cfg = tmp_path / "cursor.cfg"
    cfg.write_text("16 1 1 x_1.png\n", encoding="utf-8")
    return cfg, images


def test_xcursorgen_available_false_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert xcursorgen_available() is False


def test_xcursorgen_available_true_when_on_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _fake_xcursorgen(tmp_path / "bin", "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    assert xcursorgen_available() is True


def test_run_xcursorgen_returns_output_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # argv is "-p <dir> <config> <out>", so $4 is where the binary goes.
    _fake_xcursorgen(tmp_path / "bin", 'printf XcurFAKE > "$4"')
    _on_path(monkeypatch, tmp_path / "bin")
    cfg, images = _config(tmp_path)
    out = tmp_path / "out" / "default"
    assert run_xcursorgen(cfg, out, images) == out
    assert out.read_bytes() == b"XcurFAKE"


def test_run_xcursorgen_passes_image_dir_with_p(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _fake_xcursorgen(tmp_path / "bin", 'printf "%s" "$*" > "$4"')
    _on_path(monkeypatch, tmp_path / "bin")
    cfg, images = _config(tmp_path)
    out = tmp_path / "out" / "default"
    run_xcursorgen(cfg, out, images)
    assert out.read_text().split() == ["-p", str(images), str(cfg), str(out)]


def test_run_xcursorgen_raises_with_stderr_tail(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _fake_xcursorgen(tmp_path / "bin", 'echo "boom: bad hotspot" >&2; exit 3')
    _on_path(monkeypatch, tmp_path / "bin")
    cfg, images = _config(tmp_path)
    with pytest.raises(XcursorgenError) as exc:
        run_xcursorgen(cfg, tmp_path / "out" / "default", images)
    assert "boom: bad hotspot" in str(exc.value)
    assert "3" in str(exc.value)


def test_run_xcursorgen_raises_when_output_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # Exit 0 but produce a zero-byte file — a silent failure we must catch.
    _fake_xcursorgen(tmp_path / "bin", ': > "$4"; exit 0')
    _on_path(monkeypatch, tmp_path / "bin")
    cfg, images = _config(tmp_path)
    with pytest.raises(XcursorgenError, match=r"no output"):
        run_xcursorgen(cfg, tmp_path / "out" / "default", images)


def test_run_xcursorgen_raises_when_not_on_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    cfg, images = _config(tmp_path)
    with pytest.raises(XcursorgenError, match="not on PATH"):
        run_xcursorgen(cfg, tmp_path / "out" / "default", images)


def test_run_xcursorgen_raises_on_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    _fake_xcursorgen(tmp_path / "bin", "exit 0")
    _on_path(monkeypatch, tmp_path / "bin")
    cfg, images = _config(tmp_path)

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="xcursorgen", timeout=1)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(XcursorgenError, match="timed out"):
        run_xcursorgen(cfg, tmp_path / "out" / "default", images)


# --------------------------------------------------------------------- #
# waifu2x-ncnn-vulkan wrapper
# --------------------------------------------------------------------- #


def _fake_waifu2x(bin_dir: Path, body: str) -> Path:
    """Install a fake ``waifu2x-ncnn-vulkan`` shell script into *bin_dir*."""
    bin_dir.mkdir(parents=True, exist_ok=True)
    exe = bin_dir / "waifu2x-ncnn-vulkan"
    exe.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    return exe


def _fake_models(root: Path, model: str = WAIFU2X_MODEL) -> Path:
    """A directory that passes the ``*.param`` model-dir sniff test."""
    d = root / model
    d.mkdir(parents=True, exist_ok=True)
    (d / "noise0_scale2.0x_model.param").write_text("7767517\n", encoding="utf-8")
    (d / "noise0_scale2.0x_model.bin").write_bytes(b"\x00" * 8)
    return d


def _png(path: Path, size: tuple[int, int]) -> Path:
    from PIL import Image

    Image.new("RGBA", size, (10, 20, 30, 255)).save(path)
    return path


def _isolate(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """PATH with nothing on it and no models env var — the empty world."""
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)


def test_waifu2x_available_false_when_binary_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _isolate(monkeypatch, tmp_path)
    assert waifu2x_available() is False
    assert "not on PATH" in (waifu2x_unavailable_reason() or "")


def test_waifu2x_available_false_when_only_the_binary_is_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """The state a fresh install lands in: the executable was copied to
    /usr/local/bin and its models-* siblings were left behind."""
    _fake_waifu2x(tmp_path / "bin", "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)
    monkeypatch.setattr("themey.external._WAIFU2X_MODEL_ROOTS", ())
    assert waifu2x_available() is False
    reason = waifu2x_unavailable_reason() or ""
    # The note built from this has to send the reader to the models, not
    # to the binary they can already see on their PATH.
    assert "on PATH" in reason
    assert WAIFU2X_MODEL in reason


def test_waifu2x_available_true_with_models_beside_the_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Upstream's own layout: binary and models-* as flat siblings."""
    _fake_waifu2x(tmp_path / "bin", "exit 0")
    _fake_models(tmp_path / "bin")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)
    assert waifu2x_available() is True
    assert waifu2x_unavailable_reason() is None
    assert waifu2x_models_dir() == tmp_path / "bin" / WAIFU2X_MODEL


def test_waifu2x_models_env_accepts_the_parent_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _fake_waifu2x(tmp_path / "bin", "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    _fake_models(tmp_path / "models")
    monkeypatch.setenv(WAIFU2X_MODELS_ENV, str(tmp_path / "models"))
    assert waifu2x_models_dir() == tmp_path / "models" / WAIFU2X_MODEL


def test_waifu2x_models_env_accepts_one_model_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """Pointing straight at a models-cunet dir is the other reasonable
    reading of the variable, so it works too."""
    _fake_waifu2x(tmp_path / "bin", "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    model_dir = _fake_models(tmp_path / "models")
    monkeypatch.setenv(WAIFU2X_MODELS_ENV, str(model_dir))
    assert waifu2x_models_dir() == model_dir


def test_waifu2x_models_dir_ignores_an_empty_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _fake_waifu2x(tmp_path / "bin", "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    (tmp_path / "bin" / WAIFU2X_MODEL).mkdir(parents=True)
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)
    monkeypatch.setattr("themey.external._WAIFU2X_MODEL_ROOTS", ())
    assert waifu2x_models_dir() is None


def _ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str) -> Path:
    """Fake binary + models on PATH; returns the source PNG."""
    _fake_waifu2x(tmp_path / "bin", body)
    _fake_models(tmp_path / "bin")
    monkeypatch.setenv("PATH", str(tmp_path / "bin") + os.pathsep + os.environ["PATH"])
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)
    return _png(tmp_path / "src.png", (4, 3))


def test_run_waifu2x_returns_output_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _png(tmp_path / "canned.png", (8, 6))
    src = _ready(monkeypatch, tmp_path, f'cp "{tmp_path}/canned.png" "$4"')
    out = tmp_path / "out" / "up.png"
    assert run_waifu2x(src, out, 2) == out
    assert out.is_file()


def test_run_waifu2x_passes_an_explicit_model_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """It must never rely on cwd for -m: that is the whole models bug."""
    _png(tmp_path / "canned.png", (8, 6))
    src = _ready(
        monkeypatch, tmp_path,
        f'printf "%s" "$*" > "{tmp_path}/argv.txt"; cp "{tmp_path}/canned.png" "$4"',
    )
    run_waifu2x(src, tmp_path / "out.png", 2)
    argv = (tmp_path / "argv.txt").read_text().split()
    assert argv[argv.index("-m") + 1] == str(tmp_path / "bin" / WAIFU2X_MODEL)
    assert argv[argv.index("-s") + 1] == "2"
    assert "-n" in argv


def test_run_waifu2x_raises_with_stderr_tail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    src = _ready(monkeypatch, tmp_path, 'echo "invalid scale argument" >&2; exit 255')
    with pytest.raises(Waifu2xError) as exc:
        run_waifu2x(src, tmp_path / "out.png", 3)
    assert "invalid scale argument" in str(exc.value)
    assert "255" in str(exc.value)


def test_run_waifu2x_raises_when_output_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    # Exit 0 and write nothing — the silent failure an exit code hides.
    src = _ready(monkeypatch, tmp_path, ': > "$4"; exit 0')
    with pytest.raises(Waifu2xError, match=r"no output"):
        run_waifu2x(src, tmp_path / "out.png", 2)


def test_run_waifu2x_raises_on_wrong_output_dimensions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A 2x request that comes back 1x would silently ship art whose
    dims no longer match the BorderImage insets."""
    _png(tmp_path / "canned.png", (4, 3))
    src = _ready(monkeypatch, tmp_path, f'cp "{tmp_path}/canned.png" "$4"')
    with pytest.raises(Waifu2xError, match=r"expected 8x6"):
        run_waifu2x(src, tmp_path / "out.png", 2)


def test_run_waifu2x_raises_when_not_on_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    src = _png(tmp_path / "src.png", (4, 3))
    _isolate(monkeypatch, tmp_path)
    with pytest.raises(Waifu2xError, match="not on PATH"):
        run_waifu2x(src, tmp_path / "out.png", 2)


def test_run_waifu2x_raises_when_models_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _fake_waifu2x(tmp_path / "bin", "exit 0")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))
    monkeypatch.delenv(WAIFU2X_MODELS_ENV, raising=False)
    monkeypatch.setattr("themey.external._WAIFU2X_MODEL_ROOTS", ())
    src = _png(tmp_path / "src.png", (4, 3))
    with pytest.raises(Waifu2xError, match=WAIFU2X_MODEL):
        run_waifu2x(src, tmp_path / "out.png", 2)


def test_run_waifu2x_raises_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    src = _ready(monkeypatch, tmp_path, "exit 0")

    def _timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="waifu2x-ncnn-vulkan", timeout=1)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(Waifu2xError, match="timed out"):
        run_waifu2x(src, tmp_path / "out.png", 2)


def test_run_waifu2x_timeout_keeps_the_stderr_it_captured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """waifu2x prints its Vulkan device banner to stderr the moment it
    starts, so a timeout that discards stderr discards the one line that
    says WHICH device was chosen — and picking the software fallback is
    ~42x slower, i.e. the likeliest reason to time out at all. Without
    this the error is 'timed out' and nothing else."""
    banner = "[0 NVIDIA GeForce RTX 3070]  queueC=2[8]"
    src = _ready(monkeypatch, tmp_path, f'echo "{banner}" >&2; sleep 30')
    monkeypatch.setattr("themey.external.WAIFU2X_TIMEOUT_SECONDS", 1)
    with pytest.raises(Waifu2xError) as exc:
        run_waifu2x(src, tmp_path / "out.png", 2)
    assert "timed out" in str(exc.value)
    assert "NVIDIA GeForce RTX 3070" in str(exc.value)


def test_run_waifu2x_passes_no_gpu_flag_by_default(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    _png(tmp_path / "canned.png", (8, 6))
    src = _ready(
        monkeypatch, tmp_path,
        f'printf "%s" "$*" > "{tmp_path}/argv.txt"; cp "{tmp_path}/canned.png" "$4"',
    )
    monkeypatch.delenv(WAIFU2X_GPU_ENV, raising=False)
    run_waifu2x(src, tmp_path / "out.png", 2)
    assert "-g" not in (tmp_path / "argv.txt").read_text().split()


def test_run_waifu2x_pins_the_device_when_asked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """The escape hatch for a machine whose auto-pick lands on a software
    Vulkan device."""
    _png(tmp_path / "canned.png", (8, 6))
    src = _ready(
        monkeypatch, tmp_path,
        f'printf "%s" "$*" > "{tmp_path}/argv.txt"; cp "{tmp_path}/canned.png" "$4"',
    )
    monkeypatch.setenv(WAIFU2X_GPU_ENV, "0")
    run_waifu2x(src, tmp_path / "out.png", 2)
    argv = (tmp_path / "argv.txt").read_text().split()
    assert argv[argv.index("-g") + 1] == "0"


# --------------------------------------------------------------------- #
# Retry on a crashed launch
#
# Measured on chris's box 2026-09-02: 2 failures in 270 identical launches
# (~0.7%), always the same shape — ncnn prints ``vkCreateDevice failed -3``
# (VK_ERROR_INITIALIZATION_FAILED), hands back a device it never created,
# and waifu2x dereferences it and dies on SIGSEGV. The next launch of the
# SAME input succeeds every time. themey fires one launch per distinct
# source image, so a ~40-launch convert used to die about a quarter of the
# time on a transient the driver forgets a millisecond later.
# --------------------------------------------------------------------- #


def _counting_waifu2x(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str):
    """Fake binary that records each launch in ``launches.txt``.

    *body* runs with ``$COUNT`` set to the 1-based launch number, so a
    test can crash the first launch and succeed on the second.
    """
    counter = tmp_path / "launches.txt"
    script = (
        f'echo x >> "{counter}"\n'
        f'COUNT=$(wc -l < "{counter}")\n'
        f"{body}\n"
    )
    src = _ready(monkeypatch, tmp_path, script)
    return src, counter


def _launches(counter: Path) -> int:
    return len(counter.read_text().split()) if counter.is_file() else 0


def test_run_waifu2x_retries_a_crashed_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A SIGSEGV is the transient Vulkan-init failure, not a verdict on
    the input: relaunch and the same image goes through."""
    _png(tmp_path / "canned.png", (8, 6))
    src, counter = _counting_waifu2x(
        tmp_path,
        monkeypatch,
        f'if [ "$COUNT" -eq 1 ]; then\n'
        f'  echo "vkCreateDevice failed -3" >&2\n'
        f"  kill -SEGV $$\n"
        f"fi\n"
        f'cp "{tmp_path}/canned.png" "$4"',
    )
    out = tmp_path / "out.png"
    assert run_waifu2x(src, out, 2) == out
    assert out.is_file()
    assert _launches(counter) == 2


def test_run_waifu2x_gives_up_after_the_retry_budget(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """A binary that crashes every time is broken, not unlucky — the
    retry is bounded and the last stderr still reaches the caller."""
    src, counter = _counting_waifu2x(
        tmp_path,
        monkeypatch,
        'echo "vkCreateDevice failed -3" >&2\nkill -SEGV $$',
    )
    with pytest.raises(Waifu2xError) as exc:
        run_waifu2x(src, tmp_path / "out.png", 2)
    assert "vkCreateDevice failed -3" in str(exc.value)
    assert _launches(counter) == WAIFU2X_ATTEMPTS


def test_run_waifu2x_does_not_retry_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """An ordinary non-zero exit is a rejection of the arguments and will
    say the same thing three times over; only a signal death is retried."""
    src, counter = _counting_waifu2x(
        tmp_path, monkeypatch, 'echo "invalid scale argument" >&2; exit 255'
    )
    with pytest.raises(Waifu2xError, match="invalid scale argument"):
        run_waifu2x(src, tmp_path / "out.png", 3)
    assert _launches(counter) == 1


def test_run_waifu2x_does_not_retry_a_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    """WAIFU2X_TIMEOUT_SECONDS is 300; retrying one would spend 15
    minutes proving the machine is still wedged."""
    src, counter = _counting_waifu2x(tmp_path, monkeypatch, "sleep 30")
    monkeypatch.setattr("themey.external.WAIFU2X_TIMEOUT_SECONDS", 1)
    with pytest.raises(Waifu2xError, match="timed out"):
        run_waifu2x(src, tmp_path / "out.png", 2)
    assert _launches(counter) == 1
