# Phase 2: Colors + Wallpaper + Full Report — Pattern Map

**Mapped:** 2026-05-01
**Files analyzed:** 11 (3 NEW analyze, 2 NEW generate, 1 NEW conditional, 2 MODIFY ir/preview, 1 NEW report, 4 NEW test files, 1 UPDATE integration test)
**Analogs found:** 9 strong / 11 total — 2 files (`generate/colors.py`, `generate/wallpaper.py`) are clean-slate because no `generate/` package exists yet; 1 file (`preview.py`) is fully clean-slate because Phase 1's preview module hasn't landed
**Caveat about Phase 1 in flight:** Phase 1 plans 01-05, 01-08, 01-09 (which would create `analyze/build_theme.py`, `report.py`, `preview.py`, `install.py`, `cli.py`) are NOT yet committed. Pattern guidance below references the closest landed analog and flags clean-slate files explicitly.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/themey/ir.py` (MODIFY: add `ColorScheme`, `WallpaperSpec`) | model (frozen-dataclass IR) | transform | `src/themey/ir.py` (existing `Palette`, `BorderSpec`) | exact (extending the same file) |
| `src/themey/analyze/background.py` (NEW) | service (AST→IR transform) | transform | `src/themey/analyze/borders.py` | exact (same role + same data flow: walk AST blocks, return frozen IR) |
| `src/themey/analyze/colors.py` (NEW) | service (Pillow→IR transform) | file-I/O + transform | `src/themey/images/upscale.py` (Pillow primitive) + `src/themey/analyze/tclasses.py` (TClassSpec mapping) | partial — Pillow MEDIANCUT is novel; structure mirrors upscale.py for the PIL boundary, tclasses.py for the IR-emit shape |
| `src/themey/generate/colors.py` (NEW) | utility (text-output writer) | file-I/O sink | none (no `generate/` package yet) | clean-slate; closest precedent is `tests/fixtures/build_tiny_etheme.py` for "stdlib-only multi-block writer" idiom |
| `src/themey/generate/wallpaper.py` (NEW) | utility (json+image-copy writer) | file-I/O sink | `src/themey/etheme/archive.py` (only existing module that writes binary files atomically) | role-match (different I/O shape but same atomic-write discipline) |
| `src/themey/generate/__init__.py` (NEW) | package stub | n/a | `src/themey/analyze/__init__.py` | exact one-liner pattern |
| `src/themey/report.py` (NEW for Phase 2; would deprecate the Phase 1 scaffold if it lands first) | service (Theme.notes → text) | transform + sink | `src/themey/analyze/states.py` (note-format producer) | role-match (states.py defines the note string format; report.py categorizes them) |
| `src/themey/preview.py` (NEW or ENRICH) | utility (HTML+base64 writer) | file-I/O sink | `src/themey/images/embed.py` (`image_to_b64_uri` is exactly the swatch/thumb embed pattern) | exact for the embed primitive; HTML scaffold itself is clean-slate |
| `tests/test_colors.py` (NEW snapshot tests) | test | snapshot-assert | `tests/test_analyze_iclasses.py` + `tests/test_states.py` (current pure-function unit-test idiom; NO syrupy snapshot file exists in repo yet) | role-match for unit tests; clean-slate for `.ambr` snapshot conventions |
| `tests/test_wallpaper.py` (NEW) | test | snapshot + structural assert | same as above + `tests/test_archive.py` for "file-on-disk structural assertions" | role-match |
| `tests/test_report.py` (NEW snapshot tests) | test | snapshot-assert | same as `test_colors.py` | role-match |
| `tests/integration/test_aliens_e2e.py` (NEW or UPDATE) | test | end-to-end | `tests/test_archive.py::test_aliens_canary` (only existing Aliens-as-fixture integration test) | role-match |

---

## Pattern Assignments

### `src/themey/ir.py` — ADD `ColorScheme` and `WallpaperSpec` dataclasses

**Analog:** the file itself — extend in-place using the existing frozen-dataclass conventions.

**Frozen dataclass with explicit RGB triples** (`src/themey/ir.py` lines 15-23, the existing `Palette`):
```python
@dataclass(frozen=True)
class Palette:
    """Sampled dominant colors from the theme imagery."""

    titlebar_active: tuple[int, int, int]  # RGB 0-255
    titlebar_inactive: tuple[int, int, int]
    text_active: tuple[int, int, int]
    text_inactive: tuple[int, int, int]
