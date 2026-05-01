---
phase: 01-parser-aurorae-foundation
plan: 05
subsystem: analyze
tags: [analyze, borders, iclasses, tclasses, fallback, build_theme, tdd, ir, e16]
dependency_graph:
  requires: [01-01, 01-02, 01-03, 01-04]
  provides: [build_theme, build_border, build_iclasses, build_tclasses, discover_by_filename]
  affects: [01-07, 01-08, 01-09]
tech_stack:
  added: []
  patterns:
    - "_block_name() helper: checks head_values first, then __NAME KeyVal child (handles both modern and legacy E16 macro naming)"
    - "Storage policy: iclasses.py stores resolved Path unconditionally; build_theme logs missing-asset notes"
    - "State collapse deduplication: scratch list per iclass, set-deduplicated into main notes"
    - "Titlebar bounds: TITLE_BAR iclass_name substring only (not all ACTION_MOVE parts)"
key_files:
  created:
    - src/themey/analyze/borders.py
    - src/themey/analyze/iclasses.py
    - src/themey/analyze/tclasses.py
    - src/themey/analyze/fallback.py
    - src/themey/analyze/build_theme.py
    - tests/test_analyze_borders.py
    - tests/test_analyze_iclasses.py
    - tests/test_analyze_tclasses.py
    - tests/test_analyze_fallback.py
    - tests/test_build_theme.py
  modified:
    - src/themey/analyze/__init__.py
decisions:
  - "iclasses.py stores resolved Path unconditionally (never None for missing file); build_theme logs missing-asset note when not .is_file()"
  - "Titlebar bounds computed from TITLE_BAR iclass name only — not all ACTION_MOVE parts (CORNER_TL also has ACTION_MOVE but is the move-handle corner, not titlebar text area)"
  - "TCLASS state context keywords recognized regardless of whether they carry a value (Aliens __NORMAL has '*font-default' value)"
  - "Both modern (head_values) and legacy macro (__NAME KeyVal child) block naming handled via _block_name() helper in all three extractor modules"
  - "State collapse deduplication: scratch list per iclass; set membership guard before appending to main notes"
metrics:
  duration: "12 minutes"
  completed: "2026-05-01"
  tasks_completed: 3
  files_created: 10
  files_modified: 1
---

# Phase 01 Plan 05: AST → Theme IR Composer Summary

**One-liner:** Five analyze-layer modules (borders, iclasses, tclasses, fallback, build_theme) composing AST + asset_root into a frozen Theme IR — Aliens canary produces left='XAI', right='', border L35/R20/T30/B25, TEXT1.fg_active=(255,255,200), 5 skipped borders, 104 notes.

## What Was Built

### borders.py — BorderSpec extraction

- `select_default_border(borders)`: picks block with name "DEFAULT" first; falls back to first block with `__BORDER_PART` child; returns None if empty.
- `extract_button_parts(border_block)`: walks `__BORDER_PART` Block children; preserves `aclass=None` null sentinel when `__ACLASS` is absent.
- `build_border(border_block)`: reads `__BORDER_SIZE_{LEFT,RIGHT,TOP,BOTTOM}` and delegates to extract_button_parts.
- `_block_name(block)`: checks `head_values[0]` first, then `__NAME` KeyVal child (handles both modern and legacy macro naming).

### iclasses.py — IClassSpec dict + raw state map

- `build_iclasses(iclass_blocks, asset_root)`: returns `(dict[str, IClassSpec], dict[str, dict[str, Path | None]])`.
- EDGE_SCALING order is L R T B (indices 0-3); per Pitfall 1 in 01-RESEARCH.md.
- T-05-01 mitigation: paths resolving outside asset_root are set to None (belt-and-suspenders after safe_extract).
- Raw state map includes all declared states (including sticky/disabled) for AURORAE-04 collapse downstream.
- `_block_name()` helper handles both naming conventions.

### tclasses.py — TClassSpec dict

- `build_tclasses(tclass_blocks)`: walks `__TCLASS` blocks; uses state context pattern.
- `FG_COLOR_KEYS = ("__FORGROUND_COLOR", "__FOREGROUND_COLOR", "__COLOR")` — misspelling first per E16's primary form.
- State context keywords (`__NORMAL`, `__NORMAL_ACTIVE`, etc.) recognized regardless of whether they carry a value — Aliens uses `__NORMAL '*font-default'` (with value) as the state setter.
- `_block_name()` helper handles both naming conventions.

### fallback.py — PARSE-05 filename-pattern discovery

- `CANONICAL_FILENAMES`: 13 iclass entries mined from wilbs's corpus list, including all corners, edges, and buttons.
- `discover_by_filename(asset_root)`: rglob `*.png`; basename-indexed; first canonical match per priority order wins.
- Not exercised by Aliens.etheme (cfgs parse cleanly); hook exists for malformed-cfg corpus themes.

### build_theme.py — Top-level orchestrator

- `build_theme(asset_root, ast_nodes, *, name, display_name, author, scale)` → `Theme`
- Pipeline: borders → iclasses → tclasses → AURORAE-04 state collapse → button classification → left/right binning → palette.
- PARSE-05 fallback: when no `__BORDER` blocks, calls `discover_by_filename`; either way produces a valid `Theme`.
- State collapse deduplication: scratch list per iclass; set-guard before appending to main notes.
- Titlebar bounds from `TITLE_BAR` iclass_name substring only.
- AURORAE-02: every spatial-fallback decision logged to `Theme.notes`.

