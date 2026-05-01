---
phase: 01-parser-aurorae-foundation
plan: "07"
subsystem: generate
tags:
  - aurorae
  - svg
  - framesrg
  - kde-plasma
  - window-decoration
dependency_graph:
  requires:
    - 01-01  # ir.py (Theme, IClassSpec, BorderSpec, Palette)
    - 01-05  # build_theme + analyze stack
    - 01-06  # images.embed, images.upscale, images.ninepatch
  provides:
    - generate.aurorae.write(Theme, out_dir) -> list[Path]
    - REQUIRED_FRAMESVG_IDS constant
    - generate.desktop_writer.write_desktop
    - generate.aurorae_rc.write_aurorae_rc
    - generate.aurorae_meta.write_metadata_desktop/json
    - generate.decoration_svg.write_decoration_svg
    - generate.button_svg.write_button_svgs
  affects:
    - 01-08  # install.py + report.py consume write() output
    - 01-09  # CLI pipeline imports write as write_aurorae
tech_stack:
  added:
    - "stdlib xml.etree.ElementTree for SVG generation (register_namespace avoids ns0: mangling)"
    - "stdlib configparser.RawConfigParser + _CaseSensitiveRawConfigParser subclass (optionxform=staticmethod(str))"
    - "Hand-rolled desktop_writer (NOT configparser — preserves Name[de]=Foo localization keys)"
  patterns:
    - "post-write 18-ID validation inside write_decoration_svg (raises AssertionError if missing)"
    - "base64 PNG embed via images.embed.embed_png_b64 (no relative hrefs)"
    - "button SVG with 3-state IDs: base_id / base_id-hover / base_id-pressed"
    - "scale-linear Layout formula: BorderLeft = border_size_left * scale"
key_files:
  created:
    - src/themey/generate/__init__.py
    - src/themey/generate/desktop_writer.py
    - src/themey/generate/aurorae_rc.py
    - src/themey/generate/aurorae_meta.py
    - src/themey/generate/decoration_svg.py
    - src/themey/generate/button_svg.py
    - src/themey/generate/aurorae.py
    - tests/test_desktop_writer.py
    - tests/test_aurorae_rc.py
    - tests/test_aurorae_meta.py
    - tests/test_decoration_svg.py
    - tests/test_button_svg.py
    - tests/test_aurorae_pipeline.py
    - tests/snapshots/__snapshots__/.gitkeep
  modified: []
decisions:
  - "aurorae.py created in Task 2 (not Task 3) to resolve circular import: decoration_svg.py imports REQUIRED_FRAMESVG_IDS from aurorae for post-write validation; aurorae.py imports decoration_svg. The import inside write_decoration_svg is deferred (local import at call time, not module load) to avoid the circular dependency."
  - "_CaseSensitiveRawConfigParser subclass with optionxform = staticmethod(str) chosen over bare cp.optionxform = str — pyright basic flags the bare form as 'cannot assign method to instance'. The subclass form is the canonical configparser docs fix."
  - "Layout formula: BorderLeft = border_size_left * scale (linear). Documented as Open Question A2 tunable block in aurorae_rc._layout_values; visual gate in Plan 09 can adjust the single function."
  - "decoration_svg uses xlink:href attribute (f'{{{XLINK_NS}}}href') to match Edna's SVG 1.1 format. Modern renderers accept both href and xlink:href."
  - "Button SVG base_id is the filename without .svg (close, maximize, restore, etc.). Three <g> IDs: base_id, base_id-hover, base_id-pressed."
metrics:
  duration_minutes: 8
  completed_date: "2026-05-01"
  tasks_completed: 3
  files_created: 14
---

# Phase 01 Plan 07: Aurorae Window Decoration Generator Summary

