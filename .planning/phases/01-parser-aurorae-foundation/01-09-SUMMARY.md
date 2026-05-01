---
phase: 01-parser-aurorae-foundation
plan: "09"
subsystem: cli-pipeline
tags:
  - cli
  - pipeline
  - integration
  - typer
  - end-to-end
dependency_graph:
  requires:
    - 01-01  # ir.py (Theme IR), paths.py, log.py, fake_home fixture
    - 01-02  # etheme.archive.extract, UnsafeArchiveError
    - 01-03  # etheme.parse.parse_tree
    - 01-05  # analyze.build_theme
    - 01-06  # images stack (consumed by generate)
    - 01-07  # generate.aurorae.write, REQUIRED_FRAMESVG_IDS
    - 01-08  # install.deploy, InstallError, report.write, preview.render, external.open_preview_unless_headless, slug.slugify
  provides:
    - themey.pipeline.convert(etheme_path, *, scale) -> ConvertResult
    - themey.pipeline.ConvertResult dataclass
    - themey.cli.app (Typer entry point)
    - CLI-01: single-theme form `themey <archive.etheme>`
    - CLI-02: --scale=N flag (1, 2, or 3)
    - CLI-03: -v/-vv/-q verbosity + idempotent re-runs
  affects:
    - Phase 2+: all future plans import pipeline.convert as the standard entry point
tech_stack:
  added:
    - "Typer 0.25.1 Annotated-style API (avoids ruff B008 on typer.Argument/typer.Option in defaults)"
  patterns:
    - "pipeline.convert: with extract() lifecycle ensures asset_root valid during generate; report/preview run after block exits"
    - "Staging dir under XDG_DATA_HOME/themey/staging/ for same-filesystem os.replace atomic install"
    - "Annotated[T, typer.Argument(...)] style to satisfy ruff B008"
    - "logging.basicConfig(force=True) in log.setup_logging ensures CliRunner test output captured"
key_files:
  created:
    - src/themey/pipeline.py
    - src/themey/cli.py
    - tests/test_pipeline_aliens_canary.py
    - tests/test_cli.py
  modified: []
decisions:
  - "Annotated-style Typer API chosen over default= style to avoid ruff B008 (do not perform function call in argument defaults)"
  - "pipeline.convert runs report/preview AFTER the with extract() block — asset_root is stale outside the block but report/preview only need Theme IR data"
  - "staging dir is under XDG_DATA_HOME (same filesystem as install target) so os.replace is atomic across staging→final rename"
  - "BLE001 noqa removed — exception in top-level CLI handler is acceptable; bare Exception catch with logged error + typer.Exit(1) is the right pattern"
metrics:
  duration_minutes: 25
  completed_date: "2026-05-01"
  tasks_completed: 2
  tasks_total: 3
  files_created: 4
checkpoint_status: AWAITING_HUMAN_VERIFY
---

# Phase 01 Plan 09: CLI Integration and Pipeline Summary

**One-liner:** Typer CLI (`themey <archive.etheme>`) wired to a full pipeline orchestrator composing all Wave 1-5 outputs — archive.extract → parse_tree → build_theme → write_aurorae → install.deploy → report.write → preview.render — with --scale=N, -v/-q logging, and atomic idempotent installs.

## Phase 1 Success Criteria Status

| Criterion | Status | Evidence |
|-----------|--------|----------|
| 1. `themey Aliens.etheme` exits 0 with populated `~/.local/share/aurorae/themes/Aliens/` | PASS | test_pipeline_convert_aliens_writes_all_artifacts + CLI smoke test |
| 2. System Settings → Window Decorations shows Aliens, applies correctly | AWAITING Task 3 human checkpoint | Visual verification required on Plasma 6.6.4 |
| 3. HTML preview auto-launched, shows mocked titlebar + activation command | PASS | test_cli_aliens_end_to_end verifies Installed/Preview/Apply lines; preview.render tested in 01-08 |
| 4. Malicious .etheme rejected before any file written | PASS | test_pipeline_malicious_archive_writes_nothing |
| 5. Re-run overwrites cleanly; --scale=1/2/3 produce different BorderLeft | PASS | test_pipeline_idempotent_rerun + test_pipeline_scale_changes_BorderLeft |

## CLI Smoke Test Results

```
$ HOME=$(mktemp -d) uv run themey tests/fixtures/Aliens.etheme
INFO themey.pipeline: converting .../Aliens.etheme as Aliens (scale=2)
INFO themey.pipeline: theme: parts=12 iclasses=78 notes=104 skipped=5
INFO themey.pipeline: installed to /tmp/.../.local/share/aurorae/themes/Aliens
Installed: /tmp/.../.local/share/aurorae/themes/Aliens
Preview:   /tmp/.../.local/share/themey/previews/Aliens.html
Report:    /tmp/.../.local/share/themey/previews/Aliens.report.txt
Apply via System Settings - Window Decorations - Aliens
```

Exit code: 0. `decoration.svg` exists. `themey --help` shows scale, verbose, quiet options.

