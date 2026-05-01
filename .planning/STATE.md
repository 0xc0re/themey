---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
status: executing
stopped_at: Completed 01-05 build_theme composer (analyze → Theme IR)
last_updated: "2026-05-01T22:11:53.228Z"
last_activity: 2026-05-01
progress:
  total_phases: 4
  completed_phases: 0
  total_plans: 9
  completed_plans: 6
  percent: 67
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-05-01)

**Core value:** A user runs `themey aliens.etheme` and within seconds is staring at a Plasma desktop visibly themed with that 16-year-old E16 theme — Aurorae frame, matching colors, wallpaper, cursor — all installed and previewable.
**Current focus:** Phase 01 — parser-aurorae-foundation

## Current Position

Phase: 01 (parser-aurorae-foundation) — EXECUTING
Plan: 7 of 9
Status: Ready to execute
Last activity: 2026-05-01

Progress: [███████░░░] 67%

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

Last session: 2026-05-01T22:11:53.223Z
Stopped at: Completed 01-05 build_theme composer (analyze → Theme IR)
Resume file: None
