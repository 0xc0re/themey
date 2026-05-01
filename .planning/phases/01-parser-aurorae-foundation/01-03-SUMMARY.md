---
phase: 01-parser-aurorae-foundation
plan: 03
subsystem: etheme-parser
tags: [parser, lexer, ast, e16, cfg, tdd]
dependency_graph:
  requires: [01-01, 01-02]
  provides: [parse_file, parse_tree, Block, KeyVal, Include, AstNode]
  affects: [01-05]
tech_stack:
  added: []
  patterns:
    - "Hand-rolled lexer: stdlib re module + pos-based scan loop"
    - "Frozen dataclasses for immutable AST nodes"
    - "Recursive-descent parser with generic-block-store (no keyword whitelist)"
    - "TDD: RED commit → GREEN commit per task"
key_files:
  created:
    - src/themey/etheme/lex.py
    - src/themey/etheme/ast.py
    - src/themey/etheme/parse.py
    - tests/test_lex.py
    - tests/test_parse.py
    - tests/fixtures/build_tiny_etheme.py
    - tests/fixtures/tiny.etheme
  modified: []
decisions:
  - "Aliens.etheme uses legacy macro style: block names are __NAME child KeyVals inside block bodies, not head_values before __BGN; tests and analyze layer must check both"
  - "NEWLINE tokens collapse consecutive blank lines to one NEWLINE; parser skips them freely between productions"
  - "Lexer emits INCLUDE + ANGLE_PATH/QUOTED_PATH token pairs for #include; not a comment"
  - "__ACLASS is a plain KeyVal child on Block — no special field on Block dataclass; analyze tier reads it as isinstance(c, KeyVal) and c.keyword == '__ACLASS'"
  - "Path-escape guard in _parse_with_includes: silently drops includes whose resolved path escapes asset_root (T-03-01 mitigation)"
metrics:
  duration: "7 minutes"
  completed: "2026-05-01"
  tasks_completed: 2
  files_created: 7
---

# Phase 01 Plan 03: E16 cfg Lexer + AST + Parser Summary

**One-liner:** Hand-rolled E16 cfg lexer (TokenKind enum + pos-based scan) and recursive-descent parser with generic-block-store, #include resolution, and cycle guard — 20 tests passing on both synthetic and Aliens.etheme canary inputs.

## What Was Built

### lex.py — TokenKind and tokenize()

Final `TokenKind` enum values:
- `IDENT` — uppercase identifiers, may begin with `__` (e.g. `__EDGE_SCALING`, `__BGN`, `__END`)
- `NUMBER` — signed integers (includes negative; `int` value stored)
- `STRING` — double-quoted strings (value stored without surrounding quotes)
- `INCLUDE` — `#include` keyword (recognized before entering the `#` comment path)
- `ANGLE_PATH` — `<path>` following `INCLUDE` (e.g. `definitions`)
- `QUOTED_PATH` — `"path"` following `INCLUDE` (e.g. `borders/default.cfg`)
- `NEWLINE` — significant line-break (consecutive blank lines collapse to one)
- `EOF` — sentinel at end of input

Skipped by lexer:
- `/* ... */` C-style block comments (multi-line; newlines inside counted for line tracking)
- `#` hash line comments (EXCEPT `#include` which is recognized first)

Implementation: single while-loop over `text[pos]`; no regex scanner class; `re.compile` used only for individual pattern matches within the loop.

### ast.py — AST Node Dataclasses

Three frozen dataclasses (all `@dataclass(frozen=True)`):

```python
Include(path: str, is_angle: bool, line: int)
KeyVal(keyword: str, values: tuple[object, ...], line: int)
Block(keyword: str, head_values: tuple[object, ...], children: tuple[AstNode, ...], line: int)
AstNode = Block | KeyVal | Include
```

`values` and `head_values` elements are `int` (for NUMBER tokens) or `str` (for IDENT / STRING tokens). Misspellings (`__FORGROUND_COLOR`) are stored verbatim — the analyze layer handles aliases.

### parse.py — Recursive-Descent Parser

Public API:
- `parse_file(path: Path) -> list[AstNode]` — parse one cfg file
- `parse_tree(asset_root: Path, entry_files: list[str] | None = None) -> list[AstNode]` — parse all entry files with #include inlining
- `ParseError(Exception)` — raised on mismatched `__BGN`/`__END`

