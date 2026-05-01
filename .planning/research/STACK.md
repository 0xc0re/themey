# Stack Research

**Domain:** Single-author Linux Python 3 CLI; image manipulation + XML/INI generation + binary cursor packaging for KDE Plasma 6 themes
**Researched:** 2026-05-01
**Confidence:** HIGH overall (all version numbers verified against PyPI on research date; KDE FrameSvg behavior verified against `develop.kde.org/docs/plasma/aurorae/` and the KDE/ksvg source repo)

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
| XBM read | **Pillow** (built-in `XbmImagePlugin`) | 12.2.0 | HIGH |
| XBM → XCursor | **Subprocess to `xcursorgen`** (xorg-xcursorgen package) after rasterising XBM → PNG via Pillow | system pkg | HIGH |
| CLI framework | **Typer** | 0.25.1 | HIGH |
| Project / dep manager | **uv** | 0.11.8 | HIGH |
| Distribution | **`uv tool install` / `uvx`** (pipx-compatible fallback documented) | 0.11.8 | HIGH |
| Lint + format | **Ruff** | 0.15.12 | HIGH |
| Test runner | **pytest** | 9.0.3 | HIGH |
| Snapshot tests | **syrupy** | 5.1.0 | HIGH |
| Type checker | **pyright** in `basic` mode (skip strict for v1) | 1.1.409 | MEDIUM |
| Build backend | **`hatchling`** (default for `uv init --package`) | latest | MEDIUM |

---

## Recommended Stack — Detail

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11+ (3.12 sweet spot) | Runtime | The system already has 3.11+; 3.12 brings notable `pathlib`/typing speedups; 3.11 is LTS-ish in the Linux distro world. PROJECT.md already locks "Python 3, 3.11+." |
| Pillow | 12.2.0 (Apr 1 2026) | All raster work: open PNG/XBM, slice 9-patch borders, resize for `--scale`, sample colors, write the cursor PNG frames `xcursorgen` consumes | Pillow is the only mature pure-Python raster library that handles all four input formats we need (PNG, XBM, JPEG fallback for wallpapers, BMP just in case). XBM support is built-in via `PIL.XbmImagePlugin` — exactly what E16's `artwork/cursors/*.xbm` files need. No native build dependencies beyond libjpeg/zlib that wheels already bundle. |
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

---

## Per-Question Detailed Recommendations

### 1. Image manipulation — Pillow

**Pick:** Pillow 12.2.0. **Confidence: HIGH.**

**Why not the alternatives:**
- **Wand (ImageMagick bindings)** — adds a system-level ImageMagick dependency; overkill for our four operations (open, crop, resize, quantize). Pillow handles all of them with no native deps beyond what wheels bundle.
- **OpenCV** — 50+ MB install for what is fundamentally `crop()` and `resize()`. Color spaces are BGR by default which trips up everyone. No XBM reader.
- **scikit-image** — research-grade; brings NumPy + SciPy as transitive deps; same overkill argument.

**What Pillow gives us specifically for this project:**
- `Image.open()` accepts PNG, XBM, JPEG, BMP — all the formats E16 themes contain.
- `Image.crop((l, t, r, b))` is exactly what 9-patch slicing needs. Given `__EDGE_SCALING` borders `(left_w, right_w, top_h, bottom_h)`, we crop nine rectangles directly. **Recommendation: do NOT use the `ninepatch` PyPI package** — it's targeted at Android `.9.png` files (which encode slice points in 1-px metadata borders); we have raw rectangles from the E16 config and a hand-rolled `slice9(img, lw, rw, th, bh)` is ~15 lines.
- `Image.resize((w, h), Image.Resampling.NEAREST)` for the 2× upscale of pixel-art borders. **Use NEAREST, not LANCZOS, for theme borders** — these are 13–30 px pixel-art images and bilinear/lanczos will blur them. Reserve LANCZOS for wallpaper rescale.
- `Image.quantize(colors=N, method=Image.Quantize.MEDIANCUT)` for dominant color extraction (see Color Extraction below).

