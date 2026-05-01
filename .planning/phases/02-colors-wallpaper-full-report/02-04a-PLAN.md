---
phase: 02-colors-wallpaper-full-report
plan: 04a
type: execute
wave: 3
depends_on: [02-01, 02-02, 02-03]
files_modified:
  - src/themey/analyze/build_theme.py
  - src/themey/paths.py
  - src/themey/report.py
  - tests/test_build_theme.py
  - tests/test_paths.py
  - tests/test_report.py
autonomous: true
requirements: [COLORS-01, WALLPAPER-01]
user_setup: []
must_haves:
  truths:
    - "build_theme.py wires select_wallpaper + build_color_scheme into the analyze pipeline so Theme.color_scheme and Theme.wallpaper are populated for every theme"
    - "paths.py exposes color_schemes() and wallpapers() XDG-aware install path helpers (additive — does not modify existing helpers)"
    - "report.py is REFACTORED IN PLACE (Phase 1 shipped it as a 113-line scaffold; this plan REPLACES the scaffold's API with the new render_report + categorize_notes API and migrates tests/test_report.py to the new API)"
    - "report.py renders a three-section text file (PRESERVED / APPROXIMATED / SKIPPED) from Theme.notes via O(N) prefix-tag categorization"
    - "All notes appended by build_theme.py use one of the three prefix constants imported from themey.ir (PRESERVED_PREFIX, APPROXIMATED_PREFIX, SKIPPED_PREFIX) — single source of truth per 02-01"
  artifacts:
    - path: "src/themey/analyze/build_theme.py"
      provides: "Wires select_wallpaper + build_color_scheme; Theme.color_scheme and Theme.wallpaper populated for every theme; ALL notes.append calls use prefix constants imported from themey.ir"
      contains: "select_wallpaper"
    - path: "src/themey/report.py"
      provides: "MODIFIED IN PLACE — replaces Phase 1's write(theme, out_path) scaffold with render_report(theme, output_paths) -> str + categorize_notes(notes) -> dict[str, list[str]]; imports prefix constants from themey.ir"
      exports: ["render_report", "categorize_notes"]
    - path: "src/themey/paths.py"
      provides: "ADDITIVE — adds color_schemes() and wallpapers() XDG-aware install path helpers; existing aurorae_themes / themey_previews / themey_reports unchanged"
      exports: ["color_schemes", "wallpapers"]
  key_links:
    - from: "src/themey/analyze/build_theme.py"
      to: "src/themey/analyze/background.select_wallpaper"
      via: "build_theme calls select_wallpaper(ast_nodes, asset_root, iclasses)"
      pattern: "select_wallpaper"
    - from: "src/themey/analyze/build_theme.py"
      to: "src/themey/analyze/colors.build_color_scheme"
      via: "build_theme calls build_color_scheme(iclasses, tclasses, wallpaper, notes)"
      pattern: "build_color_scheme"
    - from: "src/themey/report.py"
      to: "src/themey/ir (PRESERVED_PREFIX, APPROXIMATED_PREFIX, SKIPPED_PREFIX)"
      via: "report.py imports constants from themey.ir for shared truth (per checker Issue 3)"
      pattern: "from themey.ir import"
    - from: "src/themey/analyze/build_theme.py"
      to: "src/themey/ir (PRESERVED_PREFIX, APPROXIMATED_PREFIX, SKIPPED_PREFIX)"
      via: "build_theme.py imports constants from themey.ir (NOT redefined locally — per checker Issue 3)"
      pattern: "from themey.ir import"
---

<objective>
Wave 3a wiring: extend `analyze/build_theme.py` so the existing pipeline calls `select_wallpaper` and `build_color_scheme`, populating `Theme.color_scheme` and `Theme.wallpaper`. Migrate the existing free-form notes appended in `build_theme.py` (fallback, missing-asset, spatial-fallback, overlap drop) to the prefix-tag convention from 02-01 — IMPORTING `PRESERVED_PREFIX` / `APPROXIMATED_PREFIX` / `SKIPPED_PREFIX` from `themey.ir` (not redefining locally — per checker Issue 3).

Extend `paths.py` with `color_schemes()` and `wallpapers()` XDG-aware install path helpers (additive — does not touch the existing Phase 1 helpers).

REFACTOR `src/themey/report.py` IN PLACE. Phase 1 shipped this file as a 113-line scaffold with the API `write(theme: Theme, out_path: Path) -> Path`. This plan REPLACES the scaffold with the Phase 2 three-section + prefix-tag categorization design — `render_report(theme, output_paths) -> str` + `categorize_notes(notes) -> dict[str, list[str]]`. The existing tests/test_report.py (which calls `themey.report.write`) is MIGRATED to call `render_report` in the same plan so no test is broken between commits.

This plan is autonomous (no checkpoint). The non-autonomous preview + Aliens E2E + visual gate is split into plan 02-04b (Wave 3b, depends on 02-04a) — addresses checker Issue 6 (scope budget) and Issue 1 (in-place vs create).

Output:
- `src/themey/analyze/build_theme.py` (MODIFIED — wires Phase 2 analyze; all notes use prefix constants from themey.ir)
- `src/themey/paths.py` (MODIFIED — additive: color_schemes, wallpapers helpers)
- `src/themey/report.py` (MODIFIED IN PLACE — refactored from Phase 1's write() scaffold to Phase 2's render_report + categorize_notes API)
- `tests/test_build_theme.py` (MODIFIED — assertions for new Theme fields, prefix-tagged notes)
- `tests/test_paths.py` (MODIFIED — tests for color_schemes, wallpapers)
- `tests/test_report.py` (MODIFIED IN PLACE — migrated from themey.report.write API to render_report API; legacy substring assertion at line 83 still satisfied because the migrated states.py notes preserve the word "dropped" per 02-01 / checker Issue 5)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/02-colors-wallpaper-full-report/02-RESEARCH.md
@.planning/phases/02-colors-wallpaper-full-report/02-PATTERNS.md
@.planning/phases/02-colors-wallpaper-full-report/02-01-PLAN.md
@.planning/phases/02-colors-wallpaper-full-report/02-02-PLAN.md
@.planning/phases/02-colors-wallpaper-full-report/02-03-PLAN.md
@src/themey/ir.py
@src/themey/paths.py
@src/themey/report.py
@src/themey/analyze/build_theme.py
@src/themey/analyze/states.py
@tests/test_build_theme.py
@tests/test_report.py
@tests/test_paths.py

