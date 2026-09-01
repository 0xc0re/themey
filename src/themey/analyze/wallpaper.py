"""Wallpaper path + fill-mode extraction from ``desktops.cfg``.

E16 themes describe their backgrounds either through the macro grammar
from ``config/definitions`` ...

    BEGIN_BACKGROUND("name")
      SET_SOLID("100 70 40")
      ADD_BACKGROUND_SCALED("artwork/backgrounds/Alien97.jpg")
      ON_DESKTOP("0")
    END_BACKGROUND

... or, hand-rolled (Rebound, Fossils_of_the_Machines), in the raw form
those macros expand to (``config/definitions:928-944``)::

    __DESKTOP __BGN
      __NAME name
      __SOLID_COLOR 100 70 40
      __BACKGROUND_LAYER "artwork/backgrounds/Alien97.jpg" 0 0 0 0 1024 1024
      __USE_ON_DESKTOP 0
    __END

themey's recursive-descent parser expands neither, so this module is a
small text pipeline: follow ``#include`` lines to other cfgs in the
archive (``<definitions>`` is E16's system macro file and never ships,
BlueIce's stray copy is neutralized by dropping ``#define`` bodies),
strip ``/* */`` comments FIRST (Aliens ships a commented-out
``ADD_OVERLAY_IMAGE_CENTERED`` that must not be treated as live), expand
the background macros into the raw grammar with the table below, then
scan the raw grammar once. Macros/keys are attributed to their enclosing
block so each block's solid rides along with its image; text outside any
block is scanned as a solid-less pseudo-block, so bare macros (and
hand-rolled test cfgs) still work.

The 6-int ``__BACKGROUND_LAYER`` tuple is ``tile keep_aspect xjust yjust
xperc yperc`` (``backgrounds.c:306-331`` stores it verbatim), and E16
renders it in ``_BgPartFindImageSize`` + ``_BackgroundRealize``
(``backgrounds.c:490-532, 596-655``): a percent > 0 (Q10, 1024 == the
whole root window) scales that axis to the screen, a percent of 0 keeps
the image's native size on that axis; ``keep_aspect`` re-derives the
other axis from the scaled one (y wins when both are set); ``tile``
repeats the resulting tile from an origin of ``(rw - w) * xjust / 1024``;
untiled layers are blended at that offset over the block's solid.
``ADD_BACKGROUND_<variant>(file)`` expands as (``config/definitions:
943-1009``):

    TILED                         1 1   0    0    0    0
    SCALED                        0 0   0    0 1024 1024
    TILED_SCALED_VERTICALLY       1 0   0    0    0 1024
    TILED_SCALED_HORIZONTALLY     1 0   0    0 1024    0
    CENTERED                      0 1 512  512    0    0
    TILED_CENTER                  1 1 512  512    0    0
    SCALED_RETAIN_ASPECT          0 1 512  512 1024 1024
    TILED_SCALED_RETAIN_ASPECT    1 1 512  512 1024 1024
    ..._ALIGN_RIGHT               0 1 1024 512    0 1024
    ..._ALIGN_LEFT                0 1   0  512    0 1024
    ..._ALIGN_TOP                 0 1 512    0 1024    0
    ..._ALIGN_BOTTOM              0 1 512 1024 1024    0

:func:`fill_mode_for_layer` maps a tuple — never a macro name, so the raw
form gets identical treatment — onto Plasma's Image-wallpaper fill
vocabulary, which is what ``WallpaperSpec.fill_mode`` / the package's
``X-Themey-FillMode`` carry and ``apply.py`` dispatches on:

    stretch   both axes scaled, aspect dropped (SCALED; a tiled
              screen-sized layer is the same picture)
    tile      native size, repeated (TILED, TILED_CENTER)
    tile-h    scaled to screen HEIGHT, repeated across
              (TILED_SCALED_VERTICALLY — 42 corpus themes, all gradient
              strips that a plain tile would repeat vertically)
    tile-v    scaled to screen WIDTH, repeated down
    pad       native size, centered (CENTERED)
    fit       aspect kept, one or both axes pinned to the screen
              (SCALED_RETAIN_ASPECT and the ALIGN_* variants; Plasma
              centers, so the alignment is lost and noted)

Every approximation the mapping makes (lost alignment, a partial
percent, an aspect-kept tile) comes back as a reason string that
``extract_wallpaper_specs`` turns into a ``wallpaper:`` note.
``BG_FILE("f")`` is not an E16 macro but a pre-DR16 spelling some themes
still carry; it is treated as SCALED. An ``ADD_BACKGROUND_*`` variant
outside the table is shipped as ``stretch`` with a note rather than
dropped.

``SET_SOLID`` / ``__SOLID_COLOR`` matters twice. Attached to an image
spec it is the solid E16 composites the image over — e13 tiles a
mostly-transparent ``tanbg.png`` over ``SET_SOLID("0 0 0")``, and
dropping the solid left Plasma tiling the transparent PNG over an
undefined color — and for ``fit``/``pad`` it is the letterbox color.
A block that declares ONLY a solid (OPENSTEP) emits a solid-only spec
(``path=None``) so the conversion still ships a wallpaper.

``extract_wallpaper_specs`` is the real extractor; ``extract_wallpapers``
is a thin backward-compatible wrapper returning just the paths, kept for
callers that don't care about fill mode.

Things a background block can carry that are NOT wallpaper images, each
logged as a ``wallpaper:``-prefixed fidelity note (per the project's
"approximated -> report.txt" philosophy) rather than silently dropped:

* ``__FORGROUND_LAYER "<path>" ...`` / ``ADD_OVERLAY_IMAGE_*`` — a
  foreground overlay composited on top of the tiled/scaled background,
  not a background image itself. Two live uses in the corpus; themey has
  no overlay concept (baking one in would be wrong for tiled bases and
  aspect-mismatched scaled bases), so it is excluded from the wallpaper
  packages, but noted.
* A declared path that doesn't resolve to a file under ``asset_root`` —
  dropped from the output, with a note instead of silence.

Path-traversal rejections (T-05-01) stay silent, same as everywhere else
security-sensitive paths are filtered — that's a safety boundary, not a
fidelity gap worth reporting. The same guard covers ``#include`` targets.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from themey.ir import WallpaperSpec

#: Q10 percent of the root window: 1024 == the whole screen.
_FULL = 1024
#: Q10 justification: 512 == centered.
_CENTER = 512

Layer = tuple[int, int, int, int, int, int]

#: ``ADD_BACKGROUND_<variant>(file)`` -> ``__BACKGROUND_LAYER file <6 ints>``
#: (``config/definitions:943-1009``; see the module docstring table).
BACKGROUND_MACROS: dict[str, Layer] = {
    "TILED": (1, 1, 0, 0, 0, 0),
    "SCALED": (0, 0, 0, 0, _FULL, _FULL),
    "TILED_SCALED_VERTICALLY": (1, 0, 0, 0, 0, _FULL),
    "TILED_SCALED_HORIZONTALLY": (1, 0, 0, 0, _FULL, 0),
    "CENTERED": (0, 1, _CENTER, _CENTER, 0, 0),
    "TILED_CENTER": (1, 1, _CENTER, _CENTER, 0, 0),
    "SCALED_RETAIN_ASPECT": (0, 1, _CENTER, _CENTER, _FULL, _FULL),
    "TILED_SCALED_RETAIN_ASPECT": (1, 1, _CENTER, _CENTER, _FULL, _FULL),
    "SCALED_RETAIN_ASPECT_ALIGN_RIGHT": (0, 1, _FULL, _CENTER, 0, _FULL),
    "SCALED_RETAIN_ASPECT_ALIGN_LEFT": (0, 1, 0, _CENTER, 0, _FULL),
    "SCALED_RETAIN_ASPECT_ALIGN_TOP": (0, 1, _CENTER, 0, _FULL, 0),
    "SCALED_RETAIN_ASPECT_ALIGN_BOTTOM": (0, 1, _CENTER, _FULL, _FULL, 0),
}

#: The fill-mode vocabulary (``WallpaperSpec.fill_mode`` /
#: ``X-Themey-FillMode``). ``apply.py`` dispatches on exactly these.
FILL_MODES: frozenset[str] = frozenset(
    {"stretch", "tile", "tile-h", "tile-v", "pad", "fit"}
)
TILE_FILL_MODES: frozenset[str] = frozenset({"tile", "tile-h", "tile-v"})

# --- preprocessing --------------------------------------------------------

_INCLUDE_RE = re.compile(
    r'^[ \t]*#include[ \t]+(?:<([^>\n]+)>|"([^"\n]+)")[^\n]*', re.MULTILINE
)
# C-style block comments; stripped before any macro scanning.
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
# A #define with its backslash-continued body (a shipped definitions copy).
_DEFINE_RE = re.compile(r"^[ \t]*#define\b(?:[^\\\n]|\\\n|\\.)*", re.MULTILINE)

# --- macro grammar -> raw grammar -----------------------------------------

_BEGIN_RE = re.compile(
    r'BEGIN_BACKGROUND\(\s*"?([^")]*?)"?\s*\)', re.IGNORECASE
)
_END_RE = re.compile(r"\bEND_BACKGROUND\b", re.IGNORECASE)
_SET_SOLID_RE = re.compile(
    r'SET_SOLID\(\s*"\s*(\d+)\s+(\d+)\s+(\d+)\s*"\s*\)', re.IGNORECASE
)
# Group 1: the macro's variant suffix ("TILED", "SCALED_RETAIN_ASPECT",
# ...) or None for bare BG_FILE. Group 3: the quoted path.
_BG_MACRO_RE = re.compile(
    r"""(?:ADD_BACKGROUND_(\w+)|(BG_FILE))\(\s*"([^"]+)"\s*\)""",
    re.IGNORECASE,
)
_OVERLAY_RE = re.compile(
    r'(ADD_OVERLAY_IMAGE_\w+)\(\s*"([^"]+)"\s*\)', re.IGNORECASE
)

