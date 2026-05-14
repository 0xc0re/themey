"""Shared pytest fixtures.

fake_home: monkeypatches HOME + XDG_DATA_HOME to a tmp directory so
install / preview / report paths route into the test's tmp tree.
Never use pyfakefs — Pillow and tarfile need real files.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-visual-hashes",
        action="store_true",
        default=False,
        help="Overwrite committed perceptual-hash snapshots from current renders.",
    )


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch HOME + XDG_DATA_HOME to tmp_path. Returns the home dir.

    Creates ``tmp_path/.local/share`` so XDG default resolution works even
    when XDG_DATA_HOME is unset.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    (tmp_path / ".local" / "share").mkdir(parents=True, exist_ok=True)
    return tmp_path
