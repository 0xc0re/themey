"""Atomic install: stage to tmpdir, then os.replace into final position.

Pattern (INSTALL-01):
  1. Caller has already written generator output to source_dir
  2. We move any existing target dir aside (.themey-old)
  3. os.replace(source_dir, target) — atomic rename
  4. On success: rm -rf .themey-old
  5. On failure: restore .themey-old; raise InstallError

The previous-install backup makes re-runs idempotent (CLI-03 partial).

Note on cross-filesystem moves: source_dir SHOULD be created under the
same XDG_DATA_HOME tree (e.g. via paths.staging_dir()) so os.replace
can rename atomically. If source_dir is on a different filesystem,
os.replace raises OSError: [Errno 18] Invalid cross-device link — the
caller is responsible for staging to the right location. See assumptions
in 01-08-PLAN.md for rationale.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import paths


class InstallError(Exception):
    """Atomic install failed; previous install (if any) was restored."""


def deploy(theme_name: str, source_dir: Path, target_root: Path | None = None) -> Path:
    """Atomically install source_dir as <target_root>/<theme_name>/.

    ``target_root`` defaults to the Aurorae themes dir (preserving existing
    callers); the QML backend passes ``paths.kwin_decorations()``. Uses
    stage-then-rename: source_dir is os.replace()'d into final position; if
    a previous install exists at that path, it is moved aside first. On
    failure, the previous install is restored.

    Returns the final installed Path. Raises InstallError on any failure.
    """
    if not source_dir.is_dir():
        raise InstallError(f"source_dir does not exist: {source_dir}")
    final = (target_root or paths.aurorae_themes()) / theme_name
    final.parent.mkdir(parents=True, exist_ok=True)
    backup = final.with_name(f"{theme_name}.themey-old")
    had_previous = final.exists()
    if backup.exists():
        shutil.rmtree(backup)
    if had_previous:
        os.replace(final, backup)  # atomic move-aside
    try:
        os.replace(source_dir, final)  # atomic rename-into-place
    except OSError as exc:
        # Roll back: restore the previous install if there was one
        if had_previous and backup.exists():
            os.replace(backup, final)
        raise InstallError(f"atomic install failed for {theme_name!r}: {exc}") from exc
    # Success — clean up the backup
    if backup.exists():
        shutil.rmtree(backup)
    return final


def deploy_file(file_name: str, source_file: Path, *, target_root: Path) -> Path:
    """Atomically install a single file as ``<target_root>/<file_name>``.

    Single-file sibling of :func:`deploy`, for the Global-Theme artifacts
    that are one file rather than a package directory (the ``.colors``
    scheme). Same INSTALL-01 pattern: move any existing target aside to
    ``<file_name>.themey-old``, ``os.replace`` the staged file into place,
    drop the backup on success, restore it on failure.

    ``source_file`` MUST be staged on the same filesystem as ``target_root``
    (see the cross-device note in the module docstring) — it is *renamed*,
    not copied, so it no longer exists afterwards.

    Returns the final installed Path. Raises InstallError on any failure.
    """
    if not source_file.is_file():
        raise InstallError(f"source_file does not exist: {source_file}")
    final = target_root / file_name
    final.parent.mkdir(parents=True, exist_ok=True)
    backup = final.with_name(f"{file_name}.themey-old")
    had_previous = final.exists()
    if backup.exists():
        backup.unlink()
    if had_previous:
        os.replace(final, backup)  # atomic move-aside
    try:
        os.replace(source_file, final)  # atomic rename-into-place
    except OSError as exc:
        if had_previous and backup.exists():
            os.replace(backup, final)
        raise InstallError(f"atomic install failed for {file_name!r}: {exc}") from exc
    if backup.exists():
        backup.unlink()
    return final
