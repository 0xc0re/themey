# Cross-Reference: wilbs (max) — parallel E16 implementation

**Discovered:** 2026-05-01 (post-init)
**Status:** Reference — wilbs is a TypeScript-based web app, themey is a Python CLI; output targets differ but the **input parser and IR are reusable** in design.

## Summary

`/home/cstory/src/wilbs/` (the "max" project) is a Next.js application with an "Enlightenment Desktop Mode" milestone (v1.1 Phase 6, shipped 2026-04-12). It ingests E16 `.etheme` archives into a CSS-variable + R2-asset bundle for in-browser theming. **It has a complete production E16 parser, a documented format reference, and a post-mortem of one architectural bug** that themey can avoid replicating.

The user's `~/src/wilbs/ethemes/e16/` directory is the same theme corpus referenced in PROJECT.md (`/home/cstory/src/wilbs/ethemes/e16/`), with sibling directories for E19/E21/E22/E25/E27 (`.edj` EFL themes — out of scope for themey).

## What's there (key files)

### Parser

| File | Purpose | Why it matters for themey |
|---|---|---|
| `src/lib/themes/e16/parse-cfg.ts` | 489-line hardened cfg parser | Reference port: state machine, `#include` resolution, `__BGN`/`__END` nesting, `__BORDER_PART` extraction with full coords, `__ICLASS` with edge scaling, `__TCLASS` with `__FORGROUND_COLOR` typo handled, `__BG_BG`/`__BG_SOLID` backgrounds, `__COLOR_MODIFIER`, legacy `__ACLASS __BORDER_PART` standalone form |
| `src/lib/themes/e16/parse-e16-archive.ts` | 330-line archive extractor | Production-validated safety caps (**32 MB total / 8 MB per file / 500 entries**), root-marker detection (scans for `borders.cfg` or `init.cfg`), all-`*.cfg`-files merging strategy, **filename-pattern fallback discovery** when cfg parsing yields incomplete results |
| `src/lib/themes/e16/parse-xpm.ts` | XPM2/XPM3 image parser | E16 themes ship XPM as well as PNG; Pillow has `XpmImagePlugin` so we don't need to port this, but it confirms XPM is in the corpus |
| `src/lib/themes/e16/types.ts` | Type definitions | Direct template for our Python `Theme` dataclass |
| `src/lib/themes/e16/__tests__/parse-cfg.test.ts` | Parser regression tests | Test fixtures we should mirror |

### Reference docs

| File | Purpose |
|---|---|
| `docs/e16-reference.md` | Canonical E16 format reference grounded in E16 source line numbers |
| `.planning/notes/e16-architecture-and-gap-matrix.md` | Post-mortem on a `__ACLASS`-related bug + full gap matrix (what wilbs parses vs. what E16 supports) |
| `.planning/phases/07-e16-button-action-fidelity-tier-1/` | Shipped phase that fixed the `__ACLASS` bug — plans, patterns, review |

## High-leverage findings (already absorbed into themey docs)

### 1. `__ACLASS` is the canonical button-action source — not spatial position

> **Wilbs's own bug post-mortem (gap-matrix.md):** "Wilbs throws away `__ACLASS` at parse time, then fakes button actions by string-matching the iclass name."

E16 represents window decoration as `__BORDER_PART` rectangles, each carrying `__ICLASS` (visual) and `__ACLASS` (behavior — `ACTION_CLOSE`, `ACTION_MAX`, `ACTION_ICONIFY`, `ACTION_SHADE`, `ACTION_RESIZE`, etc.). The `__ACLASS` value declares button intent unambiguously.

**Implication for themey:**
- Parser must capture `__ACLASS` per `__BORDER_PART` (with `null` sentinel when absent, not `undefined` — preserves a backward-compat distinction).
- AURORAE-02 button binning is **`__ACLASS`-first**, with `__ICLASS` name-pattern matching as v2 fallback for older themes that don't declare `__ACLASS`. Spatial center-of-mass is the **last** resort.

`__ACLASS` → Aurorae button-code mapping:

| `__ACLASS` value | Aurorae button code | Semantic |
|---|---|---|
| `ACTION_CLOSE` | `X` | close |
| `ACTION_MAX` | `A` | maximize/restore |
| `ACTION_ICONIFY` | `I` | minimize |
| `ACTION_SHADE` | `L` | shade (E16 had this; some Aurorae themes too) |
| `ACTION_STICK` | `S` | alldesktops (sticky) |
| `ACTION_KILL` | `X` | maps to close (no force-quit equivalent) |
| `ACTION_RESIZE` / `ACTION_RESIZE_H` / `ACTION_RESIZE_V` | (skip) | Aurorae handles resize via its own border edges |
| `ACTION_MOVE` | (skip) | titlebar drag — implicit in Aurorae |

### 2. Practical image-state model is 8 fields, not the 16-cell maximal envelope

E16's `iclass.c` defines up to 16 cells (`{normal, hilited, clicked, disabled} × {norm, active, sticky, sticky_active}`), but in practice E16 themes ship 6–8 fields with these semantics:

