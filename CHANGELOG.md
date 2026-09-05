# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **A dock**, in the theme's own iconbox art. `themey dock` builds a
  floating, centred, bottom-edge panel running `org.themey.dock` — an
  icons-only task manager whose row zooms and rises under the pointer,
  showing windows from every virtual desktop where E16's iconbox shows
  only the minimized ones on the current desktop. It carries no art:
  every plate comes at run time from the active Plasma Style's
  `widgets/tasks`, so one dock survives converting and applying any
  number of themes and re-plates itself when you switch Plasma Style in
  System Settings.

  `themey dock` is its own command because the dock needs no converted
  theme. It touches that one panel and nothing else — no global theme, no
  decoration, no other furniture panel, and, unlike a full apply, it does
  not resize or un-float your existing panels. `themey dock --remove`
  takes it away, `--dock-size PX` sets its thickness, and `themey apply
  --revert` removes it with the rest of themey's furniture. It does need
  the applet package under
  `~/.local/share/plasma/plasmoids/org.themey.dock/`, which any `themey
  convert` installs.

- **`--dock` / `--no-dock` / `--dock-size PX`** on `themey apply` and on
  `themey <theme>.etheme --apply`, building the same panel as part of a
  full apply.

- **The `org.themey.dock` applet**, vendored under **GPL-2.0+** — a fork
  of a third-party macOS-style dock which is itself a fork of KDE's
  Icons-Only Task Manager, where themey's own two applets are MIT. The
  licence text, the provenance and the list of themey's changes ship
  inside the package (`COPYING` and `README.md`). `RUNTIME_VERSION` 1 →
  2; re-convert installed packages to pick it up.

- **`themey render --target dock`** — the dock applet screenshotted in a
  bottom-edge panel inside the nested headless KWin, with two client
  windows open so the row has real tasks to plate.

### Changed

- **The HTML preview no longer opens a browser on its own.** A convert
  prints the preview's path and stops; pass `--open` to have it launched.
  `--no-open` still parses and is now what the default already does.

