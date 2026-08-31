## Project

**themey**

themey is a local Python CLI that converts Enlightenment DR16 (E16) `.etheme` archives into installable KDE Plasma 6 Look-and-Feel packages. It reads the legacy E16 config grammar (`__BORDER`, `__ICLASS`, `__TCLASS` blocks) and emits a complete modern KDE theme — Aurorae window decoration, color scheme, wallpaper, and XCursor pointer set — bundled as a one-click Plasma Global Theme. Built for one user (chris) who wants to actually run favorite 2009-era E16 themes on Plasma 6.6.4 day-to-day.

**Core Value:** A user runs `themey aliens.etheme` and within seconds is staring at a Plasma desktop visibly themed with that 16-year-old E16 theme — Aurorae frame, matching colors, wallpaper, cursor — all installed and previewable.

### Constraints

- **Tech stack**: Python 3 (assume 3.11+, present on the system). Pillow for image manipulation. Standard library for tarfile, gzip, configparser (output INI), argparse, pathlib, xml.etree (SVG output). No heavy frameworks.
- **Compatibility**: Plasma 6.x. Linux only. Targets KWin's Aurorae decoration plugin (the standard one, included in every Plasma install).
- **Dependencies on E16**: zero runtime dependency — we read the source for grammar reference only.
- **Output discipline**: every install path is under `~/.local/share/...` so a conversion is fully reversible by deleting the named directories. No system-wide writes. No root.
- **Fidelity philosophy**: faithful where the format maps cleanly, sensible defaults where it doesn't (button grouping, missing button glyphs default to a system fallback). When the converter has to approximate, it logs to `report.txt`.

## Technology Stack

