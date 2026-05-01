# Project Research Summary

**Project:** themey — E16 `.etheme` → KDE Plasma 6 Look-and-Feel CLI converter
**Domain:** Local single-user Python 3 CLI; legacy theme-format converter; image processing + structured-text emission for KDE Plasma 6
**Researched:** 2026-05-01
**Confidence:** HIGH

> **Read first:** This SUMMARY.md is the document downstream agents (roadmapper, phase planners, implementers) consume by default. The four full research files (`STACK.md`, `FEATURES.md`, `ARCHITECTURE.md`, `PITFALLS.md`) are detailed appendices. Read them when this summary points you at a specific section.

---

## Executive Summary

themey is a **single-process, single-user, single-pass Python CLI pipeline**. One invocation reads one (or many) `.etheme` archives — gzipped tars carrying E16's `__BLOCK __BGN ... __END` config grammar plus PNG/XBM assets — and writes a Plasma 6 Look-and-Feel package under `~/.local/share/...`. There is **no daemon, no GUI, no network**. The pipeline has four stages: **Ingest → Analyze → Generate (5 outputs) → Install + Report + Preview**, separated by a single canonical intermediate representation (`Theme` dataclass) which is the only contract crossing the analyze/generate seam. The recommended stack is conservative: Pillow + stdlib `xml.etree` + stdlib `configparser` + Typer CLI + `xcursorgen` subprocess, managed by `uv` with snapshot tests via syrupy. Every choice optimizes for "one author, daily-use, ~100-theme corpus" — not extensibility, not second users.

The project is **risk-front-loaded**: Phase 1 (parser + Aurorae generator + safe-extract) carries roughly two-thirds of all critical pitfalls catalogued. The Aurorae window decoration is simultaneously the hardest output to get right (FrameSvg requires 18 exactly-named element IDs, embedded raster needs `preserveAspectRatio="none"`, button-binning needs titlebar-midpoint center-of-mass) and the most visually identifying output. Once Aurorae works on the verified ground-truth `Aliens.etheme` (the canary), Phases 2–5 are largely mechanical applications of the same "IR → format" pattern. The remaining hard pitfall — XBM cursor mask handling — is isolated in its own late phase.

Three structural facts shape every recommendation:

1. **PROJECT.md is now ground-truth-correct** after recent edits — `__EDGE_SCALING` is `L R T B`, the activation command is `plasma-apply-lookandfeel`, the Look-and-Feel package uses `manifest.json` (not `metadata.desktop`), and `safe_extract` is mandatory. The researchers wrote against an earlier draft; their warnings are still valid as *prevention rationale*, but several originally-flagged risks are now closed-by-correction in PROJECT.md.
2. **State-model collapse is lossy by design** — E16 has 16 image-state cells, Aurorae has 3; every conversion logs which states were dropped.
3. **No auto-switch.** Conversion installs and prints the activation command; the user runs `plasma-apply-lookandfeel <name>` themselves.

---

## Key Findings

### Recommended Stack

(Full detail: `STACK.md`. All version numbers verified against PyPI on 2026-05-01.)

A deliberately small dependency surface: **Pillow + Typer + stdlib + one system binary**. Two pip-installed runtime deps (Pillow, Typer); everything else (XML, INI, tarfile, gzip, base64, dataclasses, tomllib for config) is stdlib. One system binary (`xcursorgen` from `xorg-xcursorgen`) is required only for the cursor phase and is gracefully degradable.

**Core technologies:**

