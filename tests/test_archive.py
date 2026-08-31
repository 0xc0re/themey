"""Negative + positive tests for the safe_extract archive validator."""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.etheme.archive import (
    MAX_ENTRIES,
    MAX_FILE_BYTES,
    MAX_TOTAL_BYTES,
    UnsafeArchiveError,
    extract,
)

FIXTURES = Path(__file__).parent / "fixtures"
MALICIOUS = FIXTURES / "malicious"


@pytest.mark.parametrize(
    "name,fragment",
    [
        ("path_traversal.tar.gz", "path-traversal"),
        ("absolute_path.tar.gz", "path-traversal"),
        ("symlink_escape.tar.gz", "symlink"),
        ("oversize_file.tar.gz", "too large"),
        ("oversize_count.tar.gz", "too many entries"),
        ("no_root_marker.tar.gz", "marker"),
        ("device_file.tar.gz", "unsafe member type"),
    ],
)
def test_malicious_archive_rejected(name: str, fragment: str) -> None:
    with pytest.raises(UnsafeArchiveError) as ei:
        with extract(MALICIOUS / name):
            pytest.fail("extract() should have raised before yielding")
    assert fragment in str(ei.value), f"expected '{fragment}' in error: {ei.value}"


def test_aliens_extracts_cleanly() -> None:
    path = FIXTURES / "Aliens.etheme"
    captured_root: Path | None = None
    with extract(path) as raw:
        assert raw.asset_root.is_dir()
        assert (raw.asset_root / "borders.cfg").is_file()
        # symlink members should be resolved to regular files
        fonts_cfg = raw.asset_root / "fonts.cfg"
        fonts_target = raw.asset_root / "fonts.theme.cfg"
        assert fonts_cfg.is_file(), "fonts.cfg should exist as regular file"
        assert not fonts_cfg.is_symlink(), "safe_extract must resolve symlinks"
        assert fonts_target.is_file()
        assert fonts_cfg.read_bytes() == fonts_target.read_bytes()
        captured_root = raw.asset_root
    # After context exit, tmpdir is gone
    assert captured_root is not None
    assert not captured_root.exists(), "tempdir should be cleaned up"


def test_over_cap_entry_count_rejected(tmp_path: Path) -> None:
    """An archive with more than MAX_ENTRIES members is still rejected.

    Built on the fly (the committed oversize_count fixture predates the cap
    raise for legitimate large themes like Ganymede at 1051 entries).
    """
    import io
    import tarfile

    archive = tmp_path / "too_many.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        for i in range(MAX_ENTRIES + 1):
            info = tarfile.TarInfo(name=f"theme/file{i}.png")
            info.size = 0
            tf.addfile(info, io.BytesIO(b""))
    with pytest.raises(UnsafeArchiveError) as ei:
        with extract(archive):
            pytest.fail("extract() should have raised before yielding")
    assert "too many entries" in str(ei.value)


def test_caps_are_correct_values() -> None:
    """Sanity-check the constants didn't drift."""
    assert MAX_TOTAL_BYTES == 32 * 1024 * 1024
    assert MAX_FILE_BYTES == 8 * 1024 * 1024
    assert MAX_ENTRIES == 4000