## TL;DR Recommendations
| Concern | Pick | Version | Confidence |
|---------|------|---------|------------|
| Python | CPython | 3.11+ (target 3.12 / 3.13) | HIGH |
| Image manipulation | **Pillow** | 12.2.0 | HIGH |
| 9-patch slicing | **Hand-rolled with `Image.crop`** (no library) | — | HIGH |
| 2× upscale | **`Image.resize(..., Resampling.NEAREST)`** for pixel-art borders, `LANCZOS` for photographic wallpapers | Pillow 12.2.0 | HIGH |
| Dominant color | **Pillow's `Image.quantize(method=MEDIANCUT)`** + manual swatch ranking | Pillow 12.2.0 | HIGH |
| SVG generation | **stdlib `xml.etree.ElementTree`** + explicit namespace registration | Python 3.11+ | HIGH |
| INI output | **stdlib `configparser.RawConfigParser`** with `optionxform = str` | Python 3.11+ | HIGH |
| `.desktop` writer | Custom thin writer (NOT `configparser`) | — | HIGH |
| XBM read | **Hand-rolled parser** (`generate/cursors.py`) — NOT Pillow's `XbmImagePlugin` | — | HIGH |
| XBM → XCursor | **Subprocess to `xcursorgen`** (xorg-xcursorgen package) after rasterising XBM → PNG via Pillow | system pkg | HIGH |
| CLI framework | **Typer** | 0.25.1 | HIGH |
| Project / dep manager | **uv** | 0.11.8 | HIGH |
| Distribution | **`uv tool install` / `uvx`** (pipx-compatible fallback documented) | 0.11.8 | HIGH |
| Lint + format | **Ruff** | 0.15.12 | HIGH |
| Test runner | **pytest** | 9.0.3 | HIGH |
| Snapshot tests | **syrupy** | 5.1.0 | HIGH |
| Type checker | **pyright** in `basic` mode (skip strict for v1) | 1.1.409 | MEDIUM |
| Build backend | **`hatchling`** (default for `uv init --package`) | latest | MEDIUM |
## Recommended Stack — Detail
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ (3.12 sweet spot) | Runtime | The system already has 3.11+; 3.12 brings notable `pathlib`/typing speedups; 3.11 is LTS-ish in the Linux distro world. PROJECT.md already locks "Python 3, 3.11+." |
| Pillow | 12.2.0 (Apr 1 2026) | All raster work: open PNG/JPEG/BMP, slice 9-patch borders, resize for `--scale`, sample colors, rasterize the cursor PNG frames `xcursorgen` consumes | Pillow is the only mature pure-Python raster library that handles the formats we need (PNG, JPEG fallback for wallpapers, BMP just in case) with no native build dependencies beyond libjpeg/zlib that wheels already bundle. **Correction (verified against the fixtures, 2026-08-30): Pillow's `XbmImagePlugin` does NOT read E16's cursor XBMs** — its header regex is anchored at `#define` (GIMP-authored files like Mac3D's start with a `/* Made with GIMP */` comment) and its hotspot sub-pattern `[^_]*_x_hot` cannot match multi-underscore names like `resize_h_x_hot`, which nearly every fixture uses. `generate/cursors.py` parses XBM itself (~40 lines: `#define` regex + `_bits[]` array) rather than losing the hotspot silently. |
| stdlib `xml.etree.ElementTree` | bundled | Emit `decoration.svg`, per-button SVGs, wallpaper `metadata.json` (no — that's JSON, ignore), preview HTML | See full rationale in "SVG generation" below. The decisive factor: **FrameSvg's contract is element IDs, nothing else**. We are not parsing third-party SVG, we are writing a known-shape document with known IDs. Stdlib is sufficient and removes a transitive dep. |
| stdlib `configparser.RawConfigParser` | bundled | Emit Aurorae `<name>rc`, KColorScheme `.colors` | INI is a stdlib problem. `RawConfigParser` skips `%`-interpolation (KColorScheme uses `%` in some font names), and `optionxform = str` preserves case (KDE keys are case-sensitive: `BackgroundNormal`, `LeftButtons`, etc.). |
| stdlib `tarfile` + `gzip` | bundled | Read `.etheme` archives; write the Look-and-Feel `.tar.gz` if we ever ship one (probably not — we install directly to `~/.local/share/...`) | One less dep. Both are battle-tested. |
| Typer | 0.25.1 (Apr 30 2026) | CLI framework | See "CLI framework" below. |
| uv | 0.11.8 (Apr 27 2026) | Package + project manager | 10–100× faster than pip; manages Python toolchain itself; `uv init --package --build-backend hatchling` produces the exact `src/`-layout single-file CLI we want. The project is "Production/Stable" per Astral. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 (Apr 7 2026) | Test runner | Always. |
| syrupy | 5.1.0 (Jan 25 2026) | Snapshot tests for generated SVG/INI/`.desktop`/`.colors` text output | Use the `AmberSnapshotExtension` (default) for INI/text and the single-file extension for full-document SVG diffs. Critical for this project: the whole point of the converter is producing exact byte-stable text outputs that KDE will parse. Syrupy beats `pytest-snapshot` on Git-friendliness and tooling. |
| ruff | 0.15.12 (Apr 24 2026) | Linter + formatter | One tool replaces flake8 + isort + black + pyupgrade + pydocstyle. Run via `uv tool` or `uvx ruff`. |
| pyright | 1.1.409 (Apr 23 2026) | Static type check | Use `basic` mode. mypy is fine if you prefer it but pyright's `basic` reports are more forgiving and the CLI is faster — better fit for a one-author tool. |
| hatchling | bundled by uv default | PEP 517 build backend | `uv init --package` defaults to it; nothing to configure. |
| `xorg-xcursorgen` (system pkg, not pip) | distro-supplied | Convert PNG cursor frames → XCursor binary | Subprocess invocation. See "XBM → XCursor" below. |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| `uv` | Project + venv + Python toolchain | `uv sync`, `uv run themey ...`, `uv tool install .` |
| `uvx` | Run CLIs without installing globally | `uvx ruff check`, `uvx pyright`, `uvx pytest` |
| `ruff format` | Format on save | Equivalent to black; `pyproject.toml` `[tool.ruff]` block |
| `ruff check --fix` | Lint with autofix | Enable rule sets: `E,W,F,I,B,C4,UP,RUF` |
| `pyright --watch` | IDE-style feedback during dev | Optional |
## Per-Question Detailed Recommendations
### 1. Image manipulation — Pillow
- **Wand (ImageMagick bindings)** — adds a system-level ImageMagick dependency; overkill for our four operations (open, crop, resize, quantize). Pillow handles all of them with no native deps beyond what wheels bundle.
- **OpenCV** — 50+ MB install for what is fundamentally `crop()` and `resize()`. Color spaces are BGR by default which trips up everyone. No XBM reader.
- **scikit-image** — research-grade; brings NumPy + SciPy as transitive deps; same overkill argument.
- `Image.open()` accepts PNG, XBM, JPEG, BMP — all the formats E16 themes contain.
- `Image.crop((l, t, r, b))` is exactly what 9-patch slicing needs. Given `__EDGE_SCALING` borders `(left_w, right_w, top_h, bottom_h)`, we crop nine rectangles directly. **Recommendation: do NOT use the `ninepatch` PyPI package** — it's targeted at Android `.9.png` files (which encode slice points in 1-px metadata borders); we have raw rectangles from the E16 config and a hand-rolled `slice9(img, lw, rw, th, bh)` is ~15 lines.
- `Image.resize((w, h), Image.Resampling.NEAREST)` for the 2× upscale of pixel-art borders. **Use NEAREST, not LANCZOS, for theme borders** — these are 13–30 px pixel-art images and bilinear/lanczos will blur them. Reserve LANCZOS for wallpaper rescale.
- `Image.quantize(colors=N, method=Image.Quantize.MEDIANCUT)` for dominant color extraction (see Color Extraction below).
### 2. SVG generation — stdlib `xml.etree.ElementTree`
- **lxml 6.1.0** — strictly faster and has a friendlier namespace API, but adds a ~5 MB compiled C dep for a use-case that emits maybe 10 small SVG files per theme. Performance is irrelevant here.
- **svgwrite 1.4.3** — **explicitly inactive** ("No new features will be added, just bugfixes" — last release July 2022). Avoid for new projects.
- **drawsvg 2.4.1** (Jan 4 2026) — actively maintained, but it's a *drawing* DSL (think: a higher-level shape API). It abstracts the element tree, which works against us: **FrameSvg cares about exact element IDs we set on `<g>` and `<image>` nodes**. We need direct DOM control, not a drawing abstraction.
### 3. INI output — stdlib `configparser.RawConfigParser`
### 4. XBM → XCursor — subprocess to `xcursorgen` (with Pillow rasterization)
- **clickgen 2.2.5** (Jun 9 2024) — most prominent Python xcursor library. *No releases in the past 12 months*; Snyk advisor explicitly flags it as "low attention from maintainers." It also accepts only PNG input, so we'd still need Pillow to convert XBM → PNG first. Adds a transitive dep for what subprocess does in 5 lines.
- **win2xcur 0.2.0** (Jan 8 2026) — actively maintained but converts *Windows* `.cur`/`.ani` files, not XBM and not PNG sequences. Wrong tool.
- **Pillow XCursor support** — does not exist. Pillow can read/write XBM but has no XCursor plugin.
- **`xcursorgen`** (xorg-xcursorgen system package) — the canonical tool. Reads a config file (`<size> <xhot> <yhot> <png_path> [delay_ms]`) and writes a binary XCursor file. Stable, ubiquitous on Linux distros, present on every KDE workstation.
# As built: 1. hand-rolled XBM parser (image + mask) — see the XBM read
# correction above; 2. rasterize through Pillow into RGBA, upscale at
# fixed x1/x2/x3 (NEAREST) — independent of --scale, which is a border/
# image factor, not a cursor one; 3. write PNG frames per nominal size;
# 4. build an xcursorgen config: "32 4 4 /tmp/foo.png"; 5. subprocess to
# xcursorgen
### 5. CLI framework — Typer
- **argparse (stdlib)** — fine but verbose, no auto-help-from-docstrings, no auto-completion shell scripts. A lot of boilerplate for `themey <theme.etheme>` + `themey --all <dir>`.
- **Click 8.3.3** — the rock-solid choice. Excellent. Decorator-based.
- **Typer 0.25.1** — built *on* Click, but uses Python type hints to derive arguments. For a single-author tool with a tiny CLI surface, Typer is the most code-per-feature-light option:
### 6. Color extraction — Pillow `quantize(method=MEDIANCUT)` + manual palette ranking
- **colorthief 0.2.1** — last release **2017**. Unmaintained, uses MMCQ (median-cut variant) under the hood. We can do the same thing with Pillow directly with no extra dep.
- **colorgram.py 1.2.0** — last release **2018**. Same story.
- **scikit-learn `KMeans`** — produces marginally better perceptual results (per several blog comparisons) but pulls in NumPy + SciPy + scikit-learn (~80 MB) for one function. Not worth it.
- **Hand-rolled k-means in NumPy** — overkill for a single-author tool.
### 7. Packaging / distribution — uv + pyproject.toml + src/ layout, distributed via `uv tool install`
- Local dev: `uv sync && uv run themey aliens.etheme`
- Personal install: `uv tool install .` → `themey` lands on PATH
- If sharing with others later: `uv tool install git+https://github.com/cstory/themey` — works without publishing to PyPI
### 8. Linting + formatting — Ruff
### 9. Testing — pytest + syrupy snapshots
- syrupy's `.ambr` files are **diff-friendly** (one file per test module, clear separators between cases) — a SVG diff for `decoration.svg` is readable in `git diff`.
- syrupy fails on missing snapshots (pytest-snapshot silently creates them, which can mask test issues).
- syrupy is actively maintained (5.1.0, Jan 25 2026); pytest-snapshot is more sporadically updated.
- Fixture: a canned subset of E16 themes in `tests/fixtures/` (commit small ones like `Aliens`).
- Unit tests: parser grammar, button binning algorithm, color sampling.
- Snapshot tests: full `decoration.svg`, full Aurorae `<name>rc`, full `.colors`, full `metadata.desktop` for at least 3 representative themes. When KDE format expectations evolve, regenerate with `pytest --snapshot-update`.
- Binary outputs (XCursor file, look-and-feel `.tar.gz`) — assert structural properties (file exists, size > N, `xcursorgen --version` produced it, tarfile contains expected entries) rather than byte-snapshotting.
### 10. Type checking — pyright basic
- **Strict mypy** is overkill — too much noise from third-party stubs (Pillow's stubs are decent but not perfect), spends time on questions that don't matter for a 2k-line tool.
- **Skip type checking** — leaves easy bugs in (typos in dict keys, `None` vs `Path`, etc.).
- **pyright basic** — middle path. Catches the obvious mistakes, doesn't fight you over generics. `uvx pyright` runs in <2s on a project this size.
## Installation
# Bootstrap the project (one time)
# Add runtime deps
# Add dev deps
# System dep (not via pip)
# sudo apt install xcursorgen         # Debian/Ubuntu (in x11-apps)
# sudo dnf install xorg-x11-apps      # Fedora
# Verify
# Personal install onto PATH
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Pillow | Wand (ImageMagick) | If you needed exotic filters or vector rasterization Pillow doesn't have. We don't. |
| Pillow | OpenCV | If you needed CV operations (feature detection, contour finding) for fancier color sampling. Probably never. |
| stdlib `xml.etree` | lxml | If you started parsing third-party SVGs with complex namespaces (you're not — you're emitting). Or if you needed XPath. |
| stdlib `configparser` | `iniparse` / hand-rolled | If KDE introduces format we can't represent. Unlikely; stdlib has handled KDE configs for 15+ years. |
| `xcursorgen` subprocess | `clickgen` | If `xcursorgen` weren't ubiquitously available. It is. |
| Typer | Click | If you want to avoid a tiangolo dep on principle, or want `Click`'s plugin system. Click is equally good. |
| Typer | argparse | If you want zero non-stdlib deps. Acceptable tradeoff; ~100 more lines of CLI code. |
| Pillow quantize | scikit-learn KMeans | If color quality becomes a complaint after V1. NumPy/sklearn are heavy; defer until need is proven. |
| uv | Poetry | If you have existing Poetry muscle memory. Poetry is fine, just slower and more opinionated. |
| uv tool install | pipx | If a user doesn't have uv. Document as fallback. |
| pyright basic | mypy strict | If contributions arrive and you want stronger guarantees. |
| syrupy | pytest-regressions | If you specifically need binary diff support (we don't — binary outputs use structural assertions). |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **svgwrite** | Maintainer-declared inactive ("no new features, just bugfixes" since July 2022) | stdlib `xml.etree.ElementTree` |
| **drawsvg** for FrameSvg output | Drawing-DSL abstraction fights the "set this exact ID on this element" requirement that FrameSvg imposes | stdlib `xml.etree.ElementTree` |
| **colorthief** (PyPI) | Last release Feb 2017 — unmaintained for 9 years | Pillow's `Image.quantize(method=MEDIANCUT)` |
| **colorgram.py** | Last release Dec 2018 — unmaintained | Pillow's `Image.quantize` |
| **clickgen** | No release in 12+ months; Snyk flags low maintainer attention; would still need Pillow for XBM→PNG conversion first | `xcursorgen` subprocess |
| **win2xcur** | Wrong direction — converts Windows `.cur` files, not XBM/PNG | `xcursorgen` subprocess |
| **`ninepatch` PyPI package** | Targets Android `.9.png` metadata-encoded slice points; we have explicit slice values from E16 config | Hand-rolled `Image.crop` |
| **`configparser.ConfigParser` (default mode)** | Default `optionxform = str.lower` mangles KDE's case-sensitive keys; `BasicInterpolation` chokes on `%` in values | `RawConfigParser` with `optionxform = str` |
| **`configparser` for `.desktop` files** | Localized keys `Name[de]=Foo` look like sections to configparser | Hand-rolled writer (~20 lines) |
| **`Image.Resampling.LANCZOS` for border upscaling** | Blurs pixel-art theme borders | `Image.Resampling.NEAREST` for border 2×; LANCZOS only for wallpapers |
| **mypy strict for v1** | Overkill for a one-author tool; fighting third-party stubs is a time sink | pyright `basic` mode |
| **Poetry** | Slower, more opinionated, less batteries-included than uv in 2026 | uv |
| **pip directly** | Slower than uv; doesn't manage Python toolchains; no project lockfile workflow | uv |
## Stack Patterns by Variant
- Add `[project.urls]` with repo URL
- Run `uv publish` (uv has a publish subcommand that wraps Twine)
- Bump `requires-python = ">=3.11"` to `>=3.12` if you've been using 3.12-only typing syntax
- Snapshot tests will fail loudly. Update `aurorae/decoration.py` and regenerate snapshots.
- Pin Plasma 6.x minimum in `metadata.desktop` (`X-Plasma-API-Version`) and gate at install time in `themey doctor`.
- Pillow handles streaming via `Image.open()` lazy load. No change needed.
- No change. XCursor format is rendered by KWin compositor regardless of Wayland/X11. Aurorae works on both.
## Version Compatibility
| Package | Compatible with | Notes |
|---------|-----------------|-------|
| Pillow 12.2.0 | Python ≥ 3.10 | Drops 3.9 in 12.x. Our 3.11+ is fine. |
| Typer 0.25.1 | Python ≥ 3.10, Click 8.3+ | Pulls Click as transitive. |
| Click 8.3.3 | Python ≥ 3.10 | (Note: 8.2.2 was yanked — pin `click>=8.3,!=8.2.2` if pinning Click directly.) |
| uv 0.11.8 | Self-managed Python toolchain | Works on Linux/macOS/Windows; Linux is our target. |
| pytest 9.0.3 | Python ≥ 3.10 | Major-version bump from 8.x → 9.x in 2026; syrupy 5.1.0 is compatible. |
| syrupy 5.1.0 | Python ≥ 3.10, pytest ≥ 7 | Active. |
| Ruff 0.15.12 | All supported Python versions | Self-contained Rust binary; no Python ABI concerns. |
| pyright 1.1.409 | Python ≥ 3.8 (target) | Node-bundled binary; runs out-of-process. |
| `xcursorgen` (system) | Any Linux distro with X.org | Stable format since 2002; no version constraints in practice. |
| KDE Plasma | 6.0 → 6.6.4 (developed against), 6.x going forward | Aurorae FrameSvg format is stable across the Plasma 6 line per PROJECT.md. |
## Sources
- [Pillow 12.2.0 (PyPI)](https://pypi.org/project/Pillow/) — Apr 1 2026
- [Click 8.3.3 (PyPI)](https://pypi.org/project/click/) — Apr 22 2026 (note 8.2.2 yanked)
- [Typer 0.25.1 (PyPI)](https://pypi.org/project/typer/) — Apr 30 2026
- [Ruff 0.15.12 (PyPI)](https://pypi.org/project/ruff/) — Apr 24 2026
- [uv 0.11.8 (PyPI)](https://pypi.org/project/uv/) — Apr 27 2026
- [pytest 9.0.3 (PyPI)](https://pypi.org/project/pytest/) — Apr 7 2026
- [syrupy 5.1.0 (PyPI)](https://pypi.org/project/syrupy/) — Jan 25 2026
- [pyright 1.1.409 (PyPI)](https://pypi.org/project/pyright/) — Apr 23 2026
- [lxml 6.1.0 (PyPI)](https://pypi.org/project/lxml/) — Apr 18 2026
- [drawsvg 2.4.1 (PyPI)](https://pypi.org/project/drawsvg/) — Jan 4 2026
- [svgwrite 1.4.3 (PyPI, INACTIVE)](https://pypi.org/project/svgwrite/) — last release Jul 2022
- [colorthief 0.2.1 (PyPI, UNMAINTAINED)](https://pypi.org/project/colorthief/) — last release Feb 2017
- [clickgen 2.2.5 (PyPI)](https://pypi.org/project/clickgen/) — Jun 9 2024 (no recent release)
- [win2xcur (GitHub)](https://github.com/quantum5/win2xcur) — 0.2.0 Jan 8 2026
- [KDE Aurorae window decorations (develop.kde.org)](https://develop.kde.org/docs/plasma/aurorae/) — FrameSvg element ID structure: `decoration-{left,right,top,bottom,topleft,topright,bottomleft,bottomright,center}` plus `-inactive` / `-maximized` / `-opaque` variants
- [KDE/ksvg (GitHub)](https://github.com/KDE/ksvg) — FrameSvg implementation; confirms 9-patch rendering by named element lookup
- [KDE Plasma Style quickstart (develop.kde.org)](https://develop.kde.org/docs/plasma/theme/quickstart/) — recommends embedding raster images in SVG (Inkscape `Effects > Images > Embed All Images`)
- [Pillow image-file-formats (XBM section)](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) — confirms XBM read/write with hotspot info
- [xcursorgen(1) Arch manual](https://man.archlinux.org/man/extra/xorg-xcursorgen/xcursorgen.1.en) — config format `<size> <xhot> <yhot> <png_path> [delay_ms]`
- [Python configparser docs](https://docs.python.org/3/library/configparser.html) — `RawConfigParser`, `optionxform`, `interpolation=None`
- [uv documentation (Astral)](https://docs.astral.sh/uv/) — uv tool, uvx, project init
- [syrupy docs](https://syrupy-project.github.io/syrupy/) — snapshot extension, Amber format
- [Pillow vs alternatives for color quantization (BVDART)](https://bvdart.nl/en/articles/dominant-color-extraction-in-practice) — practical comparison of Pillow median-cut vs k-means
- [QuantizeImageMethods comparison repo (Chadys)](https://github.com/Chadys/QuantizeImageMethods) — empirical comparison of Pillow methods vs sklearn k-means
- [uvx vs pipx (BSWEN, Mar 2026)](https://docs.bswen.com/blog/2026-03-05-uvx-vs-pipx/) — 2026 perspective on uv as pipx replacement
- [stdlib etree vs lxml (bjoernricks)](https://bjoernricks.github.io/posts/python/stdlib-etree-vs-lxml-etree/) — namespace handling differences
- [Snapshot testing with syrupy (Simon Willison TIL)](https://til.simonwillison.net/pytest/syrupy) — Amber format for text outputs

## Conventions

**Module style**

- `from __future__ import annotations` at the top of every module; `X | None`, not `Optional[X]`.
- Every module opens with a docstring that states what it does and names the
  contract it satisfies — the IDs KDE matches on, the invariant it upholds, the
  pitfall it avoids. Read those docstrings before editing; they carry the
  reasoning the code alone does not.
- Module-level `log = logging.getLogger(__name__)`. `log.setup_logging()` runs
  once, in the CLI.
- Errors are typed per subsystem: `UnsafeArchiveError`, `InstallError`,
  `RenderError`, `ApplyError`. Raise those, not bare `Exception`.

**Data**

- `ir.Theme` and its members are frozen dataclasses. `Theme.notes` is the one
  mutable field — the analysis stage appends fidelity notes there, and
  `report.py` categorizes them by prefix.
- `theme.asset_root` is valid only inside the `with extract(...)` block. Never
  read it after the block closes; `pipeline.py` documents the lifecycle.
- Install paths come from `paths.py`, which reads `os.environ` at call time
  (not import time) so tests can monkeypatch `XDG_DATA_HOME`.

**Output**

- `RawConfigParser` with `optionxform = str` for KDE INI; a hand-rolled writer
  for `.desktop` files.
- `Image.Resampling.NEAREST` for border art by default. The ONE carve-out:
  the opt-in quality path (`--upscale quality`, QML-backend-only) — hqx in
  `images/hqx.py`, and `upscale.py`'s quality mode may LANCZOS-*downsample*
  hqx(ceil(scale)) output to a fractional target. No other LANCZOS under
  `src/themey/images/`, and never on raw pixel art.
- Everything is written under `$XDG_DATA_HOME`, staged first and installed with
  `os.replace`. No system paths, no root.

**Tests**

- pytest with the `fake_home` fixture for anything that touches install paths.
- Real themes in `tests/fixtures/` are the canaries: Aliens, e13, LiteGnome,
  Mac3D, OPENSTEP. Malicious archives cover the extract validator.
- `tests/test_svg_rc_invariant.py` and the phash snapshots in
  `tests/snapshots/visual/` guard rendering. A phash diff means the pixels
  moved — regenerate only when the change is intended and verified.
- Verify with `uv run pytest`, `uv run ruff check src/`, `uv run pyright src`.

## Architecture

Pipeline: `.etheme` → ingest → analyze → generate → install → report + preview.
`pipeline.convert()` composes it; `cli.py` is the only entry point.

Two backends. **`qml` is the default** (chris, 2026-08-30): a KWin/Decoration
KPackage (`generate/qmldeco/`) installed under
`~/.local/share/kwin/decorations/themey_<slug>/` and loaded by the v1 Aurorae
plugin `org.kde.kwin.aurorae` — it replays E16's part model 1:1 (unclamped
borders, text-sized title plaques, side-border button stacks, theme TTFs).
The legacy SVG backend stays behind `--backend svg` as an escape hatch and
receives no fidelity work.

| Package | Role |
|---------|------|
| `etheme/` | `archive.py` (validating tar extract), `lex.py`, `parse.py`, `ast.py` — the E16 grammar front end |
| `analyze/` | AST → frozen `ir.Theme`: iclass resolution, state collapse, button binning, coordinate math, borders, `fonts.py` (__FONTS scan), `colors.py` (median-cut sampling of the theme's own border art into a full 8-group `ColorScheme` + the 4-field `[WM]` active/inactive background+foreground set, WCAG-AA-guarded) |
| `images/` | `ninepatch.py`, `opaque.py`, `upscale.py` (`upscale_part`: scale_px-dim targets, nearest/quality modes), `hqx.py` (opt-in quality scaler), `embed.py` — raster primitives, NEAREST default |
| `generate/qmldeco/` | DEFAULT backend: `theme_js.py` (part model, `SHADE_BUTTON_MODES`), `resolver.py` (E16 geometry, Python mirror), `actions.py`, `package.py`, `runtime/` (4 verbatim QML/JS files) |
| `generate/` (rest) | SVG backend: `aurorae.py` orchestrates `decoration_svg.py`, `aurorae_rc.py`, `aurorae_meta.py`, `button_svg.py`, `composite.py` |
| `generate/colors.py` | `.colors` writer — the 13-group/12-key Breeze-shaped file census; sampled colors from `analyze/colors.py`, semantic foregrounds + ColorEffects verbatim from Breeze stock |
| `generate/wallpaper.py` | One Plasma wallpaper package per E16 background image (`WallpaperPackage`); PNG/JPEG/BMP copied through at real dimensions, everything else re-saved as PNG; `pick_default` ranks by area for the bundle |
| `generate/cursors.py` | E16 `__CURSOR` → XCursor pointer theme via the hand-rolled XBM parser + `xcursorgen`; modern Plasma 6.6 names canonical, legacy X11 names as symlinks |
| `generate/lookandfeel.py` | Plasma Global Theme (Look-and-Feel) bundle writer — `metadata.json` + `contents/defaults`, one conditional INI group per artifact this conversion actually deployed |
| root modules | `ir.py` (IR), `paths.py` (XDG install roots), `install.py` (atomic deploy — `deploy` for package dirs, `deploy_file` for single files like `.colors`), `report.py`, `preview.py`, `kwin.py`, `render.py`, `apply.py`, `external.py` (xcursorgen wrapper), `slug.py` (naming contract), `log.py` |

**Naming contract.** Every Global-Theme artifact for one conversion derives
from `slug.plugin_id(theme.name)` = `themey_<slug>`, deliberately reused
across namespaces so `themey apply <name>` can resolve any of them: it is
the QML decoration KPackage dir name AND kwinrc `theme=` value
(`kwin/decorations/`), the Look-and-Feel bundle's `KPlugin.Id`
(`plasma/look-and-feel/`), and the `.colors` stem / `[General]
ColorScheme=` value (`color-schemes/`) — three different namespaces, same
string, on purpose. `slug.wallpaper_id(name, stem)` widens it to
`themey_<slug>_<stem-slug>` (one wallpaper package per source image,
hyphens left alone since these ids are never QML/JS identifiers).
`slug.cursor_theme_dir(name)` narrows it to `themey_<slug>-cursors` (an
XCursor theme has no KPlugin id; the directory name itself is the
`kcminputrc cursorTheme=` value). `paths.py` gained one XDG root per new
namespace: `color_schemes()`, `wallpapers()`, `cursor_themes()` (XCursor themes go
to `~/.icons`, NOT `$XDG_DATA_HOME/icons` — libXcursor/the cursor KCM on
stock Kubuntu never scan the XDG dir; verified live 2026-08-31), `look_and_feel()`, alongside the
existing `aurorae_themes()`/`kwin_decorations()`.

**`apply.py`'s global flow.** `apply_full` (the CLI default) is a superset
of the original deco-only `apply`: verify both the Look-and-Feel bundle and
the QML decoration package are installed, snapshot the pre-themey baseline
once (`kdeglobals [Themey] PrevLookAndFeelPackage` mirrors kdeglobals
`[KDE] LookAndFeelPackage`; kwinrc `ThemeyPrevDeco` packs
`library|theme|BorderSize`, both `@unset`-sentineled for an absent key and
written only the first time so a second `apply` never clobbers the real
baseline with an already-themey'd one; `kdeglobals [Themey] PrevColorScheme`
snapshots the user-layer `[General] ColorScheme` the same way when a themey
scheme is installed), run `plasma-apply-lookandfeel -a
themey_<slug>` (never `--resetLayout`), then `plasma-apply-colorscheme
themey_<slug>` — REQUIRED, not belt-and-braces: verified live on Plasma
6.6.6 (2026-08-31) that `plasma-apply-lookandfeel -a` does NOT apply the
bundle's color scheme past an explicit user-layer `ColorScheme` (it updated
kcminputrc's cursor but left even `kdedefaults/kdeglobals` on the old
scheme) — re-assert the decoration keys via
the same `_write_deco` the deco-only path uses (required even though the
LnF apply already wrote deco defaults — those land in the
`~/.config/kdedefaults/` layer, and only an explicit user-layer write is
guaranteed to win), then `plasma-apply-wallpaperimage -f tile` if the
bundle's default wallpaper package's `X-Themey-FillMode` is `tiled`
(Plasma's Image wallpaper plugin doesn't read fill-mode from the package
itself — the `tile` token itself is `apply.py`'s own
`_WALLPAPER_TILE_FILL_MODE`, flagged in its source comment as
provisionally chosen and not yet live-verified against a real Plasma 6.6
session), and one `qdbus` reconfigure last. `themey apply --revert` reads
the markers back, reapplies the recorded Look-and-Feel package (no
Breeze special-case — a real baseline is typically a third-party theme,
e.g. chris's `com.github.vinceliuice.MacVentura-Dark`), restores the deco
triple and button layout, then clears the markers it actually restored; a
failure to reapply the recorded package does NOT abort the rest of the
restore, and `PrevLookAndFeelPackage` is deliberately kept in that one case
so a later `--revert` can retry just the theme restore (`PrevColorScheme`
gets the same keep-on-failure treatment; its `@unset` case deletes the
user-layer key so the restored LnF's kdedefaults takes over). No markers present
is a friendly no-op, not an error. `themey apply Breeze` remains the
older, deco-only revert path (decoration + button layout only), unchanged
by any of this.

**External-tool pattern (`external.py`).** `xcursorgen` is load-bearing —
there is no pure-Python XCursor writer — so callers check
`xcursorgen_available()` first and skip the whole cursor stage with a
`cursors:` note when it's absent, mirroring the `xdg-open` graceful-skip
already there for preview auto-open. `run_xcursorgen` doesn't trust the
return code alone: xcursorgen can exit 0 and write nothing, so it also
verifies the output file exists and is non-empty before returning, raising
`XcursorgenError` (stderr tail attached) otherwise. `apply.py`'s
`_run_checked` follows the same shape for `plasma-apply-lookandfeel` /
`plasma-apply-wallpaperimage`.

**Report prefixes.** `report.py` categorizes `theme.notes` by string
prefix into the report's Approximated section: `aurorae_rc:`, `bundle:`,
`colors:`, `composite:`, `cursors:`, `qmldeco:`, `wallpaper:` are surfaced
first (layout/subsystem decisions), ahead of the per-state E16-collapse
notes that have no prefix.

QML-backend contracts:

1. **resolver.js and resolver.py are the same algorithm** (E16
   `BorderWinpartCalc`: Q10 percents, inclusive bottom-right anchors,
   re-centering max clamps, `__FLAG_TITLE`+`MAX_WIDTH 0` text sizing). All
   math runs in E16 REFERENCE px; ref→output conversion goes through the
   shared `scale_px(v, s) = floor(v*s + 0.5)` (half-up in BOTH languages —
   Python `round()` is banker's, `Math.round()` half-up) and the final
   multiply is EDGE-based (`x_out = scale_px(x)`, `w_out = scale_px(x+w) -
   x_out`) so adjacent parts stay seamless at fractional scales; identical
   to `v*scale` at integer scales. Scale may be fractional ([1,3], 2
   decimals) — **QML-backend-only**; svg/both hard-error. Change both
   resolvers together and bump `RUNTIME_VERSION` (currently 2);
   `tests/test_qmldeco_geometry.py` pins e13 ground truth (KILL
   40x38@(0,0), stack x=9, plaque = textwidth+25) at scale 2 and 1.5.
2. **theme.js is pure data** (`var theme = {...}` — no runtime I/O/XHR);
   image state fallbacks and origin-topology validation happen at generate
   time. Geometry fields are UNSCALED ref px; `borders`/`insets`/`pixelSize`
   are pre-scaled via `scale_px`, and exported art targets the same
   `scale_px` dims (`upscale_part`) so BorderImage insets always match the
   shipped PNGs.
3. **KPlugin Id == package dir name == kwinrc `theme=`** (`slug.plugin_id`,
   `themey_<slug>`). QML applies must NOT write BorderSize or
   ButtonsOnLeft/Right — the theme draws its own buttons and unclamped
   borders.

Three contracts govern the SVG backend's theme:

1. **Aurorae matches by element ID.** `decoration.svg` carries all 36
   `decoration-*` IDs (nine regions × active / inactive / maximized /
   maximized-inactive) plus `hint-*` margin rects. Missing maximized groups
   render a blank title bar on maximized windows.
2. **SVG and rc must agree.** Strip thicknesses in `decoration.svg` and
   `Border*` / `TitleHeight` in `<name>rc` both come from
   `decoration_svg.strip_thicknesses()`. `tests/test_svg_rc_invariant.py`
   enforces it.
3. **Geometry is measured, not declared.** Part images render as true
   9-patches per `__EDGE_SCALING` (`composite._resize_with_edge_scaling`:
   caps pinned, middles stretch). Side zones that host button stacks trim
   to their opaque art span (`images/opaque.py`); TitleHeight trims to the
   title image's opaque rows (shaped notches stay transparent in the band);
   buttons get per-code aspect-true dims (`composite.button_geometry`)
   fitted under the trimmed title. `declared_zone_extents` keeps the raw
   E16 zones for art scans.

`kwin.py` is a leaf module (no themey imports) holding the KWin facts — plugin
IDs and the per-`BorderSize` clamp brackets from the Plasma 6.6.6 Aurorae
sources — so `report` and `render` can both use it without an import cycle. Both
plugins clamp side and bottom borders to the selected bracket, which is why wide
corner art is folded into the title band instead.

Visual verification: `themey render` (nested headless KWin) is the truth —
`--plugin qml` for the default backend, `legacy`/`v2` for SVG.
`scripts/render_review.py` is a fast SVG approximation and can disagree with
KWin; it knows nothing about the QML backend.

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.

