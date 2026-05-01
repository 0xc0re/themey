# Phase 2: Colors + Wallpaper + Full Report - Research

**Researched:** 2026-05-01
**Domain:** KColorScheme `.colors` generation + Plasma 6 Wallpaper/Images packaging + E16 background-block parsing + report.txt fidelity story
**Confidence:** HIGH on KDE format details (verified against `/usr/share/color-schemes/`, `/usr/share/wallpapers/`, `kpackagetool6 -t Wallpaper/Images -s`); HIGH on E16 background grammar (verified against E16 source `definitions:927-1010` + Aliens canary); MEDIUM on color-extraction heuristic (defensible algorithm; final visual quality verified at Phase 2 visual gate, not in research).

## Summary

Phase 2 is **mostly mechanical translation work** with one judgment call: the color-extraction heuristic that maps E16 imagery to a 12-section KColorScheme palette. Both COLORS-01 and WALLPAPER-01 emit text/JSON files (no SVG, no FrameSvg quirks); the install pattern reuses Phase 1's atomic stage-then-rename primitive applied to one new file (`<name>.colors`) and one new directory (`wallpapers/<name>/`). The high-risk slice is already behind us — Phase 2 has no tarfile parsing, no XBM, no FrameSvg ID contracts, no symlink rules.

The two real risks are (1) **the wallpaper isn't where Phase 1's parser looks for it** — Aliens uses `BEGIN_BACKGROUND` macros that expand to `__DESKTOP __BGN`/`__BACKGROUND_LAYER`, NOT the `__BACKGROUND __BGN`/`__BG_BG` form Phase 1's parser was scoped against (Phase 1 RESEARCH Open Question 4 punted this to Phase 2); and (2) **report.txt's three-section taxonomy** has no precedent — we have to invent the categorization and stick to it across all v1 themes.

**Primary recommendation:** Build Phase 2 in this order — (1) extend Theme IR with palette + wallpaper fields, (2) implement E16 background-block walker (handles both `__BACKGROUND __BGN`/`__BG_BG` and the macro-expanded `__DESKTOP __BGN`/`__BACKGROUND_LAYER` forms), (3) implement color-extraction heuristic (Pillow `MEDIANCUT` on titlebar + wallpaper, weighted by saturation×area), (4) emit `<name>.colors` via stdlib `RawConfigParser`, (5) emit `wallpapers/<name>/{metadata.json, contents/images/<W>x<H>.<ext>}` via stdlib `json`, (6) extend Phase 1's HTML preview with swatches + thumbnail, (7) refactor Phase 1's report scaffold into the three-section Preserved/Approximated/Skipped format. Snapshot-test all four output formats (`.colors`, `metadata.json`, HTML, `report.txt`) against `Aliens` and one or two additional canaries.

## User Constraints (from CLAUDE.md)

### Locked Decisions (from CLAUDE.md TL;DR + PROJECT.md Key Decisions)

- **Tech stack frozen.** Python 3.11+, Pillow 12.2.0, stdlib `configparser.RawConfigParser` (with `optionxform = str`, `interpolation=None`), stdlib `xml.etree.ElementTree`, stdlib `json`. NO new dependencies. NO heavy frameworks. [VERIFIED: CLAUDE.md TL;DR table]
- **Output discipline:** every file under `~/.local/share/...`. No system writes, no root.
- **Atomic install pattern** (Phase 1 INSTALL-01): stage to tmpdir, then `os.replace` each top-level output dir. Reuse this primitive for `.colors` and `wallpapers/<name>/`.
- **Frozen `Theme` dataclass:** `Theme.notes` is the **only** mutable field. Phase 2 additions to `Theme` must be frozen-compatible. [VERIFIED: 01-01-SUMMARY.md decisions; src/themey/ir.py:79-100]
- **Don't hand-roll `.desktop` writers** (configparser breaks on localized `Name[de]=` keys). Phase 2 emits `.colors` (INI, configparser-friendly) and `metadata.json` (json.dumps) — neither needs a custom writer. [CITED: CLAUDE.md "What NOT to Use"]
- **Wallpapers use Pillow `Image.Resampling.LANCZOS` for resize** (photographic content) — NOT `NEAREST` (which is reserved for pixel-art borders). [CITED: CLAUDE.md TL;DR]
- **Colors use Pillow `Image.quantize(method=MEDIANCUT)`** — NOT colorthief (unmaintained 2017), NOT colorgram.py (unmaintained 2018), NOT scikit-learn (heavy dep). [CITED: CLAUDE.md "What NOT to Use"]
- **`__ACLASS`-first** is locked for Phase 1's button binning. Phase 2 inherits the populated `Theme.button_codes` and does not re-classify.
- **Render DEFAULT border only.** Other borders (`BORDERLESS`, `DIALOG`, etc.) already log to `report.txt` skipped section in Phase 1; Phase 2 just makes the section visible/structured.
- **GSD workflow:** all file changes go through GSD commands. No direct edits.

### Claude's Discretion

- **Color extraction heuristic** — which images to sample, how to weight clusters, how to assign extracted colors to KColorScheme roles (Window/Button/View/Selection/etc.). Recommend below.
- **Color-effects sections** (`[ColorEffects:Disabled]`, `[ColorEffects:Inactive]`) — copy verbatim from BreezeDark or compute? Recommend below.
- **HTML preview swatch layout** — flexbox row, count per row, swatch size. Recommend below.
- **report.txt section taxonomy** — what counts as "preserved" vs "approximated" vs "skipped". Recommend below.
- **Whether to also emit `metadata.desktop` for the wallpaper** — KPlugin transition is towards `metadata.json`-only on Plasma 6, but some tools still expect both. Recommend `metadata.json` only.

### Deferred Ideas (OUT OF SCOPE for Phase 2)

