# Roadmap: themey

## Overview

themey converts E16 `.etheme` archives into installable KDE Plasma 6 Look-and-Feel packages. Phase 1 builds the high-risk vertical slice — parser, Aurorae window decoration generator, safe-extract, single-theme install, and HTML preview — concentrating 9 of the 12 critical pitfalls catalogued in research. Once the parser/IR/Aurorae core is verified against the canary `Aliens.etheme`, Phases 2 and 3 add the mechanical color/wallpaper/cursor outputs that complete the visual story. Phase 4 wraps everything in the Plasma Global Theme bundle and adds batch mode, install manifest, and uninstall — the surface area that makes the tool genuinely daily-use-viable across the ~100-theme corpus. v1 is shipped when Phase 4 completes; polish features (`--list`, `--inspect`, config file) are deferred to v2.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Parser + Aurorae Foundation** - Hand-rolled `.etheme` parser, safe-extract, Aurorae window decoration generator, single-theme install, HTML preview — proven on Aliens.etheme
- [ ] **Phase 2: Colors + Wallpaper + Full Report** - Color-scheme and wallpaper generators with full Preserved/Approximated/Skipped report sections and enriched HTML preview
- [ ] **Phase 3: XCursor Pointer Theme** - XBM+mask → ARGB premultiplied → XCursor conversion with graceful `xcursorgen`-missing fallback
- [ ] **Phase 4: Look-and-Feel Bundle + Batch + Manifest + Uninstall** - Plasma Global Theme wrapper, `plasma-apply-lookandfeel` activation, batch mode, install manifest, and reversible uninstall

## Phase Details

### Phase 1: Parser + Aurorae Foundation
**Goal**: User runs `themey aliens.etheme` and gets an installable Aurorae window decoration plus an HTML preview, exercising the high-risk vertical slice end-to-end on a single theme.
**Depends on**: Nothing (first phase)
**Requirements**: PARSE-01, PARSE-02, PARSE-03, PARSE-04, PARSE-05, AURORAE-01, AURORAE-02, AURORAE-03, AURORAE-04, CLI-01, CLI-02, CLI-03, INSTALL-01, PREVIEW-01, REPORT-01
**Success Criteria** (what must be TRUE):
  1. User runs `themey Aliens.etheme` and the command exits 0 with a populated `~/.local/share/aurorae/themes/Aliens/` directory containing `decoration.svg`, per-button SVGs, `<name>rc`, `metadata.desktop`, and `metadata.json`
  2. User can open System Settings → Window Decorations, see the freshly installed Aurorae theme, apply it, and observe a window framed in the converted Aliens border
  3. User opens the auto-launched HTML preview in a browser and sees a mocked titlebar, the activation command, and a list of dropped E16 image-states
  4. User extracts a malicious `.etheme` (path-traversal, symlink-escape, or absolute-path member) and themey rejects it before any file is written
  5. User can re-run `themey Aliens.etheme` and the previous install is overwritten cleanly with no leftover artefacts; `--scale=1`, `--scale=2`, `--scale=3` each produce visibly different border thicknesses
**Plans**: 9 plans
- [ ] 01-01-PLAN.md — Project scaffold (uv project, pyproject.toml, src/themey/ skeleton, frozen Theme IR, paths, fake_home fixture)
- [ ] 01-02-PLAN.md — safe_extract + 7 malicious-archive negative fixtures + Aliens canary copy (PARSE-03)
- [ ] 01-03-PLAN.md — Lexer + AST + recursive-descent parser; #include resolution; tolerates unknown keywords + `__FORGROUND_COLOR` typo (PARSE-01, PARSE-02 partial)
- [ ] 01-04-PLAN.md — Coordinate evaluator + 3-tier button binning cascade + state collapse mapping primitives (PARSE-04, AURORAE-02 algorithm, AURORAE-04 mapping)
- [ ] 01-05-PLAN.md — Analyze pipeline: AST→Theme IR; DEFAULT-only border selection; PARSE-05 fallback hook; Aliens canary integration test (PARSE-02 finalization, PARSE-05, AURORAE-04)
- [ ] 01-06-PLAN.md — Pillow primitives: NEAREST upscale, base64 PNG embed, 9-patch slice (AURORAE-03 supporting)
- [ ] 01-07-PLAN.md — Aurorae generator: decoration.svg with 18 FrameSvg IDs, per-button SVGs, <name>rc, metadata.desktop, metadata.json (AURORAE-01, AURORAE-03)
- [ ] 01-08-PLAN.md — Atomic install + report.txt scaffold + HTML preview + headless-aware xdg-open + slug sanitizer (INSTALL-01, PREVIEW-01, REPORT-01)
- [ ] 01-09-PLAN.md — CLI Typer entry point + pipeline orchestrator + Aliens E2E test + visual checkpoint on Plasma 6.6.4 (CLI-01, CLI-02, CLI-03)

