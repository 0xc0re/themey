"""Tests for external.py — the xdg-open and xcursorgen subprocess wrappers."""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from themey.external import (
    XcursorgenError,
    open_preview_unless_headless,
    run_xcursorgen,
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
    with pytest.raises(XcursorgenError, match="empty|no output"):
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
