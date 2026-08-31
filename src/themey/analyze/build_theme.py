"""Compose AST + asset_root into a frozen Theme IR.

The single contract crossing the analyze/generate seam. Every generator in
Plans 06-08 takes a ``Theme`` and writes output; none of them reach back
into the AST or asset_root for parser-level concerns.

AURORAE-04 state collapse: every iclass's raw state map is walked via
``collapse_image_states``; dropped sticky/disabled variants append a
Theme.notes entry for the user-facing report.

PARSE-05 fallback: when no ``__BORDER`` blocks are parsed (malformed cfg or
missing cfg file), ``discover_by_filename`` scans the asset_root for canonical
PNG names and logs its use to Theme.notes.

T-05-01 (path traversal in cfg paths) is mitigated in ``build_iclasses``
(path escape → None) and an additional missing-asset note is logged here
for any iclass image path that doesn't exist on disk.

``Theme.palette`` is NOT built here: it is derived from ``Theme.scheme``
(see ``analyze/colors.py``) so the decoration backends and the emitted
``.colors`` file cannot disagree about the titlebar. Change one and you
change both.
"""
from __future__ import annotations

from pathlib import Path

from themey.etheme.ast import AstNode, Block
from themey.ir import (
    BorderSpec,
    Theme,
)

from .borders import _block_name as _border_block_name
from .borders import build_border, select_default_border
from .buttons import bin_left_right, classify_button, title_part
from .colors import build_scheme, palette_from_scheme
from .coords import REFERENCE_WINDOW_WIDTH, resolve
from .cursors import extract_cursors
from .fallback import discover_by_filename
from .fonts import parse_fonts
from .iclasses import build_iclasses
from .states import collapse_image_states
from .tclasses import build_tclasses
from .wallpaper import extract_wallpaper_specs


def _collect_blocks(nodes: list[AstNode], keyword: str) -> list[Block]:
    """Collect all top-level Block nodes with the given keyword."""
    return [n for n in nodes if isinstance(n, Block) and n.keyword == keyword]