- **E16's furniture panels are opt-in, and each flag is a tri-state.**
  Building the pager, iconbox, dragbar and dock rearranges your panels, your
  desktop grid and your top edge — the most invasive thing an apply does
  — so a plain `themey apply <name>` now themes the desktop and leaves
  all of that alone. Ask for a piece by name instead:

  ```sh
  themey apply Aliens --pager --iconbox --dragbar
  ```

  Each of `--pager`, `--iconbox` and `--dragbar` has three states. The
  positive flag builds the panel (or brings a live one back to this
  theme's spec). `--no-pager` &c. keep their old meaning: remove the
  panel a previous apply created and undo the change made only for it
  (the stacked desktop grid for the pager, the parking of your own top
  panels for the dragbar). Leaving both off leaves that panel alone — a
  panel you built earlier is still re-sized and re-configured for the
  theme being applied, but nothing is created, no desktop grid or top
  panel is touched, and a marker whose panel is gone is quietly dropped
  rather than rebuilt. `themey apply --revert` is unchanged and still
  removes everything themey recorded.

  `--dock`, `--no-dock` and `--dock-size` join them as a fourth
  tri-state, and now build the dock panel described above.

## [0.6.2] - 2026-09-03

### Changed

- **Maximized windows keep the full E16 frame (QML backend).** The
  decoration used to tell KWin that a maximized window has no left, right
  or bottom border and hid every part that fell below the title band, so
  the side rails, the bottom strip and side-stacked buttons (e13's
  ICONIFY/SHADE/STICK column) vanished on maximize while a corner button
  that fit the band's rows stayed — a half-drawn left column. E16 had no
  borderless-maximized state: it drew the same frame maximized or not and
  `MAX_AVAILABLE` sized the whole frame to the free area. themey now does
  the same — `maximizedBorders` equal the normal borders, nothing is
  maximize-conditional, and KWin insets the client by the full frame.
  `RUNTIME_VERSION` 5 → 6 (the part model lost `hideWhenMaximized`); the
  `qmldeco: button ... hidden while the window is maximized` note is gone
  with it. Re-convert installed packages to pick up the new runtime.

## [0.6.1] - 2026-09-02

### Fixed

- **`--upscale waifu2x` no longer fails a conversion when the Vulkan
  driver hiccups.** A launch killed by a *signal* is now relaunched (3
  attempts, 0.5 s apart); a non-zero exit and a timeout are not, since
  those are the tool rejecting its arguments and a wedged machine
  respectively.

  The crash is the driver's: measured over 270 otherwise identical
  launches on an RTX 3070, 2 of them had ncnn print `vkCreateDevice
  failed -3` (`VK_ERROR_INITIALIZATION_FAILED`), hand back a
  `VulkanDevice` it never created, and segfault on the dereference. At
  ~0.7% a launch that is harmless in isolation and fatal in aggregate —
  themey runs one launch per distinct source image, ~40 for Aliens across
  the decoration, the Plasma Style and the wallpapers, so about a quarter
  of `--upscale waifu2x` conversions died partway through. The wallpaper
  stage already degraded gracefully; the decoration and Plasma Style
  stages did not, so the whole run ended with `conversion failed:
  waifu2x-ncnn-vulkan exited -11`.

  It is a transient — the next launch of the same input succeeded every
  time — so three attempts take the per-image odds to ~3e-7. Verified
  after the fix: 4 real crashes across 6 Aliens conversions, all
  recovered, none failed. Pinning `$THEMEY_WAIFU2X_GPU` does not help
  (0/150 against 2/270 is not a difference at that rate).

### Documentation

- **The README now shows what `--upscale waifu2x` changes** instead of
  asserting it. Five before/after figures — `Graphiti`, `e13`, `OldE`,
  `Aliens` and `Obsidian` — each the same theme, window, `--scale 2` and
  crop rendered twice through `themey render --plugin qml`, magnified 3x
  with NEAREST so the page shows real pixels rather than the browser's
  smoothing of them. `scripts/make_upscale_figures.py` regenerates them.

  `Obsidian` is in the set as the counter-example, and is why `nearest`
  remains the default: a smooth vertical gradient has no detail below the
  pixel grid for the CNN to reconstruct, and the two runs are all but
  identical. The gain is real on drawn, organic and textured art and
  close to nil on flat gradient chrome.

- Corrects a stale scope claim in the same section, which read "Scope is
  the **window decoration only** — the Plasma Style, color scheme,
  wallpapers and cursors ... stay NEAREST regardless of this flag". That
  stopped being true in 0.6.0, when the Plasma Style started taking
  `theme.upscale` and sub-1920px wallpapers started going through the CNN
  at 2x. Cursors and the sampled colour scheme do not move; the text now
  says exactly that.

## [0.6.0] - 2026-09-02

### Added

- **`--upscale waifu2x`** — a third part-art scaler, running
  [waifu2x-ncnn-vulkan](https://github.com/nihui/waifu2x-ncnn-vulkan) on
  the window-decoration art. Local, free, deterministic and offline; the
  CNN reconstructs edges where hqx only smooths them. QML-backend-only,
  like `--upscale quality`.

  The binary needs its `models-*` directories, which most installs miss —
  upstream ships them as flat siblings of the executable and the tool
  resolves `-m` against the *current directory*, so copying just the
  binary onto `PATH` leaves it runnable and modelless. themey passes an
  explicit `-m`, probing `$THEMEY_WAIFU2X_MODELS`, the binary's own
  directory, then `/usr/local/share/` and `/usr/share/`. When either half
  is missing the conversion still succeeds: the art is upscaled with hqx
  and `report.txt` carries an `upscale:` note naming what was not found.

  `THEMEY_WAIFU2X_GPU=<index>` pins the Vulkan device when the tool's own
  auto-pick chooses badly. A timeout now quotes the device banner waifu2x
  printed before it was killed, and the limit is 300 s — a hang guard, not
  a performance budget, sized to clear the one-off shader-pipeline compile
  the first run against a device pays (36 s vs 1.7 s warm, measured).

- **`--upscale` now reaches the Plasma Style.** Panels, Kickoff/popup,
  tooltip, task and pager chrome are scaled with the same scaler as the
  window decoration; previously all three `plasmastyle.py` call sites took
  the default, so a themed desktop showed smoothed window frames beside a
  staircased panel. The mode rides on `ir.Theme.upscale`, beside `scale`.

  Changing the scaler cannot move geometry — classifiers run on source art
  and caps derive from source dims × scale — and a test pins that by
  comparing emitted SVGs with the rasters blanked. Style art repeats across
  prefixed sets, so `write()` memoizes the expensive modes: e13 goes 71 → 53
  waifu2x launches (57.9 → 39.8 s).
- **Wallpapers are upscaled too under `--upscale waifu2x`.** E16
  wallpapers are 512–1024 px and desktops are not, so Plasma has been
  upsampling them; doubling first means it downsamples instead. Verified
  against LANCZOS-straight-to-1920x1080 on five corpus wallpapers from
  512x400 to 1280x1024 — waifu2x won every one, most visibly on text and
  fine mechanical detail. Only below `WALLPAPER_UPSCALE_MAX_WIDTH`
  (1920), only under `waifu2x` (hqx on a photograph is the wrong tool),
  and a scaler failure ships the original with a `wallpaper:` note rather
  than failing the conversion.

  Upscaled wallpapers are written as **lossless PNG** whatever the source
  container was: once the byte-for-byte passthrough is forfeit the format
  is ours to pick, and a JPEG re-encode would stack a second generation of
  loss on a CNN's reconstruction of an already-lossy source. Measured on a
  doubled 800x600 corpus wallpaper, q92 costs 0.85 mean / 13 max RGB error
  to save 1.9 MB. The price is package size — Aliens goes ~3 MB at
  `nearest` to ~14 MB at `waifu2x`.

### Fixed

- `report.txt`'s Approximated section named the scaler that actually ran.
  It hardcoded "NEAREST" through every `--upscale quality` run.
- The SVG backend's rejection of a smoothing `--upscale` mode said
  "quality" whatever mode you passed.
- `upscale_part` dispatched by falling through to hqx for anything past
  the `nearest` early-returns, so a new mode would have silently rendered
  as hqx. Each mode now has an explicit branch and the fall-through raises.

### Changed

- `generate/qmldeco/package.export_images` scales each *distinct* source
  image once instead of once per manifest entry (e13: 26 rather than 76).
  Output is unchanged; the corpus survey is byte-identical.

## [0.5.0] - 2026-09-02

### Added

- **`themey <theme>.etheme --apply`** — convert, install and apply in one
  command. Rejects `--output` and `--backend svg`/`both` before the
  conversion runs, and takes the same furniture and shell-restart flags
  as `themey apply`.
- **`--widget-style windows|fusion|breeze`** on `convert` and `apply` —
  have the Global Theme bundle select a Qt *application* style
  (`kdeglobals widgetStyle`), with a record-once `PrevWidgetStyle`
  baseline that `--revert` puts back. Default: your application style is
  left alone.
- **Furniture opt-outs and sizes on `apply`** — `--no-pager`,
  `--no-iconbox`, `--no-dragbar` (each removes an already-created panel
  and undoes the desktop change made only for it), `--furniture-strut`,
  `--pager-cell PX` and `--iconbox-size PX`.
- **`scripts/reconvert_installed.py`** and **`scripts/audit_viewitem.py`**
  — maintainer scripts for refreshing every installed `themey_*` package
  and for calibrating the menu-highlight art decision across a corpus.

### Changed

- **E16-sized furniture panels that windows go below** — the pager panel
  is now one aspect-true 48 px E16 cell thick (85 px on a 16:9 screen,
  was a fixed 130 px) and the iconbox is E16's own 48 px (was 60), both
  re-asserted on every apply so existing panels shrink without a revert.
  Both also stop reserving screen space by default — E16's default
  maximize stepped around the pager rather than shrinking every window —
  so a maximized window keeps the whole screen. `--furniture-strut`
  restores the old behaviour.
- **`--iconbox-frames` now defaults to `off`** — E16's own frameless
  iconbox (`container.c` `draw_icon_base = 0`), bare icons on the trough.
  In that mode every conversion now ships `widgets/tasks.svg`, because a
  missing file brings Breeze's plates back rather than nothing.
- **Task-manager states are told apart** — nearly every E16 iconbox
  button declares only `__NORMAL`, which left the active, hovered,
  minimized and attention-seeking tasks identical. Missing states are now
  synthesized from the theme's own plate (hover and progress lightened,
  attention lighter still, minimized faded, the active task flipped so
  its bevel reads as sunken) and the active task wears a 2 px accent bar
  that follows the color scheme.
- **Popup background for item-background menu styles** — NeXTSTEP-style
  themes (`__USE_ITEM_BACKGROUNDS __ON`: OldE, OPENSTEP, NewSTEP, 8 corpus
  themes) now paint the popup/launcher centre flat in the item strip's
  dominant colour inside the strip's own bevel, instead of repeating the
  whole strip — on a 600 px Kickoff the repeated bevel rows read as a
  striped texture. E16 never drew a menu background for these styles, so
  the centre is themey's choice either way; the colour is the one the
  Window colour group already samples from the same art.

### Fixed (Plasma Style)

- **The highlighted menu item follows the art Plasma actually paints** —
  a smooth left-to-right gradient (ShinyMetal's metal sheen and 24 other
  themes) was classified as texture and repeated across a Kickoff row,
  which seamed and banded; the classifier now measures residual grain
  after removing both the row and column means, so gradients stretch and
  real grain still tiles. The selection color is sampled from the pressed
  art rather than the hover art, the label is contrast-guarded against
  the plate it actually sits on, the pressed-and-hovered state is no
  longer byte-identical to the pressed one, the reading-surface color
  follows the popup instead of the border tint (a near-black search field
  inside a light launcher), and a theme with no accent of its own gets
  focus rings in its own selection color instead of Breeze blue.

### Fixed (render)

- **`themey render` from a tty/ssh session** — the nested KWin refused
  Spectacle's screenshot ("The process is not authorized to take a
  screenshot", no PNG, rc 0) when the harness was launched outside a Plasma
  session; the private headless compositor now runs with
  `KWIN_SCREENSHOT_NO_PERMISSION_CHECKS=1`, KWin's own escape hatch.

### Fixed (fonts)

- **Font sizes and styles** — theme TTF sizes (`ariali/9`) are points at
  Imlib2's 96 dpi, so captions now render at size × 4/3 px (every TTF
  title was ~25% too small; 113 corpus themes). XLFD aliases keep their
  weight/slant (38 bold titles) and family as a source-less font entry, and
  their point field is treated as points; `xft:family-size:bold` patterns
  (3 themes) are parsed.