### Phase 2: Colors + Wallpaper + Full Report
**Goal**: User's converted theme now ships color scheme and wallpaper alongside the Aurorae decoration, and the per-theme report fully explains the fidelity story.
**Depends on**: Phase 1
**Requirements**: COLORS-01, WALLPAPER-01
**Success Criteria** (what must be TRUE):
  1. User runs `themey Aliens.etheme` and a `~/.local/share/color-schemes/Aliens.colors` file appears, selectable from System Settings → Colors and applying a palette sampled from the source theme
  2. User finds `~/.local/share/wallpapers/Aliens/` populated with `metadata.json` and `contents/images/` and can right-click the desktop → Configure Desktop → Wallpaper to pick it
  3. User opens the HTML preview and sees color swatches and a wallpaper thumbnail next to the mocked titlebar
  4. User reads `report.txt` and finds three populated sections — Preserved, Approximated, Skipped — explaining exactly which E16 inputs mapped 1:1, which were lossy and how, and which were dropped and why
**Plans**: TBD

### Phase 3: XCursor Pointer Theme
**Goal**: User's converted theme now includes a working XCursor pointer set so the cursor is themed alongside the window frame, colors, and wallpaper.
**Depends on**: Phase 2
**Requirements**: CURSORS-01
**Success Criteria** (what must be TRUE):
  1. User runs `themey Aliens.etheme` (with `xcursorgen` available on PATH) and `~/.local/share/icons/Aliens-cursors/` is populated with a full XCursor set and `index.theme` declaring `Inherits=Adwaita`
  2. User selects the converted cursor theme in System Settings → Cursors and the pointer renders as a real cursor (not a black square or invisible glyph)
  3. User runs `themey` on a system without `xcursorgen` and the conversion completes successfully — cursors are skipped, `report.txt` records the skip, and the other outputs are unaffected
**Plans**: TBD

### Phase 4: Look-and-Feel Bundle + Batch + Manifest + Uninstall
**Goal**: User can convert their entire theme corpus in one command, activate any converted theme with a single `plasma-apply-lookandfeel` invocation, and cleanly uninstall any theme.
**Depends on**: Phase 3
**Requirements**: BUNDLE-01, BUNDLE-02, INSTALL-02, INSTALL-03
**Reuses (primary phase shown in parens)**: INSTALL-01 (Phase 1) — atomic install primitive applied to the L&F bundle; CLI-01 (Phase 1) — adds the `--all` batch form to the existing CLI dispatcher
**Success Criteria** (what must be TRUE):
  1. User runs `themey Aliens.etheme`, copies the printed `plasma-apply-lookandfeel Aliens` command into a terminal, and the entire desktop — window frames, colors, wallpaper, cursor — switches to the Aliens theme in one step
  2. User runs `themey --all /home/cstory/src/wilbs/ethemes/e16/` and themey processes every `.etheme` in the directory with skip-on-error (one bad theme does not abort the run); HTML preview is suppressed in batch
  3. User finds `~/.local/share/themey/manifests/<name>.json` for every successfully converted theme, listing every file written across all five output directories
  4. User runs `themey --uninstall Aliens` and every file recorded in the manifest disappears (along with the manifest itself); running it again with `--force` does not error on the already-missing files
  5. User runs `find ~/.local/share/plasma/look-and-feel/Aliens -type l` and gets zero hits, and `manifest.json` declares `KPackageStructure=Plasma/LookAndFeel`
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Parser + Aurorae Foundation | 0/9 | Not started | - |
| 2. Colors + Wallpaper + Full Report | 0/TBD | Not started | - |
| 3. XCursor Pointer Theme | 0/TBD | Not started | - |
| 4. Look-and-Feel Bundle + Batch + Manifest + Uninstall | 0/TBD | Not started | - |
