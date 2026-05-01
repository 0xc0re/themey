# Feature Research

**Domain:** Local single-user CLI for legacy theme format conversion (E16 `.etheme` → KDE Plasma 6 Look-and-Feel package)
**Researched:** 2026-05-01
**Confidence:** HIGH (driven by PROJECT.md scope + verified KDE CLI surface; assumptions about user workflow are explicit)

## Framing Note

This is a **single-user, run-it-on-my-laptop tool** with a closed corpus (~100 `.etheme` files in `/home/cstory/src/wilbs/ethemes/e16/`, all 2009-vintage from `themes.effx.us`). It is not a public product and has no second user. That changes the table-stakes / differentiator math significantly:

- "Discoverability" features (auto-update, telemetry, etc.) are zero-value.
- "Robustness against malicious input" is zero-value.
- "Daily-use ergonomics" (batch mode, idempotent re-runs, predictable output) move from "nice" to "table stakes" because chris will rerun this hundreds of times across the corpus.
- "Reversibility" is critical — chris will install bad themes, hate them, and want them gone. An uninstall path is not optional.

The bar is "is this tool actually pleasant to live with for a week of fiddling with E16 themes?", not "does it cover every edge case for every user?"

## Feature Landscape

### Table Stakes (Required for Tool to Be Useful)