<interfaces>
<!-- All Wave 1+2 outputs available to Wave 3a: -->

```python
# From 02-01 (src/themey/ir.py)
PRESERVED_PREFIX = "PRESERVED: "
APPROXIMATED_PREFIX = "APPROXIMATED: "
SKIPPED_PREFIX = "SKIPPED: "

@dataclass(frozen=True)
class ColorScheme: ...   # 18 fields (15 explicit + 3 semantic defaults)
@dataclass(frozen=True)
class WallpaperSpec: ... # image_path, fit_mode, solid_color, desktop_label, skipped_alternatives
class Theme:             # extended with color_scheme, wallpaper optional fields

# From 02-02 (src/themey/analyze/background.py)
def select_wallpaper(ast_nodes: list[AstNode], asset_root: Path, iclasses: dict[str, IClassSpec]) -> WallpaperSpec | None: ...

# From 02-02 (src/themey/analyze/colors.py)
def build_color_scheme(iclasses, tclasses, wallpaper, notes) -> ColorScheme: ...
```

<!-- Existing build_theme.py contract (src/themey/analyze/build_theme.py:55-275) — Wave 3a EXTENDS this function: -->

```python
def build_theme(
    asset_root: Path,
    ast_nodes: list[AstNode],
    *,
    name: str,
    display_name: str | None = None,
    author: str | None = None,
    scale: int = 2,
) -> Theme: ...
```

The function currently produces a Theme with `palette=...` (Phase 1 default) and NO color_scheme/wallpaper. Wave 3a adds:
- `wallpaper = select_wallpaper(ast_nodes, asset_root, iclasses)` after iclasses is built
- `color_scheme = build_color_scheme(iclasses, tclasses, wallpaper, notes)` after the above
- Pass them into the final `Theme(...)` constructor
- Migrates ALL existing `notes.append(...)` sites (lines 101-108, 131-134, 218-228, 240-243) to use prefix constants imported from `themey.ir`

<!-- Existing paths.py (src/themey/paths.py): -->

```python
def aurorae_themes() -> Path: return _xdg_data_home() / "aurorae" / "themes"
def themey_previews() -> Path: return _xdg_data_home() / "themey" / "previews"
def themey_reports() -> Path: return _xdg_data_home() / "themey" / "previews"
# 02-04a ADDS:
def color_schemes() -> Path: return _xdg_data_home() / "color-schemes"
def wallpapers() -> Path: return _xdg_data_home() / "wallpapers"
```

<!-- EXISTING report.py contract (Phase 1, src/themey/report.py — 113 lines) — this plan REPLACES it: -->

```python
# Phase 1 (current):
def write(theme: Theme, out_path: Path) -> Path:
    """Write report.txt for *theme* to *out_path*."""
    # builds lines list with hardcoded "## Preserved", "## Approximated", "## Skipped"
    # iterates theme.notes[:20] putting them all under Approximated
    # uses theme.skipped_borders directly under Skipped
    # writes via out_path.write_text("\n".join(lines), encoding="utf-8")
    # returns out_path

# 02-04a REPLACES with:
PRESERVED_PREFIX, APPROXIMATED_PREFIX, SKIPPED_PREFIX  # imported from themey.ir
SECTION_HEADERS: dict[str, str] = {...}
def categorize_notes(notes: list[str]) -> dict[str, list[str]]: ...
def render_report(theme: Theme, output_paths: list[Path]) -> str: ...
```

<!-- EXISTING test_report.py (Phase 1) — calls themey.report.write — this plan MIGRATES it: -->

The existing tests/test_report.py (111 lines, 5 tests) imports `from themey.report import write` and asserts:
- (line ~64) "preserved" / "approximated" / "skipped" appear lowercase in the output
- (line ~75) BORDERLESS / FIXED_SIZE substring assertions for skipped_borders
- (line 83) literal substring "TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped" appears in the output (per checker Issue 5: this assertion SURVIVES because the migrated states.py keeps the word "dropped")
- (line ~99) Phase deferral mentions ("Phase 2", "Phase 3", "later phase")
- (line ~110) scale-related text ("fractional", "1.25", or "1.5")

