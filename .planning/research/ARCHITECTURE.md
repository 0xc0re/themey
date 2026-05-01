# Architecture Research

**Domain:** Local Python CLI — pipeline-style format converter (E16 `.etheme` → KDE Plasma 6 Look-and-Feel)
**Researched:** 2026-05-01
**Confidence:** HIGH (architecture choices follow well-known Python CLI/pipeline conventions; E16 grammar and KDE output formats are confirmed in `PROJECT.md` Context section)

---

## 1. System Overview

themey is a **single-process, single-user, single-pass CLI pipeline**. There is no daemon, no server, no GUI; one invocation reads one (or many) `.etheme` archives, runs a stateless pipeline, and writes outputs under `~/.local/share/`. This is the simplest topology that satisfies the requirements and it should not become more complicated.

```
┌──────────────────────────────────────────────────────────────────┐
│                     CLI / Orchestrator                           │
│              (argparse, batch loop, exit codes)                  │
└────────────────────────────────┬─────────────────────────────────┘
                                 │  one ConvertJob per .etheme
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Stage 1: Ingest                               │
│  archive  →  extract (tarfile)  →  parse (.cfg + #include)       │
│              ──────────────                                       │
│              outputs: RawTheme (asset tree path + parsed AST)    │
└────────────────────────────────┬─────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│                Stage 2: Analyze / Normalize                      │
│   resolve cross-refs, classify buttons L/R, sample colors,       │
│   pick wallpaper, compute scaled dimensions                       │
│              ──────────────                                       │
│              outputs: Theme  (canonical IR — see §3)             │
└────────────────────────────────┬─────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│              Stage 3: Generate (per output type)                 │
│  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────┐ ┌──────────┐  │
│  │ Aurorae │ │ Colors  │ │ Wallpapr │ │ Cursors │ │  L&F     │  │
│  └────┬────┘ └────┬────┘ └────┬─────┘ └────┬────┘ └────┬─────┘  │
│       └───────────┴───────────┴────────────┴───────────┘         │
│                outputs: BuildArtifact list                       │
└────────────────────────────────┬─────────────────────────────────┘
                                 ▼
┌──────────────────────────────────────────────────────────────────┐
│         Stage 4: Install + Report + Preview                      │
│  stage to tmpdir → atomic move into ~/.local/share/...           │
│  write report.txt → render preview.html → optional open          │
└──────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
                External: lookandfeeltool, xcursorgen, xdg-open
```

Key property: **the IR is the only thing that crosses Stage 2 → Stage 3.** Generators never re-read the archive or re-parse `.cfg` files. This is what makes Stage 3 trivially parallelizable and trivially testable.

---

## 2. Recommended Project Structure

```
src/themey/
├── __init__.py
├── __main__.py             # python -m themey entrypoint
├── cli.py                  # argparse, dispatch, batch loop, exit codes
│
├── etheme/                 # E16 INPUT side (everything format-specific to E16)
│   ├── __init__.py
│   ├── archive.py          #   .etheme → unpacked tree (gzipped tar)
│   ├── lex.py              #   tokenizer: comments, strings, numbers, idents
│   ├── parse.py            #   __BLOCK __BGN/__END recursive descent + #include
│   ├── ast.py              #   raw AST dataclasses (Block, KeyVal, Include)
│   └── grammar.md          #   prose spec (the "source of truth" doc)
│
├── ir.py                   # Canonical Theme dataclass + all sub-records
│                           # (no I/O, no Pillow, no E16 names — pure data)
│
├── analyze/                # ANALYSIS — RawTheme + AST → Theme IR
│   ├── __init__.py
│   ├── borders.py          #   border + iclass + tclass → BorderSpec
│   ├── buttons.py          #   center-of-mass test → LeftButtons/RightButtons
│   ├── colors.py           #   image sampling → palette
│   ├── wallpaper.py        #   pick init.cfg bg or fallback
│   └── cursors.py          #   collect xbm pairs (cursor + mask)
│
├── images/                 # Pure image utilities (Pillow wrappers)
│   ├── __init__.py
│   ├── ninepatch.py        #   slice to 9 regions given __EDGE_SCALING values
│   ├── upscale.py          #   nearest-neighbour 2x/3x for pixel art
│   └── sample.py           #   dominant-colour extraction
│
├── generate/               # OUTPUT side — one module per Plasma artifact
│   ├── __init__.py
│   ├── aurorae.py          #   decoration.svg + buttons + <name>rc + .desktop
│   ├── colors.py           #   .colors INI (KColorScheme)
│   ├── wallpaper.py        #   wallpaper package (metadata.json + images)
│   ├── cursors.py          #   xcursorgen invocation + cursor theme tree
│   └── lookandfeel.py      #   metadata.json + lookandfeel package wrapper
│
├── install.py              # stage to tmpdir, atomic rename into ~/.local/share/
├── preview.py              # render HTML preview (Jinja-free; stdlib + f-strings)
├── report.py               # report.txt: preserved / approximated / skipped
├── external.py             # subprocess wrappers: xcursorgen, lookandfeeltool, xdg-open
├── paths.py                # XDG_DATA_HOME resolution, install path constants
└── log.py                  # thin logging facade (stdlib logging, --verbose flag)

tests/
├── conftest.py             # fixtures: synthetic_theme, real_theme(Aliens), fake_home
├── fixtures/
│   ├── tiny.etheme         #   ~5KB hand-crafted; one border, two buttons, one bg
│   └── Aliens.etheme       #   real-world fidelity check
├── unit/
│   ├── test_lex.py
│   ├── test_parse.py       #   parsing + #include resolution
│   ├── test_analyze_*.py
│   ├── test_images_*.py
│   └── test_generate_*.py  #   snapshot tests per generator
├── integration/
│   ├── test_pipeline.py    #   tiny.etheme → all 5 outputs (no install)
│   └── test_install.py     #   uses tmp_path-based fake_home fixture
└── snapshots/              #   golden output trees per fixture
```