Without these, themey is either broken or a one-off shell script that wouldn't be worth the build.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Parse `.etheme` tarball** (gzipped tar with E16 `__BLOCK __BGN ... __END` config grammar, `#include`) | The core conversion input. Without this, nothing works. | LARGE | Already PARSE-01/02. Re-implemented in Python from E16 source. |
| **Generate Aurorae window decoration** (`decoration.svg` w/ FrameSvg IDs, button SVGs, `<name>rc` INI, `metadata.desktop`) | Window borders are the most visually identifying feature of an E16 theme — without them you have no theme. | LARGE | Already AURORAE-01/02/03. The signature output. |
| **Generate KColorScheme `.colors` file** | Plasma applies color via this; without it the desktop colors don't match the theme. | MEDIUM | Already COLORS-01. INI format, dominant-color sampling via Pillow. |
| **Generate wallpaper package** (`~/.local/share/wallpapers/<name>/` with `metadata.json` + `contents/images/`) | E16 themes ship a background; not converting it loses half the visual identity. | SMALL | Already WALLPAPER-01. Mostly plumbing. |
| **Generate XCursor cursor theme** | E16 cursors are part of the theme's character; XBM → XCursor conversion is mechanical. | MEDIUM | Already CURSORS-01. Dependency on `xcursorgen` or Pillow + binary XCursor format. |
| **Bundle as Plasma Look-and-Feel package** (`~/.local/share/plasma/look-and-feel/<name>/`) | One-shot activation via `plasma-apply-lookandfeel <name>` is the entire reason for the tool. Without bundling, user has to apply 4 things separately. | MEDIUM | Already BUNDLE-01. Just a wrapping step but error-prone if metadata is wrong. |
| **Single-theme command form** `themey <theme.etheme>` | The default entry point. | SMALL | Already CLI-01. argparse. |
| **Batch command form** `themey --all <dir>` | With ~100 themes in the corpus, manually invoking 100 times is hostile. | SMALL | Already CLI-01. Iterate + per-theme isolation. |
| **Skip-on-error in batch** (one bad theme doesn't kill the run) | Some `.etheme` archives in the corpus are guaranteed to be malformed (16-year-old fan-made content). Stopping on the first error means batch mode is unusable. | SMALL | Wrap each theme in try/except, log failure, continue. Critical to batch UX. |
| **Per-theme `report.txt`** (preserved / approximated / skipped) | The fidelity story matters when chris is deciding "which 5 of these 100 themes are actually good?" Without it, he has to eyeball every install. | SMALL | Already REPORT-01. Just structured logging dumped to a file in the output dir. |
| **HTML preview** (mock window titlebar, color swatches, wallpaper thumbnail, activation command) | The "did this conversion work or did it produce garbage?" sanity check before activation. The only UI surface this tool has. | MEDIUM | Already PREVIEW-01. Static HTML, file:// open via `xdg-open`. |
| **Print activation command** after install | User needs to know how to actually apply the theme. Plain stdout, not a hidden `--help` artifact. | SMALL | Just `print(f"plasma-apply-lookandfeel {name}")` at end of run. |
| **Default `--scale=2` upscale** (override `--scale=1` / `--scale=3` accepted) | E16 titlebars at 13–30 px are unusable on chris's modern display. Tool is functionally broken without scaling. | SMALL | Already CLI-02. Numeric multiplier on border/title sizes and image assets. |
| **Idempotent re-runs** (running `themey aliens.etheme` twice doesn't error — second run replaces first) | Conversion is iterative: tweak parser, re-run, look at output. If second run errors with "already exists" the dev loop becomes painful. | SMALL | Default behavior should be overwrite-with-warning. |
| **Stable, predictable output paths** under `~/.local/share/...` | Per the PROJECT.md "fully reversible by deleting the named directories" guarantee. Non-negotiable. | SMALL | Already a constraint, just enforce it. |
| **Uninstall** (`themey --uninstall <name>` removes all 4 installed dirs) | With 100 themes about to flood `~/.local/share/`, manually deleting from 4 paths each is hostile. This is table stakes the moment batch mode exists. | SMALL | Read the install manifest (see Differentiators), `rmtree` the listed dirs. |
| **Verbosity flags** (`-v`, `-vv`, `-q`) | When something goes wrong on theme #47 of 100, you want to rerun that one theme with `-vv` and see what the parser saw. | SMALL | Standard Python `logging` levels mapped to flags. |

### Differentiators (Clear Daily-Use Value-Add)

These are the difference between "I built a converter" and "I actually use this every day."

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Install manifest** (`~/.local/share/themey/manifests/<name>.json` listing every file written) | Makes `--uninstall` reliable instead of guessing dir names. Makes `--list` possible. Makes "what did themey actually install on my machine?" answerable. | SMALL | One JSON write per converted theme; trivial. **Required dependency for clean uninstall.** Pattern is well-established (CMake `install_manifest.txt`, .NET `dotnet-tools.json`, dpkg). |
| **`themey --list`** — list all themes themey has installed | Once you have 30+ converted themes installed, you forget which were yours vs which came from the KDE Store. | SMALL | Reads the manifest dir. |
| **`themey --inspect <theme.etheme>`** — dry-run, parse + summarize, write nothing | The "does this `.etheme` even parse?" pre-flight check. Useful when investigating malformed corpus entries before doing a full conversion run. | SMALL | Reuse parser + report generator, skip writers. Industry-standard `--dry-run` pattern. |
| **`themey --verify <name>`** — re-validate an installed theme against current themey output | After bumping themey, "are my installed themes still consistent with what the tool would produce now?" Useful during development. | MEDIUM | Re-converts to a temp dir, diffs against installed. |
| **Conflict handling** (`--force` overwrites, default warns + skips, `--force --backup` saves old to `<name>.bak`) | Idempotent re-runs are table stakes; explicit conflict policy is the differentiator over a script that just clobbers blindly. | SMALL | Three-state flag: warn / overwrite / overwrite-with-backup. |
| **Auto-detect source themes directory** (search `/home/cstory/src/wilbs/ethemes/e16/`, `~/Downloads/`, `/usr/share/e16/themes/`) | Removes the need to type a long path for the common case. `themey --all` with no arg should "just work." | SMALL | Hardcode candidate paths, first match wins. Cheap quality-of-life. |
| **Configuration file** (`~/.config/themey/config.toml` for default `--scale`, source dirs, output dirs, conflict policy) | Daily-use defaults shouldn't require typing flags every time. `--scale=2` is "the right default for this user, this monitor, this corpus." | SMALL | Python 3.11+ has `tomllib` in stdlib — zero new deps. Layer: defaults < config file < env vars < CLI flags. |
| **Progress UI for batch** (rich Progress with theme name + count, `--no-progress` for plain output) | Watching `themey --all ~/themes/` chew through 100 themes silently is unpleasant. Visual progress turns 60 seconds of "is it hung?" into "ah, it's on theme 47/100." | SMALL | Add `rich` to STACK; auto-disable when not a TTY (so `themey --all > log.txt` stays clean). |
| **Logging to file** (`--log <path>` or auto-log to `~/.cache/themey/run-YYYYMMDD-HHMMSS.log`) | Batch run of 100 themes generates more output than fits in scrollback. Log file is the only way to investigate "wait, what happened to theme #62?" after the fact. | SMALL | Standard Python `logging.FileHandler`. |
| **HTML preview: side-by-side before/after** (extracted E16 source images on left, generated Plasma SVG render on right) | The fidelity assessment becomes 10x faster when you can directly compare. This is the single most useful preview feature for QA-ing the conversion. | MEDIUM | Render both into the HTML page; layout via flexbox. Doesn't need interactivity. |
| **HTML preview: fake-window mockup** (compose decoration.svg as it'd appear around a Plasma window with title text + buttons) | The mock window in real proportions is more honest than just "look at the SVG." Tells you "will this actually look OK with a 25px titlebar?" | MEDIUM | Reuses the SVG that's already being generated; just embed in an HTML frame with sample title + sample window contents. |
| **Auto-open System Settings → Window Decorations after install** (opt-in via `--apply` flag) | When experimenting, the "convert → see it live on my desktop" loop should be one command. Default-off (matches PROJECT.md "no auto-switch" decision); opt-in flag is the safe middle. | SMALL | `subprocess.run(["plasma-apply-lookandfeel", name])` when `--apply` is passed. |
| **`themey --all --apply <name>`** — convert all + apply one specific name | Dev loop: "rebuild the whole catalog, then immediately switch to my favorite to inspect." | SMALL | Composition of two existing flags. |
| **JSON output mode** (`--json`) for machine-readable conversion results | Future scripting hook; chris already runs everything in scripts, having structured output instead of grep-the-log is cleaner. | SMALL | Optional alternate report format. |
| **Color-scheme variants per theme** (auto-derive `<name>` and `<name>-dark` from background luminance) | Some E16 themes have light titlebars + dark backgrounds (or vice versa). Letting the user toggle between titlebar-derived vs background-derived palettes is a fidelity win. | MEDIUM | Run color sampler twice with different source images, emit two `.colors` files. |
| **Manifest-aware `--prune`** (find install paths under `~/.local/share/...` that aren't tracked in any manifest, warn) | Useful when chris has been hand-editing or when previous themey versions left orphans. | SMALL | Compare filesystem vs manifests. |

### Anti-Features (Deliberately NOT Building)

These would seem reasonable additions but actively harm the tool given the actual user/use-case.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **GUI app (Qt/GTK)** | "It's a theme tool, themes have visuals, surely it should have a GUI." | Build complexity 10x. The user is a CLI-native dev with one workflow. HTML preview already covers all the visual feedback need. | HTML preview file:// page; the only UI. |
| **Web service / cloud uploader / "share theme" button** | Modern tools have "share" everywhere. | This is a single-user local tool. Zero second users. Server cost, attack surface, account systems — all pure overhead. | None. The themes live in `~/.local/share/`; that's it. |
| **Plasma Style (widget layer) generation** | "Aurorae handles borders; what about the panel/clock/popups?" | Already an Out-of-Scope decision in PROJECT.md. E16 themes don't ship the SVG element IDs Plasma's widget layer expects (clock face, slider rails); output would be 80% fabricated and look worse than Breeze. | Use Plasma's built-in Breeze for widgets; only convert what E16 actually supplies. |
| **QStyle (Qt widget style) plugin** | "Make Qt apps look E16 too." | C++ project, separate build system, separate install path, fundamentally different problem. Already Out of Scope per PROJECT.md. | Breeze-style Qt widgets; live with the mismatch. |
| **Theme editor / live tweak GUI** | "If conversion is approximate, let user tweak the output." | Mission creep. themey is a converter, not a theme authoring tool. KDE has built-in editors (System Settings, Aurorae editor). | Re-edit the source `.etheme` if needed; or hand-edit the generated SVG; or use KDE's editors on the installed output. |
| **E17 / EFL `.edj` theme support** | "It's still 'Enlightenment'." | Different format (binary EDC), different rendering model, different data. Whole second parser, no shared code with the E16 path. Already Out of Scope. | Stay focused on DR16. |
| **Reverse direction (Plasma → E16)** | Symmetry. | Solving a problem nobody has. No one wants to run Plasma themes in E16. | No. |
| **Telemetry / usage analytics / auto-update** | "Modern tooling has this." | Single-user local script. There is no "fleet" to monitor. Dependency on a phone-home endpoint is pure liability. | `git pull` + reinstall when chris wants new behavior. |
| **Built-in theme browser / KDE Store integration** | "Discover and install themes through themey." | themey converts a closed corpus the user already has on disk; it is not a theme manager. KDE already has the Store integration via `kpackagetool6` and System Settings. | Leave theme discovery to KDE. |
| **Daemon / background watcher** ("auto-convert when new `.etheme` lands in folder") | Looks slick. | Process-management complexity, systemd unit, log rotation, restart-on-crash — all for a workflow chris will run by hand 5 times total. | Just rerun the CLI. |
| **Network downloads** ("fetch missing fonts / icons from upstream") | "Some E16 themes reference fonts not on the system." | Network dependency, license unclear, slow, brittle. | Substitute with a Plasma default font; log the substitution to `report.txt`. |
| **Sandbox / containerization** | "Conversion handles untrusted archives, sandbox it." | The corpus is 100 trusted files chris already has. Not a public service. Not worth the complexity. | Don't run on untrusted `.etheme` files. (Document this.) |
| **Plugin system / extension API** | "Make it extensible for future formats." | Premature abstraction. There's exactly one format (E16) and one user. | If a second format ever matters, refactor then. YAGNI. |
| **Convert E16 sounds, tooltips, focuslist, dock, iconbox, pager** | "Fidelity." | Already Out of Scope per PROJECT.md. No clean Plasma 6 mapping; output would be invented. | Skip; log to `report.txt` as "not converted, no Plasma equivalent." |

## Feature Dependencies

```
[Single-theme convert] (CLI-01)
    ├─requires─> [Parser] (PARSE-01/02)
    ├─requires─> [Aurorae generator] (AURORAE-01/02/03)
    ├─requires─> [Color scheme generator] (COLORS-01)
    ├─requires─> [Wallpaper generator] (WALLPAPER-01)
    ├─requires─> [Cursor generator] (CURSORS-01)
    ├─requires─> [Look-and-Feel bundler] (BUNDLE-01)
    ├─requires─> [Per-theme isolation] (each theme writes to its own subdir, errors don't leak)
    └─enables──> [Report] (REPORT-01)
                     └─enables──> [HTML preview] (PREVIEW-01)
                                       └─enhanced-by─> [Side-by-side before/after]
                                       └─enhanced-by─> [Fake-window mockup]

[Batch convert] (--all)
    ├─requires─> [Single-theme convert]
    ├─requires─> [Per-theme isolation] (one bad theme doesn't kill the run)
    ├─requires─> [Skip-on-error] (table stakes; without it batch is useless)
    ├─enhanced-by─> [Progress UI]
    └─enhanced-by─> [Source dir auto-detect]

[Uninstall] (--uninstall <name>)
    └─requires─> [Install manifest] (per-theme JSON listing all written files)

[--list]
    └─requires─> [Install manifest]

[--verify]
    ├─requires─> [Install manifest]
    └─requires─> [Single-theme convert] (re-run into temp dir + diff)

[--inspect / dry-run]
    ├─requires─> [Parser]
    └─requires─> [Report] (stripped of file-write side effects)

[Conflict handling --force / --force --backup]
    └─requires─> [Install manifest] (to know what to back up)

[Configuration file]
    └─enhances──> [All CLI flags] (provides defaults)

[--apply flag (auto-launch)]
    ├─requires─> [BUNDLE-01]
    └─requires─> [plasma-apply-lookandfeel installed on system] (verified per PROJECT.md)

[JSON output --json]
    └─enhances──> [Report]

[Color-scheme variants (light + dark)]
    └─enhances──> [COLORS-01]
```

### Dependency Notes

- **Batch mode requires per-theme isolation.** Each theme conversion must run in its own try/except, write to its own dirs, fail without leaking state. Without this, batch is one bad theme away from a half-installed mess.
- **Uninstall requires an install manifest.** Without a record of "themey installed these exact files," uninstall has to guess (`rm -rf ~/.local/share/aurorae/themes/<name>`) and may miss orphans or — worse — delete files themey didn't install. The manifest is small (one JSON per theme) and unblocks `--list`, `--verify`, and `--prune` too. **This is the single highest-leverage non-table-stakes feature.**
- **`--list`, `--verify`, `--prune` all share the manifest infrastructure.** Build the manifest once, get four features.
- **HTML preview is fed by the report.** The report is the structured data; HTML is one rendering of it. JSON output is another. Build the report data model first; renderers are thin.
- **Idempotent re-runs require conflict handling.** "Default = warn, --force = overwrite, --force --backup = backup-then-overwrite" is the right tri-state and works whether or not a manifest exists, but works *cleanly* with a manifest.
- **`--inspect` (dry-run) reuses everything except writers.** Architectural implication: separate "decide what to write" from "write it" so dry-run is a free side effect of clean separation, not a parallel code path.
- **Configuration file enhances all flags but blocks nothing.** Build last, layer it under defaults.

## MVP Definition

### Launch With (v1) — Required for Daily Use

These are the features without which themey is either broken or hostile-to-use:

- [ ] **Parser** (PARSE-01/02) — without this, no conversion
- [ ] **Aurorae generator** (AURORAE-01/02/03) — the headline output
- [ ] **Color scheme generator** (COLORS-01)
- [ ] **Wallpaper generator** (WALLPAPER-01)
- [ ] **Cursor generator** (CURSORS-01)
- [ ] **Look-and-Feel bundle** (BUNDLE-01) — one-shot activation
- [ ] **Single-theme CLI** (`themey <theme.etheme>`) (CLI-01)
- [ ] **Batch CLI** (`themey --all <dir>`) (CLI-01) with **skip-on-error** — required because corpus is 100 themes
- [ ] **Per-theme `report.txt`** (REPORT-01) — fidelity story for each conversion
- [ ] **HTML preview** (PREVIEW-01)
- [ ] **Print activation command at end of run**
- [ ] **`--scale` flag, default 2** (CLI-02)
- [ ] **Idempotent re-runs** (overwrite-with-warning by default)
- [ ] **Stable output paths** under `~/.local/share/...`
- [ ] **Verbosity flags** (`-v`, `-vv`, `-q`)
- [ ] **Install manifest** (per-theme JSON; tiny, unblocks v1.x features)
- [ ] **`--uninstall <name>`** — required the moment batch mode exists, because chris will install 100 themes and want to remove most of them

### Add After Validation (v1.x) — Triggered by Daily-Use Pain

Build these once v1 is in actual use and chris hits the friction:

- [ ] **`--list`** — when "which themes did I install?" becomes annoying (probably immediately after first batch run)
- [ ] **Progress UI** (`rich`) — when watching silent batch becomes annoying (immediately)
- [ ] **Source-dir auto-detect** — when typing the long path 5 times gets old
- [ ] **Conflict handling** (`--force`, `--force --backup`) — when iterating on the parser and overwriting installed themes
- [ ] **`--inspect` (dry-run)** — when investigating malformed corpus entries
- [ ] **HTML preview side-by-side before/after** — when the basic preview isn't enough to judge fidelity
- [ ] **Logging to file** (`--log` or auto `~/.cache/themey/`) — when batch output exceeds scrollback
- [ ] **Configuration file** (`~/.config/themey/config.toml`) — when CLI flags are repetitive
- [ ] **`--apply` flag** (auto-activate post-install) — when the convert/apply loop becomes the dev cycle

### Future Consideration (v2+) — Defer Unless Pain Materializes

Don't build until there's clear use-case:

- [ ] **HTML preview fake-window mockup** — bigger, less obvious value than side-by-side
- [ ] **`--verify`** — only matters if themey ships breaking changes; for a single-user tool, just reconvert
- [ ] **JSON output `--json`** — only when scripting hooks are actually needed
- [ ] **Color-scheme variants (light + dark)** — only if single-variant turns out wrong for many corpus themes
- [ ] **`--prune`** (orphan detection) — only when orphans actually accumulate
- [ ] **`themey --all --apply <name>`** — composable from existing flags; build only if needed

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Parser | HIGH | HIGH | P1 |
| Aurorae generator | HIGH | HIGH | P1 |
| Color scheme generator | HIGH | MEDIUM | P1 |
| Wallpaper generator | HIGH | LOW | P1 |
| Cursor generator | MEDIUM | MEDIUM | P1 |
| Look-and-Feel bundler | HIGH | MEDIUM | P1 |
| Single-theme CLI | HIGH | LOW | P1 |
| Batch CLI w/ skip-on-error | HIGH | LOW | P1 |
| Per-theme report.txt | HIGH | LOW | P1 |
| HTML preview (basic) | HIGH | MEDIUM | P1 |
| Print activation command | HIGH | LOW | P1 |
| --scale flag | HIGH | LOW | P1 |
| Idempotent re-runs | HIGH | LOW | P1 |
| Verbosity flags | MEDIUM | LOW | P1 |
| Install manifest | HIGH | LOW | P1 (unblocks uninstall) |
| --uninstall | HIGH | LOW | P1 |
| --list | MEDIUM | LOW | P2 |
| Progress UI (rich) | MEDIUM | LOW | P2 |
| Source-dir auto-detect | MEDIUM | LOW | P2 |
| Conflict handling | MEDIUM | LOW | P2 |
| --inspect / dry-run | MEDIUM | LOW | P2 |
| HTML side-by-side preview | MEDIUM | MEDIUM | P2 |
| Logging to file | MEDIUM | LOW | P2 |
| Config file (TOML) | MEDIUM | LOW | P2 |
| --apply flag | MEDIUM | LOW | P2 |
| HTML fake-window mockup | LOW | MEDIUM | P3 |
| --verify | LOW | MEDIUM | P3 |
| JSON output | LOW | LOW | P3 |
| Color-scheme variants | LOW | MEDIUM | P3 |
| --prune | LOW | LOW | P3 |
| Composed --all --apply | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for v1 — tool is broken or hostile without it
- P2: Build during early daily-use phase as friction surfaces
- P3: Defer until clear pain or user request materializes

## Comparable Tool Analysis

themey doesn't have direct competitors (no other E16→Plasma converter exists), but adjacent tooling informs feature expectations.

| Feature | `lookandfeeltool` / `plasma-apply-lookandfeel` | `kpackagetool6` (KDE official) | `plasma-theme-switcher` (third-party) | themey approach |
|---------|------------------------------------------------|--------------------------------|---------------------------------------|-----------------|
| List installed | `--list` / `-l` | `--list` | yes | `themey --list` |
| Apply theme | `--apply <name>` / `-a` | `--install <pkg>` | yes | Print command + opt-in `--apply` |
| Uninstall | n/a (delegates to file deletion) | `--remove <name>` | n/a | `themey --uninstall <name>` |
| Manifest tracking | Implicit (filesystem) | dpkg-style metadata.desktop | none | Explicit JSON manifest |
| Dry-run | no | no | no | `themey --inspect` |
| Batch | no | no | no | `themey --all` (the killer feature) |
| Progress | no | no | no | `rich` Progress for batch |
| Preview | no | no | no | HTML preview (only UI surface) |
| Conflict policy | overwrites silently | errors | overwrites | warn / `--force` / `--force --backup` |

**Takeaway:** existing KDE tooling has zero affordances for batch conversion or fidelity reporting because no upstream tool needs them. themey's batch + report + preview triad is the entire reason the tool exists; everything else (parser, generators) is just plumbing for that user experience.

## Sources

- [PROJECT.md](file:///home/cstory/src/themey/.planning/PROJECT.md) — authoritative scope
- [plasma-apply-lookandfeel man page](https://linuxcommandlibrary.com/man/plasma-apply-lookandfeel) — verified `-l` / `-a` interface
- [plasma-apply-colorscheme man page](https://linuxcommandlibrary.com/man/plasma-apply-colorscheme) — colorscheme apply CLI
- [plasma-theme-switcher (maldoinc)](https://github.com/maldoinc/plasma-theme-switcher) — third-party theme apply tool, reference for CLI surface
- [Plasma/Create a Look and Feel Package — KDE UserBase](https://userbase.kde.org/Plasma/Create_a_Look_and_Feel_Package) — bundle layout
- [tqdm](https://github.com/tqdm/tqdm) and [Rich Progress](https://rich.readthedocs.io/en/latest/progress.html) — batch progress UI references
- [CMake install_manifest pattern](https://gergap.wordpress.com/2015/08/18/cmake-uninstall/) — manifest-driven uninstall precedent
- [.NET local tools manifest](https://learn.microsoft.com/en-us/dotnet/core/tools/local-tools-how-to-use) — manifest-as-state pattern

---
*Feature research for: themey (E16 .etheme → KDE Plasma 6 Look-and-Feel CLI converter)*
*Researched: 2026-05-01*
