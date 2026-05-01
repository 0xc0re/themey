"""Generate malicious .tar.gz fixtures that exercise every safe_extract reject path.

Run once via `uv run python tests/fixtures/build_malicious_archives.py`.
Outputs fixtures into tests/fixtures/malicious/.

The 7 fixtures correspond 1:1 to the negative tests in tests/test_archive.py.
"""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

OUT = Path(__file__).parent / "malicious"


def _add_member(
    tar: tarfile.TarFile,
    name: str,
    content: bytes,
    *,
    type_flag: bytes = tarfile.REGTYPE,
    linkname: str = "",
) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    info.type = type_flag
    info.linkname = linkname
    tar.addfile(info, io.BytesIO(content))


def build_path_traversal() -> Path:
    out = OUT / "path_traversal.tar.gz"
    out.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "borders.cfg", b"# valid marker\n")
        # Member name with .. — should be rejected
        _add_member(tar, "../etc/passwd", b"PWNED")
    return out


def build_absolute_path() -> Path:
    out = OUT / "absolute_path.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "borders.cfg", b"# valid marker\n")
        _add_member(tar, "/tmp/evil", b"PWNED")
    return out


def build_symlink_escape() -> Path:
    out = OUT / "symlink_escape.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "borders.cfg", b"# valid marker\n")
        # Symlink whose linkname escapes via parent traversal
        info = tarfile.TarInfo(name="evil")
        info.type = tarfile.SYMTYPE
        info.linkname = "../../../etc/passwd"
        tar.addfile(info)
    return out


def build_oversize_file() -> Path:
    out = OUT / "oversize_file.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "borders.cfg", b"# valid marker\n")
        # 9 MB regular file (cap is 8 MB)
        _add_member(tar, "huge.bin", b"\x00" * (9 * 1024 * 1024))
    return out


def build_oversize_count() -> Path:
    out = OUT / "oversize_count.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "borders.cfg", b"# valid marker\n")
        # 600 tiny members (cap is 500)
        for i in range(600):
            _add_member(tar, f"f{i}.txt", b"x")
    return out


def build_no_root_marker() -> Path:
    out = OUT / "no_root_marker.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "random.txt", b"hello")
        _add_member(tar, "subdir/other.cfg", b"hello")
    return out


def build_device_file() -> Path:
    out = OUT / "device_file.tar.gz"
    with tarfile.open(out, "w:gz") as tar:
        _add_member(tar, "borders.cfg", b"# valid marker\n")
        info = tarfile.TarInfo(name="evil_dev")
        info.type = tarfile.CHRTYPE  # character device
        info.devmajor = 1
        info.devminor = 3
        tar.addfile(info)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (
        build_path_traversal,
        build_absolute_path,
        build_symlink_escape,
        build_oversize_file,
        build_oversize_count,
        build_no_root_marker,
        build_device_file,
    ):
        p = fn()
        print(f"wrote {p} ({p.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