### Structure Rationale

- **`etheme/` and `generate/` are mirror-image siblings.** The whole conversion is "left half reads, right half writes," and the directory layout makes that visible. A new contributor reads `cli.py`, sees the four-stage pipeline, and walks straight into `etheme/parse.py` or `generate/aurorae.py` without hunting.
- **`ir.py` is a single flat file at the package root.** It is the contract between halves. Putting it in a folder hides it. Keeping it short and import-cheap (no Pillow, no I/O) lets every other module depend on it freely without circular-import worry.
- **`analyze/` is its own layer, not buried in `etheme/` or `generate/`.** Analysis (button binning, colour sampling, scaling) is *interpretation* of E16 data with Plasma intent in mind — it belongs to neither side. Splitting it out also makes the units small and testable in isolation.
- **`images/` is below `analyze/` and `generate/` in the dependency DAG.** It contains zero E16 or KDE knowledge — just slice / upscale / sample. This keeps Pillow contained to one corner of the codebase.
- **`external.py` is a single chokepoint for every subprocess call.** Missing-binary handling, timeout policy, dry-run support, and error formatting live in exactly one place.
- **`tests/fixtures/tiny.etheme` is hand-crafted, not borrowed.** A 5 KB synthetic theme exercises every grammar feature deterministically and runs in ms. `Aliens.etheme` provides reality-check coverage.

---

## 3. Canonical Intermediate Representation

**Recommendation: one `Theme` dataclass that all five generators consume.** Per-output structs are an anti-pattern for this project — they duplicate the shared header (name, author, palette, scale) and force the analysis layer to know about output formats.

```python
# src/themey/ir.py  (skeleton — full schema in code)
from dataclasses import dataclass, field
from pathlib import Path

@dataclass(frozen=True)
class Color: r: int; g: int; b: int; a: int = 255

@dataclass(frozen=True)
class Palette:
    titlebar_active: Color
    titlebar_inactive: Color
    text_active:     Color
    text_inactive:   Color
    window_bg:       Color
    accent:          Color
    # ... ~10 fields total, mirroring KColorScheme INI section keys

@dataclass(frozen=True)
class NinePatch:                       # one image plus its 9-patch hint frame
    source_png: Path                   # path inside extracted asset tree
    left: int; right: int; top: int; bottom: int     # in *output* pixels (post-scale)

@dataclass(frozen=True)
class BorderSpec:                      # one Aurorae frame state
    active:     NinePatch
    inactive:   NinePatch
    maximized:  NinePatch | None       # None → reuse active

@dataclass(frozen=True)
class ButtonSpec:
    code: str                          # 'X','I','A','S','F','B','L','H','N','M'
    side: str                          # 'L' | 'R'
    glyph_active:   Path | None
    glyph_inactive: Path | None
    glyph_pressed:  Path | None

@dataclass(frozen=True)
class CursorSpec:
    name: str                          # X cursor name (e.g., 'left_ptr')
    bitmap_xbm: Path
    mask_xbm:   Path | None
    hot_x: int; hot_y: int

@dataclass(frozen=True)
class WallpaperSpec:
    source: Path
    is_fallback: bool                  # True if init.cfg had no bg → we picked one

@dataclass(frozen=True)
class Theme:
    name: str
    display_name: str
    author: str | None
    description: str | None
    scale: int                         # 1, 2, or 3
    border: BorderSpec
    buttons: list[ButtonSpec]
    palette: Palette
    wallpaper: WallpaperSpec | None
    cursors: list[CursorSpec]
    notes: list[str] = field(default_factory=list)   # feeds report.txt
```