### 2. SVG generation — stdlib `xml.etree.ElementTree`

**Pick:** stdlib `xml.etree.ElementTree`. **Confidence: HIGH.**

**Why not the alternatives:**
- **lxml 6.1.0** — strictly faster and has a friendlier namespace API, but adds a ~5 MB compiled C dep for a use-case that emits maybe 10 small SVG files per theme. Performance is irrelevant here.
- **svgwrite 1.4.3** — **explicitly inactive** ("No new features will be added, just bugfixes" — last release July 2022). Avoid for new projects.
- **drawsvg 2.4.1** (Jan 4 2026) — actively maintained, but it's a *drawing* DSL (think: a higher-level shape API). It abstracts the element tree, which works against us: **FrameSvg cares about exact element IDs we set on `<g>` and `<image>` nodes**. We need direct DOM control, not a drawing abstraction.

**Why stdlib wins for FrameSvg specifically:**

KDE's FrameSvg renderer (verified against `develop.kde.org/docs/plasma/aurorae/` and `github.com/KDE/ksvg`) works like this:
1. Open the SVG.
2. Look up elements by ID: `decoration-left`, `decoration-right`, `decoration-top`, `decoration-bottom`, `decoration-topleft`, `decoration-topright`, `decoration-bottomleft`, `decoration-bottomright`, `decoration-center`.
3. Render each element into the corresponding 9-patch region of the window frame.
4. Optional state-prefixed variants: `decoration-inactive-*`, `decoration-maximized-*`, `decoration-opaque-*`. If `-inactive` is missing, the active set is reused.

**The contract is "an element with this ID exists and has a sensible bounding box."** That's it. We don't need any exotic SVG features. Stdlib `ElementTree` handles this in ~30 lines of code per SVG.

**The one stdlib gotcha to avoid** — namespace prefix mangling. By default `xml.etree.ElementTree` will serialize the SVG default namespace as `ns0:`, which Inkscape and some renderers dislike. Fix: register the namespace as `""` before serializing:

```python
ET.register_namespace("", "http://www.w3.org/2000/svg")
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
```

**Embedding raster PNG inside the SVG (per AURORAE-03):** Use `<image xlink:href="data:image/png;base64,..." />` with the PNG bytes base64-encoded inline. Verified to work with FrameSvg via the embedded-images Inkscape pattern KDE Plasma styles use (the develop.kde.org Plasma Style quickstart explicitly recommends "embed imported raster images"). Each of the 9 region elements is a `<g id="decoration-topleft">` containing a clipped `<image>` referencing the same data URI but with a viewBox/clip-path showing only the relevant slice. Alternative pattern: pre-slice into 9 PNGs and embed each as a separate `<image>` data URI inside its own `<g>` — simpler code, slightly larger SVG (because the raw bytes are duplicated in shared regions for some asymmetric border designs, but in practice not).

### 3. INI output — stdlib `configparser.RawConfigParser`

**Pick:** stdlib `configparser.RawConfigParser` with `optionxform = str`. **Confidence: HIGH.**

```python
from configparser import RawConfigParser
cp = RawConfigParser()
cp.optionxform = str  # preserve case — KDE keys are case-sensitive
cp["General"] = {"LeftButtons": "MS", "RightButtons": "IAX"}
cp["ColorEffects:Inactive"] = {"ChangeSelectionColor": "true", "Color": "112,111,110"}
with open(path, "w") as f:
    cp.write(f, space_around_delimiters=False)  # KDE writes "Key=Value", no spaces
```

**Three configparser quirks for KDE files:**

1. **Case sensitivity** — `optionxform = str` (default lowercases). Mandatory for `BackgroundNormal`, `LeftButtons`, etc.
2. **Interpolation** — `RawConfigParser` (or `ConfigParser(interpolation=None)`) is required because KColorScheme contrast values and some font specifications contain `%`, which `BasicInterpolation` will choke on.
3. **No spaces around `=`** — pass `space_around_delimiters=False` to `.write()`. KDE's `KConfig` parser tolerates spaces but the canonical KDE format has none, and `kwriteconfig6` writes none.

