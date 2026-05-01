---
phase: 01-parser-aurorae-foundation
plan: 06
subsystem: images
tags: [pillow, upscale, nearest-resampling, base64, nine-patch, edge-scaling, svg]

# Dependency graph
requires:
  - phase: 01-01
    provides: project scaffold, uv/Pillow dependency setup

provides:
  - upscale_nearest(img, scale): NEAREST resampling primitive for pixel-art E16 borders
  - embed_png_b64(png_bytes): base64 data URI string for SVG <image> href embedding
  - image_to_b64_uri(img): Pillow Image convenience wrapper for embedding
  - slice_9patch(img, left, right, top, bottom): 9-region crop driven by __EDGE_SCALING (L R T B)
  - NinePatchRegions dataclass with 9 ordered PIL.Image fields

affects: [01-07-aurorae-decoration-generator, phase-02-wallpaper, phase-03-cursors]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "NEAREST resampling mandatory for pixel-art borders; photographic resampling is a different file"
    - "data URI embedding (base64) for all SVG <image> elements to prevent relative-path resolution failures"
    - "9-patch slice with explicit ValueError for oversized edges; zero-area edges allowed (L R T B all 0)"
    - "TDD RED/GREEN commits for each primitive"

key-files:
  created:
    - src/themey/images/__init__.py
    - src/themey/images/upscale.py
    - src/themey/images/embed.py
    - src/themey/images/ninepatch.py
    - tests/test_upscale.py
    - tests/test_embed.py
    - tests/test_ninepatch.py

key-decisions:
  - "upscale_nearest constrains scale to {1,2,3} at the primitive level so Plan 07 never passes an arbitrary int"
  - "LANCZOS does not appear in src/themey/images/ — enforced by file-level docstring and grep-verified"
  - "NinePatchRegions field order is topleft, top, topright, left, center, right, bottomleft, bottom, bottomright (Plan 07 iterates in this order)"
  - "slice_9patch uses > not >= for edge validation so equal-to-dimension is rejected (left+right == width means zero center, still raises ValueError)"

patterns-established:
  - "All three primitives are pure functions with no E16/KDE knowledge — keeps Plan 07 concerns cleanly separated"
  - "Phase 2 wallpaper resampling will live in a separate images/wallpaper.py; this module never imports photographic resampling"

requirements-completed:
  - AURORAE-03

# Metrics
duration: 3min
completed: 2026-05-01
---

# Phase 01 Plan 06: Pillow Image Primitives Summary

**Three pure Pillow primitives for Aurorae generation: NEAREST upscale for pixel-art borders, base64 PNG embedding for SVG href attributes, and 9-patch region slicing driven by E16 __EDGE_SCALING (L R T B) values.**

## Performance

- **Duration:** 3 min
- **Started:** 2026-05-01T21:38:07Z
- **Completed:** 2026-05-01T21:41:30Z
- **Tasks:** 3 (each with RED + GREEN TDD commits)
- **Files modified:** 7 created

## Accomplishments

- `upscale_nearest(img, scale)` uses `Image.Resampling.NEAREST` exclusively; LANCZOS does not appear anywhere in `src/themey/images/`; validated by pixel-equality quadrant test on a 2x2 checkerboard
- `embed_png_b64(png_bytes)` / `image_to_b64_uri(img)` produce clean `data:image/png;base64,...` URIs with no whitespace; roundtrip test confirms decoded bytes load back as the original image dimensions
- `slice_9patch(img, left, right, top, bottom)` returns `NinePatchRegions` with 9 cropped regions; parameter order is L R T B matching E16 `iclass.c`; raises `ValueError` with explicit message when edges exceed image dimensions
- 18 tests pass across all three test files; ruff + pyright basic clean on all files

## Task Commits

Each task was committed atomically with RED (failing test) then GREEN (implementation):

1. **Task 1: upscale.py** — RED `e561243` (test), GREEN `33797bd` (feat)
2. **Task 2: embed.py** — RED `89f35a3` (test), GREEN `9541adc` (feat)
3. **Task 3: ninepatch.py** — RED `585e950` (test), GREEN `4a47f8e` (feat)

