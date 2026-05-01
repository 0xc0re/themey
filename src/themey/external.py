"""xdg-open wrapper with SSH/headless detection.

Suppresses preview auto-open when:
  - SSH_CONNECTION env var is set (running over SSH, T-08-05)
  - Both DISPLAY and WAYLAND_DISPLAY are unset (headless)
  - xdg-open is not on PATH

Uses subprocess.Popen (NOT run/check_call) so the browser launch does not
block the CLI from returning (per must_have truth in 01-08-PLAN.md).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


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