**Comma-separated RGB tuples** (`Color=112,111,110`) work fine because configparser doesn't try to parse values — it stores them as strings. Output them as plain strings like `f"{r},{g},{b}"`.

**`.desktop` files — DO NOT use configparser.** The Freedesktop `.desktop` spec allows comments to start with `#` AND requires UTF-8, but more importantly it has localization keys like `Name[de]=Foo` — the `[de]` part will confuse configparser into thinking it's a section. Hand-roll a 20-line `.desktop` writer:

```python
def write_desktop(path, sections):
    with open(path, "w", encoding="utf-8") as f:
        for section, entries in sections.items():
            f.write(f"[{section}]\n")
            for k, v in entries.items():
                f.write(f"{k}={v}\n")
            f.write("\n")
```

The `metadata.desktop` files Aurorae and Look-and-Feel packages need only ever have a `[Desktop Entry]` section with a fixed set of keys (`Name`, `Comment`, `X-KDE-PluginInfo-Name`, `X-KDE-PluginInfo-Author`, `X-KDE-PluginInfo-Version`, `Type`).

### 4. XBM → XCursor — subprocess to `xcursorgen` (with Pillow rasterization)

**Pick:** Pillow XBM read → Pillow PNG write → subprocess `xcursorgen`. **Confidence: HIGH.**

**State of the ecosystem:**
- **clickgen 2.2.5** (Jun 9 2024) — most prominent Python xcursor library. *No releases in the past 12 months*; Snyk advisor explicitly flags it as "low attention from maintainers." It also accepts only PNG input, so we'd still need Pillow to convert XBM → PNG first. Adds a transitive dep for what subprocess does in 5 lines.
- **win2xcur 0.2.0** (Jan 8 2026) — actively maintained but converts *Windows* `.cur`/`.ani` files, not XBM and not PNG sequences. Wrong tool.
- **Pillow XCursor support** — does not exist. Pillow can read/write XBM but has no XCursor plugin.
- **`xcursorgen`** (xorg-xcursorgen system package) — the canonical tool. Reads a config file (`<size> <xhot> <yhot> <png_path> [delay_ms]`) and writes a binary XCursor file. Stable, ubiquitous on Linux distros, present on every KDE workstation.

**Recommended pipeline:**

```python
# 1. Pillow opens XBM (mode 1, monochrome with optional hotspot)
xbm = Image.open("artwork/cursors/left_ptr.xbm")
hotspot = xbm.info.get("hotspot", (0, 0))  # XbmImagePlugin populates this
# 2. Convert to RGBA, optionally upscale by --scale
rgba = xbm.convert("RGBA")
if scale > 1:
    rgba = rgba.resize((rgba.width * scale, rgba.height * scale), Image.Resampling.NEAREST)
# 3. Write PNG temp file
rgba.save(tmp_png)
# 4. Build xcursorgen config: "32 4 4 /tmp/foo.png"
config = f"{rgba.width} {hotspot[0]*scale} {hotspot[1]*scale} {tmp_png}\n"
# 5. Subprocess
subprocess.run(["xcursorgen", "-", "out/left_ptr"], input=config, text=True, check=True)
```

Add `xcursorgen` to a startup-time runtime check (`shutil.which("xcursorgen")`) and emit a clear error pointing to the distro package (`xorg-xcursorgen` on Arch, `x11-apps` or `xcursorgen` on Debian/Ubuntu). This is preferable to the tax of a deprecated PyPI dep.

**Add to `report.txt`:** if hotspot wasn't recorded in the XBM, default to `(0, 0)` and note the approximation.

### 5. CLI framework — Typer

**Pick:** Typer 0.25.1. **Confidence: HIGH.**

