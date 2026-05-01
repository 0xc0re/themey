---
phase: 01-parser-aurorae-foundation
plan: 01-02
subsystem: security
tags: [tarfile, safe-extract, archive, cve-2007-4559, cve-2025-4330, security]

requires:
  - phase: 01-01
    provides: pyproject.toml + uv project scaffold with locked deps

provides:
  - src/themey/etheme/archive.py — safe_extract algorithm, RawTheme dataclass, extract() contextmanager, UnsafeArchiveError
  - src/themey/etheme/__init__.py — package stub
  - tests/fixtures/Aliens.etheme — real-world E16 canary fixture (2.4 MB)
  - tests/fixtures/build_malicious_archives.py — regenerable malicious fixture generator
  - tests/fixtures/malicious/ — 7 attack-vector tar.gz fixtures
  - tests/test_archive.py — 9 tests (7 negative + Aliens canary + caps sanity)

affects:
  - 01-03 (parser receives validated asset_root from extract())
  - 01-09 (CLI calls extract() before any other work)
  - all future plans that open .etheme archives

tech-stack:
  added: []
  patterns:
    - "two-pass tar extraction: regular files in pass 1, symlinks resolved by content copy in pass 2"
    - "UnsafeArchiveError raised before any file is written outside tmpdir"
    - "tempfile.TemporaryDirectory(prefix='themey-') for private 0700 tempdir"
    - "_find_theme_root: rglob for ROOT_MARKERS, shortest path wins"

key-files:
  created:
    - src/themey/etheme/__init__.py
    - src/themey/etheme/archive.py
    - tests/fixtures/build_malicious_archives.py
    - tests/fixtures/Aliens.etheme
    - tests/fixtures/malicious/path_traversal.tar.gz
    - tests/fixtures/malicious/absolute_path.tar.gz
    - tests/fixtures/malicious/symlink_escape.tar.gz
    - tests/fixtures/malicious/oversize_file.tar.gz
    - tests/fixtures/malicious/oversize_count.tar.gz
    - tests/fixtures/malicious/no_root_marker.tar.gz
    - tests/fixtures/malicious/device_file.tar.gz
    - tests/test_archive.py
  modified: []

key-decisions:
  - "Two-pass extraction: regular files in pass 1, symlinks resolved by content copy in pass 2 — no OS symlinks ever created in tmpdir"
  - "Symlink validation in pass 1 (reject if linkname resolves outside dest), copy in pass 2 (copy target bytes) — aligns with Look-and-Feel packages forbidding symlinks"
  - "_find_theme_root uses rglob for both markers, shortest path wins — Aliens has borders.cfg at root so asset_root == extraction root"

patterns-established:
  - "from themey.etheme.archive import extract; with extract(path) as raw: — the only way any code opens .etheme archives"
  - "UnsafeArchiveError message strings: 'path-traversal', 'symlink escape', 'unsafe member type', 'too large', 'too many entries', 'marker'"

requirements-completed: [PARSE-03]

duration: ~5min
completed: "2026-05-01"
---

# Phase 01 Plan 02: Safe Archive Extraction Summary

**Two-pass tar validator mitigating CVE-2007-4559/CVE-2025-4330: rejects path-traversal, symlink escape, hardlinks, device files, oversize members/counts/totals; resolves E16 archive symlinks to regular files; identifies theme root via borders.cfg/init.cfg shortest-path scan.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-01T21:25:23Z
- **Completed:** 2026-05-01T21:30:00Z
- **Tasks:** 2
- **Files created:** 12

## Accomplishments

- All 7 attack-vector fixtures rejected with `UnsafeArchiveError` before any file is written outside the private tmpdir
- Aliens.etheme (196 members, 3 internal symlinks) extracts cleanly; all 3 symlinks resolved to regular files by content copy
- `_find_theme_root` correctly returns extraction root (borders.cfg is at depth 1 in Aliens)
- 9 tests pass (7 parametrized negative tests + positive Aliens canary + caps sanity)

## Task Commits

1. **Task 1: Build malicious-archive fixture generator + copy Aliens canary** - `63c49e6` (chore)
2. **Task 2: Implement archive.py (RED)** - `1a816f7` (test)
3. **Task 2: Implement archive.py (GREEN)** - `3671a3d` (feat)

**Plan metadata:** (docs commit below)

