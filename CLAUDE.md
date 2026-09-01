## Project

**themey**

themey is a local Python CLI that converts Enlightenment DR16 (E16) `.etheme` archives into installable KDE Plasma 6 Look-and-Feel packages. It reads the legacy E16 config grammar (`__BORDER`, `__ICLASS`, `__TCLASS` blocks) and emits a complete modern KDE theme — Aurorae window decoration, color scheme, wallpaper, and XCursor pointer set — bundled as a one-click Plasma Global Theme. The goal is to actually run favorite 2009-era E16 themes on Plasma 6.6.4 day-to-day, not to produce a museum piece.

**Core Value:** A user runs `themey aliens.etheme` and within seconds is staring at a Plasma desktop visibly themed with that 16-year-old E16 theme — Aurorae frame, matching colors, wallpaper, cursor — all installed and previewable.

### Constraints

- **Tech stack**: Python 3.11+. Pillow for image manipulation, Typer for the CLI, standard library for the rest. No heavy frameworks. See Technology Stack below.
- **Compatibility**: Plasma 6.x. Linux only. Targets KWin's Aurorae decoration plugin (the standard one, included in every Plasma install).
- **Dependencies on E16**: zero runtime dependency — we read the source for grammar reference only.
- **Output discipline**: every install path is under `~/.local/share/...` so a conversion is fully reversible by deleting the named directories. No system-wide writes. No root.
- **Fidelity philosophy**: faithful where the format maps cleanly, sensible defaults where it doesn't (button grouping, missing button glyphs default to a system fallback). When the converter has to approximate, it logs to `report.txt`.

## Technology Stack

- **Python 3.11+**, managed with **uv** (`uv sync`, `uv run themey ...`);
  hatchling build backend, `src/` layout, `themey` console script.
- **Pillow** for every raster operation: open PNG/JPEG/BMP, 9-patch crops,
  NEAREST upscaling, median-cut color sampling, cursor frame rasterization.
- **Typer** for the CLI (`cli.py` is the only entry point).
- Standard library for everything else: `xml.etree.ElementTree` (SVG output),
  `configparser.RawConfigParser` (KDE INI), `tarfile` + `gzip` (`.etheme`
  reading), `pathlib`, `logging`, `json`.
- **`xcursorgen`** (the `xorg-xcursorgen` system package) is the one non-Python
  dependency — there is no pure-Python XCursor writer. When it is absent the
  cursor stage is skipped with a `cursors:` note rather than failing.
- Dev tooling: **pytest** + **syrupy** (text snapshots) + **imagehash** (phash
  visual regression), **ruff** for linting, **pyright** in `basic` mode.

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
- E16 cursor XBMs are parsed by hand in `generate/cursors.py` (~40 lines: a
  `#define` regex plus the `_bits[]` array). Do NOT "simplify" that back to
  Pillow's `XbmImagePlugin` — its header regex is anchored at `#define`, so
  GIMP-authored files (Mac3D's open with a `/* Made with GIMP */` comment)
  fail outright, and its hotspot sub-pattern `[^_]*_x_hot` cannot match
  multi-underscore names like `resize_h_x_hot`, which nearly every fixture
  uses. The second failure is the dangerous one: the hotspot is dropped
  silently and every pointer ends up mis-anchored.

**Output**

- `RawConfigParser` with `optionxform = str` for KDE INI — the default
  `ConfigParser` lowercases KDE's case-sensitive keys (`BackgroundNormal`,
  `LeftButtons`), and its `BasicInterpolation` chokes on the `%` that turns up
  in font names. A hand-rolled writer for `.desktop` files, because localized
  keys like `Name[de]=Foo` look like section headers to configparser.
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
- Verify with `uv run pytest`, `uv run ruff check .`, `uv run pyright src`.
  `ruff format` is NOT applied to this codebase and must not be run — see
  `CONTRIBUTING.md`.

## Architecture

Pipeline: `.etheme` → ingest → analyze → generate → install → report + preview.
`pipeline.convert()` composes it; `cli.py` is the only entry point.

