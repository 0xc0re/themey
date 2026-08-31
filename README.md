# themey

Convert Enlightenment DR16 (E16) `.etheme` archives into installable KDE
Plasma 6 themes.

themey reads the legacy E16 config grammar (`__BORDER`, `__ICLASS`,
`__TCLASS` blocks) and emits a complete modern KDE theme — window
decoration, color scheme, wallpaper, Plasma Style, and XCursor pointer set
— bundled as a one-click Plasma Global Theme. Point it at a 2009-era E16
theme and within seconds your Plasma 6 desktop is visibly wearing it:
frame, colors, panel, wallpaper, and cursor together.

![The E16 theme "Aliens" as a Plasma 6 window decoration](docs/images/aliens-kwin-render.png)

*The E16 theme `Aliens`, converted and screenshotted by `themey render`
inside a real headless KWin session — that biomechanical frame is E16
border art drawing an actual Plasma 6 window.*

```
$ themey Aliens.etheme
Installed:       /home/you/.local/share/kwin/decorations/themey_Aliens
Installed (colors): /home/you/.local/share/color-schemes/themey_Aliens.colors
Installed (cursors): /home/you/.icons/themey_Aliens-cursors
Installed (plasma style): /home/you/.local/share/plasma/desktoptheme/themey_Aliens
Installed (bundle):  /home/you/.local/share/plasma/look-and-feel/themey_Aliens
Preview:   /home/you/.local/share/themey/previews/Aliens.html
Report:    /home/you/.local/share/themey/previews/Aliens.report.txt
Apply via System Settings - Window Decorations - Aliens, or: themey apply Aliens
Colors:    pick 'Aliens (themey)' under System Settings - Colors
Cursors:   pick 'Aliens (themey)' under System Settings - Cursors
Global theme: themey_Aliens — apply: themey apply Aliens
```

## Status

Working today:

- `.etheme` parsing (lexer, parser, AST) with hardened archive extraction
- **QML decoration backend (default)** — an E16-faithful KWin/Decoration
  KPackage: unclamped borders, text-sized title plaques, side-border button
  stacks, theme TTF fonts, fractional `--scale`, and an opt-in hqx
  quality-upscale path
- **SVG decoration backend** (`--backend svg`) — the original Aurorae SVG
  theme (`decoration.svg`, `<name>rc`, button SVGs); kept as an escape hatch,
  clamped to the KWin Border-size brackets
- Color scheme sampled from the theme's own border art, installed as a
  KColorScheme `.colors` file
- Wallpaper packages — one per E16 background image, largest becomes the
  Global Theme default
- XCursor pointer theme via `xcursorgen` (graceful skip when the tool is
  missing)
- Plasma Style (desktop theme) — panel, popup, tooltip and pager chrome
  sliced from the theme's own art, sparse by design (Plasma falls back to
  a re-tinted Breeze per missing element)
- The whole thing bundled as one Plasma Global Theme (Look-and-Feel package)
- Atomic install under `~/.local/share/...`, idempotent on re-run
- Self-contained HTML preview with an embedded mock-window PNG
- `report.txt` recording what was preserved, approximated, and skipped
- `themey apply <name>` — apply the full Global Theme (or `--deco-only` for
  just the window decoration) to the live KWin session, plus
  `themey apply --revert`
- `themey render` — screenshot a theme inside a headless nested KWin

Not built: batch conversion (`themey --all <dir>`).

## Requirements

- Linux with KDE Plasma 6 (developed against 6.6.4–6.6.6)
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Optional, for `themey apply`: `kwriteconfig6`/`kreadconfig6`, `qdbus6`,
  and — for the full Global Theme apply — `plasma-apply-lookandfeel`,
  `plasma-apply-colorscheme`, `plasma-apply-desktoptheme`, and
  `plasma-apply-wallpaperimage` (all ship with Plasma). The last three are
  only invoked when the conversion actually produced that artifact: the
  color scheme and Plasma Style are applied explicitly because a
  Look-and-Feel apply does not displace an explicit user-layer setting, and
  the wallpaper tool only runs for a theme whose default background was
  tiled in E16.