_TDD task has separate RED (test) and GREEN (feat) commits._

## Reject-Message Strings

These are the exact substrings each attack vector produces (tests use `in` checks):

| Fixture | Attack Vector | Error Substring |
|---------|--------------|-----------------|
| path_traversal.tar.gz | `../etc/passwd` member name | `"path-traversal"` |
| absolute_path.tar.gz | `/tmp/evil` absolute member | `"path-traversal"` |
| symlink_escape.tar.gz | symlink → `../../../etc/passwd` | `"symlink escape"` |
| oversize_file.tar.gz | 9 MB member (cap 8 MB) | `"too large"` |
| oversize_count.tar.gz | 600 entries (cap 500) | `"too many entries"` |
| no_root_marker.tar.gz | no borders.cfg/init.cfg | `"marker"` |
| device_file.tar.gz | CHRTYPE member | `"unsafe member type"` |

## Aliens.etheme Symlink Resolution

All 3 symlinks in Aliens.etheme resolved successfully to regular files:

| Symlink | Target | Resolved |
|---------|--------|---------|
| `fonts.cfg` | `fonts.theme.cfg` | Yes — byte-equal copy |
| `ABOUT/aircut3.ttf` | `../ttfonts/aircut3.ttf` | Yes — byte-equal copy |
| `ABOUT/avgardm.ttf` | `../ttfonts/avgardm.ttf` | Yes — byte-equal copy |

No symlinks resolved to non-existent targets; none skipped silently.

`RawTheme.asset_root` is the directory directly containing `borders.cfg` — for Aliens this is the extraction root (the archive's top-level directory).

## Files Created/Modified

- `src/themey/etheme/__init__.py` — package stub
- `src/themey/etheme/archive.py` — safe_extract implementation (127 lines)
- `tests/fixtures/build_malicious_archives.py` — 7-fixture generator script
- `tests/fixtures/Aliens.etheme` — 2.4 MB real-world canary
- `tests/fixtures/malicious/*.tar.gz` — 7 attack-vector fixtures
- `tests/test_archive.py` — 9-test suite (TDD RED)

## Decisions Made

- **Two-pass extraction** chosen over single-pass: symlinks can point to files written later in the archive; pass 1 writes regular files, pass 2 reads and copies symlink targets. No OS symlinks ever live in the tmpdir.
- **Pass 2 silently skips missing targets** (not a raise) — pass 1 already validated the linkname resolves inside dest; if the file is absent post-extraction that's an unexpected state but not a security issue.
- **`frozenset` for ROOT_MARKERS** — immutable, hashable, O(1) lookup.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff UP035 — import from `typing` instead of `collections.abc`**
- **Found during:** Task 2 verification
- **Issue:** `from typing import Generator` should be `from collections.abc import Generator` in Python 3.9+
- **Fix:** `uv run ruff check --fix` auto-corrected the import
- **Files modified:** src/themey/etheme/archive.py
- **Verification:** `ruff check` passes, 9 tests still pass
- **Committed in:** 3671a3d (Task 2 GREEN commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Trivial import modernization. No behavioral change.

## Issues Encountered

None — plan executed cleanly. Aliens.etheme was present at the expected path (`~/src/wilbs/ethemes/e16/Aliens.etheme`).

## Known Stubs

None — this plan produces validated extraction infrastructure, no UI or data sources.

## Threat Flags

No new surface beyond the plan's explicit threat model. All T-02-01 through T-02-11 threats addressed in `_safe_extract_all`.

## Next Phase Readiness

- `extract()` contextmanager is ready for Plan 01-03 (parser) to consume `raw.asset_root`
- Aliens.etheme canary is committed and passes extraction — ready for Plan 01-09 integration test
- All 7 attack-vector fixtures committed — negative test suite is complete

---
*Phase: 01-parser-aurorae-foundation*
*Completed: 2026-05-01*

## Self-Check: PASSED

Files exist:
- FOUND: src/themey/etheme/__init__.py
- FOUND: src/themey/etheme/archive.py
- FOUND: tests/fixtures/Aliens.etheme
- FOUND: tests/fixtures/build_malicious_archives.py
- FOUND: tests/test_archive.py

Commits exist:
- FOUND: 63c49e6 (chore — fixtures)
- FOUND: 1a816f7 (test — RED)
- FOUND: 3671a3d (feat — GREEN)
