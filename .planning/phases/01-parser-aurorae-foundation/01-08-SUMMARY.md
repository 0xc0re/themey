---
phase: 01-parser-aurorae-foundation
plan: "08"
subsystem: post-generate
tags:
  - install
  - atomic
  - html-preview
  - report
  - xdg-open
  - slug
dependency_graph:
  requires:
    - 01-01  # ir.py (Theme IR), paths.py, fake_home fixture
    - 01-05  # build_theme (Theme IR populated)
    - 01-07  # generate.aurorae.write (source_dir to install)
  provides:
    - themey.slug.slugify(name) -> str
    - themey.install.deploy(theme_name, source_dir) -> Path
    - themey.install.InstallError
    - themey.report.write(theme, out_path) -> Path
    - themey.preview.render(theme, out_path) -> Path
    - themey.external.open_preview_unless_headless(html_path) -> bool
  affects:
    - 01-09  # CLI pipeline composes all five functions
tech_stack:
  added: []
  patterns:
    - "Atomic install via os.replace with backup-then-rollback (INSTALL-01)"
    - "html.escape() on all theme-derived strings in preview HTML (T-08-02)"
    - "subprocess.Popen (non-blocking) for xdg-open — not subprocess.run (T-08-05)"
    - "50-note cap in preview HTML (T-08-04 DoS mitigation)"
    - "slugify: strip .etheme suffix + path separators + leading dots + non-[A-Za-z0-9_-]"
key_files:
  created:
    - src/themey/slug.py
    - src/themey/install.py
    - src/themey/report.py
    - src/themey/preview.py
    - src/themey/external.py
    - tests/test_slug.py
    - tests/test_install.py
    - tests/test_report.py
    - tests/test_preview.py
    - tests/test_external.py
  modified: []
decisions:
  - "slugify strips .etheme suffix so display name is clean (Aliens not Aliens-etheme)"
  - "install.deploy stages to same filesystem as target — caller responsibility; documented in install.py docstring"
  - "report.txt section headers are '## Preserved', '## Approximated', '## Skipped'"
  - "preview.html is <!doctype html> (lowercase per HTML5 spec)"
  - "kwriteconfig6 command built as a concatenated string to stay under 100-char line limit"
metrics:
  duration_minutes: 15
  completed_date: "2026-05-01"
  tasks_completed: 3
  files_created: 10
---

# Phase 01 Plan 08: Post-Generate Pipeline (Install + Preview + Report) Summary

**One-liner:** Atomic filesystem install (os.replace backup-then-rename), HTML preview with palette-driven mocked titlebar and XSS-safe html.escape, report.txt three-section scaffold (Preserved/Approximated/Skipped), headless-aware xdg-open launcher (Popen, SSH_CONNECTION detection), and path-traversal-safe slugifier.

## Output

### slugify Rules (slug.py)

Character set: `[A-Za-z0-9_-]+`

Transformations applied in order:
1. Strip `.etheme` suffix (case-insensitive) — `"Aliens.etheme"` → `"Aliens"`
2. Take basename only — strips path separators: `"../etc.etheme"` → `"etc"` (after suffix strip)
3. Strip leading dots — `".hidden"` → `"hidden"`
4. Replace all non-`[A-Za-z0-9_-]` runs with single hyphen
5. Collapse multiple consecutive hyphens to one
6. Strip leading/trailing hyphens
7. Raise `ValueError` if result is empty (e.g. `"..."`, `"!!!@@@"`, `""`)

### install.deploy Rollback Behavior

Rollback protocol verified by `test_deploy_rollback_on_failure`:
1. Source dir `nonexistent` passed — `is_dir()` guard raises `InstallError` immediately
2. The OLD content at the target was preserved — no partial state left
3. No orphaned `.themey-old` backup directories left after either success or failure

All 5 install tests pass. Idempotent re-runs verified by `test_deploy_idempotent_rerun`.

### report.txt Section Headers

Exact headers (as written to file):

```
## Preserved
## Approximated
## Skipped
```

Tests use case-insensitive substring matching so minor capitalization changes won't break them.

### preview.html Validation

- Starts with `<!doctype html>` (lowercase, HTML5 compliant)
- Closes with `</html>`
- All theme-derived strings pass through `html.escape()`: display_name, name (plugin_id), notes, skipped_borders
- XSS test: `<script>alert(1)</script>` in notes renders as `&lt;script&gt;alert(1)&lt;/script&gt;`
- Notes capped at 50 entries in HTML body; overflow shown as `"... and N more (see report.txt)"`

### End-to-End Compose (Aliens Canary)

```
plan-08 components compose end-to-end with Aliens canary
```

Components from Plans 05, 07, 08 compose correctly: build_theme → write (aurorae) → write_report → render → all files present with expected content.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ruff E501 line-too-long in preview.py**
- **Found during:** Task 2 GREEN ruff check
- **Issue:** `skipped_safe = html.escape(...)` and the `kwriteconfig6` command lines exceeded 100-char limit
- **Fix:** Broke `skipped_safe` across two lines; extracted `kwrite_cmd` as a concatenated string built before the f-string template
- **Files modified:** `src/themey/preview.py`
- **Commit:** 034301f (bundled with GREEN commit)

### Plan Acceptance Criterion Note

The `subprocess.run` grep check returns 0 (correct — external.py uses only Popen). The two occurrences of `DISPLAY` and `WAYLAND_DISPLAY` in external.py each appear twice in the code (once in comment, once in actual `os.environ.get` call).

## Known Stubs

None — all five modules implement their full Phase 1 contracts. report.py explicitly marks Phase 2/3/4 sections as "deferred to later phase" which is by design (not stubs — the scaffold notes are the intended output for Phase 1).

## Threat Flags

No new security surface introduced beyond what is already modeled in the plan threat register (T-08-01 through T-08-06). All mitigations are implemented:
- T-08-01: slugify path-traversal sanitization — implemented and tested
- T-08-02: XSS via notes — html.escape on all theme-derived strings — tested
- T-08-03: rollback leaves no partial state — tested
- T-08-04: 50-note cap in preview HTML — implemented
- T-08-05: SSH/headless suppression — implemented and tested

## Self-Check: PASSED

Files verified to exist:
- `src/themey/slug.py` — FOUND
- `src/themey/install.py` — FOUND
- `src/themey/report.py` — FOUND
- `src/themey/preview.py` — FOUND
- `src/themey/external.py` — FOUND
- `tests/test_slug.py` — FOUND
- `tests/test_install.py` — FOUND
- `tests/test_report.py` — FOUND
- `tests/test_preview.py` — FOUND
- `tests/test_external.py` — FOUND

Commits verified:
- test(01-08) RED Task 1: 1ea24eb
- feat(01-08) GREEN Task 1: 5c9ef75
- test(01-08) RED Task 2: 5a27e2e
- feat(01-08) GREEN Task 2: 034301f
- test(01-08) RED Task 3: 1fea092
- feat(01-08) GREEN Task 3: b728b1c

Test count: 205 passed (30 new in this plan), 0 failures.
Aliens canary: CANARY OK — report has 3 sections, HTML has "Aliens" + "System Settings"