## Aliens Canary Results

| Property | Expected | Actual |
|----------|----------|--------|
| `border.name` | DEFAULT | DEFAULT |
| `border_size_left` | 35 | 35 |
| `border_size_right` | 20 | 20 |
| `border_size_top` | 30 | 30 |
| `border_size_bottom` | 25 | 25 |
| `len(border.parts)` | ≥ 8 | 12 |
| `left_buttons` | 'XAI' | 'XAI' |
| `right_buttons` | '' | '' |
| `TEXT1.fg_active` | (255, 255, 200) | (255, 255, 200) |
| `TEXT1.fg_normal` | (200, 200, 150) | (200, 200, 150) |
| `len(iclasses)` | ≥ 4 | 78 |
| `len(tclasses)` | ≥ 1 | 12 |
| `len(notes)` | ≥ 4 | 104 |
| `skipped_borders` | non-empty | ('BORDERLESS', 'FIXED_SIZE', 'ICONBOX', 'PAGER_TOP', 'SHAPED') |

**Aliens skipped border names:** BORDERLESS, FIXED_SIZE, ICONBOX, PAGER_TOP, SHAPED (5 total)

## Test Results

| Test File | Tests | Status |
|-----------|-------|--------|
| tests/test_analyze_borders.py | 9 | ✓ All passed |
| tests/test_analyze_iclasses.py | 11 | ✓ All passed |
| tests/test_analyze_tclasses.py | 8 | ✓ All passed |
| tests/test_analyze_fallback.py | 9 | ✓ All passed |
| tests/test_build_theme.py | 9 | ✓ All passed |
| **Total** | **46** | **✓** |

Full suite: 145/145 passing (0 regressions).

## Key Decision: Missing Image Storage Policy

**Decision:** `iclasses.py` stores the resolved `Path` unconditionally — never `None` for missing files. `build_theme.py` logs a missing-asset note when `not path.is_file()`. `None` means "this state keyword was not declared in the AST at all" — a distinct semantic from "declared but file missing on disk."

**Rationale:** Preserving the declared path unconditionally allows Plan 01-07 `decoration_svg._png_bytes` to distinguish "was declared but missing" from "never existed in cfg." Phase 1 logs the distinction so the user can audit in report.txt. The SVG generator falls back to a 1x1 transparent placeholder when `not p.is_file()`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] All Aliens blocks use legacy __NAME KeyVal naming**

- **Found during:** Task 1 initial implementation vs. Aliens canary run
- **Issue:** `iclasses.py` and `tclasses.py` had `if not block.head_values: continue` which skipped every Aliens block since Aliens uses legacy macro style (`__ICLASS __BGN __NAME TITLE_BAR_HORIZONTAL ...`).
- **Fix:** Added `_block_name()` helper to both modules (same pattern already in `borders.py`); replaced early-continue guard with name-extraction call.
- **Files modified:** `src/themey/analyze/iclasses.py`, `src/themey/analyze/tclasses.py`
- **Commit:** a6dd560

**2. [Rule 1 - Bug] TCLASS state context keywords with values not recognized**

- **Found during:** Task 3, Aliens canary TEXT1 tclass returned None for both colors
- **Issue:** Aliens `textclasses.cfg` uses `__NORMAL '*font-default'` (with a font value) as the state context setter. Initial implementation only recognized bare markers (`not kv.values`), so the state never got set and `__FORGROUND_COLOR` had no context to attach to.
- **Fix:** Changed the state-context condition to recognize `kv.keyword in TCLASS_STATE_CONTEXT_KEYS` regardless of whether values are present.
- **Files modified:** `src/themey/analyze/tclasses.py`
- **Commit:** a6dd560

**3. [Rule 1 - Bug] Titlebar bounds included all ACTION_MOVE parts**

- **Found during:** Task 3, Aliens canary produced `left_buttons=''` instead of 'XAI'
- **Issue:** Original code used `if part.aclass == "ACTION_MOVE" or "TITLE_BAR" in ...` to find titlebar bounds. `CORNER_TL` in Aliens has `aclass=ACTION_MOVE` but represents the move-handle corner (spanning x=0..124), making `titlebar_min_x=0`. This caused all 3 buttons (KILL@16, MAX@128, ICONIFY@146) to fall inside the titlebar range [0,773] and get dropped as overlap.
- **Fix:** Changed to only use parts with `"TITLE_BAR" in part.iclass_name.upper()` for titlebar bounds. `TITLE_BAR_HORIZONTAL` spans x=[153, 773], which correctly bins KILL/MAX/ICONIFY as left-of-titlebar.
- **Files modified:** `src/themey/analyze/build_theme.py`
- **Commit:** a6dd560

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes beyond those in the plan's threat model. T-05-01 mitigated in `build_iclasses` (path traversal → None) and noted via `Theme.notes` in `build_theme`. T-05-02 (iclass name propagation) accepted per plan — names are dict keys only, never used in shell/filename without slugify in Plan 08.

## Self-Check: PASSED