def build_theme(
    asset_root: Path,
    ast_nodes: list[AstNode],
    *,
    name: str,
    display_name: str | None = None,
    author: str | None = None,
    scale: float = 2,
) -> Theme:
    """Compose AST + asset_root into a frozen Theme IR.

    Selects the DEFAULT border; logs the others to Theme.skipped_borders.
    Builds iclasses dict (with __EDGE_SCALING + state→Path map).
    Builds tclasses dict tolerating __FORGROUND_COLOR / __FOREGROUND_COLOR / __COLOR.
    Classifies buttons via the 3-tier cascade and bins them spatially at
    REFERENCE_WINDOW_WIDTH=800.
    Applies AURORAE-04 state collapse, appending dropped-state notes.
    Falls back to filename-pattern discovery if zero __BORDER blocks were parsed.

    Returns a Theme. Theme.notes is the only mutable accumulator; it is
    populated during this call and passed into the Theme as-is.
    """
    notes: list[str] = []

    # ------------------------------------------------------------------
    # 1. Borders → BorderSpec (DEFAULT-only)
    # ------------------------------------------------------------------
    all_borders = _collect_blocks(ast_nodes, "__BORDER")
    default_block = select_default_border(all_borders)
    skipped: list[str] = []

    if default_block is not None:
        # Record non-DEFAULT border names as skipped
        for b in all_borders:
            if b is default_block:
                continue
            skipped_name = _border_block_name(b)
            if skipped_name is not None:
                skipped.append(skipped_name)
            else:
                skipped.append("(unnamed)")
        border = build_border(default_block)
    else:
        # PARSE-05 fallback hook: scan for canonical PNG filenames
        discovered = discover_by_filename(asset_root)
        if discovered:
            notes.append(
                "fallback: no __BORDER block parsed; "
                "used filename-pattern discovery (PARSE-05 hook)"
            )
        else:
            notes.append(
                "fallback: no __BORDER block AND no canonical PNGs found; "
                "using minimal synthetic border"
            )
        # Synthesize a minimal border with no parts
        border = BorderSpec(
            name="DEFAULT",
            border_size_left=4,
            border_size_right=4,
            border_size_top=18,
            border_size_bottom=4,
            parts=(),
        )

    # ------------------------------------------------------------------
    # 2. ICLASSes → IClassSpec dict + raw state map
    # ------------------------------------------------------------------
    iclass_blocks = _collect_blocks(ast_nodes, "__ICLASS")
    iclasses, raw_states = build_iclasses(iclass_blocks, asset_root)

    # Per resolved storage policy (Plan 01-05 revision iter 1): iclasses.py
    # stores resolved paths unconditionally; build_theme logs missing-asset notes.
    for ic_name, state_map in raw_states.items():
        for state_key, path in state_map.items():
            if path is not None and not path.is_file():
                notes.append(
                    f"{ic_name}: declared {state_key} -> "
                    f"'{path.name}' but file is missing from asset_root "
                    "(missing asset — image will fall back to placeholder in SVG)"
                )

    # ------------------------------------------------------------------
    # 3. TCLASSes → TClassSpec dict
    # ------------------------------------------------------------------
    tclass_blocks = _collect_blocks(ast_nodes, "__TCLASS")
    tclasses = build_tclasses(tclass_blocks)

    # ------------------------------------------------------------------
    # 3b. Fonts — standalone tolerant scan of fonts.theme.cfg / fonts.cfg
    # (the main lexer cannot represent lowercase aliases; see analyze/fonts.py).
    # ------------------------------------------------------------------
    fonts = parse_fonts(asset_root)

    # ------------------------------------------------------------------
    # 4. AURORAE-04 state collapse: log dropped sticky/disabled variants.
    #
    # We run collapse_image_states for every iclass for every Aurorae target.
    # The function itself appends dropped-state notes to `notes` for every
    # E16 sticky/disabled/clicked-active state that has no Aurorae equivalent.
    # collapse_image_states deduplicates dropped-state notes internally
    # (it only appends on first observation via the DROPPED_STATES frozenset).
    # ------------------------------------------------------------------
    _logged_drops: set[str] = set()  # deduplicate across targets
    for ic_name, state_map in raw_states.items():
        # We only need to call once per iclass; calling multiple times for
        # different targets would produce duplicate drop notes. Use a
        # scratch notes list and then deduplicate.
        scratch: list[str] = []
        for target in (
            "decoration-active",
            "decoration-inactive",
            "button-default",
            "button-hover",
            "button-pressed",
        ):
            collapse_image_states(state_map, target, scratch, ic_name)
        # Deduplicate into main notes
        for entry in scratch:
            if entry not in _logged_drops:
                _logged_drops.add(entry)
                notes.append(entry)

    # ------------------------------------------------------------------
    # 5. Buttons — apply 3-tier cascade per part; spatial fallback against
    #    titlebar bounds at REFERENCE_WINDOW_WIDTH=800.
    # ------------------------------------------------------------------
    button_codes: dict[str, str] = {}
    button_positions: list[tuple[str, int]] = []  # (code, x_center)

    # Resolve titlebar bounds first (needed for spatial fallback tier-3).
    #
    # Canonical E16 grammar (Section 6 / wilbs parse-cfg.ts:212): the title-
    # bearing part is the one flagged ``__FLAGS __FLAG_TITLE``. Any iclass
    # name is permitted (Aliens: TITLE_BAR_HORIZONTAL, e13: TITLEBAR). The
    # previous substring heuristic ``"TITLE_BAR" in iclass_name`` missed
    # e13's bareword TITLEBAR and left the bounds at the inversion sentinel.
    titlebar_min_x: int = REFERENCE_WINDOW_WIDTH
    titlebar_max_x: int = 0

    tp = title_part(border.parts)
    if tp is not None:
        tl_x = resolve(tp.tl_x_pct, tp.tl_x_abs, REFERENCE_WINDOW_WIDTH)
        br_x = resolve(tp.br_x_pct, tp.br_x_abs, REFERENCE_WINDOW_WIDTH)
        titlebar_min_x = min(tl_x, br_x)
        titlebar_max_x = max(tl_x, br_x)

    have_titlebar_geom = titlebar_max_x > titlebar_min_x

    for part in border.parts:
        tl_x = resolve(part.tl_x_pct, part.tl_x_abs, REFERENCE_WINDOW_WIDTH)
        br_x = resolve(part.br_x_pct, part.br_x_abs, REFERENCE_WINDOW_WIDTH)
        x_center = (tl_x + br_x) // 2

        if have_titlebar_geom:
            code, source = classify_button(
                part.aclass,
                part.iclass_name,
                x_center=x_center,
                titlebar_left=titlebar_min_x,
                titlebar_right=titlebar_max_x,
            )
        else:
            code, source = classify_button(part.aclass, part.iclass_name)

        # AURORAE-02: log every tier-3 spatial-fallback decision so the user
        # can audit assignments and drops in the generated report.txt.
        if source == "spatial":
            if code is not None:
                notes.append(
                    f"button '{part.iclass_name}' at x={x_center} "
                    f"assigned via spatial fallback -> '{code}' "
                    f"(titlebar=[{titlebar_min_x}, {titlebar_max_x}])"
                )
            else:
                notes.append(
                    f"part '{part.iclass_name}' at x={x_center} "
                    f"dropped via spatial fallback "
                    f"(ambiguous middle third or no geometry — "
                    f"titlebar=[{titlebar_min_x}, {titlebar_max_x}])"
                )
        elif source == "unknown_aclass":
            notes.append(
                f"part '{part.iclass_name}' has __ACLASS={part.aclass} which "
                "themey doesn't map to an Aurorae button code — dropped"
            )

        if code is None or source == "drop" or source == "unknown_aclass":
            continue
        button_codes[part.iclass_name] = code
        button_positions.append((code, x_center))

    left, right, overlap = bin_left_right(
        button_positions, titlebar_min_x, titlebar_max_x
    )
    for code, x in overlap:
        notes.append(
            f"button '{code}' at x={x} overlaps titlebar text region "
            f"[{titlebar_min_x}, {titlebar_max_x}] — "
            "dropped (no Aurorae equivalent for buttons inside titlebar text area)"
        )

    # ------------------------------------------------------------------
    # 5b. Cursors — parse __CURSOR blocks (Phase 3 will emit XCursor files).
    # ------------------------------------------------------------------
    cursors = extract_cursors(ast_nodes, asset_root)
    if cursors:
        missing = [c.name for c in cursors if c.xbm_path is None or not c.xbm_path.is_file()]
        notes.append(
            f"parsed {len(cursors)} __CURSOR blocks "
            f"(XCursor emission deferred to Phase 3)"
        )
        if missing:
            notes.append(
                f"cursors: {len(missing)} XBM file(s) missing from asset_root: "
                f"{', '.join(sorted(missing))}"
            )

    # ------------------------------------------------------------------
    # 5c. Wallpapers — scan desktops.cfg's macro syntax for image paths.
    # report.py's Preserved section reports the real installed count
    # (pipeline.py threads it back in); no separate note needed here.
    # ------------------------------------------------------------------
    wallpaper_specs = extract_wallpaper_specs(asset_root, notes)
    wallpapers = tuple(spec.path for spec in wallpaper_specs)

    # ------------------------------------------------------------------
    # 6. Colors — sample the whole KDE scheme from the border art, then
    #    derive the decoration Palette from its [WM] pair. One source of
    #    truth: what KDE paints on the titlebar and what the decoration
    #    backends paint are the same four colors by construction.
    # ------------------------------------------------------------------
    scheme = build_scheme(border, iclasses, tclasses, notes)
    palette = palette_from_scheme(scheme)

    return Theme(
        name=name,
        display_name=display_name or name,
        author=author,
        scale=scale,
        asset_root=asset_root,
        border=border,
        iclasses=iclasses,
        tclasses=tclasses,
        button_codes=button_codes,
        left_buttons=left,
        right_buttons=right,
        palette=palette,
        scheme=scheme,
        cursors=cursors,
        wallpapers=wallpapers,
        wallpaper_specs=wallpaper_specs,
        notes=notes,
        skipped_borders=tuple(skipped),
        fonts=fonts,
    )