- **Python 3.11+** (target 3.12) — runtime; PROJECT.md locks this. 3.11 keeps `tomllib` available; 3.12+ adds the `tarfile filter="data"` default (which we layer `safe_extract` over anyway, see Pitfall 11).
- **Pillow 12.2** — every raster operation: read PNG/XBM, nearest-neighbour upscale for pixel-art borders, LANCZOS for wallpapers, median-cut quantize for palettes. Built-in `XbmImagePlugin` is the decisive feature.
- **stdlib `xml.etree.ElementTree`** — emit `decoration.svg`, button SVGs, preview HTML. FrameSvg's contract is "an element with this ID exists at this bbox"; stdlib is sufficient. **Must `register_namespace("", svg_ns)`** to avoid `ns0:` prefix mangling.
- **stdlib `configparser.RawConfigParser`** with `optionxform = str` — emit Aurorae `<name>rc` and `.colors` files. KDE keys are case-sensitive; `RawConfigParser` skips `%`-interpolation. **`.desktop` files use a hand-rolled writer** because localization keys like `Name[de]=Foo` confuse configparser's section regex.
- **Typer 0.25** — type-hint-driven CLI. Click-based.
- **uv 0.11** — project + venv + Python toolchain manager.
- **xcursorgen subprocess** — XBM→XCursor. PyPI alternatives (`clickgen`, `win2xcur`) are unmaintained or wrong-direction.
- **pytest 9.0 + syrupy 5.1** — snapshot testing fits the byte-stable-output nature of the project.
- **Ruff 0.15 + pyright basic** — lint/format + type check.