## Files Created/Modified

- `src/themey/images/__init__.py` — empty package init (committed with Task 1 RED)
- `src/themey/images/upscale.py` — `upscale_nearest(img, scale) -> Image`; NEAREST only; ValueError on scale outside {1,2,3}
- `src/themey/images/embed.py` — `embed_png_b64(bytes) -> str`; `image_to_b64_uri(img) -> str`; DATA_URI_PREFIX constant
- `src/themey/images/ninepatch.py` — `NinePatchRegions` frozen dataclass; `slice_9patch(img, left, right, top, bottom) -> NinePatchRegions`
- `tests/test_upscale.py` — 8 tests (4 base + 4 parametrized invalid scales)
- `tests/test_embed.py` — 5 tests (prefix, no-newlines, roundtrip, convenience wrapper, empty bytes)
- `tests/test_ninepatch.py` — 5 tests (dimensions, pixel content corners, zero-scaling, oversized edges x2)

## Decisions Made

- `upscale_nearest` constrains scale to {1,2,3} at the primitive level (not just CLI) so Plan 07 never accidentally passes an arbitrary integer
- `NinePatchRegions` field order is `topleft, top, topright, left, center, right, bottomleft, bottom, bottomright` — Plan 07 must iterate in this order
- `slice_9patch` raises `ValueError` when `left+right > width` (not `>=`) — equal-to-dimension means zero-width center, which is still rejected
- LANCZOS removed even from docstring comments in `upscale.py` to satisfy `grep -c 'LANCZOS' src/themey/images/upscale.py` == 0 acceptance criterion

## Deviations from Plan

**1. [Rule 2 - Missing Critical] Removed LANCZOS from docstring comments**
- **Found during:** Task 1 acceptance criteria check
- **Issue:** The plan template docstring for upscale.py contained the word "LANCZOS" in comments (`LANCZOS BANNED for borders...`). The acceptance criterion requires `grep -c 'LANCZOS' src/themey/images/upscale.py` returns 0. Comments containing LANCZOS would fail this check.
- **Fix:** Rewrote docstring to describe the requirement positively without naming the banned resampling mode.
- **Files modified:** `src/themey/images/upscale.py`
- **Verification:** `grep -c 'LANCZOS' src/themey/images/upscale.py` returns 0; all 8 tests still pass
- **Committed in:** `33797bd` (GREEN commit for upscale)

---

**Total deviations:** 1 auto-fixed (Rule 2 — docstring wording to satisfy acceptance criterion)
**Impact on plan:** Cosmetic fix only; no behavioral change. File correctness and tests unaffected.

## Issues Encountered

None - all three primitives implemented cleanly on first attempt.

## TDD Gate Compliance

All three tasks followed the RED/GREEN sequence:

| Task | RED commit | GREEN commit | REFACTOR |
|------|-----------|-------------|---------|
| upscale.py | e561243 (test) | 33797bd (feat) | Not needed |
| embed.py | 89f35a3 (test) | 9541adc (feat) | Not needed |
| ninepatch.py | 585e950 (test) | 4a47f8e (feat) | Not needed |

## Known Stubs

None - all three primitives are complete implementations with no placeholder logic.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All functions operate on in-memory Pillow Image objects and bytes. No threat flags.

## Note for Phase 2

The wallpaper module (`images/wallpaper.py` or similar) will use photographic resampling (`Image.Resampling.LANCZOS`) for wallpaper rescaling. That module must be kept separate from this one. `src/themey/images/upscale.py` is border-only and must never import photographic resampling.

## Next Phase Readiness

- Plan 01-07 (Aurorae decoration.svg generator) can import all three primitives directly:
  - `from themey.images.upscale import upscale_nearest`
  - `from themey.images.embed import embed_png_b64, image_to_b64_uri`
  - `from themey.images.ninepatch import slice_9patch, NinePatchRegions`
- No blockers.

---
*Phase: 01-parser-aurorae-foundation*
*Completed: 2026-05-01*

## Self-Check: PASSED

- All 7 files created and confirmed present on disk
- All 6 task commits (3 RED + 3 GREEN) confirmed in git log
- 18 tests pass in final run
