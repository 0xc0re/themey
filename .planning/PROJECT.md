# themey

## What This Is

themey is a local Python CLI that converts Enlightenment DR16 (E16) `.etheme` archives into installable KDE Plasma 6 Look-and-Feel packages. It reads the legacy E16 config grammar (`__BORDER`, `__ICLASS`, `__TCLASS` blocks) and emits a complete modern KDE theme — Aurorae window decoration, color scheme, wallpaper, and XCursor pointer set — bundled as a one-click Plasma Global Theme. Built for one user (chris) who wants to actually run favorite 2009-era E16 themes on Plasma 6.6.4 day-to-day.

## Core Value

A user runs `themey aliens.etheme` and within seconds is staring at a Plasma desktop visibly themed with that 16-year-old E16 theme — Aurorae frame, matching colors, wallpaper, cursor — all installed and previewable.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] **PARSE-01**: Parser reads any `.etheme` archive (gzipped tar) and walks E16's `__BLOCK __BGN ... __END` config grammar including `#include` directives
- [ ] **PARSE-02**: Parser extracts the canonical structure: borders, image classes (with `__EDGE_SCALING` 9-patch values), text classes (titlebar text + colors), button parts (position + glyph image), backgrounds, cursors
- [ ] **AURORAE-01**: Generates a valid Aurorae window decoration: `decoration.svg` with FrameSvg-named element IDs (`decoration-left`, `-top`, `-topleft`, `-center`, etc. plus `-inactive` and `-maximized` variants), per-button SVGs (`close.svg`, `maximize.svg`, `minimize.svg`, `restore.svg`, plus `shade.svg` / `alldesktops.svg` / `keepabove.svg` / `keepbelow.svg` when E16 supplies them), `<name>rc` INI with correct `[General]` and `[Layout]` keys, and a `metadata.desktop`
- [ ] **AURORAE-02**: E16's arbitrary-position buttons are binned into Aurorae's `LeftButtons` / `RightButtons` groups using a center-of-mass test against titlebar midpoint
- [ ] **AURORAE-03**: 9-patch raster borders are preserved by embedding the source PNG inside `decoration.svg` as `<image>` with explicit FrameSvg hint frames driven by `__EDGE_SCALING`
- [ ] **COLORS-01**: Sample dominant colors from theme imagery (titlebar, buttons, dialog backgrounds) into a valid Plasma `.colors` file (KColorScheme INI format)
- [ ] **WALLPAPER-01**: Extract `init.cfg` background image (or fall back to a representative theme image) and produce a `~/.local/share/wallpapers/<name>/` package with `metadata.json` and `contents/images/`
- [ ] **CURSORS-01**: Convert `artwork/cursors/*.xbm` (monochrome bitmap) cursors into a modern XCursor pointer theme installed at `~/.local/share/icons/<name>-cursors/`
- [ ] **BUNDLE-01**: All four outputs are wrapped into a Plasma Global Theme (Look-and-Feel) package at `~/.local/share/plasma/look-and-feel/<name>/` (with `manifest.json` declaring `KPackageStructure=Plasma/LookAndFeel`) so the user can apply the entire theme with one `plasma-apply-lookandfeel <name>` invocation (`lookandfeeltool` is now an alias for the same)
- [ ] **CLI-01**: Single command form `themey <theme.etheme>` and batch form `themey --all <dir>` with per-theme output reports
- [ ] **CLI-02**: Default `--scale=2` (2× upscale of border sizes and image assets) so 13–30 px E16 titlebars are usable on modern displays; `--scale=1` and `--scale=3` accepted overrides
- [ ] **PREVIEW-01**: After conversion, generate and open a local HTML preview page showing a mocked window titlebar, color swatches, wallpaper thumbnail, and the exact `lookandfeeltool` command to activate
- [ ] **REPORT-01**: Per converted theme, write a `report.txt` listing what was preserved, what was approximated (and why), and what was skipped — so the user knows the fidelity story for that theme

### Out of Scope

