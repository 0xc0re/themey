# Pitfalls Research

**Domain:** Enlightenment DR16 `.etheme` archives → KDE Plasma 6 Look-and-Feel package conversion
**Researched:** 2026-05-01
**Confidence:** HIGH (all critical claims verified against E16 source at `/home/cstory/Downloads/e16-1.0.31/`, the user's installed Aurorae themes at `/home/cstory/.local/share/aurorae/themes/`, the actual Aliens.etheme archive contents, and current KDE developer docs / Plasma 6 porting guide. WebSearch claims about KColorScheme key names are MEDIUM — verified via multiple kdeglobals examples but not by reading kcolorscheme.cpp directly.)

---

## Critical Pitfalls

### Pitfall 1: `__EDGE_SCALING` order is **L R T B**, not "T B L R"

**What goes wrong:**
You parse `__EDGE_SCALING 3 2 32 5` as `top=3 bottom=2 left=32 right=5` because `PROJECT.md` and several sources say "T B L R". The titlebar PNG then stretches in the wrong direction at runtime — vertical stretch rules become horizontal, the tile band lands in the wrong spot, and decorations look squished or have visible scaling seams that don't appear in E16. Aurorae will happily render this without throwing an error; you only catch it visually.

**Why it happens:**
The four-int line is order-significant and undocumented in the theme files themselves; the actual order is established by the C parser. In `/home/cstory/Downloads/e16-1.0.31/src/iclass.c` the parse for both `__PADDING` and the per-state border (which is what `__EDGE_SCALING` becomes after the parser folds it into the most recently declared image state) is literally:
```c
sscanf(p2, "%i %i %i %i", &l, &r, &t, &b);
is->border->left = l;
is->border->right = r;
is->border->top = t;
is->border->bottom = b;
```
The struct is `EImageBorder { int left, right, top, bottom; }` (`/home/cstory/Downloads/e16-1.0.31/src/eimage.h`).

**How to avoid:**
Hardcode `EDGE_SCALING_ORDER = ("left", "right", "top", "bottom")` as a module-level constant in the parser with a comment citing `iclass.c:ICLASS_PADDING/ICLASS_BORDER`. Update PROJECT.md (currently says "T B L R") to match. Add a unit test that parses `__EDGE_SCALING 1 2 3 4` and asserts the resulting Python dict is `{left:1, right:2, top:3, bottom:4}`.

**Warning signs:**
Visual: titlebar tile that's clearly wider than tall has a horizontal stretch axis after conversion. PAGER_TOP icon's `__EDGE_SCALING 32 32 3 2` should make it stretch only in the L/R 32-px-margin region; if your output stretches it top/bottom instead, order is wrong. Also: borders that look "bowed" (corner pixels sampled from the wrong edge of the source PNG).

**Phase to address:** Phase 1 (parser). Test as a parser unit test, not as a visual regression; it's a parser-level bug.

---

### Pitfall 2: 1024 is fixed-point, but pixel offsets can be negative (right-anchored coords)

**What goes wrong:**
You correctly read `__BOTTOMRIGHT_X_PERCENTAGE 1024` as 100% — but you then read `__BOTTOMRIGHT_X_ABSOLUTE -27` as a clamping error and either drop it, take its absolute value, or set it to 0. Result: the close button binds to the right edge with no inset, gets clipped at the corner, or floats off the titlebar.

**Why it happens:**
E16 layout math is `final_pixel = (window_dim * percentage / 1024) + absolute`. Positive `absolute` adds inward; negative `absolute` is the standard way to express "27 px from the right edge" when paired with `percentage=1024`. From the actual `/tmp/themey_inspect/borders/default.cfg` TITLE_BAR_HORIZONTAL part: `__BOTTOMRIGHT_X_PERCENTAGE 1024` + `__BOTTOMRIGHT_X_ABSOLUTE -27`. Negative pixel deltas are the rule, not noise.

**How to avoid:**
Treat `_PERCENTAGE` as a Q10-fixed-point ratio (`fraction = pct / 1024.0`) and `_ABSOLUTE` as a signed pixel offset that can be any sign. Compute the right-edge inset as `inset_from_right = -absolute` when `percentage == 1024`. Never `abs()` a coordinate. Validate by asserting on `default.cfg` that the titlebar right edge sits at `width − 27` for any width.

**Warning signs:**
Phase-1 console log showing dropped/coerced negative values. Buttons rendering on top of each other at the right edge of the titlebar. Buttons that move off-screen as the window widens (sign of absolute being treated as percentage of width).

**Phase to address:** Phase 1 (coordinate evaluator inside the parser). The eval function must be the single source for both border coords and button coords.

---

### Pitfall 3: E16 has more states than Aurorae can express; collapse must be deliberate

**What goes wrong:**
E16's `__ICLASS` defines distinct images for `__NORMAL`, `__CLICKED`, `__NORMAL_ACTIVE`, `__CLICKED_ACTIVE`, `__NORMAL_STICKY`, `__CLICKED_STICKY`, `__NORMAL_ACTIVE_STICKY`, `__NORMAL_ACTIVE_CLICKED`, `__DISABLED` (verified in `imageclasses/borders.cfg` of Aliens.etheme — TITLE_BAR_HORIZONTAL has 8 of these). The struct in E16 (`iclass.c`) groups them into a 2D array: `{normal, hilited, clicked, disabled} × {norm, active, sticky, sticky_active}` — that's 16 cells. Aurorae has exactly three: active, inactive, maximized (`develop.kde.org/docs/plasma/aurorae/`). If you naively pick `__NORMAL` for inactive and `__NORMAL_ACTIVE` for active and ignore the rest, you silently throw away "shaded", "sticky", and click-feedback variants — and "maximized" has no E16 source at all.

**Why it happens:**
Asymmetric state models. E16 is a window-manager state machine where stickiness is a per-window flag with its own decoration; Aurorae cares only about focus and maximized geometry.

**How to avoid:**
Define the mapping table explicitly, as code:
```python
E16_TO_AURORAE_STATE = {
    "active":     ["__NORMAL_ACTIVE", "__NORMAL"],          # fall back to NORMAL
    "inactive":   ["__NORMAL"],                              # never use _ACTIVE
    "maximized":  ["__NORMAL_ACTIVE", "__NORMAL"],          # reuse active
}
# CLICKED, STICKY, DISABLED, ACTIVE_STICKY, ACTIVE_CLICKED are dropped.
```
Log the dropped states to `report.txt` so the user knows: "Aliens theme: 6 of 8 titlebar variants discarded (no Aurorae target)." Don't reuse `__NORMAL_ACTIVE_STICKY` as "maximized" — it isn't semantically maximized, just sticky-and-focused, and reusing it would surprise users whose mental model is "maximized = different border".

**Warning signs:**
A theme whose unfocused window looks identical to its focused one (you fell back to `__NORMAL_ACTIVE` for both because `__NORMAL` was missing). A `report.txt` that doesn't mention any dropped states (means you didn't track them, not that there weren't any).

**Phase to address:** Phase 1 — encoded in the parser's intermediate representation (each `ICLASS` keeps a dict of all states it defined) and in the Aurorae emitter (Phase 1 too, since this is AURORAE-01).

---

### Pitfall 4: Button binning by midpoint loses themes that use right-then-left layout

> **Superseded (2026-08):** Aurorae in Plasma 6 does NOT read `LeftButtons` /
> `RightButtons` from the theme rc — button order is **global**, from kwinrc
> `[org.kde.kdecoration2] ButtonsOnLeft` / `ButtonsOnRight`. The binning below
> still runs (it decides *which* button SVGs exist and feeds `report.txt`),
> but nothing about on-screen order is per-theme. themey no longer emits the
> two keys.

**What goes wrong:**
You bin buttons into Aurorae's `LeftButtons` / `RightButtons` by comparing each button's center-X against `window_width/2`. For the default Aliens.etheme border, `__TOPLEFT_X_ABSOLUTE 140` for ICONIFY puts it at x=140 (with `_PERCENTAGE 0`), and the titlebar starts at x=153 — so iconify-at-140 is to the **left** of the titlebar text region but it's still well past zero. Worst case: themes with two buttons on the left margin and three buttons clustered just inside the title text get bucketed weirdly because midpoint-of-window is the wrong reference. The buttons shuffle into a cluster that doesn't match the theme author's design.

**Why it happens:**
E16 buttons are positioned with mixed origin systems: each button can declare `__TOPLEFT_ORIGIN -1` (use default origin of -1 means "from left when paired with percentage=0, from right when paired with percentage=1024"). The "midpoint of titlebar" interpretation only works if you use the **titlebar's** midpoint, not the window's, AND if you've already resolved each button's actual pixel position relative to a representative window width.

**How to avoid:**
Three-step binning:
1. Resolve each button to a concrete pixel range using a reference window width (e.g. the `__BORDER_SIZE_LEFT/RIGHT/TOP/BOTTOM` plus a heuristic content width like 800 px).
2. The midpoint of the **titlebar** (not the window) is `titlebar_min_x + (titlebar_max_x - titlebar_min_x)/2` where titlebar bounds come from the TITLE_BAR_HORIZONTAL part's own coords resolved at the same reference width.
3. Buttons whose center-x falls in `[0, titlebar_min_x]` go to LeftButtons in their original X order; buttons in `[titlebar_max_x, window_width]` go to RightButtons; buttons that overlap the titlebar text region are dropped to `report.txt` with reason "overlaps titlebar text — no Aurorae equivalent".

This preserves left-cluster ordering (preserves the design intent of e.g. a "system menu" left button followed by close), prevents collisions with title text, and ensures right-edge buttons stay right.

**Warning signs:**
Aurorae rc with `LeftButtons=` (empty) and all five glyphs in `RightButtons` for a theme that visibly had a left-side menu button in the source. Buttons appearing in reverse order from the source.

**Phase to address:** Phase 1 (AURORAE-02). Add a fixture test using `default.cfg` from Aliens — assert `LeftButtons` order is empty or X-only, `RightButtons` order matches the spatial sort right-to-left.

---

### Pitfall 5: FrameSvg expects element IDs verbatim, with `decoration-` prefix and **no maximized fallback**

**What goes wrong:**
Your `decoration.svg` has elements named `top`, `topleft`, `center`, etc. — the names you'd intuit. Aurorae renders nothing visible because FrameSvg searches for IDs literally prefixed with `decoration-`. Or you include `id="decoration-maximized-center"` only and skip the eight maximized edge IDs (`-top`, `-topleft`, etc.) thinking "for maximized, only center is used" — except active/inactive *also* need their own full set, and a missing `decoration-inactive-top` causes the inactive titlebar to draw nothing on its top edge.

**Why it happens:**
KDE docs say "for maximized states, only the center element will be used" and people misread that as "for any decoration, only center is used". Verified ground truth: Edna theme at `/home/cstory/.local/share/aurorae/themes/Edna/decoration.svg` has the literal IDs:
```
decoration-bottom, decoration-center, decoration-top, decoration-left, decoration-right,
decoration-topleft, decoration-topright, decoration-bottomleft, decoration-bottomright,
decoration-inactive-{bottom,center,top,left,right,topleft,topright,bottomleft,bottomright}
```
That's 18 IDs. No maximized variants — and Edna still works. So **maximized variants are optional**; active + inactive (9 each = 18) are mandatory.

**How to avoid:**
Hardcode the required-ID set in the SVG emitter:
```python
SIDES = ["topleft","top","topright","left","center","right","bottomleft","bottom","bottomright"]
REQUIRED_IDS = [f"decoration-{s}" for s in SIDES] + [f"decoration-inactive-{s}" for s in SIDES]
```
After emitting `decoration.svg`, parse it back with `xml.etree.ElementTree` and assert all 18 IDs are present. Maximized is a stretch goal: if present, must be a full 9-set named `decoration-maximized-*` (the spec says only center is *rendered*, but unverified IDs may break some KWin versions).

**Warning signs:**
Empty/black titlebar in KWin after install. KWin debug output (`kdebugsettings` → KWin) showing "frame element not found". Visual diff: focused windows look fine, unfocused windows have a hollow/missing edge (the `-inactive-` set was incomplete).

**Phase to address:** Phase 1 (AURORAE-01). Verification step: after generating, programmatically validate ID set before declaring success.

---

### Pitfall 6: Embedding raster PNG inside SVG requires base64 + `preserveAspectRatio="none"`

**What goes wrong:**
You write the SVG with `<image href="artwork/n_title.png" .../>`. Aurorae loads the SVG, finds a relative href, fails to resolve it (it operates on the SVG content, not the file system around it), and renders nothing. Or you fix the href but leave `preserveAspectRatio` at default (`xMidYMid meet`), so the embedded PNG centers itself in the FrameSvg side region instead of stretching to fill the gap between corners — and the titlebar tile shows large transparent margins.

**Why it happens:**
SVG `<image>` elements default to `preserveAspectRatio="xMidYMid meet"`, which means "preserve aspect ratio, fit inside, center". For 9-patch tile bands you need "stretch to fit, ignore aspect". And FrameSvg can't follow file-system-relative `href` on disk inside a theme that's renamed/relocated.

**How to avoid:**
Two rules for every `<image>` in `decoration.svg`:
1. Inline the PNG as base64: `href="data:image/png;base64,<b64>"`. Use Python's `base64.b64encode(png_bytes).decode("ascii")`.
2. Always emit `preserveAspectRatio="none"` on every `<image>` element used as a tile region.

For the corner pieces (topleft etc.), aspect ratio doesn't matter much because the corner regions are sized by `__EDGE_SCALING`, but `preserveAspectRatio="none"` is still safe and consistent — apply it everywhere.

**Warning signs:**
Decoration renders as small tile in the middle of each band with empty space around it (aspect-ratio default kicked in). Decoration renders correctly during dev when `decoration.svg` is in place but breaks once installed (relative href didn't resolve from the install location). File size of `decoration.svg` is small, like under 10 KB, when source PNG is 50 KB+ (means you didn't actually embed it).

**Phase to address:** Phase 1 (AURORAE-03). Add an integration test: a generated decoration.svg, copied to a different directory, must still render the same checksums in a librsvg or QSvg dry-run rasterization.

---

### Pitfall 7: XBM cursors are 1-bit + separate mask; XCursor wants ARGB premultiplied

**What goes wrong:**
You pass an `.xbm` file directly to a tool that expects PNG, get garbage. Or you read XBM with Pillow, see a tiny monochrome image, and assume that's the cursor — but every E16 cursor ships *two* files: `cursor.xbm` (the bits) and `cursor.xbm.mask` (the alpha/transparency mask). You drop the mask, end up with a cursor that's a black rectangle on the screen because every "background" bit became opaque black instead of transparent.

**Why it happens:**
XBM is a stencil format from 1980s X11. The shape is in the data bits, the alpha is implicit in the mask file. Verified in `cursors.cfg`: every cursor line specifies `__XBM_FILE "artwork/cursors/cursor.xbm"` and the corresponding `cursor.xbm.mask` is implied (sibling file). Verified in archive: `artwork/cursors/cursor.xbm` and `artwork/cursors/cursor.xbm.mask` both ship. Plus `__FG_COLOR 255 255 255` and `__BG_COLOR 0 0 0` from cursors.cfg specify the colors to substitute for the 1-bits and 0-bits respectively. The `xcursorgen` tool wants a 32-bit ARGB PNG with premultiplied alpha and a hotspot.

**How to avoid:**
Cursor pipeline (Phase 4 — CURSORS-01):
1. Read `cursor.xbm` as a 1-bit Pillow image (Pillow's XBM reader handles this natively, mode=`'1'`).
2. Read `cursor.xbm.mask` (also XBM, also mode `'1'`).
3. Build an ARGB PNG: pixel `(x,y)` is `(R,G,B,A)` where `A = 255 if mask[x,y] else 0` and `(R,G,B) = fg_color if bits[x,y] else bg_color`.
4. Apply premultiplication: `R *= A/255` etc.
5. Read hotspot from XBM header (`#define cursor_x_hot 1` / `#define cursor_y_hot 1` are real lines you'll see — verified in `/tmp/themey_inspect/artwork/cursors/cursor.xbm`).
6. Emit PNG to a temp dir, write a config file `<size> <xhot> <yhot> <png_path>`, run `xcursorgen` (or implement the format yourself; it's documented and small).
7. Map E16 cursor names (`MOVE`, `RESIZE_H`, `RESIZE_V`, `RESIZE_BL`, `RESIZE_BR`, `MAX`, `KILL`, `ICONIFY`, `STICK`, `DEFAULT`) to XCursor canonical names — see the mapping table in the "Integration Gotchas" section below.

**Warning signs:**
After install, all cursors are black squares (mask was ignored). Cursors are present but show only a hotspot dot (mask was inverted — many XBM mask files are stored where 1=transparent, not 1=opaque). Cursor file sizes are 0 bytes (xcursorgen failed silently).

**Phase to address:** Phase 4 (CURSORS-01). This is its own phase because the XBM→ARGB pipeline is unrelated to the rest.

---

### Pitfall 8: TTF bundling into Look-and-Feel doesn't activate; X11 XLFD font names don't exist on modern Linux

**What goes wrong:**
Aliens.etheme has `ttfonts/aircut3.ttf` and `ttfonts/avgardm.ttf` and `textclasses.cfg` references them via TCLASS NORMAL `"*font-coords"`. You diligently bundle the TTFs into the look-and-feel package. Aurorae's titlebar text font isn't picked up from there — it uses the Plasma system title font (configured globally). The TTFs sit unused. Worse: half the themes reference their fonts via XLFD strings like `"-adobe-helvetica-medium-r-normal-*-*-100-*-*-*-*-*-*"` — those are X11 logical font descriptions that don't resolve on modern Linux without an X font server. Even reading `fonts.cfg` to map indirect references like `*font-coords` requires understanding the two-level indirection (`fonts.cfg` says `font-coords "<XLFD>"`, `textclasses.cfg` says `__NORMAL "*font-coords"`).

**Why it happens:**
E16 fonts pre-date the freedesktop fontconfig system (verified in `/tmp/themey_inspect/fonts.theme.cfg`). Aurorae has no per-theme font; it inherits from the system. There is no API to override.

**How to avoid:**
Don't try to override the title font; it's an Aurorae limitation. Pipeline:
1. Parse `fonts.cfg` and `textclasses.cfg` to identify what font *would* have been used for TITLE_BAR_HORIZONTAL's TCLASS (typically `TEXT1` → `font-default` → some XLFD).
2. If the resolved font is an XLFD (starts with `-`), map XLFD family token to a generic fontconfig family: `helvetica` → `sans-serif`, `lucida` → `serif`, `courier` → `monospace`. Log the mapping to `report.txt`.
3. If the resolved font references `ttfonts/*.ttf` directly (rare; requires reading the parser logic in `/home/cstory/Downloads/e16-1.0.31/src/tclass.c`), bundle the TTF *only* if it has a free license (check theme's `ABOUT/MAIN`); even then, log "font bundled but Aurorae cannot use it" — fonts can only be installed user-wide via `~/.local/share/fonts/` and require `fc-cache`. That side-effect is out of scope.
4. Take the resolved foreground color from the matching TCLASS (`__FORGROUND_COLOR` — note the misspelling, it's literally `FORGROUND` in the E16 grammar) and write it to the Aurorae rc as `ActiveTextColor` and `InactiveTextColor`. That's the fidelity we *can* deliver.

**Warning signs:**
report.txt that says "font preserved" when in fact only color was preserved. TTF files copied into the look-and-feel package contents (they don't belong there). Title text in the wrong color because you read the BACKGROUND color into ActiveTextColor by mistake.

**Phase to address:** Phase 1 — fonts/colors are part of the Aurorae rc generation. Color extraction logic should be shared with Phase 2 (COLORS-01).

---

### Pitfall 9: Plasma 6 manifest format — both `metadata.desktop` and `metadata.json`, no symlinks

**What goes wrong:**
You ship only `metadata.desktop` (which still works for Aurorae per the user's installed Sweet-Dark theme — verified at `/home/cstory/.local/share/aurorae/themes/Sweet-Dark/`). The window decoration appears in `kcm_kwindecoration` and works. Then the Look-and-Feel package wrapper needs a `manifest.json` with `"KPackageStructure": "Plasma/LookAndFeel"` (per Plasma 6 porting guide, develop.kde.org/docs/plasma/theme/theme-porting-to-plasma6/). Without it, the global theme doesn't show in System Settings → Global Theme. You debug the Aurorae-specific metadata.desktop, find it's correct, miss that the **outer** look-and-feel package has a separate manifest.

**Why it happens:**
Three different KDE package types are nested:
- The Aurorae package (in `~/.local/share/aurorae/themes/<name>/`) takes `metadata.desktop` (and optionally `metadata.json` per the user's Edna theme which has both).
- The Plasma color scheme (`~/.local/share/color-schemes/<name>.colors`) is a single file, no manifest.
- The Look-and-Feel package (`~/.local/share/plasma/look-and-feel/<name>/`) requires a Plasma 6 `manifest.json` with `KPackageStructure=Plasma/LookAndFeel`. **Plasma 6 also forbids symlinks anywhere in this tree.**

**How to avoid:**
For the Aurorae sub-package: emit `metadata.desktop` (works on Plasma 6 today) AND `metadata.json` (matches the Edna template, future-proofs against KF6 deprecation of .desktop files). The JSON form: `{"KPackageStructure": "aurorae", "KPlugin": {"Id": "<name>", "Name": "<display>", ...}}`. Critical: `KPlugin.Id` must equal the folder name.

For the Look-and-Feel package: emit only `metadata.json` with:
```json
{"KPackageStructure": "Plasma/LookAndFeel",
 "KPlugin": {"Id": "<name>", "Name": "<display>", "Version": "1.0", ...}}
```
Plus a `contents/defaults` INI with sections `[kwinrc][org.kde.kdecoration2]` (`library=org.kde.kwin.aurorae`, `theme=__aurorae__svg__<name>`), `[kdeglobals][General]` (`ColorScheme=<name>`), `[plasmarc][Theme]` etc.

For symlinks: when extracting `.etheme`, **resolve all symlinks** before emitting outputs. Aliens.etheme has `fonts.cfg → fonts.theme.cfg` and `ABOUT/aircut3.ttf → ../ttfonts/aircut3.ttf`. None of those should appear as symlinks in the output package — read through them at extract time.

**Warning signs:**
`plasma-apply-lookandfeel <name>` returns 0 but System Settings doesn't list the theme (manifest.json missing or wrong KPackageStructure). Theme appears but applying it fails silently (defaults file points at non-existent ColorScheme). `find ~/.local/share/plasma/look-and-feel/<name> -type l` returns any output (symlinks present, against spec).

**Phase to address:** Phase 5 (BUNDLE-01). Add a post-build validator that runs `find` for symlinks and checks `manifest.json` against a schema.

---

### Pitfall 10: `lookandfeeltool` is now an alias for `plasma-apply-lookandfeel`

**What goes wrong:**
Your CLI prints `Run: lookandfeeltool -a <name>` after conversion. PROJECT.md uses this exact phrasing in BUNDLE-01. On Plasma 6.6.4 systems with up-to-date packaging, `lookandfeeltool` is a thin shim/alias for `plasma-apply-lookandfeel` (per the January 2025 tldr-pages PR converting it explicitly). On *some* distros it's not installed at all (some packagers remove the alias). User runs the printed command, gets "command not found", thinks the conversion failed.

**Why it happens:**
Naming transition during the Plasma 5 → 6 split. `lookandfeeltool` was the Plasma 5 name; `plasma-apply-lookandfeel` is the Plasma 6 name. The alias exists on most distros but is not guaranteed. Both tools take `-a <pluginname>` with the same argument semantics.

**How to avoid:**
Detect at conversion time: `shutil.which("plasma-apply-lookandfeel")` first, fall back to `shutil.which("lookandfeeltool")`. Print the resolved command in the activation message and report.txt. If neither is found, print a System Settings → Global Theme manual instruction (always works). Update PROJECT.md BUNDLE-01 wording from "via `lookandfeeltool -a <name>`" to "via `plasma-apply-lookandfeel <name>` (or its alias `lookandfeeltool -a <name>`)". (Note: `plasma-apply-lookandfeel` does NOT take `-a` — it takes the plugin name positionally; double-check argument format on the user's machine before committing the message.)

**Warning signs:**
User reports "command not found". preview.html / report.txt mentions the deprecated form only.

**Phase to address:** Phase 6 (PREVIEW-01) and Phase 5 (BUNDLE-01). Single helper `resolve_apply_command()` used by both.

---

### Pitfall 11: tarfile path traversal and symlink escape in untrusted archives

**What goes wrong:**
You run `tarfile.open(etheme).extractall(dest)`. Most `.etheme` files from `themes.effx.us` (2009-era) are benign, but the user explicitly wants to be able to convert any `.etheme` they encounter. A malicious archive contains a member like `../../../.bashrc` or a symlink `evil → /home/cstory/.ssh` followed by a regular file written through that symlink. Files outside `dest` get clobbered.

**Why it happens:**
Python's `tarfile.extractall` historically did no validation (CVE-2007-4559, fifteen years to fix). The `filter="data"` parameter was added in Python 3.12 and *defaulted* in 3.14 for security, but with bugs: CVE-2025-4330 / CVE-2025-4517 showed the data filter is bypassable via PATH_MAX overflow on Linux. Even with mitigations, users on Python 3.11 (PROJECT.md says "3.11+") get the older, less-safe behavior.

**How to avoid:**
Don't use `extractall`. Iterate members and validate each one yourself:
```python
def safe_extract(tar: tarfile.TarFile, dest: pathlib.Path):
    dest = dest.resolve()
    for member in tar.getmembers():
        # Reject absolute and parent paths
        target = (dest / member.name).resolve()
        if not str(target).startswith(str(dest) + "/") and target != dest:
            raise SecurityError(f"path traversal: {member.name}")
        # Reject device files and FIFOs always
        if member.ischr() or member.isblk() or member.isfifo():
            raise SecurityError(f"unsafe member type: {member.name}")
        # For symlinks: resolve the symlink target as if from dest, ensure inside dest
        if member.issym() or member.islnk():
            link_target = (target.parent / member.linkname).resolve()
            if not str(link_target).startswith(str(dest) + "/"):
                raise SecurityError(f"symlink escape: {member.name} -> {member.linkname}")
        tar.extract(member, dest)
```
Also pass `filter="data"` if Python ≥ 3.12 as defense-in-depth. **Extract to a private temp directory** (`tempfile.TemporaryDirectory`), not directly into `~/.local/share/...`. Resolve symlinks (read the target file's content and copy it as a regular file at the symlink's location) BEFORE writing to the user's home. The Plasma 6 spec also forbids symlinks in look-and-feel packages, so you can't pass them through anyway.

**Warning signs:**
Tarfile members logged with `..` or absolute paths (always log member.name during dev). Files appearing under `~/.local/share/aurorae/themes/` that aren't part of the theme. Modified config files (`.bashrc`, `.config/...`).

**Phase to address:** Phase 1 (PARSE-01). The `safe_extract` helper goes in the parser module and is the only way the codebase ever opens a tar archive.

---

### Pitfall 12: HiDPI/fractional scaling makes Aurorae themes pixelate; KSvg helps but raster-embed defeats it

**What goes wrong:**
Plasma 6.6 has known fractional-scaling bugs in Aurorae (per the user's ground-truth Plasma version 6.6.4 and verified at discuss.kde.org/t/non-integer-scaling-application-style-window-decorations-pixelated-on-6-6-with-many-themes). The new "Aurorae V2" rewrite (blog.vladzahorodnii.com/2025/11/13/whats-next-for-aurorae/) uses raw KSvg to address this. Your themes embed PNG inside SVG — which means even on V2, the *content* is raster and will pixelate at 1.25× / 1.5× display scales no matter how good the SVG container is. The user's `--scale=2` default helps because it pre-scales the raster source 2×; on a 1× display it then downscales (with mild blur but acceptable); on a 2× display it's pixel-perfect; on a 1.5× display it interpolates.

**Why it happens:**
SVG with embedded raster is functionally a bitmap with metadata. There's no way to vectorize 2009 PNG button glyphs without losing fidelity (PROJECT.md decision: "no rasterize-to-vector step").

**How to avoid:**
Make `--scale=2` the default (PROJECT.md already says this). Document in report.txt: "This theme uses embedded PNGs at 2× source resolution. Quality on fractional display scales (1.25, 1.5, 1.75) is approximate. Pixel-perfect on 1.0×, 2.0×, and 3.0×." Test the Aurorae output at three KWin-display scales (1.0, 1.5, 2.0) before declaring Phase 1 done. On `--scale=3`, decoration.svg gets 3x larger PNGs — file size jumps; if any output exceeds e.g. 2 MB, log a warning to report.txt because some FrameSvg cache misbehaviors have been reported on large embedded images.

**Warning signs:**
Themes look fine at 100%/200% and gross at 150%. report.txt has no scale-quality note. decoration.svg larger than 5 MB (excessive embed; consider downscaling the source or using `--scale=1`).

**Phase to address:** Phase 1 (CLI-02 / scale handling) and Phase 6 (PREVIEW-01) — preview should mock at the user's actual display scale to catch this before activation.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Skip `__SHADE_DIRECTION` and shade-state borders | Faster Phase 1; Aurorae has no shade state | "Shade" is a real KWin window state; themes designed around it lose their shaded variant. report.txt note required. | Always — explicit, logged. |
| Pick `__NORMAL_ACTIVE` for both maximized and active | Avoids generating a third SVG state set | Maximized borders are visually identical to active — fine in MVP, suboptimal for themes that visibly distinguish them | MVP — log to report.txt. Revisit only if a target theme's design demands it. |
| Use a single representative window width (e.g. 800 px) when binning buttons | Avoids needing to recompute layout per actual window size | Themes designed for narrow windows may bin oddly; sticky_active variants etc. all dropped silently | MVP — narrow themes are rare in the target catalog. |
| `report.txt` is plain text, not structured | Trivial to write | Future tooling (e.g. a fidelity dashboard across all 223 themes) needs to re-parse | Acceptable — single user, single project. |
| Embed source PNG at full resolution in SVG | Maximum fidelity, simplest pipeline | decoration.svg can grow large (200 KB+); KSvg cache is per-theme so cost is bounded | Always — alternative is vector tracing which loses character. |
| Skip `__BUTTON` definitions in `buttons.cfg` (the ones outside borders) | Avoids fabricating panel buttons | E16 panel-style action buttons (EXEC_TERMINAL etc.) are out of scope per PROJECT.md "Out of Scope" | Always — already declared OOS. |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `xcursorgen` invocation | Calling system `xcursorgen` and assuming it's installed (it's the `xorg-xcursorgen` package, often not default) | Implement XCursor file format directly (small spec at x.org); avoids external dep. The format is documented and parseable in <100 LoC. |
| E16 cursor name → XCursor name | Assuming names match | E16 name → XCursor name: `DEFAULT` → `default` and `left_ptr`; `MOVE` → `move` and `fleur`; `RESIZE_H` → `sb_h_double_arrow`; `RESIZE_V` → `sb_v_double_arrow`; `RESIZE_BL` → `bottom_left_corner`; `RESIZE_BR` → `bottom_right_corner`; `MAX` → `pirate` (no good match — the E16 "kill" / "max" semantics don't have XCursor equivalents); `KILL` → `pirate`; `ICONIFY` → no good match (skip); `STICK` → no good match (skip). Generate symlinks within the cursor directory for canonical alternates (e.g. cursors/move and cursors/fleur both point at the same .xcursor file, *symlinks INSIDE the cursor dir are allowed* — the no-symlinks rule is for the Plasma look-and-feel package, not the XCursor theme dir). |
| `index.theme` (XCursor) vs `index.theme` (icon theme) | Same filename, different schema | XCursor's `index.theme` has section `[Icon Theme]` with key `Inherits=Adwaita` (so unmapped cursors fall back) and `Name=<theme>`. Icon-theme spec is different. Don't reuse code. |
| `.colors` file `[WM]` section | Putting only `activeBackground` and `inactiveBackground` | Aurorae rc reads `ActiveTextColor`/`InactiveTextColor` directly from the rc, not from .colors. The `.colors` `[WM]` section is for Breeze/legacy decoration, not Aurorae — so for our Aurorae output, the `.colors` file affects *application* widget color, not titlebar color. Set both anyway: `[WM] activeBackground/activeForeground/activeBlend/inactiveBackground/inactiveForeground/inactiveBlend` plus `frame`/`inactiveFrame` for window border tint. |
| `[Colors:View]`, `[Colors:Window]`, `[Colors:Button]` etc. | Forgetting one of the seven required color sets in `.colors` | KColorScheme requires Colors:View, :Window, :Button, :Selection, :Tooltip, :Header, :Complementary — all seven, each with BackgroundNormal/BackgroundAlternate/ForegroundNormal/ForegroundActive/ForegroundInactive/ForegroundLink/ForegroundVisited/ForegroundNegative/ForegroundNeutral/ForegroundPositive/DecorationFocus/DecorationHover. Generate from a small color-derivation function so all seven are consistent. |
| KWin reload on Wayland | Telling user `kwin --replace` | On Wayland it's `kwin_wayland --replace &` (different binary). On X11 it's `kwin_x11 --replace &`. Detect via `$XDG_SESSION_TYPE` and print the right one. Even better: just run `qdbus org.kde.KWin /KWin reconfigure` for theme reload — no compositor restart needed for decoration changes specifically. |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Re-parsing the same `#include` file each time it's referenced | Slow Phase 1 on themes with deep include trees | Cache parsed config files by canonical path inside the parser. | A theme with 10+ borders that all `#include <definitions>`. Aliens.etheme has only one or two `#include` levels — likely fine, but worth caching. |
| Loading every PNG into memory at once for `--all` batch mode | Memory blowup on the 223-theme catalog (some themes 4 MB, mostly PNGs) | Process one theme at a time; use `with` blocks; explicitly `del` Pillow images. | Batch run (`themey --all /path/`). 223 themes × tens of MB working set = OOM on a constrained machine. |
| Calling Pillow `.resize()` with default `NEAREST` | Pixelated output for `--scale=2` upscale | Pass `Image.Resampling.LANCZOS` or `BICUBIC` explicitly. Document in code comments why. | Any theme — the default is fast but ugly. |
| Re-running `xcursorgen` per cursor instead of building all .xcursor files in one pass | Slow conversion (each invocation forks) | If using external xcursorgen, batch via subprocess; ideally implement format internally. | Themes with 10+ cursors (some have full sets). |
| HTML preview opens a browser tab per converted theme in `--all` mode | 223 tabs spawned in a batch run | `--all` should suppress preview (only print the activation command per theme); single-theme mode opens preview. | Batch conversion of more than ~5 themes. |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `tarfile.extractall(dest)` without filter | Path traversal — files written outside `dest`, including `~/.bashrc`, `~/.ssh/authorized_keys` | Manual member-by-member validation (see Pitfall 11). Extract to private tempdir first; copy to `~/.local/share/...` only after validation. |
| Following symlinks during extraction | Symlink escape — adversary creates `evil → /home/cstory/.ssh/` then a regular file `evil/authorized_keys` overwrites it | Resolve symlinks at extract time, store target content as regular files. Plasma 6 forbids symlinks in look-and-feel packages anyway, so this aligns. |
| Trusting `ABOUT/MAIN` HTML to pick a theme name | XSS-like — if you ever render this in the HTML preview without escaping, attacker-controlled HTML executes in user's browser | (a) Theme name comes from archive filename, never from MAIN content. (b) If preview renders MAIN at all, parse it as plain text or escape via `html.escape`. |
| Writing into `~/.local/share/aurorae/themes/<name>` while a theme of that name already exists | Clobbering user's installed theme | Conversion outputs to a temp dir; if `--install` flag set, refuse if target exists unless `--force`. PROJECT.md says all output is reversible — make that an enforced invariant, not just an aspiration. |
| `os.makedirs(path, exist_ok=True)` with `path` derived from theme name without sanitization | Theme named `../../../etc/whatever` writes outside install dir | Sanitize theme name to `[A-Za-z0-9_-]+` (slugify) before using it in any output path. Also affects the preview HTML filename. |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Auto-applying the theme after conversion | Surprise full-desktop visual change mid-batch run; user can't undo via undo-stack | PROJECT.md key decision already says "no auto-switch, just install + preview + print command". Honor this. |
| Preview HTML includes `<a>` to executable activation command | Browsers don't run shell from HTML, but copy-paste UX is friction | Display the command in a `<pre>` block with a "click to copy" JS button (no shell invocation, just clipboard). |
| `report.txt` is a wall of text | Users skim past, miss critical "approximated" warnings | Use sections: **Preserved**, **Approximated**, **Skipped**. Approximated section first when non-empty. Hard limit ~50 lines. |
| Showing converted scale (`--scale=2`) but not the original E16 dimensions | User can't reason about whether their result is "correct" | report.txt: "E16 source titlebar: 13 px → output titlebar: 26 px (scale 2×)". Concrete numbers. |
| Identical theme names across 223 input archives if user batch-converts to a flat namespace | Later conversions overwrite earlier ones | Slugify and deduplicate: if `Aliens` exists, next is `Aliens-2`. Or refuse with clear message. |
| HTML preview opens in default browser even when running over SSH | "browser opened on the wrong machine" / silent failure on headless | Detect `$DISPLAY` empty / `$SSH_CONNECTION` set; in those cases skip auto-open and just print the file path. |

---

## "Looks Done But Isn't" Checklist

- [ ] **Aurorae rc:** Often missing `[Layout]` keys. Verify all 8 expected: `BorderLeft`, `BorderRight`, `BorderBottom`, `BorderTop`, `TitleEdgeTop`, `TitleEdgeBottom`, `TitleEdgeLeft`, `TitleEdgeRight`. Also `LeftButtons` / `RightButtons` strings — even if empty, must be present.
- [ ] **decoration.svg:** Often missing `decoration-inactive-*` set (forgot the unfocused state). Verify 18 IDs minimum (9 active + 9 inactive). Validate after generation, not just at runtime.
- [ ] **Per-button SVGs:** Often missing `restore.svg` (the maximized-state version of `maximize.svg`). Without it, a maximized window's "restore" glyph falls back to a generic one. Also commonly missing: hover and pressed sub-elements within each button SVG (Aurorae looks for `<button-name>-hover` and `<button-name>-pressed` IDs).
- [ ] **Color scheme `.colors`:** Often missing one of the seven `[Colors:*]` sections. Validate against KColorScheme's required-sections list before declaring done.
- [ ] **XCursor theme:** Often missing `index.theme` with `Inherits=Adwaita` (or similar) — without it, unmapped cursor names show as the system default (jarring mismatch). Also commonly missing: hotspot in cursors that aren't pointer-tip (e.g. `move` should have hotspot at center).
- [ ] **Look-and-feel `manifest.json`:** Often has `KPackageStructure` but not `Plasma/LookAndFeel` (e.g. `Plasma/Theme` or wrong case). Validate string match.
- [ ] **Look-and-feel `contents/defaults`:** Often missing one of the four sections (kwinrc decoration, kdeglobals colors, plasmarc theme, kcminputrc cursor). All four needed for `plasma-apply-lookandfeel` to actually switch all four layers.
- [ ] **Wallpaper package:** Often missing `metadata.json` (KPackageStructure=Wallpaper/Image). The wallpaper image alone in `~/.local/share/wallpapers/<name>/contents/images/` does not register with Plasma without the manifest.
- [ ] **Wallpaper `metadata.json` field:** Often missing `X-KDE-PluginInfo-Name` or it doesn't match folder name. Both `metadata.json`'s `KPlugin.Id` AND the parent folder name must agree.
- [ ] **report.txt:** Often missing the "Skipped" section. If you preserved everything, say so explicitly; if you skipped silently, the user has no idea what's missing.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong `__EDGE_SCALING` order (Pitfall 1) | LOW | Fix the constant, regenerate. Output dirs are under `~/.local/share/...`; delete + reconvert. |
| Decoration shows nothing (Pitfall 5/6) | LOW | Inspect `decoration.svg` for the 18 required IDs; check `<image>` elements for `data:` href and `preserveAspectRatio="none"`. Regenerate. |
| Path traversal during extraction (Pitfall 11) | HIGH if undetected | If user reports modified system files: instruct them to inspect `~/.bash_history`, restore from backup. Always extract to tempdir; the output dir clobbering is bounded to `~/.local/share/...` if `safe_extract` is used. |
| Black/garbled cursors (Pitfall 7) | LOW | XBM mask not applied or inverted. Regenerate the cursor pipeline; manually verify one cursor PNG looks right before regenerating the full set. |
| Theme installs but doesn't apply (Pitfall 9/10) | LOW | Verify `manifest.json` schema; verify `contents/defaults` has all four sections; try `plasma-apply-lookandfeel` directly with verbose flag. |
| Symlinks leaked into output (Pitfall 9) | MEDIUM | `find ~/.local/share/plasma/look-and-feel/<name> -type l -delete`, then re-extract the source `.etheme` with symlinks resolved. |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. EDGE_SCALING order is L R T B | Phase 1 (parser) | Unit test: parser of `__EDGE_SCALING 1 2 3 4` produces dict `{left:1, right:2, top:3, bottom:4}` |
| 2. Negative pixel coords + 1024 fixed-point | Phase 1 (coord evaluator) | Unit test: TITLE_BAR_HORIZONTAL coords resolve to `(left=153, right=window_width−27)` for Aliens default border |
| 3. Aurorae has 3 states, E16 has 16 | Phase 1 (state collapse mapping) | Run on Aliens, assert report.txt logs ≥4 dropped states |
| 4. Button binning by titlebar midpoint | Phase 1 (AURORAE-02) | Fixture: Aliens default border → `LeftButtons=""`, `RightButtons` includes IA in spatial order |
| 5. FrameSvg required ID set | Phase 1 (AURORAE-01) | Post-build XML validation: 18 required IDs present in decoration.svg |
| 6. PNG embed + preserveAspectRatio="none" | Phase 1 (AURORAE-03) | Smoke test: rasterize generated SVG with QSvg; checksum invariant under file move |
| 7. XBM cursors are 1-bit + mask | Phase 4 (CURSORS-01) | Convert one cursor; visual diff against reference XCursor preview |
| 8. Title font + color extraction | Phase 1 (rc generation) + Phase 2 (COLORS-01) | rc has `ActiveTextColor` matching the source TCLASS `__FORGROUND_COLOR` |
| 9. Plasma 6 manifest + no symlinks | Phase 5 (BUNDLE-01) | `find <pkg> -type l` returns empty; `manifest.json` has KPackageStructure=Plasma/LookAndFeel |
| 10. lookandfeeltool naming | Phase 5/6 (activation message) | `which plasma-apply-lookandfeel` resolved at print-time |
| 11. tarfile path traversal | Phase 1 (PARSE-01) | Negative test: archive with `../etc/passwd` member fails extraction with SecurityError |
| 12. HiDPI / fractional scale pixelation | Phase 1 (CLI-02) + Phase 6 (PREVIEW-01) | Visual smoke test at 1.0×, 1.5×, 2.0× display scale |

---

## Sources

- E16 source code (ground truth for grammar): `/home/cstory/Downloads/e16-1.0.31/src/iclass.c`, `iclass.h`, `eimage.h`, `borders.c`, `tclass.c`, `cursors.c`. Confirms `EImageBorder { left, right, top, bottom }`, the parse `sscanf(p2, "%i %i %i %i", &l, &r, &t, &b)` for both `__PADDING` and per-state borders, and the 16-cell `ImageStateArray { norm, active, sticky, sticky_active } × { normal, hilited, clicked, disabled }` model. (HIGH confidence.)
- User's installed Aurorae themes (ground truth for KDE side): `/home/cstory/.local/share/aurorae/themes/{Edna,Sweet-Dark,Sweet-Dark-transparent}/`. Confirms minimum required FrameSvg ID set (18 IDs, no maximized variants needed), that `metadata.desktop` alone works, and that `metadata.json` is acceptable when both exist. (HIGH confidence.)
- Actual Aliens.etheme archive contents at `/tmp/themey_inspect/`. Confirms tar layout (gzipped, extracts FLAT — no top-level theme dir), symlink presence (`fonts.cfg → fonts.theme.cfg`, `ABOUT/aircut3.ttf → ../ttfonts/aircut3.ttf`), XBM cursor + mask sibling layout, and XLFD font strings in `fonts.theme.cfg`. (HIGH confidence.)
- [Aurorae window decorations | KDE Developer](https://develop.kde.org/docs/plasma/aurorae/) — element ID prefixes, state suffixes, metadata.desktop format. (HIGH.)
- [Porting Themes to Plasma 6 | KDE Developer](https://develop.kde.org/docs/plasma/theme/theme-porting-to-plasma6/) — `manifest.json` with `KPackageStructure=Plasma/LookAndFeel` is required, no symlinks in package tree, QML import renames. (HIGH.)
- [What's next for Aurorae? — Vlad Zahorodnii (2025-11-13)](https://blog.vladzahorodnii.com/2025/11/13/whats-next-for-aurorae/) — Aurorae V2 rewrite using KSvg, fractional-scaling fixes ongoing, V1/V2 coexist, no formal V1 deprecation. (HIGH.)
- [Non-integer scaling pixelation on 6.6 — KDE Discuss](https://discuss.kde.org/t/non-integer-scaling-application-style-window-decorations-pixelated-on-6-6-with-many-themes/44480) — confirms the user's Plasma 6.6 has known fractional-scaling Aurorae bugs. (MEDIUM — community thread.)
- [tldr-pages PR #15444: lookandfeeltool to alias, plasma-apply-lookandfeel new page](https://github.com/tldr-pages/tldr/pull/15444) — confirms the rename. (HIGH.)
- [Path traversal bug in Python's tarfile (CVE-2007-4559) — Secure Code Warrior](https://www.securecodewarrior.com/article/traversal-bug-in-pythons-tarfile-module) and [CVE-2025-4330: Python tarfile path traversal](https://www.sentinelone.com/vulnerability-database/cve-2025-4330/) — even with Python 3.12+ `filter="data"` default, bypasses exist via PATH_MAX overflow. (HIGH.)
- [xcursorgen man page (X.Org)](https://www.x.org/releases/current/doc/man/man3/Xcursor.3.xhtml) — XCursor file format, ARGB packing, hotspot semantics. (HIGH.)
- [SVG elements and Inkscape | KDE Developer](https://develop.kde.org/docs/plasma/theme/theme-svg/) — embed (don't link) raster images; `preserveAspectRatio="none"` recommended for stretched tiles. (HIGH.)
- [Cursor themes — ArchWiki](https://wiki.archlinux.org/title/Cursor_themes) — `index.theme` schema, `Inherits=` fallback chain, freedesktop spec compliance. (HIGH.)
- [KDE bug 439222 — \[WM\] frame and inactiveFrame colors not honored in kdeglobals](https://bugs.kde.org/show_bug.cgi?id=439222) — confirms `[WM]` section keys: `activeBackground`, `activeForeground`, `activeBlend`, `inactiveBackground`, `inactiveForeground`, `inactiveBlend`, `frame`, `inactiveFrame`. (MEDIUM — bug report referencing actual key names but not authoritative spec doc.)

---
*Pitfalls research for: E16 .etheme → Plasma 6 Look-and-Feel conversion*
*Researched: 2026-05-01*