**Avoid:** `svgwrite` (inactive 2022), `drawsvg` (DSL fights FrameSvg's exact-ID requirement), `colorthief`/`colorgram.py` (unmaintained 2017–2018), `clickgen` (no recent release), PyPI `ninepatch` (Android `.9.png` format), `configparser` for `.desktop` files, `LANCZOS` for border upscale (blurs pixel-art).

### Expected Features

(Full detail: `FEATURES.md`. Framing: closed corpus of ~100 trusted `.etheme` files, single user.)

**Must have (table stakes):**

- All five generators: Aurorae, color-scheme, wallpaper, XCursor, Look-and-Feel bundle.
- Single-theme `themey <theme.etheme>` and batch `themey --all <dir>` with **skip-on-error**.
- Per-theme `report.txt` (Preserved / Approximated / Skipped sections).
- HTML preview file (the only UI surface); auto-suppress on headless / SSH.
- Print activation command (`plasma-apply-lookandfeel <name>`).
- Default `--scale=2` (overrideable to 1 or 3); idempotent re-runs.
- Stable, reversible output paths under `~/.local/share/...`.
- Verbosity flags `-v`/`-vv`/`-q`.
- **Install manifest** (per-theme JSON listing every file written) — small, but unblocks `--uninstall`/`--list`/`--verify`/`--prune`. Highest-leverage non-table-stakes feature.
- **`themey --uninstall <name>`** — promoted to table-stakes the moment batch mode exists.

**Should have (early daily-use friction):**

- `--list`, batch progress UI (`rich`, auto-disabled when not a TTY), source-dir auto-detect, conflict handling (`--force` / `--force --backup`), `--inspect` (dry-run), HTML side-by-side preview, file logging, config file (TOML via stdlib `tomllib`), `--apply` flag (opt-in auto-activate).

**Defer (v2+):** HTML fake-window mockup, `--verify`, `--prune`, `--json` output, light/dark color-scheme variants.

**Anti-features:** GUI, web/cloud, telemetry, plugin system, daemon, network downloads, sandbox, Plasma Style generation, QStyle, E17/EFL, reverse direction. All explicitly Out of Scope per PROJECT.md.

### Architecture Approach

(Full detail: `ARCHITECTURE.md`.)

**Functional pipeline with a frozen-dataclass IR.** Stages are pure functions `In → Out`; no shared mutable context object. The `Theme` dataclass at `src/themey/ir.py` is the **single contract** between the input half (`etheme/`, `analyze/`) and the output half (`generate/`, `install.py`, `report.py`, `preview.py`). Generators consume `Theme` and write to a passed-in `out_dir: Path`. Every stage is trivially unit-testable with hand-built dataclasses; the import DAG is enforceable by a single test; `--inspect` is a free side-effect of clean separation.

**Major components (one-line responsibilities):**

1. **`cli.py`** — Typer dispatch, batch loop, exit codes. ~150 LoC.
2. **`etheme/{archive,lex,parse,ast}.py`** — INPUT side. Hand-rolled recursive-descent parser (~150 lines for a 7-production grammar; Lark/PEG would be overkill). `archive.py` includes mandatory `safe_extract`. AST is dumb data — fixed-point math (1024=100%) is *not* a parser concern.
3. **`ir.py`** — flat at package root. The `Theme` dataclass + sub-records. Pure data; imports nothing heavy. The one mutable accumulator is `Theme.notes: list[str]` which feeds `report.txt`.
4. **`analyze/{borders,buttons,colors,wallpaper,cursors}.py`** — INTERPRETATION layer. Resolves cross-refs, applies E16→Aurorae state-collapse, runs button center-of-mass binning against the **titlebar** midpoint, samples palette from titlebar+dialog+button regions weighted, picks wallpaper. Owns the lossy decisions; logs them.
5. **`images/{ninepatch,upscale,sample}.py`** — pure Pillow primitives. Zero E16 or KDE knowledge.
6. **`generate/{aurorae,colors,wallpaper,cursors,lookandfeel}.py`** — OUTPUT side. Mirror of `etheme/`. Each is `def generate(theme: Theme, out_dir: Path) -> list[Path]`.
7. **`external.py`** — single subprocess chokepoint. Wraps `xcursorgen`, `xdg-open`, `plasma-apply-lookandfeel` (resolution only). Returns tagged unions; generators degrade gracefully.
8. **`install.py`** — atomic installer. Stage to tmpdir, then `os.replace` each top-level dir. All-or-nothing per theme.
9. **`paths.py`** — XDG-aware. Tests use `fake_home` fixture (tmp_path + monkeypatched env). **Never `pyfakefs`** — Pillow and tarfile need real files.

**Sequencing within a theme:** generators run **serially** (aurorae → colors → wallpaper → cursors → lookandfeel). Parallelism within a theme buys nothing. If `--all` over 100 themes ever feels slow, parallelize at the **theme** level (`multiprocessing.Pool`), never at the generator level.

### Critical Pitfalls

(Full detail: `PITFALLS.md` — 12 pitfalls plus tech-debt patterns, integration gotchas, performance traps, and a "looks done but isn't" checklist.)

Post-correction picture (3 of 12 are now closed-by-correction in PROJECT.md):

1. **`__EDGE_SCALING` order is `L R T B`** *(closed-by-correction)*. C parser is `sscanf("%i %i %i %i", &l, &r, &t, &b)`. Hardcode the constant; unit-test the parser.
2. **Negative pixel offsets are intentional, not errors.** Layout is `final = (window_dim × pct/1024) + absolute`; `pct=1024, abs=-27` means "27 px from right edge". Never `abs()` a coordinate.
3. **State-model collapse is lossy and must be deliberate** *(policy now in PROJECT.md Context)*. Define explicit `E16_TO_AURORAE_STATE` mapping; log every dropped state.
4. **Button-binning must use titlebar midpoint, not window midpoint.** Three-step: resolve → bound titlebar → bin by `[0, titlebar_min_x]` → Left, `[titlebar_max_x, window_w]` → Right; overlap drops to `report.txt`.
5. **FrameSvg requires 18 exactly-named IDs** — `decoration-{topleft,top,topright,left,center,right,bottomleft,bottom,bottomright}` plus `decoration-inactive-*`. Maximized variants are optional (Edna ships without them and works). Validate the ID set programmatically after generation.
6. **Embedded raster needs `preserveAspectRatio="none"` AND base64 inline.** Relative `href` cannot resolve after install relocation; default aspect-ratio centers tiles leaving transparent margins.
7. **XBM cursors are 1-bit + sibling `.mask` file.** Without combining bits + mask into ARGB premultiplied, cursors render as black squares or invisible. Phase 4 only.
8. **Aurorae cannot override the title font.** Don't bundle TTFs. Map XLFD tokens to fontconfig generics, log the mapping, preserve the foreground *color* via the rc's `ActiveTextColor`/`InactiveTextColor` (E16 grammar misspells `__FORGROUND_COLOR`).
9. **Look-and-Feel package uses `manifest.json` not `metadata.desktop`** *(closed-by-correction)*. The Aurorae sub-package still uses `metadata.desktop`. The L&F tree forbids symlinks anywhere — resolve at extract time.
10. **`plasma-apply-lookandfeel` is the canonical command name** *(closed-by-correction)*; `lookandfeeltool` is an alias on most distros but not guaranteed. Resolve via `shutil.which`. **Argument format (positional vs `-a`) needs verification on the user's machine** — see Open Questions.
11. **`tarfile.extractall` is unsafe even with Python 3.12+ `filter="data"`** (CVE-2025-4330 PATH_MAX bypass). Mandatory `safe_extract` from Phase 1 day one *(now mandated in PROJECT.md)*.
12. **HiDPI/fractional scaling pixelates embedded raster.** `--scale=2` default helps; pixel-perfect at 1.0/2.0/3.0×, approximate at 1.25/1.5/1.75×. Cap output SVG size with a warning above ~2 MB.

---

## Implications for Roadmap

### Phase 1 scope conflict — RESOLVED

The three researchers proposed different Phase 1 scopes:

| Researcher | Phase 1 scope |
|------------|---------------|
| Architecture | Ingest + parser + analyze + Aurorae + install + preview. **No colors, wallpaper, cursors, or L&F bundle.** |
| Features | All 5 generators (Aurorae + colors + wallpaper + cursors + L&F bundle) — these are P1 "table stakes." |
| Pitfalls | 8 of 12 critical pitfalls land in Phase 1 regardless. |

**Resolution: take Architecture's narrow Phase 1.** Reasoning:

- The headline output is Aurorae. If Aurorae fidelity is wrong, nothing else matters and the whole design is reconsidered. Front-load it.
- Colors / wallpaper / cursors / L&F bundle are mechanical applications of the same "Theme IR → format" pattern once the IR and Aurorae are proven. Stretching Phase 1 to cover all five concentrates *every* phase-1 risk in one phase.
- "Table stakes" in FEATURES.md describes what the **shipped tool** must have, not what Phase 1 alone must produce. Phases 2–5 still ship before declaring v1.
- Phase 1's pitfalls are tightly *coupled* (parser → analyze → Aurorae) and resolve well as one focused block. Adding colors+wallpaper+cursors+L&F adds 4 *uncoupled* sets of risk that would mask real Aurorae issues.

### Phase 1: Parse → Analyze → Aurorae → Install → Preview (the foundation)

**Rationale:** Highest-risk, highest-value vertical slice. If this works, the rest is mechanical.
**Delivers:** `themey aliens.etheme` produces an installable Aurorae window decoration the user applies via System Settings → Window Decorations. Single-theme only. HTML preview opens in browser.
**Implements:** PARSE-01, PARSE-02, AURORAE-01/02/03, CLI-01 (single-theme form), CLI-02 (`--scale`), PREVIEW-01 (basic), partial REPORT-01 (stdout).
**Avoids/addresses:** Pitfalls 1, 2, 3, 4, 5, 6, 8 (color half), 11, 12. Nine of 12 critical pitfalls front-loaded by design.
**Critical gates before Phase 2:**

- `safe_extract` rejects `../etc/passwd` and symlink-escape archives in negative tests.
- Aliens.etheme produces a `decoration.svg` with all 18 required FrameSvg IDs (programmatically validated).
- Aliens default border resolves to `LeftButtons=""`, `RightButtons` ordered spatially right-to-left.
- `report.txt` (or stdout) lists ≥4 dropped E16 states for Aliens.
- Visual smoke test on Plasma 6.6.4 at scales 1.0×, 1.5×, 2.0×.

### Phase 2: Color scheme + Wallpaper

**Rationale:** Both are mechanical given Phase 1's IR. Color sampling shares logic with Aurorae's title-color extraction; wallpaper is mostly plumbing.
**Delivers:** Conversion now also installs `~/.local/share/color-schemes/<name>.colors` and `~/.local/share/wallpapers/<name>/`. Theme is "75% there" visually.
**Implements:** COLORS-01, WALLPAPER-01, full REPORT-01 (Preserved/Approximated/Skipped sections), HTML preview gains color swatches and wallpaper thumbnail.
**Pitfalls addressed:** Color half of 8 (`__FORGROUND_COLOR`), Integration Gotcha "seven required `[Colors:*]` sections."
**Research flag:** None — Pillow median-cut + KColorScheme INI structure are well-documented.

### Phase 3: XCursor generation

**Rationale:** Cursors are isolated — independent pipeline (XBM → ARGB premultiplied → xcursorgen) with no shared logic. Build alone so failure modes don't entangle.
**Delivers:** `~/.local/share/icons/<name>-cursors/` with full XCursor set + `index.theme` (`Inherits=Adwaita`).
**Implements:** CURSORS-01.
**Pitfalls addressed:** Pitfall 7 (XBM bits + mask + premultiplied), Integration Gotcha "E16 cursor name → XCursor name mapping."
**Research flag:** **Light research likely.** XCursor binary format is small enough to implement inline (~100 LoC) which removes the system-dep. Decision deferred to Phase 3 spike.
**Graceful degradation:** if `xcursorgen` is missing, skip cursor output, append note to `report.txt`, install proceeds for other four artifacts.

### Phase 4: Look-and-Feel bundle + activation messaging

**Rationale:** Requires all four prior outputs (it's the wrapper). Cannot start before Phases 2–3.
**Delivers:** `~/.local/share/plasma/look-and-feel/<name>/` with `manifest.json` (`KPackageStructure=Plasma/LookAndFeel`) and `contents/defaults` INI. **One-command activation.**
**Implements:** BUNDLE-01, activation-command print logic.
**Pitfalls addressed:** Pitfall 9 (manifest.json + no-symlinks final-package validation), Pitfall 10 (`plasma-apply-lookandfeel` resolution + alias fallback). Plus checklist items: all four `contents/defaults` sections, `KPlugin.Id` matches folder name.
**Critical gate:** `find <pkg> -type l` returns empty; `manifest.json` validates against schema; theme installs *and* applies via `plasma-apply-lookandfeel` end-to-end.
**Research flag:** **Worth a 30-minute pass** on `contents/defaults` exact INI structure for Plasma 6.6.4 and the `theme=__aurorae__svg__<name>` syntax for custom themes.

### Phase 5: Batch mode + manifest + uninstall

**Rationale:** Single-theme is daily-use-viable after Phase 4. Batch mode requires per-theme isolation, skip-on-error, and the install manifest. Uninstall and `--list` come "free" once the manifest exists.
**Delivers:** `themey --all <dir>` with progress UI; `themey --uninstall <name>`; `themey --list`; auto-suppress preview in batch (preventing 100 browser tabs).
**Implements:** CLI-01 batch form, install manifest, `--uninstall`, `--list`, conflict handling (`--force` / `--force --backup`), progress UI (`rich`).
**Stack addition:** `rich`. Auto-disable when not a TTY.
**Pitfalls addressed:** Performance Trap (browser tab per theme), UX Pitfalls (name collisions → slugify+dedupe; SSH/headless preview suppression).
**Research flag:** None — standard CLI patterns.

### Phase 6: Polish (deferred to v1.x as friction surfaces)

In likely-friction order: source-dir auto-detect, `--inspect`, HTML side-by-side before/after, file logging, config file (TOML via stdlib `tomllib`), `--apply` flag.

### Out-of-roadmap (v2+)

HTML fake-window mockup, `--verify`, `--prune`, `--json`, light/dark color-scheme variants. None blocks v1.

### Phase Ordering Rationale

- **Risk-first.** Phase 1 concentrates 9 of 12 critical pitfalls. By Phase 2 the parser/IR/Aurorae core is verified against Aliens; later phases are decoupled additions.
- **Dependency-driven.** Phase 4 (L&F bundle) requires Phases 2–3 outputs. Phase 5 (batch) requires Phase 1's CLI skeleton + manifest format which is trivially added in Phase 4.
- **One output per phase after Phase 1.** Snapshot tests for that output land in the same phase. Failure is locally-attributable.
- **Pitfalls 1, 9, 10 are pre-resolved by PROJECT.md corrections.** The researchers wrote against an earlier draft. Their warnings remain useful as *implementation guidance* (how to encode the correct value, what to validate) but the underlying mistakes can no longer originate from PROJECT.md being wrong.
- **No premature parallelism.** Generators run serially within a theme; theme-level parallelism is a Phase 6+ optimization, not foundational.

### Research Flags

**Phases that may benefit from `/gsd-research-phase`:**

- **Phase 3 (cursors):** focused research on subprocess-vs-inline `xcursorgen` decision and on edge-case E16-to-XCursor name mapping (`MAX`, `STICK`, `ICONIFY`).
- **Phase 4 (Look-and-Feel bundle):** focused research on the `contents/defaults` INI exact structure for Plasma 6.6.4 and on `plasma-apply-lookandfeel` argument format.

**Phases with standard patterns (no research needed):**

- **Phase 2 (colors + wallpaper):** Pillow median-cut + KColorScheme + wallpaper `metadata.json` are well-documented.
- **Phase 5 (batch + manifest):** standard CLI patterns.
- **Phase 6 (polish):** trivial features built reactively.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All version numbers verified against PyPI on research date; "what NOT to use" claims backed by last-release dates or maintainer statements. |
| Features | HIGH | Closed-corpus single-user framing makes the must/should/defer split clear — no second users to satisfy. |
| Architecture | HIGH | Pipeline + frozen-IR is a well-known Python CLI pattern; the project shape fits this pattern exactly. |
| Pitfalls | HIGH | All 12 verified against ground truth — E16 source on disk, the user's installed Aurorae themes, and the actual extracted Aliens.etheme. Three are now closed-by-correction in PROJECT.md (1, 9, 10) — the warnings did their job. |

**Overall confidence:** **HIGH.** The corpus is closed and trusted, the user's Plasma version is known and inspectable, the input grammar is documented in C source on the user's disk, and the output formats are documented on `develop.kde.org`. Only meaningful uncertainty is "fidelity feels right?" — a per-theme judgment that resolves on first real conversion.

### Gaps to Address (Open Questions)

These are open questions the roadmapper should decide whether to (a) lock down before Phase 1, (b) defer to a Phase 3/4 spike, or (c) leave for runtime resolution.

1. **`plasma-apply-lookandfeel` argument format** — positional `<name>` vs `-a <name>`. **Recommend: lock down via 2-minute check on the user's Plasma 6.6.4 system before Phase 4.** Update PROJECT.md BUNDLE-01 with the verified form. Trivial; not worth a research pass.
2. **Fractional-scaling visual quality** at 1.25×/1.5×/1.75×. **Recommend: defer to Phase 1 visual-smoke-test gate.** If quality is fine on the user's monitor, no further action. If not, evaluate `--scale=3` as per-display config-file default in Phase 6.
3. **TTF font bundling** — current recommendation is "don't bundle." Some E16 themes are visually defined by their bundled font. **Recommend: lock the "don't bundle" decision now** (Aurorae cannot use it anyway); document a manual one-off install step in `report.txt` if a target theme looks wrong.
4. **`xcursorgen` subprocess vs inline implementation.** **Recommend: defer to Phase 3 spike (1–2 hours).** Subprocess is the safer default; inline removes the system-dep but adds maintenance.
5. **Maximized state Aurorae IDs.** **Recommend: lock as "do not emit maximized variants in Phase 1; revisit if a target theme visibly distinguishes them and Aurorae's fallback looks wrong."** Already documented as tech-debt-pattern.
6. **Reference window width for button binning.** **Recommend: lock as `REFERENCE_WINDOW_WIDTH = 800` constant in `analyze/buttons.py`** with a code comment; Aliens default border has been verified to bin correctly at this width.
7. **Batch-mode parallelism trigger threshold.** **Recommend: explicitly defer.** Time the user's first 100-theme batch run, decide based on wall-clock. Migration path documented in ARCHITECTURE.md §13.
8. **`metadata.json` vs `metadata.desktop` for the Aurorae sub-package.** **Recommend: emit *both* in Phase 1** to future-proof against KF6 deprecation. Marginal extra code, zero risk.

---

## Sources

### Primary (HIGH confidence)

**Ground truth on disk:**

- `/home/cstory/Downloads/e16-1.0.31/src/{iclass,borders,tclass,cursors,config,menus}.c` and `eimage.h` — E16 grammar + struct field order (`EImageBorder { left, right, top, bottom }`).
- `/home/cstory/.local/share/aurorae/themes/{Edna,Sweet-Dark,Sweet-Dark-transparent}/` — verified working FrameSvg ID set, `metadata.desktop` + optional `metadata.json` co-existence.
- Extracted `Aliens.etheme` contents — verified flat archive layout, symlinks (`fonts.cfg`, `ABOUT/aircut3.ttf`), XBM `cursor.xbm` + `cursor.xbm.mask` pairs, XLFD font strings.

**KDE / Plasma official:**

- [Aurorae window decorations (develop.kde.org)](https://develop.kde.org/docs/plasma/aurorae/) — FrameSvg element IDs, state suffixes, `metadata.desktop` schema.
- [Porting Themes to Plasma 6 (develop.kde.org)](https://develop.kde.org/docs/plasma/theme/theme-porting-to-plasma6/) — `manifest.json`, no-symlinks rule.
- [SVG elements and Inkscape (develop.kde.org)](https://develop.kde.org/docs/plasma/theme/theme-svg/) — embed raster, `preserveAspectRatio="none"`.
- [KDE/ksvg (GitHub)](https://github.com/KDE/ksvg) — FrameSvg implementation.

**PyPI version verification (Apr–May 2026):** Pillow 12.2.0, Typer 0.25.1, Click 8.3.3 (8.2.2 yanked), Ruff 0.15.12, uv 0.11.8, pytest 9.0.3, syrupy 5.1.0, pyright 1.1.409.

**Security CVEs:**

- [CVE-2007-4559 (tarfile path traversal)](https://www.securecodewarrior.com/article/traversal-bug-in-pythons-tarfile-module).
- [CVE-2025-4330 (data-filter PATH_MAX bypass)](https://www.sentinelone.com/vulnerability-database/cve-2025-4330/) — justifies mandatory `safe_extract` even on Python 3.12+.

**X11 / freedesktop:**

- [xcursorgen man page (X.Org)](https://www.x.org/releases/current/doc/man/man3/Xcursor.3.xhtml) — XCursor format, ARGB packing, hotspot semantics.
- [Cursor themes — ArchWiki](https://wiki.archlinux.org/title/Cursor_themes) — `index.theme` schema, `Inherits=` fallback.

### Secondary (MEDIUM confidence)

- [What's next for Aurorae? — Vlad Zahorodnii (2025-11-13)](https://blog.vladzahorodnii.com/2025/11/13/whats-next-for-aurorae/) — Aurorae V2 / KSvg context.
- [Non-integer scaling pixelation — KDE Discuss](https://discuss.kde.org/t/non-integer-scaling-application-style-window-decorations-pixelated-on-6-6-with-many-themes/44480).
- [tldr-pages PR #15444](https://github.com/tldr-pages/tldr/pull/15444) — `lookandfeeltool` → `plasma-apply-lookandfeel` rename.
- [KDE bug 439222](https://bugs.kde.org/show_bug.cgi?id=439222) — `[WM]` section keys in `.colors`.

### Tertiary (LOW confidence — needs validation during implementation)

- E16 cursor-name → XCursor-name mapping in PITFALLS.md Integration Gotchas — `MAX → pirate`, `KILL → pirate`, `ICONIFY → skip`, `STICK → skip` are author judgment, not verified upstream. Validate at Phase 3.
- `KColorScheme` exact required key set per `[Colors:*]` section — verified against multiple `kdeglobals` examples but not by reading `kcolorscheme.cpp` directly. Validate by writing one and applying it before declaring Phase 2 done.

---

*Research synthesis for: themey — E16 `.etheme` → KDE Plasma 6 Look-and-Feel CLI converter*
*Synthesized: 2026-05-01 — incorporates PROJECT.md corrections (`__EDGE_SCALING` order, `plasma-apply-lookandfeel` naming, Look-and-Feel `manifest.json`, mandatory `safe_extract`)*
*Ready for roadmap: yes*