- **Plasma Style (desktop theme for Plasma's own widgets — panel, popups, clock)** — E16 themes don't supply the SVG element IDs Plasma expects (clock face, slider rails, etc.), so the conversion would be largely fabricated. The link `develop.kde.org/docs/plasma/theme/quickstart/` covers this layer; we deliberately target Aurorae instead.
- **Application QStyle (Qt widget style)** — Translating E16's dialog/button bitmaps to a Qt `QStyle` plugin requires a separate C++ project. Out of scope; Plasma's built-in Breeze remains for app widgets.
- **E17 / EFL `.edj` themes** — Different format and rendering model. DR16 only.
- **E16 sounds, tooltips, focuslist, dock, iconbox, pager** — No clean Plasma 6 equivalent; would be invented mappings with no payoff.
- **Reverse direction (Plasma → E16)** — Solving the wrong problem.
- **Cross-platform / non-Linux** — Plasma is Linux/BSD-only.
- **Live-reload / GUI app** — CLI is sufficient for daily use; an HTML preview is the only UI.

## Context

- **The theme catalog**: ~100+ `.etheme` archives in `/home/cstory/src/wilbs/ethemes/e16/`, dated 2009 from `themes.effx.us`. Sizes range 80 KB to 4 MB. Format unchanged from current E16 release.
- **E16 source available locally** at `/home/cstory/Downloads/e16-1.0.31/` — used as ground-truth reference for the config grammar (`src/borders.c`, `src/iclass.c`, `src/tclass.c`, `src/config.c`, `src/menus.c`). We do not link to or invoke the E16 binary; we re-implement the parser in Python because the grammar is small, stable, and we want full control over output.
- **E16 theme structure** (verified by extracting `Aliens.etheme`): root-level `borders.cfg`, `imageclasses.cfg`, `buttons.cfg`, `cursors.cfg`, `init.cfg`, `menustyles.cfg`, `textclasses.cfg`, `tooltips.cfg`, `windowmatches.cfg`, `fonts.cfg`, `desktops.cfg`. Subdirs `borders/`, `imageclasses/`, `artwork/`, `ttfonts/`. `ABOUT/MAIN` carries title + author metadata.
- **Coordinate convention**: E16 borders use a hybrid percent-of-window + absolute-pixel coord system, where `__TOPLEFT_X_PERCENTAGE 1024` represents 100% (1.0 in 10-bit fixed-point). Conversion logic must respect this.
- **`__EDGE_SCALING` field order is `L R T B`** (left, right, top, bottom) — verified against E16 source `iclass.c` (`sscanf("%i %i %i %i", &l, &r, &t, &b)`) and the `EImageBorder { left, right, top, bottom }` struct in `eimage.h`. Do not invert this.
- **State model collapse**: E16 supports up to 16 image-state cells (`{normal, hilited, clicked, disabled}` × `{norm, active, sticky, sticky_active}`). Aurorae has only 3 targets (`active`, `inactive`, `maximized`). The collapse mapping is opinionated and lossy — every conversion logs which E16 states were dropped or collapsed into which Aurorae state.
- **Look-and-Feel package format**: outer LnF bundle requires `manifest.json` with `KPackageStructure=Plasma/LookAndFeel`, **not** `metadata.desktop`. The Aurorae sub-package inside still uses `metadata.desktop`. The LnF tree forbids symlinks anywhere — symlinks in a source `.etheme` (e.g. `Aliens.etheme` has `fonts.cfg -> fonts.theme.cfg`) must be resolved at extraction.
- **Tar safety is non-optional**: `tarfile.extractall` is unsafe even with the Python 3.12+ `filter="data"` default (CVE-2025-4330 path-traversal bypass). Phase 1 ships a custom member-by-member `safe_extract` validator from day one.
- **Minimum FrameSvg ID set is 18** (9 active suffixes × 2 for active/inactive: `left`, `right`, `top`, `bottom`, `topleft`, `topright`, `bottomleft`, `bottomright`, `center`). Maximized variants are optional in practice (verified: Edna theme on chris's machine ships without them and works).
- **XBM cursors are 1-bit + sibling `.mask` file** (e.g. `cursor.xbm` + `cursor.xbm.mask` in `artwork/cursors/`). Both must be combined into a premultiplied ARGB PNG before `xcursorgen`.
- **Parallel TypeScript implementation exists** at `/home/cstory/src/wilbs/src/lib/themes/e16/` (the "max" project, shipped v1.1 Phase 6 — Enlightenment Desktop Mode for in-browser theming). Hardened parser (489 LoC), production-validated extraction caps (32 MB total / 8 MB per file / 500 entries), theme-root marker scan (`borders.cfg` or `init.cfg`), filename-pattern fallback discovery, full `__ACLASS` capture per `__BORDER_PART`, `__BG_BG` background parsing, `__COLOR_MODIFIER` capture. **Read it before writing the Python port** — it answers most questions and pre-resolves a buttons-fire-resize bug they shipped and post-mortemed. Detail in `.planning/research/WILBS-REFERENCE.md`.
- **`__ACLASS` is the canonical button-action source — not spatial position.** Wilbs's gap-matrix post-mortem: throwing away `__ACLASS` and faking actions by `__ICLASS` name-matching shipped a buttons-fire-resize bug. Our parser must capture `__ACLASS` per `__BORDER_PART` (with `null` sentinel when absent, not `undefined`). Button binning is `__ACLASS`-first, then `__ICLASS` name pattern, then spatial center-of-mass.
- **Multiple borders per theme**: E16 themes ship `DEFAULT`, `BORDERLESS`, `FIXED_SIZE`, `DIALOG`, `MENU`, `ATTENTION`, etc. Aurorae has only one window decoration. themey renders **DEFAULT only** (selection rule: `DEFAULT` → first border with positioned parts → `borders[0]`); other borders log a SKIPPED entry in `report.txt`.
- **`__CHANGES_SHAPE __ON`** indicates non-rectangular borders (X11 SHAPE extension). Aurorae is rectangular only. themey ignores the shape data and renders the rectangular bounding frame, with a SKIPPED note in `report.txt`.
- **Practical image-state model is 8 fields, not 16**: in the corpus, themes use `__NORMAL`, `__NORMAL_ACTIVE`, `__HILITED_ACTIVE`, `__CLICKED_ACTIVE`, `__HILITED`, `__CLICKED`, plus optional `__NORMAL_STICKY` / `__NORMAL_ACTIVE_STICKY`. AURORAE-04's collapse maps these 8 to Aurorae's 3; sticky variants drop with a logged note (Aurorae has no per-desktop button state).
- **Target Plasma version**: developed against Plasma 6.6.4 / KWin 6.6.4 (chris's machine). Should work on any 6.x release because Aurorae's FrameSvg spec and `lookandfeeltool` are stable across the Plasma 6 line.
- **Authoritative spec sources**: `develop.kde.org/docs/plasma/aurorae/` for Aurorae window decorations; `develop.kde.org/docs/plasma/theme/` for Plasma Style (the layer we're explicitly NOT targeting). KColorScheme `.colors` format is plain INI. XCursor format is well-documented.
- **Aurorae buttons code letters**: `X`=close, `I`=minimize, `A`=maximize/restore, `S`=alldesktops, `F`=keepabove, `B`=keepbelow, `L`=shade, `H`=help, `N`=appmenu (6.3+), `M`=menu. Used in `[General] LeftButtons` / `RightButtons` strings.
- **Verified KDE theme dirs on chris's system**: `~/.local/share/aurorae/themes/` (has Sweet-Dark / Sweet-Dark-transparent / Edna), `~/.local/share/plasma/desktoptheme/` (has Sweet, Sweet-Ambar-Blue, Edna). Confirms target install paths.

## Constraints

- **Tech stack**: Python 3 (assume 3.11+, present on the system). Pillow for image manipulation. Standard library for tarfile, gzip, configparser (output INI), argparse, pathlib, xml.etree (SVG output). No heavy frameworks.
- **Compatibility**: Plasma 6.x. Linux only. Targets KWin's Aurorae decoration plugin (the standard one, included in every Plasma install).
- **Dependencies on E16**: zero runtime dependency — we read the source for grammar reference only.
- **Output discipline**: every install path is under `~/.local/share/...` so a conversion is fully reversible by deleting the named directories. No system-wide writes. No root.
- **Fidelity philosophy**: faithful where the format maps cleanly, sensible defaults where it doesn't (button grouping, missing button glyphs default to a system fallback). When the converter has to approximate, it logs to `report.txt`.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Target Aurorae (window decoration) over Plasma Style (widget layer) for borders | E16 themes are fundamentally window-manager themes; Aurorae's FrameSvg + button grouping is a near-direct mapping. Plasma Style would require fabricating IDs E16 doesn't supply. | — Pending |
| Bundle outputs into a Plasma Global Theme (Look-and-Feel) package | One-command activation via `lookandfeeltool -a <name>` matches the "use them daily" goal. | — Pending |
| Faithful + smart fallback (not strict 1:1, not "inspired by") | Strict 1:1 would skip too many themes due to button-position constraints; "inspired by" loses too much character. The middle path matches user intent. | — Pending |
| Default 2× upscale of border/title sizes | E16 titlebars are 13–30 px — unusable on modern displays without scaling. Override available via `--scale`. | — Pending |
| From-scratch Python parser for E16 config grammar (no E16 runtime) | Grammar is small, stable, and full output control matters more than reusing the C parser. | — Pending |
| Embed source PNG inside SVG with FrameSvg hint frames (no rasterize-to-vector step) | Vectorizing complex theme imagery would lose character; embedding PNG keeps fidelity and KWin's FrameSvg renderer handles 9-patch stretching natively. | — Pending |
| Custom `safe_extract` for tar archives in Phase 1 (no `tarfile.extractall`) | CVE-2025-4330 bypasses the Python 3.12+ `filter="data"` default. Source `.etheme` files are 16+ years old, sometimes contain symlinks, and Look-and-Feel packages forbid symlinks anyway — explicit member validation is the only safe path. | — Pending |
| Default action after convert: install + open HTML preview + print activation command (no auto-switch) | "Install + auto-switch" risks surprising the user mid-conversion; explicit activation step is the safer daily-use posture. | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-05-01 after initialization*
