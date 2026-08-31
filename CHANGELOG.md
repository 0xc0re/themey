# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