- **argparse (stdlib)** — fine but verbose, no auto-help-from-docstrings, no auto-completion shell scripts. A lot of boilerplate for `themey <theme.etheme>` + `themey --all <dir>`.
- **Click 8.3.3** — the rock-solid choice. Excellent. Decorator-based.
- **Typer 0.25.1** — built *on* Click, but uses Python type hints to derive arguments. For a single-author tool with a tiny CLI surface, Typer is the most code-per-feature-light option:

```python
import typer
app = typer.Typer()

@app.command()
def convert(theme: Path, scale: int = 2, install: bool = True, preview: bool = True):
    """Convert one .etheme to a Plasma Look-and-Feel package."""
    ...

@app.command()
def batch(directory: Path, scale: int = 2):
    """Convert every .etheme in a directory."""
    ...
```

Active development (releases Apr 22, Apr 26, Apr 30 2026). Backed by tiangolo (FastAPI). Auto-generates `--help`, shell completion, and respects PEP 593 / `Annotated` for richer types.

If you want zero-dep purism, fall back to argparse. But for ~100 lines of CLI code saved, Typer is the right call.

### 6. Color extraction — Pillow `quantize(method=MEDIANCUT)` + manual palette ranking

**Pick:** Pillow's built-in median-cut quantizer, then rank the resulting palette by saturation × pixel count. **Confidence: HIGH.**

```python
def dominant_palette(img: Image.Image, n_colors: int = 8) -> list[tuple[int, int, int]]:
    # Median cut → palette image with up to n_colors entries
    quantized = img.convert("RGB").quantize(colors=n_colors, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()[: n_colors * 3]
    counts = sorted(quantized.getcolors(), reverse=True)  # [(count, idx), ...]
    rgbs = [(palette[i*3], palette[i*3+1], palette[i*3+2]) for _, i in counts]
    return rgbs
```

**Why not the alternatives:**
- **colorthief 0.2.1** — last release **2017**. Unmaintained, uses MMCQ (median-cut variant) under the hood. We can do the same thing with Pillow directly with no extra dep.
- **colorgram.py 1.2.0** — last release **2018**. Same story.
- **scikit-learn `KMeans`** — produces marginally better perceptual results (per several blog comparisons) but pulls in NumPy + SciPy + scikit-learn (~80 MB) for one function. Not worth it.
- **Hand-rolled k-means in NumPy** — overkill for a single-author tool.

