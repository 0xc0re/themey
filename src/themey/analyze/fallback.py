"""PARSE-05: filename-pattern fallback discovery for malformed-cfg themes.

When the AST yields zero __BORDER blocks (or an otherwise empty Theme),
scan the extracted asset_root for canonical 2009-era E16 PNG names and
synthesize a minimal IClassSpec dict.

The pattern list is mined from wilbs's parse-e16-archive.ts, where it has
been exercised against the production corpus.

Phase 1 implements the discovery primitive; Aliens.etheme does NOT exercise
this path because its cfgs parse cleanly. Future-phase malformed-cfg themes
in the ~100-theme corpus will hit this fallback.
"""
from __future__ import annotations

from pathlib import Path

# iclass-name → list of canonical PNG basenames in priority order.
# Mined from wilbs's parse-e16-archive.ts production corpus list.
CANONICAL_FILENAMES: dict[str, list[str]] = {
    "TITLE_BAR_HORIZONTAL": [
        "border_top_default.png",
        "title_default.png",
        "title.png",
        "n_title.png",
    ],
    "BUTTON_CLOSE": [
        "button_close_active.png",
        "button_close.png",
        "close_active.png",
        "close.png",
    ],
    "BUTTON_MAXIMIZE": [
        "button_max_active.png",
        "button_max.png",
        "button_maximize_active.png",
        "button_maximize.png",
        "max_active.png",
        "max.png",
    ],
    "BUTTON_ICONIFY": [
        "button_iconify_active.png",
        "button_iconify.png",
        "button_minimize_active.png",
        "button_minimize.png",
        "iconify_active.png",
        "iconify.png",
    ],
    "BUTTON_KILL": [
        "button_kill_active.png",
        "button_kill.png",
        "kill_active.png",
        "kill.png",
    ],
    "BORDER_TOP": [
        "border_top_default.png",
        "border_top.png",
        "n_top.png",
    ],
    "BORDER_BOTTOM": [
        "border_bottom_default.png",
        "border_bottom.png",
        "n_bottom.png",
    ],
    "BORDER_LEFT": [
        "border_left_default.png",
        "border_left.png",
        "n_left.png",
    ],
    "BORDER_RIGHT": [
        "border_right_default.png",
        "border_right.png",
        "n_right.png",
    ],
    "CORNER_TL": [
        "border_topleft_default.png",
        "border_topleft.png",
        "n_topleft.png",
    ],
    "CORNER_TR": [
        "border_topright_default.png",
        "border_topright.png",
        "n_topright.png",
    ],
    "CORNER_BL": [
        "border_bottomleft_default.png",
        "border_bottomleft.png",
        "n_bottomleft.png",
    ],
    "CORNER_BR": [
        "border_bottomright_default.png",
        "border_bottomright.png",
        "n_bottomright.png",
    ],
}


def discover_by_filename(asset_root: Path) -> dict[str, Path]:
    """Recursively scan asset_root; return mapping of iclass name → first
    canonical PNG match per the priority list.

    Missing slots are absent from the returned dict; the caller decides what
    to do with unmatched entries.

    Strategy:
    1. Build a flat index: basename → resolved Path (first occurrence wins
       when multiple files share the same basename across subdirectories).
    2. For each iclass in CANONICAL_FILENAMES, try each candidate in priority
       order; the first hit is returned and the search stops for that iclass.
    """
    # Build a flat index: basename -> first resolved Path found (rglob order)
    index: dict[str, Path] = {}
    for p in asset_root.rglob("*.png"):
        name = p.name
        if name not in index:
            index[name] = p

    out: dict[str, Path] = {}
    for iclass_name, candidates in CANONICAL_FILENAMES.items():
        for cand in candidates:
            if cand in index:
                out[iclass_name] = index[cand]
                break

    return out