### Why one IR, not five

- **DRY metadata.** Name/author/scale appear in every output. Split structs would carry duplicate fields and make rename/version bumps a five-touch change.
- **Generators stay pure.** Each generator is `def generate(theme: Theme, out_dir: Path) -> list[Path]`. No upstream ordering, no hidden coupling. Trivial to unit-test with a hand-built `Theme`.
- **Snapshot testing becomes free.** A `Theme` is a frozen dataclass tree → `dataclasses.asdict` → JSON → diff against golden file. Snapshots verify the analysis stage independently of any generator's output.
- **Parallelism is real.** `concurrent.futures.ThreadPoolExecutor` over the five generators works cleanly because `Theme` is frozen; Pillow holds the GIL during decode but releases it during heavy native work, so two-three workers shave wall-clock time on a batch run. (For a single-theme run, parallelism is not worth the complexity — see §6.)
- **`notes: list[str]`** is the one place the IR is mutable in spirit. Generators may append fidelity notes ("button 'help' had no glyph, used system fallback") which `report.py` flushes at the end. Keep this as the **only** back-channel; don't let it grow into a generic event bus.

### Alternative considered: per-output dataclasses

Each generator gets its own typed input (`AuroraeSpec`, `ColorsSpec`, ...). Rejected because (a) the analysis layer becomes responsible for output-shaped concerns, (b) duplicate metadata fields, (c) every new fidelity note needs five places to land. The single-IR cost — Aurorae generator imports a `Palette` it ignores — is trivial.

---

## 4. Data Flow

```
.etheme path
    │
    │ etheme/archive.py  (gzipped tar → tmp asset tree)
    ▼
RawTheme(asset_root: Path, manifest: dict)
    │
    │ etheme/parse.py  (lex + recursive descent + #include resolution)
    ▼
RawTheme + AST(list[Block])
    │
    │ analyze/*  (cross-ref iclass↔border, button L/R bin, colour sample, scale)
    ▼
Theme   ◄── this is the boundary
    │
    ├──▶ generate/aurorae.py    → <name>/aurorae/...
    ├──▶ generate/colors.py     → <name>/colors/<name>.colors
    ├──▶ generate/wallpaper.py  → <name>/wallpaper/...
    ├──▶ generate/cursors.py    → <name>/cursors/...     (calls xcursorgen)
    └──▶ generate/lookandfeel.py→ <name>/look-and-feel/...
    │
    │ install.py  (stage to mktemp dir → os.replace into ~/.local/share/...)
    ▼
Installed packages on disk
    │
    ├──▶ report.py   → <name>/report.txt
    └──▶ preview.py  → <name>/preview.html  (and external.open(html) if --preview)
```

**One-way flow.** Nothing downstream imports anything upstream of itself. `etheme/` doesn't import `ir`. `analyze/` imports `etheme.ast` and `ir`. `generate/` imports `ir` and `images`. `install.py` and `report.py` import only `ir`. This DAG is enforceable with a single `pytest` test that walks the AST of imports.

**Where the seams are (for testing):**

| Seam | Test target | How |
|------|-------------|-----|
| archive → AST | `test_parse.py` | feed `tiny.etheme` extracted tree, assert AST shape |
| AST → IR | `test_analyze_*.py` | feed hand-built AST, assert `Theme` shape (snapshot) |
| IR → output bytes | `test_generate_*.py` | feed hand-built `Theme`, snapshot output tree |
| output bytes → installed | `test_install.py` | use `fake_home` fixture (tmp_path-based) |
| end-to-end | `test_pipeline.py` | `tiny.etheme` → all artifacts in tmpdir |