## Layout Values for Aliens Canary (Baseline)

| Scale | BorderLeft | TitleHeight | BorderBottom |
|-------|-----------|-------------|-------------|
| 1 | 35 | 26 | 6 |
| 2 | 70 | 52 | 12 |
| 3 | 105 | 78 | 18 |

Linear scaling confirmed: BorderLeft = `border_size_left * scale` = `35 * scale`.

## Test Count

- Previous total (after Plan 08): 205 tests
- New tests in this plan: 13 (6 pipeline canary + 7 CLI)
- **Total after Plan 09: 218 tests, all passing**

## Task 3: Visual Checkpoint (AWAITING)

**Status:** Task 3 (`checkpoint:human-verify`) is the blocking gate for Phase 1 completion.

**What was built (Tasks 1+2 complete):**
- `src/themey/pipeline.py` — full pipeline orchestrator
- `src/themey/cli.py` — Typer entry point
- `tests/test_pipeline_aliens_canary.py` — 6 E2E canary tests
- `tests/test_cli.py` — 7 CLI unit tests

**How to run the real install:**
```bash
cd /home/cstory/src/themey
uv run themey ~/src/wilbs/ethemes/e16/Aliens.etheme
# Or: uv run themey tests/fixtures/Aliens.etheme
```

**Visual verification steps:**
1. Browser preview opens automatically (or print the file:// URL)
2. Open System Settings → Window Decorations → verify "Aliens" appears
3. Apply and verify window frames render with Aliens borders
4. Test `--scale=1` (thinner) and `--scale=3` (thicker)
5. Test malicious archive: `uv run themey tests/fixtures/malicious/path_traversal.tar.gz` → exits non-zero
6. Re-run idempotency: run twice, second run replaces first cleanly

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Lint] Converted cli.py from default-style to Annotated-style Typer API**
- **Found during:** Task 2 GREEN ruff check
- **Issue:** `typer.Argument(...)` and `typer.Option(...)` as default values trigger ruff B008 (do not perform function call in argument defaults)
- **Fix:** Refactored all parameters to `Annotated[T, typer.Argument(...)]` / `Annotated[T, typer.Option(...)]` style — the style Typer itself recommends in its own docs
- **Files modified:** `src/themey/cli.py`
- **Commit:** d7158ad

**2. [Rule 1 - Lint] Removed unused noqa BLE001 directive from cli.py**
- **Found during:** Task 2 GREEN ruff check
- **Issue:** Plan code had `# noqa: BLE001` on the except line, but BLE001 (blind exception catch) is not enabled in this project's ruff config (ruleset is E,W,F,I,B,C4,UP,RUF — not A/BLE)
- **Fix:** Removed the noqa directive; bare `except Exception` for top-level CLI is correct without suppression
- **Files modified:** `src/themey/cli.py`
- **Commit:** d7158ad

**3. [Rule 1 - Lint] Fixed test file: unused imports, semicolon one-liners**
- **Found during:** Task 1 GREEN ruff check
- **Issue:** Plan-provided test code had `ConvertResult` imported but unused; semicolon-separated statements (`cp = RawConfigParser(); cp.optionxform = str`) trigger E702; `before`/`after`/`ei` variables assigned but never used
- **Fix:** Removed unused `ConvertResult` import, removed unused `pytest` import in test_cli.py; split semicolons to separate lines; removed unused before/after/ei assignments
- **Files modified:** `tests/test_pipeline_aliens_canary.py`, `tests/test_cli.py`
- **Commits:** 889c594, d7158ad

## Visual Checkpoint Iterations

None — Task 3 not yet reached. This section will be updated after the human-verify checkpoint.

## Known Stubs

None — pipeline.convert is fully wired. All five phase outputs (Aurorae theme, report, preview, install, slug) compose correctly. No placeholder values flow to UI rendering.

## Threat Flags

No new security surface beyond what is modeled in the plan threat register (T-09-01 through T-09-05). All mitigations implemented:
- T-09-01: malicious archive → UnsafeArchiveError caught in pipeline top-level except; test_pipeline_malicious_archive_writes_nothing passes
- T-09-02: --scale=999 rejected by Typer min=1, max=3 at parse time; test_cli_scale_4_rejected passes
- T-09-05: SSH/headless suppression via external.open_preview_unless_headless (implemented in 01-08)

## Self-Check: PASSED

Files verified to exist:
- `src/themey/pipeline.py` — FOUND
- `src/themey/cli.py` — FOUND
- `tests/test_pipeline_aliens_canary.py` — FOUND
- `tests/test_cli.py` — FOUND

Commits verified:
- test(01-09) RED Task 1: c6ac450
- feat(01-09) GREEN Task 1: 889c594
- test(01-09) RED Task 2: 434155b
- feat(01-09) GREEN Task 2: d7158ad

Test count: 218 passed (13 new in this plan), 0 failures.
CLI smoke: `uv run themey tests/fixtures/Aliens.etheme` exits 0, decoration.svg written.
`uv run themey --help` exits 0, shows scale/verbose/quiet options.
