"""Wrappers for the external tools themey shells out to.

**xdg-open** (preview auto-open). Suppressed when:
  - SSH_CONNECTION env var is set (running over SSH, T-08-05)
  - Both DISPLAY and WAYLAND_DISPLAY are unset (headless)
  - xdg-open is not on PATH

Uses subprocess.Popen (NOT run/check_call) so the browser launch does not
block the CLI from returning (per must_have truth in 01-08-PLAN.md).

**xcursorgen** (XCursor binary assembly, xorg-xcursorgen package). Unlike
xdg-open this one is load-bearing — there is no pure-Python XCursor writer
— so callers ask :func:`xcursorgen_available` first and skip the whole
cursor stage with a note when it is absent (graceful degradation, see
``generate/cursors.py``). ``xcursorgen`` reports some failures by exiting 0
and producing nothing, so :func:`run_xcursorgen` verifies the output file
exists and is non-empty rather than trusting the return code alone.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

XCURSORGEN = "xcursorgen"
XCURSORGEN_TIMEOUT_SECONDS = 60


class XcursorgenError(Exception):
    """The xcursorgen subprocess failed or produced no usable output."""


def open_preview_unless_headless(html_path: Path) -> bool:
    """Open *html_path* in the user's browser unless headless/SSH is detected.

    Returns True if the browser was launched, False if suppressed.
    Caller should print the path on False so the user can open manually.
    """
    if os.environ.get("SSH_CONNECTION"):
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False
    xdg = shutil.which("xdg-open")
    if not xdg:
        return False
    subprocess.Popen(
        [xdg, str(html_path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return True


def xcursorgen_available() -> bool:
    """True when the ``xcursorgen`` executable is on PATH."""
    return shutil.which(XCURSORGEN) is not None


def run_xcursorgen(config: Path, out: Path, image_dir: Path) -> Path:
    """Assemble the XCursor binary described by *config* into *out*.

    *config* holds one ``<size> <xhot> <yhot> <png>`` line per nominal
    size; the PNG names are resolved relative to *image_dir* (``-p``).

    Returns *out*. Raises :class:`XcursorgenError` when the tool is absent,
    times out, exits non-zero, or leaves no non-empty output file — with
    the tail of stderr attached so the caller can report why.
    """
    exe = shutil.which(XCURSORGEN)
    if exe is None:
        raise XcursorgenError(f"{XCURSORGEN} is not on PATH")
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "-p", str(image_dir), str(config), str(out)]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=XCURSORGEN_TIMEOUT_SECONDS
        )
    except subprocess.TimeoutExpired as exc:
        raise XcursorgenError(
            f"{XCURSORGEN} timed out after {XCURSORGEN_TIMEOUT_SECONDS}s on {config}"
        ) from exc
    tail = proc.stderr.strip()[-500:]
    if proc.returncode != 0:
        raise XcursorgenError(
            f"{XCURSORGEN} exited {proc.returncode} on {config.name}: {tail}"
        )
    if not out.is_file() or out.stat().st_size == 0:
        raise XcursorgenError(
            f"{XCURSORGEN} produced no output (or an empty file) at {out}: {tail}"
        )
    return out
