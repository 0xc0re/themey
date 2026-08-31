"""Tests for themey.install.deploy / deploy_file — atomic install with rollback."""
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


def _make_file(tmp_path: Path, name: str, content: str) -> Path:
    src = tmp_path / name
    src.write_text(content, encoding="utf-8")
    return src


def test_deploy_file_fresh_install(fake_home: Path, tmp_path: Path) -> None:
    from themey import paths
    from themey.install import deploy_file

    source = _make_file(tmp_path, "src.colors", "CONTENT")
    result = deploy_file(
        "themey_Test.colors", source, target_root=paths.color_schemes()
    )
    expected = fake_home / ".local" / "share" / "color-schemes" / "themey_Test.colors"
    assert result == expected
    assert expected.read_text(encoding="utf-8") == "CONTENT"
    # The staged source has been renamed away, not copied.
    assert not source.exists()


def test_deploy_file_overwrites_existing(fake_home: Path, tmp_path: Path) -> None:
    from themey import paths
    from themey.install import deploy_file

    deploy_file(
        "themey_Test.colors",
        _make_file(tmp_path, "old.colors", "OLD"),
        target_root=paths.color_schemes(),
    )
    result = deploy_file(
        "themey_Test.colors",
        _make_file(tmp_path, "new.colors", "NEW"),
        target_root=paths.color_schemes(),
    )
    assert result.read_text(encoding="utf-8") == "NEW"
    # No backup litter left behind.
    assert not result.with_name("themey_Test.colors.themey-old").exists()


def test_deploy_file_rollback_on_failure(fake_home: Path, tmp_path: Path) -> None:
    from themey import paths
    from themey.install import InstallError, deploy_file

    result = deploy_file(
        "themey_Test.colors",
        _make_file(tmp_path, "keep.colors", "OLD"),
        target_root=paths.color_schemes(),
    )
    with pytest.raises(InstallError):
        deploy_file(
            "themey_Test.colors",
            tmp_path / "nonexistent.colors",
            target_root=paths.color_schemes(),
        )
    assert result.is_file()
    assert result.read_text(encoding="utf-8") == "OLD"


def test_deploy_file_rejects_directory_source(fake_home: Path, tmp_path: Path) -> None:
    from themey import paths
    from themey.install import InstallError, deploy_file

    src_dir = tmp_path / "a_dir"
    src_dir.mkdir()
    with pytest.raises(InstallError):
        deploy_file(
            "themey_Test.colors", src_dir, target_root=paths.color_schemes()
        )


def test_deploy_file_creates_missing_target_root(
    fake_home: Path, tmp_path: Path
) -> None:
    from themey import paths
    from themey.install import deploy_file

    root = paths.color_schemes()
    assert not root.exists()
    deploy_file(
        "themey_Test.colors",
        _make_file(tmp_path, "fresh.colors", "X"),
        target_root=root,
    )
    assert root.is_dir()


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