The MIGRATION strategy:
- Replace the import `from themey.report import write` with `from themey.report import render_report, categorize_notes`
- Convert "write to file then read text" idiom to "render_report returns text directly"; assertions remain substring-based
- DROP the test_report_phase1_scaffold_section_for_phase2_3 test (line ~91) — Phase 2 fully replaces the deferral language; the new render_report does NOT mention "Phase 2/3" because the deferred features are now SHIPPED in Phase 2
- DROP the test_report_includes_scale_note test (line ~102) — the scale note belongs to the OLD Approximated scaffold; the new render_report drives section content from theme.notes, not hardcoded scaffold text. (If scale fidelity is important, build_theme.py should append an APPROXIMATED note about scale; that's a Phase 2 design choice — for V1, drop the test rather than retrofit fake notes)
- KEEP and ADAPT test_report_three_sections to call render_report and assert the three new section headers
- KEEP and ADAPT test_report_includes_skipped_borders — but BORDERLESS/FIXED_SIZE now reach the report via SKIPPED-prefixed notes appended in build_theme.py (per the migration in Task 1 below); the test must construct a Theme whose `notes` list contains `f"{SKIPPED_PREFIX}border 'BORDERLESS' (Aurorae renders DEFAULT only)"`
- KEEP and ADAPT test_report_includes_notes_in_approximated — adapt to render_report; the assertion `assert note in text` still works because `categorize_notes` strips the prefix but the NOTE BODY (including "TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped") survives in the rendered text under whichever section it routes to (SKIPPED for the migrated states.py producer)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Wire build_theme.py with prefix-tagged notes + extend paths.py with color-schemes/wallpapers helpers</name>
  <files>src/themey/analyze/build_theme.py, src/themey/paths.py, tests/test_build_theme.py, tests/test_paths.py</files>
  <read_first>
    - src/themey/analyze/build_theme.py (entire 275 lines — analog: existing pipeline orchestration; lines 79-275 show the assemble flow; lines 101-108, 131-134, 218-228, 240-243 are the existing notes.append sites to migrate)
    - src/themey/paths.py (entire file — analog: aurorae_themes / themey_previews helper pattern, _xdg_data_home() lines 12-16)
    - src/themey/ir.py (after 02-01 — confirm the three *_PREFIX constants are defined as module-level strings)
    - src/themey/analyze/states.py (after 02-01 — confirm the SKIPPED_PREFIX import pattern is already established)
    - tests/test_build_theme.py (entire file — analog: existing assertions on Theme fields; the test_aliens_canary integration at lines 254-339)
    - tests/test_paths.py (analog: XDG override + fake_home routing patterns)
    - .planning/phases/02-colors-wallpaper-full-report/02-RESEARCH.md §3 lines 110-114 (color-schemes install path) and §3 lines 312-326 (wallpapers install path)
    - .planning/phases/02-colors-wallpaper-full-report/02-PATTERNS.md "Notes Accumulator Convention" lines 542-553 (prefix-tag migration for build_theme.py)
  </read_first>
  <behavior>
    - Test 1 (paths.color_schemes): with HOME=tmp_path and XDG_DATA_HOME unset → color_schemes() returns tmp_path/.local/share/color-schemes
    - Test 2 (paths.color_schemes XDG override): with XDG_DATA_HOME=/custom → color_schemes() returns /custom/color-schemes
    - Test 3 (paths.wallpapers): same pattern as color_schemes but path ends in /wallpapers
    - Test 4 (build_theme populates color_scheme): construct synthetic AST + asset_root with a TITLE_BAR_HORIZONTAL iclass having an on-disk PNG; build_theme returns a Theme where theme.color_scheme is a ColorScheme instance (NOT None)
    - Test 5 (build_theme populates wallpaper when present): include a synthetic __DESKTOP block with __BACKGROUND_LAYER pointing at an on-disk PNG; build_theme returns Theme where theme.wallpaper is a WallpaperSpec
    - Test 6 (build_theme handles missing wallpaper gracefully): no __DESKTOP / __BACKGROUND blocks → theme.wallpaper is None; theme.color_scheme is still populated (sampling falls back to titlebar only)
    - Test 7 (build_theme migrates ALL notes to prefix tags): every entry in theme.notes starts with one of "PRESERVED: ", "APPROXIMATED: ", or "SKIPPED: ". The test iterates theme.notes; for each, asserts `n.startswith("PRESERVED: ") or n.startswith("APPROXIMATED: ") or n.startswith("SKIPPED: ")`. The assertion message reports any unprefixed note for debugging.
    - Test 8 (build_theme appends SKIPPED notes for skipped border): a synthetic AST with two __BORDER blocks (DEFAULT + BORDERLESS) → theme.notes contains an entry like "SKIPPED: border 'BORDERLESS' (Aurorae renders DEFAULT only)"
    - Test 9 (Theme.skipped_borders still populated): the existing Phase 1 behaviour (skipped_borders tuple) is unchanged — this verifies the prefix-tag migration is additive
    - Test 10 (build_theme.py imports prefix constants from themey.ir, NOT locally redefined per checker Issue 3): grep confirms `from themey.ir import PRESERVED_PREFIX, APPROXIMATED_PREFIX, SKIPPED_PREFIX` (or equivalent) and the file does NOT contain `PRESERVED_PREFIX = ` or `APPROXIMATED_PREFIX = ` at the module level
  </behavior>
  <action>
**A. Extend `src/themey/paths.py`** by appending two new helper functions after `themey_reports()`:

```python
def color_schemes() -> Path:
    """Plasma 6 KColorScheme install dir.

    Verified path on Plasma 6.6.4: ~/.local/share/color-schemes/<name>.colors
    (single .colors file, NO subdirectory — see RESEARCH §3 lines 110-114).
    """
    return _xdg_data_home() / "color-schemes"


def wallpapers() -> Path:
    """Plasma 6 Wallpaper/Images install dir.

    Verified layout on Plasma 6.6.4: ~/.local/share/wallpapers/<name>/{metadata.json,contents/images/}
    (per-theme subdirectory — see RESEARCH §3 lines 312-326).
    """
    return _xdg_data_home() / "wallpapers"
```

**B. Modify `src/themey/analyze/build_theme.py`** in three coordinated edits:

(B1) Add new imports near the top (after the existing `from .borders import` etc.). Per checker Issue 3 — DO NOT redefine prefix constants locally; import them from `themey.ir`:

```python
from themey.ir import (
    APPROXIMATED_PREFIX,
    PRESERVED_PREFIX,
    SKIPPED_PREFIX,
    BorderSpec,
    Palette,
    Theme,
)

from .background import select_wallpaper
from .colors import build_color_scheme
```

(Combine the new prefix imports with the existing `from themey.ir import (BorderSpec, Palette, Theme)` block at lines 24-28.)

(B2) Migrate the existing `notes.append(...)` call sites to use the prefix tags. Specifically (line numbers reference current build_theme.py):

| Current line | Current text | New text |
|--------------|--------------|----------|
| 101-104 | `"fallback: no __BORDER block parsed; used filename-pattern discovery (PARSE-05 hook)"` | `f"{APPROXIMATED_PREFIX}fallback: no __BORDER block parsed; used filename-pattern discovery (PARSE-05 hook)"` |
| 106-109 | `"fallback: no __BORDER block AND no canonical PNGs found; using minimal synthetic border"` | `f"{SKIPPED_PREFIX}no __BORDER block AND no canonical PNGs found; using minimal synthetic border"` |
| 131-135 | `f"{ic_name}: declared {state_key} -> '{path.name}' but file is missing from asset_root (missing asset — image will fall back to placeholder in SVG)"` | `f"{SKIPPED_PREFIX}{ic_name}: declared {state_key} -> '{path.name}' but file is missing from asset_root (missing asset — image will fall back to placeholder in SVG)"` |
| 218-222 | `f"button '{part.iclass_name}' at x={x_center} assigned via spatial fallback -> '{code}' (titlebar=[{titlebar_min_x}, {titlebar_max_x}])"` | `f"{APPROXIMATED_PREFIX}button '{part.iclass_name}' at x={x_center} assigned via spatial fallback -> '{code}' (titlebar=[{titlebar_min_x}, {titlebar_max_x}])"` |
| 224-229 | `f"part '{part.iclass_name}' at x={x_center} dropped via spatial fallback (ambiguous middle third or no geometry — titlebar=[{titlebar_min_x}, {titlebar_max_x}])"` | `f"{SKIPPED_PREFIX}part '{part.iclass_name}' at x={x_center} dropped via spatial fallback (ambiguous middle third or no geometry — titlebar=[{titlebar_min_x}, {titlebar_max_x}])"` |
| 240-244 | `f"button '{code}' at x={x} overlaps titlebar text region [{titlebar_min_x}, {titlebar_max_x}] — dropped (no Aurorae equivalent for buttons inside titlebar text area)"` | `f"{SKIPPED_PREFIX}button '{code}' at x={x} overlaps titlebar text region [{titlebar_min_x}, {titlebar_max_x}] — dropped (no Aurorae equivalent for buttons inside titlebar text area)"` |

Also append SKIPPED entries for each skipped non-DEFAULT border. After the `for b in all_borders: ... skipped.append(...)` loop (around line 88-95), add (per RESEARCH §5 line 537):

```python
        # Phase 2: surface skipped borders in report.txt SKIPPED section
        for skipped_name in skipped:
            notes.append(
                f"{SKIPPED_PREFIX}border '{skipped_name}' "
                f"(Aurorae renders DEFAULT only)"
            )
```

(B3) After `tclasses = build_tclasses(tclass_blocks)` (around line 141), add the Phase 2 wiring:

```python
    # ------------------------------------------------------------------
    # 4b. Phase 2: select wallpaper from __DESKTOP / __BACKGROUND blocks
    # ------------------------------------------------------------------
    wallpaper = select_wallpaper(ast_nodes, asset_root, iclasses)
    if wallpaper is not None:
        notes.append(
            f"{PRESERVED_PREFIX}wallpaper image: "
            f"{wallpaper.image_path.name if wallpaper.image_path else '(solid)'} "
            f"(desktop label: {wallpaper.desktop_label or 'unnamed'})"
        )
        for skipped_label in wallpaper.skipped_alternatives:
            notes.append(
                f"{SKIPPED_PREFIX}desktop background '{skipped_label}' "
                f"(Plasma wallpaper packages support one image per package)"
            )
    else:
        notes.append(
            f"{SKIPPED_PREFIX}no __DESKTOP/__BACKGROUND block found; "
            f"wallpaper output uses solid-colour fallback (or omitted)"
        )

    # ------------------------------------------------------------------
    # 4c. Phase 2: build full KColorScheme from titlebar+wallpaper sampling
    # ------------------------------------------------------------------
    color_scheme = build_color_scheme(iclasses, tclasses, wallpaper, notes)
```

Then update the final `return Theme(...)` (current lines 260-275) to add the two new fields:

```python
    return Theme(
        # ... all existing fields ...
        color_scheme=color_scheme,
        wallpaper=wallpaper,
    )
```

**C. Extend `tests/test_paths.py`** to add Test 1, Test 2, Test 3 from the behavior section, mirroring the existing `test_aurorae_themes_default` / `test_aurorae_themes_xdg_override` pattern.

**D. Modify `tests/test_build_theme.py`** to add Tests 4-10 from the behavior section. Construct synthetic AST nodes per the existing `_kv` / `_block` / `_border_block` / `_part_block` helpers (already defined at lines 36-82).

For Test 4 (color_scheme populated), a minimal synthetic test setup:
- Create tmp_path with an `artwork/title.png` file (8×8 RGBA red, via Pillow)
- Build an AST list with one `__ICLASS` block named `TITLE_BAR_HORIZONTAL` with `__NORMAL "artwork/title.png"`, plus one `__BORDER` block named `DEFAULT`
- Call `build_theme(asset_root=tmp_path, ast_nodes=...)`
- Assert `theme.color_scheme is not None and isinstance(theme.color_scheme, ColorScheme)`

For Test 8 (skipped border SKIPPED note), construct an AST with `_border_block("DEFAULT")` AND `_border_block("BORDERLESS")`. Assert `any("SKIPPED: border 'BORDERLESS'" in n for n in theme.notes)`.

For Test 7 (every note prefix-tagged), iterate theme.notes; for each note, assert `n.startswith("PRESERVED: ") or n.startswith("APPROXIMATED: ") or n.startswith("SKIPPED: ")`. Report the unprefixed note in the assertion message.

For Test 10 (single source of truth check): use grep-style assertions OR a static check. Recommended: add an inline test that does:
```python
def test_build_theme_imports_prefix_constants_from_ir() -> None:
    """Per checker Issue 3: build_theme.py imports the three *_PREFIX constants from themey.ir
    rather than redefining them locally — single source of truth in ir.py."""
    src_text = Path("src/themey/analyze/build_theme.py").read_text(encoding="utf-8")
    # Imported (positive)
    assert "from themey.ir import" in src_text and (
        "PRESERVED_PREFIX" in src_text and "APPROXIMATED_PREFIX" in src_text
        and "SKIPPED_PREFIX" in src_text
    )
    # NOT redefined (negative): no top-level assignment to the prefix constants
    import re
    assert not re.search(r"^PRESERVED_PREFIX[ \t]*=", src_text, re.MULTILINE)
    assert not re.search(r"^APPROXIMATED_PREFIX[ \t]*=", src_text, re.MULTILINE)
    assert not re.search(r"^SKIPPED_PREFIX[ \t]*=", src_text, re.MULTILINE)
```

DO NOT modify the existing `test_aliens_canary` test (lines 254-339) — let it run unchanged; the migration should not break it (the substring `in` checks survive the prefix addition; `len(theme.notes) >= 4` still holds because we're ADDING notes, not removing).

**E. The existing `test_build_theme_logs_spatial_fallback_assigned` test (lines 160-195) and `test_build_theme_logs_spatial_fallback_dropped_middle` test (lines 198-224)** use substring checks like `"spatial fallback" in n.lower()` — these PASS unchanged after migration because the prefix is prepended, not the body replaced. Verify by reading the existing assertions before declaring the task done.
  </action>
  <verify>
    <automated>cd /home/cstory/src/themey &amp;&amp; uv run pytest tests/test_build_theme.py tests/test_paths.py -x -v &amp;&amp; uv run pytest tests/ -x &amp;&amp; uv run ruff check src/themey/analyze/build_theme.py src/themey/paths.py tests/test_build_theme.py tests/test_paths.py &amp;&amp; uv run pyright src/themey/analyze/build_theme.py src/themey/paths.py tests/test_build_theme.py tests/test_paths.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def color_schemes" src/themey/paths.py` returns 1
    - `grep -c "^def wallpapers" src/themey/paths.py` returns 1
    - `grep -c "from .background import select_wallpaper" src/themey/analyze/build_theme.py` returns 1
    - `grep -c "from .colors import build_color_scheme" src/themey/analyze/build_theme.py` returns 1
    - `grep -c "PRESERVED_PREFIX" src/themey/analyze/build_theme.py` returns at least 2 (import + usage)
    - `grep -c "APPROXIMATED_PREFIX" src/themey/analyze/build_theme.py` returns at least 3 (import + at least 2 usages — fallback note, spatial assignment note)
    - `grep -c "SKIPPED_PREFIX" src/themey/analyze/build_theme.py` returns at least 6 (import + at least 5 usages — empty fallback, missing asset, spatial drop, overlap drop, skipped border, no-wallpaper)
    - `grep -cE '^(PRESERVED|APPROXIMATED|SKIPPED)_PREFIX[[:space:]]*=' src/themey/analyze/build_theme.py` returns 0 (per checker Issue 3 — NOT locally redefined)
    - `grep -c "select_wallpaper(ast_nodes, asset_root, iclasses)" src/themey/analyze/build_theme.py` returns 1
    - `grep -c "build_color_scheme(iclasses, tclasses, wallpaper, notes)" src/themey/analyze/build_theme.py` returns 1
    - `grep -c "color_scheme=color_scheme" src/themey/analyze/build_theme.py` returns 1
    - `grep -c "wallpaper=wallpaper" src/themey/analyze/build_theme.py` returns 1
    - **Per checker Issue 2 (runnable grep filter for note-prefix audit)**: `bash -c "grep -E '^[[:space:]]+notes\.append\(' src/themey/analyze/build_theme.py | grep -vE '(_PREFIX|\"PRESERVED:|\"APPROXIMATED:|\"SKIPPED:)' | wc -l"` returns 0 (every notes.append uses one of the three prefix constants — verified by excluding lines that mention `_PREFIX`, `"PRESERVED:`, `"APPROXIMATED:`, or `"SKIPPED:`). The exact command — copy-paste runnable verbatim, including the surrounding `bash -c "..."` — is the acceptance gate.
    - **Per checker Warning W3 (import-resolution acceptance check)**: `bash -c "cd /home/cstory/src/themey && uv run python -c 'from themey.analyze.background import select_wallpaper; from themey.analyze.colors import build_color_scheme; print(\"imports OK\")'"` exits 0 with the line "imports OK"
    - `uv run pytest tests/test_paths.py` reports >= 6 tests (was 3, +3 new for color_schemes / wallpapers)
    - `uv run pytest tests/test_build_theme.py` reports new tests passing (Tests 4-10)
    - `uv run pytest tests/ -x` passes ALL tests (no regression)
    - `uv run ruff check src/themey/analyze/build_theme.py src/themey/paths.py tests/test_build_theme.py tests/test_paths.py` exits 0
    - `uv run pyright src/themey/analyze/build_theme.py src/themey/paths.py tests/test_build_theme.py tests/test_paths.py` reports 0 errors
  </acceptance_criteria>
  <done>
    `build_theme.py` calls `select_wallpaper` and `build_color_scheme`, populating `Theme.color_scheme` and `Theme.wallpaper` for every theme. ALL `notes.append` sites use one of the three prefix constants imported from `themey.ir` (no local redefinitions — per checker Issue 3). `paths.py` exposes `color_schemes()` and `wallpapers()` XDG-aware helpers. The single-source-of-truth grep gate (per checker Issue 2) returns 0 — every notes.append uses a prefix. All existing tests pass; new tests validate wiring, migration, and the no-redefinition rule.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Refactor src/themey/report.py IN PLACE — replace Phase 1 write() scaffold with render_report + categorize_notes API; migrate tests/test_report.py</name>
  <files>src/themey/report.py, tests/test_report.py</files>
  <read_first>
    - src/themey/report.py (entire 113-line existing file — Phase 1 shipped this scaffold; this task REPLACES the API. The existing code uses out_path.write_text and returns out_path; the new API returns a string and lets the caller decide where to write)
    - tests/test_report.py (entire 111-line existing file — Phase 1 shipped 5 tests calling `themey.report.write`; this task MIGRATES them. Specifically line 83 asserts the literal substring "TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped" which SURVIVES the migration because per checker Issue 5, the migrated states.py keeps the word "dropped")
    - src/themey/ir.py (after 02-01 — confirm the three *_PREFIX constants are defined; confirm Theme contract)
    - src/themey/analyze/states.py (after 02-01 — confirm the migrated note format includes the word "dropped" so test_report.py:83 still passes)
    - src/themey/analyze/build_theme.py (after Task 1 — confirm prefix tags are emitted; the report consumes those notes)
    - .planning/phases/02-colors-wallpaper-full-report/02-RESEARCH.md §5 lines 482-602 (full three-section format spec + category definitions + note format)
    - .planning/phases/02-colors-wallpaper-full-report/02-PATTERNS.md "src/themey/report.py" lines 334-388
  </read_first>
  <behavior>
    - Test 1 (categorize_notes routes by prefix): input list ["PRESERVED: a", "APPROXIMATED: b", "SKIPPED: c"] → returned dict {"preserved": ["a"], "approximated": ["b"], "skipped": ["c"]} (each note text is stripped of its prefix in the output)
    - Test 2 (categorize_notes default for un-prefixed): input ["legacy free-form note"] → routes to "approximated" key (per RESEARCH §5 line 590-592 — overstates lossiness rather than understating)
    - Test 3 (categorize_notes preserves order within each category): ["PRESERVED: a", "PRESERVED: b", "PRESERVED: c"] → preserved == ["a", "b", "c"]
    - Test 4 (render_report contains all three section headers): rendered text contains literal substrings "PRESERVED (mapped 1:1 from E16 source)", "APPROXIMATED (lossy mapping; reason explained)", "SKIPPED (no Plasma equivalent or out of scope for v1)"
    - Test 5 (render_report header has theme metadata): rendered text contains theme.name, theme.author, the strings "Theme:", "Source:" (or "Author:"), "Generated:", "Scale:"
    - Test 6 (render_report lists output paths): given output_paths=[Path("/x/Aliens.colors"), Path("/y/wallpapers/Aliens"), Path("/z/aurorae/themes/Aliens")] → rendered text contains all three path strings
    - Test 7 (render_report bullets each note in its section): for a Theme with 2 PRESERVED, 1 APPROXIMATED, 3 SKIPPED notes → exactly 6 lines start with "- " (or "* ", consistent bullet) under their respective section headers
    - Test 8 (render_report empty section is rendered with "(none)"): for a Theme with no SKIPPED notes → the SKIPPED header is followed by "(none)" (chosen design — explicit absence is clearer than omitting the section). Documented in the function docstring.
    - Test 9 (snapshot — recommended): full text of render_report for a fixed Theme matches a syrupy `.ambr` snapshot
    - **Migration test 10 (legacy assertion survival per checker Issue 5)**: a Theme constructed with `notes=["SKIPPED: TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped (no Aurorae target ...)"]` → render_report's output contains the literal substring "TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped" (the prefix was stripped by categorize_notes but the note body — including the word "dropped" — survived). This is the same substring the legacy `test_report_includes_notes_in_approximated` asserted; the migrated test now asserts it under the SKIPPED section.
    - Migration test 11 (skipped_borders no longer surfaced via Theme.skipped_borders directly — surfaces via SKIPPED-prefixed notes appended in build_theme.py): a Theme constructed with `notes=[f"{SKIPPED_PREFIX}border 'BORDERLESS' (Aurorae renders DEFAULT only)"]` → render_report's output contains the literal substring "border 'BORDERLESS'". The legacy `test_report_includes_skipped_borders` test is migrated to construct the SKIPPED-prefixed note explicitly rather than relying on the scaffold's hardcoded behaviour.
    - Migration test 12 (legacy lowercase assertion still survives): the rendered text contains "PRESERVED" / "APPROXIMATED" / "SKIPPED" (uppercase, in section headers); the legacy `text.lower()` substring assertions for "preserved" / "approximated" / "skipped" still match.
  </behavior>
  <action>
**A. REPLACE the entire content of `src/themey/report.py`** with the new Phase 2 design (per RESEARCH §5 + PATTERNS.md lines 334-388). The current 113-line scaffold is REPLACED; do not preserve `def write(...)` — that API is fully superseded.

Per checker Issue 1: this is "MODIFY" not "CREATE" — the file already exists, this plan refactors it in place; the dependent test file (tests/test_report.py) is migrated to the new API in the SAME plan so no commit boundary leaves the suite broken.

New content:

```python
"""report.txt three-section renderer: PRESERVED / APPROXIMATED / SKIPPED.

Notes are prefix-tagged at write-time (per RESEARCH §5 / Decision 5) so
categorization is deterministic O(N). Free-form notes (Phase 1 legacy that
hasn't been migrated yet) default to APPROXIMATED — overstates lossiness
rather than understating.

Section taxonomy (RESEARCH §5 lines 552-558):
  PRESERVED: E16 source data appears unchanged in meaning (titlebar PNG,
             text colours, button glyphs, border thicknesses, wallpaper image)
  APPROXIMATED: E16 source informs the output but is transformed lossily
                (8→2 state collapse, sampled palette, fit mode lost)
  SKIPPED: E16 source has no Plasma equivalent or is out of scope
           (multi-desktop wallpapers, sticky button states, menus,
           non-DEFAULT borders, cursors-when-xcursorgen-missing)

API change history:
  - Phase 1 (01-08): shipped scaffold `write(theme, out_path) -> Path`
  - Phase 2 (02-04a): REPLACED with `render_report(theme, output_paths) -> str`
    + `categorize_notes(notes) -> dict[str, list[str]]`. Caller writes the
    returned string to disk via Path.write_text — separates rendering from I/O.

Empty-section rendering policy: empty sections are rendered with "(none)"
under the section header rather than omitted. Explicit absence reads more
clearly in `cat report.txt` than a missing section, especially for the
SKIPPED section which often is empty for well-behaved themes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from themey.ir import (
    APPROXIMATED_PREFIX,
    PRESERVED_PREFIX,
    SKIPPED_PREFIX,
    Theme,
)

# Section headers — fixed-width underline matches RESEARCH §5 reference output
SECTION_HEADERS: dict[str, str] = {
    "preserved": "PRESERVED (mapped 1:1 from E16 source)\n" + "=" * 38,
    "approximated": "APPROXIMATED (lossy mapping; reason explained)\n" + "=" * 46,
    "skipped": "SKIPPED (no Plasma equivalent or out of scope for v1)\n" + "=" * 53,
}


def categorize_notes(notes: list[str]) -> dict[str, list[str]]:
    """Route prefix-tagged notes into the three sections O(N).

    Args:
        notes: each entry should start with PRESERVED:, APPROXIMATED:, or
               SKIPPED:. Entries without a recognised prefix default to
               approximated (RESEARCH §5 line 590-592 — fail-safe to overstate
               lossiness).

    Returns:
        {"preserved": [...], "approximated": [...], "skipped": [...]} where
        each list contains note bodies with their prefix stripped (the body
        starts with the first character after the ": " separator).
    """
    out: dict[str, list[str]] = {
        "preserved": [],
        "approximated": [],
        "skipped": [],
    }
    for note in notes:
        if note.startswith(PRESERVED_PREFIX):
            out["preserved"].append(note[len(PRESERVED_PREFIX):])
        elif note.startswith(APPROXIMATED_PREFIX):
            out["approximated"].append(note[len(APPROXIMATED_PREFIX):])
        elif note.startswith(SKIPPED_PREFIX):
            out["skipped"].append(note[len(SKIPPED_PREFIX):])
        else:
            # Legacy free-form note: route to APPROXIMATED per Pitfall J fail-safe
            out["approximated"].append(note)
    return out


def _format_header(theme: Theme, output_paths: list[Path]) -> str:
    """Build the report.txt header (theme metadata + outputs + activation hints)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    output_lines = "\n".join(f"  {p}" for p in output_paths)
    return (
        "themey conversion report\n"
        "========================\n"
        f"Theme:        {theme.name}\n"
        f"Source:       {theme.asset_root}\n"
        f"Author:       {theme.author or '(unknown)'}\n"
        f"Generated:    {now}\n"
        f"Scale:        {theme.scale}x\n\n"
        f"Outputs:\n{output_lines}\n\n"
        "To activate the window decoration:\n"
        f"  System Settings -> Window Decorations -> {theme.name}\n"
        "To activate the color scheme:\n"
        f"  System Settings -> Colors -> {theme.name}\n"
        "To activate the wallpaper:\n"
        f"  Right-click desktop -> Configure Desktop -> Wallpaper -> {theme.name}\n"
    )


def _format_section(header: str, items: list[str]) -> str:
    """One section block: header underline + bulleted item list, or '(none)' if empty."""
    if not items:
        return f"{header}\n(none)\n"
    body = "\n".join(f"- {it}" for it in items)
    return f"{header}\n{body}\n"


def render_report(theme: Theme, output_paths: list[Path]) -> str:
    """Render the full three-section report.txt as a string.

    Args:
        theme: the converted Theme; theme.notes drives section content.
        output_paths: absolute paths of the artefacts written by Phase 2
                      (and Phase 1 + future Phase 3/4) — listed in the header
                      so the user can see what got installed where.

    Returns:
        Multi-line plain-text report. Caller writes it to
        ~/.local/share/themey/previews/<name>.txt.
    """
    sections = categorize_notes(theme.notes)
    return "\n".join([
        _format_header(theme, output_paths),
        _format_section(SECTION_HEADERS["preserved"], sections["preserved"]),
        _format_section(SECTION_HEADERS["approximated"], sections["approximated"]),
        _format_section(SECTION_HEADERS["skipped"], sections["skipped"]),
    ])
```

**B. MIGRATE `tests/test_report.py`** to the new API. Read the existing 111-line file end-to-end first; identify the 5 existing tests; apply the migration plan from `<interfaces>` above:
1. Update import from `from themey.report import write` to `from themey.report import render_report, categorize_notes`. Also import `from themey.ir import SKIPPED_PREFIX` so legacy assertions can construct prefix-tagged notes explicitly.
2. Adapt `test_report_three_sections` to call `text = render_report(theme, [])` and assert the three new section headers (case-sensitive: "PRESERVED", "APPROXIMATED", "SKIPPED"). The legacy lowercase assertion `text.lower()` still matches because the new headers contain "PRESERVED" / "APPROXIMATED" / "SKIPPED" which lowercase to "preserved" / "approximated" / "skipped".
3. Adapt `test_report_includes_skipped_borders`: construct a Theme whose `notes` contains `[f"{SKIPPED_PREFIX}border 'BORDERLESS' (Aurorae renders DEFAULT only)", f"{SKIPPED_PREFIX}border 'FIXED_SIZE' (...)"]`; assert "BORDERLESS" and "FIXED_SIZE" appear in `render_report(theme, [])`.
4. Adapt `test_report_includes_notes_in_approximated` (despite the name — the test now lands the note in SKIPPED section because the migrated states.py uses SKIPPED_PREFIX): pass `notes=["SKIPPED: TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped (no Aurorae target ...)"]`; assert the substring `"TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped"` appears in `render_report(theme, [])`. The substring SURVIVES because (a) the prefix is stripped by categorize_notes, (b) the body including the word "dropped" remains. Per checker Issue 5 fix in 02-01, the word "dropped" is preserved in the migrated states.py — this test is the regression guard for that decision.
5. DROP `test_report_phase1_scaffold_section_for_phase2_3` — Phase 2 ships color/wallpaper, so the deferral language is no longer accurate.
6. DROP `test_report_includes_scale_note` — the scale note belonged to the Phase 1 hardcoded scaffold; the new render_report drives section content from `theme.notes`, not hardcoded text. If scale fidelity matters, build_theme.py should append an APPROXIMATED note about scale (deferred: not in this plan's scope).
7. ADD new tests 1-9 from the behavior section above (categorize_notes routing, render_report headers, etc.) with synthetic Theme factories. Reuse the existing `_make_theme` helper at lines 9-54 — extend its signature to accept `notes` and `skipped_borders` (already does) and rely on it for all new tests.
8. ADD migration tests 10, 11, 12 from the behavior section to make explicit that the legacy substring assertions survive.

For Test 9 (snapshot), use syrupy's `snapshot` fixture and assert the full rendered text equals it. Document in module docstring of the test file: "Updates require `pytest --snapshot-update` after RESEARCH §5 spec changes."
  </action>
  <verify>
    <automated>cd /home/cstory/src/themey &amp;&amp; uv run pytest tests/test_report.py -x -v &amp;&amp; uv run pytest tests/ -x &amp;&amp; uv run ruff check src/themey/report.py tests/test_report.py &amp;&amp; uv run pyright src/themey/report.py tests/test_report.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def render_report" src/themey/report.py` returns 1
    - `grep -c "^def categorize_notes" src/themey/report.py` returns 1
    - `grep -c "^def write" src/themey/report.py` returns 0 (per checker Issue 1: the Phase 1 `write` API is REPLACED — no parallel API)
    - `grep -c "from themey.ir import" src/themey/report.py` returns 1 (prefix constants imported from ir, NOT redefined — per checker Issue 3)
    - `grep -cE '^(PRESERVED|APPROXIMATED|SKIPPED)_PREFIX[[:space:]]*=' src/themey/report.py` returns 0 (NOT locally redefined)
    - `grep -c "PRESERVED (mapped 1:1 from E16 source)" src/themey/report.py` returns 1
    - `grep -c "APPROXIMATED (lossy mapping; reason explained)" src/themey/report.py` returns 1
    - `grep -c "SKIPPED (no Plasma equivalent or out of scope for v1)" src/themey/report.py` returns 1
    - `grep -c "from themey.report import write" tests/test_report.py` returns 0 (legacy import removed)
    - `grep -c "render_report\|categorize_notes" tests/test_report.py` returns at least 5 (new API used in tests)
    - `uv run pytest tests/test_report.py` reports >= 9 tests passed (categorize_notes routing + render_report headers + migration survival tests)
    - `uv run pytest tests/test_report.py -k "TITLE_BAR_HORIZONTAL" or "dropped"` includes at least one passing test (per checker Issue 5: the legacy substring survives the migration)
    - After running pytest, `find tests/__snapshots__ -name "test_report.ambr" -size +200c` returns the snapshot file with substantive content
    - `uv run pytest tests/ -x` passes ALL tests (no regression — particularly tests/test_states.py and tests/test_build_theme.py which were updated by 02-01 and Task 1 of this plan)
    - `uv run ruff check src/themey/report.py tests/test_report.py` exits 0
    - `uv run pyright src/themey/report.py tests/test_report.py` reports 0 errors
  </acceptance_criteria>
  <done>
    `report.py` has been REFACTORED IN PLACE — Phase 1's `write(theme, out_path)` scaffold is REPLACED by the Phase 2 `render_report(theme, output_paths) -> str` + `categorize_notes(notes) -> dict[str, list[str]]` API. Prefix constants are imported from `themey.ir` (single source of truth per checker Issue 3). `tests/test_report.py` is migrated to the new API; the legacy substring assertion at line 83 (`"TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped"`) still passes because per checker Issue 5 the migrated states.py preserved the word "dropped". Snapshot test locks the output format. All notes from Wave 1+2 (states.py SKIPPED, build_theme.py PRESERVED/APPROXIMATED/SKIPPED, colors.py PRESERVED/APPROXIMATED/SKIPPED) land in the correct section.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Theme.notes free-form text | If Wave 1+2 missed a note migration, render_report quietly routes it to APPROXIMATED — silent miscategorization but not a security threat. categorize_notes default-routes un-prefixed notes to APPROXIMATED per RESEARCH §5 fail-safe |
| build_theme integration | Wave 3a wires upstream analyze functions into the existing Phase 1 pipeline; mis-passing asset_root would cause Pillow opens to fail with FileNotFoundError (loud failure, not silent corruption) |
| ~/.local/share/... write surface | This plan does NOT write to disk — render_report returns a string; the caller decides where to write. paths.color_schemes() and paths.wallpapers() return Path objects but do not create them. The test suite uses `fake_home` so XDG-routed paths land in tmp_path |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04a-01 | Tampering | build_theme integration mis-passes asset_root to select_wallpaper / build_color_scheme | mitigate | Test 4-6 in Task 1 verify the wiring with synthetic AST + on-disk PNGs; the Aliens canary test (existing tests/test_build_theme.py:254-339) verifies on real-world data |
| T-02-04a-02 | Tampering | A new producer added to build_theme.py forgets the prefix and routes silently to APPROXIMATED | mitigate | Task 1 acceptance criterion (the runnable grep gate per checker Issue 2) catches any unprefixed notes.append at the build_theme.py level: `bash -c "grep -E '^[[:space:]]+notes\.append\(' src/themey/analyze/build_theme.py | grep -vE '(_PREFIX|\"PRESERVED:|\"APPROXIMATED:|\"SKIPPED:)' | wc -l"` returns 0 |
| T-02-04a-03 | Tampering | report.py local redefinition of prefix constants drifts from themey.ir (Pitfall J) | mitigate | Acceptance criterion `grep -cE '^(PRESERVED\|APPROXIMATED\|SKIPPED)_PREFIX[[:space:]]*=' src/themey/report.py` returns 0 enforces the no-redefinition rule per checker Issue 3 |
| T-02-04a-04 | Repudiation | Migration breaks the legacy "TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped" assertion at tests/test_report.py:83 | mitigate | Per checker Issue 5: the migrated states.py keeps the word "dropped"; this plan's migration test 10 explicitly asserts the substring survives in render_report output |
| T-02-04a-05 | Information disclosure | render_report includes theme.asset_root which is a tempdir path | accept | These paths point to ephemeral tempdirs; report.txt is written to user-owned XDG dir; no exfiltration vector |
</threat_model>

<verification>
- `uv run pytest tests/ -x` passes — all of: existing Phase 1 tests + new IR tests (02-01) + states migration test (02-01) + analyze/background and analyze/colors tests (02-02) + generate/colors and generate/wallpaper tests (02-03) + build_theme integration tests + report tests (this plan)
- `uv run ruff check src/ tests/` passes across the full Phase 2 surface
- `uv run pyright src/ tests/` reports 0 errors
- No notes in `Theme.notes` are unprefixed after build_theme finishes (every note routes deterministically into one of the three sections); enforced by Task 1's runnable grep gate per checker Issue 2
- Prefix constants are defined exactly ONCE in `themey.ir` (per 02-01); `build_theme.py` and `report.py` IMPORT them, NOT redefine them — enforced by `grep -cE '^(PRESERVED\|APPROXIMATED\|SKIPPED)_PREFIX[[:space:]]*=' <file>` returning 0 in both files
- The legacy assertion at `tests/test_report.py:83` ("TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped") survives the migration because the migrated states.py preserves the word "dropped" per checker Issue 5
- `paths.color_schemes()` and `paths.wallpapers()` return XDG-correct paths under fake_home routing
</verification>

<success_criteria>
- `build_theme.py` populates `Theme.color_scheme` and `Theme.wallpaper` for every theme (no longer None)
- ALL `notes.append` sites in `build_theme.py` use one of the three prefix constants imported from `themey.ir` (no local redefinitions; runnable grep gate enforces)
- `paths.py` exposes `color_schemes()` and `wallpapers()` (additive — does not modify existing helpers)
- `report.py` is refactored in place — Phase 1's `write(theme, out_path)` is REPLACED by `render_report(theme, output_paths) -> str` + `categorize_notes(notes)` (per checker Issue 1)
- `tests/test_report.py` is migrated to the new API in the SAME plan; the legacy substring assertion at line 83 still passes (per checker Issue 5 — "dropped" preserved)
- All Wave 1+2 tests still pass (no regression to ir/states/background/colors/generate.colors/generate.wallpaper/embed/build_theme/paths)
- Plan 02-04b can build on this plan's outputs (preview.py refactor + Aliens E2E test + visual gate)
</success_criteria>

<output>
After completion, create `.planning/phases/02-colors-wallpaper-full-report/02-04a-SUMMARY.md` documenting:
- Confirmation that build_theme.py imports prefix constants from themey.ir (no local redefinitions)
- Confirmation that the runnable grep gate (checker Issue 2) returns 0
- The exact list of notes appended by build_theme.py for Aliens.etheme (proves migration is complete)
- Confirmation that report.py was refactored in place (write() removed, render_report + categorize_notes added)
- Confirmation that tests/test_report.py was migrated and the legacy line-83 assertion still passes (per checker Issue 5)
- The exact paths returned by paths.color_schemes() and paths.wallpapers() under fake_home routing (sanity check for 02-04b's Aliens E2E test)
- Carry-forward: 02-04b implements preview.py refactor + Aliens E2E + visual gate
</output>