# --- raw grammar ----------------------------------------------------------

_BLOCK_RE = re.compile(r"__DESKTOP\s+__BGN(.*?)\b__END\b", re.DOTALL)
_NAME_RE = re.compile(r'__NAME\s+(?:"([^"]*)"|(\S+))')
_SOLID_COLOR_RE = re.compile(r"__SOLID_COLOR\s+(\d+)\s+(\d+)\s+(\d+)")
_LAYER_RE = re.compile(
    r'__BACKGROUND_LAYER\s+(?:"([^"]+)"|(\S+))'
    r"\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)"
)
_FORGROUND_LAYER_RE = re.compile(r'__FORGROUND_LAYER\s+(?:"([^"]+)"|(\S+))')


def fill_mode_for_layer(
    tile: int, keep_aspect: int, xjust: int, yjust: int, xperc: int, yperc: int
) -> tuple[str, tuple[str, ...]]:
    """Map one ``__BACKGROUND_LAYER`` tuple onto a Plasma fill mode.

    Returns ``(mode, reasons)`` — *mode* is one of :data:`FILL_MODES`,
    *reasons* the approximations made (empty when the mapping is exact),
    each a sentence fragment the caller prefixes with the image name.

    The decision follows E16's renderer (module docstring): a percent > 0
    means "this axis spans the screen", so

    * tiled + both axes spanned = one screen-sized tile = ``stretch``
      (or ``tile-h`` when ``keep_aspect`` re-derives the width from the
      height, which is what E16 does when both percents are set);
    * tiled + height spanned = ``tile-h``; tiled + width = ``tile-v``;
      tiled + neither = ``tile``;
    * untiled + both spanned = ``fit`` with ``keep_aspect``, else
      ``stretch``;
    * untiled + one axis spanned = ``fit`` (E16 pins that axis and lets
      the other follow — with ``keep_aspect`` that IS a fit on the
      pinned axis; without it the other axis stays native, which Plasma
      cannot express, so the closest mode is still ``fit``);
    * untiled + neither = ``pad`` (native, placed by justification).
    """
    reasons: list[str] = []
    scaled_x = xperc > 0
    scaled_y = yperc > 0

    if tile:
        if scaled_x and scaled_y:
            mode = "tile-h" if keep_aspect else "stretch"
        elif scaled_y:
            mode = "tile-h"
        elif scaled_x:
            mode = "tile-v"
        else:
            mode = "tile"
    elif scaled_x and scaled_y:
        mode = "fit" if keep_aspect else "stretch"
    elif scaled_x or scaled_y:
        mode = "fit"
    else:
        mode = "pad"

    for axis, perc in (("x", xperc), ("y", yperc)):
        if 0 < perc != _FULL:
            reasons.append(
                f"E16 scales {axis} to {perc}/1024 of the screen, which "
                "Plasma cannot express; pinned to the whole screen"
            )
    if mode in ("tile-h", "tile-v") and keep_aspect:
        reasons.append(
            "E16 keeps the tile's aspect when scaling it to the screen; "
            "Plasma's tiled fill leaves the tile's other axis at its "
            "native size"
        )
    if mode == "fit" and not keep_aspect:
        reasons.append(
            "E16 scales one axis to the screen and leaves the other at "
            "its native size; Plasma fits both axes"
        )
    if mode in ("fit", "pad") and (xjust, yjust) != (_CENTER, _CENTER):
        reasons.append(
            f"E16 aligns it at ({xjust}, {yjust})/1024 of the screen; "
            "Plasma centers it"
        )
    if mode in TILE_FILL_MODES and (xjust, yjust) != (0, 0):
        reasons.append(
            f"E16 starts the tiling at ({xjust}, {yjust})/1024 of the "
            "screen; Plasma tiles from the top-left corner"
        )
    return mode, tuple(reasons)