### Fixed (window buttons)

- **Themes that define their own action classes get their buttons back.**
  A border part's `__ACLASS` was matched against a fixed table of E16's
  stock action names, so a theme-private one was dropped — Ganymede binds
  its close button to `ACTION_GANYMEDE_KILL` and converted with no
  clickable buttons at all. The `__ACLASS` blocks in a theme's
  `actionclasses.cfg` / `buttons.cfg` / `slideouts.cfg` are now read (E16
  loads all three before `borders.cfg`) and the part is mapped by the
  window operation it actually fires. E16's own stock action classes are
  bundled and layered underneath, so a part naming one the theme never
  defines — `ACTION_WINDOW_SLIDEOUT` alone accounts for 100 of them —
  resolves too. Across the corpus this recovers 37 buttons in 31 themes.
  A slideout becomes the window menu and raise/lower become
  keep-above/keep-below; every such approximation is recorded in
  `report.txt`.
- **`BEGIN_*`/`END_*` blocks are terminated.** `END_SLIDEOUT`,
  `END_BORDER`, `END_IMAGE`, `END_MENU` and friends are object-like
  macros, and none of them expanded, so every such block was left open
  and swallowed whatever followed it. Object-like macros now expand
  except those named `__*` or `XC_*`, which are E16's own keyword ids,
  cursor constants and action names and must reach the parser verbatim.

