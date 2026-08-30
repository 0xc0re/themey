# themey

Convert Enlightenment DR16 (E16) `.etheme` archives into KDE Plasma 6 window
decorations.

themey reads the legacy E16 config grammar (`__BORDER`, `__ICLASS`, `__TCLASS`
blocks), slices the theme's border art into 9-patch regions, and emits an
Aurorae decoration you can select in System Settings — so a 2009-era E16 theme
frames your Plasma 6 windows today.

```
themey Aliens.etheme
Installed: /home/you/.local/share/aurorae/themes/Aliens
Preview:   /home/you/.local/share/themey/previews/Aliens.html
Report:    /home/you/.local/share/themey/previews/Aliens.report.txt
Apply via System Settings - Window Decorations - Aliens, or: themey apply Aliens
```

## Status

Working today:

- `.etheme` parsing (lexer, parser, AST) with hardened archive extraction
- Aurorae window decoration: `decoration.svg`, `<name>rc`, `metadata.desktop`,
  `metadata.json`, per-button SVGs
- Atomic install under `~/.local/share/aurorae/themes/`, idempotent on re-run
- Self-contained HTML preview with an embedded mock-window PNG
- `report.txt` recording what was preserved, approximated, and skipped
- `themey apply` — switch the live KWin session to an installed theme
- `themey render` — screenshot a theme inside a headless nested KWin

