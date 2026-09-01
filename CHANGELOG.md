# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **E16 menu styles** — `menustyles.cfg` is parsed: `#include <definitions>`
  now resolves to a bundled copy of E16's macro file (function-like macros
  only), so the `NORMAL_/NEXTSTEP_MENU_STYLE_VERTICAL` blocks every corpus
  theme uses expand into `__MENU_STYLE` blocks (`analyze/menus.py`,
  `ir.MenuStyleSpec`). The Plasma popup background follows the DEFAULT
  style's `__BG_ICLASS` whatever its name, and a NeXTSTEP style
  (`__USE_ITEM_BACKGROUNDS __ON` — OldE, OPENSTEP, NewSTEP) repeats the
  `__ITEM_ICLASS` row art that E16 stacked per menu row instead of falling
  back to a flat DIALOG; the `colors` Window group samples the same source.
  11 corpus themes change popup source, all to what E16 drew.

### Fixed

- **Highlight strips no longer smear** — `widgets/viewitem` caps for a
  rectangular (opaque-cornered) MENU_SEL strip follow the declared
  `__EDGE_SCALING` instead of the pill radius pin (OldE's 3 px bevels were
  pinned at 7/7, leaving a 2-row middle that Kickoff stretched ten times
  taller), and a grain-textured middle repeats (`hint-tile-center`) rather
  than stretching across Plasma's taller rows; gradient middles such as
  Aliens' glow still stretch, because repeating them bands. 138 corpus
  themes move to declared caps, 35 repeat their middle.
- **Style re-apply reload** — `themey apply` bounces the Plasma Style
  through Breeze's `default` when the themey style is already current:
  `plasma-apply-desktoptheme` with the current name is a no-op, so a
  re-converted style (fresh package and cleared kcache) kept painting the
  previous conversion's SVGs from plasmashell's memory (OldE's rejected
  "Enlightenment" wordmark cap survived a re-convert + apply, live
  2026-09-01).
- **Plasma Style highlights** — Kickoff/list selection art (`MENU_SEL`) now
  clamps its FrameSvg caps to 12 ref px (101 corpus themes shipped caps up
  to 199 px, smearing whole menu backgrounds into a 30 px row), honors the
  declared edge for non-pill art, refuses fully transparent art so Breeze
  fills in (5 themes had no selection highlight at all), and closes an
  open-ended pill by mirroring its rimmed cap (Yellow's missing right
  border). Wordmark dragbar caps are allowed on the panel's length axis
  (67 more themes ship their real bar art). `widgets/button` prefers
  `DIALOG_WIDGET_BUTTON`, E16's real push button.