```

**Optional fields with `None` sentinel** (lines 32-39, `IClassSpec`):
```python
normal: Path | None  # path under asset_root, may be None
normal_active: Path | None
```

**Tuple-of-frozen-children for variable-length children** (lines 75, 100, `BorderSpec.parts` and `Theme.skipped_borders`):
```python
parts: tuple[ButtonPart, ...]
skipped_borders: tuple[str, ...] = ()
```

**`Theme.notes` mutable accumulator pattern** (lines 99, plus the docstring lines 81-85) is the SOLE precedent for mutation; per `02-RESEARCH.md` §8 the new `ColorScheme` and `WallpaperSpec` must be **fully frozen** and added to `Theme` as `Optional[...] = None` defaults so Phase 1's `Theme(...)` constructions still typecheck.

**Pattern to follow when extending Theme:**
- Add `WallpaperSpec` and `ColorScheme` as `@dataclass(frozen=True)` blocks at module level (matching existing style — class-level docstring on first line, fields below).
- Add to `Theme`: `color_scheme: ColorScheme | None = None` and `wallpaper: WallpaperSpec | None = None`. **Defaults required** because Phase 1's `_make_theme` test factory (`tests/test_ir.py:66-84`) does not supply them.
- Do NOT modify `Palette`. Per RESEARCH §8 "Migration Risk", introduce `ColorScheme` as a separate dataclass.

**Apply the helper-method pattern from RESEARCH Decision 5:** add a tiny method on `Theme` (or a free function in `ir.py`) like `note(category, text)` that wraps `theme.notes.append(f"{category}: {text}")`. Phase 2 plan 01 will migrate Phase 1 call sites in `analyze/states.py` (and any others Phase 1 lands).

---

### `src/themey/analyze/background.py` (NEW)

**Analog:** `src/themey/analyze/borders.py` (lines 1-123) — closest match because both walk top-level AST `Block` nodes by keyword and emit a frozen IR object.

**Imports pattern** (`src/themey/analyze/borders.py` lines 1-9):
```python
"""AST __BORDER block → BorderSpec + ButtonPart extraction.

DEFAULT-only selection per CLAUDE.md / WILBS-REFERENCE.md Section 6.
"""
from __future__ import annotations

from themey.etheme.ast import Block, KeyVal
from themey.ir import BorderSpec, ButtonPart
```

**Block-keyword dispatch + `_to_int` value coercion** (lines 11-14, 51-93):
```python
def _to_int(v: object) -> int:
    """Coerce an AST value (int | str) to int for pyright basic compatibility."""
    return int(v)  # type: ignore[arg-type]

# ...
for child in border.children:
    if not (isinstance(child, Block) and child.keyword == "__BORDER_PART"):
        continue
    # ...
    for kv in child.children:
        if not isinstance(kv, KeyVal):
            continue
        k = kv.keyword
        if k == "__ICLASS" and kv.values:
            iclass = str(kv.values[0])
        elif k == "__ACLASS" and kv.values:
            aclass = str(kv.values[0])
```

**Dual-form keyword handling** (`borders.py` `_block_name`, lines 16-29) is a direct precedent for `background.py` recognizing **both** `__DESKTOP` and `__BACKGROUND` block keywords (RESEARCH Pitfall A). Mirror this comment style:
```python
def _block_name(block: Block) -> str | None:
    """Extract block name from head_values or legacy __NAME KeyVal child.

    Handles BOTH naming conventions found in E16 themes:
    - Modern: ``__BORDER DEFAULT __BGN`` → head_values = ("DEFAULT",)
    - Legacy macro (Aliens.etheme): ``__BORDER __BGN __NAME DEFAULT ...``
    """
```

**Path-traversal defense (T-05-01 mitigation)** copied from `analyze/iclasses.py` lines 84-95 — required for any path read from cfg per RESEARCH §Security:
```python
asset_root_resolved = str(asset_root.resolve())
# ...
full = (asset_root / p).resolve()
# T-05-01: reject paths that escape asset_root
if not (
    str(full) == asset_root_resolved
    or str(full).startswith(asset_root_resolved + "/")
):
    states[kv.keyword] = None