- **Light/dark color-scheme variants** — `ROBUST-V2-03` is v2; Phase 2 emits a single `.colors` file per theme.
- **Cursor theme** — `CURSORS-01` is Phase 3.
- **Look-and-Feel bundle** (`manifest.json`, `KPackageStructure=Plasma/LookAndFeel`, `contents/defaults`) — Phase 4.
- **Install manifest** (`~/.local/share/themey/manifests/<name>.json`) — Phase 4. Phase 2 must NOT introduce a manifest format that Phase 4 has to migrate; just track output files via the atomic-install primitive.
- **`__COLOR_MODIFIER`** parsing — captured by Phase 1 parser as opaque AST nodes; Phase 2 does NOT apply tinting (Aurorae has no tinting facility). Log to `report.txt` skipped section.
- **Multiple wallpapers per theme / per-desktop wallpapers** — Plasma's per-virtual-desktop-wallpaper feature exists but our wallpaper package is one image per resolution. Aliens has 4 `__DESKTOP __BGN` blocks; pick one (heuristic below) and SKIPPED-log the others.
- **Animated `__BACKGROUND_LAYER` overlays** (`__FORGROUND_LAYER` macros — note E16's typo) — emit base image only, log overlay skip.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COLORS-01 | Sample dominant colors from theme imagery (titlebar, buttons, dialog backgrounds, weighted) into a valid Plasma `.colors` file at `~/.local/share/color-schemes/<name>.colors` with all required `[Colors:*]` sections and `[WM]` | §1 KColorScheme spec; §2 color-extraction heuristic; §7 atomic-write reuse |
| WALLPAPER-01 | Extract `__BACKGROUND` block (or fallback) and produce `~/.local/share/wallpapers/<name>/` with `metadata.json` and `contents/images/`; `tile=1`→`tiled`, `keepaspect=1`→`letterboxed`, otherwise stretch | §3 Plasma 6 Wallpaper/Images spec; §4 E16 background grammar; §7 atomic-write reuse |

REPORT-01 and PREVIEW-01 are nominally Phase 1 requirements but per ROADMAP.md "Note on multi-phase requirements" — Phase 2 enriches both: PREVIEW-01 gets swatches+thumbnail (§6), REPORT-01 gets the full Preserved/Approximated/Skipped sections (§5).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Parse `__BACKGROUND` / `__DESKTOP __BGN` / `__BACKGROUND_LAYER` blocks | analyze | parser (already records as opaque blocks per Phase 1 OQ4) | Phase 1 parser stores blocks verbatim; Phase 2 analyze interprets. Keeps parser dumb. |
| Extract dominant colors from PNG/JPG | analyze (`analyze/colors.py`) | — | Pure function over `asset_root`/PIL; deterministic. |
| Resolve wallpaper IClass → image path | analyze (`analyze/background.py`) | — | Walks parsed AST + IClass map. |
| Map E16 palette → KColorScheme roles | analyze | — | Mapping table; deterministic; testable in isolation. |
| Write `<name>.colors` INI | generate (`generate/colors.py`) | — | RawConfigParser sink, no logic. |
| Write `wallpapers/<name>/metadata.json` | generate (`generate/wallpaper.py`) | — | json.dumps sink. |
| Copy/resize wallpaper image to `contents/images/` | generate | — | Pillow LANCZOS, write atomic. |
| Emit `report.txt` three sections | generate (extend Phase 1 `report.py`) | analyze (notes accumulator already populated) | Phase 1 scaffolds the file; Phase 2 categorizes Theme.notes into three buckets. |
| Enrich HTML preview with swatches + thumbnail | generate (extend Phase 1 `preview.py`) | — | Inline base64 image + flex CSS. |
| Atomic install of `.colors` + `wallpapers/<name>/` | install (extend Phase 1 install.py) | — | Reuse `os.replace` primitive. |

## Standard Stack

### Core (Phase 2 actually uses)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pillow | 12.2.0 | Open PNG/JPG/GIF wallpapers; resize via LANCZOS; quantize via MEDIANCUT for color extraction | [CITED: CLAUDE.md] Built-in handles all formats E16 ships in `artwork/backgrounds/`. Aliens has 14 files: 13 `.jpg`, 1 `.gif` — Pillow handles both natively. [VERIFIED: ls /tmp/aliens-test/artwork/backgrounds/] |
| stdlib `configparser.RawConfigParser` | bundled | Emit `<name>.colors` (KColorScheme INI). Use `optionxform = str` to preserve case-sensitive keys. NO `interpolation=None` needed — `.colors` files don't contain `%` characters in real data | [CITED: CLAUDE.md TL;DR + verified against `/usr/share/color-schemes/BreezeDark.colors`] |
| stdlib `json` | bundled | Emit `wallpapers/<name>/metadata.json`. Use `indent=4` to match KDE convention. | [CITED: develop.kde.org/docs/plasma/wallpapers/] |
| stdlib `shutil` | bundled | Copy wallpaper bytes when no resize is needed (faster than Pillow open+save). | Already in Phase 1 (atomic install). |
| stdlib `tempfile.TemporaryDirectory` | bundled | Atomic install staging — same pattern as Phase 1. | [CITED: 01-RESEARCH.md Pattern 4] |

### Supporting (dev-time only)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 9.0.3 | Test runner | Always |
| syrupy | 5.1.0 | Snapshot test `.colors`, `metadata.json`, HTML, `report.txt` | All four Phase 2 outputs are byte-stable text — perfect for syrupy `.ambr` snapshots [VERIFIED: syrupy is the project standard per 01-01-SUMMARY.md] |
| ruff | 0.15.12 | Lint + format | Always |
| pyright | 1.1.409 (basic mode) | Type check | Always |

### Alternatives Considered (already ruled out by CLAUDE.md)

| Instead of | Could Use | Why Rejected |
|------------|-----------|--------------|
| Pillow MEDIANCUT | colorthief 0.2.1 | Unmaintained since Feb 2017 [CITED: CLAUDE.md] |
| Pillow MEDIANCUT | colorgram.py 1.2.0 | Unmaintained since Dec 2018 [CITED: CLAUDE.md] |
| Pillow MEDIANCUT | scikit-learn KMeans | 80 MB transitive deps for one function [CITED: CLAUDE.md] |
| stdlib json | KConfig Python bindings (PyKF6) | Would add KDE dev binding; `metadata.json` is plain JSON [VERIFIED: cat /usr/share/wallpapers/Next/metadata.json — pure JSON, no KConfig syntax] |
| stdlib RawConfigParser | iniparse | Stdlib has handled KDE configs for 15+ years [CITED: CLAUDE.md] |

**No new packages installed.** Phase 1's `pyproject.toml` is unchanged for Phase 2.

## 1. KColorScheme `.colors` File Format (Plasma 6.x)

**Source of truth used:** Local installed `/usr/share/color-schemes/BreezeDark.colors` (181 lines), `/usr/share/color-schemes/BreezeLight.colors`, and `~/.local/share/color-schemes/Edna.colors` (third-party theme). [VERIFIED: cat output above] Plus the discuss.kde.org confirmation that `~/.local/share/color-schemes/` is the user-installable location. [CITED: https://discuss.kde.org/t/where-are-the-default-colors-files-stored-in-plasma-6/19873]

### Install Path

`~/.local/share/color-schemes/<name>.colors` — single file, no subdirectory. [VERIFIED: `ls ~/.local/share/color-schemes/` shows `Edna.colors`, `Sweet.colors`, `SweetAmbarBlue.colors` — flat layout]

### Section Inventory (BreezeDark.colors as canonical)

| Section | Required? | Purpose |
|---------|-----------|---------|
| `[General]` | **YES** | Holds `ColorScheme=` (machine ID) and `Name=` (human label, with `Name[locale]=` variants) |
| `[KDE]` | recommended | `contrast=4` — tunes UI shadow depth; safe to copy from BreezeDark |
| `[WM]` | **YES** | Window-decoration colors (titlebar): `activeBackground`, `activeBlend`, `activeForeground`, `inactiveBackground`, `inactiveBlend`, `inactiveForeground` — 6 keys, R,G,B integer triples |
| `[Colors:Window]` | **YES** | Application window chrome (background, foreground, link, decoration colors) — 12 keys |
| `[Colors:Button]` | **YES** | Push-button surfaces — same 12 keys |
| `[Colors:View]` | **YES** | List/tree/text view backgrounds — same 12 keys |
| `[Colors:Selection]` | **YES** | Selected-row colors — same 12 keys |
| `[Colors:Tooltip]` | **YES** | Tooltip backgrounds — same 12 keys |
| `[Colors:Header]` | recommended (Plasma 6 addition) | Dialog/window header bars — same 12 keys plus `[Colors:Header][Inactive]` variant |
| `[Colors:Complementary]` | recommended | "Inverted" palette for accent overlays — same 12 keys |
| `[ColorEffects:Disabled]` | recommended | How disabled widgets desaturate — 7 keys (Color, ColorAmount, ColorEffect, ContrastAmount, ContrastEffect, IntensityAmount, IntensityEffect) |
| `[ColorEffects:Inactive]` | recommended | How inactive windows desaturate — 8 keys (above + ChangeSelectionColor, Enable) |

[VERIFIED: every section above appears in BreezeDark.colors with the listed key sets]

### `[Colors:*]` 12-Key Schema (each section)

| Key | Format | Meaning |
|-----|--------|---------|
| `BackgroundNormal` | `R,G,B` (0-255 int triple) | Primary surface fill |
| `BackgroundAlternate` | `R,G,B` | Alternating-row stripe |
| `ForegroundNormal` | `R,G,B` | Primary text |
| `ForegroundActive` | `R,G,B` | Hovered/focused text |
| `ForegroundInactive` | `R,G,B` | Disabled/unfocused text |
| `ForegroundLink` | `R,G,B` | Hyperlink |
| `ForegroundVisited` | `R,G,B` | Visited link |
| `ForegroundPositive` | `R,G,B` | Success/OK text (green family) |
| `ForegroundNeutral` | `R,G,B` | Warning text (orange family) |
| `ForegroundNegative` | `R,G,B` | Error text (red family) |
| `DecorationFocus` | `R,G,B` | Focus ring color (the "accent") |
| `DecorationHover` | `R,G,B` | Hover ring color |

**Color value format:** `R,G,B` integers 0-255, NO alpha component, NO leading `#`. [VERIFIED: every line in `/usr/share/color-schemes/BreezeDark.colors` Colors sections, e.g. `BackgroundNormal=32,35,38`]

> **Important:** This is **different** from the Aurorae `<name>rc` format which uses `R,G,B,A` 4-tuples for `ActiveTextColor`/`InactiveTextColor`. Phase 1's writer must emit 4-tuples for the aurorae rc; Phase 2's writer must emit 3-tuples for the `.colors` file. Don't conflate them.

### `[WM]` 6-Key Schema (window manager / titlebar)

| Key | Format | Meaning |
|-----|--------|---------|
| `activeBackground` | `R,G,B` | Focused titlebar fill |
| `activeForeground` | `R,G,B` | Focused titlebar text |
| `activeBlend` | `R,G,B` | Focused titlebar gradient end / accent |
| `inactiveBackground` | `R,G,B` | Unfocused titlebar fill |
| `inactiveForeground` | `R,G,B` | Unfocused titlebar text |
| `inactiveBlend` | `R,G,B` | Unfocused titlebar gradient end |

[VERIFIED: BreezeDark `[WM]` lines 175-181]

> **Important:** This is the section that gives the user the "this looks like the E16 theme" payoff in System Settings → Window Decorations preview. Source `activeBackground`/`activeForeground` from the Aliens TITLE_BAR_HORIZONTAL `__NORMAL_ACTIVE` image + TEXT1 `__FORGROUND_COLOR` after `__NORMAL_ACTIVE`. Phase 1 already wrote these to the Aurorae rc; Phase 2 mirrors them into the `.colors` `[WM]` section.

### `[General]` 2-Key Schema (+ optional locale variants)

```ini
[General]
ColorScheme=Aliens
Name=Aliens
shadeSortColumn=true
```

`ColorScheme=` is the machine ID (must match the filename minus `.colors`). `Name=` is the human label shown in System Settings. `shadeSortColumn=true` is universally present in `/usr/share/color-schemes/*.colors` and is what determines whether tree-view sort indicators are shaded. Including it is harmless; omitting may break some KDE apps' default behavior. [VERIFIED: `grep shadeSortColumn /usr/share/color-schemes/*.colors`]

### `[ColorEffects:*]` Schema

Per KDE convention these tune how disabled/inactive widgets transform. **Recommendation: copy verbatim from BreezeDark** — these settings are perceptual tuning that shouldn't depend on the source theme's palette. The user can override per-section in System Settings → Colors → Edit if they want.

```ini
[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0
```

### Validation

There is no `kpackagetool6` validator for color schemes (color-schemes is not in `kpackagetool6 --list-types`). Validation is by-eye: open System Settings → Colors → install our file → see it appear in the picker. [VERIFIED: `kpackagetool6 --list-types` output above; no entry for color-schemes]

For automated tests, the validation gate is:
- File parses cleanly with stdlib `configparser.RawConfigParser`
- All 7 required sections present (`[General]`, `[WM]`, `[Colors:Window]`, `[Colors:Button]`, `[Colors:View]`, `[Colors:Selection]`, `[Colors:Tooltip]`)
- Every R,G,B value is 3 comma-separated integers in 0-255
- `[General] ColorScheme` matches the filename slug

## 2. Color Extraction Algorithm

### Inputs Available

After Phase 1, the analyze stage has populated `Theme` with:
- `iclasses` dict — every E16 IClass with image paths under `asset_root`
- `tclasses` dict — text classes with `fg_normal`/`fg_active` RGB triples
- `border` — DEFAULT BorderSpec with positioned button parts pointing at IClasses

Phase 2 adds the wallpaper image (from §4) and any `SET_SOLID R G B` color hint.

### Algorithm: weighted MEDIANCUT on titlebar + wallpaper

**Step 1 — Source image priority list** (mirrors wilbs `mapToBundle.ts:291-308` priority order, which has been production-validated for 100+ themes):
1. `iclasses["TITLE_BAR_HORIZONTAL"].normal_active` (or fallback chain `normal_active → normal → hilited`)
2. `iclasses["TITLE_BAR_HORIZONTAL"].normal` (always)
3. The wallpaper image identified in §4 (downsampled to ≤512px on long edge)
4. Border edge IClasses (`__NORMAL` of any border-part image)
5. `iclasses["DEFAULT_BUTTON"].normal` if present

[CITED: /home/cstory/src/wilbs/src/lib/themes/e16/map-to-bundle.ts:291-308 priority list]

**Step 2 — Per-image MEDIANCUT to 8 bins:**

```python
from PIL import Image
img = Image.open(path).convert("RGBA")
# Drop transparent pixels — composite over neutral grey to avoid biasing toward 0,0,0
bg = Image.new("RGBA", img.size, (128, 128, 128, 255))
opaque = Image.alpha_composite(bg, img).convert("RGB")
# Quantize to 8 dominant colors using median-cut
quant = opaque.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
palette = quant.getpalette()[:24]  # first 8 RGB triples
counts = quant.getcolors(maxcolors=8)  # [(count, idx), ...]
```

[VERIFIED: Pillow 12.2.0 docs https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.quantize — `method=Image.Quantize.MEDIANCUT` is the constant; `Image.Quantize` enum exposes MEDIANCUT, MAXCOVERAGE, FASTOCTREE, LIBIMAGEQUANT]

**Step 3 — Saturation-weighted ranking** (demote near-grey clusters that dominate dark photographic wallpapers):

```python
def rank(rgb, count):
    r, g, b = rgb
    mx, mn = max(rgb), min(rgb)
    sat = 0 if mx == 0 else (mx - mn) / mx  # HSV saturation
    return count * (0.3 + 0.7 * sat)  # wilbs formula, production-tuned
```

[CITED: /home/cstory/src/wilbs/src/lib/themes/e16/extract-palette.ts:154-159 — same `0.3 + 0.7 * saturation` weight, production-validated]

**Step 4 — Role assignment** (the actual mapping E16→KColorScheme):

| KColorScheme role | Source | Heuristic |
|---|---|---|
| `[WM] activeBackground` | titlebar `__NORMAL_ACTIVE` MEDIANCUT top cluster | The dominant titlebar color — what the user "sees" |
| `[WM] activeForeground` | tclass TEXT1 `fg_active` | Already explicit in E16 source — exact match |
| `[WM] activeBlend` | titlebar 2nd cluster (or 1.2× lighter of activeBackground) | Gradient accent |
| `[WM] inactiveBackground` | titlebar `__NORMAL` MEDIANCUT top cluster | Distinct unfocused look |
| `[WM] inactiveForeground` | tclass TEXT1 `fg_normal` | Already explicit |
| `[WM] inactiveBlend` | inactiveBackground darkened 0.2 | Computed |
| `[Colors:Window] BackgroundNormal` | wallpaper-or-titlebar most-saturated cluster, darkened 0.4 | App window backdrop should be muted |
| `[Colors:Window] ForegroundNormal` | luminance-contrast pick (white if BG dark, black if BG light) | Readability gate |
| `[Colors:Window] BackgroundAlternate` | BackgroundNormal lightened 0.05 | Stripe contrast |
| `[Colors:Window] DecorationFocus` | wallpaper most-saturated cluster (full saturation, ~80% luminance) | The "accent" |
| `[Colors:Window] DecorationHover` | DecorationFocus | Same |
| `[Colors:Window] ForegroundActive` | DecorationFocus | Same hue family |
| `[Colors:Window] ForegroundInactive` | desaturated ForegroundNormal | Computed |
| `[Colors:Window] ForegroundLink` | shift accent +30° hue | Distinct from accent but same family |
| `[Colors:Window] ForegroundVisited` | shift accent +60° hue | Distinct from link |
| `[Colors:Window] ForegroundPositive` | green family — fixed `39,174,96` (Breeze) | Semantic, not theme-derived |
| `[Colors:Window] ForegroundNeutral` | orange family — fixed `246,116,0` (Breeze) | Semantic |
| `[Colors:Window] ForegroundNegative` | red family — fixed `218,68,83` (Breeze) | Semantic |
| `[Colors:Button]` | inherit `[Colors:Window]` values verbatim | Reduces palette inconsistency |
| `[Colors:View]` | inherit `[Colors:Window]` (slightly darker BackgroundNormal) | Lists/text-views look like dimmed windows |
| `[Colors:Selection]` | BackgroundNormal=DecorationFocus, ForegroundNormal=contrast pick | Selected rows pop |
| `[Colors:Tooltip]` | inherit `[Colors:Window]` | Match window |
| `[Colors:Header]` | inherit `[Colors:Window]` | Same |
| `[Colors:Complementary]` | inherit `[Colors:Window]` with BG even darker | Subtle variant |

**Why this heuristic over alternatives:**
- **Sample titlebar AND wallpaper, weighted toward titlebar** — the titlebar is what the user sees on every window; the wallpaper supplies the accent that ties the desktop together. Sampling only the titlebar produces palettes that don't match the user's wallpaper memory; sampling only the wallpaper makes app windows feel disconnected from the window frames. [REASONING: production-mirrored from wilbs which samples both]
- **Fix Positive/Neutral/Negative to Breeze defaults** — these are semantic colors (green=success, red=error). Sampling them from a 2009 dark sci-fi theme would produce confusingly-tinted "Save" buttons. Users expect green-success/red-error regardless of theme aesthetics. [REASONING: KDE convention — every `/usr/share/color-schemes/*.colors` file uses near-identical Positive/Neutral/Negative values across themes]
- **Compose Window→Button→View→Tooltip→Header→Complementary from one root** — reduces visual chaos. Edna does the same (verbatim copies of most fields across sections per `cat ~/.local/share/color-schemes/Edna.colors`). [VERIFIED: Edna's BackgroundNormal is `38,50,56` in Window/View/Tooltip/Header/Complementary]
- **Drop transparent pixels by compositing over grey** — Pillow's `quantize` on RGBA includes alpha=0 pixels at face value; compositing first prevents "the dominant color is fully transparent black" pathology.

**Confidence:** MEDIUM — this is a defensible heuristic, but the Phase 2 visual gate is what proves it. Add the Aliens canary as Plan 02-N and verify in System Settings → Colors that the resulting palette "feels like Aliens" before declaring success.

### `[Colors:Header]` Caveat

Plasma 6 added `[Colors:Header]` plus the `[Colors:Header][Inactive]` quirk-syntax variant section (note the bracket-suffix-bracket pattern). [VERIFIED: BreezeDark.colors lines 70-95]

`configparser.RawConfigParser` may have trouble with `[Section][Sub]` syntax. **Mitigation:** write `[Colors:Header]` and `[Colors:Header][Inactive]` as two separate sections with the literal bracketed names. Test with `RawConfigParser.read_string(' '.join(...))` to confirm round-trip — if it fails, fall back to writing the file via raw `Path.write_text()` of a hand-formatted string (KColorScheme is read by KConfig, which handles this syntax; we just have to emit it).

[ASSUMED] Whether `RawConfigParser` round-trips `[Colors:Header][Inactive]` cleanly. **Test in Plan 02-01.**

## 3. KDE Wallpaper Plugin Packaging (Plasma 6.x)

### Install Path and Layout

```
~/.local/share/wallpapers/<name>/
├── metadata.json                       # KPlugin metadata
└── contents/
    ├── images/
    │   ├── 1920x1080.png               # filename = WIDTHxHEIGHT.<ext>
    │   └── ...optionally other sizes
    ├── images_dark/                    # OPTIONAL — for dark-mode variants
    │   └── 1920x1080.png
    └── screenshot.png                  # OPTIONAL — preview thumbnail in picker
```

[VERIFIED: structure of `/usr/share/wallpapers/Next/`, `/usr/share/wallpapers/Altai/`, and `~/.local/share/wallpapers/Edna-RanchoCucamonga/`]

### Filename Convention: `<W>x<H>.<ext>`

The image filename MUST be `<width>x<height>.<extension>` — Plasma's wallpaper plugin uses this to pick the best resolution for the user's display. [VERIFIED: `ls /usr/share/wallpapers/Next/contents/images/` → `1440x2960.png`, `5120x2880.png`, `7680x2160.png`; CITED: KDE Discuss "rename images to reflect their respective resolutions"]

**File-format support:** PNG, JPG, JXL all work. [VERIFIED: `file /usr/share/wallpapers/Next/contents/images/*.png` shows non-interlaced 8-bit PNGs] Phase 2 should preserve the source format when possible (E16 ships .jpg → write .jpg; .gif → convert to .png since GIF is poorly supported).

**Recommended single-output strategy:** ship ONE image at the source's native resolution. Don't try to scale up; Plasma scales down to fit. Aliens' `Alien97.jpg` is, e.g., 1024x768 — write `contents/images/1024x768.jpg` (verify dimension via Pillow). If the source is `.gif`, convert to `.png` (preserve dimensions).

### `metadata.json` — Required Schema

**Minimal valid manifest** (verified against `~/.local/share/wallpapers/Edna-RanchoCucamonga/metadata.json`, which works on chris's Plasma 6.6.4):

```json
{
    "KPlugin": {
        "Id": "Aliens",
        "Name": "Aliens",
        "License": "CC-BY-SA-4.0",
        "Version": "1.0",
        "Authors": [
            {
                "Name": "themey (converted from E16 theme by <author>)",
                "Email": ""
            }
        ]
    }
}
```

[VERIFIED: minimal-schema example confirmed by Edna-RanchoCucamonga local install which works in System Settings; CITED: develop.kde.org/docs/plasma/wallpapers/ which shows the same minimal `{"KPlugin": {"Id": ..., "Name": ...}}` shape]

**Required keys** (from observation of working wallpapers):
- `KPlugin.Id` — MUST equal the directory name (`<name>`). [CITED: github.com/zzag/plasma5-wallpapers-dynamic/issues/17 "metadata.json must be identical to wallpaper's folder name"]
- `KPlugin.Name` — human label shown in the wallpaper picker

**Recommended keys** (in real-world wallpapers but not strictly required):
- `KPlugin.License` — string. Aliens are 2009 community themes; use `"LGPL-2.1-or-later"` or `"unknown"` rather than fabricating a license. Recommend `"unknown"`.
- `KPlugin.Version` — string. Use `"1.0"` for our converter output.
- `KPlugin.Authors` — array of `{Name, Email}` objects. If E16's `ABOUT/MAIN` carries an author, populate; otherwise omit or use `themey` as author.

**Optional keys we should NOT emit:**
- `Name[xx]` localized variants — we have one user (chris); shipping 38 locale variants would be silly
- `X-KDE-PlasmaImageWallpaper-AccentColor` — we're emitting our own `.colors` file; per-wallpaper accent override would conflict
- `X-Plasma-MainScript` — only for QML wallpaper plugins (animated/dynamic), not for `Wallpaper/Images`

### Validation Command

```bash
kpackagetool6 -t Wallpaper/Images -s ~/.local/share/wallpapers/Aliens
```

[VERIFIED: command exists on chris's machine; tested against `/usr/share/wallpapers/Next` and returned `Name: Sub-Arctic | Plugin: Next | Author: ... | Path: ...`]

This is a **smoke test** — it confirms `metadata.json` parses and `KPlugin.Id` resolves. It does not validate the `contents/images/` layout (Plasma fails open on missing images at apply time). Use as a Phase 2 test gate; failure means metadata is broken; success doesn't guarantee the picker will display the image.

### Why `metadata.json` not `metadata.desktop`

Plasma 5 used `metadata.desktop` (KDE's `.desktop`-file dialect). Plasma 6 transitioned to `metadata.json` per `KPackageStructure` framework changes. Some packages (Edna-RanchoCucamonga) ship both for backward compatibility.

**Recommendation:** emit `metadata.json` only. Plasma 6 prefers it; chris's machine is 6.6.4; v2 deferred work could add `metadata.desktop` if a Plasma 5 user ever cares.

[CITED: Phase 1 RESEARCH lines 86, 487 — the same transition happened for the Aurorae sub-package; Phase 1 chose to emit BOTH because Edna ships both. For wallpaper, the pressure is lower because the wallpaper picker only reads the structured metadata for display name; the image works regardless.]

## 4. Where E16 Themes Store the Wallpaper

### Two grammar forms — Phase 2 must handle both

**Form 1 — Raw `__BACKGROUND __BGN` block** (what wilbs's parser recognizes):

```
__BACKGROUND __BGN
  __NAME my_bg
  __BG_BG "TITLE_BAR_HORIZONTAL" 0 0 512 512 1024 1024
  __BG_SOLID 100 70 40
__END
```

Where `__BG_BG` syntax is `"<iclass_name>" tile keepaspect xjust yjust xperc yperc`. [CITED: REQUIREMENTS.md PARSE-02; wilbs `parse-cfg.ts:317-341`; CLAUDE.md PROJECT.md context line about `__BG_BG`]

**Form 2 — Macro-expanded `__DESKTOP __BGN` block** (what Aliens uses, what wilbs's parser MISSES):

```
__DESKTOP __BGN
  __NAME "Aliens_Alien97"
  __SOLID_COLOR 100 70 40
  __BACKGROUND_LAYER artwork/backgrounds/Alien97.jpg 0 0 0 0 1024 1024
  __USE_ON_DESKTOP 0
  __USE_ON_DESKTOP 4
__END
```

Where `__BACKGROUND_LAYER` syntax is `<file> <tile> <keepaspect> <xjust> <yjust> <xperc> <yperc>` — same 6 trailing params as `__BG_BG` but the resource is a **file path, not an iclass name**. [VERIFIED: /home/cstory/Downloads/e16-1.0.31/config/definitions:927-1010 macro definitions]

**Verified against Aliens canary:** `/tmp/aliens-test/desktops.cfg` contains 4 `BEGIN_BACKGROUND(...)` macros, each expanding to a `__DESKTOP __BGN` block with one or more `ADD_BACKGROUND_SCALED(...)` macros (→ `__BACKGROUND_LAYER`) and multiple `ON_DESKTOP(N)` macros (→ `__USE_ON_DESKTOP N`). [VERIFIED: cat output above]

### Macro Reference (from `definitions:927-1010`)

| Macro | Expands To |
|-------|-----------|
| `BEGIN_BACKGROUND(name)` | `__DESKTOP __BGN; __NAME name` |
| `END_BACKGROUND` | `__END` |
| `SET_SOLID(color)` | `__SOLID_COLOR color` |
| `ADD_BACKGROUND_TILED(file)` | `__BACKGROUND_LAYER file 1 1 0 0 0 0` |
| `ADD_BACKGROUND_SCALED(file)` | `__BACKGROUND_LAYER file 0 0 0 0 1024 1024` |
| `ADD_BACKGROUND_CENTERED(file)` | `__BACKGROUND_LAYER file 0 1 512 512 0 0` |
| `ADD_BACKGROUND_SCALED_RETAIN_ASPECT(file)` | `__BACKGROUND_LAYER file 0 1 512 512 1024 1024` |
| `ADD_BACKGROUND_TILED_SCALED_RETAIN_ASPECT(file)` | `__BACKGROUND_LAYER file 1 1 512 512 1024 1024` |
| `ON_DESKTOP(num)` | `__USE_ON_DESKTOP num` |
| `DEFAULT_BACKGROUND` | `__USE_ON_DESKTOP __DESKTOP_ALL` |
| `ADD_OVERLAY_IMAGE_*(file)` | `__FORGROUND_LAYER ...` (note E16's typo — same as `__FORGROUND_COLOR`) |

### Phase 2 Background Selection Algorithm

```
Input:  parsed AST containing 0..N __DESKTOP __BGN blocks AND 0..N __BACKGROUND __BGN blocks
Output: (image_path, fit_mode, fallback_solid_color)
  where fit_mode ∈ {tiled, letterboxed, stretch}
  and fallback_solid_color is RGB triple (used if image_path is None)

Step 1: collect candidates from BOTH grammar forms
  - For each __DESKTOP block: extract __BACKGROUND_LAYER lines and the first __SOLID_COLOR
  - For each __BACKGROUND block: extract __BG_BG (resolve iclass to .normal path) and __BG_SOLID

Step 2: prefer image over solid; prefer first __DESKTOP block in source order
  (Aliens has 4 desktops; we pick desktop-0's primary background as "the wallpaper")

Step 3: derive fit_mode from the 6 layer params (tile, keepaspect, _, _, _, _)
  - tile=1 → "tiled" (Plasma map: emit no fit hint; Plasma defaults to tiled if image is small)
  - tile=0, keepaspect=1 → "letterboxed" (we just write the file at native resolution; Plasma honors aspect)
  - tile=0, keepaspect=0 → "stretch" (Plasma also honors when image is forced to fill)

Step 4: if no candidate, fallback chain:
  - Largest image in artwork/backgrounds/ if dir exists
  - TITLE_BAR_HORIZONTAL.normal upscaled 2x
  - SET_SOLID color from any __DESKTOP block → emit a solid-color PNG (fabricated)
  - Final fallback: 1x1 grey PNG, log SKIPPED in report

Step 5: log every dropped candidate to Theme.notes (the other 3 of Aliens' 4 desktops)
```

### Important: Plasma's `Wallpaper/Images` Plugin Doesn't Use the `fit` Hint

The `Wallpaper/Images` plugin reads images from `contents/images/` and uses Plasma's wallpaper picker to set fit (the user picks "Stretched", "Scaled", "Centered", "Tiled" in the desktop config UI). **There is no per-wallpaper fit setting in `metadata.json`** for `Wallpaper/Images` — that's set by the user at apply-time per-screen.

**Implication:** the E16 `tile`/`keepaspect` flags are LOST in Phase 2 output. **Log this to report.txt approximated section** ("E16 background was tiled; Plasma's default is stretched — set in Desktop Settings → Wallpaper if you want tile mode"). The image itself is preserved, only the rendering hint is dropped.

[VERIFIED: cat /usr/share/wallpapers/Next/metadata.json shows no fit/scale/position keys; develop.kde.org/docs/plasma/wallpapers/ shows only Id/Name/License + AccentColor — no fit field]

### Aliens Wallpaper Selection (worked example)

Source: `/tmp/aliens-test/desktops.cfg` has 4 `BEGIN_BACKGROUND` blocks for desktops Aliens_Alien97 (desktops 0,4,8,...), Aliens_Giger (1,5,9,...), Aliens_NameMe (2,6,...), Aliens_Alien01 (3,7,...).

Phase 2 picks the **first one in source order**: `Aliens_Alien97` → `artwork/backgrounds/Alien97.jpg` with `__SOLID_COLOR 100 70 40` fallback. Other 3 logged as SKIPPED ("E16 theme defined backgrounds for desktops 1,2,3 (Aliens_Giger, Aliens_NameMe, Aliens_Alien01); Plasma wallpaper packages support only one image per package").

## 5. report.txt Three-Section Format

### Format Recommendation

Plain text, fixed-column-width readable, parseable-line entries (one fact per line, no continuations).

```
themey conversion report
========================
Theme:        Aliens
Source:       /home/cstory/src/wilbs/ethemes/e16/Aliens.etheme
Author:       Don (E16 theme)
Generated:    2026-05-15 14:30:00
Scale:        2x

Outputs:
  ~/.local/share/aurorae/themes/Aliens/
  ~/.local/share/color-schemes/Aliens.colors
  ~/.local/share/wallpapers/Aliens/

To activate the window decoration:
  System Settings -> Window Decorations -> Aliens
To activate the color scheme:
  System Settings -> Colors -> Aliens
To activate the wallpaper:
  Right-click desktop -> Configure Desktop -> Wallpaper -> Aliens

PRESERVED (mapped 1:1 from E16 source)
======================================
- Border: DEFAULT (35/20/30/25 px)
- Buttons: kill->X, maximize->A, iconify->I (left)
- Titlebar image: artwork/n_title.png (TITLE_BAR_HORIZONTAL/__NORMAL_ACTIVE)
- Titlebar text color (focused): 255,255,200 (TEXT1/__FORGROUND_COLOR after __NORMAL_ACTIVE)
- Titlebar text color (unfocused): 200,200,150 (TEXT1/__FORGROUND_COLOR after __NORMAL)
- Wallpaper image: artwork/backgrounds/Alien97.jpg

APPROXIMATED (lossy mapping; reason explained)
==============================================
- 8 E16 image-states collapsed to 2 Aurorae states:
    __NORMAL -> decoration-inactive-*
    __NORMAL_ACTIVE -> decoration-*
    __HILITED_ACTIVE -> button-hover element
    __CLICKED_ACTIVE -> button-pressed element
- Color scheme palette derived from titlebar+wallpaper sampling
  (KColorScheme requires 12-color palette; E16 supplies titlebar
  and wallpaper images; assignment heuristic: titlebar->[WM],
  wallpaper-saturated->DecorationFocus accent)
- Wallpaper fit mode (E16 ADD_BACKGROUND_SCALED -> Plasma default "Scaled")
  E16 source declared keepaspect=0; Plasma user can override in
  Configure Desktop -> Wallpaper if tile or center is preferred
- Embedded PNGs at 2x source resolution: pixel-perfect on
  1.0x/2.0x/3.0x display scales; approximate at 1.25x/1.5x/1.75x

SKIPPED (no Plasma equivalent or out of scope for v1)
=====================================================
- Border: BORDERLESS (E16 has multiple borders; Aurorae has only DEFAULT)
- 3 additional desktop backgrounds: Aliens_Giger, Aliens_NameMe,
  Aliens_Alien01 (Plasma wallpaper packages support one image per package)
- 9 sticky-state image variants (no Aurorae per-desktop button state)
- Disabled image-states (Aurorae uses Qt disabled-styling instead)
- __COLOR_MODIFIER blocks (Aurorae has no tinting facility)
- artwork/cursors/*.xbm (cursor theme is Phase 3)
- TTF fonts (Aurorae uses system font; cannot override per-theme)
- E16 menus, tooltips, focuslist, dock, iconbox, pager
  (no clean Plasma equivalent — explicit out-of-scope per PROJECT.md)
- __CHANGES_SHAPE __ON (Aurorae is rectangular only)
- xcursorgen not found on PATH (or: cursors successfully generated)  [Phase 3]
```

### Three-Section Taxonomy Definitions

| Section | Definition | Examples |
|---------|-----------|----------|
| **PRESERVED** | E16 source data appears in the output unchanged in meaning. The user gets exactly what the theme author intended for that field. | Titlebar PNG bytes; titlebar text color; button glyphs; border thicknesses; the chosen wallpaper image |
| **APPROXIMATED** | E16 source data informs the output but is transformed in a lossy way. The user gets a reasonable interpretation that loses some original detail. | 8→2 state collapse; sampled color palette (we derive 12 colors from a few images); wallpaper fit mode (E16's tile/keepaspect lost) |
| **SKIPPED** | E16 source data has no Plasma equivalent or is explicitly out of scope. The data is in the source but does NOT appear in the output. | Multi-desktop wallpapers; sticky button states; menus; tooltips; cursors-when-xcursorgen-missing; non-DEFAULT borders |

### Where Notes Come From

Phase 1's analyze stage already populates `Theme.notes` with strings like:
- `"TITLE_BAR_HORIZONTAL: __NORMAL_STICKY dropped (no Aurorae target for sticky/disabled/clicked-active variants)"` (from `analyze/states.py` per 01-04-SUMMARY.md)
- (TBD by Plan 01-05 Phase 1 finalization) entries about `BORDERLESS` etc. being skipped

Phase 2's analyze stage adds:
- "Wallpaper extracted from desktop 0 (Aliens_Alien97); 3 other desktop backgrounds skipped"
- "Color scheme palette derived from <N> images: titlebar __NORMAL_ACTIVE + wallpaper Alien97.jpg"
- "[Colors:Header] section emitted with copied [Colors:Window] values" (if we choose to)
- One entry per `__COLOR_MODIFIER` block found

### Implementation: refactor Phase 1's report.py

Phase 1 plan 01-08 ships `report.py` as a scaffold (header + flat list of notes). Phase 2 refactors it to:

```python
# src/themey/report.py
def render_report(theme: Theme, outputs: Outputs) -> str:
    sections = categorize_notes(theme.notes)  # returns dict[str, list[str]]
    return "\n".join([
        _header(theme, outputs),
        _section("PRESERVED", sections["preserved"]),
        _section("APPROXIMATED", sections["approximated"]),
        _section("SKIPPED", sections["skipped"]),
    ])

def categorize_notes(notes: list[str]) -> dict[str, list[str]]:
    # Heuristic: keyword routing
    # Notes containing "dropped", "skipped", "ignored" → SKIPPED
    # Notes containing "approximated", "collapsed", "sampled", "derived", "fit mode lost" → APPROXIMATED
    # Notes starting with explicit role tags ("PRESERVED:") → that section
    # Default → APPROXIMATED (safe — overstates lossiness rather than understating)
```

**Recommendation: prefix-tag notes** at write-time so categorization is deterministic. Example:

```python
theme.notes.append("PRESERVED: titlebar PNG (artwork/n_title.png)")
theme.notes.append("APPROXIMATED: 8 image-states collapsed to 2")
theme.notes.append("SKIPPED: BORDERLESS border (Aurorae has only one)")
```

This deprecates Phase 1's free-form note format. Phase 2 plan-01 should add a `_note(category, text)` helper used everywhere, and migrate Phase 1's existing call sites.

## 6. HTML Preview Enrichment

### Current State (Phase 1)

Phase 1 ships `src/themey/preview.py` with:
- Mocked titlebar `<div>` styled with active titlebar color
- Activation-command `<pre>` block (`kwriteconfig6 ...`)
- Notes list (`<ul>`)

[VERIFIED: 01-RESEARCH.md lines 982-1018 — current preview.py contents]

### Phase 2 Additions

**(a) Color swatches row** — add a flexbox row showing all 12 KColorScheme palette colors with hex labels:

```html
<h2>Color scheme</h2>
<div class="swatches">
  <div class="swatch" style="background:#202326" title="Window Background">
    <span>BG</span><code>#202326</code>
  </div>
  <div class="swatch" style="background:#3daee9">
    <span>Accent</span><code>#3daee9</code>
  </div>
  <!-- ...etc, one per significant role: Window BG, Window FG, Accent (DecorationFocus),
       WM activeBackground, WM activeForeground, WM inactiveBackground -->
</div>
```

```css
.swatches { display: flex; flex-wrap: wrap; gap: 6px; margin: 1em 0; }
.swatch {
  width: 90px; height: 70px;
  display: flex; flex-direction: column; justify-content: flex-end;
  padding: 4px; border-radius: 4px;
  font-size: 11px; color: white;
  text-shadow: 0 1px 2px black;
}
.swatch code { background: rgba(0,0,0,0.4); padding: 1px 3px; }
```

**6 swatches is enough** — showing all 12 keys × 7 sections (84 swatches) is overkill for a preview. Show: Window BG, Window FG, Accent, WM active BG, WM active FG, WM inactive BG.

**(b) Wallpaper thumbnail** — base64-embedded img, capped at 320px wide:

```python
import base64
from io import BytesIO
from PIL import Image

def _wallpaper_thumb_data_uri(wallpaper_path: Path) -> str:
    img = Image.open(wallpaper_path).convert("RGB")
    img.thumbnail((320, 240), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"
```

```html
<h2>Wallpaper</h2>
<img class="wallpaper-thumb" src="{data_uri}" alt="Wallpaper preview" />
```

```css
.wallpaper-thumb {
  max-width: 320px; max-height: 240px;
  border: 1px solid #ccc; border-radius: 4px;
  display: block; margin: 1em 0;
}
```

**Embed strategy: base64 in single HTML file** — keeps the preview as one self-contained file the user can email or open from anywhere. JPEG at quality 80 keeps the data URI under ~30 KB for 320×240 thumbnails.

**Accessibility:** `alt="Wallpaper preview"` on img; `title="role name"` on swatches. Keyboard navigability isn't a concern for a preview file.

### Notes List Adjustment

The notes list is now categorized (per §5). Render as 3 sublists with headings rather than one flat ul:

```html
<h2>Conversion notes</h2>
<details open><summary>Preserved (12 entries)</summary>
  <ul>...</ul>
</details>
<details open><summary>Approximated (4 entries)</summary>
  <ul>...</ul>
</details>
<details><summary>Skipped (8 entries)</summary>
  <ul>...</ul>
</details>
```

`<details>` collapses skipped notes by default — keeps the page scannable.

## 7. Atomic Write + Idempotent Re-Install Pattern

Phase 1 (`INSTALL-01`, plan 01-08) ships the primitive: stage to `tempfile.TemporaryDirectory(prefix="themey-")`, write all files, `os.replace(stage_dir, final_dir)` to atomically swap. [CITED: 01-RESEARCH.md Pattern 4 + Code Examples "Atomic install (INSTALL-01)" lines 952-980]

### Per-Output Atomic Strategy

| Output | Stage path | Final path | Atomic primitive |
|---|---|---|---|
| Aurorae theme | `<tmp>/aurorae/<name>/` | `~/.local/share/aurorae/themes/<name>/` | `os.replace` (dir-to-dir) — already in Phase 1 |
| **Color scheme (Phase 2)** | `<tmp>/colors/<name>.colors` | `~/.local/share/color-schemes/<name>.colors` | `os.replace` (file-to-file) — single-file variant |
| **Wallpaper (Phase 2)** | `<tmp>/wallpapers/<name>/` | `~/.local/share/wallpapers/<name>/` | `os.replace` (dir-to-dir) — same primitive as Aurorae |
| Report.txt + preview.html | `<tmp>/themey/<name>.txt` and `.html` | `~/.local/share/themey/previews/<name>.{txt,html}` | `os.replace` per file |

**Critical detail for single-file `.colors`:** parent dir `~/.local/share/color-schemes/` must exist. `mkdir(parents=True, exist_ok=True)` before `os.replace`. The file itself is atomic (POSIX `rename(2)` over a file is atomic on the same filesystem).

**Critical detail for `wallpapers/<name>/` dir-rename:** `os.replace` on dirs requires the destination dir to be empty OR the source to be a non-empty dir replacing the existing one. Python 3.9+ `os.replace` on a directory replaces the destination directory atomically when both source and dest are on the same filesystem AND the dest is empty or doesn't exist. **For idempotent re-install over an existing populated dir**, the Phase 1 strategy is `shutil.rmtree(final_dir, ignore_errors=True); os.replace(stage_dir, final_dir)` — same pattern reused. [VERIFIED: this matches what Phase 1's plan-01-08 will implement per 01-RESEARCH.md Code Examples lines 952-980]

### Same-Filesystem Constraint

`os.replace` is only atomic on the same filesystem. `tempfile.TemporaryDirectory()` defaults to `/tmp` which on some setups is `tmpfs` — different filesystem from `~/.local/share/`. **Phase 2 must stage in `~/.local/share/themey/.staging/<random>/` instead** to guarantee same-fs.

[ASSUMED] This is what Phase 1's plan 01-08 will implement. **Verify with Phase 1 plan 01-08 author when it lands.** If Phase 1 stages in /tmp, Phase 2 inherits the bug and must fix it for both phases simultaneously.

### Phase 4 Manifest Compatibility

`INSTALL-02` (Phase 4) introduces `~/.local/share/themey/manifests/<name>.json` listing every file written. Phase 2 should NOT pre-implement this; just track which output paths were written by passing them up to the orchestrator. The Phase 4 manifest writer can collect from the orchestrator's return value.

**Recommendation:** add a `WriteResult` named tuple returned from each generator function:

```python
WriteResult = namedtuple("WriteResult", "files dirs")
# files: list[Path] absolute paths of files written
# dirs: list[Path] absolute paths of dirs created (for rmtree on uninstall)
```

Phase 2 generators return `WriteResult`. Phase 4 manifest writer aggregates them. Phase 2 itself doesn't need to use the result beyond logging.

## 8. Theme IR Additions Needed

Current `Theme` (src/themey/ir.py:79-100) is fully populated by Phase 1's analyze stage. Phase 2 additions must preserve `frozen=True`. Recommended additions:

```python
# Add new frozen dataclass
@dataclass(frozen=True)
class WallpaperSpec:
    """The chosen desktop background — one image plus solid-color fallback."""
    image_path: Path | None  # absolute path under asset_root; None means solid only
    fit_mode: str  # one of "tiled", "letterboxed", "stretch" — informational only
    solid_color: tuple[int, int, int] | None  # RGB; used as fallback or as wallpaper background
    desktop_label: str | None  # e.g. "Aliens_Alien97" — for report.txt PRESERVED line
    skipped_alternatives: tuple[str, ...]  # other desktop labels we ignored

# Extend ColorScheme — supersedes Phase 1's tiny Palette dataclass
# (Phase 1 Palette has only 4 colors: titlebar_active, titlebar_inactive, text_active, text_inactive)
@dataclass(frozen=True)
class ColorScheme:
    """Full 12-section KColorScheme palette ready for INI emission."""
    # WM section (6 keys)
    wm_active_background: tuple[int, int, int]
    wm_active_foreground: tuple[int, int, int]
    wm_active_blend: tuple[int, int, int]
    wm_inactive_background: tuple[int, int, int]
    wm_inactive_foreground: tuple[int, int, int]
    wm_inactive_blend: tuple[int, int, int]
    # Window/Button/View/Selection/Tooltip/Header/Complementary share schema
    # We compute one root then expose a simple field set:
    background_normal: tuple[int, int, int]
    background_alternate: tuple[int, int, int]
    foreground_normal: tuple[int, int, int]
    foreground_active: tuple[int, int, int]
    foreground_inactive: tuple[int, int, int]
    foreground_link: tuple[int, int, int]
    foreground_visited: tuple[int, int, int]
    decoration_focus: tuple[int, int, int]
    decoration_hover: tuple[int, int, int]
    # Semantic colors (fixed per recommendation §2)
    foreground_positive: tuple[int, int, int] = (39, 174, 96)
    foreground_neutral: tuple[int, int, int] = (246, 116, 0)
    foreground_negative: tuple[int, int, int] = (218, 68, 83)
    # View/Selection variants computed at INI-write time from above

# Extend Theme dataclass
@dataclass(frozen=True)
class Theme:
    # ... all existing fields ...
    palette: Palette  # KEEP for backward compat with Phase 1 (titlebar+text only)
    color_scheme: ColorScheme | None  # NEW: full KColorScheme — populated in Phase 2
    wallpaper: WallpaperSpec | None  # NEW: chosen background — populated in Phase 2
    notes: list[str] = field(default_factory=list)
    skipped_borders: tuple[str, ...] = ()
```

**Why both `palette` and `color_scheme`:** `palette` is still used by Phase 1's HTML preview titlebar styling and the Aurorae rc's `ActiveTextColor`. Adding `color_scheme` rather than replacing keeps Phase 1 code unchanged. After Phase 2 ships, a v2 cleanup could collapse the two — but for now, additive is safer.

**Why `WallpaperSpec.fit_mode` is informational only:** Plasma's `Wallpaper/Images` plugin doesn't honor a fit hint (per §3) — so we don't write it anywhere. We track it in the IR purely so report.txt's APPROXIMATED section can say "E16 declared tile mode; Plasma will use stretch unless user changes it".

**Why `WallpaperSpec` fields are absolute paths, not relative to asset_root:** Phase 2's wallpaper generator opens the image with PIL and writes a copy. Asset_root is a tmpdir that gets cleaned up post-conversion. Storing absolute paths here avoids "wait, is this rel-to-asset-root or abs?" confusion at generate-time.

### Migration Risk

Phase 1's `Palette` dataclass is a frozen field of `Theme`. Adding NEW fields with `= None` defaults is backward compatible — Phase 1 code that doesn't set them gets `None`, Phase 1 tests still pass. Adding to `Palette` (instead of new dataclass) would risk breaking Phase 1's frozen-instance tests. **Recommendation: introduce `ColorScheme` as a new dataclass; do not modify `Palette`.**

[VERIFIED: src/themey/ir.py:15-22 — Palette has 4 fields; tests in tests/test_ir.py exercise frozen-ness; new fields with defaults won't break those tests]

## 9. Test Strategy

### Snapshot Targets (syrupy `.ambr` files)

| Output | Snapshot? | Notes |
|--------|-----------|-------|
| `Aliens.colors` (full INI) | YES | byte-stable text; perfect for `.ambr` |
| `wallpapers/Aliens/metadata.json` | YES | json.dumps with sorted keys + indent=4 = stable |
| `wallpapers/Aliens/contents/images/<W>x<H>.jpg` | NO | binary, large; assert structurally (file exists, dimensions match) |
| `<name>.html` preview (without base64 image) | YES | use a fixture wallpaper path that snapshot doesn't include the data URI |
| `<name>.html` preview WITH base64 image | NO | data URI byte-shifts under Pillow upgrades |
| `report.txt` | YES | byte-stable; great for catching unintended note format changes |

**Strategy for HTML with embedded image:** snapshot the HTML with a `<!-- thumbnail data uri omitted in snapshot -->` placeholder; assert separately that the data URI is well-formed (`startswith("data:image/jpeg;base64,")` and decodes back to a valid PIL image).

### Canary Corpus

| Theme | Why include | What it tests |
|-------|-------------|---------------|
| `Aliens` (already in tests/fixtures) | Phase 1 canary; macro-form `__DESKTOP __BGN`; multi-desktop backgrounds | Background macro parsing; primary path |
| `tiny.etheme` (hand-crafted, ~5 KB, raw `__BACKGROUND __BGN` form) | Tests the OTHER grammar form | Background raw-form parsing |
| One additional real theme from the corpus (PICK ONE: `Vector` or `Edna` or `Brushed_Steel`) | Ensures algorithm generalizes | Color extraction for non-Aliens palettes |
| (NEGATIVE) `notheme.etheme` — theme with ZERO background blocks | Tests fallback chain | Background fallback to titlebar PNG |

**Recommendation:** add 2 fixtures total — `tiny.etheme` (hand-crafted, raw `__BACKGROUND` form) and one randomly-picked corpus theme as a "non-Aliens visual gate". Don't try to cover the full 100-theme corpus in Phase 2; Phase 4's batch mode will surface real bugs.

### KDE-side Validation Test

```bash
kpackagetool6 -t Wallpaper/Images -s ~/.local/share/wallpapers/Aliens
```

[VERIFIED: command exists; tested above against `/usr/share/wallpapers/Next`]

Add as a subprocess call in a pytest test marked `@pytest.mark.requires_kde`. Skip when `kpackagetool6` isn't on PATH (CI without Plasma).

```python
@pytest.mark.skipif(shutil.which("kpackagetool6") is None, reason="kpackagetool6 not installed")
def test_wallpaper_validates_via_kpackagetool6(fake_home, ...):
    convert_aliens(install=True)
    result = subprocess.run(
        ["kpackagetool6", "-t", "Wallpaper/Images", "-s", str(fake_home / ".local/share/wallpapers/Aliens")],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "Plugin     : Aliens" in result.stdout
```

There is no analogous validator for `.colors` files. Use:
```python
import configparser
cp = configparser.RawConfigParser()
cp.optionxform = str
cp.read(install_path / "Aliens.colors")
assert "Colors:Window" in cp.sections()
assert "WM" in cp.sections()
# etc.
```

### Visual Gate (Manual)

Phase 2 final task should be a manual visual checkpoint, same pattern as Phase 1 plan 01-09:
1. Run `themey Aliens.etheme`
2. Open System Settings → Colors → see "Aliens" in list → click → desktop adopts new colors
3. Right-click desktop → Configure Desktop → Wallpaper → see "Aliens" in picker → select → wallpaper applies
4. Eyeball: do the colors and wallpaper feel like the source theme?

This is the only proof that the heuristic in §2 produces aesthetically-coherent palettes.

## 10. Common Pitfalls (Phase 2-specific)

### Pitfall A: Phase 1 parser doesn't recognize `__DESKTOP __BGN`/`__BACKGROUND_LAYER`
**What goes wrong:** Plan 02-N tries to read `theme.backgrounds` (or whatever Phase 1 stores) and finds an empty list because Phase 1's parser only emitted opaque AST nodes for unknown blocks (per Phase 1 RESEARCH OQ4).
**Why it happens:** Aliens uses macro-expanded form; wilbs's reference parser only handles the raw `__BACKGROUND __BGN` form.
**How to avoid:** Phase 2 plan 01 reads the AST directly (not Theme.backgrounds), walking for both `__DESKTOP` and `__BACKGROUND` block keywords. Document the dual-form recognition in `analyze/background.py` with a comment pointing at `definitions:927-932`.
**Warning signs:** `theme.wallpaper` is None for Aliens after analyze; report.txt shows "no wallpaper found" for a theme that visibly has 4 wallpapers.

### Pitfall B: Pillow `quantize()` on RGBA includes transparent pixels
**What goes wrong:** Theme images with transparency (button glyphs especially) produce a "dominant color = fully transparent black" cluster, biasing the palette toward black.
**Why it happens:** Pillow's median-cut treats each pixel uniformly; transparent pixels are RGBA=(0,0,0,0) and that's a perfectly valid "black" sample.
**How to avoid:** composite over neutral grey before quantize:
```python
bg = Image.new("RGBA", img.size, (128, 128, 128, 255))
opaque = Image.alpha_composite(bg, img).convert("RGB")
quant = opaque.quantize(colors=8, method=Image.Quantize.MEDIANCUT)
```
**Warning signs:** Palette tests show a near-black or near-grey cluster as #1 dominant for themes with transparent borders.

### Pitfall C: `<W>x<H>.png` filename must be EXACT
**What goes wrong:** Writing `1920x1080.png` for a 1024×768 image, OR writing `1024 x 768.png` (with spaces), OR `1024X768.png` (capital X) — Plasma silently fails to load the wallpaper.
**Why it happens:** Plasma's `Wallpaper/Images` plugin parses filenames as resolution hints to pick the best fit for the screen.
**How to avoid:** read actual dimensions from PIL after open; use lowercase `x`; format string `f"{w}x{h}{ext}"`.
**Warning signs:** wallpaper appears as black in the picker; package validates with `kpackagetool6` but selection does nothing.

### Pitfall D: `KPlugin.Id` mismatch with directory name
**What goes wrong:** Wallpaper installs to `~/.local/share/wallpapers/Aliens/` but `metadata.json` has `"Id": "aliens"` (lowercase) → Plasma rejects silently.
**Why it happens:** the Id field is the canonical identifier; the directory name must match.
**How to avoid:** derive both from a single sanitized `slug = theme.name`. Add a unit test: `assert metadata["KPlugin"]["Id"] == output_dir.name`.
**Warning signs:** `kpackagetool6 -s` succeeds but the wallpaper doesn't show in the picker.
[CITED: github.com/zzag/plasma5-wallpapers-dynamic/issues/17]

### Pitfall E: `RawConfigParser` mangles `[Colors:Header][Inactive]` section name
**What goes wrong:** writing `cp["Colors:Header][Inactive"]` (escape brackets in name?) produces garbage; writing the literal `[Colors:Header][Inactive]` line via raw write works but `RawConfigParser` may not round-trip it.
**Why it happens:** `RawConfigParser` parses `[name]` lines and the bracket-suffix syntax is non-standard.
**How to avoid:** test round-trip first; if `RawConfigParser` chokes, write the file as raw text via `Path.write_text("\n".join(...))`. KConfig (Plasma's actual reader) handles this syntax fine; we just need to emit it.
**Warning signs:** `[Colors:Header]` works but `[Colors:Header][Inactive]` either silently merges with the previous section or produces a section literally named `Colors:Header][Inactive`.

### Pitfall F: tempfile staging on `/tmp` (different filesystem)
**What goes wrong:** `os.replace(stage, final)` raises `OSError: [Errno 18] Invalid cross-device link` when `/tmp` is `tmpfs` and `~/.local/share` is on the home filesystem.
**Why it happens:** POSIX `rename(2)` requires both paths on same filesystem.
**How to avoid:** stage in `~/.local/share/themey/.staging/<random>/` (under home, same fs as final dest). Use `tempfile.mkdtemp(dir=home_staging)` instead of `tempfile.TemporaryDirectory()` with default location.
**Warning signs:** test passes locally on a tmpfs-less setup, fails on standard Linux desktop installs.

### Pitfall G: Palette extraction is non-deterministic across Pillow versions
**What goes wrong:** `Image.quantize(method=MEDIANCUT, colors=8)` produces different palettes on Pillow 12.1 vs 12.2 due to internal algorithm tweaks. Snapshot tests of `.colors` files break on Pillow upgrade.
**Why it happens:** MEDIANCUT has implementation-defined tie-breaking on equal cluster sizes.
**How to avoid:** pin Pillow exactly in `uv.lock` (already done by Phase 1); if a future Pillow upgrade breaks snapshots, regenerate them. This is acceptable maintenance — `uv sync` brings in the locked version. Document in plan: "Pillow upgrades require `pytest --snapshot-update` and visual re-verify."
**Warning signs:** CI green on dev box, red on a freshly-bootstrapped checkout with newer Pillow.

### Pitfall H: `__SOLID_COLOR` vs `__BG_SOLID` are different keywords
**What goes wrong:** parser only checks for `__BG_SOLID` and misses `__SOLID_COLOR` (the macro form). Solid-color fallback is lost.
**Why it happens:** these are two separate keywords from the two grammar forms (per `definitions:934-935`).
**How to avoid:** `analyze/background.py` MUST check both keywords when extracting the solid-color fallback.

### Pitfall I: Wallpaper images may be GIF (animated or not)
**What goes wrong:** writing `Alien97.gif` as `1024x768.gif` works; Plasma may render only the first frame for animated gifs (or fail).
**Why it happens:** GIF format is rare in modern wallpaper plugins; Plasma supports it imperfectly.
**How to avoid:** convert GIF to PNG via Pillow (open + first-frame + save as PNG with `.png` extension). Aliens has 1 GIF (`giger045.gif`); if that's the chosen wallpaper, conversion is mandatory.
**Warning signs:** wallpaper picker shows the file but the desktop renders empty.

### Pitfall J: report.txt notes from Phase 1 are free-form; categorization is heuristic
**What goes wrong:** `categorize_notes("FOO_THING dropped (no Aurorae target)")` lands in SKIPPED based on "dropped" keyword — but a future Phase 1 update writes "ANOTHER_THING approximated and dropped" → ambiguity.
**Why it happens:** Phase 1's note format predates the three-section split.
**How to avoid:** prefix-tag at write time (`"PRESERVED: ..."`, `"APPROXIMATED: ..."`, `"SKIPPED: ..."`) and migrate Phase 1 call sites in Plan 02-01. Heuristic-only categorization is fragile.
**Warning signs:** snapshot tests of report.txt fail with notes appearing in unexpected sections after a Phase 1 plan ships.

## Runtime State Inventory

Phase 2 introduces NEW install destinations under `~/.local/share/`. Same OS-state caveats as Phase 1 apply:

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | None — Phase 2 writes only fresh files. | None |
| Live service config | KDE Plasma Workspace reads `~/.local/share/color-schemes/` and `~/.local/share/wallpapers/` at theme-application time (when user picks via System Settings or right-click desktop config). The lists are built by directory scan. **Implication:** writing a new file/dir makes it discoverable; no reload command needed. KCM caching (kcm_colors / kcm_wallpaper) may require closing+reopening the dialog to see additions — same caveat as Phase 1's KWin decoration KCM. | Document only |
| OS-registered state | None at OS level. KDE only re-scans on demand. | None |
| Secrets/env vars | None. | None |
| Build artifacts / installed packages | None new in Phase 2; `uv tool install .` is unaffected by what files we write. | None |

**Idempotent re-install verified path:** `themey Aliens.etheme` twice in a row should:
1. Overwrite `~/.local/share/color-schemes/Aliens.colors` cleanly (atomic file replace)
2. Overwrite `~/.local/share/wallpapers/Aliens/` cleanly (rmtree+rename per Phase 1 pattern)
3. Leave no stale files behind from the first run

## Environment Availability

| Dependency | Required By | Available on chris's machine | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Pillow 12.2.0 | All Phase 2 image work | YES (per Phase 1 install) | 12.2.0 | none — required |
| `kpackagetool6` | Wallpaper validation tests (optional) | YES | 2.0 | skip test if missing |
| Python `configparser` | `.colors` writer | YES (stdlib) | 3.11+ | none |
| Python `json` | `metadata.json` writer | YES (stdlib) | 3.11+ | none |
| Python `xml.etree.ElementTree` | NOT used in Phase 2 (HTML preview is hand-formatted, not XML) | YES (stdlib) | — | n/a |

**No new system dependencies introduced by Phase 2.** Phase 3 will introduce `xcursorgen`; Phase 2 doesn't.

[VERIFIED: kpackagetool6 --version on chris's machine: 2.0]

## Security Domain

> Phase 2 introduces no new attack surface beyond Phase 1's `safe_extract`. The .etheme inputs are still untrusted; the outputs go to user-owned XDG paths.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | n/a — local CLI, no auth |
| V3 Session Management | no | n/a |
| V4 Access Control | no | n/a — single-user; output paths are `~/.local/share/...` (user-owned) |
| V5 Input Validation | yes | E16 background image paths must be path-validated against `asset_root` (no `../` escape); already covered by Phase 1's `safe_extract` for archive entries, but Phase 2 must re-validate when reading `__BACKGROUND_LAYER <file>` values from cfg (a malicious cfg could reference `/etc/passwd` even with a clean tar archive) |
| V6 Cryptography | no | n/a — no secrets, no crypto |

### Phase 2-Specific Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious `__BACKGROUND_LAYER` file path with `../` escape | Tampering | Resolve every path with `(asset_root / path).resolve()` and assert `asset_root in resolved.parents`. Reject otherwise. |
| Malicious image content (PIL CVE / decompression bomb) | Denial of service | Set `Image.MAX_IMAGE_PIXELS` to a sane cap (e.g. `100_000_000`) before opening. Pillow raises `Image.DecompressionBombError` above the cap. |
| Malicious filename used in output path | Tampering | Filename is derived from theme `name` (already slug-sanitized in Phase 1 INSTALL-01). Don't trust E16's `__NAME` field for output paths. |

**Recommendation:** add a single helper `_safe_open_image(path: Path, asset_root: Path) -> Image.Image` that validates the path is under asset_root, sets `Image.MAX_IMAGE_PIXELS = 100_000_000`, and opens. Use it everywhere Phase 2 opens an image.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|---|---|---|---|
| `metadata.desktop` for wallpaper packages | `metadata.json` | Plasma 5 → Plasma 6 transition (KPackageStructure framework) | Phase 2 emits json-only |
| Per-wallpaper fit/scale in metadata | User-set in Configure Desktop UI per-screen | Plasma 6 (always was for `Wallpaper/Images`) | Phase 2 cannot ship a fit hint; logs to APPROXIMATED |
| `colorthief` / `colorgram.py` for palette extraction | Pillow MEDIANCUT (or k-means in numpy) | Pillow has shipped `quantize` for years; community alternatives unmaintained since 2017–2018 | Phase 2 uses Pillow direct |
| `metadata.json`-only wallpaper plugin | Adds `X-KDE-PlasmaImageWallpaper-AccentColor` field for per-wallpaper accent | Plasma 6 introduced | Phase 2 does NOT emit this field (we ship a separate `.colors` file) |

## Critical Decisions Needed Before Planning

The planner must resolve these before writing PLAN.md files. Each has a recommended default below.

### Decision 1: Should Phase 2 ship `metadata.desktop` AND `metadata.json` for the wallpaper, or json-only?
- **Recommendation: json-only.** Phase 1 ships both for the Aurorae sub-package because Edna does. For wallpaper, the conformance pressure is lower (the picker only displays metadata; the image works regardless). Keeps the writer simpler and consistent with what's documented at develop.kde.org/docs/plasma/wallpapers/.
- **Risk:** if a Plasma 5 user ever cares (unlikely on chris's 6.6.4 box), `metadata.desktop` can be added in v2.

### Decision 2: For multi-desktop themes (Aliens has 4), pick one wallpaper or ship multiple?
- **Recommendation: pick the first `__DESKTOP __BGN` block in source order; SKIPPED-log the others.** Plasma's `Wallpaper/Images` package is one image (or one image per resolution). Plasma supports per-virtual-desktop wallpapers but only via the user setting them individually in Configure Desktop — not via the wallpaper package. Trying to ship multiple packages (`Aliens-Alien97`, `Aliens-Giger`, etc.) would clutter the user's wallpaper picker for one theme conversion.
- **Risk:** the chosen wallpaper may not be the user's favorite from the theme. Mitigated by SKIPPED-logging the alternatives so the user can manually re-run extraction or switch later.

### Decision 3: Color extraction — sample titlebar only, wallpaper only, or both?
- **Recommendation: both, with titlebar driving `[WM]` and wallpaper-saturated cluster driving accent.** Wilbs production-validated this pattern across 100+ themes. Sampling only titlebar produces palettes disconnected from the wallpaper memory; only wallpaper makes app windows feel disconnected from the frame.
- **Risk:** the heuristic may produce ugly palettes for some themes. Visual gate at end of Phase 2 catches this; iterate the role-assignment table in §2 if needed.

### Decision 4: `[ColorEffects:Disabled]` and `[ColorEffects:Inactive]` — copy verbatim from BreezeDark or compute?
- **Recommendation: copy verbatim from BreezeDark.** These tune perceptual desaturation; they don't depend on the source theme palette. Computing from the theme would risk producing un-readable disabled-state widgets. The user can edit via System Settings if they want a different treatment.
- **Risk:** none material.

### Decision 5: report.txt note format — free-form or prefix-tagged?
- **Recommendation: prefix-tag (PRESERVED:, APPROXIMATED:, SKIPPED:).** Heuristic categorization on free-form notes is fragile (Pitfall J). Phase 2 plan 01 should add a `theme.note(category, text)` helper, migrate Phase 1's existing `theme.notes.append(...)` call sites, and write categorization as a 1-line dispatch on the prefix.
- **Risk:** churn through Phase 1 code (~5–10 call sites). Worth it for stable categorization.

## Pitfalls

(Listed inline in §10 above — A through J. Pitfall A is the highest-priority — the rest are mechanical.)

## Code Examples

### Color extraction pipeline (analyze/colors.py)

```python
# Source: derived from wilbs extract-palette.ts (production-validated) +
# Pillow 12.2 docs https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.quantize
from pathlib import Path
from PIL import Image
from typing import NamedTuple

Image.MAX_IMAGE_PIXELS = 100_000_000  # decompression-bomb guard

class WeightedColor(NamedTuple):
    rgb: tuple[int, int, int]
    weight: float  # count * (0.3 + 0.7 * saturation)

def extract_dominant(image_path: Path, k: int = 8) -> list[WeightedColor]:
    img = Image.open(image_path).convert("RGBA")
    bg = Image.new("RGBA", img.size, (128, 128, 128, 255))
    opaque = Image.alpha_composite(bg, img).convert("RGB")
    quant = opaque.quantize(colors=k, method=Image.Quantize.MEDIANCUT)
    palette_flat = quant.getpalette()
    counts = quant.getcolors(maxcolors=k) or []  # list[(count, palette_index)]

    out: list[WeightedColor] = []
    for count, idx in counts:
        r, g, b = palette_flat[idx*3:idx*3+3]
        sat = 0.0 if max(r,g,b) == 0 else (max(r,g,b) - min(r,g,b)) / max(r,g,b)
        out.append(WeightedColor(rgb=(r,g,b), weight=count * (0.3 + 0.7 * sat)))
    return sorted(out, key=lambda c: -c.weight)
```

### `.colors` writer (generate/colors.py)

```python
# Source: verified against /usr/share/color-schemes/BreezeDark.colors structure
import configparser
from pathlib import Path

def _rgb(t: tuple[int,int,int]) -> str:
    return f"{t[0]},{t[1]},{t[2]}"

def write_colors_ini(theme, out_path: Path) -> None:
    cp = configparser.RawConfigParser()
    cp.optionxform = str  # preserve case (BackgroundNormal not backgroundnormal)

    cs = theme.color_scheme
    cp["General"] = {
        "ColorScheme": theme.name,
        "Name": theme.display_name,
        "shadeSortColumn": "true",
    }
    cp["KDE"] = {"contrast": "4"}
    cp["WM"] = {
        "activeBackground": _rgb(cs.wm_active_background),
        "activeForeground": _rgb(cs.wm_active_foreground),
        "activeBlend": _rgb(cs.wm_active_blend),
        "inactiveBackground": _rgb(cs.wm_inactive_background),
        "inactiveForeground": _rgb(cs.wm_inactive_foreground),
        "inactiveBlend": _rgb(cs.wm_inactive_blend),
    }
    # The 12-key block, repeated for each Colors:* section
    base = {
        "BackgroundNormal": _rgb(cs.background_normal),
        "BackgroundAlternate": _rgb(cs.background_alternate),
        "ForegroundNormal": _rgb(cs.foreground_normal),
        "ForegroundActive": _rgb(cs.foreground_active),
        "ForegroundInactive": _rgb(cs.foreground_inactive),
        "ForegroundLink": _rgb(cs.foreground_link),
        "ForegroundVisited": _rgb(cs.foreground_visited),
        "ForegroundPositive": _rgb(cs.foreground_positive),
        "ForegroundNeutral": _rgb(cs.foreground_neutral),
        "ForegroundNegative": _rgb(cs.foreground_negative),
        "DecorationFocus": _rgb(cs.decoration_focus),
        "DecorationHover": _rgb(cs.decoration_hover),
    }
    for section in ("Colors:Window", "Colors:Button", "Colors:View",
                    "Colors:Selection", "Colors:Tooltip", "Colors:Header",
                    "Colors:Complementary"):
        cp[section] = dict(base)  # may diverge per role in v1.1 — for now identical

    # ColorEffects copied verbatim from BreezeDark
    cp["ColorEffects:Disabled"] = {
        "Color": "56,56,56", "ColorAmount": "0", "ColorEffect": "0",
        "ContrastAmount": "0.65", "ContrastEffect": "1",
        "IntensityAmount": "0.1", "IntensityEffect": "2",
    }
    cp["ColorEffects:Inactive"] = {
        "ChangeSelectionColor": "true", "Color": "112,111,110",
        "ColorAmount": "0.025", "ColorEffect": "2",
        "ContrastAmount": "0.1", "ContrastEffect": "2",
        "Enable": "false", "IntensityAmount": "0", "IntensityEffect": "0",
    }
    with out_path.open("w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
```

### `metadata.json` writer (generate/wallpaper.py)

```python
# Source: verified against ~/.local/share/wallpapers/Edna-RanchoCucamonga/metadata.json
import json
from pathlib import Path

def write_wallpaper_metadata(theme, out_dir: Path) -> Path:
    data = {
        "KPlugin": {
            "Id": theme.name,                    # MUST equal out_dir.name
            "Name": theme.display_name,
            "License": "unknown",                # E16 themes pre-date SPDX adoption
            "Version": "1.0",
            "Authors": [
                {"Name": theme.author or "themey (E16 conversion)", "Email": ""}
            ],
        }
    }
    out_path = out_dir / "metadata.json"
    out_path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
    return out_path
```

### Wallpaper image copy with format conversion (generate/wallpaper.py)

```python
# Source: PIL docs + filename convention from
# https://discuss.kde.org/t/how-to-make-the-wallpaper-package
import shutil
from PIL import Image
from pathlib import Path

def write_wallpaper_image(src: Path, contents_images_dir: Path) -> Path:
    contents_images_dir.mkdir(parents=True, exist_ok=True)

    # Read dimensions to drive the filename convention
    with Image.open(src) as img:
        w, h = img.size
        # Convert GIF → PNG; preserve JPG/PNG natively
        if src.suffix.lower() in (".gif",):
            ext = ".png"
            img.convert("RGB").save(contents_images_dir / f"{w}x{h}{ext}", "PNG")
        else:
            ext = src.suffix.lower()
            shutil.copy2(src, contents_images_dir / f"{w}x{h}{ext}")
    return contents_images_dir / f"{w}x{h}{ext}"
```

### Background block walker (analyze/background.py)

```python
# Source: E16 source /home/cstory/Downloads/e16-1.0.31/config/definitions:927-1010
# Handles BOTH grammar forms: __BACKGROUND __BGN (raw) and __DESKTOP __BGN (macro-expanded).
from pathlib import Path
from typing import Optional

def select_wallpaper(ast, asset_root: Path, iclasses) -> Optional["WallpaperSpec"]:
    candidates: list[tuple[Path, str, tuple[int,int,int]|None, str]] = []  # (path, fit, solid, label)

    for block in ast.blocks:
        # Form 1: macro-expanded
        if block.keyword == "__DESKTOP":
            label = block.kvs.get("__NAME", "(unnamed)")
            solid = _parse_solid(block.kvs.get("__SOLID_COLOR"))
            for layer in block.kvs.get_all("__BACKGROUND_LAYER"):
                # syntax: <file> <tile> <keepaspect> <xjust> <yjust> <xperc> <yperc>
                parts = layer.split()
                if len(parts) >= 7:
                    file_rel, tile, keepaspect, *_ = parts
                    fit = _fit_from_flags(int(tile), int(keepaspect))
                    abs_path = (asset_root / file_rel).resolve()
                    if asset_root in abs_path.parents and abs_path.exists():
                        candidates.append((abs_path, fit, solid, label))
                        break  # take first layer of each desktop

        # Form 2: raw __BACKGROUND
        elif block.keyword == "__BACKGROUND":
            label = block.kvs.get("__NAME", "(unnamed)")
            solid = _parse_solid(block.kvs.get("__BG_SOLID"))
            bg_bg = block.kvs.get("__BG_BG")
            if bg_bg:
                # syntax: "<iclass>" tile keepaspect xjust yjust xperc yperc
                parts = bg_bg.split()
                if parts:
                    iclass_name = parts[0].strip('"')
                    ic = iclasses.get(iclass_name)
                    if ic and ic.normal:
                        tile, keepaspect = int(parts[1]), int(parts[2])
                        fit = _fit_from_flags(tile, keepaspect)
                        abs_path = ic.normal
                        candidates.append((abs_path, fit, solid, label))

    if not candidates:
        return None  # caller falls back to titlebar PNG or solid color

    # Pick first in source order (heuristic: matches user's "primary" desktop)
    chosen = candidates[0]
    skipped_labels = tuple(c[3] for c in candidates[1:])
    return WallpaperSpec(
        image_path=chosen[0],
        fit_mode=chosen[1],
        solid_color=chosen[2],
        desktop_label=chosen[3],
        skipped_alternatives=skipped_labels,
    )

def _fit_from_flags(tile: int, keepaspect: int) -> str:
    if tile: return "tiled"
    if keepaspect: return "letterboxed"
    return "stretch"

def _parse_solid(raw: str | None) -> tuple[int,int,int] | None:
    if not raw: return None
    parts = raw.replace('"','').split()
    if len(parts) >= 3:
        try: return (int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError: return None
    return None
```

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| B1 | `RawConfigParser` round-trips `[Colors:Header][Inactive]` section name cleanly | §1 / Pitfall E | Fall back to raw text writer; same output, more code |
| B2 | Plasma 6.6.4 reads `metadata.json`-only wallpaper packages without `metadata.desktop` | §3 / Decision 1 | Verified by Edna-RanchoCucamonga local install which is json-only and works — but if Plasma's behavior changed in a 6.6.x patch we don't know about, fallback is to also emit metadata.desktop (~10 LoC) |
| B3 | Picking the first `__DESKTOP __BGN` block in source order matches the user's intent for "the wallpaper" | §4 / Decision 2 | User gets a wallpaper they didn't expect; mitigated by SKIPPED log of alternatives. Could be addressed by `--wallpaper=<name>` CLI flag in v2 |
| B4 | The saturation-weighted MEDIANCUT heuristic produces aesthetically-coherent palettes for the corpus | §2 / Decision 3 | Visual gate may reject; iterate role-assignment table. Worst case is regenerating snapshots and tuning weights — no architectural change |
| B5 | Phase 1 ships background blocks as opaque AST nodes accessible to Phase 2 (per Phase 1 RESEARCH OQ4 recommendation) | §4 / Pitfall A | If Phase 1 doesn't store backgrounds at all, Phase 2 plan 02-01 must extend the parser. **Verify when Phase 1 plan 01-03/01-05 land.** |
| B6 | `Image.MAX_IMAGE_PIXELS = 100_000_000` is sufficient for all corpus wallpapers (rejects only decompression bombs) | §Security | Largest legitimate wallpaper in corpus is 2 MB Aliens .jpg = ~3 MP. Cap at 100 MP allows ~10× headroom. |
| B7 | `tile=1`/`keepaspect=1` flag values are LOST in Plasma's `Wallpaper/Images` plugin output (no fit field in `metadata.json`) | §3 / §4 | Mitigation already planned: log to APPROXIMATED. If Plasma 6.7+ adds a fit field, we can emit it later |
| B8 | `kpackagetool6 -t Wallpaper/Images -s` returncode 0 means metadata is well-formed | §9 | Verified against `/usr/share/wallpapers/Next` — produced clean output, returncode 0. Sufficient as smoke test |
| B9 | Phase 1 plan 01-08 stages atomic writes in same-fs as `~/.local/share/` (not `/tmp`) | §7 / Pitfall F | Cross-device link error at install time. Mitigation: independently audit Phase 1's plan 01-08 staging path before Phase 2 starts |

**Empty / Confirmed:** none — every section above carries at least one assumption. The visual gate at end of Phase 2 is the catch-all for B3, B4, B7.

## Open Questions

1. **What does `Theme.notes` look like after Phase 1 lands?**
   - What we know: per 01-04-SUMMARY.md, the format is `"{context_label}: {state} dropped (reason)"`. Plan 01-05 / 01-08 will add more.
   - What's unclear: whether Phase 1 prefix-tags by category (PRESERVED/APPROXIMATED/SKIPPED) or leaves it free-form.
   - Recommendation: Phase 2 plan 02-01 introduces the prefix-tag convention and migrates whatever Phase 1 wrote — see Decision 5.

2. **Should the wallpaper image be upscaled when tiny?**
   - What we know: Aliens wallpapers are 800×600-ish (2009 desktop standard). Modern displays are 1920×1080 and up. Plasma will upscale to fit but the result is blurry.
   - What's unclear: whether to ship native (sharp but small) or LANCZOS-upscale to a target size (larger file, smoother fit).
   - Recommendation: ship native resolution. Plasma's "Scaled" mode handles upscaling at apply time. If the user wants nicer scaling, they can re-run themey with `--scale=2` or use a higher-res wallpaper via Configure Desktop.

3. **Should overlay layers (`__FORGROUND_LAYER` macros) be composited into the wallpaper?**
   - What we know: E16 supports overlays — text/logo on top of the base wallpaper. Aliens uses one (commented out): `/* ADD_OVERLAY_IMAGE_CENTERED("artwork/Elogo.png") */`.
   - What's unclear: whether to PIL-composite the overlay onto the wallpaper for fidelity, or skip overlays entirely.
   - Recommendation: skip in v1; log to APPROXIMATED. Compositing risks aspect-ratio bugs, alpha-channel surprises. If a corpus theme uses overlays heavily and the result is visibly bad, revisit in Phase 2.5.

## Sources

### Primary (HIGH confidence)

**Ground truth on disk:**
- `/usr/share/color-schemes/BreezeDark.colors` (181 lines) — canonical KColorScheme INI structure for Plasma 6.6.4
- `/usr/share/color-schemes/BreezeLight.colors` — light-theme variant
- `~/.local/share/color-schemes/Edna.colors` — third-party `.colors` file confirmed to work in System Settings
- `/usr/share/wallpapers/Next/{metadata.json,contents/images/}` — canonical KDE-shipped Wallpaper/Images structure
- `/usr/share/wallpapers/Altai/` — second canonical example
- `~/.local/share/wallpapers/Edna-RanchoCucamonga/{metadata.json,contents/images/}` — minimal third-party wallpaper package confirmed to work
- `/home/cstory/Downloads/e16-1.0.31/config/definitions:927-1010` — `BEGIN_BACKGROUND` / `ADD_BACKGROUND_*` / `SET_SOLID` macro definitions
- `/home/cstory/Downloads/e16-1.0.31/src/backgrounds.c:1140-1207` — E16 background config parser confirms `BG_RGB`, `BG_BG_FILE`, `BG_BG_PARAM` keyword handling
- `/tmp/aliens-test/desktops.cfg` — verified Aliens uses `BEGIN_BACKGROUND(...)` macro form, 4 desktops, `ADD_BACKGROUND_SCALED` for image, `SET_SOLID` for fallback
- `/tmp/aliens-test/textclasses.cfg` — TEXT1 has `__FORGROUND_COLOR 200 200 150` (unfocused) and (after `__NORMAL_ACTIVE`) the focused color
- `/tmp/aliens-test/imageclasses/borders.cfg` — TITLE_BAR_HORIZONTAL with `__NORMAL "artwork/n_title.png"` and `__EDGE_SCALING 3 2 3 2`
- `/home/cstory/src/wilbs/src/lib/themes/e16/extract-palette.ts` (321 lines) — production-validated saturation-weighted palette extraction; `0.3 + 0.7 * saturation` weight formula
- `/home/cstory/src/wilbs/src/lib/themes/e16/map-to-bundle.ts` (623 lines) — production palette source priority: `DESKTOP_BG → PAGER_BG → titlebar → border edge → dragbar`
- `kpackagetool6 -t Wallpaper/Images -s /usr/share/wallpapers/Next` — confirmed exit 0, structured output

**Pillow / stdlib documentation:**
- [Pillow `Image.quantize` docs](https://pillow.readthedocs.io/en/stable/reference/Image.html#PIL.Image.Image.quantize) — `Image.Quantize.MEDIANCUT` enum
- [Pillow Image File Formats](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html) — confirms PNG/JPG/GIF support
- [Python `configparser.RawConfigParser` docs](https://docs.python.org/3/library/configparser.html#configparser.RawConfigParser) — `optionxform`, `interpolation` settings
- [Python `os.replace` docs](https://docs.python.org/3/library/os.html#os.replace) — atomic-rename semantics, same-fs constraint

**KDE / Plasma:**
- [develop.kde.org/docs/plasma/wallpapers/](https://develop.kde.org/docs/plasma/wallpapers/) — Wallpaper plugin metadata.json schema with minimal example
- [discuss.kde.org: Where are .colors files stored in Plasma 6](https://discuss.kde.org/t/where-are-the-default-colors-files-stored-in-plasma-6/19873) — confirms `/usr/share/color-schemes/` and `~/.local/share/color-schemes/` paths
- [github.com/zzag/plasma5-wallpapers-dynamic issue #17](https://github.com/zzag/plasma5-wallpapers-dynamic/issues/17) — `KPlugin.Id` MUST match directory name

### Secondary (MEDIUM confidence)
- [docs.kde.org/stable_kf6/en/plasma-workspace/kcontrol/colors/](https://docs.kde.org/stable_kf6/en/plasma-workspace/kcontrol/colors/) — KCM Colors user docs
- [github.com/luisbocanegra/kde-material-you-colors](https://github.com/luisbocanegra/kde-material-you-colors) — third-party tool that auto-generates `.colors` files; useful as a reference for what fields matter
- [develop.kde.org/docs/plasma/theme/theme-details/](https://develop.kde.org/docs/plasma/theme/theme-details/) — Plasma Style theme docs (different from KColorScheme but cross-referenced)

### Tertiary (LOW confidence — flagged in Assumptions Log)
- The exact role-assignment table in §2 is a defensible heuristic, not validated against >100 themes. Visual gate at end of Phase 2 is the proof.
- `[Colors:Header][Inactive]` round-trip behavior of Python's `RawConfigParser` is untested; pitfall E covers the fallback.

## Metadata

**Confidence breakdown:**
- KColorScheme `.colors` format (§1): **HIGH** — verified byte-for-byte against three shipped examples (BreezeDark, BreezeLight, Edna)
- Plasma Wallpaper packaging (§3): **HIGH** — verified against three shipped examples + `kpackagetool6` smoke validation
- E16 background grammar (§4): **HIGH** — verified against `definitions:927-1010` and Aliens canary contents
- Color extraction algorithm (§2): **MEDIUM** — algorithm is defensible (mirrors production wilbs) but role-assignment table needs visual gate; final palette quality only confirmed by manual visual inspection
- report.txt format (§5): **MEDIUM** — three-section taxonomy is novel; categorization accuracy depends on prefix-tag adoption per Decision 5
- HTML preview (§6): **HIGH** — straightforward extension of Phase 1 pattern
- Atomic install (§7): **HIGH** — reuses Phase 1 primitive; only same-fs caveat to verify
- IR additions (§8): **HIGH** — additive frozen-dataclass extension; no churn through Phase 1 code
- Test strategy (§9): **HIGH** — syrupy snapshots + kpackagetool6 smoke + manual visual gate

**Research date:** 2026-05-01
**Valid until:** 2026-06-01 — Plasma 6 KColorScheme/Wallpaper formats are stable across 6.x; PyPI versions could drift but no new deps anyway.