| Field | Window focus | Button interaction | Aurorae target |
|---|---|---|---|
| `__NORMAL` | unfocused | — | `decoration-inactive-*` |
| `__NORMAL_ACTIVE` | focused | — | `decoration-*` (the active set) |
| `__HILITED_ACTIVE` | focused | hovered | button SVG `hover` element |
| `__CLICKED_ACTIVE` | focused | pressed | button SVG `pressed` element |
| `__HILITED` | (legacy) hovered, focus-independent | hovered | fallback for `hover` |
| `__CLICKED` | (legacy) pressed, focus-independent | pressed | fallback for `pressed` |
| `__NORMAL_STICKY` | unfocused + sticky | — | (sticky semantics dropped — log to report) |
| `__NORMAL_ACTIVE_STICKY` | focused + sticky | — | (sticky semantics dropped — log to report) |

AURORAE-04's collapse mapping should target these 8, not the 16-cell envelope. Sticky variants drop with a logged note.

### 3. Production safety caps (use verbatim)

From `parse-e16-archive.ts`:
- `MAX_TOTAL_BYTES = 32 * 1024 * 1024` (32 MB total extracted)
- `MAX_FILE_BYTES = 8 * 1024 * 1024` (8 MB per file)
- `MAX_ENTRIES = 500` (entry-count cap)

These were chosen against the actual corpus and survive in production. Adopt as-is in PARSE-03.

### 4. Theme-root detection by marker scan

Don't guess whether the archive has a top-level theme dir. Walk every entry, find the shortest path containing `borders.cfg` or `init.cfg`, and treat its parent as the theme root. Other paths in the archive resolve relative to that root.

### 5. Filename-pattern fallback discovery

Some 2009-era themes have malformed `borders.cfg` files. The wilbs extractor falls back to scanning for canonical filenames: `border_top_default.png`, `border_topleft_default.png`, `button_close_active.png`, etc. This rescues themes that would otherwise produce empty output. Worth implementing — themey's PARSE-05 covers this.

### 6. Multiple borders per theme

E16 themes ship multiple `__BORDER` blocks: `DEFAULT`, `BORDERLESS`, `FIXED_SIZE`, `DIALOG`, `MENU`, `ATTENTION`, `TRANSIENT`, `INTERNAL`, etc. Aurorae has only one window decoration. **themey renders DEFAULT only**, with a logged note in `report.txt` listing the other borders that were dropped (selection rule: `DEFAULT` → first-with-parts → `borders[0]`).

### 7. `__CHANGES_SHAPE __ON` is non-rectangular

A small subset of E16 themes use shape masks (X11 SHAPE extension) for non-rectangular window frames. Aurorae is rectangular only. **themey skips shape-masked themes' shape data** with an entry in `report.txt`; the rectangular fallback still renders.

### 8. `__BACKGROUND` block format

Wallpaper definition format (verified):

```
__BACKGROUND __BGN
  __NAME DESKTOP_BG
  __BG_SOLID 32 32 64                                        ← optional fallback color
  __BG_BG "WALLPAPER_PIXMAP" 0 1 0 0 0 0                     ← imageclass-name tile keepaspect xjust yjust xperc yperc
__END
```

The `__BG_BG` value is a quoted iclass name followed by integers; the iclass's `__NORMAL` pixmap is the wallpaper. WALLPAPER-01 should:
1. Find a `__BACKGROUND` whose `__BG_BG` references an existing image class.
2. If none, fall back to a representative theme image (titlebar background, or largest PNG).
3. Use `__BG_SOLID` color as a fallback fill for the Plasma wallpaper config.

### 9. `__COLOR_MODIFIER` blocks (informational)

E16 supports per-image RGB color tinting via `__COLOR_MODIFIER` blocks. Wilbs parses them but discards them (their renderer doesn't apply tints). Aurorae has no tinting facility either, so themey also captures-and-drops, with a note in `report.txt` per theme that has them.

## What we deliberately do NOT port from wilbs

- **EDC / `.edj` parsing** (`src/lib/themes/efl/`) — for E17+ EFL themes. PROJECT.md scopes themey to DR16 only.
- **Bundle schema (`src/lib/themes/bundle-schema.ts`)** — wilbs targets a CSS-variable + R2-asset web bundle. themey targets KDE Aurorae + KColorScheme + Plasma Look-and-Feel. Different output layer; the IR shape transfers but the bundle schema itself does not.
- **Token derivation (`src/lib/themes/derive-tokens.ts`)** — wilbs derives CSS tokens (`--bg`, `--accent`, etc.). themey derives KColorScheme `[Colors:*]` sections. The k-means palette extraction approach is reusable; the output mapping is not.
- **`ResizeGrip` overlay logic** — wilbs's web renderer needed an overlay for resize affordances; KWin handles resize natively for Aurorae themes. Skip entirely.
- **MCP / R2 / Drizzle / Clerk integration** — wilbs is a multi-tenant web app. themey is single-user local CLI.

## Updates applied to themey planning docs

- `PROJECT.md` Context: cite wilbs as parallel implementation; note multiple-border + non-rectangular handling
- `REQUIREMENTS.md`:
  - PARSE-02: explicitly capture `__ACLASS` per part with null sentinel
  - PARSE-03: adopt 32 MB / 8 MB / 500-entry caps verbatim; add root-marker detection
  - PARSE-05 (new): filename-pattern fallback discovery for malformed-cfg themes
  - AURORAE-02: `__ACLASS`-first → `__ICLASS` name pattern → spatial center-of-mass cascade
  - AURORAE-04: target the 8-state practical model with sticky-variant logging
  - WALLPAPER-01: cite `__BG_BG` format and fallback rule

---
*Cross-reference compiled 2026-05-01 from /home/cstory/src/wilbs/. Future planners: read this before starting any phase that touches the parser or button binning.*
