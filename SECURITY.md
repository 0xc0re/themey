# Security

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | ✅ |

## Reporting a vulnerability

Email **c0re@merle.io**. Please include the archive or input that triggers the
issue if you can share it.

GitHub's private vulnerability reporting is not available on private
repositories, and this repository is currently private, so it cannot be
enabled today. It will be turned on when the repository is made public; until
then, email is the only channel.

## Threat model

**themey's entire job is to process untrusted input.** That is not a
hypothetical: `.etheme` files are downloaded from the internet, and the README
(["Where to get themes"](README.md#where-to-get-themes)) actively tells people
where to download them from. Those archives are 25-year-old third-party
artwork, served off plain-HTTP directory listings, with no signatures, no
checksums, and no maintained authority behind them. Anyone who can serve or
tamper with one of those files controls the bytes themey parses.

So the design assumption throughout is: **the archive is hostile.**

### Extraction hardening

`src/themey/etheme/archive.py` never calls `tarfile.extractall`. Its module
docstring cites CVE-2007-4559 and CVE-2025-4330, and the reasoning is worth
restating: Python 3.12's `filter="data"` default closed the classic
`extractall` traversal hole, but it is a filter applied by the same library
that then performs the write, and CVE-2025-4330 is a case of that filtering
being incompletely applied — a link-extraction path that bypassed the filter.
Rather than depend on the extractor policing itself, themey validates every
member up front and writes the files itself.

Concretely, `_safe_extract_all` rejects an archive outright when any member is:

- a **path traversal** — a name containing `..`, or an **absolute path**
- a member whose resolved destination **escapes the extraction directory**
- a **symlink whose target escapes** the extraction directory
- a **device, character, or FIFO special file**
- a **hardlink** (it can race the extraction)

Symlinks that pass validation are never written as symlinks. They are resolved
in a second pass by copying the target's bytes, so the extracted tree contains
regular files only. (Look-and-Feel packages forbid symlinks anyway, and a
legitimate theme has little reason to contain one.)

Size and count caps, from `archive.py:18-22`:

| Constant | Value | Purpose |
|---|---|---|
| `MAX_TOTAL_BYTES` | 32 MB (`32 * 1024 * 1024`) | total extracted bytes — the real zip-bomb defense |
| `MAX_FILE_BYTES` | 8 MB (`8 * 1024 * 1024`) | per-file cap |
| `MAX_ENTRIES` | 4000 | bounds member iteration (legitimate themes reach four digits — Ganymede has 1051 entries) |

Every rejection raises `UnsafeArchiveError` before any bytes are yielded to the
rest of the pipeline. Extraction happens into a `tempfile.TemporaryDirectory`
that is removed on context exit.

**Test coverage.** Seven malicious-archive fixtures live in
`tests/fixtures/malicious/`, each asserted in
`tests/test_archive.py::test_malicious_archive_rejected`:

| Fixture | Covers |
|---|---|
| `path_traversal.tar.gz` | `..` in a member name |
| `absolute_path.tar.gz` | absolute member path |
| `symlink_escape.tar.gz` | symlink pointing outside the extract dir |
| `oversize_file.tar.gz` | per-file cap |
| `oversize_count.tar.gz` | entry-count cap |
| `device_file.tar.gz` | device/character/FIFO special file |
| `no_root_marker.tar.gz` | no `borders.cfg` / `init.cfg` — not a theme |

`test_over_cap_entry_count_rejected` builds an over-`MAX_ENTRIES` archive on
the fly (the committed `oversize_count` fixture predates a cap raise), and
`test_caps_are_correct_values` pins the three constants so they cannot drift
silently. `tests/test_pipeline_aliens_canary.py` additionally asserts that a
malicious archive run through the full pipeline writes **nothing** to disk.

### Blast radius

Even a successful attack against the converter is bounded by where themey is
allowed to write:

- Every install path is under `$XDG_DATA_HOME` (default `~/.local/share/…`)
  or `~/.icons` for XCursor themes. Roots come from `src/themey/paths.py`.
- No system paths. No `/usr`, no `/etc`, no root, and themey never asks for
  privilege escalation.
- Installs are **staged into a temporary directory and moved into place with
  `os.replace`** (`src/themey/install.py`), so a failed conversion cannot
  leave a half-written package behind.
- A conversion is fully reversible by deleting the named directories, which
  the run prints.
- There is **zero runtime dependency on E16** — no E16 code is executed, ever.
  themey only reads the config grammar.

### What themey does *not* protect you from

Stated plainly, because this is the real residual risk:

**A converted theme ships the source theme's assets, and your compositor then
loads them in its own process.** The generated KPackage contains the source
theme's TTF fonts and its PNG artwork. When you apply the theme, KWin — not
themey — parses those fonts and images, inside the compositor process.

themey does not sanitize, re-encode, or validate font files beyond copying
them, and it does not validate image files beyond whatever Pillow does when it
opens them. **Converting a hostile theme means handing untrusted font and
image files to your compositor.** If you do not trust the source of an
`.etheme`, do not apply the theme it produces.

Nothing in the extraction hardening above changes this. The hardening keeps a
malicious archive from writing outside the extract directory; it does not make
the artwork inside it safe to render.

**The same applies during conversion, where Pillow is the parser.** themey
decodes untrusted third-party PNGs by design, so Pillow's own image-parsing
CVEs are directly in scope rather than incidental. The minimum is therefore a
security floor, not a feature floor: `pillow>=12.3` in `pyproject.toml`,
because 12.3.0 fixes 13 advisories (10 high) that land in paths themey
actually exercises — heap out-of-bounds writes in `Image.crop()` and
`Image.paste()` (used for 9-patch slicing), decompression-bomb bypasses in the
`BdfFontFile`/`PcfFontFile` loaders, and an out-of-bounds read on the mmap
path. Keep Pillow current; Dependabot watches `uv.lock` for exactly this.

### On the other side of the ledger

Two things that are *not* attack surface, both verified in the source:

- **Generated `theme.js` is pure data.** The QML decoration backend emits
  `var theme = {...};` and nothing else — no runtime file I/O, no XHR, no
  JSON fetch. This is a stated contract in `generate/qmldeco/theme_js.py`
  (whose docstring notes Qt6 gates `XHR` file reads behind
  `QML_XHR_ALLOW_FILE_READ` in the first place), and image-state fallbacks and
  origin-topology validation are resolved at *generate* time, not at runtime.
- **No shell is ever invoked.** There is no `shell=True` anywhere in `src/` —
  no `shell=` argument at all, so every `subprocess` call uses the
  `shell=False` default with a list argv. External binaries are resolved with
  `shutil.which` before invocation (`external.py`'s `xcursorgen`,
  `apply.py`'s `_which` for `kwriteconfig6`/`kreadconfig6`/`qdbus6` and the
  `plasma-apply-*` tools). The one exception is the developer-only
  `themey render` harness (`render.py`), which pre-checks its tools with
  `shutil.which` and then invokes `dbus-run-session`/`kwin_wayland` by name
  via `PATH`; it still passes a list argv and no shell.

Theme names taken from the archive are normalized through `src/themey/slug.py`
before they become directory names, plugin IDs, or config values.

### Dependencies

The runtime dependency surface is deliberately small — Pillow and Typer — and
everything else is stdlib. Pillow is the one that matters here: it is the code
that actually parses attacker-supplied PNG, JPEG, and BMP data out of an
`.etheme`, so a Pillow decoder vulnerability is a themey vulnerability. **Keep
it current.**

Dependabot version updates and security alerts are enabled
(`.github/dependabot.yml`), and GitHub's dependency graph does parse this
project's `uv.lock`, so Python dependencies are covered by alerts and not only
by scheduled version bumps.
