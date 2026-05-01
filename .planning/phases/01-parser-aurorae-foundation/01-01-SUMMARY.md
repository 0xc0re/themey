---
phase: 01-parser-aurorae-foundation
plan: 01-01
subsystem: scaffold
tags: [scaffold, ir, paths, tdd]
dependency_graph:
  requires: []
  provides:
    - pyproject.toml with locked deps
    - src/themey/ir.py (Theme IR contract)
    - src/themey/paths.py (XDG path helpers)
    - src/themey/log.py (logging facade)
    - tests/conftest.py (fake_home fixture)
  affects:
    - all future plans in Phase 01 (import themey.ir.Theme)
    - all test files (use fake_home fixture)
tech_stack:
  added:
    - Pillow 12.2.0
    - Typer 0.25.1
    - pytest 9.0.3
    - syrupy 5.1.0
    - ruff 0.15.12
    - pyright 1.1.409
    - hatchling (build backend)
  patterns:
    - frozen dataclass IR with single mutable accumulator (Theme.notes)
    - XDG_DATA_HOME-aware path helpers (monkeypatchable in tests)
    - TDD red-green cycle for core dataclasses and path resolution
key_files:
  created:
    - pyproject.toml
    - .gitignore
    - uv.lock
    - .python-version
    - src/themey/__init__.py
    - src/themey/__main__.py
    - src/themey/ir.py
    - src/themey/paths.py
    - src/themey/log.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_ir.py
    - tests/test_paths.py
  modified: []
decisions:
  - "Theme.notes is the ONLY mutable field on the frozen Theme dataclass — analyze stage appends, report/preview reads"
  - "XDG paths read os.environ at call time (not module load) so monkeypatching works correctly in tests"
  - "__main__.py uses type: ignore[import-not-found] for cli import (Plan 09 creates themey.cli)"
metrics:
  duration: "~5 minutes"
  completed: "2026-05-01"
  tasks_completed: 3
  files_created: 13
---

# Phase 01 Plan 01: Project Scaffold + Frozen Theme IR Summary

Bootstrap the themey uv-managed Python package with all locked dev/runtime deps, a frozen-dataclass IR module, XDG-aware paths module, and `fake_home` test fixture.

## What Was Built

**uv project with hatchling backend** at Python 3.11+ baseline (3.12 used for dev). All four dep groups installed and verified:

| Package | Requested | Resolved |
|---------|-----------|----------|
| Pillow | >=12.2,<13 | 12.2.0 |
| Typer | >=0.25,<0.26 | 0.25.1 |
| pytest | >=9.0,<10 | 9.0.3 |
| syrupy | >=5.1,<6 | 5.1.0 |
| ruff | >=0.15,<0.16 | 0.15.12 |
| pyright | >=1.1.409,<2 | 1.1.409 |

**Theme IR dataclass hierarchy** (`src/themey/ir.py`):

| Class | Frozen | Fields |
|-------|--------|--------|
| `Palette` | yes | titlebar_active, titlebar_inactive, text_active, text_inactive |
| `IClassSpec` | yes | name, edge_scaling(4-tuple), normal, normal_active, hilited, hilited_active, clicked, clicked_active, normal_sticky, normal_active_sticky |
| `TClassSpec` | yes | name, fg_normal, fg_active |
| `ButtonPart` | yes | iclass_name, aclass, tl_x_pct, tl_x_abs, tl_y_pct, tl_y_abs, br_x_pct, br_x_abs, br_y_pct, br_y_abs |
| `BorderSpec` | yes | name, border_size_left/right/top/bottom, parts(tuple) |
| `Theme` | yes | name, display_name, author, scale, asset_root, border, iclasses, tclasses, button_codes, left_buttons, right_buttons, palette, notes(mutable list), skipped_borders |

**`fake_home` fixture signature** (`tests/conftest.py`):
```python
@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch HOME + XDG_DATA_HOME to tmp_path. Returns the home dir."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    (tmp_path / ".local" / "share").mkdir(parents=True, exist_ok=True)
    return tmp_path
```

## Commits

| Hash | Type | Description |
|------|------|-------------|
| b89a234 | chore | initialize uv project + pin locked stack |
| e4cb3df | test | add failing tests (RED phase) |
| 78184fb | feat | implement Theme IR + XDG paths skeleton (GREEN) |
| cf562fa | feat | add fake_home fixture |
| d3cdcac | fix | resolve ruff C408/E501 and pyright import-not-found |

## Test Results

6 tests pass, 0 failures:
- `test_ir.py::test_theme_is_frozen` — FrozenInstanceError raised on field mutation
- `test_ir.py::test_iclass_spec_has_required_fields` — IClassSpec constructs correctly
- `test_ir.py::test_theme_notes_is_mutable` — notes list mutates while Theme is frozen
- `test_paths.py::test_aurorae_themes_default` — XDG default path from HOME
- `test_paths.py::test_aurorae_themes_xdg_override` — XDG_DATA_HOME override
- `test_paths.py::test_fake_home_routes_paths` — fake_home fixture wires paths into tmp_path

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] ruff C408 — dict() call in test_ir.py**
- **Found during:** overall verification after Task 3
- **Issue:** `_make_theme()` used `dict(name=...)` syntax; ruff C408 requires dict literal
- **Fix:** rewrote as `{"name": ...}` dict literal
- **Files modified:** tests/test_ir.py
- **Commit:** d3cdcac

**2. [Rule 1 - Bug] ruff E501 — docstring line too long in test_ir.py**
- **Found during:** overall verification after Task 3
- **Issue:** `test_theme_notes_is_mutable` docstring exceeded 100-char line limit
- **Fix:** rewrote docstring in multi-line format
- **Files modified:** tests/test_ir.py
- **Commit:** d3cdcac

**3. [Rule 1 - Bug] pyright reportMissingImports on `__main__.py`**
- **Found during:** overall verification after Task 3
- **Issue:** `from themey.cli import app` fails pyright because `cli.py` is created in Plan 09
- **Fix:** added `# type: ignore[import-not-found]` inline comment
- **Files modified:** src/themey/__main__.py
- **Commit:** d3cdcac

## Known Stubs

None — this is the scaffold plan. No UI components or data sources wired yet.

## Threat Flags

None — no new network endpoints, auth paths, or trust-boundary surface introduced. The `paths._xdg_data_home()` env-var read is addressed by T-01-01 (accepted) in the plan's threat model.

## Self-Check: PASSED