**One-liner:** Full Aurorae generator stack — decoration.svg (18 FrameSvg IDs + base64 PNG + hint margins), `<name>rc` (RawConfigParser case-preserved INI), metadata.desktop (hand-rolled writer), metadata.json (KF6 KPlugin format), and per-button SVGs (close/maximize/restore/minimize + optional shade/alldesktops/keepabove/keepbelow) — all validated by the Aliens canary end-to-end.

## Output

### Files Written by write() for Aliens Canary (scale=2)

| File | Size |
|------|------|
| decoration.svg | 124,358 bytes |
| Aliensrc | 666 bytes |
| metadata.desktop | 302 bytes |
| metadata.json | 602 bytes |
| close.svg | 3,110 bytes |
| maximize.svg | 4,523 bytes |
| restore.svg | 4,520 bytes |
| minimize.svg | 3,191 bytes |

**Total: 8 files.** decoration.svg is 121 KB, well under the 2 MB FrameSvg cache threshold (Pitfall 12).

### ns0: Prefix Check

`OK: no ns0: prefix` — `ET.register_namespace("", SVG_NS)` called before any element creation in both `decoration_svg.py` and `button_svg.py`.

### Layout Formula (Open Question A2 Baseline)

From `aurorae_rc._layout_values(theme)` (tunable block for visual gate in Plan 09):

```
s = theme.scale
BorderLeft  = border_size_left  * s   → Aliens: 35 * 2 = 70
BorderRight = border_size_right * s   → Aliens: 35 * 2 = 70
BorderBottom = border_size_bottom * s → Aliens:  6 * 2 = 12
BorderTop   = border_size_top  * s    → Aliens: 35 * 2 = 70
TitleEdgeTop = TitleEdgeBottom = 2 * s
TitleEdgeLeft = TitleEdgeRight = 4 * s
TitleHeight = max(15, border_size_top * s - 4 * s) = max(15, 70 - 8) = 62
PaddingLeft = PaddingRight = BorderLeft * 2 = 140
PaddingTop  = BorderTop * 2 = 140
PaddingBottom = BorderBottom * 2 = 24
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test fixture missing directory creation**
- **Found during:** Task 2 GREEN phase
- **Issue:** `_make_theme_with_iclass(tmp_path / "assets")` passed a non-existent directory to `_make_tiny_png`, causing Pillow `OSError: [Errno 2] No such file or directory`
- **Fix:** Added `tmp_path.mkdir(parents=True, exist_ok=True)` at the top of `_make_tiny_png` in `test_decoration_svg.py`
- **Files modified:** `tests/test_decoration_svg.py`
- **Commit:** 306efa4 (bundled with implementation commit)

**2. [Rule 1 - Bug] Fixed pyright basic type error in button_svg._build_button_svg**
- **Found during:** Final verification
- **Issue:** pyright basic reports `bytes | None` cannot be assigned to `bytes` parameter in `embed_png_b64` call. Variables `hover` and `pressed` derived via `or normal` chain remained `bytes | None` until after the `if normal is None` block.
- **Fix:** Refactored to use explicit `if X is not None else normal` conditional assignment to narrow the type for pyright.
- **Files modified:** `src/themey/generate/button_svg.py`
- **Commit:** acff0f1

**3. [Rule 3 - Blocking] aurorae.py created in Task 2 (not Task 3)**
- **Found during:** Task 2 implementation
- **Issue:** `decoration_svg.py` imports `REQUIRED_FRAMESVG_IDS` from `themey.generate.aurorae` for post-write validation. `aurorae.py` hadn't been created yet (it was Task 3). Without it, Task 2's implementation would fail at import time.
- **Fix:** Created `aurorae.py` during Task 2. The circular import (decoration_svg → aurorae → decoration_svg) is resolved by making the import inside `write_decoration_svg` a local/deferred import (not at module level).
- **Files modified:** `src/themey/generate/aurorae.py` (created early)
- **Commit:** 306efa4

**4. [Rule 2 - Lint] Fixed RUF003 ambiguous Unicode multiplication signs**
- **Found during:** Task 2 ruff check
- **Issue:** `×` (Unicode MULTIPLICATION SIGN U+00D7) in comments triggers ruff RUF003
- **Fix:** Replaced with `x` (ascii) in comments in both `decoration_svg.py` and `button_svg.py`
- **Files modified:** `src/themey/generate/decoration_svg.py`, `src/themey/generate/button_svg.py`
- **Commit:** 306efa4

### Plan Acceptance Criterion Note

The plan states: `grep -c 'configparser' src/themey/generate/desktop_writer.py` should return 0. The file returns 2 because the docstring says "DO NOT use configparser" — these are documentary comments, not imports. There is no `import configparser` in `desktop_writer.py`. The acceptance criterion intent (don't USE configparser) is satisfied.

## Key Technical Notes

### _CaseSensitiveRawConfigParser Rationale

`aurorae_rc.py` uses a subclass pattern rather than the bare `cp.optionxform = str` form:

```python
class _CaseSensitiveRawConfigParser(configparser.RawConfigParser):
    optionxform = staticmethod(str)  # type: ignore[assignment]
