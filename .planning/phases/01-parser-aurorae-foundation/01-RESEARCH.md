# Phase 1: Parser + Aurorae Foundation - Research

**Researched:** 2026-05-01
**Domain:** E16 `.etheme` archive parsing + KDE Plasma 6 Aurorae window decoration generation
**Confidence:** HIGH

## Summary

Phase 1 is a single high-risk vertical slice: ingest one `.etheme` archive through a hand-rolled E16 grammar parser, build a frozen `Theme` IR, and emit an installable Aurorae window decoration plus an HTML preview. The success criterion is a real Aurorae frame appearing on Plasma 6.6.4 when the user converts `Aliens.etheme`.

The stack is locked by CLAUDE.md (Pillow 12.2 + Typer 0.25 + uv 0.11 + stdlib `xml.etree` + stdlib `configparser.RawConfigParser` + pytest 9.0 + syrupy 5.1 + ruff 0.15 + pyright basic). This research does NOT re-litigate stack choices; it is prescriptive on **format constraints, algorithms, and verification gates** the planner needs to author tasks.

The phase concentrates 9 of 12 critical pitfalls catalogued in `research/PITFALLS.md`. Three of them are now closed-by-correction in PROJECT.md (`__EDGE_SCALING` order, `plasma-apply-lookandfeel` naming, Look-and-Feel manifest format) but the remaining six are live risks that this research surfaces with concrete mitigations: tar safe-extract (CVE-2025-4330), the 18-ID FrameSvg contract, base64-embedded raster with `preserveAspectRatio="none"`, the three-tier `__ACLASS`-first button binning cascade, the lossy 8→2 image-state collapse, and the negative-pixel-offset coordinate evaluator.

**Primary recommendation:** Build five small files in this order — `archive.py` (safe_extract), `lex.py`+`parse.py` (recursive descent), `ir.py` (frozen Theme dataclass), `analyze/borders.py`+`analyze/buttons.py` (interpretation, including `__ACLASS` cascade), and `generate/aurorae.py` (the headline output). Validate Aurorae output by re-parsing the generated `decoration.svg` and asserting the 18 required FrameSvg IDs are present. The Aliens.etheme canary is verified to ship `__ACLASS` on every part, so the `__ACLASS`-first cascade succeeds on it without falling back to spatial binning.

<user_constraints>
## User Constraints (from CLAUDE.md)

> **Note:** Phase 1 has no `CONTEXT.md` (no `/gsd-discuss-phase` was run). The locked decisions below are extracted verbatim from `CLAUDE.md` and the `Key Decisions` table in `PROJECT.md`. The planner should treat these with the same authority as a CONTEXT.md.

### Locked Decisions (from CLAUDE.md TL;DR + PROJECT.md Key Decisions)

**Stack:**
- **Python 3.11+** (3.12 sweet spot). Note: developer machine has Python 3.14.4 — fine, target language baseline is 3.11.
- **Pillow 12.2.0** for all raster work (open PNG/XBM, slice 9-patch, resize, sample colors). Built-in `XbmImagePlugin` covers cursor input. (Developer machine has Pillow 12.1.1 currently — `uv sync` installs 12.2 from the lockfile.)
- **Typer 0.25.1** for CLI. Type-hint-driven; built on Click 8.3.
- **uv 0.11.8** for package + project + Python toolchain (developer machine has 0.11.7 — fine).
- **stdlib `xml.etree.ElementTree`** for SVG generation. Must `register_namespace("", "http://www.w3.org/2000/svg")` to avoid `ns0:` prefix mangling.
- **stdlib `configparser.RawConfigParser`** with `optionxform = str` and `space_around_delimiters=False` for Aurorae `<name>rc`. KDE keys are case-sensitive.
- **Hand-rolled `.desktop` writer** (NOT configparser) — localization keys like `Name[de]=Foo` confuse configparser's section regex.
- **Hand-rolled 9-patch slice + recursive-descent parser** (no Lark, no `ninepatch` PyPI package, no svgwrite, no drawsvg).
- **pytest 9.0.3 + syrupy 5.1.0** for testing; snapshot tests for byte-stable text outputs (SVG, INI, .desktop).
- **Ruff 0.15.12 + pyright 1.1.409 (basic mode)** for lint/format/type.
- **Hatchling** build backend (uv default).

**Architecture (from PROJECT.md Key Decisions):**
- **Target Aurorae over Plasma Style** for borders (FrameSvg + button grouping is a near-direct mapping).
- **From-scratch Python parser** for E16 grammar (no E16 runtime dependency).
- **Embed source PNG inside SVG** with FrameSvg hint frames — no rasterize-to-vector step.
- **Custom `safe_extract` for tar archives** in Phase 1 (mandatory; CVE-2025-4330 bypasses Python 3.12+ `filter="data"`).
- **Default action after convert: install + open HTML preview + print activation command** — no auto-switch.
- **Default `--scale=2`** of border/title sizes; override via `--scale=1` or `--scale=3`.

**Output paths (locked, all under `~/.local/share/...`):**
- Aurorae window decoration: `~/.local/share/aurorae/themes/<name>/`
- HTML preview: `~/.local/share/themey/previews/<name>.html`
- (Phase 2+ paths not in scope for this phase.)

### Claude's Discretion

These were not pre-decided and are areas where the planner can choose:

- **Project scaffold layout details** (test directory structure, exact module split inside `analyze/`, conftest fixture names) — recommended layout in `## Architecture Patterns` section below; planner may diverge if there's a reason.
- **Whether `metadata.json` is emitted alongside `metadata.desktop`** for the Aurorae sub-package. Research recommends emitting **both** in Phase 1 (Edna ships both; future-proofs against KF6 deprecation; marginal extra code).
- **HTML preview styling** — minimal CSS, mocked titlebar shape, color of activation-command code block. Just needs to render in Firefox/Chromium.
- **Reference window width for spatial-fallback button binning** — research recommends `REFERENCE_WINDOW_WIDTH = 800` constant in `analyze/buttons.py` (Aliens default border binned correctly at this width per SUMMARY.md Open Question 6). The cascade prefers `__ACLASS` → `__ICLASS` name; spatial fallback only matters for older themes without `__ACLASS`.
- **Whether to emit maximized variants** (`decoration-maximized-*` IDs) in Phase 1 — research recommends **do not emit** in Phase 1 (Edna ships without them and works; revisit only if a specific theme demands it).
- **Verbosity level mapping** for `-v` / `-vv` / `-q` — research suggests `-q`=`WARNING`, default=`INFO`, `-v`=`DEBUG`, `-vv`=`DEBUG` with parser-level trace; planner picks final mapping.

### Deferred Ideas (OUT OF SCOPE for Phase 1)

These are explicitly NOT in Phase 1, even though work on them might seem related:

- **COLORS-01 / WALLPAPER-01** — Phase 2. Phase 1 may sample a single titlebar foreground color into the rc's `ActiveTextColor`/`InactiveTextColor` (that's part of AURORAE-01) but does NOT emit a `.colors` file or a wallpaper package.
- **CURSORS-01** — Phase 3. Phase 1 does NOT call `xcursorgen`, does NOT touch XBM cursor data. (`cursors.cfg` may be parsed if it falls out of the grammar walk; cursor data is just stored as `Theme.cursors` for Phase 3.)
- **BUNDLE-01 / BUNDLE-02 / INSTALL-02 / INSTALL-03** — Phase 4. No `look-and-feel/` package, no install manifest JSON, no `--uninstall`, no `--all` batch mode. Phase 1 is single-theme only.
- **Filename-pattern fallback discovery (PARSE-05)** — required by phase scope but ONLY for the path "cfg parsing yielded incomplete results". On Aliens.etheme this fallback never fires because cfg parsing succeeds. Phase 1 implements the hook; full coverage of malformed-cfg corpus themes is exercised in later phases.
- **ActionClass standalone-block parsing** (`__ACLASS __BGN ... __END` blocks separate from `__BORDER_PART`) — out of scope. Phase 1 captures the **inline** `__ACLASS NAME` field on each `__BORDER_PART`. Standalone aclass blocks (Tier 2 in wilbs's gap-matrix) are a future fidelity item that Aurorae cannot honor anyway.
- **Multiple borders per theme** — DEFAULT only. Other border types (BORDERLESS, FIXED_SIZE, DIALOG, MENU, ATTENTION) are noted in `report.txt` as SKIPPED.
- **Non-rectangular borders** (`__CHANGES_SHAPE __ON`) — render rectangular bounding frame, log SKIPPED.
- **TTF font bundling** — Aurorae cannot override the title font. Don't ship `.ttf` files in the package; map XLFD family token to a generic and log to `report.txt`.
- **`__COLOR_MODIFIER` blocks** — captured into `Theme.notes` as informational, not applied (Aurorae has no tinting facility).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PARSE-01 | Read `.etheme` (gzipped tar) and walk E16's `__BLOCK __BGN ... __END` grammar including `#include` directives, `/* */` C-comments, and `#`-comments | `## Standard Stack` (stdlib `tarfile`+`gzip`); `## Architecture Patterns` Pattern 2 (recursive descent ~150 lines); `## Code Examples` "E16 grammar sketch" |
| PARSE-02 | Extract canonical structure: borders (with `__ACLASS` per part, `null` sentinel), image classes (`__EDGE_SCALING L R T B`), text classes (with E16's `__FORGROUND_COLOR` typo + tolerant fallbacks), button parts, `__BACKGROUND` blocks (`__BG_SOLID` / `__BG_BG`), `__COLOR_MODIFIER` (captured but not applied), cursors | `## Code Examples` "Aliens.etheme structure"; `## Common Pitfalls` Pitfall 1 (EDGE_SCALING order is L R T B); WILBS-REFERENCE.md `__ACLASS` rule |
| PARSE-03 | Custom `safe_extract` validates every tar member; rejects path-traversal, symlink-escape, hardlinks, absolute paths; caps **32 MB total / 8 MB per file / 500 entries**; identifies theme root by scanning for `borders.cfg` or `init.cfg` (shortest path wins) | `## Common Pitfalls` Pitfall 11; `## Code Examples` "safe_extract algorithm"; WILBS-REFERENCE.md production caps |
| PARSE-04 | Coordinate evaluator handles E16's hybrid `(window_dim × pct/1024) + absolute` model, including intentional negative absolute offsets | `## Common Pitfalls` Pitfall 2; `## Code Examples` "coordinate evaluator" — verified against Aliens default.cfg `__BOTTOMRIGHT_X_PERCENTAGE 1024` + `__BOTTOMRIGHT_X_ABSOLUTE -27` |
| PARSE-05 | Filename-pattern fallback discovery when cfg parsing yields incomplete results | `## Don't Hand-Roll` (use wilbs's pattern list); not exercised by Aliens (cfg parses cleanly) but hook must exist |
| AURORAE-01 | Generate Aurorae window decoration with all **18 required FrameSvg element IDs** in `decoration.svg`, per-button SVGs, `<name>rc` INI with `[General]` and `[Layout]`, both `metadata.desktop` AND `metadata.json` | `## Common Pitfalls` Pitfall 5 (18-ID contract); `## Code Examples` "decoration.svg skeleton" + "Aurorae rc skeleton" + Edna metadata.json template |
| AURORAE-02 | Three-tier button-binning cascade: `__ACLASS`-first, then `__ICLASS` name pattern, then spatial center-of-mass against **titlebar midpoint** | `## Common Pitfalls` Pitfall 4; `## Code Examples` "button binning cascade"; WILBS-REFERENCE.md aclass mapping table |
| AURORAE-03 | 9-patch raster borders preserved by embedding source PNG as **base64-encoded** inline `<image>` with `preserveAspectRatio="none"` and FrameSvg hint frames driven by `__EDGE_SCALING` | `## Common Pitfalls` Pitfall 6; `## Code Examples` "embedded raster pattern" |
| AURORAE-04 | E16's 8-field practical image-state model collapses to Aurorae's 2-state model via explicit `E16_TO_AURORAE_STATE` mapping; sticky variants drop with logged note | `## Common Pitfalls` Pitfall 3; `## Code Examples` "state collapse mapping" |
| CLI-01 | Single-theme form `themey <theme.etheme>` (Phase 1 ships single only; batch is Phase 4) | `## Code Examples` "Typer entry point" |
| CLI-02 | `--scale=N` flag (default 2, accepts 1/2/3) controls uniform border + image upscale | `## Architecture Patterns` Image Pipeline §8; upscale **before** slicing with `Image.Resampling.NEAREST` |
| CLI-03 | Verbosity flags `-v` / `-vv` / `-q`; idempotent re-runs (cleanly overwrite previous install) | `## Code Examples` "atomic install" — `os.replace` after staging to tmpdir |
| INSTALL-01 | Atomic install: stage to tmpdir, then `os.replace` each top-level output dir | `## Code Examples` "atomic install" |
| PREVIEW-01 | After conversion, write `~/.local/share/themey/previews/<name>.html` with mocked titlebar, list of dropped E16 states, and the activation command; auto-open via `xdg-open` unless headless / SSH / batch | `## Code Examples` "preview HTML"; `## Common Pitfalls` Pitfall 12 (SSH detection) |
| REPORT-01 | Per-theme `report.txt` with three sections — Preserved / Approximated / Skipped (Phase 1 ships scaffolding; Phase 2 fills full semantics) | `## Code Examples` "report.txt skeleton" |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|--------------|----------------|-----------|
| Read `.etheme` archive | Local Filesystem (tarfile) | — | Single-process CLI; no daemon, no service. |
| Validate tar members (safe_extract) | Local Filesystem | — | Security boundary at extraction; nothing else trusts archive contents. |
| Parse E16 cfg grammar | In-Process (Python) | — | Pure CPU; recursive-descent over text. |
| Resolve `#include <path>` | In-Process (file lookup in extracted tree) | Local Filesystem (read-only) | Includes resolve relative to theme root inside the extracted tmpdir. |
| Build `Theme` IR | In-Process (frozen dataclass) | — | Single contract crossing analyze/generate seam. |
| 9-patch image upscale | In-Process (Pillow) | — | All raster work in one library. |
| Emit `decoration.svg` | In-Process (xml.etree) | — | Output bytes; no DOM, no renderer. |
| Emit `<name>rc` INI | In-Process (configparser.RawConfigParser) | — | INI is a stdlib problem. |
| Emit `metadata.desktop` | In-Process (hand-rolled writer) | — | configparser misparses localization keys. |
| Emit `metadata.json` | In-Process (json.dumps) | — | Trivial. |
| Atomic install | Local Filesystem (os.replace) | — | tempfile.TemporaryDirectory + atomic rename. |
| Render HTML preview | In-Process (string formatting / f-strings) | Browser (xdg-open) | Output is a static file; browser opens it. |
| Auto-open preview | OS shell (xdg-open subprocess) | — | Best-effort; print path on failure. |

**Verified tier correctness:** All Phase 1 work happens on the local filesystem in a single process. Aurorae output is interpreted by KWin's Aurorae plugin at theme-application time (a separate process owned by the Plasma session) — themey just writes bytes; KWin reads them. There is no client-server split, no IPC during conversion, no network.

## Standard Stack

> All versions verified against PyPI on 2026-05-01 (research date). Lockfile (`uv.lock`) pins these.

### Core (Phase 1 actually uses)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11+ | Runtime | `[VERIFIED: developer machine has 3.14.4]`. Project targets 3.11 baseline (CLAUDE.md). |
| Pillow | 12.2.0 | Open PNG, NEAREST upscale, base64-encode PNG bytes | `[VERIFIED: pypi.org/pillow uploaded 2026-04-01]` Built-in XBM/PNG support; no native deps beyond bundled libjpeg/zlib. |
| Typer | 0.25.1 | CLI | `[VERIFIED: pypi.org/typer uploaded 2026-04-30]` Type-hint-driven; built on Click 8.3. |
| stdlib `tarfile` + `gzip` | bundled | Read `.etheme` | `[CITED: docs.python.org/3/library/tarfile]` Battle-tested; reads gzipped tars natively. |
| stdlib `xml.etree.ElementTree` | bundled | Emit `decoration.svg`, button SVGs | `[CITED: docs.python.org/3/library/xml.etree]` Sufficient for FrameSvg's "set this exact ID" contract. Must `register_namespace("", svg_ns)` to avoid `ns0:` prefix. |
| stdlib `configparser.RawConfigParser` | bundled | Emit `<name>rc` | `[CITED: docs.python.org/3/library/configparser]` `optionxform=str` preserves KDE's case-sensitive keys; `RawConfigParser` skips `%`-interpolation. |
| stdlib `tempfile` | bundled | Stage extraction + install to tmpdir | `[CITED: docs.python.org/3/library/tempfile]` `TemporaryDirectory()` context manager. |
| stdlib `base64` | bundled | Base64-encode embedded PNG bytes for SVG `<image>` | `[CITED: docs.python.org/3/library/base64]` `b64encode(png_bytes).decode("ascii")`. |
| stdlib `pathlib`, `dataclasses`, `shutil`, `os`, `json`, `html`, `subprocess` | bundled | Plumbing | All standard. |

### Supporting (dev-time only)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 | Test runner | `[VERIFIED: pypi 2026-04-07]` Always. |
| syrupy | 5.1.0 | Snapshot tests for SVG/INI/.desktop bytes | `[VERIFIED: pypi 2026-01-25]` Default Amber extension is diff-friendly in `git diff`. |
| ruff | 0.15.12 | Lint + format | `[VERIFIED: pypi 2026-04-24]` `select = ["E","W","F","I","B","C4","UP","RUF"]`. |
| pyright | 1.1.409 | Type check (basic mode) | `[VERIFIED: pypi 2026-04-23]` `typeCheckingMode = "basic"` in `pyproject.toml`. |
| hatchling | (uv default) | PEP 517 build backend | `uv init --package` defaults to it. |

### Alternatives Considered (already ruled out by CLAUDE.md / SUMMARY.md)
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled recursive descent | Lark / Parsimonious | Adds a dep for a 7-production grammar; `#include` resolution needs custom hooks anyway; Lark is Earley/LALR not RD. **Rejected.** |
| stdlib `xml.etree` | lxml 6.1.0 / drawsvg / svgwrite | lxml is faster but ~5 MB compiled C dep; drawsvg is a drawing DSL that fights "set this exact ID"; svgwrite is **maintainer-declared inactive since July 2022**. **Rejected.** |
| Hand-rolled 9-patch slice | PyPI `ninepatch` | Targets Android `.9.png` metadata-encoded slice points; we have explicit slice values from `__EDGE_SCALING`. **Rejected.** |
| Pillow base | colorthief / colorgram.py | Both unmaintained (2017–2018). **Rejected** (not used in Phase 1 anyway; colors are Phase 2). |
| `subprocess` to `xcursorgen` | clickgen (PyPI) / win2xcur | clickgen has no recent release (Jun 2024); win2xcur is wrong direction. **Rejected** (not used in Phase 1 anyway; cursors are Phase 3). |
| Typer | Click / argparse | Click is equally good but more boilerplate; argparse would save the dep but ~100 more lines for `themey <theme.etheme>` + `--scale`. **Typer wins on code-per-feature.** |

**Installation (one-time bootstrap):**
```bash
uv init --package --build-backend hatchling themey
cd themey
uv add pillow typer
uv add --group dev pytest syrupy ruff pyright
uv sync
uv run themey --help
```

**Version verification commands** (planner should run these at task start to confirm versions are still current):
```bash
uv run python -c "import PIL; print('Pillow:', PIL.__version__)"  # expect 12.2.x
uv run python -c "import typer; print('Typer:', typer.__version__)"  # expect 0.25.x
uvx pytest --version  # expect 9.0.x
```

## Architecture Patterns

### System Architecture Diagram

```
   .etheme path  ──>  archive.py  ──>  extracted tmpdir
                       (safe_extract:                   __  rejects ../ + symlinks
                        validate every                    + caps 32MB / 8MB / 500
                        tar member)                       + resolves theme root marker

                                       │
                                       ▼  (assets + .cfg files in tmp tree)

                        lex.py  ──>  parse.py  ──>  ast.py
                        (tokens)     (recursive    (Block / KeyVal / Include nodes)
                                      descent;
                                      resolves
                                      #include)
                                       │
                                       ▼  list[Block]

                        analyze/borders.py     ──┐
                        analyze/buttons.py     ──┤── ir.Theme  (frozen dataclass;
                        (button cascade,         │    SINGLE seam between halves;
                         state collapse,         │    notes: list[str] is the
                         titlebar midpoint)      │    only mutable accumulator)
                                       │        │
                                       ▼        │
                                                │
                        images/upscale.py    ──┘   (NEAREST upscale of border PNGs;
                                                    base64-encode PNG bytes)
                                       │
                                       ▼  Theme

                        generate/aurorae.py
                        (decoration.svg with 18 IDs +
                         per-button SVGs +
                         <name>rc INI +
                         metadata.desktop +
                         metadata.json)
                                       │
                                       ▼  out_dir: list[Path]

                        install.py  (stage to tmpdir → os.replace
                                      ~/.local/share/aurorae/themes/<name>/)
                                       │
                                       ▼

                        report.py    ──>  ~/.local/share/themey/previews/<name>.report.txt
                        preview.py   ──>  ~/.local/share/themey/previews/<name>.html
                                          ▼
                                       external.py
                                       (xdg-open <html>; suppressed if SSH/headless)
                                          ▼
                                       browser
```

The arrows trace the primary use case (`themey Aliens.etheme` → installed Aurorae theme + opened preview) from input to output. The `Theme` IR is the only thing that crosses the analyze/generate seam — generators never re-read the archive or AST.

### Recommended Project Structure

```
src/themey/
├── __init__.py
├── __main__.py           # python -m themey entrypoint (calls cli.app)
├── cli.py                # Typer dispatch, exit codes, --scale, -v/-vv/-q
│
├── etheme/               # E16 INPUT side (mirror-image of generate/)
│   ├── __init__.py
│   ├── archive.py        # gzipped-tar extraction + safe_extract validator
│   ├── lex.py            # tokenizer: comments, strings, numbers, idents
│   ├── parse.py          # __BLOCK __BGN/__END recursive descent + #include
│   └── ast.py            # raw AST dataclasses (Block, KeyVal, Include)
│
├── ir.py                 # Canonical Theme dataclass (flat at root; pure data)
│
├── analyze/              # AST → Theme IR (interpretation, lossy decisions)
│   ├── __init__.py
│   ├── borders.py        # __BORDER + __ICLASS + __EDGE_SCALING → BorderSpec
│   ├── buttons.py        # 3-tier cascade: __ACLASS → __ICLASS → spatial
│   ├── states.py         # E16_TO_AURORAE_STATE collapse mapping
│   └── coords.py         # (window_dim × pct/1024) + absolute resolver
│
├── images/               # Pure Pillow primitives (zero E16/KDE knowledge)
│   ├── __init__.py
│   ├── upscale.py        # NEAREST upscale for borders
│   └── embed.py          # base64-encode PNG bytes for SVG <image>
│
├── generate/             # OUTPUT side (mirror of etheme/)
│   ├── __init__.py
│   ├── aurorae.py        # decoration.svg + button SVGs + <name>rc + metadata
│   └── desktop_writer.py # hand-rolled .desktop INI writer (NOT configparser)
│
├── install.py            # Stage to tmpdir, os.replace into ~/.local/share/...
├── preview.py            # HTML preview generator
├── report.py             # report.txt (Phase 1 scaffold only)
├── external.py           # subprocess wrapper for xdg-open
├── paths.py              # XDG_DATA_HOME-aware install paths
└── log.py                # stdlib logging facade

tests/
├── conftest.py           # fake_home (tmp_path + monkeypatched HOME/XDG_DATA_HOME)
├── fixtures/
│   ├── tiny.etheme       # ~5 KB hand-crafted: one border, two buttons, one iclass
│   └── Aliens.etheme     # real-world canary (copy from ~/src/wilbs/ethemes/e16/)
├── unit/
│   ├── test_archive.py   # safe_extract: ../, symlink-escape, oversize, oversize-count
│   ├── test_lex.py
│   ├── test_parse.py     # grammar including #include, /* */, #-comments
│   ├── test_coords.py    # negative absolute, fixed-point 1024
│   ├── test_buttons.py   # __ACLASS cascade, titlebar midpoint, spatial fallback
│   ├── test_states.py    # E16→Aurorae collapse + drop logging
│   └── test_generate_aurorae.py  # syrupy snapshots of decoration.svg + rc
├── integration/
│   ├── test_pipeline.py  # tiny.etheme → installed tree
│   └── test_aliens.py    # Aliens.etheme end-to-end (canary)
└── snapshots/            # syrupy .ambr files
```

### Pattern 1: Hand-rolled recursive-descent parser
**What:** A small lexer plus recursive-descent parser. Grammar in BNF below.
**When to use:** This grammar — small (~7 productions), stable (E16 hasn't changed in years), zero runtime deps wanted.
**Grammar (sketch):**
```
file        := (toplevel)*
toplevel    := include | block | top_kv
include     := '#include' ('<' path '>' | '"' path '"') NEWLINE
block       := keyword '__BGN' (statement)* '__END'
statement   := keyword (value)+ NEWLINE | block
keyword     := IDENT (uppercase, may start with __)
value       := IDENT | INTEGER | STRING | PATH | NEGATIVE_INTEGER
comment     := '/*' ... '*/' | '#' ... NEWLINE   (skipped by lexer)
top_kv      := '__E_CFG_VERSION' INTEGER NEWLINE   (special — single-line top-level)
```

`#include` paths are resolved relative to the theme root identified at extraction time (the directory containing `borders.cfg` or `init.cfg`, whichever appears at the shortest path in the archive).

**The `#include <definitions>` problem:** Every Aliens cfg starts with `#include <definitions>`. There is no `definitions` file in `.etheme` archives — it's a reference to E16's built-in `/usr/share/e16/config/definitions` macro file containing C-preprocessor macros (`BEGIN_BACKGROUND` → `__DESKTOP __BGN`, `ADD_BACKGROUND_SCALED` → `__BACKGROUND_LAYER ...`, etc.) `[VERIFIED: /home/cstory/Downloads/e16-1.0.31/config/definitions:927]`. The Phase 1 parser MUST silently skip `#include <definitions>` (treat as no-op) and MUST NOT crash on unknown keywords like `__DESKTOP`, `__BACKGROUND_LAYER`, `__SOLID_COLOR`, `__USE_ON_DESKTOP` — these come from the legacy macro form in `desktops.cfg` which Phase 1 does not need to interpret. The parser is a generic block-extractor that recognizes `__BGN`/`__END` structure and records all key-values; the analyze layer picks the relevant blocks. **Unknown blocks/keys are recorded, not rejected.**

**Trade-offs vs alternatives:** See `## Standard Stack` table — Lark/Parsimonious rejected for this size; regex split is fragile (`/* ... */` crosses lines, blocks nest); configparser is the wrong format entirely.

### Pattern 2: Functional pipeline with frozen IR
**What:** Each stage is a pure function `In -> Out`. State flows forward via dataclasses; no shared mutable context object.
**When to use:** "Transform A into B" with clear stages — exactly this project.
**Example:**
```python
# cli.py — the whole pipeline in one block
def convert(etheme_path: Path, scale: int = 2, verbosity: int = 0) -> ConvertResult:
    with archive.extract(etheme_path) as raw:        # tmpdir; auto-cleanup
        ast = parse.parse_tree(raw)                  # list[Block] from all .cfg
        theme = analyze.build_theme(raw, ast, scale=scale)
        out_tmp = make_tmp_out_dir(theme.name)
        artifacts = generate.aurorae(theme, out_tmp)
        installed = install.deploy(theme.name, out_tmp)
        report.write(theme, installed.report_path)
        html = preview.render(theme, installed.preview_path)
        external.open_preview_unless_headless(html)
        return ConvertResult(name=theme.name, html=html, notes=theme.notes)
```

The IR (`Theme`) is the only thing that crosses analyze→generate. `Theme.notes: list[str]` is the **only** mutable accumulator — fed by analyze, read by `report.py`. Don't let it become a generic event bus.

### Pattern 3: Snapshot testing for byte-stable outputs
**What:** Each generator's golden output (SVG/INI/.desktop bytes) is checked into `tests/snapshots/`. syrupy fails if output differs; `pytest --snapshot-update` regenerates after intentional change.
**When to use:** Any output that should be byte-stable. All Phase 1 outputs qualify (decoration.svg, button SVGs, rc INI, metadata files).
**Example:**
```python
# tests/unit/test_generate_aurorae.py
def test_aurorae_decoration_svg(snapshot, tiny_theme, tmp_path):
    paths = generate.aurorae.write(tiny_theme, tmp_path)
    decoration = (tmp_path / "decoration.svg").read_text()
    assert decoration == snapshot
```

### Pattern 4: Atomic install via stage-then-rename
**What:** Generators write to a fresh tmpdir. `install.py` calls `os.replace(tmp_dir, final_dir)` to swap atomically.
**When to use:** Always. Partial failures must leave the previous install untouched.
**Example:** see `## Code Examples` "Atomic install (INSTALL-01)".

### Anti-Patterns to Avoid

- **Generators that side-effect into `~/.local/share/...` directly** — generators take `out_dir: Path` and write only there. `install.py` is the only module that knows about user-home install paths. (Tests pass `tmp_path` and never come near real install paths.)
- **A `Context` god-object passed through every stage** — hides dependencies; defeats the point of pipeline stages. Each stage takes the minimum it needs.
- **Catching every exception to "make conversion robust"** — silent skipping hides real bugs. Catch only domain-specific exceptions (`MalformedThemeError`, `UnsafeArchiveError`, `MissingAssetError`); let `KeyboardInterrupt`/`OSError`/etc. propagate. (Phase 4 batch mode will need per-theme isolation but Phase 1 is single-theme — fail loudly.)
- **`tarfile.extractall(dest, filter="data")`** — even Python 3.12+ data-filter has CVE-2025-4330 bypass. Use the `safe_extract` algorithm in `## Code Examples`.
- **`configparser.ConfigParser` (default mode) for the `<name>rc`** — default `optionxform = str.lower` mangles `LeftButtons`, `BackgroundNormal`, etc. Use `RawConfigParser` with `optionxform = str`.
- **`configparser` for `metadata.desktop`** — localization keys like `Name[de]=Foo` look like sections. Hand-roll a 20-line writer.
- **`Image.Resampling.LANCZOS` for border upscaling** — blurs pixel-art borders. Use `NEAREST` for borders. (LANCZOS is reserved for wallpapers in Phase 2.)
- **`<image href="path/to/file.png">` in `decoration.svg`** — relative paths fail to resolve after install relocation. Use `<image href="data:image/png;base64,..." preserveAspectRatio="none">`.
- **Letting generators reach back into the AST** — the `Theme` IR is the only contract. If a generator needs a value, put it in the IR.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Read PNG/XBM | Custom decoders | Pillow `Image.open()` | Mature; PNG, XBM, JPEG, BMP all supported. XBM has hotspot info via `img.info["hotspot"]`. |
| Gzipped tar extract | Custom binary parser | stdlib `tarfile.open(path, "r:gz")` | Both gzip + tar in one call. (We DO hand-roll member validation — `safe_extract` — but stdlib does the heavy lifting.) |
| INI emit | Custom INI writer | `configparser.RawConfigParser` with `optionxform=str` | Stdlib handles edge cases (escaping, line continuation). Quirks documented in `## Code Examples`. |
| SVG emit | Hand-stitched strings | stdlib `xml.etree.ElementTree` | Stdlib gets escaping, namespaces, attribute order right. |
| Base64 encode | Custom | `base64.b64encode(bytes).decode("ascii")` | Stdlib. |
| CLI parsing | Custom argparse hand-rolling | Typer | ~100 lines saved over argparse for this CLI's surface. |
| Filename-pattern fallback (PARSE-05) | Reinvent the pattern list | Port wilbs's canonical names | `~/src/wilbs/src/lib/themes/e16/parse-e16-archive.ts` enumerates `border_top_default.png`, `border_topleft_default.png`, `button_close_active.png`, etc. — 16 years of seeing the corpus. |
| `__ACLASS` → Aurorae button code mapping | Reinvent | Use the WILBS-REFERENCE.md table | `ACTION_CLOSE → X`, `ACTION_MAX → A`, `ACTION_ICONIFY → I`, `ACTION_SHADE → L`, `ACTION_STICK → S`, `ACTION_KILL → X`, `ACTION_RESIZE/_H/_V → drop`, `ACTION_MOVE → drop`. |
| Aurorae rc `[Layout]` defaults | Reinvent | Lifted from Edna `Ednarc` (`/home/cstory/.local/share/aurorae/themes/Edna/Ednarc`) | Verified working values; `## Code Examples` shows them with comments on which scale uniformly. |

**Key insight:** Phase 1 has exactly one custom algorithm worth writing — the safe_extract validator. Everything else is composition of stdlib primitives + Pillow. Resist the urge to write a "small parser library" or a "FrameSvg helper class"; the work is small enough that a function per task is the right granularity.

## Common Pitfalls

> Drawn from `research/PITFALLS.md`. Each pitfall is verified against ground truth (E16 source, Edna theme, Aliens.etheme contents) and has a phase-1 prevention.

### Pitfall 1: `__EDGE_SCALING` order is `L R T B`
**What goes wrong:** Parsing `__EDGE_SCALING 3 2 32 5` as `(top, bottom, left, right)` swaps the stretch axes. The titlebar tile band lands in the wrong spot.
**Why it happens:** Order is undocumented in cfg files; established only by C parser. `[VERIFIED: /home/cstory/Downloads/e16-1.0.31/src/iclass.c]` does `sscanf("%i %i %i %i", &l, &r, &t, &b)` and the struct is `EImageBorder { left, right, top, bottom }` (`eimage.h`).
**How to avoid:** Hardcode `EDGE_SCALING_ORDER = ("left", "right", "top", "bottom")` as a module-level constant in `analyze/borders.py` with a comment citing `iclass.c`. Add a unit test: `parse("__EDGE_SCALING 1 2 3 4")` produces `{left:1, right:2, top:3, bottom:4}`.
**Warning signs:** Visual — titlebar tile clearly wider than tall has horizontal stretch axis after conversion. Aliens `imageclasses/borders.cfg` PAGER_TOP iclass has `__EDGE_SCALING 32 32 3 2` — should stretch only at the L/R 32-px margin region.

### Pitfall 2: 1024 is fixed-point, but pixel offsets can be negative
**What goes wrong:** Reading `__BOTTOMRIGHT_X_PERCENTAGE 1024` as 100% then dropping the `__BOTTOMRIGHT_X_ABSOLUTE -27` thinking it's a clamping error. Result: titlebar binds to right edge with no inset, gets clipped.
**Why it happens:** E16 layout math is `final_pixel = (window_dim × percentage / 1024) + absolute`. Negative `absolute` paired with `percentage=1024` is the standard way to express "27 px from right edge".
**How to avoid:** Treat `_PERCENTAGE` as a Q10-fixed-point ratio (`fraction = pct / 1024.0`); treat `_ABSOLUTE` as a signed pixel offset. **Never call `abs()` on a coordinate.** Keep this logic in `analyze/coords.py` so all border-coord and button-coord resolution flows through one function.
**Verified against Aliens:** `borders/default.cfg:64-72` has TITLE_BAR_HORIZONTAL with `__BOTTOMRIGHT_X_PERCENTAGE 1024` + `__BOTTOMRIGHT_X_ABSOLUTE -27`. At reference width 800, this resolves to `(800 × 1024/1024) + (-27) = 773` — i.e. 27 px from right edge.
**Phase to address:** Phase 1 (PARSE-04). Unit test asserts `coords.resolve(pct=1024, abs=-27, window_dim=800) == 773`.

### Pitfall 3: 8 E16 image-states collapse to 2 Aurorae states (lossy by design)
**What goes wrong:** Naive collapse picks `__NORMAL` for inactive and `__NORMAL_ACTIVE` for active and silently drops everything else. `__HILITED_ACTIVE` (focused-hovered) and `__CLICKED_ACTIVE` (focused-pressed) lose their button-feedback variants. Sticky variants disappear with no log entry.
**Why it happens:** E16 supports `{normal, hilited, clicked, disabled} × {norm, active, sticky, sticky_active}` (16 cells in C struct). Practical themes use 8 of these (per WILBS-REFERENCE.md). Aurorae has 2 (active, inactive) plus optional `*-hover` and `*-pressed` IDs **inside button SVGs**.
**How to avoid:** Define explicit mapping in `analyze/states.py`:
```python
E16_TO_AURORAE_STATE = {
    "decoration-active":   ["__NORMAL_ACTIVE", "__NORMAL"],   # fallback chain
    "decoration-inactive": ["__NORMAL"],                       # never use _ACTIVE for inactive
    # Per-button hover/pressed targets in button SVGs (not decoration.svg):
    "button-hover":        ["__HILITED_ACTIVE", "__HILITED"],
    "button-pressed":      ["__CLICKED_ACTIVE", "__CLICKED"],
    # Dropped (no Aurorae target):
    # __NORMAL_STICKY, __NORMAL_ACTIVE_STICKY, __CLICKED_STICKY, __CLICKED_ACTIVE_CLICKED
}
```
Every dropped state appends a string to `Theme.notes` like `"Aliens TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped (no Aurorae per-desktop button state)"`.
**Warning signs:** A theme whose unfocused window looks identical to focused (means fallback to `__NORMAL_ACTIVE` for both because `__NORMAL` was missing — but Aliens has both; verified in `imageclasses/borders.cfg:7-8`). `report.txt` listing zero dropped states means tracking is broken, not that there were no drops.
**Verified against Aliens:** TITLE_BAR_HORIZONTAL ICLASS has 8 fields (`__NORMAL`, `__CLICKED`, `__NORMAL_ACTIVE`, `__CLICKED_ACTIVE`, `__NORMAL_STICKY`, `__CLICKED_STICKY`, `__NORMAL_ACTIVE_STICKY`, `__NORMAL_ACTIVE_CLICKED`). Of these, 2 map to decoration states (`__NORMAL` → inactive, `__NORMAL_ACTIVE` → active); 0 are useful for hover/pressed (TITLE_BAR_HORIZONTAL is not a button); the other 6 are dropped with notes. Buttons (`BUTTON_ICONIFY`, `BUTTON_MAXIMIZE`, `BUTTON_KILL`) DO have `__NORMAL_ACTIVE` (hover) and `__CLICKED_ACTIVE` (pressed) feedback variants worth preserving in their button SVGs.

### Pitfall 4: Button binning needs **titlebar** midpoint, not window midpoint, AND `__ACLASS`-first
**What goes wrong:** Naive midpoint-of-window split puts left-cluster buttons on the wrong side. Worse: ignoring `__ACLASS` means relying on iclass name pattern matching, which mis-fires on buttons whose iclass name doesn't include "CLOSE"/"MAX"/etc. — exact bug shipped in wilbs and post-mortemed.
**Why it happens:** E16 buttons can be arbitrarily positioned; `__ACLASS` is the canonical action declaration; `__ICLASS` is just the visual.
**How to avoid:** Three-tier cascade in `analyze/buttons.py`:
1. **`__ACLASS` first.** If `part.aclass == "ACTION_CLOSE"` → button code `X`; `ACTION_MAX` → `A`; `ACTION_ICONIFY` → `I`; `ACTION_SHADE` → `L`; `ACTION_STICK` → `S`; `ACTION_KILL` → `X` (no force-quit equivalent in Aurorae). Skip resize/move actions (Aurorae handles natively).
2. **`__ICLASS` name pattern fallback.** If `part.aclass is None`, match `iclass.upper()` against patterns: `BUTTON_CLOSE` → `X`, `BUTTON_MAXIMIZE`/`BUTTON_MAX` → `A`, `BUTTON_ICONIFY`/`BUTTON_MINIMIZE` → `I`, `BUTTON_SHADE` → `L`, `BUTTON_STICK` → `S`, `BUTTON_KILL` → `X`.
3. **Spatial center-of-mass against titlebar midpoint** (last resort). Resolve each button's pixel range using `REFERENCE_WINDOW_WIDTH = 800`. Find the titlebar part (`flags` contains `__FLAG_TITLE` or `aclass == "ACTION_MOVE"` and large width). Bin by `[0, titlebar_min_x]` → Left, `[titlebar_max_x, window_w]` → Right. Buttons overlapping titlebar text region drop with a `report.txt` note.
4. Within each bin, sort by X coordinate ascending.

**Verified against Aliens:** `borders/default.cfg` ships `__ACLASS` on every part:
- BUTTON_ICONIFY (TL_X=140-152) — `ACTION_ICONIFY` → `I`
- BUTTON_MAXIMIZE (TL_X=118-138) — `ACTION_MAX` → `A`
- TITLE_BAR_HORIZONTAL (TL_X=153 to right−27) — `ACTION_MOVE` → drop (titlebar)
- BUTTONR / BUTTONL / BUTTONB / BUTTONT (resize edges) — `ACTION_RESIZE_*` → drop
- CORNER_TR / CORNER_BR / CORNER_BL — `ACTION_RESIZE` → drop
- CORNER_TL — `ACTION_MOVE` → drop
- BUTTON_KILL (TL_X=11-22) — `ACTION_KILL` → `X`

Result on Aliens: All three of Aliens' buttons (kill at x=11, maximize at x=118, iconify at x=140) sit at x < 153 (titlebar starts at 153). Spatially they're all "left of titlebar". Tier-1 ACLASS resolution gives codes `X, A, I`; spatial step (which we don't even reach) would put all three in `LeftButtons`. **Expected output: `LeftButtons="XAI"` (kill, max, iconify in spatial L→R order at x=11/118/140), `RightButtons=""`** — NOT `XIA` as someone might guess from convention. (Edna ships `LeftButtons=XIA` because Edna is a different theme; Aliens has its own spatial layout.)

### Pitfall 5: FrameSvg requires 18 exactly-named element IDs
**What goes wrong:** Generating a `decoration.svg` with elements named `top`, `topleft`, `center` (intuitive) instead of `decoration-top`, `decoration-topleft`, `decoration-center` (correct). KWin's FrameSvg renderer searches by literal `decoration-*` IDs and renders nothing visible. Or skipping the inactive set means unfocused windows render with hollow edges.
**Why it happens:** FrameSvg's contract is "an element with this ID exists at this bbox" — period.
**How to avoid:** Hardcode the required IDs and validate after generation:
```python
SIDES = ["topleft", "top", "topright", "left", "center", "right",
         "bottomleft", "bottom", "bottomright"]
REQUIRED_IDS = (
    [f"decoration-{s}" for s in SIDES] +
    [f"decoration-inactive-{s}" for s in SIDES]
)  # 18 IDs total

# After writing decoration.svg, parse and assert:
import xml.etree.ElementTree as ET
root = ET.parse(out_dir / "decoration.svg").getroot()
present = {e.get("id") for e in root.iter() if e.get("id")}
missing = set(REQUIRED_IDS) - present
assert not missing, f"FrameSvg IDs missing: {missing}"
```
Also include FrameSvg **hint margins** as 1×1 invisible rects with IDs `hint-{top,bottom,left,right}-margin` and `shadow-hint-{top,bottom,left,right}-margin` (sized in pixels) — verified present in Edna's decoration.svg `[VERIFIED: /home/cstory/.local/share/aurorae/themes/Edna/decoration.svg]` lines 985-1034. These tell FrameSvg the border thickness in each direction.
**Maximized variants:** Edna ships **without** `decoration-maximized-*` — verified in the ID list `[VERIFIED]`. Phase 1 omits maximized variants.

### Pitfall 6: Embedded raster needs `preserveAspectRatio="none"` AND base64 inline
**What goes wrong:** `<image href="artwork/n_title.png" />` — relative `href` fails to resolve after the SVG is installed to a different directory. Or the href is base64'd but `preserveAspectRatio` defaults to `xMidYMid meet` ("preserve aspect, fit inside, center"), so the titlebar tile centers in its band leaving transparent margins.
**Why it happens:** SVG default behavior + FrameSvg cannot follow filesystem-relative paths.
**How to avoid:** Two rules for every `<image>` in `decoration.svg`:
1. Inline as base64: `href="data:image/png;base64,<b64>"` (use `xlink:href` for SVG 1.1 compat; modern renderers accept both — emit `xlink:href` to match Edna).
2. Always emit `preserveAspectRatio="none"`.

```python
import base64
png_bytes = (asset_root / iclass.normal_image).read_bytes()
b64 = base64.b64encode(png_bytes).decode("ascii")
image = ET.SubElement(group, "image", {
    "{http://www.w3.org/1999/xlink}href": f"data:image/png;base64,{b64}",
    "x": "0", "y": "0",
    "width": str(scaled_width), "height": str(scaled_height),
    "preserveAspectRatio": "none",
})
```

### Pitfall 7 (deferred): XBM cursors are 1-bit + sibling `.mask` file
**Phase 1 status:** OUT OF SCOPE. Cursors are Phase 3. The parser reads `cursors.cfg` and stores `Theme.cursors` for later phases; nothing is rasterized or written.

### Pitfall 8: TTF fonts and color extraction
**What goes wrong:** Bundling `ttfonts/*.ttf` into the Aurorae package. Aurorae cannot override the title font — the TTFs sit unused. Worse: misreading XLFD font strings like `"-adobe-helvetica-medium-r-normal-..."` as parseable font names; they don't resolve on modern Linux without an X font server.
**How to avoid:**
- Don't bundle TTFs in the Aurorae output directory.
- Parse `textclasses.cfg`. Find `__TCLASS TEXT1` (the standard titlebar tclass referenced from `__BORDER_PART __TCLASS TEXT1`). Read its `__FORGROUND_COLOR R G B` (E16's typo; tolerate `__FOREGROUND_COLOR` and `__COLOR` as fallbacks).
- Map XLFD family token to fontconfig generic — but **don't write it anywhere** in Phase 1; the title font is system-controlled. Just log to `report.txt` "title font preserved as system default; E16 source declared `*font-default`".
- Write `__FORGROUND_COLOR` to the rc as `ActiveTextColor=R,G,B,255` and the inactive variant (or the same value if no `__NORMAL_ACTIVE` form). E16 grammar puts the focused color after `__NORMAL_ACTIVE` and unfocused after `__NORMAL`. Verified in Aliens `textclasses.cfg:75-87` — TEXT1 has both: focused `255,255,200` (after `__NORMAL_ACTIVE`) and unfocused `200,200,150` (after `__NORMAL`).

### Pitfall 9 (mostly deferred): Plasma 6 manifest format
**Phase 1 status:** Aurorae sub-package only. Emit BOTH `metadata.desktop` AND `metadata.json` for the Aurorae theme `[VERIFIED: Edna ships both]`. The outer Look-and-Feel `manifest.json` is Phase 4. Symlink prohibition applies in Phase 4 too — but `safe_extract` already resolves source-archive symlinks, so the input is symlink-free for both phases.

### Pitfall 10 (deferred): `plasma-apply-lookandfeel` argument format
**Phase 1 status:** Phase 1's preview shows the activation command for the Aurorae theme only — System Settings → Window Decorations is the activation path for a bare Aurorae theme, NOT `plasma-apply-lookandfeel` (which is Phase 4's Look-and-Feel bundle activation). Phase 1 preview should show: "Apply via System Settings → Window Decorations → '<name>'". Phase 4 will resolve the `plasma-apply-lookandfeel` command and update the preview text. **Local environment verified:** both `plasma-apply-lookandfeel` and `lookandfeeltool` are present at `/usr/bin/` `[VERIFIED: command -v]`.

### Pitfall 11: tarfile path traversal and symlink escape
**What goes wrong:** `tarfile.open(etheme).extractall(dest)` writes outside `dest` if archive contains `../../../.bashrc` or symlink `evil → /home/cstory/.ssh/`.
**Why it happens:** CVE-2007-4559 (15-year-old `extractall` bug); CVE-2025-4330 (PATH_MAX bypass on `filter="data"` even on Python 3.12+).
**How to avoid:** **`safe_extract` algorithm in `## Code Examples`.** Member-by-member validation. Reject path-traversal, absolute paths, symlinks (resolve targets at extract time, copy file content to the symlink's location as a regular file), hardlinks, FIFOs, device files, character devices, oversize files, oversize counts. Verified caps from wilbs production (`[VERIFIED: ~/src/wilbs/src/lib/themes/e16/parse-e16-archive.ts:13-19]`): 32 MB total / 8 MB per file / 500 entries.
**Verified against Aliens:** Aliens.etheme contains 3 symlinks (`fonts.cfg → fonts.theme.cfg`, `ABOUT/aircut3.ttf → ../ttfonts/aircut3.ttf`, `ABOUT/avgardm.ttf → ../ttfonts/avgardm.ttf`) `[VERIFIED: tar -tvzf]`. None escape the archive root, so `safe_extract` resolves them by reading the target file and writing its content to the symlink's path as a regular file. Phase 1 ships negative tests with malicious archives (`../etc/passwd`, `evil → /etc`, oversize file, 600 entries).

### Pitfall 12: Fractional-scaling pixelation
**What goes wrong:** At 1.25×/1.5×/1.75× display scale, embedded PNG content pixelates. `--scale=2` default helps because output PNG is 2× source resolution; pixel-perfect at 1.0×, 2.0×, 3.0×; approximate at fractional.
**How to avoid:** Default `--scale=2` (already in CLI-02). Add a note to `report.txt`: `"Embedded PNGs at 2× source resolution. Pixel-perfect on 1.0×/2.0×/3.0× display scales; approximate at 1.25×/1.5×/1.75×."`. If `decoration.svg` exceeds 2 MB after generation (depends on theme), warn in `report.txt` (FrameSvg cache misbehaviors reported on large embedded images).

## Runtime State Inventory

> Phase 1 is greenfield (new project, no existing installed state to migrate). No runtime state inventory needed — but the **install** step does have OS-registered state to consider:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — Phase 1 writes only fresh files. No databases, no config keystores. | None |
| Live service config | KWin reads `~/.local/share/aurorae/themes/<name>/` at theme-application time (when the user picks the theme via System Settings or `kwin --replace`). The theme list is built by scanning that directory. **Implication:** writing a new theme dir makes it discoverable; deleting it makes it disappear. No reload command needed for new themes (KWin re-scans on demand). | None for write; a re-run idempotency edge case (see below). |
| OS-registered state | None at the OS level. KDE's KCM (`kcm_kwindecoration`) caches the theme list per-session — not invalidated until the KCM module is re-opened or the user signals reload. **Implication:** if the user has the KCM open during conversion, they may need to close+reopen to see the new theme. Acceptable; document in `report.txt`. | Document only |
| Secrets/env vars | None. | None |
| Build artifacts / installed packages | `uv tool install .` creates a `themey` script in `~/.local/bin/`. Phase 1 ships uses `uv run themey` from the project; `uv tool install` is a deployment step the user runs once after Phase 1 completes. | Documented in README; not part of Phase 1 task scope. |

**Re-run idempotency edge case:** Per CLI-03, `themey Aliens.etheme` re-run must overwrite cleanly. The `os.replace` install pattern already covers this — the previous theme dir is replaced atomically. **Open question for the planner:** if the user has the previous theme **currently active** and we replace its files mid-render, KWin may flash. Phase 1 risk acceptance: this is a transient visual artifact, not a correctness bug; document it in `report.txt`. Phase 4's atomic Look-and-Feel install will need the same answer.

## Code Examples

> Verified patterns. All paths are inside `src/themey/`.

### `safe_extract` algorithm (PARSE-03)
```python
# src/themey/etheme/archive.py
"""Tar-safe extraction of E16 .etheme archives.

CVE-2007-4559 / CVE-2025-4330: tarfile.extractall is unsafe even with the
Python 3.12+ filter="data" default. We validate every member and resolve
symlinks at extract time (Look-and-Feel packages forbid symlinks; the
input shouldn't have them in the first place).
"""
from __future__ import annotations

import tarfile
import tempfile
from contextlib import contextmanager
from pathlib import Path

# Caps verified in production by ~/src/wilbs/src/lib/themes/e16/parse-e16-archive.ts
MAX_TOTAL_BYTES = 32 * 1024 * 1024  # 32 MB total extracted
MAX_FILE_BYTES = 8 * 1024 * 1024    # 8 MB per file
MAX_ENTRIES = 500                    # entry-count cap

# Marker filenames that identify the theme root (shortest-path wins).
ROOT_MARKERS = frozenset({"borders.cfg", "init.cfg"})


class UnsafeArchiveError(Exception):
    """Raised when an archive member fails the safe-extract validator."""


@contextmanager
def extract(etheme_path: Path):
    """Extract an .etheme archive into a temp directory.

    Yields a RawTheme(asset_root: Path) where asset_root is the directory
    containing borders.cfg / init.cfg (the theme root). The tempdir is
    auto-cleaned on context exit.
    """
    with tempfile.TemporaryDirectory(prefix="themey-") as td:
        td_path = Path(td).resolve()
        with tarfile.open(etheme_path, "r:gz") as tf:
            _safe_extract_all(tf, td_path)
        root = _find_theme_root(td_path)
        yield RawTheme(asset_root=root)


def _safe_extract_all(tf: tarfile.TarFile, dest: Path) -> None:
    total = 0
    count = 0
    members = tf.getmembers()
    if len(members) > MAX_ENTRIES:
        raise UnsafeArchiveError(f"too many entries: {len(members)} > {MAX_ENTRIES}")
    for m in members:
        count += 1
        # Reject device/character/fifo special files
        if m.ischr() or m.isblk() or m.isfifo():
            raise UnsafeArchiveError(f"unsafe member type: {m.name}")
        # Reject hardlinks (can race the extraction)
        if m.islnk():
            raise UnsafeArchiveError(f"hardlinks not allowed: {m.name}")
        # Reject absolute paths and ..-traversal
        if Path(m.name).is_absolute() or ".." in Path(m.name).parts:
            raise UnsafeArchiveError(f"path-traversal: {m.name}")
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest) + "/") and target != dest:
            raise UnsafeArchiveError(f"member escapes dest: {m.name}")
        # Symlinks: resolve target inside dest, then write target content as regular file
        if m.issym():
            link_target = (target.parent / m.linkname).resolve()
            if not str(link_target).startswith(str(dest) + "/"):
                raise UnsafeArchiveError(f"symlink escape: {m.name} -> {m.linkname}")
            # Do not write the symlink yet — wait until target file is written.
            # Approach: do a two-pass extraction: regular files first, then read each
            # symlink's resolved target and copy its bytes to the symlink's path.
            continue  # handled in pass 2
        # Regular files: enforce per-file cap and write
        if m.isfile():
            if m.size > MAX_FILE_BYTES:
                raise UnsafeArchiveError(f"file too large: {m.name} ({m.size} bytes)")
            total += m.size
            if total > MAX_TOTAL_BYTES:
                raise UnsafeArchiveError(f"archive too large: > {MAX_TOTAL_BYTES} bytes")
            target.parent.mkdir(parents=True, exist_ok=True)
            with tf.extractfile(m) as src, open(target, "wb") as dst:
                dst.write(src.read())
        elif m.isdir():
            target.mkdir(parents=True, exist_ok=True)
    # Pass 2: resolve symlinks
    for m in members:
        if not m.issym():
            continue
        target = (dest / m.name).resolve()
        link_resolved = (target.parent / m.linkname).resolve()
        if link_resolved.is_file():
            target.write_bytes(link_resolved.read_bytes())  # copy content
        else:
            # Target missing or directory — skip with note (logged later)
            pass


def _find_theme_root(extract_dir: Path) -> Path:
    """Find the directory containing borders.cfg or init.cfg (shortest path wins)."""
    candidates: list[Path] = []
    for marker in ROOT_MARKERS:
        candidates.extend(extract_dir.rglob(marker))
    if not candidates:
        raise UnsafeArchiveError(
            f"no theme root marker ({', '.join(ROOT_MARKERS)}) in archive"
        )
    return sorted(candidates, key=lambda p: len(p.parts))[0].parent
```

### Coordinate resolver (PARSE-04)
```python
# src/themey/analyze/coords.py
"""E16 hybrid coord resolution: final = (window_dim * pct/1024) + absolute.

`pct` is Q10 fixed point (1024 == 100%). `absolute` is signed pixel offset
that may be negative (e.g. pct=1024 + abs=-27 means '27 px from right edge').
NEVER call `abs()` on a coordinate.
"""
from __future__ import annotations


def resolve(percentage: int, absolute: int, window_dim: int) -> int:
    """Resolve an E16 coord to a concrete pixel value at a given window dim."""
    return int(window_dim * percentage / 1024) + absolute


# Reference window width for spatial-fallback button binning.
# Aliens default border verified to bin correctly at 800px.
REFERENCE_WINDOW_WIDTH = 800
REFERENCE_WINDOW_HEIGHT = 600
```

### Button binning cascade (AURORAE-02)
```python
# src/themey/analyze/buttons.py
"""Three-tier button binning: __ACLASS first → __ICLASS pattern → spatial."""
from __future__ import annotations

from .coords import resolve, REFERENCE_WINDOW_WIDTH

# Tier 1: __ACLASS → Aurorae button code
ACLASS_TO_BUTTON = {
    "ACTION_CLOSE":   "X",
    "ACTION_KILL":    "X",   # no force-quit equivalent; alias to close
    "ACTION_MAX":     "A",
    "ACTION_ICONIFY": "I",
    "ACTION_SHADE":   "L",
    "ACTION_STICK":   "S",
}
# Aclasses that are NOT buttons — drop them (Aurorae handles natively):
ACLASS_DROP = frozenset({
    "ACTION_RESIZE", "ACTION_RESIZE_H", "ACTION_RESIZE_V",
    "ACTION_MOVE",  # titlebar drag
})

# Tier 2: __ICLASS name pattern → button code (case-insensitive substring match)
ICLASS_PATTERN_TO_BUTTON = [
    ("BUTTON_CLOSE",    "X"),
    ("BUTTON_KILL",     "X"),
    ("BUTTON_MAXIMIZE", "A"),
    ("BUTTON_MAX",      "A"),
    ("BUTTON_ICONIFY",  "I"),
    ("BUTTON_MINIMIZE", "I"),
    ("BUTTON_SHADE",    "L"),
    ("BUTTON_STICK",    "S"),
]


def classify_button(part) -> tuple[str | None, str]:
    """Returns (button_code, source) where source is 'aclass'|'iclass'|'spatial'|None."""
    if part.aclass in ACLASS_DROP:
        return None, "drop"
    if part.aclass in ACLASS_TO_BUTTON:
        return ACLASS_TO_BUTTON[part.aclass], "aclass"
    iclass_upper = part.iclass.upper()
    for pattern, code in ICLASS_PATTERN_TO_BUTTON:
        if pattern in iclass_upper:
            return code, "iclass"
    return None, "spatial"  # caller handles spatial fallback


def bin_left_right(buttons, titlebar_min_x: int, titlebar_max_x: int):
    """Bin buttons into LeftButtons / RightButtons strings.

    `buttons` is a list of (code, x_center) pairs already resolved at
    REFERENCE_WINDOW_WIDTH via coords.resolve.
    """
    left = sorted(
        [b for b in buttons if b[1] < titlebar_min_x],
        key=lambda b: b[1],
    )
    right = sorted(
        [b for b in buttons if b[1] > titlebar_max_x],
        key=lambda b: b[1],
    )
    overlap = [b for b in buttons if titlebar_min_x <= b[1] <= titlebar_max_x]
    return (
        "".join(b[0] for b in left),
        "".join(b[0] for b in right),
        overlap,  # caller logs to report.txt
    )
```

**Aliens canary expected output:** Per `borders/default.cfg` parts at TL_X = 11 (kill, X), 118 (max, A), 140 (iconify, I), with TITLE_BAR_HORIZONTAL starting at 153 — all three buttons sit left of the titlebar. `LeftButtons="XAI"` (kill, max, iconify in spatial L→R order), `RightButtons=""`. The Aliens unit test should assert exactly this.

### State collapse mapping (AURORAE-04)
```python
# src/themey/analyze/states.py
"""E16 -> Aurorae image-state collapse. Lossy by design; logs every drop."""
from __future__ import annotations

# Decoration states (titlebar/border per-focus state)
DECORATION_STATE_MAP = {
    "decoration-active":   ["__NORMAL_ACTIVE", "__NORMAL"],   # fallback chain
    "decoration-inactive": ["__NORMAL"],
}

# Per-button state (inside button SVG, NOT decoration.svg)
BUTTON_STATE_MAP = {
    "button-default":  ["__NORMAL_ACTIVE", "__NORMAL"],
    "button-hover":    ["__HILITED_ACTIVE", "__HILITED"],
    "button-pressed":  ["__CLICKED_ACTIVE", "__CLICKED"],
}

# Always-dropped E16 states (no Aurorae target):
DROPPED_STATES = frozenset({
    "__NORMAL_STICKY", "__NORMAL_ACTIVE_STICKY",
    "__CLICKED_STICKY", "__CLICKED_ACTIVE_STICKY",
    "__HILITED_STICKY", "__HILITED_ACTIVE_STICKY",
    "__NORMAL_ACTIVE_CLICKED",  # rare; not a state Aurorae models
    "__DISABLED",
})


def collapse_image_states(iclass, target: str, notes: list[str]) -> str | None:
    """Pick the source path for a given Aurorae target via fallback chain.

    Returns the path (relative to asset_root) or None if no source exists.
    Appends a note to `notes` for every dropped state seen on the iclass.
    """
    chain = DECORATION_STATE_MAP.get(target) or BUTTON_STATE_MAP.get(target) or []
    for src in chain:
        path = getattr(iclass, src.lower().lstrip("_"), None)  # e.g. iclass.normal
        if path:
            return path
    return None
```

### Aurorae rc skeleton (AURORAE-01)
> Lifted from Edna's working `Ednarc` `[VERIFIED: ~/.local/share/aurorae/themes/Edna/Ednarc]`. Keys marked `[scaled]` multiply by `theme.scale`; other keys are scale-invariant.
```ini
[General]
ActiveTextColor=255,255,200,255
InactiveTextColor=200,200,150,255
TitleAlignment=Center
TitleVerticalAlignment=Center
UseTextShadow=true
ActiveTextShadowColor=0,0,0,255
InactiveTextShadowColor=0,0,0,255
TextShadowOffsetX=0
TextShadowOffsetY=1
LeftButtons=XAI
RightButtons=
Shadow=true
Animation=1

[Layout]
BorderLeft=4         ; [scaled] from __BORDER_SIZE_LEFT (Aliens: 35) — see note
BorderRight=4        ; [scaled] from __BORDER_SIZE_RIGHT (Aliens: 20)
BorderBottom=10      ; [scaled] from __BORDER_SIZE_BOTTOM (Aliens: 25)
TitleEdgeTop=4       ; [scaled] padding inside titlebar above text
TitleEdgeBottom=4    ; [scaled]
TitleEdgeLeft=7      ; [scaled]
TitleEdgeRight=7     ; [scaled]
TitleBorderLeft=3    ; [scaled]
TitleBorderRight=3   ; [scaled]
TitleHeight=15       ; [scaled] from __BORDER_SIZE_TOP - title insets
ButtonWidth=12       ; [scaled] from __MIN_WIDTH on button parts
ButtonHeight=12      ; [scaled]
ButtonSpacing=8      ; [scaled]
ButtonMarginTop=2    ; [scaled]
ButtonMarginLeft=3   ; [scaled]
ExplicitButtonSpacer=0
PaddingTop=35        ; [scaled] FrameSvg padding for shadows; from __BORDER_SIZE_TOP
PaddingBottom=90     ; [scaled]
PaddingRight=77      ; [scaled]
PaddingLeft=77       ; [scaled]
```

**Mapping note (Aliens default border):** E16 `__BORDER_SIZE_*` maps to Aurorae `Border*` and `Padding*`. Aliens has `LEFT=35, RIGHT=20, TOP=30, BOTTOM=25`; with `--scale=2` these become `LEFT=70, RIGHT=40, TOP=60, BOTTOM=50`. The exact mapping `BorderLeft = __BORDER_SIZE_LEFT * scale - some_inset` is one of the values the planner needs to tune; suggested starting point is `BorderLeft = max(2, __BORDER_SIZE_LEFT * scale // 8)` (Edna's hand-tuned values are tiny relative to its visual border thickness). The right answer is "iterate until the visible frame matches the source".

### `decoration.svg` skeleton (AURORAE-01 + AURORAE-03)
```python
# src/themey/generate/aurorae.py — sketch
import base64
import xml.etree.ElementTree as ET

SVG_NS   = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
ET.register_namespace("", SVG_NS)
ET.register_namespace("xlink", XLINK_NS)

SIDES = ("topleft", "top", "topright", "left", "center", "right",
         "bottomleft", "bottom", "bottomright")


def write_decoration_svg(theme, out_dir, scale: int):
    # Compute total SVG canvas size: title height + body
    border = theme.border  # already scaled
    width  = border.body_width  # e.g. REFERENCE_WINDOW_WIDTH * scale
    height = border.title_height + border.body_height

    svg = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": str(width), "height": str(height),
        "version": "1.1",
        "xmlns": SVG_NS, f"xmlns:xlink": XLINK_NS,
    })

    # 1. For each of 9 regions x {active, inactive}, emit a <g id="decoration-...">
    #    containing an <image> with preserveAspectRatio="none".
    for state_prefix in ("decoration", "decoration-inactive"):
        png_for_state = (
            border.active_png_bytes if state_prefix == "decoration"
            else border.inactive_png_bytes
        )
        b64 = base64.b64encode(png_for_state).decode("ascii")
        for side in SIDES:
            g = ET.SubElement(svg, f"{{{SVG_NS}}}g", {"id": f"{state_prefix}-{side}"})
            x, y, w, h = compute_region_bbox(side, border)
            ET.SubElement(g, f"{{{SVG_NS}}}image", {
                f"{{{XLINK_NS}}}href": f"data:image/png;base64,{b64}",
                "x": str(x), "y": str(y), "width": str(w), "height": str(h),
                "preserveAspectRatio": "none",
            })

    # 2. Hint margins (1×1 invisible rects telling FrameSvg the border thickness)
    for hint, val in (
        ("hint-top-margin", border.edge_top),
        ("hint-bottom-margin", border.edge_bottom),
        ("hint-left-margin", border.edge_left),
        ("hint-right-margin", border.edge_right),
    ):
        ET.SubElement(svg, f"{{{SVG_NS}}}rect", {
            "id": hint, "x": "0", "y": "0",
            "width": str(val), "height": str(val),
            "style": "opacity:0",
        })

    ET.ElementTree(svg).write(out_dir / "decoration.svg",
                              xml_declaration=True, encoding="utf-8")
    # Validate
    _assert_required_ids(out_dir / "decoration.svg")


def _assert_required_ids(svg_path):
    required = (
        [f"decoration-{s}" for s in SIDES] +
        [f"decoration-inactive-{s}" for s in SIDES]
    )
    root = ET.parse(svg_path).getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(required) - present
    if missing:
        raise AssertionError(f"FrameSvg IDs missing: {missing}")
```

### Hand-rolled `metadata.desktop` writer
```python
# src/themey/generate/desktop_writer.py
"""Hand-rolled .desktop INI writer.

DO NOT use configparser — localization keys like `Name[de]=Foo` look like
section headers to configparser's regex.
"""
from pathlib import Path


def write_desktop(path: Path, sections: dict[str, dict[str, str]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        first = True
        for section, entries in sections.items():
            if not first:
                f.write("\n")
            f.write(f"[{section}]\n")
            for k, v in entries.items():
                f.write(f"{k}={v}\n")
            first = False
```

Aurorae `metadata.desktop` keys (from Edna template):
```
[Desktop Entry]
Name=Aliens
X-KDE-PluginInfo-Author=themes.effx.us
X-KDE-PluginInfo-Email=
X-KDE-PluginInfo-Name=Aliens          ; MUST equal folder name
X-KDE-PluginInfo-Version=1.0
X-KDE-PluginInfo-Category=
X-KDE-PluginInfo-Depends=
X-KDE-PluginInfo-License=Unknown
X-KDE-PluginInfo-EnabledByDefault=true
X-KDE-PluginInfo-blur=false
```

### Aurorae `metadata.json` template
```python
# generate/aurorae.py
import json

def write_aurorae_metadata_json(out_dir, theme):
    data = {
        "KPackageStructure": "aurorae",
        "KPlugin": {
            "Authors": [{"Name": theme.author or "themes.effx.us", "Email": ""}],
            "Category": "Plasma 6 Window Decorations",
            "ServiceTypes": ["aurorae"],
            "EnabledByDefault": True,
            "Name": theme.display_name,
            "Description": f"{theme.display_name} window decoration (converted from E16)",
            "Id": theme.name,        # MUST equal folder name
            "Version": "1.0",
            "License": "Unknown",
            "X-KDE-PluginInfo-blur": False,
            "X-KPackage-Dependencies": [],
        },
    }
    (out_dir / "metadata.json").write_text(json.dumps(data, indent=4))
```

### Atomic install (INSTALL-01)
```python
# src/themey/install.py
import os
import shutil
from pathlib import Path

from . import paths


def deploy(theme_name: str, source_dir: Path) -> Path:
    final = paths.aurorae_themes() / theme_name
    final.parent.mkdir(parents=True, exist_ok=True)
    backup = final.with_name(f"{theme_name}.themey-old")
    if final.exists():
        if backup.exists():
            shutil.rmtree(backup)
        os.replace(final, backup)        # atomic move-aside
    try:
        os.replace(source_dir, final)    # atomic rename-into-place
    except OSError:
        # Roll back if final-rename failed
        if backup.exists():
            os.replace(backup, final)
        raise
    if backup.exists():
        shutil.rmtree(backup)
    return final
```

### HTML preview (PREVIEW-01)
```python
# src/themey/preview.py
import html
from pathlib import Path


def render(theme, out_path: Path) -> Path:
    rows = "\n".join(
        f"<li><code>{html.escape(n)}</code></li>" for n in theme.notes
    )
    html_doc = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>themey: {html.escape(theme.display_name)}</title>
<style>
  body {{ font: 14px sans-serif; max-width: 720px; margin: 2em auto; padding: 1em; }}
  .titlebar {{ background: rgb({theme.palette.titlebar_active.css_rgb});
              color: rgb({theme.palette.text_active.css_rgb});
              padding: 0.5em 1em; border-radius: 4px 4px 0 0;
              font-weight: bold; }}
  pre {{ background: #f4f4f4; padding: 0.75em; border-radius: 4px;
         user-select: all; }}
  ul.notes {{ font-size: 12px; color: #555; }}
</style></head><body>
<h1>{html.escape(theme.display_name)}</h1>
<div class="titlebar">{html.escape(theme.display_name)} - example window</div>
<p>Apply via <strong>System Settings - Window Decorations - {html.escape(theme.display_name)}</strong>.</p>
<p>Or run from a terminal:</p>
<pre>kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key library org.kde.kwin.aurorae
kwriteconfig6 --file kwinrc --group org.kde.kdecoration2 --key theme __aurorae__svg__{html.escape(theme.name)}
qdbus org.kde.KWin /KWin reconfigure</pre>
<h2>Conversion notes ({len(theme.notes)} entries)</h2>
<ul class="notes">{rows}</ul>
</body></html>
"""
    out_path.write_text(html_doc, encoding="utf-8")
    return out_path
```

### Headless / SSH detection for preview auto-open
```python
# src/themey/external.py
import os
import shutil
import subprocess
from pathlib import Path


def open_preview_unless_headless(html_path: Path) -> bool:
    """Open the HTML preview in the user's browser unless we detect headless/SSH.
    Returns True if launched; False if suppressed (still safe — caller prints path).
    """
    if os.environ.get("SSH_CONNECTION"):
        return False
    if not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"):
        return False
    xdg = shutil.which("xdg-open")
    if not xdg:
        return False
    subprocess.Popen(
        [xdg, str(html_path)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return True
```

### Typer entry point (CLI-01/02/03)
```python
# src/themey/cli.py
import logging
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def convert(
    theme: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    scale: int = typer.Option(2, "--scale", min=1, max=3),
    verbose: int = typer.Option(0, "-v", count=True),
    quiet: bool = typer.Option(False, "-q"),
) -> None:
    """Convert one .etheme to a Plasma Aurorae window decoration."""
    _setup_logging(verbose, quiet)
    from . import pipeline    # local import; keep startup fast
    result = pipeline.convert(theme, scale=scale)
    typer.echo(f"Installed: {result.installed_dir}")
    typer.echo(f"Preview:   {result.preview_path}")
    typer.echo(f"Apply via System Settings - Window Decorations - {result.theme_name}")


def _setup_logging(verbose: int, quiet: bool) -> None:
    level = logging.WARNING if quiet else (
        logging.DEBUG if verbose >= 1 else logging.INFO
    )
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
```

Pyproject script entry: `themey = "themey.cli:app"`.

### `Aliens.etheme` structure (verified)
```
Aliens.etheme  (gzipped tar; flat layout, NO top-level theme dir)
├── ABOUT/
│   ├── MAIN                 (theme metadata; HTML)
│   ├── title.png            (about-page banner)
│   ├── Edoc_bg.png
│   ├── bg.png
│   ├── aircut3.ttf -> ../ttfonts/aircut3.ttf       SYMLINK
│   └── avgardm.ttf -> ../ttfonts/avgardm.ttf       SYMLINK
├── artwork/
│   ├── cursors/             (10 cursors: cursor, move, kill, max,
│   │                          iconify, stick, resize_h/v/bl/br
│   │                          + .xbm.mask sibling for each)        Phase 3
│   ├── dialogs/, iconbox/, menustyles/             Phase 1 IGNORES (out of scope)
│   ├── backgrounds/         (12 jpg/gif files)     Phase 2
│   └── *.png                (titlebar/border/button glyphs — what Phase 1 needs)
├── borders/
│   ├── default.cfg          ← Phase 1 ONLY parses this border
│   ├── borderless.cfg       ← Phase 1 logs SKIPPED in report.txt
│   ├── fixed_size.cfg
│   ├── iconbox.cfg
│   ├── pager_top.cfg
│   └── shaped.cfg           (__CHANGES_SHAPE __ON; logged SKIPPED)
├── borders.cfg              (top-level: just #include directives)
├── buttons.cfg              (3 commented-out __BUTTON blocks; out of scope)
├── cursors.cfg              (10 __CURSOR blocks; Phase 3)
├── desktops.cfg             (legacy BEGIN_BACKGROUND macros; Phase 2)
├── fonts.cfg -> fonts.theme.cfg                    SYMLINK
├── fonts.theme.cfg          (XLFD font defs; informational only)
├── imageclasses/
│   └── borders.cfg          (large file; defines TITLE_BAR_HORIZONTAL,
│                             BUTTON_KILL, BUTTON_ICONIFY, BUTTON_MAXIMIZE,
│                             CORNER_TL, CORNER_TR, CORNER_BL, CORNER_BR,
│                             BUTTONL/R/T/B, etc.)
├── imageclasses.cfg         (top-level: #include borders.cfg + others)
├── init.cfg                 (start-up bg + progress-bar UI; Phase 2 ignores
│                             the legacy BEGIN_BACKGROUND form here)
├── menustyles.cfg, tooltips.cfg, windowmatches.cfg (out of scope)
├── textclasses.cfg          (TEXT1 tclass: titlebar font + color)
└── ttfonts/
    ├── aircut3.ttf          (cited but not bundled — Aurorae cannot use)
    └── avgardm.ttf
```

**Phase 1 reads:** `borders.cfg` (which `#include`s `borders/default.cfg`), `imageclasses.cfg` (which `#include`s `imageclasses/borders.cfg`), `textclasses.cfg`. The parser may also read `cursors.cfg`, `init.cfg`, `desktops.cfg` for parser-completeness, but `Theme.cursors` and `Theme.background` are stored without being acted on (Phase 2/3 work).

**Aliens canary expected outputs (Phase 1 success criteria):**
- `~/.local/share/aurorae/themes/Aliens/decoration.svg` exists, has 18 FrameSvg IDs
- `~/.local/share/aurorae/themes/Aliens/Aliensrc` has `LeftButtons=XAI`, `RightButtons=""`
- `~/.local/share/aurorae/themes/Aliens/{close,maximize,minimize}.svg` exist (note: `restore.svg` only if `BUTTON_MAXIMIZE` — present)
- `~/.local/share/aurorae/themes/Aliens/metadata.desktop` and `metadata.json` exist
- `~/.local/share/themey/previews/Aliens.html` opens in browser
- `~/.local/share/themey/previews/Aliens.report.txt` exists with sections

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.11+ | Runtime | yes | 3.14.4 | — |
| `uv` | Project + venv | yes | 0.11.7 | — (close enough to 0.11.8 lockfile target; lock will install matching deps) |
| Pillow | Image work | yes (system Python) | 12.1.1 | `uv sync` installs 12.2 in venv |
| `xdg-open` | Auto-open preview | yes | `/usr/bin/xdg-open` | Print path on missing |
| `plasma-apply-lookandfeel` | Phase 4 only (informational for Phase 1) | yes | `/usr/bin/plasma-apply-lookandfeel` | Phase 4 will resolve via `shutil.which` |
| `lookandfeeltool` | Phase 4 alias | yes | `/usr/bin/lookandfeeltool` | Phase 4 fallback path |
| `xcursorgen` | Phase 3 only | **NO** | — | Phase 3 must skip cursors + log to `report.txt` |
| KDE Plasma 6.x | Visual smoke test (manual gate) | yes (per PROJECT.md) | 6.6.4 | — |
| KWin | Theme rendering | yes (assumed; part of Plasma) | 6.6.4 | — |
| `~/src/wilbs/ethemes/e16/Aliens.etheme` | Test fixture | yes | 2.4 MB tar.gz | — |
| `/home/cstory/Downloads/e16-1.0.31/` | Grammar reference | yes | 1.0.31 | — |
| `/home/cstory/.local/share/aurorae/themes/Edna/` | Reference Aurorae theme | yes | — | — |

**Missing dependencies with no fallback:** None for Phase 1.

**Missing dependencies with fallback:** `xcursorgen` is missing but Phase 1 doesn't need it. Document in the planner for Phase 3: user will need to `sudo pacman -S xorg-xcursorgen` before Phase 3 runs OR Phase 3 must implement inline XCursor format (deferred decision per SUMMARY.md Open Question 4).

**Notable observations:**
- Developer's Python is 3.14 (newer than CLAUDE.md target of 3.11+). All Phase 1 stdlib calls are forward-compatible — `tarfile.extractall(filter=...)` (3.12+), `tomllib` (3.11+), and standard pathlib all work. `uv sync` will create a venv pinned to whatever `requires-python = ">=3.11"` allows.
- Pillow 12.1.1 is present system-wide, but `uv add pillow` will install 12.2.0 in the project venv. The version delta is patch-level; no Phase 1 code path uses 12.2-only API.

## Validation Architecture

> Skipped — `workflow.nyquist_validation` is `false` in `.planning/config.json`.

## Security Domain

> Phase 1 has no auth, no sessions, no network — but the **archive ingestion** is the security boundary. ASVS V5 (Input Validation) applies.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|------------------|
| V2 Authentication | no | — (single-user local CLI) |
| V3 Session Management | no | — |
| V4 Access Control | no | — (file permissions delegated to OS) |
| V5 Input Validation | **yes** | Custom `safe_extract` validator (see `## Code Examples`); reject path-traversal, symlink-escape, oversize, oversize-count |
| V6 Cryptography | no | — (no secrets, no signing) |
| V12 File Handling | **yes** | All output paths derived from sanitized theme name; theme name from archive filename (NOT from inside-archive content); slugify to `[A-Za-z0-9_-]+`; no shell invocation with archive-derived strings |
| V13 API & Web Service | no | — |

### Known Threat Patterns for `.etheme` ingestion

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Path traversal via tar member `../../.bashrc` | Tampering | `safe_extract`: resolve member path against extract root; reject if escaped |
| Symlink escape (member `evil → /etc/passwd`) | Tampering | `safe_extract`: resolve symlink target; reject if outside extract root; rewrite as regular file copy |
| Hardlink racing (member `evil` is a hardlink to existing file) | Tampering | `safe_extract`: reject all `member.islnk()` |
| Zip-bomb (oversize file) | DoS | `safe_extract`: enforce 8 MB per-file cap, 32 MB total cap |
| Entry-count bomb (millions of empty entries) | DoS | `safe_extract`: enforce 500-entry max |
| Device file ingestion (`/dev/zero`-style entries) | Tampering | `safe_extract`: reject `member.ischr()`, `isblk()`, `isfifo()` |
| Theme-name injection via filename (`../etc.etheme`) | Tampering | Sanitize filename: `[A-Za-z0-9_-]+`; reject names containing path separators or starting with `.` |
| Output-path injection via `__NAME` block content | Tampering | **Theme name comes from archive filename, NEVER from inside-archive content** (per PITFALLS.md UX section). Read `__NAME` for display only; sanitize for any HTML output via `html.escape()`. |
| HTML injection via `ABOUT/MAIN` content | Tampering | Phase 1 does not render `ABOUT/MAIN` in the preview HTML. Theme display name uses the archive filename, escaped via `html.escape()`. |

**Phase 1 negative test fixtures** the planner should ensure Phase 1's tasks include:
- `tests/fixtures/malicious/path_traversal.tar.gz` — member `../etc/passwd`
- `tests/fixtures/malicious/symlink_escape.tar.gz` — symlink to `/etc/passwd`
- `tests/fixtures/malicious/oversize_file.tar.gz` — 9 MB single member
- `tests/fixtures/malicious/oversize_count.tar.gz` — 600 empty members
- `tests/fixtures/malicious/no_root_marker.tar.gz` — no `borders.cfg` or `init.cfg`
- `tests/fixtures/malicious/absolute_path.tar.gz` — member `/tmp/evil`
- `tests/fixtures/malicious/device_file.tar.gz` — character device member

Each must produce `UnsafeArchiveError` BEFORE any file is written outside the extraction tmpdir.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tarfile.extractall(dest)` | `safe_extract` member validator | CVE-2025-4330 (2025) | Don't use `extractall` even with `filter="data"` |
| `lookandfeeltool -a <name>` | `plasma-apply-lookandfeel <name>` | Plasma 5→6 (2024) | Phase 4 concern; Phase 1 references System Settings GUI |
| `metadata.desktop` only for Aurorae | `metadata.desktop` AND `metadata.json` | KF6 transition (ongoing) | Emit both in Phase 1 |
| `pyfakefs` for filesystem tests | `tmp_path` + monkeypatched `HOME`/`XDG_DATA_HOME` | always preferred for this project | Pillow + tarfile need real files |
| pip / Poetry | `uv` | 2024–2026 | 10–100× faster; manages Python toolchain itself |
| `unittest` + setUp | `pytest` + fixtures | 2010s onward | Standard now |
| `pytest-snapshot` | `syrupy` | recently | syrupy fails on missing snapshots; better diffability |

**Deprecated/outdated (do not use):**
- **svgwrite** — maintainer-declared inactive since July 2022.
- **drawsvg** for FrameSvg — abstracts the element tree, fights "set this exact ID".
- **colorthief / colorgram.py** — unmaintained since 2017–2018.
- **clickgen / win2xcur** — wrong tools for our XBM→XCursor pipeline (Phase 3 concern only).
- **ninepatch (PyPI)** — Android-format-specific.
- **`Image.Resampling.LANCZOS` for border upscale** — blurs pixel art.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Aliens default border binning produces `LeftButtons="XAI"`, `RightButtons=""` | Pitfall 4 | Visually wrong button placement on Plasma; planner's Aliens canary test fails. **Mitigation:** plan task that runs the binning algorithm against parsed Aliens default.cfg and prints the result before declaring the test value correct. The `__ACLASS` cascade is verified; what's assumed is that all three buttons end up "left of titlebar" given they sit at x=11/118/140 with titlebar at x=153. |
| A2 | The `BorderLeft = max(2, __BORDER_SIZE_LEFT * scale // 8)` mapping in the Aurorae rc Layout section produces visually correct borders | Aurorae rc skeleton | Frame appears too thick/thin around windows. **Mitigation:** This is a "tune until it looks right" value; the Aliens visual smoke test on Plasma 6.6.4 is the gate. Edna's hand-tuned values for a different theme don't transfer mechanically. Planner should treat this as Claude's discretion and iterate during the visual gate. |
| A3 | KWin re-scans `~/.local/share/aurorae/themes/` on demand without an explicit `kwin --replace` | Runtime State Inventory | User has to manually reload KWin to see the new theme. **Mitigation:** include `qdbus org.kde.KWin /KWin reconfigure` in the preview HTML's instructions as a one-liner. |
| A4 | Embedding the **same** PNG bytes for both `decoration-*` (active) and `decoration-inactive-*` is acceptable when the source ICLASS has no distinct `__NORMAL` vs `__NORMAL_ACTIVE` images | State collapse | Inactive windows look identical to active. **Verified for Aliens:** TITLE_BAR_HORIZONTAL has both `__NORMAL` and `__NORMAL_ACTIVE` (same image, but distinct entries in cfg) — using the same image is correct for this theme. For other themes that distinguish, the analyze layer picks the per-state source via `DECORATION_STATE_MAP`. |
| A5 | The 800-px reference window width gives correct binning for Aliens | `REFERENCE_WINDOW_WIDTH` | Buttons land in wrong bin for some themes. **Verified for Aliens:** all 3 buttons are at fixed `_PERCENTAGE 0` offsets (140, 118, 11), so window-width-independent — they're always left of titlebar regardless of width. Spatial fallback only matters if `__ACLASS` is missing (not the case for Aliens). |

If this table is non-empty, the planner should mark each as a verification task in PLAN.md or treat as a discuss-phase question. **Aliens-specific assumptions A1, A4, A5 are testable in Phase 1's first plan; A2, A3 are Plasma-environment-dependent and only confirmed by the visual smoke test gate.**

## Open Questions

1. **Exact `[Layout]` numerical mappings from `__BORDER_SIZE_*` → `BorderLeft`/`Padding*`/etc.**
   - What we know: Edna's `Ednarc` has values; Aliens has different `__BORDER_SIZE_*` numbers (35/20/30/25). Visual fidelity needs tuning.
   - What's unclear: Exact algebraic mapping. Edna's `BorderLeft=2` with a visually thick frame implies the **PaddingLeft=77** is doing most of the visual work (padding includes shadows; FrameSvg renders the border PNG inside this region).
   - Recommendation: Start with `BorderLeft=__BORDER_SIZE_LEFT*scale, PaddingLeft=__BORDER_SIZE_LEFT*scale*2` and iterate visually. Document the chosen formula in a constant block in `generate/aurorae.py` so it's easy to adjust.

2. **What does Phase 1 do with `cursors.cfg`, `desktops.cfg`, `init.cfg` legacy macros?**
   - What we know: Aliens uses `BEGIN_BACKGROUND` macros that expand to `__DESKTOP __BGN` / `__BACKGROUND_LAYER` (not `__BACKGROUND __BGN` / `__BG_BG` that wilbs's `parse-cfg.ts` recognizes). The parser must not crash.
   - What's unclear: Should Phase 1 implement macro expansion (read `definitions` from E16 source and apply preprocessor)? Or just generic-block-store everything and let Phase 2 figure it out?
   - Recommendation: **Generic-block-store.** The parser records every `__BGN`/`__END` block as a `Block(keyword, kvs, children)` AST node regardless of whether it knows what to do with the contents. Analyze layer for Phase 1 only consumes blocks it understands (`__BORDER`, `__ICLASS`, `__TCLASS`); other blocks (`__DESKTOP`, `__CURSOR`) are stored verbatim on `Theme` for Phase 2/3 to consume. **Macro expansion is NOT needed in Phase 1** as long as the parser tolerates unknown keywords as opaque key-value lines.

3. **Phase 1 syrupy snapshot: should `Aliens.etheme` have full byte snapshots?**
   - What we know: Aliens is the canary; small-fixture `tiny.etheme` would be deterministic. Aliens has 12 jpgs in `artwork/backgrounds/` totaling ~2 MB — committing it as a fixture is fine.
   - What's unclear: SVG snapshots will diff every time Pillow's PNG byte order changes. Pin Pillow version in `uv.lock` and accept the snapshot dance.
   - Recommendation: `tiny.etheme` (hand-crafted, ~5 KB, no external dependencies on PNG byte stability) gets full snapshots. `Aliens.etheme` integration test asserts **structural** properties (18 IDs present, `LeftButtons` matches expected, files exist) rather than byte-snapshot of the SVG.

4. **Should `__BACKGROUND` block parsing happen in Phase 1?**
   - What we know: WALLPAPER-01 is Phase 2. Aliens uses legacy `BEGIN_BACKGROUND` macros (not `__BACKGROUND __BGN` form). Wilbs only recognizes the `__BACKGROUND` form.
   - Recommendation: Phase 1 records **both** forms as opaque AST blocks. Phase 2 implements the real parsing (macro expansion or hardcoded recognition of `__DESKTOP` + `__BACKGROUND_LAYER` keys). No Phase 1 task needs to interpret backgrounds.

## Sources

### Primary (HIGH confidence)

**Ground truth on disk:**
- `/home/cstory/Downloads/e16-1.0.31/src/iclass.c` lines 369-386 (state fallback) and `iclass.c` `sscanf("%i %i %i %i", &l, &r, &t, &b)` for `__EDGE_SCALING` order.
- `/home/cstory/Downloads/e16-1.0.31/src/eimage.h` — `EImageBorder { int left, right, top, bottom; }` struct.
- `/home/cstory/Downloads/e16-1.0.31/config/definitions` lines 927-968 — `BEGIN_BACKGROUND` / `ADD_BACKGROUND_*` macro expansions.
- `/tmp/themey_inspect/` — extracted Aliens.etheme (verified flat layout, 3 symlinks, XBM cursor + mask sibling, XLFD font strings).
- `/home/cstory/.local/share/aurorae/themes/Edna/{decoration.svg,Ednarc,metadata.desktop,metadata.json,close.svg}` — verified working FrameSvg ID set (18 IDs, no maximized variants), Aurorae rc structure, both metadata files coexist.
- `/home/cstory/src/wilbs/src/lib/themes/e16/parse-cfg.ts` — 489-line production parser; types and `__ACLASS` capture pattern.
- `/home/cstory/src/wilbs/src/lib/themes/e16/parse-e16-archive.ts` — production safety caps (32 MB / 8 MB / 500 entries) and root-marker detection.
- `/home/cstory/src/wilbs/.planning/notes/e16-architecture-and-gap-matrix.md` — `__ACLASS` bug post-mortem (the resize-on-hover bug).

**KDE / Plasma official:**
- [Aurorae window decorations (develop.kde.org)](https://develop.kde.org/docs/plasma/aurorae/) — FrameSvg element ID structure, state suffixes.
- [Plasma Style quickstart (develop.kde.org)](https://develop.kde.org/docs/plasma/theme/quickstart/) — `preserveAspectRatio="none"` for embedded raster, embed-don't-link rule.
- [KDE/ksvg (GitHub)](https://github.com/KDE/ksvg) — FrameSvg implementation; 9-patch rendering by named element lookup.

**PyPI version verification (2026-05-01):**
- Pillow 12.2.0 (uploaded 2026-04-01)
- Typer 0.25.1 (2026-04-30)
- pytest 9.0.3 (2026-04-07)
- syrupy 5.1.0 (2026-01-25)
- ruff 0.15.12 (2026-04-24)
- pyright 1.1.409 (2026-04-23)
- uv 0.11.8 (2026-04-27)

**Security CVEs:**
- [CVE-2007-4559 (tarfile path traversal)](https://www.securecodewarrior.com/article/traversal-bug-in-pythons-tarfile-module).
- [CVE-2025-4330 (data-filter PATH_MAX bypass)](https://www.sentinelone.com/vulnerability-database/cve-2025-4330/) — justifies mandatory `safe_extract` even on Python 3.12+.

### Secondary (MEDIUM confidence)
- [What's next for Aurorae? — Vlad Zahorodnii (2025-11-13)](https://blog.vladzahorodnii.com/2025/11/13/whats-next-for-aurorae/) — Aurorae V2 / KSvg context.
- [Non-integer scaling pixelation — KDE Discuss](https://discuss.kde.org/t/non-integer-scaling-application-style-window-decorations-pixelated-on-6-6-with-many-themes/44480) — Plasma 6.6 fractional scaling bugs.
- [tldr-pages PR #15444](https://github.com/tldr-pages/tldr/pull/15444) — `lookandfeeltool` to `plasma-apply-lookandfeel` rename.

### Tertiary (LOW confidence — flagged in Assumptions Log)
- Exact mapping `__BORDER_SIZE_* → BorderLeft/PaddingLeft/etc.` — Edna's hand-tuned values do not transfer mechanically; iterate visually.
- Whether the `BorderLeft=max(2, __BORDER_SIZE_LEFT * scale // 8)` formula gives a visually correct frame.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — all versions verified against PyPI 2026-05-01; CLAUDE.md locks the picks; alternatives ruled out with citations.
- Architecture: **HIGH** — pipeline + frozen-IR is a well-known Python CLI pattern; structure mirrors the proven wilbs implementation; verified against ARCHITECTURE.md research.
- Pitfalls: **HIGH** — 12 critical pitfalls verified against E16 source on disk, the user's installed Edna theme, and the actual Aliens.etheme contents. Three closed-by-correction in PROJECT.md.
- Aliens canary expectations (A1/A4/A5): **HIGH** — verified by reading `borders/default.cfg` and `imageclasses/borders.cfg` byte-for-byte.
- Aurorae rc layout numerical mappings (A2): **MEDIUM** — needs visual gate; Edna's values do not mechanically transfer.
- Plasma session-level theme reload (A3): **MEDIUM** — `qdbus org.kde.KWin /KWin reconfigure` is the standard reload command but not 100% guaranteed; Plasma's behavior for new themes is to re-scan on demand.

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 (30 days for stable stack; PyPI versions move). Verify versions again before Phase 2 starts.