Two backends. **`qml` is the default** (since 2026-08-30): a KWin/Decoration
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
| `generate/wallpaper.py` | One Plasma wallpaper package per E16 background image (`WallpaperPackage`); PNG/JPEG/BMP copied through at real dimensions, everything else re-saved as PNG. Two `SET_SOLID` exceptions: alpha-carrying sources with a solid underneath are flattened over it (e13's tanbg.png over black — E16 composites the tile over the solid), and a SET_SOLID-only block (OPENSTEP) becomes a small flat 128×128 package. `pick_default` ranks by `(not solid, area)` — a solid never outranks art |
| `generate/cursors.py` | E16 `__CURSOR` → XCursor pointer theme via the hand-rolled XBM parser + `xcursorgen`; modern Plasma 6.6 names canonical, legacy X11 names as symlinks |
| `generate/plasmastyle.py` | Plasma Style (`Plasma/Theme` KPackage under `plasma/desktoptheme/themey_<slug>/`, selected by the bundle's `[plasmarc][Theme] name=`) — panel/popup/tooltip/pager chrome as KSvg FrameSvg sets. Deliberately sparse: ship an SVG only where E16 has real counterpart art and let Breeze fill in per missing file, re-tinted through the package's own `colors`. Every shipped SVG is mirrored byte-identically into `solid/` and `opaque/`. The panel background ships real dragbar/iconbox art (middle TILED via `hint-tile-center` — the only file allowed that hint; `west-`/`east-` sets from the vertical bar art) when a candidate passes the shaped + `PANEL_MAX_REF_CAPS` guards (baked-in wordmarks live in the caps and would stretch unreadably across a 40 px panel); guard failures fall back to the flat translucent tint, whose mirrors alone are re-rendered opaque. `widgets/tasks.svg` comes from the iconbox button art (focus = clicked art); `dialogs/background.svg` composes MENU_T/B/L/R strip pieces around the center when authored (corners only when dims match the adjacent strips — FrameSvg stretches a corner to the border thicknesses) |
| `generate/lookandfeel.py` | Plasma Global Theme (Look-and-Feel) bundle writer — `metadata.json` + `contents/defaults`, one conditional INI group per artifact this conversion actually deployed |
| root modules | `ir.py` (IR), `paths.py` (XDG install roots), `install.py` (atomic deploy — `deploy` for package dirs, `deploy_file` for single files like `.colors`, `clear_style_cache` for the Version-keyed plasmashell kcache, called at both convert and apply time), `report.py`, `preview.py`, `kwin.py`, `render.py`, `apply.py`, `external.py` (xcursorgen wrapper), `slug.py` (naming contract), `log.py` |

**Naming contract.** Every Global-Theme artifact for one conversion derives
from `slug.plugin_id(theme.name)` = `themey_<slug>`, deliberately reused
across namespaces so `themey apply <name>` can resolve any of them: it is
the QML decoration KPackage dir name AND kwinrc `theme=` value
(`kwin/decorations/`), the Look-and-Feel bundle's `KPlugin.Id`
(`plasma/look-and-feel/`), the `.colors` stem / `[General]
ColorScheme=` value (`color-schemes/`), AND the Plasma Style package dir /
`[plasmarc][Theme] name=` value (`plasma/desktoptheme/`) — four different
namespaces, same string, on purpose. `slug.wallpaper_id(name, stem)` widens it to
`themey_<slug>_<stem-slug>` (one wallpaper package per source image,
hyphens left alone since these ids are never QML/JS identifiers).
`slug.cursor_theme_dir(name)` narrows it to `themey_<slug>-cursors` (an
XCursor theme has no KPlugin id; the directory name itself is the
`kcminputrc cursorTheme=` value). `paths.py` gained one XDG root per new
namespace: `color_schemes()`, `wallpapers()`, `cursor_themes()` (XCursor themes go
to `~/.icons`, NOT `$XDG_DATA_HOME/icons` — libXcursor/the cursor KCM on
stock Kubuntu never scan the XDG dir; verified live 2026-08-31),
`desktop_themes()`, `look_and_feel()`, alongside the
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
scheme is installed; `PrevPlasmaTheme` and `PrevPanelLengthModes` follow the
same pattern for the Plasma Style and the per-panel `lengthMode` map), run
`plasma-apply-lookandfeel -a
themey_<slug>` (never `--resetLayout`), then `plasma-apply-colorscheme
themey_<slug>` — REQUIRED, not belt-and-braces: verified live on Plasma
6.6.6 (2026-08-31) that `plasma-apply-lookandfeel -a` does NOT apply the
bundle's color scheme past an explicit user-layer `ColorScheme` (it updated
kcminputrc's cursor but left even `kdedefaults/kdeglobals` on the old
scheme) — then, when the Plasma Style package is installed,
`_clear_style_cache` followed by `plasma-apply-desktoptheme themey_<slug>`
(explicit for the same user-layer-shadowing reason; the cache clear must
come first or plasmashell repaints from the stale Version-keyed kcache of a
previous conversion) — re-assert the decoration keys via
the same `_write_deco` the deco-only path uses (required even though the
LnF apply already wrote deco defaults — those land in the
`~/.config/kdedefaults/` layer, and only an explicit user-layer write is
guaranteed to win), then `_set_panels_fit` (every panel's `lengthMode` to
`fit` — E16's iconbox/dragbar are content-sized and a full-width bar reads
as Plasma, not E16), then `_ensure_furniture` (E16's left-edge furniture:
a thick content-sized pager panel hugging TOP-left — E16's pager window
spot — and a slim iconbox panel hugging BOTTOM-left with an icons-only
task manager showing only MINIMIZED windows; TWO panels because pager
cell size is thickness ÷ desktop-grid columns while task-icon size IS the
thickness (a shared 60px panel shrank pager cells to ~26px slivers,
verified live 2026-08-31); created via plasmashell scripting, `[Themey]
PagerPanel`/`IconboxPanel` markers hold the containment ids — artifact
markers, not
`Prev*` baselines: overwritten when the recorded panel is gone, skipped
when alive, deleted when revert removes the panel; placed after the fit
step so the new panels never pollute `PrevPanelLengthModes`; creation
scripts set `p.minimumLength = 0` — a scripted `new Panel` starts with
min=max=full-screen and `lengthMode='fit'` never clears it — and the
pager gets `showOnlyCurrentScreen=true` so multi-head cells keep desktop
aspect). Just before the furniture, `_set_desktop_grid_column` stacks the
desktops one per row (kwinrc `[Desktops] Rows=Number` AND the writable
`VirtualDesktopManager.rows` D-Bus property — KWin reads the config key
only at startup, verified live 2026-08-31; `PrevDesktopRows` baseline,
restored on revert). Then the
tiled-wallpaper fix-up, and one `qdbus`
reconfigure last. The panel steps come BEFORE the wallpaper one on
purpose: the wallpaper step is the likeliest to raise, and a failed apply
should still have delivered the panel feel.

