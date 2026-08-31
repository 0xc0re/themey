"""Wallpaper path + fill-mode extraction from ``desktops.cfg``.

E16 themes describe their backgrounds via a macro syntax that themey's
recursive-descent parser does not expand:

    BEGIN_BACKGROUND("name")
      SET_SOLID("100 70 40")
      ADD_BACKGROUND_SCALED("artwork/backgrounds/Alien97.jpg")
      ON_DESKTOP("0")
    END_BACKGROUND

The image references we care about are the bare-quoted string arguments to
the ``ADD_BACKGROUND_*`` and ``BG_FILE`` macros. A simple regex over the raw
text is enough — we don't need a full macro expander for parse-only
purposes.

``ADD_BACKGROUND_TILED`` and its variants (``ADD_BACKGROUND_TILED_SCALED_
VERTICALLY`` etc. — any E16 background macro whose name contains
``TILED``) map to ``fill_mode="tiled"``; ``ADD_BACKGROUND_SCALED`` and
``BG_FILE`` (which E16 also renders untiled) map to ``"scaled"``. That
fill mode becomes the installed wallpaper package's ``X-Themey-FillMode``
(``generate/wallpaper.py``).

``extract_wallpaper_specs`` is the real extractor; ``extract_wallpapers``
is a thin backward-compatible wrapper returning just the paths, kept for
callers that don't care about fill mode.

Two things a background block can carry that are NOT wallpaper images,
each logged as a ``wallpaper:``-prefixed fidelity note (per the project's
"approximated -> report.txt" philosophy) rather than silently dropped:

* ``__FORGROUND_LAYER "<path>" ...`` — a foreground overlay composited on
  top of the tiled/scaled background, not a background image itself.
  themey has no overlay concept, so it's excluded from the wallpaper
  packages, but noted.
* A declared path that doesn't resolve to a file under ``asset_root`` —
  dropped from the output (as before), now with a note instead of
  silence.

Path-traversal rejections (T-05-01) stay silent, same as everywhere else
security-sensitive paths are filtered — that's a safety boundary, not a
fidelity gap worth reporting.
"""
from __future__ import annotations

import re
from pathlib import Path

from themey.ir import WallpaperSpec

# Group 1: the macro's variant suffix ("TILED", "SCALED", "TILED_SCALED_
# VERTICALLY", ...) or "" for bare BG_FILE. Group 2: the quoted path.
_BG_MACRO_RE = re.compile(
    r"""(?:ADD_BACKGROUND_(\w+)|(BG_FILE))\(\s*"([^"]+)"\s*\)""",
    re.IGNORECASE,
)

_FORGROUND_LAYER_RE = re.compile(r'__FORGROUND_LAYER\s+"([^"]+)"', re.IGNORECASE)


def _fill_mode(variant: str | None) -> str:
    """"tiled" for any ADD_BACKGROUND_TILED* variant, else "scaled"."""
    if variant and "TILED" in variant.upper():
        return "tiled"
    return "scaled"


def extract_wallpaper_specs(
    asset_root: Path, notes: list[str] | None = None
) -> tuple[WallpaperSpec, ...]:
    """Return every distinct wallpaper declared in ``<asset_root>/desktops.cfg``.

    Paths that escape ``asset_root`` (T-05-01) are silently filtered out.
    Paths that don't exist on disk are also dropped, but — unlike a
    traversal escape — that's a fidelity gap, not a safety boundary, so a
    ``wallpaper:`` note is appended to *notes* (when given) instead of
    staying silent. Same for ``__FORGROUND_LAYER`` overlay images, which
    are excluded from the returned specs but noted (see module
    docstring). The returned tuple preserves the declaration order of the
    *first* occurrence of each path (its fill mode wins if the same path
    is later declared with a different one) so the output is
    deterministic.
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
    out: list[WallpaperSpec] = []
    for match in _BG_MACRO_RE.finditer(text):
        add_variant, bg_file_variant, rel = match.groups()
        full = (asset_root / rel).resolve()
        if not (
            str(full) == asset_root_resolved
            or str(full).startswith(asset_root_resolved + "/")
        ):
            continue  # T-05-01 — safety boundary, stays silent
        if not full.is_file():
            if notes is not None:
                notes.append(
                    f"wallpaper: {rel!r} declared in desktops.cfg but not "
                    "found in the archive; skipped"
                )
            continue
        if full in seen:
            continue
        seen.add(full)
        variant = add_variant if add_variant is not None else bg_file_variant
        out.append(WallpaperSpec(path=full, fill_mode=_fill_mode(variant)))

    if notes is not None:
        for layer_match in _FORGROUND_LAYER_RE.finditer(text):
            notes.append(
                f"wallpaper: __FORGROUND_LAYER {layer_match.group(1)!r} is a "
                "foreground overlay, not a wallpaper image; excluded"
            )

    return tuple(out)


def extract_wallpapers(asset_root: Path) -> tuple[Path, ...]:
    """Bare-path view of :func:`extract_wallpaper_specs`, for callers that
    don't need fill mode."""
    return tuple(spec.path for spec in extract_wallpaper_specs(asset_root))