### Added

- **XLFD family aliasing** — X11 core families that fontconfig has no
  alias for (`lucida`, 1360 corpus alias lines; `fixed`,
  `lucidatypewriter`, `clean`) no longer fall to the default sans: lucida
  renders with DejaVu Sans (Bitstream Vera, the same foundry lineage as
  Lucida), the monospace names with DejaVu Sans Mono, clean with the generic
  sans-serif; helvetica/times/courier keep going through fontconfig's own
  Nimbus/Liberation aliases. Each mapping is reported as a `fonts:` note.
- **E16 tooltips** — `tooltips.cfg` is parsed (E16's `ThemeConfigLoad`
  order; the `DEFINE_TOOLTIP*` macros expand through the bundled
  `config/definitions`) and the Plasma Style's `widgets/tooltip.svg` plus
  the Tooltip colour group now come from the DEFAULT `__TOOLTIP` block's
  own iclass and tclass, as `TooltipShow` resolves them, with the old
  `TT_MAIN`/`TT_TEXT` names as the fallback. 11 corpus themes that dress
  their tooltip with TT_MINI/BAR/COORDS/TT_CLOUD art shipped no tooltip
  before (223/223 do now) and 88 painted the text in TT_TEXT's colour
  instead of the TEXT1/TEXT2/COORDS/MENU_TEXT tclass E16 used. The first
  block that registers wins, as E16's loader skips a repeated name and
  creates nothing for an undefined iclass; an artless tooltip iclass and
  an undefined tclass fall back with a report note.