`_set_wallpaper_tiled` runs when the bundle's default wallpaper package's
`X-Themey-FillMode` is `tiled`, and it takes TWO steps because
`plasma-apply-wallpaperimage -f` exposes no tile token at all on Plasma
6.6.6 (verified live 2026-08-31: every spelling of tile is "Invalid fill
mode"; only the camelCase QML names
`stretch`/`preserveAspectFit`/`preserveAspectCrop`/`pad` are accepted, and
Plasma's Image wallpaper plugin doesn't read fill-mode from the package
either). So: `plasma-apply-wallpaperimage <image>` sets the image, then a
plasmashell scripting D-Bus call writes `FillMode =
_WALLPAPER_TILE_FILL_MODE_INT` (3, QML `Image.Tile`) on every desktop's
Image wallpaper config. The CONFIG lands (KCM shows Tiled) but plasmashell
6.6.6 does NOT repaint fill-mode from ANY scripting write (verified live
2026-08-31 — FillMode alone, +reloadConfig, even an Image swap left the
render pixel-identical), so a tiled apply ends with
`systemctl --user restart plasma-plasmashell` (`_restart_plasmashell`,
dead last so it can't race any evaluateScript; failure = warning, never a
failed apply; opt-out `--no-restart-shell`).

`themey apply --revert` reads
the markers back, reapplies the recorded Look-and-Feel package (no
Breeze special-case — a real baseline is typically a third-party theme,
e.g. `com.github.vinceliuice.MacVentura-Dark`), restores the deco
triple, button layout and panel length modes, removes the themey-created
iconbox panel (before the panel-mode restore, so that script iterates only
surviving panels), then clears the markers it
actually restored; a
failure to reapply the recorded package does NOT abort the rest of the
restore, and `PrevLookAndFeelPackage` is deliberately kept in that one case
so a later `--revert` can retry just the theme restore (`PrevColorScheme`
and `PrevPlasmaTheme` get the same keep-on-failure treatment; their
`@unset` case deletes the
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
`_run_checked` follows the same shape, and every external write in that
module funnels through it — the `plasma-apply-*` tools and the plasmashell
scripting D-Bus calls alike.

**Report prefixes.** `report.py` categorizes `theme.notes` by string
prefix into the report's Approximated section: `aurorae_rc:`, `bundle:`,
`colors:`, `composite:`, `cursors:`, `plasmastyle:`, `qmldeco:`,
`wallpaper:` are surfaced
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
`themey render --target style` screenshots the Plasma Style's FrameSvg sets
(panel/popup/tooltip/tasks) via a plasmoidviewer probe applet in the same
nested session — the verification vehicle for `generate/plasmastyle.py` work.
`scripts/render_review.py` is a fast SVG approximation and can disagree with
KWin; it knows nothing about the QML backend.

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.