---

## 5. Component Responsibilities

| Component | Single-line responsibility |
|-----------|---------------------------|
| `cli.py` | Parse args, iterate themes, return correct exit code. |
| `etheme/archive.py` | Extract `.etheme` (gzipped tar) to a tmpdir asset tree. |
| `etheme/lex.py` | Tokenize `.cfg` source (comments `/*...*/` and `#`, idents, ints, strings). |
| `etheme/parse.py` | Recursive-descent parse `__BLOCK __BGN ... __END`, resolve `#include` paths. |
| `etheme/ast.py` | Raw AST node dataclasses — no semantic interpretation. |
| `ir.py` | The canonical `Theme` dataclass and all sub-records. |
| `analyze/borders.py` | Resolve `__BORDER → __ICLASS` → produce `BorderSpec` with 9-patch values. |
| `analyze/buttons.py` | Bin buttons into Left/Right by titlebar-midpoint center-of-mass test. |
| `analyze/colors.py` | Sample dominant colours from titlebar/dialog imagery → `Palette`. |
| `analyze/wallpaper.py` | Pick `init.cfg` background or representative image fallback. |
| `analyze/cursors.py` | Pair each `*.xbm` cursor with its mask, read hotspot. |
| `images/ninepatch.py` | Slice a PIL.Image into 9 regions given edge values. |
| `images/upscale.py` | Nearest-neighbour 2×/3× upscale (pixel-art preserving). |
| `images/sample.py` | Pillow `quantize` + dominant-colour extraction. |
| `generate/aurorae.py` | Emit `decoration.svg`, button SVGs, `<name>rc`, `metadata.desktop`. |
| `generate/colors.py` | Emit `<name>.colors` INI in KColorScheme format. |
| `generate/wallpaper.py` | Emit `metadata.json` + `contents/images/<name>.<ext>`. |
| `generate/cursors.py` | Convert XBM pairs to PNGs, write xcursorgen config, invoke `xcursorgen`. |
| `generate/lookandfeel.py` | Emit Look-and-Feel package `metadata.json` linking the four sub-themes. |
| `install.py` | Stage to tmpdir, then `os.replace` each artifact into `~/.local/share/...`. |
| `preview.py` | Render `preview.html` (mock titlebar, swatches, wallpaper thumb, command). |
| `report.py` | Write `report.txt` from `Theme.notes` plus generator-emitted fidelity flags. |
| `external.py` | Resolve and invoke `xcursorgen`, `lookandfeeltool`, `xdg-open`; degrade gracefully. |
| `paths.py` | Resolve `XDG_DATA_HOME`, build install paths, never hard-code `/home/...`. |

---

## 6. Architectural Patterns

### Pattern 1: Functional pipeline with frozen IR

**What:** Each stage is a pure function `In -> Out`. State flows forward via dataclasses; no shared mutable context object.

**When to use:** Any time the problem is "transform A into B" with clear stages. This is exactly that.

**Trade-offs:**
- ✅ Trivially testable — any stage testable with a fake input dataclass.
- ✅ Trivially traceable — `repr(theme)` after analysis tells you everything.
- ✅ Re-runnable — re-running just the generators is a one-liner.
- ⚠ Slightly more allocation than a mutating object, but irrelevant for a CLI that runs in seconds.

```python
# cli.py — the whole pipeline in one readable block
def convert(etheme_path: Path, opts: Options) -> ConvertResult:
    raw   = etheme.archive.extract(etheme_path)
    ast   = etheme.parse.parse_tree(raw)
    theme = analyze.build_theme(raw, ast, scale=opts.scale)
    out   = build_output_dir(theme.name)
    arts  = generate.run_all(theme, out)        # see §7 on parallel/serial
    install.deploy(arts)
    report.write(theme, out / "report.txt")
    preview.render(theme, out / "preview.html")
    return ConvertResult(name=theme.name, html=out / "preview.html", notes=theme.notes)
```

### Pattern 2: Hand-rolled recursive-descent parser (the right choice here)

**What:** A small lexer + recursive-descent parser written in plain Python. No Lark, no Parsimonious, no PLY.

