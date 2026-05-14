"""Wallpaper path extraction from ``desktops.cfg``.

E16 themes describe their backgrounds via a macro syntax that themey's
recursive-descent parser does not expand:

    BEGIN_BACKGROUND("name")
      SET_SOLID("100 70 40")
      ADD_BACKGROUND_SCALED("artwork/backgrounds/Alien97.jpg")
      ON_DESKTOP("0")
    END_BACKGROUND

The image references we care about are the bare-quoted string arguments
to ``ADD_BACKGROUND_SCALED`` and ``BG_FILE`` macros. A simple regex over
the raw text is enough — we don't need a full macro expander for parse-
only purposes.

Phase 2 (WALLPAPER-01) will resize the source images and write the
KDE wallpaper metadata; this module only collects paths.
"""
from __future__ import annotations

import re
from pathlib import Path

_BG_MACRO_RE = re.compile(
    r"""(?:ADD_BACKGROUND_SCALED|BG_FILE)\(\s*"([^"]+)"\s*\)""",
    re.IGNORECASE,
)


def extract_wallpapers(asset_root: Path) -> tuple[Path, ...]:
    """Return every distinct wallpaper image path declared in
    ``<asset_root>/desktops.cfg``, resolved under ``asset_root``.

    Paths that escape ``asset_root`` (T-05-01) or that don't exist on
    disk are silently filtered out. The returned tuple preserves the
    declaration order of the *first* occurrence of each path so the
    output is deterministic.
    """
    cfg = asset_root / "desktops.cfg"
    if not cfg.is_file():
        return ()
    try:
        text = cfg.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ()

    asset_root_resolved = str(asset_root.resolve())
    seen: set[Path] = set()
    out: list[Path] = []
    for match in _BG_MACRO_RE.finditer(text):
        rel = match.group(1)
        full = (asset_root / rel).resolve()
        if not (
            str(full) == asset_root_resolved
            or str(full).startswith(asset_root_resolved + "/")
        ):
            continue
        if not full.is_file():
            continue
        if full in seen:
            continue
        seen.add(full)
        out.append(full)
    return tuple(out)