- Optional, for cursor conversion: `xcursorgen` (Debian/Ubuntu: `x11-apps`;
  Fedora: `xorg-x11-apps`). Without it, `themey convert` still runs — it
  just skips the pointer theme and notes why in `report.txt`.
- Optional, for `themey render`: `kwin_wayland`, `dbus-run-session`,
  `spectacle`, `kdialog`

## Install

```bash
git clone https://github.com/0xc0re/themey.git themey && cd themey
uv sync                 # dev environment
uv tool install .       # put `themey` on PATH
```

Or run it without installing: `uv run themey <theme.etheme>`.

## Where to get themes

themey needs a `.etheme` file — a gzipped tar of an E16 theme directory.
The corpus is still online, a couple of hundred themes deep, and mostly
from 2000–2009.

Start at **<https://themes.effx.us/packages/e16/>** — 223 ready-to-use
`.etheme` archives (17K–3.7M), one direct download each. This is the
library [enlightenment.org/e16](https://www.enlightenment.org/e16) itself
points at, and where this repo's test fixtures came from:

```bash
curl -O https://themes.effx.us/packages/e16/Aliens.etheme
themey Aliens.etheme
```

To pick by eye first, browse
**<https://ps.ucw.cz/e16/e16-themes-gallery/>** — a screenshot gallery of
the same corpus, alphabetical from `7teenE` to `Yellow` — then fetch the
archive by name from effx.us. (`scripts/survey_corpus.py` already uses it
as its reference thumbnail source.)

| Also worth knowing | What you get |
|--------------------|--------------|
| [enlightenment.org/e16](https://www.enlightenment.org/e16) | The official E16 project page — what E16 is, and the fact that it is still maintained (DR16 1.0.30, Aug 2024) |
| [sourceforge.net/projects/enlightenment/files/e16-themes/](https://sourceforge.net/projects/enlightenment/files/e16-themes/) | The official core theme package (1.0.3, Oct 2023). `.tar.gz` bundles of several themes each — **not** individual `.etheme` files, so unpack and repack per theme |
| [github.com/dharrop/themes](https://github.com/dharrop/themes) | 233 bleeding-edge themes, but as unpacked directories rather than archives — see the repack tip below |
| [github.com/burzumishi/e16-themes](https://github.com/burzumishi/e16-themes) | 223 `.etheme` files mirrored on GitHub — the same set as effx.us. Unofficial, no README or license; handy if you would rather `git clone` the lot than fetch one at a time |

**Repacking an unpacked tree.** themey only accepts gzipped-tar archives,
and dharrop's themes are laid out as `<Theme>/e16/borders.cfg`. The
extractor finds the config root at whatever depth it sits, so wrapping the
theme directory as-is is enough:

```bash
tar czf AE.etheme -C themes AE && themey AE.etheme
```

**A word of caution.** These are third-party archives off the open web,
unsigned and unchecksummed, from sites that mostly stopped being updated
fifteen years ago — untrusted input by any reasonable definition. themey's
extractor is hardened against the usual tar tricks (path traversal, symlink
escape, absolute paths, device files, size and entry-count caps), but read
[SECURITY.md](SECURITY.md) before pointing it at a theme you did not
download yourself.

## Usage

### Convert

```bash
themey Aliens.etheme                     # convert + install + open the preview
themey convert Aliens.etheme --scale 3   # same thing, explicit subcommand
themey Aliens.etheme --scale 1.5         # fractional scale (QML backend only)
themey Aliens.etheme --output /tmp/out   # write to a directory; install nothing
themey Aliens.etheme --no-open           # skip the browser
```

`themey FILE.etheme` is shorthand for `themey convert FILE.etheme`.

| Flag | Meaning |
|------|---------|
| `--scale N` | Border/image upscale factor in `[1, 3]`. Default `2`. Fractional values (e.g. `1.5`) are accepted only with the QML backend — the SVG backend requires an integer. |
| `--upscale MODE` | Part-art scaler: `nearest` (default, pixel-art sharp, NEAREST resampling) or `quality` (hqx smoothing, then a LANCZOS *downsample* to the fractional target). `quality` is QML-backend-only. |
| `--backend NAME` | Decoration backend: `qml` (default — the E16-faithful QML KPackage), `svg` (the legacy Aurorae SVG theme), or `both`. |
| `--shade-button ACTION` | QML-backend-only. KWin removed window shading in Plasma 6, so E16's shade button is dead weight; this remaps it instead. One of `maximize` (default), `keepAbove`, `keepBelow`, `menu`, `hide`, or `none` (today's inert disabled button, which still absorbs clicks). e13, for example, has no maximize button of its own, so the dead shade slot becomes the missing action. |
| `--output DIR` | Write the theme tree(s), color scheme, wallpaper packages, cursor theme, Plasma Style, bundle, report, and preview under `DIR` instead of installing. Nothing under `~/.local/share` is touched. |
| `--no-open` | Do not launch the HTML preview. The preview is also suppressed automatically over SSH and on headless machines. |
| `-v` / `-vv` / `-q` | `-v` and `-vv` both switch to DEBUG (no extra verbosity between them today); `-q` restricts to WARNING+. |

### Apply

```bash
themey apply Aliens                 # apply the FULL Global Theme (deco, colors, Plasma Style, wallpaper, cursors, panels)
themey apply Aliens --deco-only     # just the window decoration, kwinrc-only
themey apply Aliens --deco-only --backend svg --border-size Huge  # SVG-backend-only: BorderSize is theme-controlled on QML
themey apply --revert               # restore whatever was active before the last full `themey apply`
themey apply Breeze                 # legacy escape hatch: switch the decoration back to Breeze
```

`themey apply <name>` (no flags) applies the whole installed Look-and-Feel
bundle via `plasma-apply-lookandfeel`, then re-applies the color scheme and
Plasma Style explicitly (`plasma-apply-colorscheme` /
`plasma-apply-desktoptheme` — the Look-and-Feel apply lands in the
`~/.config/kdedefaults/` layer and will not displace an explicit user-layer
setting), re-asserts the decoration keys in the user-layer `kwinrc` for the
same reason, resizes your panels (below), and finally fixes up a tiled
default wallpaper if the theme's default background was tiled in E16.
`--deco-only` keeps the original behavior: it writes only
`kwinrc [org.kde.kdecoration2]` and asks KWin to reconfigure — nothing else
on the desktop changes.

**Panels get resized.** A full apply sets *every* plasmashell panel to
fit-content length (`lengthMode = fit`), because E16's iconbox and dragbar
are content-sized and a full-width bar reads as Plasma, not E16. This
visibly rearranges your desktop. The previous per-panel modes are recorded
once in `kdeglobals [Themey] PrevPanelLengthModes` and put back by
`themey apply --revert`.

The first time you run a full `themey apply`, it snapshots your current
global theme, decoration, color scheme (`[Themey] PrevColorScheme`), Plasma
Style, and panel lengths (an ordinary `kdeglobals`/`kwinrc`/`plasmarc` read,
not a guess) so `themey apply --revert` can put them back later — including a
baseline that is itself a third-party theme, not Breeze. Repeated
`themey apply` calls never overwrite that original snapshot with an
already-themey'd one. Revert restores each piece independently: if one of
them can't be reapplied (say the baseline global theme was uninstalled
since), the rest is still restored and that one marker is kept so a later
`--revert` can retry just the part that failed.

`themey apply Breeze` is the older, decoration-only revert path — it just
switches the window decoration back to Breeze and restores your previous
titlebar button layout; it doesn't touch colors, Plasma Style, wallpaper,
cursors, or panels.

Both Aurorae SVG plugins clamp a theme's left, right, and bottom borders to
the System Settings "Border size" bracket; `--deco-only --backend svg` reads
the installed `<name>rc` and picks the smallest bracket that fits unless
`--border-size` overrides it. The QML backend (the default) never clamps —
it draws its own unclamped borders and ignores `--border-size` entirely.

### Render

```bash
themey render Aliens.etheme -o /tmp/aliens.png
themey render Aliens --plugin qml               # the default backend's truth
themey render Aliens --maximized --plugin v2 --border-size Large
```

`render` launches a private `kwin_wayland --virtual` session with its own XDG
directories and D-Bus session, opens a client window inside it, and
screenshots the virtual framebuffer. It never touches the live desktop. The
argument is either a `.etheme` path (converted on the fly) or the name of an
installed theme. `--plugin` selects `legacy` (`org.kde.kwin.aurorae` SVG,
default), `v2` (`org.kde.kwin.aurorae.v2` SVG), or `qml` (the QML decoration
package backend).

### Shell helper

```bash
scripts/install_theme.sh Aliens.etheme --apply --render --scale 2
```

Convert and install in one step, optionally switching the live session
(`--apply`) and screenshotting the result (`--render`). It also works
around snap-launched shells that point `XDG_DATA_HOME` into a sandbox KWin
never reads.

## Global Theme outputs

A full `themey <theme>.etheme` conversion installs up to five artifacts,
plus the decoration, all named from the same slug via `slug.plugin_id`
(`themey_<slug>`, deliberately reused across namespaces) so `themey apply
<name>` can find every piece:

| Artifact | Install path | Id / name |
|----------|---------------|-----------|
| QML window decoration | `~/.local/share/kwin/decorations/themey_<slug>/` | KPlugin Id = `themey_<slug>`, also the `kwinrc theme=` value |
| Color scheme | `~/.local/share/color-schemes/themey_<slug>.colors` | `[General] ColorScheme=themey_<slug>` |
| Wallpaper package(s) | `~/.local/share/wallpapers/themey_<slug>_<image-stem>/` | one per convertible background image; the largest becomes the bundle's default |
| XCursor pointer theme | `~/.icons/themey_<slug>-cursors/` (not under `~/.local/share` — libXcursor/System Settings only scan `~/.icons` + `/usr/share/icons` on stock Kubuntu) | directory name doubles as `kcminputrc cursorTheme=` |
| Plasma Style (desktop theme) | `~/.local/share/plasma/desktoptheme/themey_<slug>/` | `[plasmarc][Theme] name=themey_<slug>` — panel, popup, tooltip and pager chrome; sparse by design, Plasma falls back to a re-tinted Breeze per missing element |
| Global Theme (Look-and-Feel) bundle | `~/.local/share/plasma/look-and-feel/themey_<slug>/` | KPlugin Id = `themey_<slug>` (same string as the deco, different namespace) — this is what `themey apply <name>` and System Settings → Appearance → Global Theme apply |

Any artifact a theme has nothing to offer for — no `__CURSOR` blocks, no
background images, `xcursorgen` missing — is simply skipped, with a note in
`report.txt`; the bundle omits the matching key rather than pointing at
nothing. The SVG backend (`--backend svg`) installs to
`~/.local/share/aurorae/themes/<Name>/` instead of the QML path, and still
gets the shared colors/wallpaper/cursor/Plasma-Style/bundle artifacts.

### Uninstall

Every path lives under `~/.local/share` (or `$XDG_DATA_HOME`), plus
`~/.icons` for the cursor theme, so a conversion is fully reversible —
delete the named directories/files:

```bash
rm -rf ~/.local/share/kwin/decorations/themey_Aliens \
       ~/.local/share/color-schemes/themey_Aliens.colors \
       ~/.local/share/wallpapers/themey_Aliens_* \
       ~/.icons/themey_Aliens-cursors \
       ~/.local/share/plasma/desktoptheme/themey_Aliens \
       ~/.local/share/plasma/look-and-feel/themey_Aliens \
       ~/.local/share/themey/previews/Aliens.{html,report.txt}
```

(Add `~/.local/share/aurorae/themes/Aliens` too if you converted with
`--backend svg`/`both`, and `~/.cache/plasma_theme_themey_Aliens*.kcache` if
you ever applied the theme — plasmashell's rendered-SVG cache.) A conversion
writes nowhere but those per-user directories, never needs root, and has no
runtime dependency on E16; only `themey apply` touches `~/.config`, and only
the `kwinrc`/`kdeglobals`/`plasmarc` keys `--revert` puts back.

## How it works

```
.etheme ──► ingest ──► analyze ──► generate ──► install ──► report + preview
```

| Stage | Module | Job |
|-------|--------|-----|
| ingest | `etheme/archive.py`, `etheme/lex.py`, `etheme/parse.py` | Validate and extract the tar, lex the E16 config grammar, parse it into an AST |
| analyze | `analyze/` | Resolve `__ICLASS` image paths and states, collapse `__TCLASS` colors, bin border parts into buttons and strips, sample the color scheme from the border art — producing the frozen `Theme` IR (`ir.py`) |
| generate | `generate/qmldeco/` (QML backend, default), `generate/` (SVG backend), `generate/colors.py`, `generate/wallpaper.py`, `generate/cursors.py`, `generate/plasmastyle.py`, `generate/lookandfeel.py`, `images/` | Emit the decoration, `.colors`, wallpaper packages, XCursor theme, Plasma Style, and the Global Theme bundle |
| install | `install.py` | Stage under `$XDG_DATA_HOME/themey/staging`, then `os.replace` into place — atomic, with the previous install kept aside until the swap succeeds |
| report | `report.py`, `preview.py` | Explain the conversion; render the mock window |

Two backends generate the window decoration. **QML is the default**: a
KWin/Decoration KPackage that replays E16's part model 1:1 — unclamped
borders, text-sized title plaques, side-border button stacks, the theme's
own TTF fonts — loaded by the v1 Aurorae plugin (`org.kde.kwin.aurorae`,
still shipped in Plasma 6.6 for QML packages). The SVG backend
(`--backend svg`) stays as an escape hatch: it matches Aurorae's FrameSvg by
element ID, is clamped by both Aurorae plugins to the System Settings
"Border size" bracket, and receives no further fidelity work.

`kwin.py` holds the KWin facts both `render` and `apply` need: plugin IDs
and KWin's per-`BorderSize` clamp brackets, taken from the Plasma 6.6.6
Aurorae sources.

## Fidelity

Where E16 maps cleanly onto Plasma 6, themey is faithful. Where it does
not, it approximates and says so. Every conversion writes a `report.txt`
with four sections — Preserved, Approximated, Skipped, Apply — covering the
decoration, color sampling, wallpaper, Plasma Style, and cursor conversion
together.
Known approximations include non-`DEFAULT` borders (skipped), E16 button
states beyond normal/hilited/clicked (collapsed), and semantic colors
(link/visited/error/warning/success), which stay Breeze stock rather than
being tinted to the theme.

## Development

```bash
uv run pytest              # 826 passed, 1 skipped
uv run ruff check .        # clean
uv run pyright src         # basic mode
```

Test fixtures live in `tests/fixtures/`: five real themes (`Aliens`, `e13`,
`LiteGnome`, `Mac3D`, `OPENSTEP`), a synthetic `tiny.etheme`, and seven
malicious archives covering path traversal, symlink escape, absolute paths,
device files, and the size and entry-count caps. The real themes are
third-party work — provenance and licensing are recorded in
[`tests/fixtures/ATTRIBUTION.md`](tests/fixtures/ATTRIBUTION.md).

`tests/test_svg_rc_invariant.py` and the phash snapshots in
`tests/snapshots/visual/` guard rendering. A phash diff means the pixels
moved — regenerate only when the change is intended and verified.

Two review scripts support the visual loop:

- `scripts/render_review.py` — fast mock of Aurorae's layout. An
  approximation; it knows nothing about the QML backend and can disagree
  with KWin on tiling, hint margins, and border clamping.
- `scripts/visual_review.py` — mock mode, or `--live` to swap the running
  session's decoration, screenshot, and revert.

`themey render` is the truth — `--plugin qml` for the default backend,
`legacy`/`v2` for the SVG backend. Use the scripts only when `kwin_wayland`
and `spectacle` are unavailable.

## Docs

- [CONTRIBUTING.md](CONTRIBUTING.md) — how to set up, test, and send changes
- [SECURITY.md](SECURITY.md) — the threat model for untrusted `.etheme`
  archives, and how to report a vulnerability
- [CHANGELOG.md](CHANGELOG.md) — what changed, release by release
- [tests/fixtures/ATTRIBUTION.md](tests/fixtures/ATTRIBUTION.md) —
  provenance of the bundled E16 themes

## License

MIT — see [LICENSE](LICENSE). The bundled E16 test fixtures are third-party
work under their own terms; see
[tests/fixtures/ATTRIBUTION.md](tests/fixtures/ATTRIBUTION.md).