- **Decoration text** — captions are placed inside the part with E16's
  justification formula (centered titles on fixed-width bars, 135 themes),
  shadow/outline effects paint in the tclass state's `__BACKGROUND_COLOR`
  (E16's `bg_col`; `__EFFECT_COLOR` never existed) and `__EFFECT_OUTLINE`
  renders as an outline.
- **E16 grammar** — `__EDGE_SCALING` and `__FILLRULE` are per image state;
  the lexer reads whole `sscanf` words in any case (lowercase and
  punctuated iclass names, quote-glued words, `//` comments, `atoi`
  numerics) — WashedBlue, eLap, LiteGnome and the Base family regain
  their parts; `__KEEP_ON_TOP __OFF` parts stack under on-top parts;
  max-clamp recentering and min-clamp order match `borders.c` exactly.
- **Cursors** — E16 swaps fg/bg for every theme pointer; converted
  pointers were color-inverted before.
- **Wallpapers** — the full `__BACKGROUND_LAYER` tuple (macro and raw
  forms, `#include`-followed) maps to `stretch|tile|tile-h|tile-v|pad|fit`;
  `themey apply` dispatches each mode and writes the letterbox solid.
  Rebound, Fossils_of_the_Machines and BS-E gain their wallpapers.
- **apply** — the Plasma tools no longer inherit a snap-sandbox
  `XDG_DATA_HOME` (the VS Code terminal broke `plasma-apply-lookandfeel`).
- **Panels (live feedback, e13)** — plasmashell derives every panel's
  minimum thickness from the UNPREFIXED panel-background caps, so the
  shared set is now cap-free (strict guard, iconbox trough or tint) and
  wordmark drag-bar art ships only in the `north-`/`south-` sets, and only
  on bars at least 24 ref px thick (a 6 px strip stretched to a 60 px
  panel smeared its E). The left furniture panels prefer the iconbox
  trough over the vertical drag bar. `themey apply` re-asserts the
  furniture panels' thickness on every run and quits plasmashell
  gracefully before the tiled-wallpaper restart so scripted panel config
  is flushed.

### Added

- `scripts/batch_survey.py` — in-process corpus convert survey (223
  archives, ~17 s) with crash classes, outlier tables, note histograms and
  a delta against a previous run; `ConvertResult.notes` exposes the full
  fidelity notes for it.

## [0.1.0] - 2026-08-31

First release. Converts an Enlightenment DR16 `.etheme` archive into an
installable KDE Plasma 6 Global Theme.

### Added

- **E16 front end** — lexer, parser, and AST for the legacy config grammar
  (`__BORDER`, `__ICLASS`, `__TCLASS` blocks), fronted by a hardened archive
  extractor that validates every tar member and caps total size, per-file
  size, and entry count. See [SECURITY.md](SECURITY.md).
- **QML decoration backend (default)** — a KWin/Decoration KPackage that
  replays E16's part model: unclamped borders, text-sized title plaques,
  side-border button stacks, and the theme's own TTF fonts. Supports
  fractional `--scale` and an opt-in hqx quality-upscale path.
- **SVG decoration backend** (`--backend svg`) — the original Aurorae SVG
  theme (`decoration.svg`, `<name>rc`, per-button SVGs), kept as an escape
  hatch and clamped to KWin's Border-size brackets.
- **Color scheme** — median-cut sampled from the theme's own border art and
  written as a Breeze-shaped KColorScheme `.colors` file, WCAG-AA guarded.
- **Wallpapers** — one Plasma wallpaper package per E16 background image; the
  largest becomes the Global Theme default.
- **Cursors** — E16 `__CURSOR` XBMs converted to an XCursor pointer theme via
  a hand-rolled XBM parser and `xcursorgen`, with modern Plasma 6.6 shape
  names canonical and legacy X11 names as symlinks. Skips gracefully with a
  report note when `xcursorgen` is absent.
- **Plasma Style** — a `desktoptheme` package built from the theme's art
  (panel, dialogs, tooltip, button, viewitem, scrollbar, arrows, pager).
- **Look-and-Feel bundle** — everything above packaged as one Plasma Global
  Theme, with one conditional INI group per artifact the conversion actually
  produced.
- **`themey apply <name>`** — applies the full Global Theme to the live KWin
  session (or `--deco-only` for just the window decoration), snapshotting the
  pre-themey baseline on first run. **`themey apply --revert`** restores it.
- **`themey render`** — screenshots a converted theme inside a headless
  nested KWin session. This is the visual ground truth for the project.
- **Atomic, reversible install** — every artifact is staged and then
  `os.replace`d into place under `$XDG_DATA_HOME` (or `~/.icons` for cursor
  themes). No system paths, no root; a conversion is undone by deleting the
  directories the run prints.
- **Preview and report** — a self-contained HTML preview with an embedded
  mock-window PNG, plus a `report.txt` recording what was preserved,
  approximated, and skipped.

### Security

- Requires `pillow>=12.3` as a security floor. themey decodes untrusted
  third-party images by design, and 12.3.0 fixes 13 advisories (10 high) in
  paths it exercises — heap out-of-bounds writes in `Image.crop()` /
  `Image.paste()`, decompression-bomb bypasses in the `BdfFontFile` /
  `PcfFontFile` loaders, and an out-of-bounds read on the mmap path.

### Known limitations

- Batch conversion (`themey --all <dir>`) is not implemented.
- Converting a theme means handing its fonts and images to your compositor;
  see the residual-risk section of [SECURITY.md](SECURITY.md).

[Unreleased]: https://github.com/0xc0re/themey/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/0xc0re/themey/releases/tag/v0.1.0