```

**Action for the planner:**
- Function signature `select_wallpaper(ast_blocks: list[Block], asset_root: Path, iclasses: dict[str, IClassSpec]) -> WallpaperSpec | None`.
- Walk both `__DESKTOP` and `__BACKGROUND` blocks; first in source order wins; rest go into `skipped_alternatives`.
- For every file path from `__BACKGROUND_LAYER`, run the iclasses.py path-traversal check.
- Use `_to_int` for the trailing 6 numeric params.

---

### `src/themey/analyze/colors.py` (NEW)

**No clean analog — this is the first Pillow-quantize use in the codebase.**

**Closest existing PIL-boundary pattern** is `src/themey/images/upscale.py` (lines 9-32):
```python
"""NEAREST upscale primitive for pixel-art E16 border PNGs.

Borders MUST use NEAREST resampling (Pitfall 12 / Anti-Pattern in 01-RESEARCH.md).

Phase 2 wallpaper module uses a separate file with photographic resampling.
"""
from __future__ import annotations

from PIL import Image


def upscale_nearest(img: Image.Image, scale: int) -> Image.Image:
    """Return a new Image of (width*scale, height*scale) using NEAREST resampling.
    ...
    """
    if scale not in (1, 2, 3):
        raise ValueError(f"scale must be 1, 2, or 3 (got {scale})")
    if scale == 1:
        return img.copy()
    new_size = (img.width * scale, img.height * scale)
    return img.resize(new_size, resample=Image.Resampling.NEAREST)
```

**Pattern to copy:**
- Module-docstring callout to the resampling/algorithm choice and a sibling-file pointer (`upscale.py` calls out NEAREST; `colors.py` should call out **MEDIANCUT** and point at RESEARCH §2 Pitfall B about transparent-pixel compositing).
- Pure-function-on-`Image` signature; no side effects.
- Validate input ranges with explicit `ValueError`.

**IR-emit shape** mirrors `analyze/tclasses.py` lines 42-83 (`build_tclasses` returns a fully-typed dict):
```python
def build_tclasses(tclass_blocks: list[Block]) -> dict[str, TClassSpec]:
    out: dict[str, TClassSpec] = {}
    for block in tclass_blocks:
        # ... compute ...
        out[name] = TClassSpec(name=name, fg_normal=..., fg_active=...)
    return out
```

**Recommended clean-slate signatures (per RESEARCH §2 + Code Examples lines 1037-1061):**
```python
"""Pillow MEDIANCUT dominant-color extraction + KColorScheme role assignment.

MEDIANCUT chosen per CLAUDE.md TL;DR (colorthief/colorgram unmaintained).
Composite-over-grey before quantize per RESEARCH §2 Pitfall B (transparent
pixels otherwise bias the palette toward black).

Phase 2 wallpaper module is in generate/wallpaper.py (this file is the
analyze-side colour extraction; that one is the file-write side).
"""
from __future__ import annotations
from pathlib import Path
from typing import NamedTuple
from PIL import Image
from themey.ir import ColorScheme, IClassSpec, TClassSpec, WallpaperSpec

Image.MAX_IMAGE_PIXELS = 100_000_000  # decompression-bomb guard (RESEARCH §Security)

class WeightedColor(NamedTuple):
    rgb: tuple[int, int, int]
    weight: float

def extract_dominant(image_path: Path, k: int = 8) -> list[WeightedColor]:
    ...

def build_color_scheme(
    iclasses: dict[str, IClassSpec],
    tclasses: dict[str, TClassSpec],
    wallpaper: WallpaperSpec | None,
    notes: list[str],
) -> ColorScheme:
    ...
