# Requirements: themey

**Defined:** 2026-05-01
**Core Value:** A user runs `themey aliens.etheme` and within seconds is staring at a Plasma desktop visibly themed with that 16-year-old E16 theme — Aurorae frame, matching colors, wallpaper, cursor — all installed and previewable.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Parser

- [x] **PARSE-01**: Parser reads any `.etheme` archive (gzipped tar) and walks E16's `__BLOCK __BGN ... __END` config grammar including `#include` directives, C-style `/* */` comments, and `#`-comments
- [x] **PARSE-02**: Parser extracts the canonical structure: borders (with `__ACLASS` captured per `__BORDER_PART` with `null` sentinel when absent — NOT undefined; this distinguishes "parser saw no `__ACLASS`" from "field not surfaced yet"), image classes (with `__EDGE_SCALING L R T B` 9-patch values), text classes (titlebar text + colors, including E16's misspelled `__FORGROUND_COLOR` key with `__FOREGROUND_COLOR` / `__COLOR` tolerant fallbacks), button parts (position + glyph image), `__BACKGROUND` blocks (`__BG_SOLID R G B` and `__BG_BG "<iclass>" tile keepaspect xjust yjust xperc yperc` formats), `__COLOR_MODIFIER` blocks (captured for the report even though Aurorae has no tinting facility), cursors
- [x] **PARSE-03**: Custom `safe_extract` validates every tar member by path before extraction (rejects path-traversal, symlink-escape, hardlinks, and absolute paths) — replacing `tarfile.extractall` to mitigate CVE-2007-4559 / CVE-2025-4330. Enforces production-validated caps: **32 MB total extracted size, 8 MB per file, 500 entries max**. Identifies theme root by scanning for `borders.cfg` or `init.cfg` (shortest path wins; other paths in the archive resolve relative to that root)
- [x] **PARSE-04**: Coordinate evaluator correctly handles E16's hybrid `(window_dim × pct/1024) + absolute` model, including intentional negative absolute offsets (e.g. `pct=1024, abs=-27` ⇒ "27 px from right edge")
- [x] **PARSE-05**: When cfg parsing yields incomplete results (missing image classes or no border with positioned image references), parser falls back to filename-pattern discovery scanning for canonical 2009-era names (`border_top_default.png`, `border_topleft_default.png`, `button_close_active.png`, etc.) — rescues malformed-cfg themes from the corpus

### Aurorae Window Decoration

- [x] **AURORAE-01**: Generates a valid Aurorae window decoration with all 18 required FrameSvg element IDs (`decoration-{topleft,top,topright,left,center,right,bottomleft,bottom,bottomright}` × `{active, inactive}`) in a single `decoration.svg`, plus per-button SVGs (`close.svg`, `maximize.svg`, `minimize.svg`, `restore.svg`, plus `shade.svg` / `alldesktops.svg` / `keepabove.svg` / `keepbelow.svg` when E16 supplies them), `<name>rc` INI with correct `[General]` and `[Layout]` keys, and *both* `metadata.desktop` and `metadata.json`
- [x] **AURORAE-02**: E16's button parts are mapped to Aurorae's `LeftButtons` / `RightButtons` groups via a three-tier cascade: (1) **`__ACLASS`-first** — `ACTION_CLOSE`→`X`, `ACTION_MAX`→`A`, `ACTION_ICONIFY`→`I`, `ACTION_SHADE`→`L`, `ACTION_STICK`→`S`, `ACTION_KILL`→`X`; (2) `__ICLASS` name pattern fallback for parts without `__ACLASS` (`BUTTON_CLOSE`→`X`, `BUTTON_MAXIMIZE`→`A`, `BUTTON_ICONIFY`/`BUTTON_MINIMIZE`→`I`, etc.); (3) spatial **center-of-mass test against titlebar midpoint** (not window midpoint) only as a last resort. Resize/move action classes are dropped (Aurorae handles those natively). Overlap cases and any spatial-fallback decisions are logged to `report.txt`
- [x] **AURORAE-03**: 9-patch raster borders are preserved by embedding source PNG inside `decoration.svg` as base64 inline `<image>` with `preserveAspectRatio="none"` and FrameSvg hint frames driven by `__EDGE_SCALING`
- [x] **AURORAE-04**: E16's practical 8-field image-state model (`__NORMAL`, `__NORMAL_ACTIVE`, `__HILITED_ACTIVE`, `__CLICKED_ACTIVE`, `__HILITED`, `__CLICKED`, optional `__NORMAL_STICKY`, `__NORMAL_ACTIVE_STICKY`) collapses to Aurorae's 2-state model via an explicit `E16_TO_AURORAE_STATE` mapping: `__NORMAL`→`decoration-inactive-*`, `__NORMAL_ACTIVE`→`decoration-*`, `__HILITED_ACTIVE`→button SVG `hover` element, `__CLICKED_ACTIVE`→button SVG `pressed` element. Sticky variants drop with a logged note (Aurorae has no per-desktop button state); legacy `__HILITED`/`__CLICKED` serve as fallbacks when the active variants are missing. Every dropped or fallback state is logged to `report.txt`

### Color Scheme

- [ ] **COLORS-01**: Sample dominant colors from theme imagery (titlebar, buttons, dialog backgrounds, weighted) into a valid Plasma `.colors` file at `~/.local/share/color-schemes/<name>.colors` with all required `[Colors:*]` sections and `[WM]`

### Wallpaper

- [ ] **WALLPAPER-01**: Extract the `__BACKGROUND` block from `init.cfg` (or any cfg) — `__BG_BG "<iclass_name>" tile keepaspect xjust yjust xperc yperc` references an image class whose `__NORMAL` pixmap is the wallpaper bitmap; `__BG_SOLID R G B` is the fallback fill color. When no usable `__BACKGROUND` block exists, fall back to a representative theme image (titlebar background or largest PNG). Produce `~/.local/share/wallpapers/<name>/` with `metadata.json` and `contents/images/`; map `tile=1`→Plasma `tiled`, `keepaspect=1`→Plasma `letterboxed`, otherwise stretch-to-fit

### Cursor Theme

- [ ] **CURSORS-01**: Convert `artwork/cursors/*.xbm` (1-bit) + sibling `*.xbm.mask` files into ARGB-premultiplied PNGs and produce a modern XCursor pointer theme at `~/.local/share/icons/<name>-cursors/` with `index.theme` (`Inherits=Adwaita`); falls back gracefully (skip + report) if `xcursorgen` is missing from the system

### Look-and-Feel Bundle

- [ ] **BUNDLE-01**: Wraps all four prior outputs into a Plasma Global Theme at `~/.local/share/plasma/look-and-feel/<name>/` with `manifest.json` declaring `KPackageStructure=Plasma/LookAndFeel`, a `contents/defaults` INI referencing the bundled artifacts, and zero symlinks anywhere in the tree
- [ ] **BUNDLE-02**: After install, prints the exact `plasma-apply-lookandfeel <name>` activation command (resolved via `shutil.which`, with `lookandfeeltool` alias fallback)

### CLI

- [ ] **CLI-01**: Single-theme form `themey <theme.etheme>` and batch form `themey --all <dir>` with skip-on-error in batch mode (one bad theme does not abort the run)
- [ ] **CLI-02**: `--scale=N` flag (default 2, accepts 1/2/3) controls uniform border + image upscale
- [ ] **CLI-03**: Verbosity flags `-v` / `-vv` / `-q` and idempotent re-runs (re-running on the same theme overwrites cleanly)

### Install + Uninstall

- [ ] **INSTALL-01**: Atomic install: stage to a tmpdir, then `os.replace` each top-level output dir — partial failures leave the previous install untouched
- [ ] **INSTALL-02**: Per-theme JSON install manifest at `~/.local/share/themey/manifests/<name>.json` listing every file written across all five output dirs
- [ ] **INSTALL-03**: `themey --uninstall <name>` removes every file recorded in the manifest (and the manifest itself), with `--force` to ignore missing-file warnings

### Preview + Reporting

- [ ] **PREVIEW-01**: After single-theme conversion, write a local `~/.local/share/themey/previews/<name>.html` with mocked window titlebar, color swatches, wallpaper thumbnail, list of dropped E16 states, and the activation command; auto-open via `xdg-open` unless headless / SSH / batch (suppressed in `--all`)
- [ ] **REPORT-01**: Per converted theme, write `report.txt` (alongside the install manifest) with three sections — Preserved (what mapped 1:1) / Approximated (what was lossy and how) / Skipped (what we couldn't convert and why)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### CLI ergonomics

- **CLI-V2-01**: `--list` — list installed themey-managed themes
- **CLI-V2-02**: `--inspect <theme.etheme>` — dry-run that prints what would be produced without writing
- **CLI-V2-03**: Source-directory auto-detection (find `.etheme` files in common locations)
- **CLI-V2-04**: `--force` / `--force --backup` conflict handling for name collisions
- **CLI-V2-05**: `--apply` flag (opt-in auto-activate after install)
- **CLI-V2-06**: TOML config file at `~/.config/themey/config.toml` (defaults for `--scale`, output paths)
- **CLI-V2-07**: File logging (`--log-file`) in addition to stdout

### Preview enhancements

- **PREVIEW-V2-01**: HTML side-by-side before/after view (source PNG vs converted SVG)
- **PREVIEW-V2-02**: Fake-window mockup with realistic chrome rendering

### Robustness

- **ROBUST-V2-01**: `--verify` re-validates an installed theme against its manifest
- **ROBUST-V2-02**: `--prune` removes orphaned files in install dirs not in any manifest
- **ROBUST-V2-03**: Light/dark color-scheme variants per theme
- **ROBUST-V2-04**: `--json` machine-readable output

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Plasma Style (desktop theme for Plasma's own widgets — panel, popups, clock) | E16 themes don't supply the SVG element IDs Plasma expects (clock face, slider rails, etc.); conversion would be largely fabricated |
| Application QStyle (Qt widget style) | Translating E16's dialog/button bitmaps to a Qt `QStyle` plugin is a separate C++ project — no honest mapping |
| E17 / EFL `.edj` themes | Different format and rendering model — DR16 only |
| E16 sounds, tooltips, focuslist, dock, iconbox, pager | No clean Plasma 6 equivalent — would be invented mappings with no payoff |
| Reverse direction (Plasma → E16) | Solving the wrong problem |
| Cross-platform / non-Linux | Plasma is Linux/BSD-only |
| Live-reload / GUI app | CLI is sufficient for daily use; HTML preview is the only UI |
| TTF font bundling into theme | Aurorae cannot override the title font — bundling does nothing |
| Telemetry / analytics / crash reporting | Single-user local tool — no users to track |
| Plugin system / extensibility hooks | One author, no second users — YAGNI |
| Network downloads (theme repos) | All input is local files |
| Daemon / background mode | One-shot CLI is the entire UX |
| Theme editor | We're a converter, not an editor |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PARSE-01 | Phase 1 | Complete |
| PARSE-02 | Phase 1 | Complete |
| PARSE-03 | Phase 1 | Complete |
| PARSE-04 | Phase 1 | Complete |
| PARSE-05 | Phase 1 | Complete |
| AURORAE-01 | Phase 1 | Complete |
| AURORAE-02 | Phase 1 | Complete |
| AURORAE-03 | Phase 1 | Complete |
| AURORAE-04 | Phase 1 | Complete |
| COLORS-01 | Phase 2 | Pending |
| WALLPAPER-01 | Phase 2 | Pending |
| CURSORS-01 | Phase 3 | Pending |
| BUNDLE-01 | Phase 4 | Pending |
| BUNDLE-02 | Phase 4 | Pending |
| CLI-01 | Phase 1 | Pending |
| CLI-02 | Phase 1 | Pending |
| CLI-03 | Phase 1 | Pending |
| INSTALL-01 | Phase 1 | Pending |
| INSTALL-02 | Phase 4 | Pending |
| INSTALL-03 | Phase 4 | Pending |
| PREVIEW-01 | Phase 1 | Pending |
| REPORT-01 | Phase 1 | Pending |

**Coverage:**
- v1 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

**By phase:**
- Phase 1 (Parser + Aurorae Foundation): 15 requirements — PARSE-01/02/03/04/05, AURORAE-01/02/03/04, CLI-01/02/03, INSTALL-01, PREVIEW-01, REPORT-01
- Phase 2 (Colors + Wallpaper + Full Report): 2 requirements — COLORS-01, WALLPAPER-01
- Phase 3 (XCursor Pointer Theme): 1 requirement — CURSORS-01
- Phase 4 (Look-and-Feel Bundle + Batch + Manifest + Uninstall): 4 requirements — BUNDLE-01, BUNDLE-02, INSTALL-02, INSTALL-03

**Note on multi-phase requirements:** Per the no-split rule, each requirement is mapped to exactly one phase — the first phase where work on it begins.
- CLI-01 (single + batch forms) is mapped to Phase 1 where the single-theme form ships; the batch form is implemented in Phase 4 as part of that phase's work.
- PREVIEW-01 ships an initial version in Phase 1 (mocked titlebar, dropped states, activation command); Phase 2 enriches it with color swatches and wallpaper thumbnail, and Phase 4 adds the batch-mode auto-suppression.
- REPORT-01 ships its scaffold in Phase 1 (stdout + initial sections); Phase 2 fills in the full Preserved/Approximated/Skipped semantics.
- INSTALL-01 (atomic install) ships in Phase 1 for the single-theme path; Phase 4 reuses the same primitive for the Look-and-Feel bundle and batch mode.

---
*Requirements defined: 2026-05-01*
*Last updated: 2026-05-01 — traceability filled by roadmapper*