**For Plasma palettes specifically** — KColorScheme needs a small set of named colors (`BackgroundNormal`, `BackgroundAlternate`, `ForegroundNormal`, `ForegroundActive`, `DecorationFocus`, `DecorationHover`). The mapping strategy:
1. Sample **separate** palettes from titlebar, dialog background, and button regions (so we don't average dark/light into mud).
2. From titlebar palette: highest-count dark color → `WindowBar/BackgroundNormal`; complement → text.
3. From dialog/window-body palette: highest-count → `View/BackgroundNormal`.
4. From button glyph: most saturated non-grayscale color → `DecorationFocus`.

The "right" palette for Plasma isn't "the 8 dominant colors of the theme image," it's "the colors at the structural points the theme already assigns meaning." Use Pillow as the primitive; the smarts are in *which region you sample from*.

### 7. Packaging / distribution — uv + pyproject.toml + src/ layout, distributed via `uv tool install`

**Pick:** uv 0.11.8 with `src/` layout, Hatchling build backend, distributed for personal install via `uv tool install .`. **Confidence: HIGH.**

**Project skeleton (what `uv init --package themey` produces, lightly tweaked):**

```
themey/
├── pyproject.toml         # [project], [project.scripts] themey = "themey.cli:app"
├── README.md
├── uv.lock                # committed
├── src/
│   └── themey/
│       ├── __init__.py
│       ├── cli.py         # Typer app
│       ├── parser/        # E16 config grammar
│       ├── aurorae/       # decoration.svg + buttons + rc + metadata
│       ├── colors/        # KColorScheme writer
│       ├── wallpaper/
│       ├── cursors/       # XBM → xcursorgen
│       └── lookandfeel/   # bundle
├── tests/
│   ├── fixtures/          # canned .etheme samples
│   ├── snapshots/         # syrupy .ambr files
│   └── test_*.py
└── .planning/             # (this directory)
```

**`pyproject.toml` shape:**

```toml
[project]
name = "themey"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["pillow>=12.2", "typer>=0.25"]

[project.scripts]
themey = "themey.cli:app"

[dependency-groups]
dev = ["pytest>=9", "syrupy>=5", "ruff>=0.15", "pyright>=1.1.400"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 100
[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "RUF"]

[tool.pyright]
typeCheckingMode = "basic"
```

**Distribution for the one user (chris):**
- Local dev: `uv sync && uv run themey aliens.etheme`
- Personal install: `uv tool install .` → `themey` lands on PATH
- If sharing with others later: `uv tool install git+https://github.com/cstory/themey` — works without publishing to PyPI

**Why `uv tool install` over `pipx`:** uv is 10–100× faster, manages its own Python toolchain, configures PATH automatically, and is now the default in the Astral ecosystem. pipx still works as a fallback — keep it documented in the README ("If you don't have `uv`: `pipx install .`").

### 8. Linting + formatting — Ruff

**Pick:** Ruff 0.15.12. **Confidence: HIGH.**

Confirmed default. Replaces flake8, isort, black, pyupgrade, pydocstyle (and more) with a single Rust binary. Run via `uvx ruff format` and `uvx ruff check --fix`. `select = ["E","W","F","I","B","C4","UP","RUF"]` is a reasonable starting set: pyflakes errors, pycodestyle, isort, bugbear, comprehensions, pyupgrade, ruff-specific rules.

### 9. Testing — pytest + syrupy snapshots

**Pick:** pytest 9.0.3 + syrupy 5.1.0. **Confidence: HIGH.**

This project's testing problem is primarily "did the converter produce the exact expected text/binary outputs given a fixed input theme?" That's the *definition* of snapshot testing.

**syrupy vs pytest-snapshot:**
- syrupy's `.ambr` files are **diff-friendly** (one file per test module, clear separators between cases) — a SVG diff for `decoration.svg` is readable in `git diff`.
- syrupy fails on missing snapshots (pytest-snapshot silently creates them, which can mask test issues).
- syrupy is actively maintained (5.1.0, Jan 25 2026); pytest-snapshot is more sporadically updated.

**Test strategy:**
- Fixture: a canned subset of E16 themes in `tests/fixtures/` (commit small ones like `Aliens`).
- Unit tests: parser grammar, button binning algorithm, color sampling.
- Snapshot tests: full `decoration.svg`, full Aurorae `<name>rc`, full `.colors`, full `metadata.desktop` for at least 3 representative themes. When KDE format expectations evolve, regenerate with `pytest --snapshot-update`.
- Binary outputs (XCursor file, look-and-feel `.tar.gz`) — assert structural properties (file exists, size > N, `xcursorgen --version` produced it, tarfile contains expected entries) rather than byte-snapshotting.

### 10. Type checking — pyright basic

**Pick:** pyright 1.1.409 in `basic` mode. **Confidence: MEDIUM** (mypy strict is also defensible).

For a one-author personal CLI:
- **Strict mypy** is overkill — too much noise from third-party stubs (Pillow's stubs are decent but not perfect), spends time on questions that don't matter for a 2k-line tool.
- **Skip type checking** — leaves easy bugs in (typos in dict keys, `None` vs `Path`, etc.).
- **pyright basic** — middle path. Catches the obvious mistakes, doesn't fight you over generics. `uvx pyright` runs in <2s on a project this size.

If you have a strong preference for mypy, that's fine — pick one, configure once, move on. The point of a recommendation is to stop the bike-shedding.

---

## Installation

```bash
# Bootstrap the project (one time)
uv init --package --build-backend hatchling themey
cd themey

# Add runtime deps
uv add pillow typer

# Add dev deps
uv add --group dev pytest syrupy ruff pyright

# System dep (not via pip)
sudo pacman -S xorg-xcursorgen      # Arch
# sudo apt install xcursorgen         # Debian/Ubuntu (in x11-apps)
# sudo dnf install xorg-x11-apps      # Fedora

# Verify
uv run themey --help
uvx ruff check src/
uvx pyright src/
uv run pytest

# Personal install onto PATH
uv tool install .
themey aliens.etheme
```

---

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

---

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

---

## Stack Patterns by Variant

**If chris later wants to share themey publicly on PyPI:**
- Add `[project.urls]` with repo URL
- Run `uv publish` (uv has a publish subcommand that wraps Twine)
- Bump `requires-python = ">=3.11"` to `>=3.12` if you've been using 3.12-only typing syntax

**If KDE Plasma 7 ships and breaks the FrameSvg contract:**
- Snapshot tests will fail loudly. Update `aurorae/decoration.py` and regenerate snapshots.
- Pin Plasma 6.x minimum in `metadata.desktop` (`X-Plasma-API-Version`) and gate at install time in `themey doctor`.

**If a theme is too large for in-memory processing (unlikely at <4 MB):**
- Pillow handles streaming via `Image.open()` lazy load. No change needed.

**If we need to support Wayland-only systems (we already are — Plasma 6 is Wayland-default):**
- No change. XCursor format is rendered by KWin compositor regardless of Wayland/X11. Aurorae works on both.

---

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

---

## Sources

**PyPI version verification (all confirmed Apr 2026):**
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

**Authoritative format/spec sources (HIGH confidence):**
- [KDE Aurorae window decorations (develop.kde.org)](https://develop.kde.org/docs/plasma/aurorae/) — FrameSvg element ID structure: `decoration-{left,right,top,bottom,topleft,topright,bottomleft,bottomright,center}` plus `-inactive` / `-maximized` / `-opaque` variants
- [KDE/ksvg (GitHub)](https://github.com/KDE/ksvg) — FrameSvg implementation; confirms 9-patch rendering by named element lookup
- [KDE Plasma Style quickstart (develop.kde.org)](https://develop.kde.org/docs/plasma/theme/quickstart/) — recommends embedding raster images in SVG (Inkscape `Effects > Images > Embed All Images`)
- [Pillow image-file-formats (XBM section)](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) — confirms XBM read/write with hotspot info
- [xcursorgen(1) Arch manual](https://man.archlinux.org/man/extra/xorg-xcursorgen/xcursorgen.1.en) — config format `<size> <xhot> <yhot> <png_path> [delay_ms]`
- [Python configparser docs](https://docs.python.org/3/library/configparser.html) — `RawConfigParser`, `optionxform`, `interpolation=None`

**Comparative / supporting (MEDIUM confidence):**
- [uv documentation (Astral)](https://docs.astral.sh/uv/) — uv tool, uvx, project init
- [syrupy docs](https://syrupy-project.github.io/syrupy/) — snapshot extension, Amber format
- [Pillow vs alternatives for color quantization (BVDART)](https://bvdart.nl/en/articles/dominant-color-extraction-in-practice) — practical comparison of Pillow median-cut vs k-means
- [QuantizeImageMethods comparison repo (Chadys)](https://github.com/Chadys/QuantizeImageMethods) — empirical comparison of Pillow methods vs sklearn k-means
- [uvx vs pipx (BSWEN, Mar 2026)](https://docs.bswen.com/blog/2026-03-05-uvx-vs-pipx/) — 2026 perspective on uv as pipx replacement
- [stdlib etree vs lxml (bjoernricks)](https://bjoernricks.github.io/posts/python/stdlib-etree-vs-lxml-etree/) — namespace handling differences
- [Snapshot testing with syrupy (Simon Willison TIL)](https://til.simonwillison.net/pytest/syrupy) — Amber format for text outputs

---
*Stack research for: themey — E16 `.etheme` → KDE Plasma 6 Look-and-Feel CLI converter*
*Researched: 2026-05-01*
