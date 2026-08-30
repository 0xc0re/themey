---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: "Phase 02 — Aurorae fidelity + render/apply tooling landed; .colors + wallpaper emission not started"
last_updated: "2026-08-30T00:00:00.000Z"
last_activity: 2026-08-29
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 14
  completed_plans: 9
  percent: 64
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-01)

**Core value:** A user runs `themey aliens.etheme` and within seconds is staring at a Plasma desktop visibly themed with that 16-year-old E16 theme — Aurorae frame, matching colors, wallpaper, cursor — all installed and previewable.
**Current focus:** Phase 02 — colors-wallpaper-full-report

## Current Position

Phase: 02 (colors-wallpaper-full-report) — EXECUTING
Plan: none active (unplanned fidelity + tooling work since 2026-05-13)
Status: Aurorae decoration verified on Plasma 6.6 via `themey render`; the
  planned Phase 2 deliverables (.colors writer, wallpaper package) are untouched
Last activity: 2026-08-29

Progress: [██████░░░░] 64%

**Shipped since the Phase 1 checkpoint** (all outside the numbered plans):

- Aurorae decoration contract corrected for Plasma 6.6 (both plugins):
  `hint-*` margins + `hint-stretch-borders`, `decoration-maximized-*` groups,
  sides/bottom capped at the KWin Oversized ceiling (48), corner art folded into
  the title band, rc key set matched to Aurorae's exact casing
- `themey render` — headless nested-KWin screenshot harness (the truth; the
  mock in `scripts/render_review.py` is only an approximation)
- `themey apply` — point the live KWin at an installed theme, with the
  BorderSize bracket chosen from the installed rc
- CLI grew a subcommand group (`convert` is the default), `--output DIR`,
  `--no-open`
- `scripts/install_theme.sh` — convert + install, optional `--apply` / `--render`
- Parser coverage: `__PADDING`, `__FLAGS`, BORDERPART extras, expanded ACLASS
  vocabulary, `__CURSOR` blocks, `desktops.cfg` backgrounds (parsed into the IR;
  cursors and wallpapers are not yet emitted)
- Test suite at 333 passed / 1 skipped, including the SVG↔rc invariant and
  perceptual-hash visual snapshots for five real themes

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: —
- Total execution time: 0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| - | - | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01-parser-aurorae-foundation P01-01 | 6m | 3 tasks | 13 files |
| Phase 01-parser-aurorae-foundation P01-06 | 3m | 3 tasks | 7 files |
| Phase 01 P05 | 12m | 3 tasks | 11 files |
| Phase 01-parser-aurorae-foundation P07 | 8m | 3 tasks | 14 files |
| Phase 01 P08 | 15 | 3 tasks | 10 files |
| Phase 01-parser-aurorae-foundation P09 (partial — checkpoint) | 25m | 2/3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- Roadmap: Narrow Phase 1 (parser + Aurorae + safe-extract + single-theme install) over wide Phase 1 — front-loads 9 of 12 critical pitfalls to one focused block (per research SUMMARY.md resolution)
- Roadmap: Coarse granularity → 4 phases (consolidates SUMMARY.md's proposed 6 by merging bundle + batch + manifest + uninstall into Phase 4, dropping the no-requirement "polish" phase)
- Roadmap: CLI-01 (single + batch) maps to Phase 1 where the single-theme form ships first; batch form is implemented in Phase 4 but the requirement is not split
- [Phase ?]: Theme.notes is the only mutable field on the frozen Theme dataclass — analyze stage appends, report/preview reads
- [Phase ?]: XDG paths read os.environ at call time (not module load) so monkeypatching works correctly in tests
- [Phase ?]: __main__.py uses type: ignore[import-not-found] for cli import (Plan 09 creates themey.cli)
- [01-06]: upscale_nearest constrains scale to {1,2,3} at primitive level so Plan 07 never passes arbitrary int
- [01-06]: NinePatchRegions field order: topleft, top, topright, left, center, right, bottomleft, bottom, bottomright (Plan 07 iterates this order)
- [01-06]: LANCZOS does not appear in src/themey/images/ — enforced at file level; Phase 2 wallpaper uses separate module
- [Phase ?]: iclasses.py stores resolved Path unconditionally; build_theme logs missing-asset notes
- [Phase ?]: Titlebar bounds: TITLE_BAR iclass_name substring only (CORNER_TL ACTION_MOVE excluded)
- [Phase ?]: TCLASS state context markers recognized with or without values (Aliens uses __NORMAL with font arg)
- [Phase ?]: slugify strips .etheme suffix so display name is clean (Aliens not Aliens-etheme)
- [Phase ?]: install.deploy stages to same filesystem as target — caller responsibility; documented in install.py docstring
- [Phase ?]: report.txt section headers: '## Preserved', '## Approximated', '## Skipped'
- [Phase ?]: preview.html: html.escape on all theme-derived strings; 50-note cap; Popen (non-blocking) for xdg-open
- [01-09]: pipeline.convert stages output under XDG_DATA_HOME/themey/staging for same-filesystem atomic os.replace
- [01-09]: Typer Annotated-style API used in cli.py to satisfy ruff B008 (no function calls in argument defaults)
- [01-09]: CLI exits non-zero + logs error on conversion failure (bare Exception catch at top-level is correct; BLE001 not in ruff ruleset)
- [post-01]: `decoration_svg.strip_thicknesses()` is the single source of truth for SVG strip thickness AND rc Border*/TitleHeight; enforced by tests/test_svg_rc_invariant.py
- [post-01]: `kwin.py` is a leaf module (no themey imports) so report and render can both use the plugin IDs and BorderSize brackets without an import cycle
- [post-01]: Sides/bottom capped at 48 — KWin's Oversized bracket ceiling; both Aurorae plugins clamp, so wider art is folded into the title band via wide left/right frame columns
- [post-01]: `themey render` (nested KWin) is the visual truth; scripts/render_review.py is explicitly an approximation

### Pending Todos

None yet.

### Blockers/Concerns

- Phase 4 prep: Verify `plasma-apply-lookandfeel` argument format (positional vs `-a`) on user's Plasma 6.6.4 system before starting Phase 4 (per SUMMARY.md Open Question 1)
- Phase 3 prep: Decide subprocess vs inline `xcursorgen` (1–2 hour spike) at Phase 3 start (per SUMMARY.md Open Question 4)

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| *(none)* | | | |

## Session Continuity

Last session: 2026-08-29
Stopped at: "Aurorae contract fix + phash snapshot regeneration + install_theme.sh"
Resume file: .planning/phases/02-colors-wallpaper-full-report/02-01-PLAN.md

Note: the Phase 2 plans (02-01 … 02-04b) were written before the fidelity and
tooling work above and have not been re-checked against the current code. Reread
them against `src/themey/` before executing — `report.py` and `preview.py` have
already moved past the "Phase 1 scaffold" they assume.