- **Text states, orientation, hovered menu text** — the title caption
  follows E16's four text-state groups (a sticky window's title uses the
  `__NORMAL_STICKY`/`__NORMAL_ACTIVE_STICKY` colour, font effect and effect
  colour; `sticky_active` falls back to `normal`, as `TextclassPopulate`
  does), `__DRAWING_EFFECT` is per state (43 corpus themes shadow only the
  focused title), `__ORIENTATION` is honoured (`__FONT_TO_UP` reads
  bottom-to-top, `__FONT_TO_DOWN` top-to-bottom; 72 themes), long
  captions elide in the middle like E16, the Plasma Selection text colour
  comes from the menu tclass's `__HILITED` state (61 themes; E16 never
  consults `__NORMAL_ACTIVE` for menus), and a vertical separator uses
  the `__CLICKED` art (107 themes) as `dialog.c` draws it.
- **Sticky-window art** — the QML decoration now carries E16's sticky and
  sticky-active image groups (`*Sticky` slots) and shows them on windows on
  all desktops, as E16 did for every part (122 corpus themes ship distinct
  sticky art). State fallbacks follow `ImageclassPopulate` verbatim, so an
  active window no longer borrows the inactive hover/click art when it has
  no active hover art (DeepBlue's title bar flickered). The keywords are
  mapped by E16's own ids: `__NORMAL_ACTIVE_HILITED` is sticky-active
  hover (id 364), not a hover-of-active alias. Runtime v5.
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

- **cpp conditionals** — the mini-preprocessor honours `#if`/`#ifdef`/
  `#ifndef`/`#elif`/`#else`/`#endif` like E16's epp (integer literals,
  `defined(X)`, macro names; E16's always-present symbols such as
  `ENLIGHTENMENT_VERSION` count as defined). eMac's six `#ifdef` colour
  variants no longer all apply with the last one winning, and `#if 0`
  blocks (ThiNicE, Spring, Summer) vanish.
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

[Unreleased]: https://github.com/0xc0re/themey/compare/v0.6.2...HEAD
[0.6.2]: https://github.com/0xc0re/themey/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/0xc0re/themey/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/0xc0re/themey/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/0xc0re/themey/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/0xc0re/themey/compare/v0.2.0...v0.4.0
[0.2.0]: https://github.com/0xc0re/themey/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/0xc0re/themey/releases/tag/v0.1.0