**When to use:** Grammar is small (< ~10 productions), stable (E16 hasn't changed in years), and you want zero runtime dependencies. All three apply.

**Trade-offs vs alternatives:**

| Approach | Verdict | Why |
|----------|---------|-----|
| **Hand-rolled lexer + RD parser** | ✅ Recommended | ~150 lines. Zero deps. Direct control over `#include` resolution and error messages with line numbers. |
| **Lark (Earley/LALR)** | ❌ Overkill | Adds a dependency for a 7-production grammar. Lark is Earley/LALR, not RD; it shines on ambiguous or evolving grammars — neither applies. ([lark-parser docs](https://lark-parser.readthedocs.io/)) |
| **Parsimonious / TatSu (PEG)** | ❌ Overkill | Same overkill story. `#include` would need custom hooks anyway. |
| **Regex section-splitter** | ❌ Fragile | Looks attractive for the flat `__BLOCK __BGN ... __END` shape, but nested blocks (a `__BORDER` containing multiple parts) and `/* ... */` comments crossing lines blow it up. Also produces useless error messages. |
| **`configparser`** | ❌ Wrong format | E16 syntax is not INI — keys are whitespace-delimited, not `=` delimited; values can be lists; comments are C-style. |

**The grammar (sketch):**

```
file        := (toplevel)*
toplevel    := include | block
include     := '#include' string_or_path NEWLINE
block       := keyword '__BGN' (statement)* '__END'
statement   := keyword (value)+ NEWLINE | block
keyword     := IDENT (uppercase, may start with __)
value       := IDENT | INTEGER | STRING | PATH
comment     := '/*' ... '*/' | '#' ... NEWLINE   (skipped by lexer)
```

Recursive descent: one function per non-terminal, each consuming tokens off a peekable iterator. ~150 lines including error messages with `(file, line)` context.

**Fixed-point integers:** the `1024 = 100%` convention is *not* a parser concern. The parser yields `KeyVal('__TOPLEFT_X_PERCENTAGE', 1024)` as a plain integer; `analyze/borders.py` divides by 1024.0 when materializing the `BorderSpec`. Keep the parser dumb.

### Pattern 3: Snapshot testing for generators

**What:** Each generator's golden output (file tree of bytes) is checked into `tests/snapshots/`. Tests assert byte-for-byte equality and CLI flag `--update-snapshots` regenerates.

**When to use:** Generators that produce structured text/binary output where any unintended change is a bug. All five generators qualify.

**Trade-offs:**
- ✅ Catches every accidental output regression.
- ✅ Diffs are human-readable for SVG/INI/JSON outputs.
- ⚠ PNG outputs (button glyphs) need either pixel-tolerant comparison or pinned Pillow version; pin the version.

### Pattern 4: External-process boundary in one file

**What:** `external.py` wraps every `subprocess.run` call. Functions return tagged results (`OK(stdout)`, `MissingBinary(name)`, `Failed(returncode, stderr)`).

```python
# external.py — sketch
def run_xcursorgen(config: Path, out: Path) -> ExternalResult:
    binary = shutil.which("xcursorgen")
    if binary is None:
        return MissingBinary("xcursorgen", install_hint="pacman -S xorg-xcursorgen")
    proc = subprocess.run([binary, str(config), str(out)],
                          capture_output=True, text=True, timeout=30)
    return OK(proc.stdout) if proc.returncode == 0 else Failed(proc.returncode, proc.stderr)
```

Generators handle the union and add a note to `Theme.notes` rather than crashing the whole pipeline. **Cursor generation degrades to "skip cursors, note in report"; Look-and-Feel installation degrades to "files installed, run lookandfeeltool manually".** The HTML preview launcher is a "best effort" — if `xdg-open` is missing, just print the path.

---

## 7. Sequencing: Generators Run Serially in Phase 1

**Run generators serially.** Reasons:

1. A single theme's full conversion is sub-second to a few seconds. There is no human-perceptible win from parallelizing.
2. Errors are easier to attribute when stages run in a deterministic order.
3. Pillow image decoding does release the GIL, but most of our work is small SVG/INI text generation — CPU-bound *within Python*. Threads buy little.
4. Generators do *not* share file targets (each writes to a distinct subdirectory) so parallelism is **safe**, just not *valuable*.

**When to revisit:** if `themey --all <dir>` over 100 themes ever feels slow, parallelize at the **theme** level (one `ConvertJob` per process via `multiprocessing.Pool`) — never at the generator level. Each theme is independent; this scales linearly with cores. Punt this until measured.

**Ordering inside a theme (because it minimizes wasted work on failure):**

```
1. aurorae       (the headline output; fail fast if borders are malformed)
2. colors        (cheap; uses already-loaded images from analyze)
3. wallpaper     (cheap)
4. cursors       (slow + external binary; defer so failure doesn't block the rest)
5. lookandfeel   (last; references all four prior outputs by directory name)
```

Stage 4 (install) is **all-or-nothing** within one theme: stage everything to a tmpdir, then atomic-rename each top-level artifact in. If any generator fatally fails, write the report and skip install.

---

## 8. Image Pipeline Details

Three separate questions; the answers compose:

**Q1: When does 2× upscale happen — before or after slicing?**

**Before.** Upscale the source PNG once with nearest-neighbour, then slice the upscaled image. Slicing first means computing scaled edge values and risking off-by-one fractional pixel issues. Upscale first → all subsequent math is integer.

```python
# analyze/borders.py
img        = Image.open(asset_root / iclass.image)
img_scaled = images.upscale.nearest(img, factor=opts.scale)
edges      = NinePatchEdges(left=L*opts.scale, right=R*opts.scale, ...)
# slicing happens lazily inside generate/aurorae.py — see Q2
```

**Q2: Cache 9-patch slices, or re-slice every time?**

**Don't slice at all in Phase 1.** Aurorae's `decoration.svg` references the source PNG via `<image>` and uses `FrameSvg` hint frames to drive 9-patch stretching natively (this is the design decision recorded in PROJECT.md Key Decisions). KWin handles the slicing at render time. Only upscale + embed.

If a future generator (e.g., per-state PNG export for the HTML preview) needs actual sliced regions, slice on demand and cache by `(source_path, edges, scale)` in an in-process dict. Never persist slices to disk; they're cheap and re-derivable.

**Q3: Color extraction — per-image or per-theme?**

**Per-theme, sampling multiple images.** A single image (just the titlebar) gives a misleading palette. Sample:
- titlebar active state (weight × 3)
- titlebar inactive state (weight × 1)
- dialog/window background (weight × 2)
- one button glyph (weight × 1)

Quantize each with Pillow's median-cut to 8 colours, weight-merge, then pick the top 6 distinct hues. This produces a `Palette` that hangs together visually. Cost: ~100 ms per theme.

---

## 9. Build Order — Phase 1 Candidate

**Phase 1 (MVP — minimum visible value):**

```
✅ etheme/archive.py        extract gzipped tar
✅ etheme/lex.py + parse.py recursive-descent parser
✅ etheme/ast.py            AST nodes
✅ ir.py                    Theme dataclass
✅ analyze/borders.py       border + iclass → BorderSpec
✅ analyze/buttons.py       L/R binning
✅ images/upscale.py        2× nearest-neighbour
✅ generate/aurorae.py      THE headline output
✅ install.py               atomic install to ~/.local/share/aurorae/themes/
✅ preview.py               HTML preview (Aurorae mock + activation command)
✅ external.py              subprocess wrappers (only `xdg-open` needed yet)
✅ cli.py                   `themey <theme.etheme>` (single-theme, no batch)
```

**Phase 1 deliverable:** `themey aliens.etheme` produces an installable Aurorae window decoration the user can apply via System Settings → Window Decorations. HTML preview opens in browser. **No global-theme bundle yet, no colors, no wallpaper, no cursors.** This is enough to validate the hardest piece (Aurorae fidelity).

**Defer to Phase 2:**
- `analyze/colors.py` + `generate/colors.py` (nice but not the headline)
- `analyze/wallpaper.py` + `generate/wallpaper.py` (one image; trivial after Phase 1 lands)
- `report.py` (Phase 1 just prints notes to stdout)

**Defer to Phase 3:**
- `generate/cursors.py` (XBM → XCursor + xcursorgen; the most painful generator and least visible)
- `generate/lookandfeel.py` + bundling (depends on the four prior outputs existing)
- `cli.py --all` batch mode

**Defer to Phase 4:**
- Robustness: error recovery in parser, malformed-archive handling, edge-case borders
- Snapshot test infrastructure across all generators
- Per-theme `report.txt` polish

**Why this order:** the Aurorae generator is the highest-risk, highest-value component. If it doesn't work, nothing matters. If it does, the remaining generators are straightforward applications of the same IR-to-format pattern and can be added one per phase without disturbing earlier work.

---

## 10. External-Process Boundaries

| Binary | Used by | Phase | Failure behavior |
|--------|---------|-------|------------------|
| `xdg-open` (or `firefox`) | `preview.py` | 1 | If missing, print path; don't fail. |
| `xcursorgen` | `generate/cursors.py` | 3 | If missing, skip cursor output, add `Theme.notes` entry, install proceeds. |
| `lookandfeeltool` | `cli.py` (post-install hint only) | 3 | Never invoked automatically (Key Decision: no auto-switch). Just printed. |

**Resolution policy** (in `external.py`):

```python
def resolve(binary: str, *, hint_pkg: str | None = None) -> Path | MissingBinary:
    p = shutil.which(binary)
    return Path(p) if p else MissingBinary(binary, hint=hint_pkg)
```

Never hard-code paths. Always `shutil.which`. Always provide a per-binary install hint. Never call a missing binary; **detect at the start of the relevant generator** and short-circuit cleanly.

**One special rule for `xcursorgen`:** because cursor conversion is multi-step (XBM → PNG with PIL → write xcursorgen `.in` config → run xcursorgen), check the binary *first* before doing any image conversion work. Failing fast saves a few hundred ms and avoids leaving stray PNGs in tmpdir.

---

## 11. Testing Strategy

**Layout:** `tests/unit/` mirrors `src/themey/`; `tests/integration/` exercises the pipeline end-to-end.

**Two fixtures, one philosophy:**

1. `tiny.etheme` — hand-crafted ~5 KB synthetic theme. Has *exactly one* of each construct: one border, two buttons (one each side), one iclass with a 9-patch, one tclass, one cursor, one background. Runs in < 50 ms. Used by all unit tests.
2. `Aliens.etheme` — real-world theme from `/home/cstory/src/wilbs/ethemes/e16/` (copied into `tests/fixtures/`). Used by integration tests as a fidelity check. If a change breaks Aliens, that's the canary.

**Snapshot tests live with their generator** — `tests/unit/test_generate_aurorae.py` checks generated SVG/INI/desktop bytes against `tests/snapshots/aurorae/tiny/`. The single test method is parameterized over fixtures; updates via `--snapshot-update`.

**Avoiding pollution of `~/.local/share/`:**

The clean answer is a `fake_home` fixture using `tmp_path` + monkeypatching `paths.py`:

```python
# tests/conftest.py
@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".local/share").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / ".local/share"))
    return home
```

This is preferable to `pyfakefs` for this project because:
- Pillow opens real image files. `pyfakefs` requires extra config to play nicely with C extensions and image I/O.
- `tarfile` and `gzip` operate on real files in the fixture path; we *want* those to be real.
- Subprocess calls (xcursorgen) need real files to operate on. Faking the FS would break that test surface.
- `tmp_path` is built into pytest, requires no extra dependency.

Use `pyfakefs` only if a future test specifically needs to simulate disk-full / permission-denied scenarios — and isolate that to one test file.

([tmp_path docs](https://docs.pytest.org/en/stable/how-to/tmp_path.html)) ([pyfakefs comparison](https://woteq.com/how-to-test-file-system-operations-with-tmp_path-in-python-using-pytest/))

---

## 12. Anti-Patterns

### Anti-Pattern 1: Letting generators reach back into the AST

**What people do:** "The Aurorae generator needs the raw `__EDGE_SCALING` numbers — let it import `etheme.ast`."

**Why it's wrong:** Couples output format to input format. Now changing the parser breaks Aurorae output. Now Aurorae generator can't be unit-tested without spinning up the parser. The IR boundary is the whole point.

**Do this instead:** If a generator needs a value, make sure analysis puts it in the IR. If you're tempted, the IR has a hole. Fix the hole.

### Anti-Pattern 2: Generators that side-effect into `~/.local/share/` directly

**What people do:** `aurorae.write_to_user_dir(theme)` — generator computes the install path itself.

**Why it's wrong:** Untestable without `pyfakefs` or polluting the dev's actual KDE config. Mixes "produce bytes" with "place bytes."

**Do this instead:** Generators take a `out_dir: Path` parameter and write only there. `install.py` is the only module that knows about `~/.local/share/`. Tests pass `tmp_path` and never come near real install paths.

### Anti-Pattern 3: A `Context` god-object passed through every stage

**What people do:** `class ConvertContext` with archive, AST, theme, options, paths, logger, notes... mutated by every stage.

**Why it's wrong:** Hides dependencies. Makes refactoring "what does this stage actually need?" impossible. Inverts the benefit of having stages.

**Do this instead:** Each stage takes the minimum it needs and returns the next type. `Theme.notes` is the *only* mutable accumulator and even that is appended via a small helper, not promiscuous mutation.

### Anti-Pattern 4: Catching every exception to "make conversion robust"

**What people do:** `try: convert(theme); except Exception: continue` in the batch loop.

**Why it's wrong:** Silently skipping failures means the user trusts a green run that converted 30/100 themes. Real bugs hide.

**Do this instead:** Catch only domain-specific exceptions (`MalformedThemeError`, `MissingAssetError`, `ExternalToolError`). Let `KeyboardInterrupt`, `OSError`, etc. propagate. Per-theme failures in batch mode go to a tally on stdout: `aliens.etheme  OK   |   broken.etheme  FAIL: missing __TBL section`.

### Anti-Pattern 5: Premature parallelism

**What people do:** Reach for `multiprocessing` because there are five generators.

**Why it's wrong:** The five generators take milliseconds each. Process startup overhead exceeds the work.

**Do this instead:** Serial by default. If `--all` over 100+ themes ever feels slow, parallelize at the theme boundary (each theme is independent). Don't parallelize within a theme.

---

## 13. Scaling Considerations

| Scale | Adjustment |
|-------|-----------|
| 1 theme | Serial pipeline, sub-second wall time. Default. |
| 10 themes (`--all`) | Serial loop, < 30s. No change. |
| 100+ themes | Add `multiprocessing.Pool(N=cpu_count)` at the **theme** level in `cli.py`. |
| 1000+ themes | Out of scope (chris has ~100; this is a personal tool). |

The first bottleneck under batch load will be **Pillow image decode** (every theme reloads a few PNGs). If anyone ever cares: add an LRU cache on `Image.open` keyed by `(path, mtime)` in `images/__init__.py`. Don't do it now.

The second bottleneck would be **xcursorgen subprocess spawn** at ~50 ms each. Mitigation: do all image prep first, then batch xcursorgen invocations. Don't do this now either.

---

## 14. Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| `xcursorgen` | `subprocess.run` via `external.py` | Required only for cursor generation (Phase 3). Skip cleanly if missing. |
| `lookandfeeltool` | Never invoked; printed in CLI hint only | Avoids accidental theme switch mid-conversion (Key Decision in PROJECT.md). |
| `xdg-open` / `firefox` | Optional; only when `--preview` requested | Print path if both missing. |
| Pillow (PIL) | Library import; not subprocess | Pin version in pyproject for reproducible PNG output. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `etheme/` ↔ `analyze/` | Import (analyze imports etheme.ast) | One-way; etheme/ is unaware of IR. |
| `analyze/` ↔ `generate/` | Via `Theme` IR only | The critical seam. Tested by snapshot. |
| `generate/` ↔ `install.py` | Generators return list of (src_dir, install_subdir) | Generators never know the final HOME. |
| `*` ↔ `external.py` | Tagged-union return values | No raised `subprocess.CalledProcessError` ever escapes. |
| `*` ↔ `paths.py` | Via env-aware helpers | `XDG_DATA_HOME` honored; tests can override. |

---

## Sources

- [PROJECT.md](file:///home/cstory/src/themey/.planning/PROJECT.md) — authoritative on E16 grammar shape, output paths, and Key Decisions.
- [Lark parser documentation](https://lark-parser.readthedocs.io/) — confirmed Earley/LALR (not RD); confirmed it's overkill for this grammar size.
- [pytest tmp_path docs](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — fixture used for `fake_home`.
- [pyfakefs comparison article](https://woteq.com/how-to-test-file-system-operations-with-tmp_path-in-python-using-pytest/) — supports the recommendation to prefer `tmp_path` for this project.
- [KDE develop.kde.org/docs/plasma/aurorae/](https://develop.kde.org/docs/plasma/aurorae/) — Aurorae FrameSvg hint frame and decoration.svg structure (cited in PROJECT.md Context).

---
*Architecture research for: Python CLI pipeline (E16 → KDE Plasma 6 theme conversion)*
*Researched: 2026-05-01*
