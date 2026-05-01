"""Tests for external.open_preview_unless_headless — xdg-open subprocess wrapper."""
from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from themey.external import open_preview_unless_headless


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