Parsed into the IR but not yet emitted: cursors (`__CURSOR` blocks) and
wallpapers (`desktops.cfg` backgrounds). Color schemes, the Look-and-Feel
bundle, batch conversion, and `--uninstall` are not built yet. See
[Roadmap](#roadmap).

## Requirements

- Linux with KDE Plasma 6 (developed against 6.6)
- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Optional, for `themey apply`: `kwriteconfig6` and `qdbus6` (both ship with Plasma)
- Optional, for `themey render`: `kwin_wayland`, `dbus-run-session`, `spectacle`,
  `kdialog`

## Install

```bash
git clone <repo> themey && cd themey
uv sync                 # dev environment
uv tool install .       # put `themey` on PATH
```

Or run it without installing: `uv run themey <theme.etheme>`.

## Usage

### Convert

```bash
themey Aliens.etheme                    # convert + install + open the preview
themey convert Aliens.etheme --scale 3  # same thing, explicit subcommand
themey Aliens.etheme --output /tmp/out  # write to a directory; install nothing
themey Aliens.etheme --no-open          # skip the browser
```

`themey FILE.etheme` is shorthand for `themey convert FILE.etheme`.

| Flag | Meaning |
|------|---------|
| `--scale N` | Border/image upscale factor: 1, 2 (default), or 3. E16 art is small; 2× suits a modern display. Upscaling uses NEAREST, so pixel art stays crisp. |
| `--output DIR` | Write the theme tree, report, and preview under `DIR`. Nothing under `~/.local/share` is touched. |
| `--no-open` | Do not launch the HTML preview. The preview is also suppressed automatically over SSH and on headless machines. |
| `-v` / `-q` | DEBUG / WARNING-only logging. |

### Apply

```bash
themey apply Aliens               # point the live KWin at the theme
themey apply Aliens --border-size Huge
themey apply Aliens --legacy-plugin   # v1 QML plugin (reads the text-shadow keys)
themey apply Breeze               # revert
```

`apply` writes `kwinrc` `[org.kde.kdecoration2]` through `kwriteconfig6` and
asks KWin to reconfigure. System Settings → Window Decorations does the same
thing by hand.

Both Aurorae plugins clamp a theme's left, right, and bottom borders to the
System Settings "Border size" bracket, so a chunky E16 frame looks squashed at
`Normal`. `apply` reads the installed `<name>rc` and picks the smallest bracket
that fits; `--border-size` overrides it.

### Render

```bash
themey render Aliens.etheme -o /tmp/aliens.png
themey render Aliens --maximized --plugin v2 --border-size Large
```

`render` launches a private `kwin_wayland --virtual` session with its own XDG
directories and D-Bus session, opens a client window inside it, and screenshots
the virtual framebuffer. It never touches the live desktop. The argument is
either a `.etheme` path (converted on the fly) or the name of an installed
theme.

### Shell helper

```bash
scripts/install_theme.sh Aliens.etheme --apply --render --scale 2
```

Convert and install in one step, optionally switching the live session and
screenshotting the result. It also works around snap-launched shells that point
`XDG_DATA_HOME` into a sandbox KWin never reads.

## What gets written

```
~/.local/share/aurorae/themes/<Name>/
    decoration.svg        9-patch FrameSvg, border art base64-embedded
    <Name>rc              INI: [General] + [Layout]
    metadata.desktop      Aurorae plugin metadata
    metadata.json         KF6 metadata
    close.svg maximize.svg restore.svg minimize.svg menu.svg
    shade.svg alldesktops.svg keepabove.svg keepbelow.svg   (when the theme has them)
~/.local/share/themey/previews/
    <Name>.html           self-contained preview
    <Name>.report.txt     fidelity report
```

Every path lives under `~/.local/share`, so a conversion is fully reversible:

```bash
rm -rf ~/.local/share/aurorae/themes/Aliens \
       ~/.local/share/themey/previews/Aliens.{html,report.txt}
```

themey never writes outside `$XDG_DATA_HOME` (or `~/.local/share`), never needs
root, and has no runtime dependency on E16.

## How it works

```
.etheme ──► ingest ──► analyze ──► generate ──► install ──► report + preview
```

| Stage | Module | Job |
|-------|--------|-----|
| ingest | `etheme/archive.py`, `etheme/lex.py`, `etheme/parse.py` | Validate and extract the tar, lex the E16 config grammar, parse it into an AST |
| analyze | `analyze/` | Resolve `__ICLASS` image paths and states, collapse `__TCLASS` colors, bin border parts into buttons and strips, sample the palette — producing the frozen `Theme` IR (`ir.py`) |
| generate | `generate/`, `images/` | Composite each 9-patch region, upscale it, base64-embed it into `decoration.svg`, write `<name>rc` and the metadata and button SVGs |
| install | `install.py` | Stage to `$XDG_DATA_HOME/themey/staging`, then `os.replace` into place — atomic, with the previous install kept aside until the swap succeeds |
| report | `report.py`, `preview.py` | Explain the conversion; render the mock window |

Two facts drive most of the design:

- **Aurorae matches by element ID.** `decoration.svg` must carry all 36 IDs
  (`decoration-*`, `-inactive`, `-maximized`, `-maximized-inactive` × nine
  regions) plus `hint-*` margin rects. Missing maximized groups render a blank
  title bar on maximized windows.
- **`decoration.svg` and `<name>rc` must agree.** Strip thicknesses in the SVG
  and `Border*`/`TitleHeight` in the rc come from one function,
  `decoration_svg.strip_thicknesses()`, and `tests/test_svg_rc_invariant.py`
  enforces it.

`kwin.py` holds the KWin facts both `render` and `apply` need: plugin IDs and
KWin's per-`BorderSize` clamp brackets, taken from the Plasma 6.6.6 Aurorae
sources.

## Fidelity

Where E16 maps cleanly onto Aurorae, themey is faithful. Where it does not, it
approximates and says so. Every conversion writes a `report.txt` with three
sections — Preserved, Approximated, Skipped — plus an Apply section naming the
recommended Border size. Known approximations include non-`DEFAULT` borders
(skipped), E16 button states beyond normal/hilited/clicked (collapsed), and
button order, which Aurorae takes from `kwinrc` rather than from the theme.

## Development

```bash
uv run pytest              # 333 passed, 1 skipped, ~7s
uv run ruff check src/     # clean; scripts/ and tests/ still have findings
uv run pyright src         # basic mode
```

Test fixtures live in `tests/fixtures/`: five real themes (`Aliens`, `e13`,
`LiteGnome`, `Mac3D`, `OPENSTEP`), a synthetic `tiny.etheme`, and seven
malicious archives covering path traversal, symlink escape, absolute paths,
device files, and the size and entry-count caps.

`tests/test_visual_snapshot.py` guards rendering with perceptual hashes of the
composited decoration under `tests/snapshots/visual/`. Regenerate them
deliberately — a phash change means the pixels moved.

Two review scripts support the visual loop:

- `scripts/render_review.py` — fast mock of Aurorae's layout. An approximation;
  it can disagree with KWin on tiling, hint margins, and border clamping.
- `scripts/visual_review.py` — mock mode, or `--live` to swap the running
  session's decoration, screenshot, and revert.

`themey render` is the truth. Use the scripts only when `kwin_wayland` and
`spectacle` are unavailable.

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Parser, Aurorae generator, safe extract, install, preview | Complete |
| 2 | Color scheme, wallpaper, full report | Partial — parsing and Aurorae fidelity landed; `.colors` and wallpaper emission remain |
| 3 | XCursor pointer theme (`xcursorgen`) | Not started |
| 4 | Look-and-Feel bundle, batch mode, manifest, uninstall | Not started |

Planning documents live under `.planning/`: `PROJECT.md`, `ROADMAP.md`,
`REQUIREMENTS.md`, `STATE.md`, and per-phase plans and summaries.