```

The bare `cp.optionxform = str` form causes pyright basic to report "cannot assign method to instance" because `optionxform` is typed as a method in `configparser.RawConfigParser`. The `staticmethod(str)` form at class level is the canonical configparser docs fix. The `# type: ignore[assignment]` suppresses a remaining pyright subtlety about staticmethod typing. This decision is documented in STATE.md under decisions.

### Circular Import Resolution

`decoration_svg.py` needs `REQUIRED_FRAMESVG_IDS` from `aurorae.py` for post-write validation, but `aurorae.py` imports `decoration_svg`. The cycle is broken by making the import a local import inside `write_decoration_svg`:

```python
def write_decoration_svg(theme: Theme, out_dir: Path) -> Path:
    ...
    # Post-write validation — deferred import to avoid circular at module load
    from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS
```

This is a standard Python circular-import mitigation pattern.

## Known Stubs

None — all data is wired. The generated files contain real PNG content from theme.iclasses paths (or transparent 1x1 fallback if assets are missing, logged via Theme.notes in build_theme).

## Threat Flags

| Flag | File | Description |
|------|------|-------------|
| threat_flag: path-open | src/themey/generate/decoration_svg.py | `_png_bytes()` calls `Image.open(p)` on paths from `theme.iclasses`. Per T-07-01 in plan threat model: `p.is_file()` guard is present; corrupt PNG propagates as exception (Plan 09 catches and shows clear message). |

## Self-Check: PASSED

Files verified to exist:
- `src/themey/generate/__init__.py` — FOUND
- `src/themey/generate/desktop_writer.py` — FOUND
- `src/themey/generate/aurorae_rc.py` — FOUND
- `src/themey/generate/aurorae_meta.py` — FOUND
- `src/themey/generate/decoration_svg.py` — FOUND
- `src/themey/generate/button_svg.py` — FOUND
- `src/themey/generate/aurorae.py` — FOUND
- `tests/test_desktop_writer.py` — FOUND
- `tests/test_aurorae_rc.py` — FOUND
- `tests/test_aurorae_meta.py` — FOUND
- `tests/test_decoration_svg.py` — FOUND
- `tests/test_button_svg.py` — FOUND
- `tests/test_aurorae_pipeline.py` — FOUND
- `tests/snapshots/__snapshots__/.gitkeep` — FOUND

Commits verified:
- test(01-07) RED Task 1: 0ff9572
- feat(01-07) GREEN Task 1: 832bf4c
- test(01-07) RED Task 2: c363ac4
- feat(01-07) GREEN Task 2+3: 306efa4
- feat(01-07) Task 3 pipeline: 3b6b15a
- fix(01-07) pyright fix: acff0f1

Test count: 175 passed (30 new in this plan), 0 failures.
Aliens canary: CANARY OK — LeftButtons=XAI, BorderLeft=70, KPlugin.Id=Aliens