def _inside(full: Path, root_resolved: str) -> bool:
    return str(full) == root_resolved or str(full).startswith(root_resolved + "/")


def _read_with_includes(
    path: Path, asset_root: Path, root_resolved: str, visited: set[Path]
) -> str:
    """*path*'s text with every resolvable ``#include`` of an archive file
    spliced in (recursively; a visited set breaks cycles, the T-05-01
    guard drops targets outside the archive, missing files such as
    ``<definitions>`` vanish silently)."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""

    def splice(m: re.Match[str]) -> str:
        rel = m.group(1) or m.group(2)
        full = (asset_root / rel).resolve()
        if not _inside(full, root_resolved) or full in visited or not full.is_file():
            return ""
        visited.add(full)
        return "\n" + _read_with_includes(full, asset_root, root_resolved, visited) + "\n"

    return _INCLUDE_RE.sub(splice, text)


def _expand_macros(text: str, note: Callable[[str], None]) -> str:
    """Rewrite the ``config/definitions`` background macros into the raw
    grammar so one scanner handles both spellings."""
    text = _BEGIN_RE.sub(lambda m: f"__DESKTOP __BGN\n__NAME {m.group(1)}\n", text)
    text = _END_RE.sub("\n__END\n", text)
    text = _SET_SOLID_RE.sub(
        lambda m: f"__SOLID_COLOR {m.group(1)} {m.group(2)} {m.group(3)}", text
    )

    def layer(m: re.Match[str]) -> str:
        variant, rel = m.group(1), m.group(3)
        if variant is None:  # BG_FILE
            ints = BACKGROUND_MACROS["SCALED"]
        else:
            ints = BACKGROUND_MACROS.get(variant.upper())
            if ints is None:
                note(
                    f"wallpaper: {rel!r}: unknown macro ADD_BACKGROUND_"
                    f"{variant}; treated as ADD_BACKGROUND_SCALED"
                )
                ints = BACKGROUND_MACROS["SCALED"]
        return f'__BACKGROUND_LAYER "{rel}" ' + " ".join(map(str, ints))

    text = _BG_MACRO_RE.sub(layer, text)
    # Overlay geometry is irrelevant (note-only); any 5-int tail will do.
    text = _OVERLAY_RE.sub(lambda m: f'__FORGROUND_LAYER "{m.group(2)}" 1 512 512 0 0', text)
    return text


def _parse_solid(body: str) -> tuple[int, int, int] | None:
    m = _SOLID_COLOR_RE.search(body)
    if m is None:
        return None
    r, g, b = (min(int(m.group(i)), 255) for i in (1, 2, 3))
    return (r, g, b)


def extract_wallpaper_specs(
    asset_root: Path, notes: list[str] | None = None
) -> tuple[WallpaperSpec, ...]:
    """Return every distinct wallpaper declared in ``<asset_root>/desktops.cfg``
    (and the archive cfgs it ``#include``s).

    Paths that escape ``asset_root`` (T-05-01) are silently filtered out.
    Paths that don't exist on disk are also dropped, but — unlike a
    traversal escape — that's a fidelity gap, not a safety boundary, so a
    ``wallpaper:`` note is appended to *notes* (when given) instead of
    staying silent. Same for ``__FORGROUND_LAYER`` / ``ADD_OVERLAY_IMAGE_*``
    overlay images, which are excluded from the returned specs but noted,
    and for every fill-mode approximation :func:`fill_mode_for_layer`
    reports (see module docstring). The returned tuple preserves the
    declaration order of the *first* occurrence of each path (its fill
    mode wins if the same path is later declared with a different one) so
    the output is deterministic. A block that declares only a solid yields
    a solid-only spec (``path=None``).
    """
    cfg = asset_root / "desktops.cfg"
    if not cfg.is_file():
        return ()
    asset_root_resolved = str(asset_root.resolve())
    text = _read_with_includes(
        cfg, asset_root, asset_root_resolved, {cfg.resolve()}
    )
    if not text:
        return ()
    text = _COMMENT_RE.sub(" ", text)
    text = _DEFINE_RE.sub(" ", text)

    def note(msg: str) -> None:
        if notes is not None:
            notes.append(msg)

    # The macro expansion joins statements with ";" in config/definitions;
    # a hand-rolled cfg may copy that spelling.
    text = _expand_macros(text, note).replace(";", "\n")

    # (block name, body) per __DESKTOP block, plus the residual text
    # outside every block as one nameless, solid-less pseudo-block.
    blocks: list[tuple[str, str]] = []
    residual_parts: list[str] = []
    last_end = 0
    for bm in _BLOCK_RE.finditer(text):
        residual_parts.append(text[last_end : bm.start()])
        body = bm.group(1)
        nm = _NAME_RE.search(body)
        name = (nm.group(1) if nm.group(1) is not None else nm.group(2)) if nm else ""
        blocks.append((name, body))
        last_end = bm.end()
    residual_parts.append(text[last_end:])
    blocks.append(("", "\n".join(residual_parts)))

    seen: set[Path] = set()
    seen_solids: set[tuple[int, int, int]] = set()
    out: list[WallpaperSpec] = []

    for block_name, body in blocks:
        solid = _parse_solid(body) if block_name else None
        block_emitted = False
        for match in _LAYER_RE.finditer(body):
            rel = match.group(1) if match.group(1) is not None else match.group(2)
            full = (asset_root / rel).resolve()
            if not _inside(full, asset_root_resolved):
                continue  # T-05-01 — safety boundary, stays silent
            if not full.is_file():
                note(
                    f"wallpaper: {rel!r} declared in desktops.cfg but not "
                    "found in the archive; skipped"
                )
                continue
            block_emitted = True
            if full in seen:
                continue
            seen.add(full)
            layer: Layer = tuple(int(match.group(i)) for i in range(3, 9))  # type: ignore[assignment]
            mode, reasons = fill_mode_for_layer(*layer)
            for reason in reasons:
                note(f"wallpaper: {rel!r} ({mode}): {reason}")
            out.append(
                WallpaperSpec(
                    path=full, fill_mode=mode, solid_rgb=solid, name=block_name,
                )
            )

        # Solid-only block: E16 paints a flat color; ship that.
        if not block_emitted and solid is not None:
            if solid in seen_solids:
                continue
            seen_solids.add(solid)
            out.append(
                WallpaperSpec(
                    path=None, fill_mode="stretch", solid_rgb=solid,
                    name=block_name,
                )
            )
            note(
                f"wallpaper: background {block_name!r} declares only "
                f"SET_SOLID; generating a flat rgb{solid} wallpaper"
            )

    # Live overlays: real overlays exist in the grammar but themey has no
    # compositing story for them (wrong for tiled bases); note-only.
    for layer_match in _FORGROUND_LAYER_RE.finditer(text):
        rel = layer_match.group(1) or layer_match.group(2)
        note(
            f"wallpaper: __FORGROUND_LAYER {rel!r} is a foreground overlay "
            "themey cannot composite, not a wallpaper image; background "
            "used without it"
        )

    return tuple(out)


def extract_wallpapers(asset_root: Path) -> tuple[Path, ...]:
    """Bare-path view of :func:`extract_wallpaper_specs`, for callers that
    don't need fill mode."""
    return tuple(
        spec.path
        for spec in extract_wallpaper_specs(asset_root)
        if spec.path is not None
    )
