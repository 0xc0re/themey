"""Tests for themey.install.deploy — atomic install with rollback."""
from __future__ import annotations

from pathlib import Path

import pytest


def _make_source(tmp_path: Path, name: str, content: str) -> Path:
    """Create a temporary source directory with a single file."""
    src = tmp_path / name
    src.mkdir(parents=True, exist_ok=True)
    (src / "marker.txt").write_text(content)
    return src


def test_deploy_fresh_install(fake_home: Path, tmp_path: Path) -> None:
    from themey.install import deploy

    source = _make_source(tmp_path, "source_fresh", "CONTENT")
    result = deploy("TestTheme", source)
    expected = fake_home / ".local" / "share" / "aurorae" / "themes" / "TestTheme"
    assert result == expected
    assert (expected / "marker.txt").read_text() == "CONTENT"


def test_deploy_overwrites_existing(fake_home: Path, tmp_path: Path) -> None:
    from themey.install import deploy

    # First install
    src1 = _make_source(tmp_path, "src1", "OLD")
    deploy("TestTheme", src1)

    # Second install
    src2 = _make_source(tmp_path, "src2", "NEW")
    result = deploy("TestTheme", src2)
    assert (result / "marker.txt").read_text() == "NEW"


def test_deploy_idempotent_rerun(fake_home: Path, tmp_path: Path) -> None:
    from themey.install import deploy

    src1 = _make_source(tmp_path, "idem1", "FIRST")
    deploy("TestTheme", src1)

    src2 = _make_source(tmp_path, "idem2", "SECOND")
    result = deploy("TestTheme", src2)
    assert (result / "marker.txt").read_text() == "SECOND"


def test_deploy_rollback_on_failure(fake_home: Path, tmp_path: Path) -> None:
    from themey.install import InstallError, deploy

    # Pre-install something
    src = _make_source(tmp_path, "rollback_src", "OLD")
    result = deploy("TestTheme", src)
    assert (result / "marker.txt").read_text() == "OLD"

    # Now try to deploy a non-existent source directory
    nonexistent = tmp_path / "nonexistent"
    with pytest.raises(InstallError):
        deploy("TestTheme", nonexistent)

    # OLD content should still be there
    assert result.is_dir()
    assert (result / "marker.txt").read_text() == "OLD"


def test_deploy_under_xdg_data_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    xdg = tmp_path / "xdg_data"
    xdg.mkdir()
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg))

    from themey.install import deploy

    source = _make_source(tmp_path, "xdg_source", "XDG_CONTENT")
    result = deploy("TestTheme", source)
    expected = xdg / "aurorae" / "themes" / "TestTheme"
    assert result == expected
    assert (expected / "marker.txt").read_text() == "XDG_CONTENT"