```

The `notes: list[str]` parameter mirrors `analyze/states.py` `collapse_image_states` (lines 40-79): the analyze layer is the single owner of the `Theme.notes` accumulator, takes it by reference, appends prefix-tagged strings.

---

### `src/themey/generate/colors.py` (NEW) — `RawConfigParser` `.colors` writer

**No existing analog — `generate/` package does not exist yet.**

**Closest pattern** is `tests/fixtures/build_tiny_etheme.py` lines 98-112 (the only stdlib-only multi-block writer in the repo):
```python
def _add(tar: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    tar.addfile(info, io.BytesIO(content))


def main() -> None:
    with tarfile.open(OUT, "w:gz") as tar:
        _add(tar, "borders.cfg", BORDERS_CFG)
        _add(tar, "borders/default.cfg", BORDERS_DEFAULT_CFG)
        ...
```

**Pattern to copy:**
- Stdlib-only top-of-file imports (`from __future__ import annotations`, `import configparser`, `from pathlib import Path`).
- Tiny private helpers (`_add` style) for each section assignment.
- One public `write_colors_ini(theme: Theme, out_path: Path) -> Path` returning the absolute written path (matches the `tests/fixtures/build_tiny_etheme.py` "do one thing, return what was written" idiom).

**Clean-slate signature recommendation (matches RESEARCH §1 + Code Examples lines 1066-1126):**
```python
"""KColorScheme `.colors` INI writer using stdlib RawConfigParser.

Format: verified against /usr/share/color-schemes/BreezeDark.colors (Plasma 6.6.4).
Uses optionxform = str to preserve case-sensitive KDE keys (BackgroundNormal,
LeftButtons, etc.) — see CLAUDE.md "What NOT to Use".

NO interpolation=None needed: real .colors values do not contain `%` characters.
Verify Pitfall E (`[Colors:Header][Inactive]` round-trip) in Plan 02 implementation.
"""
from __future__ import annotations
import configparser
from pathlib import Path

from themey.ir import Theme

def _rgb(t: tuple[int, int, int]) -> str:
    return f"{t[0]},{t[1]},{t[2]}"

def write_colors_ini(theme: Theme, out_path: Path) -> Path:
    cp = configparser.RawConfigParser()
    cp.optionxform = str  # KDE keys are case-sensitive
    # ... build sections per RESEARCH Code Example ...
    with out_path.open("w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
    return out_path
```

**Critical pyright-basic detail copied from analyze/iclasses.py:** `cp.optionxform = str` triggers a pyright basic warning (assigning a method override). The existing codebase pattern (search `analyze/iclasses.py:62`, `analyze/borders.py:13`, `analyze/tclasses.py:20`) is `# type: ignore[arg-type]` or `# type: ignore[method-assign]` inline comment when needed.

---

### `src/themey/generate/wallpaper.py` (NEW)

**Closest analog** is `src/themey/etheme/archive.py` lines 100-104 — only file in the repo that writes raw bytes to disk:
```python
target.parent.mkdir(parents=True, exist_ok=True)
with tf.extractfile(m) as src, open(target, "wb") as dst:  # type: ignore[union-attr]
    dst.write(src.read())
```

**Mkdir-then-write pattern from archive.py line 100** is exactly what `metadata.json` and the `contents/images/` write need.

**Path-traversal validation pattern** copied from `archive.py` lines 76-79 — required because the wallpaper image path comes from cfg:
```python
target = (dest / m.name).resolve()
dest_prefix = str(dest) + "/"
if not str(target).startswith(dest_prefix) and target != dest:
    raise UnsafeArchiveError(f"member escapes dest: {m.name}")
```

**For Pillow image conversion** copy `src/themey/images/upscale.py` discipline (Pillow `Image.open` + `Resampling.LANCZOS` for photographic per CLAUDE.md, distinct from `upscale.py`'s NEAREST):
```python
# Mirrors upscale.py module-doc pattern: state the resampling choice + why
"""Wallpaper image copy + Plasma metadata.json writer.

LANCZOS resampling for photographic content per CLAUDE.md TL;DR
(NEAREST is reserved for pixel-art borders in src/themey/images/upscale.py).
GIF→PNG conversion per RESEARCH Pitfall I.
"""
```

**Filename convention discipline** (RESEARCH Pitfall C):
- Read actual `(w, h) = img.size` from PIL after open.
- Format `f"{w}x{h}{ext}"` with lowercase `x`.
- Add a unit test asserting `metadata["KPlugin"]["Id"] == out_dir.name` (RESEARCH Pitfall D).

**Recommended clean-slate signatures (per RESEARCH Code Examples lines 1130-1175):**
```python
def write_wallpaper_metadata(theme: Theme, out_dir: Path) -> Path: ...
def write_wallpaper_image(src: Path, contents_images_dir: Path) -> Path: ...
```

---

### `src/themey/generate/__init__.py` (NEW)

**Analog:** `src/themey/analyze/__init__.py` (line 1):
```python
"""Analyze sub-package: pure-function algorithm primitives for the analyze pipeline."""
```

Adapt to:
```python
"""Generate sub-package: file-output writers (.colors INI, wallpaper json+image)."""
```

---

### `src/themey/report.py` (NEW for Phase 2)

**Closest analog** is `src/themey/analyze/states.py` (lines 40-79) — the producer of the existing `Theme.notes` format. The note-format reader (this file) must agree with the producer.

**Existing note format established by states.py lines 75-78:**
```python
notes.append(
    f"{context_label}: {src_state} dropped "
    f"(no Aurorae target for sticky/disabled/clicked-active variants)"
)
```

**Categorization heuristic (RESEARCH §5 + Decision 5 + Pitfall J):** Phase 2 plan 01 should introduce a `_note(category, text)` helper in `ir.py` (or a free function next to `Theme`) and **migrate the states.py call site** above to:
```python
theme.notes.append(f"SKIPPED: {context_label}: {src_state} (no Aurorae target ...)")
```

**Module-docstring pattern** copied from `analyze/states.py` lines 1-9:
```python
"""E16 -> Aurorae image-state collapse. Lossy by design; logs every drop.

E16 has up to 16 image-state cells; Aurorae has 2 (active, inactive)
plus 3 button SVG sub-states (default, hover, pressed). The 8-state
practical model (per WILBS-REFERENCE.md Section 2) maps as below.
"""
```

Adapt for `report.py`:
```python
"""report.txt three-section renderer: PRESERVED / APPROXIMATED / SKIPPED.

Notes are prefix-tagged at write-time (per RESEARCH §5 Decision 5) so
categorization is deterministic O(N). Free-form notes (Phase 1 legacy)
default to APPROXIMATED — overstates lossiness rather than understating.
"""
```

**Pure-function signature pattern** mirrors `analyze/states.py` `collapse_image_states` and `analyze/borders.py` `build_border` — single function, all I/O via parameters, returns a value:
```python
def categorize_notes(notes: list[str]) -> dict[str, list[str]]: ...
def render_report(theme: Theme, output_paths: list[Path]) -> str: ...
```

**Constant tables at module top** (mirroring `states.py` `DECORATION_STATE_MAP`, `BUTTON_STATE_MAP`, `DROPPED_STATES`):
```python
PRESERVED_PREFIX = "PRESERVED: "
APPROXIMATED_PREFIX = "APPROXIMATED: "
SKIPPED_PREFIX = "SKIPPED: "
SECTION_HEADERS: dict[str, str] = {
    "preserved": "PRESERVED (mapped 1:1 from E16 source)\n" + "=" * 38,
    "approximated": "APPROXIMATED (lossy mapping; reason explained)\n" + "=" * 46,
    "skipped": "SKIPPED (no Plasma equivalent or out of scope for v1)\n" + "=" * 53,
}
```

---

### `src/themey/preview.py` (NEW or ENRICH)

**Embed primitive — exact analog** in `src/themey/images/embed.py` lines 32-43:
```python
def image_to_b64_uri(img: Image.Image) -> str:
    """Save a Pillow Image as PNG bytes, then embed as data URI.

    Args:
        img: Any Pillow Image. Will be serialized as PNG.

    Returns:
        A ``data:image/png;base64,...`` data URI string.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return embed_png_b64(buf.getvalue())
```

**The wallpaper thumbnail in RESEARCH §6 lines 649-660 is a JPEG (not PNG)** so the planner has two options:
1. Add a `image_to_jpeg_b64_uri(img, quality=80)` companion in `images/embed.py` (preferred — single source of truth for embedding).
2. Inline the BytesIO/base64 dance in `preview.py` (acceptable but duplicates logic).

**Pattern to follow:** add the JPEG helper to `images/embed.py`. Mirror the existing `image_to_b64_uri` docstring shape. The DATA_URI_PREFIX constant pattern (`embed.py` line 14) generalizes to `JPEG_URI_PREFIX = "data:image/jpeg;base64,"`.

**HTML+CSS scaffold itself is clean-slate** — no precedent in the repo. Use the `.swatches` flexbox + `.wallpaper-thumb` CSS shown in RESEARCH §6 lines 619-674. Use stdlib f-strings (no template engine).

**Critical:** The base64 image data URI is **not** snapshot-stable across Pillow versions (RESEARCH §9 line 815). Per the test strategy, snapshot the HTML with the data URI replaced by a placeholder; test the URI separately for `startswith("data:image/jpeg;base64,")`. This mirrors the `tests/test_embed.py:test_embed_png_b64_prefix` (line 21) and `test_embed_png_b64_roundtrip` (line 32) patterns.

---

### `tests/test_colors.py`, `tests/test_wallpaper.py`, `tests/test_report.py` (NEW)

**Analog for unit-test structure:** `tests/test_analyze_iclasses.py` (lines 1-183) and `tests/test_states.py` (lines 1-97).

**Synthetic AST factory pattern** from `tests/test_analyze_iclasses.py` lines 17-23:
```python
def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _iclass_block(name: str, *children: KeyVal) -> Block:
    """Build a synthetic __ICLASS block with head_values=(name,)."""
    return Block(keyword="__ICLASS", head_values=(name,), children=children, line=0)
```

For `test_colors.py` adapt to:
```python
def _desktop_block(name: str, *children: KeyVal) -> Block:
    return Block(keyword="__DESKTOP", head_values=(), children=(_kv("__NAME", name), *children), line=0)
```

**Theme factory pattern** from `tests/test_ir.py` lines 8-84 — `_make_theme(**kwargs)` defaults dict + `defaults.update(kwargs)` is the established override idiom. Phase 2 must extend `_make_theme` to set `color_scheme=None, wallpaper=None` defaults so existing tests keep passing.

**Tmp-path pattern** from `tests/test_analyze_iclasses.py` lines 31, 81 — every file-touching test takes `tmp_path: Path` (not `fake_home` — `fake_home` is reserved for tests that exercise XDG path resolution end-to-end).

**Existing-file write pattern** from `tests/test_analyze_iclasses.py` lines 81-84:
```python
def test_build_iclass_state_paths_resolve_existing_files(tmp_path: Path) -> None:
    """When the file exists on disk, .is_file() returns True."""
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "n.png").write_bytes(b"fake png")
```

For wallpaper tests use this exact pattern with PNG bytes from `tests/test_embed.py` `_make_png_bytes` (lines 12-17):
```python
def _make_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Create a small PNG image and return its bytes."""
    img = Image.new("RGBA", (width, height), (42, 84, 126, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
```

**Snapshot tests are clean-slate.** No `.ambr` file exists in `tests/`. The syrupy convention per docs is:
```python
def test_colors_snapshot_aliens(snapshot, tmp_path):
    # ... build a Theme, call write_colors_ini, read back ...
    assert (tmp_path / "Aliens.colors").read_text() == snapshot
```
First run creates `tests/__snapshots__/test_colors.ambr`. Per RESEARCH §9, regenerate via `pytest --snapshot-update` after Pillow upgrades. Document this in the test file's module docstring.

**Structural-assertion pattern (for binaries / file-existence)** from `tests/test_archive.py::test_aliens_canary_extracts` (per Phase 1 Plan 02 SUMMARY metrics — file structure assertions, not byte snapshots). Apply to `test_wallpaper.py` for the `<W>x<H>.jpg` image — assert exists, assert PIL can re-open it, assert dimensions, do NOT byte-snapshot.

---

### `tests/integration/test_aliens_e2e.py` (NEW or UPDATE)

**Closest analog** is the Aliens canary in `tests/test_archive.py` (the only existing test that touches the real `Aliens.etheme` fixture per `01-02-SUMMARY.md`).

**Pattern to follow:**
- Fixture path discipline: `tests/fixtures/Aliens.etheme` (already committed, 2.4 MB).
- Use the `extract()` contextmanager from `themey.etheme.archive` (lines 43-55 of `archive.py`):
  ```python
  with extract(etheme_path) as raw:
      # raw.asset_root is valid only inside the with-block
      ...
  ```
- Use `fake_home` (`tests/conftest.py` lines 14-24) for any test that asserts on install paths under `~/.local/share/`.

**Phase 2 e2e test additions:**
- After convert → assert `~/.local/share/color-schemes/Aliens.colors` exists and parses with `RawConfigParser`.
- Assert `~/.local/share/wallpapers/Aliens/metadata.json` parses with `json.load` and `KPlugin.Id == "Aliens"`.
- Assert `~/.local/share/wallpapers/Aliens/contents/images/` contains exactly one file matching the regex `r"\d+x\d+\.(jpg|png)"`.
- Assert report.txt contains all three section headers (`PRESERVED`, `APPROXIMATED`, `SKIPPED`).

---

## Shared Patterns

### Module Docstring
**Source:** `src/themey/etheme/archive.py` lines 1-7, `src/themey/analyze/states.py` lines 1-9, `src/themey/images/upscale.py` lines 1-8
**Apply to:** Every new Phase 2 module
```python
"""<one-line summary>.

<paragraph explaining the why, citing RESEARCH section / pitfall by reference>.

<sibling-pointer to related module if relevant, e.g. "Phase 2 wallpaper module
uses a separate file with photographic resampling.">
"""
from __future__ import annotations
```

The `from __future__ import annotations` line appears in every `.py` source file in the repo and is mandatory for the project's Python 3.11+ baseline.

### Path-Traversal Validation (T-05-01 / V5 Input Validation)
**Source:** `src/themey/analyze/iclasses.py` lines 62, 84-95; `src/themey/etheme/parse.py` lines 91, 101-106; `src/themey/etheme/archive.py` lines 74-79, 83-86
**Apply to:** `src/themey/analyze/background.py` (every `__BACKGROUND_LAYER` file path), `src/themey/analyze/colors.py` (every image path opened from cfg), `src/themey/generate/wallpaper.py` (image source path before PIL.open)
```python
asset_root_resolved = str(asset_root.resolve())
full = (asset_root / p).resolve()
if not (
    str(full) == asset_root_resolved
    or str(full).startswith(asset_root_resolved + "/")
):
    # treat as missing-asset (None) or raise — depends on context
    ...
```

### Pyright-basic Type Coercion
**Source:** `src/themey/analyze/borders.py` line 13, `src/themey/analyze/iclasses.py` line 28, `src/themey/analyze/tclasses.py` line 22
**Apply to:** All Phase 2 analyze code that reads `KeyVal.values` (which is typed `tuple[object, ...]`)
```python
def _to_int(v: object) -> int:
    """Coerce an AST value (int | str) to int for pyright basic compatibility."""
    return int(v)  # type: ignore[arg-type]
```

This is the project's established pattern for the `KeyVal.values: tuple[object, ...]` boundary. Re-define locally in each new module (the existing analyze files all duplicate it; do not import — keep modules independently importable).

### Notes Accumulator Convention
**Source:** `src/themey/analyze/states.py` lines 40-79 (`collapse_image_states(..., notes: list[str], context_label: str)`)
**Apply to:** `analyze/background.py`, `analyze/colors.py` — every analyze function that may produce a fidelity warning takes `notes: list[str]` as a parameter and `theme.notes` is passed in by the caller. Do NOT mutate `theme` directly inside analyze primitives — they remain pure-on-non-list-args.

**Phase 2 prefix-tag migration:** Per RESEARCH Decision 5, the existing free-form append (`states.py` lines 75-78) must change from:
```python
notes.append(f"{context_label}: {src_state} dropped (no Aurorae target ...)")
```
to:
```python
notes.append(f"SKIPPED: {context_label}: {src_state} (no Aurorae target ...)")
```
Plan 02-01 owns this migration. The single existing call site is in `src/themey/analyze/states.py:75`. The corresponding test assertion in `tests/test_states.py:84-88` uses `in` substring checks that will continue to pass (it checks for `__NORMAL_STICKY`, `__DISABLED`, `TITLE_BAR_HORIZONTAL` — all still present after the prefix is added).

### Frozen-Dataclass Field Conventions
**Source:** `src/themey/ir.py` lines 15-100, `src/themey/etheme/ast.py` lines 18-83
**Apply to:** `ColorScheme`, `WallpaperSpec` additions
- `@dataclass(frozen=True)` on every class.
- Class-level docstring on first line after the decorator.
- `tuple[int, int, int]` for RGB (never `list[int]` or `Color` namedtuple — repo convention is plain tuples).
- `Path | None` for optional file paths.
- `tuple[X, ...]` for variable-length child collections (never `list[X]` — frozen consistency).
- New fields on `Theme` must have `= None` or `= field(default_factory=...)` defaults so existing `Theme(...)` constructions in `tests/test_ir.py:66-84` still typecheck.

### Decompression-Bomb Guard
**Source:** RESEARCH §Security recommendation lines 988-991 (no existing analog — Phase 1 has no PIL.open from untrusted input)
**Apply to:** `analyze/colors.py`, `generate/wallpaper.py`, `preview.py` — every module that calls `Image.open` on a path derived from cfg
```python
from PIL import Image
Image.MAX_IMAGE_PIXELS = 100_000_000  # decompression-bomb guard
```
Set this once at module top (Pillow's `MAX_IMAGE_PIXELS` is process-global). Per RESEARCH this is sufficient for the corpus (largest legitimate wallpaper is ~3 MP). Phase 1's `archive.py` does the equivalent for tar via `MAX_TOTAL_BYTES`/`MAX_FILE_BYTES`/`MAX_ENTRIES` (lines 18-20).

---

## No Analog Found (clean-slate guidance for the planner)

| File | Role | Data Flow | Reason | Recommended Approach |
|------|------|-----------|--------|----------------------|
| `src/themey/generate/colors.py` | utility | file-I/O sink | No `generate/` package exists; first `RawConfigParser`-using module | Follow RESEARCH §Code Examples lines 1066-1126 verbatim. Verify Pitfall E (`[Colors:Header][Inactive]` round-trip) in Plan 02-01 RED phase before committing the writer. |
| `src/themey/generate/wallpaper.py` | utility | file-I/O sink + image transform | First `json.dumps`-using module; first `shutil.copy2`-using module | Follow RESEARCH Code Examples lines 1130-1175. Path-traversal validation copied from archive.py. |
| `src/themey/preview.py` | utility | file-I/O sink (HTML) | Phase 1 plan 01-09 hasn't landed; no HTML scaffold in repo yet | Build clean-slate; reuse `images/embed.py` for base64. Add a JPEG variant (`image_to_jpeg_b64_uri`) to embed.py rather than inline-coding base64 in preview.py. |
| `tests/snapshots/*.ambr` (syrupy) | test artifact | snapshot file | No syrupy snapshot file exists in the repo; only unit tests have been written so far | First `pytest` run creates `tests/__snapshots__/test_<name>.ambr`. Document in test-module docstring that updates require `pytest --snapshot-update`. Per RESEARCH §9 line 815, do NOT snapshot the base64 wallpaper data URI — replace it with a placeholder for the snapshot. |

---

## Metadata

**Analog search scope:** `/home/cstory/src/themey/src/themey/` (entire source tree, 14 .py files), `/home/cstory/src/themey/tests/` (entire test tree, 14 .py files), `/home/cstory/src/themey/pyproject.toml`, `/home/cstory/src/themey/CLAUDE.md`, all 4 Phase 1 SUMMARY files referenced in upstream input.

**Files scanned:** 28 source/test files + 4 phase-1 summaries + RESEARCH.md (1336 lines).

**Notable coverage gaps the planner should be aware of:**
1. Phase 1 plans 01-05 (analyze pipeline `build_theme.py`), 01-08 (`report.py`, `preview.py`, `install.py`), 01-09 (`cli.py`, integration test) are **not yet committed**. Phase 2 planning that depends on these landed files (notably `report.py` refactor and `install.py` reuse) must either:
   - Coordinate sequencing — wait for 01-08 to land before starting Phase 2 plan 04 (report) / plan 05 (atomic install reuse), OR
   - Build clean-slate Phase 2 versions and have Phase 1 align (per RESEARCH "Migration Risk").
2. The single existing call site that produces a `Theme.notes` entry is `src/themey/analyze/states.py:75-78`. Migration to the prefix-tag convention is **one change**, not the "5–10 sites" RESEARCH Decision 5 estimates — until Phase 1 plans 01-05 / 01-08 add more sites.
3. No `RawConfigParser` precedent exists in the repo. Pitfall E (`[Colors:Header][Inactive]` round-trip) is genuinely untested; Plan 02 (colors writer) RED phase should include a test that round-trips this exact section name and falls back to `Path.write_text(hand_formatted)` if it fails.

**Pattern extraction date:** 2026-05-01
