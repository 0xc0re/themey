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
- `Image.Resampling.NEAREST` for border art by default. TWO carve-outs, both
  opt-in, both QML-backend-only, and both LANCZOS on already-smooth input,
  never on raw pixel art — the two smoothing `--upscale` modes overshoot to a
  factor their scaler supports and come back down: (1) `quality` — hqx in
  `images/hqx.py`, and `upscale.py`'s quality mode may LANCZOS-*downsample*
  hqx(ceil(scale)) output to a fractional target; (2) `waifu2x` —
  waifu2x-ncnn-vulkan scales by powers of two ONLY, so `_waifu2x_factor` picks
  the smallest supported factor ≥ scale (2 up to scale 2, 4 above it) and the
  surplus comes off with LANCZOS onto the same `scale_px` target. Unlike hqx,
  waifu2x anti-aliases the ALPHA too and themey keeps that: E16's 1-bit mask
  re-imposed would re-staircase the very edges the CNN reconstructed, the QML
  `BorderImage` composites RGBA correctly, and `images/opaque.py`'s coverage
  vote is SVG-backend-only, which no smoothing mode reaches. No other LANCZOS
  under `src/themey/images/`.
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
| `etheme/` | `archive.py` (validating tar extract), `lex.py`, `parse.py`, `ast.py` — the E16 grammar front end. The lexer follows E16's `config.c` line reader + `sscanf("%s")`: a token is one whole whitespace-delimited word in ANY case, classified afterwards (IDENT / NUMBER / STRING — punctuated names like `pager_titelleiste-` round-trip verbatim, keywords stay the `__UPPER` set), quotes glue onto touching text (`"BUTTON_"ICONIFY` is one word, the Base family's button iclasses), `//` starts a comment (epp runs with C++ comments on), and numeric fields go through `ast.atoi` (`19P` → 19, `--` → 0). Fixed 2026-09-01: the old `[_A-Z]`-only IDENT dropped lowercase names and left WashedBlue/eLap/LiteGnome with mangled or shared iclasses. `#include <definitions>` resolves to the bundled verbatim E16 1.0.31 `config/definitions` (`etheme/data/`, MIT-style `E16_COPYING`) — every corpus `menustyles.cfg` (223/223) is written with `NORMAL_/NEXTSTEP_MENU_STYLE_VERTICAL(...)`. Every FUNCTION-like macro registers; of the object-like ones, those named `__*` or `XC_*` are SKIPPED (`_IDENTITY_DEFINE`) because that prefix pair is exactly E16's own vocabulary — the numeric keyword ids (`__BGN 999`, `__ON 1`), the `XC_*` cursor constants and the `__A_*` action macros whose bodies are IPC command lines (`__A_KILL` → `wop * close`), and expanding any of them replaces the keyword grammar with numbers or an action's identity with a command string (`analyze/aclasses.py` reads the `__A_*` NAME). The 36 that remain are all block-structure sugar and DO expand — fixed 2026-09-02: `END_SLIDEOUT`/`END_BORDER`/`END_IMAGE`/`END_MENU`… → `__END`, `BEGIN_FONTS` → `__FONTS __BGN`, `TEXT_JUSTIFY_CENTER` → `__JUSTIFICATION 512`, the `__ON` flag shorthands; while they were skipped, every `BEGIN_*`/`END_*` pair was left unterminated and the block swallowed everything after it (Ganymede's `__ACLASS` blocks ended up inside an unclosed `__SLIDEOUT`, costing it every window button). Default entry files mirror E16's `ThemeConfigLoad` order where themey has a consumer: borders, imageclasses, textclasses, cursors, tooltips, menustyles, windowmatches — plus `actionclasses.cfg`, `buttons.cfg`, `slideouts.cfg` read in a SEPARATE pass by `build_theme` (`ACLASS_ENTRY_FILES`), which takes only their `__ACLASS` blocks: they also carry desktop-furniture `__ICLASS`/`__BUTTON` blocks, and folding those into the main node list would change what every other analyzer sees. The mini-cpp honours `#if/#ifdef/#ifndef/#elif/#else/#endif` (integer literals, `defined(X)`, macro names; E16's always-present epp symbols `ENLIGHTENMENT_*`/`ECONFDIR`/`ECACHEDIR` count as defined, `THEME_VARIANT_*`/`SCREEN_*` do not) — eMac's `#ifdef` colour variants used to all apply, last wins |
| `analyze/` | AST → frozen `ir.Theme`: iclass resolution, state collapse, button binning, coordinate math, borders, `aclasses.py` (`__ACLASS __BGN` blocks → `{name: primary __A_* verb}`, last-wins per `aclass.c:321-332`'s `ActionclassEmpty` refill; `stock_aclasses()` parses the bundled verbatim E16 `config/actionclasses.cfg` and is layered UNDER the theme's own blocks — E16 skips its stock file once the theme ships one, themey keeps it so a stock name the theme omits still resolves. Feeds tier 1b of `buttons.py`/`qmldeco/actions.py`: a border part's `__ACLASS <name>` used to be matched against a fixed table of STOCK names only, so every theme-private name was an `unknown_aclass` drop — Ganymede binds its close button to `ACTION_GANYMEDE_KILL` and shipped with no clickable buttons at all. `VERB_TO_BUTTON` maps the verb (`__A_KILL`→X, `__A_MAX_*`/`__A_ZOOM`/`__A_FULLSCREEN`→A, `__A_ICONIFY`→I, `__A_SHADE`→L, `__A_STICK`→S, `__A_RAISE`→F, `__A_LOWER`→B, `__A_SHOW_MENU`/`__A_SLIDEOUT`→M — a slideout is "a bar of more buttons to control the Window with", which is KWin's window menu), `VERB_DROP` silently drops move/resize/desktop/launcher verbs as `ACLASS_DROP` does their stock names, and `_VERB_APPROXIMATIONS` notes each inexact swap. 54 unresolvable parts → 17 across the corpus, 31 themes gained 37 buttons 2026-09-02; the 17 that remain name a class NOTHING defines, which is inert in E16 too), `menus.py` (`__MENU_STYLE` → `MenuStyleSpec`: `__BG_ICLASS`/`__ITEM_ICLASS`/`__SUBMENU_ICLASS`/`__USE_ITEM_BACKGROUNDS`; with item backgrounds ON the bg iclass is None because E16's `MenuRedraw` never paints one — every row wears the item iclass, menus.c:928-985), `tooltips.py` (`__TOOLTIP` → `TooltipSpec`: name, `__ICLASS`, `__TCLASS`, the four positional `__BUBBLEn_ICLASS` clouds, `__DISTANCE`, `__TOOLTIP_HELP_ICON`; the first block that actually REGISTERS wins because `TooltipConfigLoad` skips a block whose name `TooltipFind` already knows, tooltips.c:170 — the opposite of menu styles — while a block without name+iclass+tclass, or naming an iclass the theme never defines (`_TtCreate`'s `ImageclassAlloc(ic0, 0)` has no fallback, tooltips.c:102), registers nothing and gets a `tooltips:` note; all 223 corpus themes define DEFAULT/ICONBOX/PAGER through the `DEFINE_TOOLTIP*` macros), `fonts.py` (__FONTS scan; `XLFD_FAMILY_ALIASES` maps the X11 core families fontconfig has no alias for — lucida → DejaVu Sans (Vera, Lucida's foundry lineage), fixed/lucidatypewriter → DejaVu Sans Mono, clean → sans-serif — while helvetica/times/courier pass through to fontconfig's own Nimbus/Liberation aliases; the authored name stays in `FontSpec.source_family` and each distinct mapping gets a `fonts:` note), `wallpaper.py` (text pipeline over `desktops.cfg` + its archive `#include`s: `ADD_BACKGROUND_*` macros expanded to the raw `__BACKGROUND_LAYER file tile keep_aspect xjust yjust xperc yperc` tuple from `config/definitions:943-1009`, so Rebound/Fossils' hand-written raw blocks parse too; `fill_mode_for_layer` maps the tuple — never the macro name — onto `stretch`/`tile`/`tile-h` (scaled to screen height, tiled across — the gradient-strip TILED_SCALED_VERTICALLY)/`tile-v`/`pad` (CENTERED)/`fit` (SCALED_RETAIN_ASPECT and ALIGN_*, alignment lost + noted); `__FORGROUND_LAYER` overlays stay note-only), `windowmatches.py` (`__MATCH_WINDOW` → `IconMatchSpec(kind, pattern, image)`: the `__USE_ICON` rules the bundled `USE_ICON_IMAGE_FOR_CLIENT_{CLASS,NAME,TITLE}` macros expand to — E16 1.0.31's ONLY per-app icon hook, no `icondefs.cfg`; dropped with an `icons:` note when the image is not a file in the archive (Egradient names an iclass), the pattern is a catch-all (Hazard's `__HAS_TITLE *`) or no criterion is set; `__USE_BORDER` blocks are backlog), `colors.py` (median-cut sampling of the theme's own border art into a full 8-group `ColorScheme` + the 4-field `[WM]` active/inactive background+foreground set, WCAG-AA-guarded) |
| `images/` | `ninepatch.py`, `opaque.py`, `upscale.py` (`upscale_part`: scale_px-dim targets, one explicit branch per `UPSCALE_MODES` entry — nearest/quality/waifu2x — and a raise on the fall-through, because every mode past the `nearest` early-returns used to become hqx silently), `hqx.py` (in-tree quality scaler), `waifu2x.py` (the `(img, factor) -> img` shape hqx has, over a temp-PNG round trip through `external.run_waifu2x`), `embed.py` — raster primitives, NEAREST default |
| `generate/qmldeco/` | DEFAULT backend: `theme_js.py` (part model, `SHADE_BUTTON_MODES`), `resolver.py` (E16 geometry, Python mirror), `actions.py`, `package.py`, `runtime/` (4 verbatim QML/JS files) |
| `generate/` (rest) | SVG backend: `aurorae.py` orchestrates `decoration_svg.py`, `aurorae_rc.py`, `aurorae_meta.py`, `button_svg.py`, `composite.py` |
| `generate/colors.py` | `.colors` writer — the 13-group/12-key Breeze-shaped file census; sampled colors from `analyze/colors.py`, semantic foregrounds + ColorEffects verbatim from Breeze stock |
| `generate/wallpaper.py` | One Plasma wallpaper package per E16 background image (`WallpaperPackage`); PNG/JPEG/BMP copied through at real dimensions, everything else re-saved as PNG. Two `SET_SOLID` exceptions: alpha-carrying sources with a solid underneath are flattened over it (e13's tanbg.png over black — E16 composites the tile over the solid), and a SET_SOLID-only block (OPENSTEP) becomes a small flat 128×128 package. `pick_default` ranks by `(not solid, area)` — a solid never outranks art. `metadata.json` carries `X-Themey-FillMode` (the six-mode vocabulary above) and, when the block had a SET_SOLID, `X-Themey-SolidColor` (`r,g,b`) for the fit/pad letterbox |
| `generate/icons.py` | `windowmatches.cfg` `__USE_ICON` rules → a per-app XDG icon theme `themey_<slug>-icons` under `paths.icon_themes()` = `$XDG_DATA_HOME/icons` (scanned by KIconTheme, unlike the cursor root): `48x48/apps/<Icon>.png` (NEAREST-fitted, E16's iconbox `iconsize = 48`) for every `.desktop` entry an E16 rule matches — `fnmatch.fnmatchcase` like E16's `regex.c` (flags 0): `class` → `StartupWMClass=` else the file stem, `name` → `Exec=` argv0 else stem, `title` → `Name=` (approximate, noted); first rule wins per icon name, absolute-path `Icon=` skipped, hand-rolled `.desktop` reader (localized keys break configparser), `applications_dirs()` reads `$XDG_DATA_HOME`/`$XDG_DATA_DIRS` at call time; `index.theme` `Inherits=breeze,hicolor` is static (the user's icon theme is restored on revert). Low yield by design (11/223 corpus themes carry rules, 5 working) — chris opted in 2026-09-01. Nothing shipped → `None`, no dir, an `icons:` note |
| `generate/cursors.py` | E16 `__CURSOR` → XCursor pointer theme via the hand-rolled XBM parser + `xcursorgen`; modern Plasma 6.6 names canonical, legacy X11 names as symlinks. Polarity is E16's, NOT X11's: E16 swaps fg/bg for every theme cursor (`eimage.c:783-789`, `cursors.c:71-74` — "pmap bits in all theme cursors are inverted"), so a mask-set pixel whose image bit is SET paints `__BG_COLOR`, image bit CLEAR paints `__FG_COLOR`, mask-clear is transparent. Which element that colors depends on the theme's bitmap (Aliens: black arrow, white outline; Yellow: yellow arrow); every pointer was color-inverted before 2026-09-01 |
| `generate/plasmastyle.py` | Plasma Style (`Plasma/Theme` KPackage under `plasma/desktoptheme/themey_<slug>/`, selected by the bundle's `[plasmarc][Theme] name=`) — panel/popup/tooltip/pager chrome as KSvg FrameSvg sets. Deliberately sparse: ship an SVG only where E16 has real counterpart art and let Breeze fill in per missing file, re-tinted through the package's own `colors`. Every shipped SVG is mirrored byte-identically into `solid/` and `opaque/`. The panel background is three layers in one file: the UNPREFIXED set carries only small-cap art (both axes ≤ `PANEL_MAX_REF_CAPS`, the iconbox trough typically) or the flat translucent tint — plasmashell turns the unprefixed set's caps into EVERY panel's minimum thickness regardless of prefix (verified live 2026-09-01: e13's 60 px wordmark caps forced the 60 px iconbox panel to 120 px even with a `west-` set present); the `north-`/`south-` sets carry the wordmark dragbar art (length-axis caps up to `PANEL_MAX_REF_LENGTH_CAPS`, pinned like E16 did, margin hints hugging them at `cap − 4` output px) only on bars ≥ `PANEL_WORDMARK_MIN_THICKNESS_REF` (24 ref px) thick, because the panel stretches the whole bar to its thickness and e13's 6 px strip smeared its E ten times taller; the `west-`/`east-` sets dress the left-edge furniture from `ICONBOX_VERTICAL` first (E16's iconbox art — the vertical dragbar knob stretched over a 60 px panel read as a rotated E). Middles are STRETCHED whenever E16 stretched them (the default `__FILLRULE` — `hint-tile-center` only when E16 itself tiled, `IClassSpec.fill_for(state)`; tiling repeated photographic troughs across HandOfGod and NorthernLights bars, verified live 2026-09-01). Shaped art is rejected everywhere; a tint fallback's mirrors alone are re-rendered opaque. `widgets/viewitem.svg` (MENU_SEL) picks caps per art shape (`_viewitem_caps`): rounded pills (a shape-mask-cut corner, `_is_rounded`) or zero-declared axes get the cross-section radius pin; opaque rectangular strips honor the declared `__EDGE_SCALING` (OldE's 3 px bevels — the radius pin left a 2-row middle Kickoff stretched 10x), and when that strip's middle is grain rather than gradient (`_middle_is_textured` over `_band_stats`' three luminance stdevs — RESIDUAL grain ≥ 8 after both marginals are removed, vertical drift ≤ 8 and < grain/1.5, horizontal drift ≤ 1.5·grain; Aliens' bone-textured glow drifts 13.5 vertically and banded when repeated, ShinyMetal's left-to-right sheen has grain 3.8 against drift_h 36.9 and seamed, while OldE's streaky rust 10.4/4.0/10.2 stays tiled — `scripts/audit_viewitem.py` is the corpus-wide calibration table) it is tiled, since E16 rows were the art's own height and Plasma rows are ~2x taller. Every viewitem set is capped at `VIEWITEM_MAX_ROW_CHROME_PX` (24) OUTPUT px of top+bottom caps — past it the set stays at source scale (`_emit_set(max_v_chrome_px=)`), because a Kickoff sidebar row is ~30 px and FrameSvg paints a degenerate sliver when the caps do not fit (StarEnli's 27 px pill at 1.5x = 36 px of caps, chris's screenshot 2026-09-01) — and NO `normal-` set is ever shipped: `PlasmaExtras.Highlight` paints `normal` for a current-but-unhovered item at 0.6 opacity (Kickoff forces `hovered: true`, Kicker/folder views do not) while E16 painted it on every row, and Breeze ships none. `widgets/line.svg` (DIALOG_WIDGET_SEPARATOR) takes its thickness from the iclass `__PADDING` like E16's `DITEM_SEPARATOR` (`dialog.c:1048-1056`: h = pad.t+pad.b, w = pad.l+pad.r; 127 corpus themes 2 px, 73 4 px, 13 undeclared → art dim), the art trimmed to its opaque span on the thickness axis and centred when thinner (`_rule_art`; LCARS's 1×16 art has ONE opaque hairline row, and a NEAREST squeeze of 16 rows into 4 dropped it) else squeezed into it, both capped at `LINE_MAX_REF_THICKNESS` (LCARS 8+8) — never the art's own dimension (StarEnli's 46 px-wide strip gave a 4 ref px vertical rule). `widgets/frame.svg` (DIALOG_WIDGET_AREA) is a RING with a fully transparent `center` (`_emit_set(clear_center=)`, ring = max(caps, scaled padding) per side): E16's `DITEM_AREA` covers the interior with the area window (`dialog.c:776-783`), and all 223 corpus themes have an opaque centre (14 solid, StarEnli magenta) that shipped whole as the GroupBox background. `widgets/tooltip.svg` styles ONLY QQC2 `PlasmaComponents3.ToolTip` (its QML hardcodes the `solid/widgets/tooltip` mirror); task-manager and pager hover tooltips are `PlasmaCore.ToolTipArea` → `PlasmaQuick::Dialog`, painted from `dialogs/background.svg` (corrected 2026-09-01 — the earlier docs credited tooltip.svg with those). `widgets/tooltip.svg` and the `colors` Tooltip group come from the parsed DEFAULT `__TOOLTIP` block — `TooltipShow` (tooltips.c:752) looks that name up for every window/button hint — its `__ICLASS` first (11 corpus themes name TT_MINI/BAR/COORDS/TT_CLOUD, and had no tooltip art before 2026-09-01) then the `TT_MAIN` convention — an artless DEFAULT iclass is passed over with a note; NO shaped-art rejection, because 45 corpus TT_MAINs (Aliens, e13, OldE) are 10-31% transparent from rounded corners the emit path trims, and they shipped before — and its `__TCLASS` when the theme defines it (88 name TEXT1/TEXT2/COORDS/…; two name an iclass by mistake — E16 painted its built-in fallback tclass, themey paints `TT_TEXT` and notes it); `widgets/tasks.svg` comes from the iconbox button art (focus = clicked art; `launcher-hover-`/`focus-hover-` only with explicit hilited art; `--iconbox-frames off` is the DEFAULT since 2026-09-01 and replays E16's own frameless iconbox — `container.c:98-114` `draw_icon_base = 0` — as 1 px center-only sets with margin hints from the iconbox trough's `__PADDING`, because skipping the file would bring Breeze's plates back, while `on` ships the button art as per-icon plates. A prefix whose E16 chain falls back to the NORMAL art is SYNTHESIZED instead (`_synth_task_states`, one note listing which): nearly every corpus iconbox button declares only `__NORMAL`, which made all seven sets byte-identical and left the active, minimized and hovered task indistinguishable (219/223 synthesize at least one state) — `hover`/`progress` blend the plate 12% toward white, `attention` blends the HOVER plate a further 25% (compounded 34% — off the normal plate it landed only 13% above hover and the two read alike), `minimized` fades it to 55% alpha, `focus` flips it VERTICALLY (an E16 bevel's light and dark edges swap = the depressed button), and `focus-hover` composes both — the 12% hover lighten over that flipped plate, since as plain `focus` the active task under the mouse gave no hover feedback at all. Every `_TASKS_BAR_STATES` entry (`focus`, `focus-hover`) additionally wears a `TASKS_FOCUS_BAR_PX` (2 OUTPUT px, unscaled) accent bar on the panel-adjacent edge. Every synthesized set slices with the plate's own `fill_for` (`_TaskPlate.tile_center`) — a tiled `normal-` beside stretched synthesized sets changed the frame's texture on hover — and, when the iclass declares no `__PADDING`, with explicit `hint-<side>-margin` rects from the plate's caps (`_bar_margins`): the bar edge is 2 px thicker than every other set's border, and FrameSvg reads an unhinted side's margin off that thickness, so the active task's icon used to shift, one set per `_TASKS_FOCUS_EDGES` entry (unprefixed = bottom, plus Breeze's own `north-`/`west-`/`east-`; `Task.qml`'s prefix chain is `["<edge>-<p>", "<p>"]` so the unprefixed set IS the bottom-panel one). The bar is a `class="ColorScheme-Highlight" style="fill:currentColor"` rect inside the border `<g>` plus a `<style id="current-color-scheme">` sheet — KSvg swaps that sheet's body for the ACTIVE scheme's classes, so the accent tracks the scheme instead of baked pixels (verified headless 2026-09-01: the bar rendered the package's own `[Colors:Selection] BackgroundNormal`, not the authored fallback). Frames-OFF keeps the same states as a white wash (`_TASKS_OFF_ALPHA`, `focus-hover` = the hover alpha) plus the bar. `metadata.json` `X-Themey-TasksHover` = whether a tasks.svg ships at all — always true in frames-OFF, and in frames-ON whenever the theme has iconbox button art, since the hover frame is now synthesized when `__HILITED` is absent — which apply writes into the iconbox task manager's `taskHoverEffect`); `dialogs/background.svg` composes MENU_T/B/L/R strip pieces around the center when authored (corners only when dims match the adjacent strips — FrameSvg stretches a corner to the border thicknesses). The popup center/background source (`_dialog_candidates`) is the parsed DEFAULT (else ROOT) menu style first — its `__BG_ICLASS` whatever it is named (TinyPlatinum names DIALOG, Aliens MENU_SEL), or with `__USE_ITEM_BACKGROUNDS __ON` (NeXTSTEP style: OldE, OPENSTEP, NewSTEP, 8 corpus themes) the `__ITEM_ICLASS` normal art with its centre box painted FLAT in the strip's dominant colour (`_flat_center`, the same `extract_dominant` the Window colour group samples) inside the strip's own bevel — E16 stacked that strip per row and drew no menu background at all, and repeating the strip (`hint-tile-center`, the behaviour until 2026-09-01) painted its bevel rows as stripes across a 600 px Kickoff on the live desktop; tiling remains only as the fallback when the art yields no dominant colour — then the MENU_BG → DIALOG name convention; shaped art is skipped at every step, and the `colors` Window group samples the same source. The package's OWN `colors` (`style_scheme`) re-anchors the panel-facing groups to the art actually shipped: Selection samples the CLICKED MENU_SEL art because that is what Kickoff paints on press (`Highlight.qml` paints `hover` for the current item — `hovered` is true inside any view, at 0.6 opacity when the view lacks focus — and `selected+hover` only while the mouse is down), its label colour prefers the menu tclass's EXPLICITLY declared clicked colour (an absent one resolves through `TextclassPopulate` to the untouched row's normal) and is guarded against both the pressed and hover plates, falling back to guarding the PRESSED plate alone when no colour clears WCAG AA on both — 8 corpus themes, a near-white hover over a near-black clicked admits none, and the pressed plate is what sits behind the label. `Colors:View` is re-derived one ladder step from the POPUP surface (`analyze.colors.view_from_window`) rather than the sampled border tint, which had put ShinyMetal's search field at rgb(6,6,6) inside a 148-grey Kickoff (206 corpus themes move). `selected+hover-` is the clicked art at `VIEWITEM_PRESSED_HOVER_BRIGHTNESS` (1.08, RGB only, alpha put back verbatim so the shape mask survives) so it is not byte-identical to `selected-`; and when the theme yielded no accent at all (`ColorScheme.accent_fallback`, 150 corpus themes) every group's `DecorationFocus`/`DecorationHover` re-points to that Selection background instead of Breeze blue. This is the Plasma Style package's `colors`, i.e. plasmashell — the standalone `.colors` scheme `generate/colors.py` writes for Dolphin/System Settings still comes from the raw sampled scheme and carries none of it |
| `generate/plasmoids/` | themey's OWN applets, theme-agnostic by design (no art inside — everything comes at runtime from the ACTIVE Plasma Style via KSvg, so one panel configuration survives re-converts of any theme): `org.themey.pager` (E16's pager in LIVE mode — live wallpaper minis read from `org.kde.PlasmaShell.wallpaper <screen>` over D-Bus on load/every `wallpaperPollSeconds`/each desktop switch, never baked; one `TasksModel` per desktop cell painting `widgets/pager` `window-`/`window-active-` PAGER_WIN rects, stock-style textColor rects when the style has no `window-center`; PAGER_SEL = `active-` on the current desk; cell click switches desktops through KWin's readwrite `VirtualDesktopManager.current`, rect click `requestActivate`) and `org.themey.deskbutton` (one end of E16's dragbar, config `direction=next|prev`; `widgets/themey-dragbar.svg` `<next|prev>-<horiz|vert>-<state>`, `widgets/arrows` fallback). D-Bus goes through the Plasma5Support executable `DataSource` — deprecated-but-shipped on 6.6, the only in-stack shim applet QML has. Packages under `paths.plasmoids()` = `$XDG_DATA_HOME/plasma/plasmoids/<id>/`, rewritten on every convert (`install.deploy`), `X-Themey-Runtime` = `RUNTIME_VERSION`. Verify with `themey render --target pager` (panel-containment plasmoidviewer in the nested KWin with `KWIN_WAYLAND_NO_PERMISSION_CHECKS` so libtaskmanager gets the window-management protocol; plasmoidviewer reports its own window as the applet's `screenGeometry`, which is why the QML takes the cell aspect from the `Screen` attached property and drops the screen filter when that rect is not the window's screen) |
| `generate/lookandfeel.py` | Plasma Global Theme (Look-and-Feel) bundle writer — `metadata.json` + `contents/defaults`, one conditional INI group per artifact this conversion actually deployed. `WIDGET_STYLES` (`windows`→`Windows`, `fusion`→`Fusion`, `breeze`→`Breeze`) is the one vocabulary behind `--widget-style` on both `convert` and `apply` (`cli.WidgetStyle` mirrors its keys for Typer, a test pins them in sync): the token stamps `X-Themey-WidgetStyle` with the QT style name and emits `[kdeglobals][KDE] widgetStyle=` in the defaults, both omitted entirely when no style was asked for — every polished Plasma look in the wild ships an application style, and Qt's built-in `Windows` is the only period-correct one installed here |
| root modules | `ir.py` (IR), `paths.py` (XDG install roots), `install.py` (atomic deploy — `deploy` for package dirs, `deploy_file` for single files like `.colors`, `clear_style_cache` for the Version-keyed plasmashell kcache, called at both convert and apply time), `report.py` (takes the EFFECTIVE `upscale=` so the Approximated line names the scaler that actually ran — it hardcoded "NEAREST" through every `--upscale quality` run until 2026-09-02, and a waifu2x run that fell back must read hqx), `preview.py`, `kwin.py`, `render.py`, `apply.py`, `external.py` (xcursorgen + waifu2x wrappers), `slug.py` (naming contract), `log.py` |

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
`kcminputrc cursorTheme=` value); `slug.icon_theme_dir(name)` likewise
to `themey_<slug>-icons` (the kdeglobals `[Icons] Theme=` value, read by
apply from the bundle's `[kdeglobals][Icons]` group). `paths.py` gained one XDG root per new
namespace: `color_schemes()`, `wallpapers()`, `cursor_themes()` (XCursor themes go
to `~/.icons`, NOT `$XDG_DATA_HOME/icons` — libXcursor/the cursor KCM on
stock Kubuntu never scan the XDG dir; verified live 2026-08-31),
`desktop_themes()`, `look_and_feel()`, `plasmoids()`, `icon_themes()`
(`$XDG_DATA_HOME/icons` — this one IS scanned by KIconTheme), alongside the
existing `aurorae_themes()`/`kwin_decorations()`.

**`apply.py`'s global flow.** `apply_full` (the CLI default of `themey
apply`, and of `themey convert --apply`, which makes the same call right
after the install — the guards on `--apply` reject `--output` and
`--backend svg`/`both` BEFORE converting, and convert takes apply's six
furniture flags plus `--no-restart-shell` and `--widget-style`) is a superset
of the original deco-only `apply`: verify both the Look-and-Feel bundle and
the QML decoration package are installed, snapshot the pre-themey baseline
once (`kdeglobals [Themey] PrevLookAndFeelPackage` mirrors kdeglobals
`[KDE] LookAndFeelPackage`; kwinrc `ThemeyPrevDeco` packs
`library|theme|BorderSize`, both `@unset`-sentineled for an absent key and
written only the first time so a second `apply` never clobbers the real
baseline with an already-themey'd one; `kdeglobals [Themey] PrevColorScheme`
snapshots the user-layer `[General] ColorScheme` the same way when a themey
scheme is installed; `PrevIconTheme` the user-layer `[Icons] Theme` when the
bundle names an installed `themey_<slug>-icons` (written explicitly after the
colour scheme — chris's kdeglobals has `Theme=Fluency`, the same shadowing —
then `dbus-send --type=signal /KIconLoader org.kde.KIconLoader.iconChanged
int32:0`, failure = warning; revert mirrors the colours block);
`PrevWidgetStyle` the user-layer `[KDE] widgetStyle` when a Qt application
style is going to be written at all; `PrevPlasmaTheme`, `PrevPanelLengthModes` and
`PrevPanelFloating` follow the
same pattern for the Plasma Style and the per-panel `lengthMode`/`floating`
maps), run
`plasma-apply-lookandfeel -a
themey_<slug>` (never `--resetLayout`), then `plasma-apply-colorscheme
themey_<slug>` — REQUIRED, not belt-and-braces: verified live on Plasma
6.6.6 (2026-08-31) that `plasma-apply-lookandfeel -a` does NOT apply the
bundle's color scheme past an explicit user-layer `ColorScheme` (it updated
kcminputrc's cursor but left even `kdedefaults/kdeglobals` on the old
scheme) — then, when the bundle carries an `X-Themey-WidgetStyle` stamp
(`themey convert --widget-style windows|fusion|breeze`) or `apply
--widget-style` overrides it for the one run, the Qt APPLICATION style as
a third user-layer kdeglobals write (`[KDE] widgetStyle=`, same
kdedefaults-shadowing reason as the colours and icons) plus a `dbus-send
--type=signal /KGlobalSettings org.kde.KGlobalSettings.notifyChange
int32:2 int32:0` broadcast so running apps restyle without a relogin
(failure = warning); with no stamp AND no flag the application style is
left entirely alone — no baseline recorded, nothing written — and revert
restores or deletes the key the same way the colours block does — then, when the Plasma Style package is installed,
`_clear_style_cache` followed by `plasma-apply-desktoptheme themey_<slug>`
(explicit for the same user-layer-shadowing reason; the cache clear must
come first or plasmashell repaints from the stale Version-keyed kcache of a
previous conversion; when the effective plasmarc name — kdedefaults
cascade included — is ALREADY `themey_<slug>` the tool is a no-op and
plasmashell keeps the previous conversion's SVGs in memory, so the step
first bounces through Breeze's `default` style — verified live
2026-09-01, OldE's rejected wordmark cap survived re-convert + apply
until bounced) — re-assert the decoration keys via
the same `_write_deco` the deco-only path uses (required even though the
LnF apply already wrote deco defaults — those land in the
`~/.config/kdedefaults/` layer, and only an explicit user-layer write is
guaranteed to win), then `_set_panels_fit` (every panel's `lengthMode` to
`fit` AND `floating` off — E16's iconbox/dragbar are content-sized docked
strips: a full-width bar reads as Plasma and a floating one adds an 8 px
halo), then `_ensure_furniture` (E16's left-edge furniture:
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
aspect; since 2026-09-01 the pager panel hosts themey's OWN
`org.themey.pager` — a recorded panel still carrying the stock pager
reads `stale` from the existence check and is removed + recreated — and
the iconbox script writes `taskHoverEffect` from the Plasma Style's
`X-Themey-TasksHover`, which every later apply RE-writes into the live
panel (`FurnitureSpec.reassert` — the style changes under a panel that
outlives it, so the creation script cannot be its only writer; it is
themey's per-theme spec, unlike the widget config left to the user). A THIRD furniture panel, E16's dragbar
(`DragbarPanel`): full-width TOP panel, `scale_px(16, X-Themey-Scale)`
px thick floored at 24 (`dragbar_thickness_px`), `lengthMode=fill`,
`org.themey.deskbutton` next → panelspacer → systemtray → digitalclock →
deskbutton prev (E16's default ordering: RAISE/next at the start,
LOWER/prev at the end); created LAST, right after `_park_top_panels`,
which moves every pre-existing top panel to a nonexistent screen index
(`p.screen = screenCount` → `p.screen == -1`, config kept, never shown —
verified live 2026-09-01; fallback right edge + autohide) and records
`id=screen:location:hiding|…` once in `PrevTopPanels` (a later apply parks
and appends only unrecorded top panels; the dragbar's own marker id is
always excluded). Which of the three get built, and how big, is
`FurnitureOptions` (`DEFAULT_FURNITURE` is the module singleton every
default reads, because ruff's B008 forbids a call in an argument
default). The SIZES are E16 1.0.31's own: a 48 px pager CELL
(`_PAGER_CELL_PX`, `pager.c:788-796`) with the panel one aspect-true cell
thick — `pager_thickness_px` = `max(1, round(cell × screen_w/screen_h))`
over `_read_screen_aspect`'s live `screenGeometry(0)`, 85 px on 16:9,
falling back to 16:9 with a warning when the script fails or answers
garbage — and a 48 px iconbox (`_ICONBOX_HEIGHT`, E16's `iconsize`; the
panel thickness IS the task-icon size). Both are overridable
(`--pager-cell`/`--iconbox-size`, non-positive rejected as a usage error)
and both are re-asserted on every apply (`_furniture_reassert_script`),
so the 130/60 px panels earlier applies created shrink with no revert.
Both left-edge panels default to plasmashell's WindowsGoBelow — E16's
default maximize was `MAX_AVAILABLE` (`mod-misc.c:160`), which stepped
around the pager instead of shrinking every window for it. The SCRIPTING
engine has no string for that mode (every spelling reads back `'none'`
on 6.6.6, verified live 2026-09-01), so the creation/re-assert scripts
omit the `hiding` assignment entirely for such a panel and
`_write_furniture_visibility` writes `plasmashellrc [PlasmaViews][Panel
<id>] panelVisibility` through kwriteconfig6 instead
(`PanelView::VisibilityMode`: NormalPanel 0, AutoHide 1, DodgeWindows 2,
WindowsGoBelow 3 — 3 for pager/iconbox, 0 for the dragbar, which keeps
its strut), dead last of the panel section: it must follow every script
that assigns a panel's `hiding`, the `--no-dragbar` unparking included,
because plasmashell flushes a scripted `hiding` lazily and would rewrite
the file over it. The written value survives a plasmashell restart and
was measured in force AFTER one (KWin's MaximizeArea on that screen went
x=130 → x=60); whether it applies without one is untested, so an apply
that ends without a restart warns that the struts stand until it.
`--furniture-strut` puts both panels back to NormalPanel and the scripted
`hiding = 'none'`. `--no-pager`/`--no-iconbox`/`--no-dragbar` leave a
panel out AND remove an already-recorded live one with its marker
(`_remove_furniture`, the extracted revert-loop body — on the apply path
it warns and keeps the marker rather than failing the whole apply), and
the step that exists only for that panel is undone: the stacked desktop
grid for the pager (`_undo_desktop_grid_column`, restoring
`PrevDesktopRows` when a baseline exists), the top-panel parking for the
dragbar (`_undo_top_panel_parking`). `_furniture_specs()` with defaults
still returns all three, which is what revert enumerates. apply refuses to
run without the applet packages the ENABLED panels host (`org.themey.pager`
for the pager, `org.themey.deskbutton` for the dragbar)
under `paths.plasmoids()` and warns when their `X-Themey-Runtime` is
behind the code's. Just before the furniture, when the pager is on, `_set_desktop_grid_column` stacks the
desktops one per row (kwinrc `[Desktops] Rows=Number` AND the writable
`VirtualDesktopManager.rows` D-Bus property — KWin reads the config key
only at startup, verified live 2026-08-31; `PrevDesktopRows` baseline,
restored on revert). Then the
wallpaper fill-mode step, and one `qdbus`
reconfigure last. The panel steps come BEFORE the wallpaper one on
purpose: the wallpaper step is the likeliest to raise, and a failed apply
should still have delivered the panel feel.

`_set_wallpaper_fill(image, mode, solid)` runs with the bundle's default
wallpaper package's `X-Themey-FillMode` (legacy `tiled`/`scaled` read as
`tile`/`stretch`; unknown values log a warning and leave the wallpaper
alone) and dispatches two ways, because `plasma-apply-wallpaperimage -f`
accepts only the camelCase QML names
`stretch`/`preserveAspectFit`/`preserveAspectCrop`/`pad` on Plasma 6.6.6
(verified live 2026-08-31: every spelling of tile is "Invalid fill mode",
and Plasma's Image wallpaper plugin doesn't read fill-mode from the package
either). `stretch`/`fit`/`pad` go through the tool's `-f`
(`_WALLPAPER_FILL_MODE_TOKENS`; E16's SCALED is a stretch and Plasma's
default is a crop, so even the plain mode needs it); when the package also
carries `X-Themey-SolidColor` and the mode is `fit`/`pad`, a plasmashell
scripting call writes the Image wallpaper's `Color` key so the letterbox
shows E16's solid. The three tile modes set the image without `-f`, then
the same scripting shape writes `FillMode` with the QML `Image.fillMode`
int (`_WALLPAPER_FILL_MODE_INTS`: `tile`=3 Tile, `tile-v`=4
TileVertically, `tile-h`=5 TileHorizontally) on every desktop's Image
wallpaper config. The CONFIG lands (KCM shows the mode) but plasmashell
6.6.6 does NOT repaint fill-mode from ANY scripting write (verified live
2026-08-31 — FillMode alone, +reloadConfig, even an Image swap left the
render pixel-identical), so a tile-mode apply ends with
`systemctl --user restart plasma-plasmashell` (`_restart_plasmashell`,
dead last so it can't race any evaluateScript; failure = warning, never a
failed apply; opt-out `--no-restart-shell`). Since 2026-09-01 a Plasma
Style apply restarts the shell too: applets compute some KSvg metrics
ONCE at load (`KickoffSingleton.lineSvg.horLineHeight`,
`listItemMetrics` — `elementSize()` is a function, not a bound
property), so after `plasma-apply-desktoptheme` Kickoff kept drawing the
PREVIOUS theme's 6 px separator over StarEnli's 3 px art (verified live).
A deco/colour-only apply still never restarts. Whether the `-f` path and the
`Color` write repaint live without a restart is NOT yet verified.

`themey apply --revert` reads
the markers back, reapplies the recorded Look-and-Feel package (no
Breeze special-case — a real baseline is typically a third-party theme,
e.g. `com.github.vinceliuice.MacVentura-Dark`), restores the deco
triple, button layout and panel length/floating modes, removes the themey-created
pager/iconbox/dragbar panels (before the panel-mode restore, so that script iterates only
surviving panels), unparks the recorded top panels (`PrevTopPanels`:
screen/location/hiding back exactly; after the dragbar removal, before
the mode restores; keep-on-failure), then clears the markers it
actually restored; a
failure to reapply the recorded package does NOT abort the rest of the
restore, and `PrevLookAndFeelPackage` is deliberately kept in that one case
so a later `--revert` can retry just the theme restore (`PrevColorScheme`,
`PrevIconTheme`, `PrevWidgetStyle`
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

`waifu2x-ncnn-vulkan` (`--upscale waifu2x`) follows the same shape with one
extra check the models force. Upstream ships the binary and its `models-*`
dirs as FLAT SIBLINGS and the tool resolves its `-m models-cunet` default
against the **cwd**, so an install that copied only the executable onto PATH
is runnable and modelless — the state a fresh install usually lands in.
`waifu2x_available()` therefore tests for a usable model dir too
(`_is_model_dir`: any `*.param`), `waifu2x_unavailable_reason()` returns
which half is missing as a sentence so the note can name it, and
`run_waifu2x` always passes an explicit `-m`. Discovery is an ordered probe:
`$THEMEY_WAIFU2X_MODELS` (parent OR one model dir) → the binary's own
directory → `/usr/local/share/waifu2x-ncnn-vulkan` →
`/usr/share/waifu2x-ncnn-vulkan`. Output verification goes one step past
xcursorgen's: exit code, file exists, file non-empty, AND dims are exactly
`factor ×` the source — a silently 1x result would ship art whose dims no
longer match the BorderImage insets. `WAIFU2X_MODEL` (`models-cunet`) and
`WAIFU2X_NOISE` (0) are constants: E16 art is rendered chrome rather than the
anime cels waifu2x trained on, so `models-upconv_7_photo` is the obvious A/B,
and `-n -1` the one to try if a theme's intentional dither reads as noise.
Verified against the binary 2026-09-02: `-s` accepts 1/2/4/8/16/32 and
rejects 3 on all three shipped models; ~0.8 s per warm launch on an RTX 3070,
which is why `package.export_images` memoizes per SOURCE FILE (e13: 76
manifest entries → 26 launches; Aliens 60 → 16, 12.6 s end to end).
Device pick is `-g auto` (20/20 runs took the discrete GPU; warm llvmpipe was
only 2x slower, so auto is fine) with `$THEMEY_WAIFU2X_GPU` as the override.
`WAIFU2X_TIMEOUT_SECONDS` is 300 and is a HANG guard, not a performance
budget: the first run against a device compiles its shader pipelines — 36.2 s
cold vs 1.70 s warm on the same device, measured — and 120 s left barely 3x
headroom over that, which is the likeliest reading of the one timeout chris
hit 2026-09-02 that never reproduced warm. The timeout path attaches the
stderr captured before the kill, because waifu2x prints its device banner
immediately and without it a timeout says nothing about why.

**The fallback is ONE decision point**, in `pipeline.convert` right after
`build_theme` (where `theme.notes` exists): `upscale == "waifu2x"` and no
binary/models → `effective_upscale = "quality"` plus an `upscale:` note, and
`effective_upscale` is what BOTH `qmldeco.write` and `write_report` get, so
the report can never name a scaler that did not run. `upscale_part` stays
pure and raises `Waifu2xError` if called anyway — pipeline decides, upscale
executes. The svg guard rejects any non-nearest mode and now interpolates the
mode into its message instead of hardcoding "quality".

**Report prefixes.** `report.py` categorizes `theme.notes` by string
prefix into the report's Approximated section: `aurorae_rc:`, `bundle:`,
`colors:`, `composite:`, `cursors:`, `fonts:`, `icons:`,
`plasmastyle:`, `qmldeco:`,
`tooltips:`, `upscale:`, `wallpaper:` are surfaced
first (layout/subsystem decisions), ahead of the per-state E16-collapse
notes that have no prefix.

QML-backend contracts:

1. **resolver.js and resolver.py are the same algorithm** (E16
   `BorderWinpartCalc`: Q10 percents, inclusive bottom-right anchors,
   re-centering max clamps with E16's own `((x + ox) − max) >> 1` (`ox`
   inclusive — one px left of the naive form when `span − max` is even),
   min clamps only when max did not (`else if`), `__FLAG_TITLE`+`MAX_WIDTH
   0` text sizing with the min clamp AFTER the span clamp). All
   math runs in E16 REFERENCE px; ref→output conversion goes through the
   shared `scale_px(v, s) = floor(v*s + 0.5)` (half-up in BOTH languages —
   Python `round()` is banker's, `Math.round()` half-up) and the final
   multiply is EDGE-based (`x_out = scale_px(x)`, `w_out = scale_px(x+w) -
   x_out`) so adjacent parts stay seamless at fractional scales; identical
   to `v*scale` at integer scales. Scale may be fractional ([1,3], 2
   decimals) — **QML-backend-only**; svg/both hard-error. Change both
   resolvers together and bump `RUNTIME_VERSION` (currently 5);
   `tests/test_qmldeco_geometry.py` pins e13 ground truth (KILL
   40x38@(0,0), stack x=9, plaque = textwidth+25) at scale 2 and 1.5.
2. **theme.js is pure data** (`var theme = {...}` — no runtime I/O/XHR);
   image state fallbacks and origin-topology validation happen at generate
   time. Geometry fields are UNSCALED ref px; `borders`/`insets`/`pixelSize`
   are pre-scaled via `scale_px`, and exported art targets the same
   `scale_px` dims (`upscale_part`) so BorderImage insets always match the
   shipped PNGs. Insets are PER IMAGE SLOT (`slotInsets[slot]`, `insets` =
   the normal slot's) because E16's `__EDGE_SCALING` is per image state
   (`iclass.c` `ICLASS_LRTB` writes `is->border` on the state last opened;
   `IClassSpec.edge_by_state` / `edge_for(state)`, last-wins
   `edge_scaling` as the fallback for states without their own edge).
   Captions: `text.effect*` is `none|shadow|outline` from
   `__DRAWING_EFFECT` PER STATE (`tclass.c:327` stores it on the current
   TextState — `effectNormal/Active/Sticky/StickyActive`, and the same
   four for `color*`/`effectColor*`; `ThemeyPart.qml` picks by
   `clientActive` × `clientOnAllDesktops`, `TClassSpec.fg_for/effect_for`
   resolve through `TextclassPopulate`'s chain where sticky_active.normal
   → norm.normal), painted in the
   tclass state's `__BACKGROUND_COLOR` (`effectColorNormal`/`Active`;
   E16 `text.c` TsTextDraw uses `bg_col`, calloc'ed black by default —
   `__EFFECT_COLOR` is NOT an E16 keyword), and `ThemeyPart.qml` places
   the caption inside the part with E16's `((limit − textw) × just) >> 10`
   so 512 centers even on a fixed-width title bar; captions elide in the
   MIDDLE (E16 TextstateTextFit1). `text.orientation` is `__ORIENTATION`
   (definitions: RIGHT 0, DOWN 1 = +90°, UP 2 = −90°, LEFT 3 = 180°;
   undefined tokens such as `__UP` are atoi 0 and stay horizontal even in
   a `MAX_HEIGHT 0` plaque, as E16 draws them). `slotTile[slot]`
   carries the per-state `__FILLRULE` (`null|h|v|both`; BorderImage
   repeat modes) and `keepOnTop` mirrors `__KEEP_ON_TOP` (off parts get
   a negative z so they stack under every on-top part). Image slots
   mirror E16's FOUR ImageState arrays (norm/active/sticky/sticky_active
   × normal/hilited/clicked, `iclass.c` ImageclassGetImageState):
   `normal`/`normalActive`/`hover`/`hoverActive`/`pressed`/`pressedActive`
   plus the same six with a `Sticky` suffix, which `ThemeyPart.qml` picks
   when `client.onAllDesktops` (E16 passes `EoIsSticky(ewin)` for every
   part, `borders.c:179`; 122 corpus themes ship sticky art that differs).
   Fallback chains are `ImageclassPopulate` verbatim: hilited/clicked →
   that group's normal; active.normal, sticky.normal AND
   sticky_active.normal → norm.normal — an active window never borrows
   the inactive hover art (DeepBlue's title bar flickered to it). Keyword
   ids from `config/definitions`: `__NORMAL_ACTIVE_HILITED` ==
   `__HILITED_ACTIVE_STICKY` == 364 (sticky_active.hilited — NOT a
   hover-of-active alias), `__NORMAL_ACTIVE_CLICKED` ==
   `__CLICKED_ACTIVE_STICKY` == 363.
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
`themey render --target pager` screenshots themey's own pager applet against
the theme's Plasma Style (2×2 nested desktops, a kdialog client for a rect).
`themey render --target style` screenshots the Plasma Style's FrameSvg sets
(panel/popup/tooltip/tasks/pager) via a plasmoidviewer probe applet in the same
nested session — note the `widgets/tooltip` cell shows the QQC2 tooltip only;
task/pager hover tooltips paint from the `dialogs/background` cell — the verification vehicle for `generate/plasmastyle.py` work.
`scripts/render_review.py` is a fast SVG approximation and can disagree with
KWin; it knows nothing about the QML backend.

Corpus verification: `uv run python scripts/batch_survey.py --out DIR
[--compare PREV/summary.json]` converts every archive in
`~/Desktop/ethemes/e16/` (223) in-process with `output_dir` set — never
installing, one worker process per theme with a timeout, home dirs
checked untouched afterwards — and writes `summary.md`/`summary.json`:
crash classes, viewitem cap/visibility outliers, Plasma Style sources,
theme.js outliers, wallpaper/cursor presence, the top-40 note patterns
and a delta table against a previous run. Run it before and after any
analyze/generate change; ~17 s on 8 workers. `ConvertResult.notes` carries
the full `theme.notes` for it (report.txt truncates the per-state bucket).
`uv run python scripts/audit_viewitem.py --out DIR` is the narrower
companion for `widgets/viewitem` work: the three `_band_stats`
measurements per MENU_SEL state, the `_viewitem_caps` branch and the tile
decision under the pre-2026-09-01 classifier (a frozen copy, so it cannot
drift) against the current one with every flip flagged, plus the
Selection/View colours with contrast ratios and a `contact.png` of every
theme's hover and selected strips for the eyeball check (223 rows, held
under `MAX_SHEET_BYTES` = 1 MB by a scale ladder). ~90 s, nothing
installed, nothing written outside `--out`. `uv run python
scripts/reconvert_installed.py [--dry-run] [--only PKG_ID ...]`
(one or more full `themey_<slug>` ids, a bare `<slug>` also accepted)
refreshes the
locally INSTALLED `themey_*` reference packages: it maps each installed
package id back to its `.etheme` through `slug.plugin_id` on the archive
stem, re-runs `pipeline.convert` in-process with the current defaults
(never `apply`, never a preview), and prints a report.txt-derived
note-count delta per theme. Run it at the end of a pass that changed a
generator, so the packages chris eyeballs are not stale; an installed
package with no matching archive is listed, never deleted.

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.