Grammar implemented:
```
file     := (toplevel)*
toplevel := include | block | top_kv
include  := '#include' ('<' path '>' | '"' path '"')
block    := keyword head_value* '__BGN' (statement)* '__END'
top_kv   := keyword value* NEWLINE
```

Generic-block-store: any IDENT followed by `__BGN` forms a Block; any IDENT followed by values forms a KeyVal. No keyword whitelist.

Security mitigations applied:
- **T-03-01** (path traversal): `_parse_with_includes` silently drops includes whose resolved path doesn't start with `root.resolve()`
- **T-03-02** (infinite cycle): `seen: set[Path]` guards re-entry; cycle returns empty list

## Aliens.etheme Canary Results

Parsing `Aliens.etheme` `borders.cfg` (which `#includes` `borders/default.cfg`):
- **Border blocks found:** 6 (BORDERLESS, DEFAULT, FIXED_SIZE, ICONBOX, PAGER_TOP, SHAPED)
- **DEFAULT border `__BORDER_PART` children:** 12 (>= 8 required)
- **`__ACLASS` values on DEFAULT parts:** ACTION_ICONIFY, ACTION_KILL, ACTION_MAXIMIZE, ACTION_MOVE, ACTION_SHADE, and spatial parts

Parsing `Aliens.etheme` `imageclasses.cfg`:
- **`__ICLASS` blocks found:** 78
- **Required names verified:** TITLE_BAR_HORIZONTAL ✓, BUTTON_KILL ✓, BUTTON_ICONIFY ✓, BUTTON_MAXIMIZE ✓

### Important Discovery: Aliens uses legacy macro block-naming style

Aliens cfg files put block names as `__NAME <NAME>` KeyVal children inside the block body, not as head_values before `__BGN`. For example:

```
__BORDER __BGN        ← head_values = ()
  __NAME DEFAULT      ← KeyVal child keyword="__NAME", values=("DEFAULT",)
  __BORDER_PART __BGN ← head_values = ()
    __ICLASS BUTTON_ICONIFY  ← KeyVal child
    __ACLASS ACTION_ICONIFY  ← KeyVal child
  __END
__END
```

The analyze layer (Plan 05) must use a `_block_name()` helper that checks both `head_values[0]` and the `__NAME` child KeyVal. The plan tests include a `_block_name()` helper for this purpose.

### Tolerance behaviors

**At parse time (parser is agnostic):**
- `__FORGROUND_COLOR` misspelling preserved verbatim (test confirmed)
- `__FOREGROUND_COLOR` and `__COLOR` aliases NOT handled at parse time — left for analyze tier
- Unknown keywords (`__DESKTOP`, `__BACKGROUND_LAYER`, `__USE_ON_DESKTOP`, `__SOLID_COLOR`) parse without error as generic Block/KeyVal

**At #include resolution time:**
- `#include <definitions>` silently skipped (no node emitted)
- Missing include targets silently dropped (stale includes in legacy themes)
- Path-escape attempts silently dropped (T-03-01)
- Cycle re-entry returns empty list (T-03-02)

## Test Results

| Test File | Tests | Status |
|-----------|-------|--------|
| tests/test_lex.py | 8 | ✓ All passed |
| tests/test_parse.py | 12 | ✓ All passed |
| **Total** | **20** | **✓** |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Aliens uses __NAME KeyVal not head_values for block names**

- **Found during:** Task 2, Aliens canary tests
- **Issue:** Plan tests assumed block names appear in `head_values` (e.g. `__BORDER DEFAULT __BGN`). Aliens.etheme uses legacy macro style where the block name comes from a `__NAME DEFAULT` child KeyVal inside the body.
- **Fix:** Updated `test_parse_tree_aliens_default_cfg` and `test_parse_tree_aliens_imageclasses` to use a `_block_name()` helper that checks both `head_values[0]` and `__NAME` child KeyVal. Parser behavior is correct — this was a test assertion issue, not a parser bug.
- **Files modified:** tests/test_parse.py
- **Commit:** 3bdf316

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes beyond those documented in the plan's threat model. `_parse_with_includes` implements T-03-01 and T-03-02 mitigations as specified.

## Self-Check: PASSED

All 7 created files exist. All 4 task commits verified in git log.
Tests: 20/20 passing. Ruff: clean. Pyright: 0 errors.
