"""Tar-safe extraction of E16 .etheme archives.

CVE-2007-4559 / CVE-2025-4330: tarfile.extractall is unsafe even with the
Python 3.12+ filter="data" default. We validate every member and resolve
symlinks at extract time (Look-and-Feel packages forbid symlinks; the
input shouldn't have them in the first place).
"""
from __future__ import annotations

import tarfile
import tempfile
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

# Caps verified in production by ~/src/wilbs/src/lib/themes/e16/parse-e16-archive.ts
MAX_TOTAL_BYTES: int = 32 * 1024 * 1024  # 32 MB total extracted
MAX_FILE_BYTES: int = 8 * 1024 * 1024  # 8 MB per file
# Legitimate themes reach four digits (Ganymede: 1051 entries); the size caps
# above are the real zip-bomb defense, this only bounds member iteration.
MAX_ENTRIES: int = 4000  # entry-count cap

# Marker filenames that identify the theme root (shortest-path wins).
ROOT_MARKERS: frozenset[str] = frozenset({"borders.cfg", "init.cfg"})


class UnsafeArchiveError(Exception):
    """Raised when an archive member or property fails the safe-extract validator."""


@dataclass(frozen=True)
class RawTheme:
    """Validated, extracted E16 theme tree.

    ``asset_root`` is the directory containing ``borders.cfg`` or ``init.cfg``
    (whichever is at the shortest path). This path is only valid during the
    ``with extract(...)`` block — the temporary directory is cleaned up on
    context exit.
    """

    asset_root: Path


@contextmanager
def extract(etheme_path: Path) -> Generator[RawTheme, None, None]:
    """Open an .etheme, validate every member, extract to a temp dir.

    Yields a :class:`RawTheme`. Raises :class:`UnsafeArchiveError` on any
    validation failure. The tempdir is auto-cleaned on context exit.
    """
    with tempfile.TemporaryDirectory(prefix="themey-") as td:
        td_path = Path(td).resolve()
        with tarfile.open(etheme_path, "r:gz") as tf:
            _safe_extract_all(tf, td_path)
        root = _find_theme_root(td_path)
        yield RawTheme(asset_root=root)


def _safe_extract_all(tf: tarfile.TarFile, dest: Path) -> None:
    """Validate and extract all members, resolving symlinks by content copy."""
    total = 0
    members = tf.getmembers()
    if len(members) > MAX_ENTRIES:
        raise UnsafeArchiveError(
            f"too many entries: {len(members)} > {MAX_ENTRIES}"
        )
    for m in members:
        # Reject device/character/fifo special files
        if m.ischr() or m.isblk() or m.isfifo():
            raise UnsafeArchiveError(f"unsafe member type: {m.name}")
        # Reject hardlinks (can race the extraction)
        if m.islnk():
            raise UnsafeArchiveError(f"hardlinks not allowed: {m.name}")
        # Reject absolute paths and ..-traversal
        if Path(m.name).is_absolute() or ".." in Path(m.name).parts:
            raise UnsafeArchiveError(f"path-traversal: {m.name}")
        target = (dest / m.name).resolve()
        dest_prefix = str(dest) + "/"
        if not str(target).startswith(dest_prefix) and target != dest:
            raise UnsafeArchiveError(f"member escapes dest: {m.name}")
        # Symlinks: validate link target is inside dest, defer content copy to pass 2
        if m.issym():
            link_target = (target.parent / m.linkname).resolve()
            if not str(link_target).startswith(dest_prefix):
                raise UnsafeArchiveError(
                    f"symlink escape: {m.name} -> {m.linkname}"
                )
            # Do not write the symlink yet — handled in pass 2 after files are written
            continue
        # Regular files: enforce per-file cap and write bytes
        if m.isfile():
            if m.size > MAX_FILE_BYTES:
                raise UnsafeArchiveError(
                    f"file too large: {m.name} ({m.size} bytes > {MAX_FILE_BYTES})"
                )
            total += m.size
            if total > MAX_TOTAL_BYTES:
                raise UnsafeArchiveError(
                    f"archive too large: total > {MAX_TOTAL_BYTES} bytes"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(m) as src, open(target, "wb") as dst:  # type: ignore[union-attr]
                dst.write(src.read())
        elif m.isdir():
            target.mkdir(parents=True, exist_ok=True)

    # Pass 2: resolve symlinks by copying target file bytes
    for m in members:
        if not m.issym():
            continue
        target = (dest / m.name).resolve()
        link_resolved = (target.parent / m.linkname).resolve()
        if link_resolved.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(link_resolved.read_bytes())
        # If target missing or directory — skip silently (logged later if needed)


def _find_theme_root(extract_dir: Path) -> Path:
    """Find the directory containing borders.cfg or init.cfg (shortest path wins)."""
    candidates: list[Path] = []
    for marker in ROOT_MARKERS:
        candidates.extend(extract_dir.rglob(marker))
    if not candidates:
        raise UnsafeArchiveError(
            f"no theme root marker ({', '.join(sorted(ROOT_MARKERS))}) in archive"
        )
    return sorted(candidates, key=lambda p: len(p.parts))[0].parent
