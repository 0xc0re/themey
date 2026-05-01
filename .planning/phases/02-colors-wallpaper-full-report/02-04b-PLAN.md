---
phase: 02-colors-wallpaper-full-report
plan: 04b
type: execute
wave: 4
depends_on: [02-01, 02-02, 02-03, 02-04a]
files_modified:
  - src/themey/preview.py
  - tests/test_preview.py
  - tests/test_aliens_phase2_e2e.py
autonomous: false
requirements: [COLORS-01, WALLPAPER-01]
user_setup: []
must_haves:
  truths:
    - "preview.py is REFACTORED IN PLACE (Phase 1 shipped it as a 98-line module with html.escape protection at lines 14, 42, 43, 44; this plan REPLACES the API with the new render_preview design AND PRESERVES the html.escape protection that Phase 1 already had)"
    - "preview.py renders an HTML file containing 6 color swatches (Window BG, Window FG, Accent, WM active BG, WM active FG, WM inactive BG) and a base64-embedded wallpaper thumbnail"
    - "EVERY theme-derived string inserted into the rendered HTML (theme.display_name, swatch labels, activation_command, theme.author, categorized note bodies) is wrapped in html.escape() before insertion (per checker Issue 4 — preserves the XSS protection Phase 1 already had at lines 14, 42, 43, 44 of the legacy preview.py)"
    - "The Aliens canary end-to-end test produces a .colors file selectable in System Settings, a wallpapers/Aliens/ package selectable in Configure Desktop, an HTML preview with swatches+thumbnail, and a report.txt with all three sections populated"
    - "The Aliens E2E test calls themey.etheme.parse.parse_tree(asset_root, entry_files=[...]) — the EXACT pinned signature (per src/themey/etheme/parse.py:47-73 and checker Warning W1) — NOT a defensive try/except wrapper"
    - "User visually confirms in System Settings → Colors that the Aliens-derived palette installs and renders, and in Configure Desktop → Wallpaper that the Aliens wallpaper installs and renders"
  artifacts:
    - path: "src/themey/preview.py"
      provides: "MODIFIED IN PLACE — replaces Phase 1's render(theme, out_path) -> Path API with render_preview(theme, *, color_scheme_path, wallpaper_dir, activation_command, embed_thumbnail=True) -> str; PRESERVES html.escape() protection on every theme-derived string"
      exports: ["render_preview"]
    - path: "tests/test_aliens_phase2_e2e.py"
      provides: "End-to-end test: extract Aliens.etheme → parse_tree → build_theme → write .colors + wallpaper package + report + preview; assert all artefacts present and well-formed"
      contains: "Aliens"
  key_links:
    - from: "src/themey/preview.py"
      to: "src/themey/images/embed.image_to_jpeg_b64_uri"
      via: "preview embeds wallpaper thumbnail via the JPEG variant"
      pattern: "image_to_jpeg_b64_uri"
    - from: "src/themey/preview.py"
      to: "src/themey/report.categorize_notes"
      via: "preview reuses categorize_notes for the categorised notes list"
      pattern: "from themey.report import categorize_notes"
    - from: "src/themey/preview.py"
      to: "html.escape stdlib"
      via: "every theme-derived string is escaped before insertion (per checker Issue 4 — preserves Phase 1's protection)"
      pattern: "html.escape"
---

<objective>
Wave 3b finalization. Three tasks in this plan:

1. **REFACTOR `src/themey/preview.py` IN PLACE** (per checker Issue 1): Phase 1 shipped this file as a 98-line module with `def render(theme, out_path) -> Path` and html.escape protection at lines 14, 42, 43, 44. This plan REPLACES the API with the Phase 2 `render_preview(theme, *, color_scheme_path, wallpaper_dir, activation_command, embed_thumbnail=True) -> str` design — and PRESERVES the html.escape protection on every theme-derived string (per checker Issue 4 — the legacy module already had `import html` and `html.escape(s)` calls; the new module MUST retain them or theme name `<script>alert(1)</script>` lands in HTML attribute values unescaped).

2. **Aliens.etheme end-to-end test** (`tests/test_aliens_phase2_e2e.py`): extract Aliens.etheme, parse via `parse_tree(asset_root, entry_files=[...])` (per checker Warning W1 — the PINNED parser signature, NOT a defensive try/except wrapper), call build_theme, write .colors + wallpaper package + report + preview; assert each artefact is well-formed.

3. **Manual visual gate** (Task 3, checkpoint:human-verify): user runs the conversion writing to real `~/.local/share/...`, opens System Settings → Colors and Configure Desktop → Wallpaper, confirms both install and the rendering "feels like Aliens".

This plan is non-autonomous because of the visual checkpoint. Tasks 1-2 are autonomous; Task 3 is the human-verify gate.

Output:
- `src/themey/preview.py` (MODIFIED IN PLACE — refactored API; html.escape protection preserved)
- `tests/test_preview.py` (MODIFIED — migrated from `themey.preview.render` to `render_preview`; existing XSS test extended to cover the new code paths)
- `tests/test_aliens_phase2_e2e.py` (NEW — end-to-end fixture test using the pinned parse_tree signature)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/02-colors-wallpaper-full-report/02-RESEARCH.md
@.planning/phases/02-colors-wallpaper-full-report/02-PATTERNS.md
@.planning/phases/02-colors-wallpaper-full-report/02-01-PLAN.md
@.planning/phases/02-colors-wallpaper-full-report/02-02-PLAN.md
@.planning/phases/02-colors-wallpaper-full-report/02-03-PLAN.md
@.planning/phases/02-colors-wallpaper-full-report/02-04a-PLAN.md
@src/themey/ir.py
@src/themey/preview.py
@src/themey/report.py
@src/themey/paths.py
@src/themey/etheme/parse.py
@src/themey/etheme/archive.py
@src/themey/images/embed.py
@tests/test_preview.py
@tests/test_archive.py
@tests/conftest.py

<interfaces>
<!-- Pinned parser entry-point signatures (src/themey/etheme/parse.py:40-73) — NO try/except needed: -->

```python
# src/themey/etheme/parse.py — these signatures are STABLE; the Aliens E2E test calls them directly.
def parse_file(path: Path) -> list[AstNode]:
    """Parse one cfg file. Returns top-level nodes (Blocks, KeyVals, Includes)."""

def parse_tree(
    asset_root: Path,
    entry_files: list[str] | None = None,
) -> list[AstNode]:
    """Parse a theme tree starting from entry_files; resolve #include directives.

    Default entry_files = ["borders.cfg", "imageclasses.cfg", "textclasses.cfg"].
    Missing entry files are silently skipped.
    Returns flat list of all top-level AstNode entries from all parsed files.
    """
```

The Aliens E2E test must call: `parse_tree(raw.asset_root, entry_files=["borders.cfg", "imageclasses.cfg", "textclasses.cfg", "desktops.cfg", "init.cfg"])` — extending the default list with `desktops.cfg` (where __DESKTOP blocks live for the wallpaper) and `init.cfg` (the theme's main entry which may #include other cfg files). Per checker Warning W1: NO try/except TypeError wrapper — the signature is pinned.

<!-- All Wave 1+2+3a outputs available to Wave 3b: -->

```python
# From 02-01 (src/themey/ir.py)
PRESERVED_PREFIX, APPROXIMATED_PREFIX, SKIPPED_PREFIX  # imported from themey.ir
@dataclass(frozen=True) class Theme:  # has color_scheme + wallpaper fields

# From 02-03 (src/themey/images/embed.py)
def image_to_jpeg_b64_uri(img: Image.Image, quality: int = 80) -> str: ...

# From 02-03 (src/themey/generate/colors.py + generate/wallpaper.py)
def write_colors_ini(theme: Theme, out_path: Path) -> Path: ...
def write_wallpaper_package(theme: Theme, out_dir: Path) -> Path: ...

# From 02-04a (src/themey/report.py — refactored in place)
def render_report(theme: Theme, output_paths: list[Path]) -> str: ...
def categorize_notes(notes: list[str]) -> dict[str, list[str]]: ...

# From 02-04a (src/themey/paths.py — additive)
def color_schemes() -> Path: ...
def wallpapers() -> Path: ...
```

<!-- EXISTING preview.py contract (Phase 1, src/themey/preview.py — 98 lines) — this plan REPLACES it: -->

```python
# Phase 1 (current) src/themey/preview.py — already has html.escape protection:
import html  # line 14

def render(theme: Theme, out_path: Path) -> Path:
    """Write an HTML preview of *theme* to *out_path*."""
    notes_html = "\n".join(
        f"  <li><code>{html.escape(n)}</code></li>"     # ESCAPES (line 26)
        for n in theme.notes[:50]
    )
    name_safe = html.escape(theme.display_name)         # ESCAPES (line 42)
    plugin_id_safe = html.escape(theme.name)            # ESCAPES (line 43)
    skipped_safe = html.escape(...)                     # ESCAPES (line 44)
    # builds HTML with escaped strings interpolated
    out_path.write_text(doc, encoding="utf-8")
    return out_path

# 02-04b REPLACES with:
def render_preview(
    theme: Theme,
    *,
    color_scheme_path: Path | None,
    wallpaper_dir: Path | None,
    activation_command: str,
    embed_thumbnail: bool = True,
) -> str:
    """Returns the HTML document; caller writes it. PRESERVES html.escape on
    every theme-derived string per checker Issue 4 (matches Phase 1 behaviour)."""
```

<!-- EXISTING test_preview.py (Phase 1) — calls themey.preview.render — this plan MIGRATES it: -->

The existing tests/test_preview.py (126 lines, 6 tests) imports `from themey.preview import render` and includes `test_preview_escapes_html_in_notes` (line 94) which constructs a Theme with `notes=["<script>alert(1)</script>"]` and asserts:
- The raw `<script>alert(1)</script>` does NOT appear in the output
- The escaped form `&lt;script&gt;` DOES appear

This test is the regression guard that motivates the html.escape requirement. The migration MUST preserve this protection — the new render_preview MUST escape every theme-derived string before HTML insertion.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Refactor src/themey/preview.py IN PLACE — new render_preview API; PRESERVE html.escape protection on every theme-derived string</name>
  <files>src/themey/preview.py, tests/test_preview.py</files>
  <read_first>
    - src/themey/preview.py (entire 98-line existing file — Phase 1 shipped this with html.escape calls at lines 14, 26, 42, 43, 44; this task REPLACES the API but MUST PRESERVE the html.escape pattern. Per checker Issue 4: failing to preserve protection is a regression — the new render_preview without escape calls would silently land theme-controlled strings in HTML attribute values unescaped)
    - tests/test_preview.py (entire 126-line existing file — Phase 1 shipped 6 tests calling themey.preview.render; this task MIGRATES them. Specifically test_preview_escapes_html_in_notes at line 94 is the XSS regression guard — its assertions MUST continue to pass against the new render_preview)
    - src/themey/images/embed.py (after 02-03 — image_to_jpeg_b64_uri added; preview.py imports this for wallpaper thumbnails)
    - src/themey/ir.py (Theme.color_scheme, Theme.wallpaper contracts from 02-01)
    - src/themey/report.py (after 02-04a — preview reuses categorize_notes for the categorised notes list)
    - .planning/phases/02-colors-wallpaper-full-report/02-RESEARCH.md §6 lines 604-696 (HTML preview spec + CSS examples)
    - .planning/phases/02-colors-wallpaper-full-report/02-PATTERNS.md "src/themey/preview.py" lines 391-417
    - tests/test_embed.py (analog: data URI prefix assertion patterns)
  </read_first>
  <behavior>
    - Test 1 (HTML structure): rendered HTML contains `<html`, `<head>`, `<body>`, `<style>` tags (well-formed enough to parse)
    - Test 2 (mocked titlebar styled by ColorScheme): rendered HTML contains a div with inline style `background:` set to a string matching the ColorScheme.wm_active_background as `rgb(R,G,B)` or `#RRGGBB`
    - Test 3 (6 swatches): rendered HTML contains exactly 6 elements with class `swatch`. Use `re.findall(r'class="swatch"', html)` count == 6
    - Test 4 (each swatch has a hex label): the rendered HTML contains 6 hex codes matching `#[0-9a-fA-F]{6}`
    - Test 5 (wallpaper thumbnail data URI): when theme.wallpaper.image_path points to an on-disk image, rendered HTML contains an `<img` whose `src` attribute starts with `data:image/jpeg;base64,`
    - Test 6 (no wallpaper graceful degradation): when theme.wallpaper is None or theme.wallpaper.image_path is None, rendered HTML omits the wallpaper section without raising; the rest renders normally
    - Test 7 (activation command embedded): rendered HTML contains a `<pre>` or `<code>` block with the activation command string passed in (e.g. "plasma-apply-lookandfeel Aliens")
    - Test 8 (categorised notes lists): rendered HTML contains three `<details>` (or `<h3>`) sections — Preserved, Approximated, Skipped — each containing a `<ul>` with the categorised notes (rely on `report.categorize_notes` for routing)
    - Test 9 (data URI prefix isolated for snapshot stability per RESEARCH §9 line 815): the public function `render_preview(theme, *, ..., embed_thumbnail=True)` accepts `embed_thumbnail=False` for snapshot-test runs which substitutes the data URI with a placeholder string `"<!-- thumbnail data uri omitted for snapshot stability -->"`
    - **Test 10 (per checker Issue 4 — XSS protection on theme.display_name)**: construct a Theme with `display_name='<script>alert(1)</script>'`; render_preview output must NOT contain the raw substring `<script>alert(1)</script>` and MUST contain the escaped form `&lt;script&gt;`. This is the migrated regression guard from Phase 1's tests/test_preview.py:94.
    - **Test 11 (per checker Issue 4 — XSS protection on activation_command)**: pass `activation_command='<svg/onload=alert(1)>'`; the output must contain `&lt;svg` and must NOT contain the raw `<svg/onload=alert(1)>`.
    - **Test 12 (per checker Issue 4 — XSS protection on note bodies)**: pass `notes=["PRESERVED: <iframe src=javascript:alert(1)></iframe>"]`; the iframe payload appears escaped in the categorised-notes section, not raw.
    - **Test 13 (per checker Issue 4 — XSS protection on theme.author)**: construct a Theme with `author='<img src=x onerror=alert(1)>'`; if author appears in the rendered HTML (e.g. in a metadata footer), it appears escaped, not raw.
    - **Test 14 (per checker Issue 4 — XSS protection on swatch labels)**: swatch labels are hardcoded constants ("Window BG", etc.) so they don't need escaping per se, but VERIFY by reading the rendered HTML that the labels are present unescaped — confirms hardcoded constants are not double-escaped (no `&amp;Window BG`).
  </behavior>
  <action>
**A. REPLACE the entire content of `src/themey/preview.py`** with the new Phase 2 design (per RESEARCH §6 + PATTERNS.md lines 391-417). The current 98-line scaffold is REPLACED; do not preserve `def render(...)` — that API is fully superseded.

Per checker Issue 1: this is "MODIFY" not "CREATE" — the file already exists, this plan refactors it in place; the dependent test file (tests/test_preview.py) is migrated to the new API in the SAME plan so no commit boundary leaves the suite broken.

Per checker Issue 4: the new module MUST `import html` at the top AND wrap every theme-derived string in `html.escape(s)` before inserting it into HTML. The Phase 1 module already had this protection at lines 14, 42, 43, 44 — losing it would be a security regression.

New content:

```python
"""HTML preview file: mocked titlebar + colour swatches + wallpaper thumbnail.

Per RESEARCH §6 lines 604-696. The output is a single self-contained HTML
file (data: URIs for the thumbnail) the user can open in a browser or
email to themselves.

XSS protection (per Phase 1 design preserved through the 02-04b refactor —
the legacy preview.py at lines 14, 42, 43, 44 already did this; the new
render_preview MUST keep it or theme-controlled strings land in HTML
attribute values unescaped):
  Every theme-derived string (theme.display_name, theme.author, swatch
  labels that come from theme data, the activation_command argument,
  categorised note bodies) is wrapped in html.escape() before insertion.
  T-08-02 (XSS via theme name) — see Phase 1's 01-08-PLAN.md threat model
  and tests/test_preview.py:94 (the regression guard).

Snapshot-test stability (RESEARCH §9 line 815): the base64 data URI is NOT
snapshot-stable across Pillow versions. The render_preview function takes
an `embed_thumbnail` keyword to substitute a placeholder during snapshot
runs; the integration test asserts the data URI prefix separately.

API change history:
  - Phase 1 (01-08): shipped `render(theme, out_path) -> Path` (writes file)
  - Phase 2 (02-04b): REPLACED with `render_preview(theme, *, color_scheme_path,
    wallpaper_dir, activation_command, embed_thumbnail=True) -> str` (returns
    HTML string; caller writes). Adds 6 colour swatches + wallpaper thumbnail
    + categorised notes via report.categorize_notes.
"""
from __future__ import annotations

import html
from pathlib import Path

from PIL import Image

from themey.images.embed import image_to_jpeg_b64_uri
from themey.ir import Theme
from themey.report import categorize_notes

THUMBNAIL_PLACEHOLDER = "<!-- thumbnail data uri omitted for snapshot stability -->"


def _hex(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _swatches_html(theme: Theme) -> str:
    """Render exactly 6 colour swatches per RESEARCH §6 line 645.

    Swatch labels are hardcoded constants so they don't need escaping;
    hex codes are derived from theme.color_scheme but are guaranteed
    [#0-9a-f] safe by _hex() so they don't need escaping either.
    """
    if theme.color_scheme is None:
        return "<p>(no color scheme)</p>"
    cs = theme.color_scheme
    swatches = [
        ("Window BG", cs.background_normal),
        ("Window FG", cs.foreground_normal),
        ("Accent", cs.decoration_focus),
        ("WM active BG", cs.wm_active_background),
        ("WM active FG", cs.wm_active_foreground),
        ("WM inactive BG", cs.wm_inactive_background),
    ]
    parts = []
    for label, rgb in swatches:
        hex_code = _hex(rgb)
        # Labels are hardcoded constants — escape defensively anyway in case the
        # constants are ever made theme-derived in the future.
        label_safe = html.escape(label)
        parts.append(
            f'<div class="swatch" style="background:{hex_code}" title="{label_safe}">'
            f'<span>{label_safe}</span><code>{hex_code}</code>'
            "</div>"
        )
    return '<div class="swatches">' + "".join(parts) + "</div>"


def _wallpaper_html(theme: Theme, *, embed_thumbnail: bool) -> str:
    """Render the wallpaper section. Empty string if no wallpaper or no image."""
    if theme.wallpaper is None or theme.wallpaper.image_path is None:
        return ""
    if not embed_thumbnail:
        # Placeholder for snapshot stability — string is a constant, no escape needed
        return (
            f'<h2>Wallpaper</h2><img class="wallpaper-thumb" '
            f'src="{THUMBNAIL_PLACEHOLDER}" alt="Wallpaper preview" />'
        )
    if not theme.wallpaper.image_path.is_file():
        return ""
    with Image.open(theme.wallpaper.image_path) as img:
        thumb = img.copy()
        thumb.thumbnail((320, 240), Image.Resampling.LANCZOS)
        data_uri = image_to_jpeg_b64_uri(thumb, quality=80)
    # data_uri is base64 — guaranteed safe characters. No escape needed.
    return (
        '<h2>Wallpaper</h2>'
        f'<img class="wallpaper-thumb" src="{data_uri}" alt="Wallpaper preview" />'
    )


def _notes_html(theme: Theme) -> str:
    """Render the three categorised notes sections per RESEARCH §6 lines 681-694.

    XSS protection: each note body is wrapped in html.escape() before
    insertion into the <li> element. Note bodies originate from theme analysis
    code and may contain user-supplied substrings (theme name, file paths) —
    must be treated as untrusted.
    """
    sections = categorize_notes(theme.notes)
    parts = []
    for label, key, default_open in (
        ("Preserved", "preserved", True),
        ("Approximated", "approximated", True),
        ("Skipped", "skipped", False),
    ):
        items = sections[key]
        open_attr = " open" if default_open else ""
        # Per checker Issue 4: escape every note body — they may contain user-supplied content
        body = (
            "".join(f"<li>{html.escape(item)}</li>" for item in items)
            or "<li>(none)</li>"
        )
        parts.append(
            f'<details{open_attr}><summary>{html.escape(label)} ({len(items)} entries)</summary>'
            f'<ul>{body}</ul></details>'
        )
    return "".join(parts)


def _titlebar_html(theme: Theme) -> str:
    """Mocked titlebar div using ColorScheme [WM] colours.

    XSS protection: theme.display_name is wrapped in html.escape() before
    insertion into the div text content (Phase 1 line 42 equivalent).
    """
    if theme.color_scheme is None:
        return '<div class="titlebar">no color scheme</div>'
    cs = theme.color_scheme
    bg = _hex(cs.wm_active_background)
    fg = _hex(cs.wm_active_foreground)
    name_safe = html.escape(theme.display_name)
    return (
        f'<div class="titlebar" style="background:{bg}; color:{fg}">'
        f'{name_safe} &mdash; mocked window titlebar'
        '</div>'
    )


def render_preview(
    theme: Theme,
    *,
    color_scheme_path: Path | None,
    wallpaper_dir: Path | None,
    activation_command: str,
    embed_thumbnail: bool = True,
) -> str:
    """Render the full HTML preview document.

    Args:
        theme: the converted Theme.
        color_scheme_path: path to the installed .colors file (shown in body).
        wallpaper_dir: path to the installed wallpaper package dir.
        activation_command: shell command the user runs to apply the theme
                            (e.g. "plasma-apply-lookandfeel Aliens"). This
                            string is wrapped in html.escape() before insertion
                            (per checker Issue 4 — caller may pass partially
                            user-controlled content).
        embed_thumbnail: if False, replace the wallpaper data URI with the
                         placeholder constant — for snapshot-test stability
                         (RESEARCH §9 line 815).

    Returns:
        Complete HTML5 document as a string. Caller writes it to
        ~/.local/share/themey/previews/<name>.html.
    """
    css = (
        "body { font-family: sans-serif; max-width: 720px; margin: 2em auto; }"
        ".titlebar { padding: 8px 12px; border-radius: 4px 4px 0 0; }"
        ".swatches { display: flex; flex-wrap: wrap; gap: 6px; margin: 1em 0; }"
        ".swatch { width: 90px; height: 70px; display: flex; flex-direction: column;"
        " justify-content: flex-end; padding: 4px; border-radius: 4px;"
        " font-size: 11px; color: white; text-shadow: 0 1px 2px black; }"
        ".swatch code { background: rgba(0,0,0,0.4); padding: 1px 3px; }"
        ".wallpaper-thumb { max-width: 320px; max-height: 240px;"
        " border: 1px solid #ccc; border-radius: 4px; display: block; margin: 1em 0; }"
        "pre { background: #f4f4f4; padding: 8px; border-radius: 4px; overflow-x: auto; }"
    )
    # Per checker Issue 4: escape every theme-derived string before insertion
    name_safe = html.escape(theme.display_name)
    activation_safe = html.escape(activation_command)
    author_safe = html.escape(theme.author or "")
    return (
        "<!DOCTYPE html>"
        '<html lang="en">'
        f'<head><meta charset="utf-8"><title>themey: {name_safe}</title>'
        f"<style>{css}</style></head>"
        "<body>"
        f"<h1>themey: {name_safe}</h1>"
        f"{_titlebar_html(theme)}"
        "<h2>Color scheme</h2>"
        f"{_swatches_html(theme)}"
        f"{_wallpaper_html(theme, embed_thumbnail=embed_thumbnail)}"
        "<h2>Activate</h2>"
        f"<pre>{activation_safe}</pre>"
        "<h2>Conversion notes</h2>"
        f"{_notes_html(theme)}"
        + (f'<p class="meta">Author: {author_safe}</p>' if author_safe else "")
        + "</body></html>"
    )
```

**B. MIGRATE `tests/test_preview.py`** to the new API:
1. Update imports: replace `from themey.preview import render` with `from themey.preview import render_preview`. Add `import re` for the swatch-count assertion.
2. Convert each test from "render(theme, out_path); read out_path" to "html = render_preview(theme, color_scheme_path=..., wallpaper_dir=..., activation_command='...')". The legacy `_make_theme` factory at lines 9-58 is fine to reuse — it still produces a Theme without color_scheme/wallpaper (those default to None per 02-01). Add a new `_make_theme_with_color_scheme()` factory variant for tests that need swatches.
3. Adapt `test_preview_writes_valid_html` → assert `<html`, `<head>`, `<body>` substrings appear in the returned string (no file write).
4. Adapt `test_preview_includes_theme_name` → assert escaped display_name appears in the returned string.
5. Adapt `test_preview_includes_activation_instructions` → pass `activation_command="plasma-apply-lookandfeel Aliens"`; assert "plasma-apply-lookandfeel Aliens" appears in the output (escaped if necessary — the literal string has no HTML-special characters so it appears verbatim).
6. **KEEP `test_preview_escapes_html_in_notes` (the XSS regression guard) — adapt to the new API**. Construct a Theme with `notes=["<script>alert(1)</script>"]`. The legacy assertions:
   - `assert "<script>alert(1)</script>" not in text` — STILL PASSES (per checker Issue 4: html.escape is preserved in render_preview)
   - `assert "&lt;script&gt;" in text` — STILL PASSES
7. DROP `test_preview_includes_qdbus_reload_command` — the legacy preview hardcoded the qdbus reload command; the new render_preview takes activation_command as a parameter and the caller decides what to put in the `<pre>` block. The test no longer applies; if qdbus support is desired, build_theme.py or the CLI should construct the activation_command string explicitly.
8. ADAPT `test_preview_includes_notes_count` → adapt to the new format which uses `<details><summary>X (N entries)</summary>`. Assert that for `notes=["a","b","c"]`, the substring `(3 entries)` (or per-section counts that sum to 3) appears.
9. ADD new tests 1-14 from the behavior section — particularly tests 10-14 (XSS protection on display_name, activation_command, notes, author, swatch labels) which are the explicit regression guards for checker Issue 4.

For Test 9 (snapshot stability), call `render_preview(..., embed_thumbnail=False)` and snapshot the result; the placeholder string makes the snapshot Pillow-version-independent.
  </action>
  <verify>
    <automated>cd /home/cstory/src/themey &amp;&amp; uv run pytest tests/test_preview.py -x -v &amp;&amp; uv run pytest tests/ -x &amp;&amp; uv run ruff check src/themey/preview.py tests/test_preview.py &amp;&amp; uv run pyright src/themey/preview.py tests/test_preview.py</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "^def render_preview" src/themey/preview.py` returns 1
    - `grep -c "^def render" src/themey/preview.py` returns 1 (only render_preview, the regex matches it; legacy `def render(...)` API is removed — verify there is exactly ONE `^def render` match and `grep -c "^def render(" src/themey/preview.py` returns 0)
    - **Per checker Issue 4 — XSS protection acceptance gates**:
      - `grep -c "import html" src/themey/preview.py` returns 1 (stdlib html module imported at module top)
      - `grep -c "html.escape" src/themey/preview.py` returns at least 4 (per checker Issue 4 fix: at least 4 escape calls — display_name in titlebar, display_name in document title/h1, activation_command in pre block, note bodies in li elements; author in metadata footer if present)
    - `grep -c "image_to_jpeg_b64_uri" src/themey/preview.py` returns 1 (uses 02-03's helper)
    - `grep -c "from themey.report import categorize_notes" src/themey/preview.py` returns 1
    - `grep -c "class=\"swatch\"" src/themey/preview.py` returns 1 (single source emitting swatch divs)
    - `grep -c "wallpaper-thumb" src/themey/preview.py` returns at least 1
    - `grep -c "Image.Resampling.LANCZOS" src/themey/preview.py` returns 1 (photographic resample)
    - `grep -c "Image.Resampling.NEAREST" src/themey/preview.py` returns 0 (NEAREST is reserved for borders, NOT preview thumbnails — CLAUDE.md TL;DR rule enforced)
    - `uv run pytest tests/test_preview.py` reports >= 10 tests passed (originals adapted + tests 10-14 for XSS protection)
    - `uv run pytest tests/test_preview.py::test_preview_escapes_html_in_notes` passes (the legacy XSS regression guard adapted to render_preview — proves checker Issue 4 fix works)
    - `uv run pytest tests/test_preview.py -k "xss or escape"` includes at least 4 passing tests (per checker Issue 4: explicit XSS coverage on display_name, activation_command, notes, author)
    - `uv run pytest tests/ -x` passes ALL tests (no regression)
    - `uv run ruff check src/themey/preview.py tests/test_preview.py` exits 0
    - `uv run pyright src/themey/preview.py tests/test_preview.py` reports 0 errors
  </acceptance_criteria>
  <done>
    `preview.py` is REFACTORED IN PLACE — Phase 1's `render(theme, out_path) -> Path` is REPLACED by `render_preview(theme, *, color_scheme_path, wallpaper_dir, activation_command, embed_thumbnail=True) -> str`. Per checker Issue 4: `import html` is preserved, every theme-derived string (display_name, activation_command, note bodies, author, swatch labels) is wrapped in `html.escape()` before HTML insertion — preserving the XSS protection that Phase 1's preview.py already had at lines 14, 42, 43, 44. Returns a complete HTML5 document with mocked titlebar, exactly 6 colour swatches, base64-embedded wallpaper thumbnail (LANCZOS resample), activation command pre block, and three categorised notes sections. `embed_thumbnail=False` substitutes a placeholder for snapshot-test stability. The legacy XSS regression guard from tests/test_preview.py:94 is migrated and still passes.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Aliens.etheme end-to-end test using pinned parse_tree signature (per checker W1)</name>
  <files>tests/test_aliens_phase2_e2e.py</files>
  <read_first>
    - tests/test_archive.py lines 39-55 (analog: existing Aliens canary that uses the extract() context manager)
    - tests/test_build_theme.py lines 243-339 (analog: existing aliens_asset_root fixture that calls parse_tree; THIS IS THE PINNED PATTERN — copy verbatim, no try/except wrapper per checker Warning W1)
    - tests/conftest.py (analog: fake_home fixture)
    - src/themey/etheme/parse.py lines 40-73 (PIN the signatures: `parse_file(path) -> list[AstNode]` and `parse_tree(asset_root, entry_files=None) -> list[AstNode]` — the test uses `parse_tree`)
    - src/themey/etheme/archive.py (verify extract() yields RawTheme(asset_root=...))
    - src/themey/analyze/build_theme.py (after 02-04a — the orchestrator that runs the full analyze pipeline including select_wallpaper + build_color_scheme)
    - src/themey/generate/colors.py (02-03 — write_colors_ini)
    - src/themey/generate/wallpaper.py (02-03 — write_wallpaper_package)
    - src/themey/report.py (after 02-04a — render_report)
    - src/themey/preview.py (after Task 1 of this plan — render_preview)
    - src/themey/paths.py (after 02-04a — color_schemes(), wallpapers())
    - .planning/phases/02-colors-wallpaper-full-report/02-PATTERNS.md "tests/integration/test_aliens_e2e.py" lines 477-495
  </read_first>
  <behavior>
    - Test 1 (orchestration scaffold): the test extracts Aliens.etheme via `extract()`, calls `parse_tree(raw.asset_root, entry_files=[...])` with the explicit list including desktops.cfg + init.cfg (NO try/except — the signature is pinned per checker Warning W1), calls build_theme to get a Theme; assertions on the resulting Theme object (color_scheme is not None, wallpaper is not None, len(notes) > 0)
    - Test 2 (.colors install path): write_colors_ini(theme, paths.color_schemes() / f"{theme.name}.colors") creates the file under the fake_home XDG dir; file is non-empty; parses with RawConfigParser; has [General], [WM], [Colors:Window] sections
    - Test 3 (wallpaper install path): write_wallpaper_package(theme, paths.wallpapers() / theme.name) creates fake_home/.local/share/wallpapers/Aliens/metadata.json AND fake_home/.local/share/wallpapers/Aliens/contents/images/<W>x<H>.<ext>
    - Test 4 (KPlugin.Id matches dir): json.load(metadata.json)["KPlugin"]["Id"] == "Aliens" exactly (Pitfall D enforced end-to-end)
    - Test 5 (image filename regex): the image file in contents/images/ matches `^\d+x\d+\.(jpg|png)$`
    - Test 6 (report.txt has all three sections): render_report(theme, [color_scheme_path, wallpaper_dir]) → text contains all three section header strings
    - Test 7 (preview.html has swatches + thumbnail): render_preview(theme, ..., embed_thumbnail=True) → HTML contains 6 elements with class="swatch" AND contains "data:image/jpeg;base64,"
    - Test 8 (idempotent re-run): running write_colors_ini and write_wallpaper_package a SECOND time produces the same file content (byte-equal for metadata.json; byte-equal for image)
    - Test 9 (no symlinks): `find {wallpaper_dir} -type l` returns 0 entries (the install must be symlink-free per Phase 4 LnF requirement, also a sanity for Phase 2)
  </behavior>
  <action>
**Create `tests/test_aliens_phase2_e2e.py`** using the PINNED parser signature per checker Warning W1:

```python
"""End-to-end Aliens.etheme conversion through the full Phase 2 pipeline.

Pipeline:
    Aliens.etheme
      -> extract() yields RawTheme(asset_root)
      -> parse_tree(asset_root, entry_files=[...]) -> list[AstNode]
         (PINNED signature per src/themey/etheme/parse.py:47-73 and
          checker Warning W1 — NO try/except wrapper; the signature is stable)
      -> build_theme(asset_root, ast_nodes) -> Theme (with color_scheme, wallpaper)
      -> write_colors_ini(theme, paths.color_schemes() / f"{theme.name}.colors")
      -> write_wallpaper_package(theme, paths.wallpapers() / theme.name)
      -> render_report(theme, output_paths) -> .txt
      -> render_preview(theme, ...) -> .html

The test uses fake_home so all install paths route into tmp_path.
"""
from __future__ import annotations

import configparser
import json
import re
from pathlib import Path

import pytest

from themey import paths
from themey.analyze.build_theme import build_theme
from themey.etheme.archive import extract
from themey.etheme.parse import parse_tree  # PINNED entry point per checker W1
from themey.generate.colors import write_colors_ini
from themey.generate.wallpaper import write_wallpaper_package
from themey.preview import render_preview
from themey.report import render_report

FIXTURES = Path(__file__).parent / "fixtures"


def test_aliens_phase2_end_to_end(fake_home: Path) -> None:
    aliens_path = FIXTURES / "Aliens.etheme"
    assert aliens_path.is_file(), "Aliens.etheme fixture must be committed"

    with extract(aliens_path) as raw:
        # Per checker Warning W1: PINNED signature parse_tree(asset_root, entry_files=...).
        # NO try/except TypeError wrapper — the signature is stable per
        # src/themey/etheme/parse.py:47-73. Default entry_files extends with
        # desktops.cfg (where __DESKTOP blocks live) and init.cfg (the theme
        # entry point that may #include other cfg files).
        ast_nodes = parse_tree(
            raw.asset_root,
            entry_files=[
                "borders.cfg",
                "imageclasses.cfg",
                "textclasses.cfg",
                "desktops.cfg",
                "init.cfg",
            ],
        )
        theme = build_theme(
            asset_root=raw.asset_root,
            ast_nodes=ast_nodes,
            name="Aliens",
            display_name="Aliens",
            author="Don",
            scale=2,
        )

        # Test 1: Theme has color_scheme + wallpaper populated
        assert theme.color_scheme is not None, "Phase 2 must populate color_scheme"
        assert theme.wallpaper is not None, "Aliens has 4 desktops; wallpaper must be picked"

        # Test 2: .colors install
        colors_dir = paths.color_schemes()
        colors_dir.mkdir(parents=True, exist_ok=True)
        colors_path = colors_dir / f"{theme.name}.colors"
        write_colors_ini(theme, colors_path)
        assert colors_path.is_file()
        cp = configparser.RawConfigParser(strict=False)
        cp.optionxform = str  # type: ignore[method-assign]
        cp.read(colors_path)
        for required in ("General", "WM", "Colors:Window", "Colors:Button",
                         "Colors:View", "Colors:Selection", "Colors:Tooltip"):
            assert required in cp.sections(), f"missing [{required}] in .colors"

        # Test 3, 4, 5: wallpaper package install
        wp_root = paths.wallpapers()
        wp_root.mkdir(parents=True, exist_ok=True)
        wp_dir = wp_root / theme.name
        write_wallpaper_package(theme, wp_dir)
        meta = wp_dir / "metadata.json"
        assert meta.is_file()
        meta_data = json.loads(meta.read_text(encoding="utf-8"))
        assert meta_data["KPlugin"]["Id"] == "Aliens", "Pitfall D: Id must equal dir name"
        images_dir = wp_dir / "contents" / "images"
        assert images_dir.is_dir()
        image_files = list(images_dir.iterdir())
        assert len(image_files) == 1, f"expected one image file, got {image_files}"
        assert re.match(r"^\d+x\d+\.(jpg|png)$", image_files[0].name), \
            f"image filename must match WxH.ext (lowercase x): {image_files[0].name}"

        # Test 6: report.txt three sections
        report_text = render_report(theme, [colors_path, wp_dir])
        for header in ("PRESERVED (mapped 1:1 from E16 source)",
                       "APPROXIMATED (lossy mapping; reason explained)",
                       "SKIPPED (no Plasma equivalent or out of scope for v1)"):
            assert header in report_text, f"missing section header: {header}"

        # Test 7: preview HTML with swatches + base64 thumbnail
        html = render_preview(
            theme,
            color_scheme_path=colors_path,
            wallpaper_dir=wp_dir,
            activation_command="plasma-apply-lookandfeel Aliens",
            embed_thumbnail=True,
        )
        assert len(re.findall(r'class="swatch"', html)) == 6, "must have 6 swatches"
        assert "data:image/jpeg;base64," in html, "wallpaper thumbnail must be embedded"

        # Test 8: idempotent re-run (write again; check byte-equal for metadata.json)
        meta_first = meta.read_bytes()
        write_wallpaper_package(theme, wp_dir)
        assert meta.read_bytes() == meta_first, "second run must produce identical metadata.json"

        # Test 9: no symlinks anywhere in wallpaper tree
        symlinks = [p for p in wp_dir.rglob("*") if p.is_symlink()]
        assert symlinks == [], f"wallpaper package must be symlink-free: {symlinks}"
```

Note: this test uses the existing `fake_home` fixture from `tests/conftest.py`. The `extract()` context manager yields a `RawTheme` with `asset_root` per `tests/test_archive.py:42-52`. Per checker Warning W1: the parser signature is PINNED — `parse_tree(raw.asset_root, entry_files=[...])` — no try/except wrapper. If the parser signature ever changes, this test will fail loudly with a clear error rather than silently masking the bug.
  </action>
  <verify>
    <automated>cd /home/cstory/src/themey &amp;&amp; uv run pytest tests/test_aliens_phase2_e2e.py -x -v &amp;&amp; uv run pytest tests/ --ignore=tests/test_aliens_phase2_e2e.py -x -q --tb=no &amp;&amp; uv run ruff check tests/test_aliens_phase2_e2e.py &amp;&amp; uv run pyright tests/test_aliens_phase2_e2e.py</automated>
  </verify>
  <acceptance_criteria>
    - `test -f tests/test_aliens_phase2_e2e.py` succeeds
    - `grep -c "extract(aliens_path)" tests/test_aliens_phase2_e2e.py` returns 1 (uses Phase 1 archive primitive)
    - `grep -c "parse_tree(" tests/test_aliens_phase2_e2e.py` returns at least 1 (per checker W1: pinned signature, NOT a fallback wrapper)
    - `grep -c "try:" tests/test_aliens_phase2_e2e.py` returns 0 (per checker W1: NO defensive try/except around parse — the signature is stable)
    - `grep -c "TypeError" tests/test_aliens_phase2_e2e.py` returns 0 (per checker W1: no signature-mismatch fallback)
    - `grep -c "build_theme(" tests/test_aliens_phase2_e2e.py` returns 1
    - `grep -c "write_colors_ini" tests/test_aliens_phase2_e2e.py` returns 1
    - `grep -c "write_wallpaper_package" tests/test_aliens_phase2_e2e.py` returns at least 1
    - `grep -c "render_report" tests/test_aliens_phase2_e2e.py` returns 1
    - `grep -c "render_preview" tests/test_aliens_phase2_e2e.py` returns 1
    - `grep -c "fake_home" tests/test_aliens_phase2_e2e.py` returns at least 1 (uses XDG-routing fixture)
    - **Per checker Warning W5** (split verify command into focused E2E run + a fast `--tb=no -q` sweep of the rest): the verify block executes `uv run pytest tests/test_aliens_phase2_e2e.py -x -v` first (focused E2E with verbose output for the iteration loop), then `uv run pytest tests/ --ignore=tests/test_aliens_phase2_e2e.py -x -q --tb=no` to confirm no regression in the rest of the suite without re-running the slow E2E test. Both commands must exit 0.
    - `uv run ruff check tests/test_aliens_phase2_e2e.py` exits 0
    - `uv run pyright tests/test_aliens_phase2_e2e.py` reports 0 errors
  </acceptance_criteria>
  <done>
    `tests/test_aliens_phase2_e2e.py` extracts the Aliens.etheme fixture, calls the PINNED `parse_tree(asset_root, entry_files=[...])` (per checker W1 — no try/except wrapper), runs the full analyze + generate + report + preview pipeline against a fake_home XDG tree, and asserts every Phase 2 success criterion (.colors well-formed, wallpaper package well-formed with KPlugin.Id == dir name and lowercase-x dimension filename, report.txt has three section headers, preview HTML has 6 swatches and base64 thumbnail, idempotent re-run, no symlinks). The verify command per checker W5 splits into focused E2E + fast suite-sweep to keep iteration loops responsive.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Manual visual gate on Plasma 6.6.4 — confirm Aliens palette + wallpaper install and apply</name>
  <what-built>
    Tasks 1-2 plus the upstream Phase 2 plans produced the full stack:
    - `analyze/build_theme.py` populates Theme.color_scheme + Theme.wallpaper (via 02-04a)
    - `generate/colors.py` writes a Plasma 6 .colors file (via 02-03)
    - `generate/wallpaper.py` writes a Plasma 6 Wallpaper/Images package (via 02-03)
    - `report.py` renders three-section text report (via 02-04a)
    - `preview.py` renders HTML with swatches + thumbnail + html.escape protection (via Task 1 of this plan)
    - `tests/test_aliens_phase2_e2e.py` proves the pipeline works against a fake XDG tree (via Task 2)

    What this checkpoint adds: visual confirmation on the user's REAL Plasma 6.6.4 desktop that the heuristics produce coherent output — the snapshot tests can prove byte-stability but only the human can decide "this feels like Aliens".
  </what-built>
  <how-to-verify>
**STEP 1 — Run the conversion writing to the real ~/.local/share/...**

Since Phase 1's CLI (Plan 01-09) has not landed yet, run the equivalent inline. The command uses the PINNED `parse_tree` signature per checker W1:

```bash
cd /home/cstory/src/themey
uv run python -c "
from pathlib import Path
from themey import paths
from themey.analyze.build_theme import build_theme
from themey.etheme.archive import extract
from themey.etheme.parse import parse_tree  # pinned per checker W1
from themey.generate.colors import write_colors_ini
from themey.generate.wallpaper import write_wallpaper_package
from themey.report import render_report
from themey.preview import render_preview

aliens = Path('tests/fixtures/Aliens.etheme')
with extract(aliens) as raw:
    nodes = parse_tree(
        raw.asset_root,
        entry_files=['borders.cfg', 'imageclasses.cfg', 'textclasses.cfg', 'desktops.cfg', 'init.cfg'],
    )
    theme = build_theme(asset_root=raw.asset_root, ast_nodes=nodes, name='Aliens', display_name='Aliens', author='Don', scale=2)

    cs_dir = paths.color_schemes(); cs_dir.mkdir(parents=True, exist_ok=True)
    cs_path = cs_dir / 'Aliens.colors'
    write_colors_ini(theme, cs_path)
    print(f'wrote: {cs_path}')

    wp_root = paths.wallpapers(); wp_root.mkdir(parents=True, exist_ok=True)
    wp_dir = wp_root / 'Aliens'
    write_wallpaper_package(theme, wp_dir)
    print(f'wrote: {wp_dir}')

    prev_dir = paths.themey_previews(); prev_dir.mkdir(parents=True, exist_ok=True)
    (prev_dir / 'Aliens.txt').write_text(render_report(theme, [cs_path, wp_dir]), encoding='utf-8')
    (prev_dir / 'Aliens.html').write_text(
        render_preview(theme, color_scheme_path=cs_path, wallpaper_dir=wp_dir, activation_command='plasma-apply-lookandfeel Aliens'),
        encoding='utf-8'
    )
    print(f'wrote: {prev_dir}/Aliens.html')
"
```

Expected stdout: 4 "wrote: ..." lines pointing at real paths under ~/.local/share/.

**STEP 2 — Verify .colors in System Settings**

1. Open System Settings → Colors (or run `systemsettings kcm_colors` from a terminal)
2. Scroll the colour scheme list — Aliens should appear (the picker may need to be closed and reopened if Plasma cached the directory)
3. Click Aliens — does the desktop adopt new colours? In particular:
   - Window backgrounds change
   - Selection highlight changes to a colour from the Aliens palette
   - The list itself shows a preview thumbnail

Expected: scheme appears, applies, and the colours visibly come from the Aliens theme (greens, oranges, dark backgrounds — Aliens is a dark sci-fi theme).

**STEP 3 — Verify wallpaper in Configure Desktop**

1. Right-click an empty area of the desktop → Configure Desktop and Wallpaper
2. In the Wallpaper picker, scroll for "Aliens" — should appear with a thumbnail
3. Click Aliens → apply
4. Close the dialog and observe the desktop background

Expected: wallpaper picker shows Aliens; selecting it applies an Alien-themed image (one of `artwork/backgrounds/Alien97.jpg`, `artwork/backgrounds/giger045.gif` converted to PNG, etc.).

**STEP 4 — Verify report.txt and preview.html**

```bash
cat ~/.local/share/themey/previews/Aliens.txt
xdg-open ~/.local/share/themey/previews/Aliens.html
```

Expected:
- report.txt has all three sections populated (PRESERVED, APPROXIMATED, SKIPPED)
- preview.html opens in browser; shows 6 colour swatches; shows a wallpaper thumbnail; lists three categorised note sections
- preview.html does NOT execute any javascript even if a theme name contained `<script>` (per checker Issue 4 fix — html.escape protection)

**STEP 5 — Cleanup (so the real install does not pollute your daily desktop)**

If the colours / wallpaper applied above and you want to revert:

```bash
# Switch System Settings → Colors → BreezeDark (or your usual)
# Switch desktop wallpaper back to your usual
# Remove the converted artefacts:
rm -f ~/.local/share/color-schemes/Aliens.colors
rm -rf ~/.local/share/wallpapers/Aliens
rm -f ~/.local/share/themey/previews/Aliens.{txt,html}
```
  </how-to-verify>
  <resume-signal>
Reply with one of:
- **"approved"** — all 5 verification steps passed; Phase 2 is shippable
- **"colors look wrong: <description>"** — palette doesn't feel like Aliens; gap closure needed (will trigger /gsd-plan-phase --gaps)
- **"wallpaper picker is empty"** — KPlugin.Id mismatch or kpackagetool6 rejected the package; debug needed
- **"report sections empty"** — categorize_notes routing bug; debug needed
- **"preview missing thumbnail"** — image_to_jpeg_b64_uri failed; debug needed
- **"other: <description>"** — describe what was off; planner will decide gap closure vs revision
  </resume-signal>
  <files>~/.local/share/color-schemes/Aliens.colors, ~/.local/share/wallpapers/Aliens/, ~/.local/share/themey/previews/Aliens.{txt,html}</files>
  <action>Human-only checkpoint. Implementation steps are described in &lt;how-to-verify&gt;. The agent does NOT modify code in this task — it pauses, prints the verification instructions to the user, and waits for the user's resume signal before progressing to the SUMMARY step.</action>
  <verify>Manual visual confirmation per &lt;how-to-verify&gt; STEP 1-5. No automated command applies.</verify>
  <done>User replies with "approved" (or one of the gap-trigger signals listed in &lt;resume-signal&gt;). On "approved", Phase 2 is shippable; the SUMMARY can be written.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| Aliens.etheme tarball | Phase 1's safe_extract has already validated this; the Phase 2 pipeline trusts asset_root contents |
| ~/.local/share/... write surface | This plan WRITES to the user's real XDG dirs (during the manual checkpoint only — automated tests use fake_home). Any leaked write outside the named subdirs would pollute the user's daily Plasma config |
| theme-derived strings → HTML | preview.py inserts theme.display_name, theme.author, activation_command, note bodies into HTML attributes/text — must be html.escape()'d before insertion (per checker Issue 4 — preserves Phase 1 protection) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-02-04b-01 | Tampering | render_preview emits user-controlled strings (theme.display_name, theme.author, theme.notes, activation_command) without escaping → HTML injection / XSS in preview.html | mitigate | Per checker Issue 4: preview.py imports `html` stdlib at module top; every theme-derived string is wrapped in `html.escape(s)` before insertion. Tests 10-14 in Task 1 are explicit XSS regression guards (display_name, activation_command, note bodies, author, swatch labels). Phase 1 already had this protection at lines 14, 42, 43, 44 — this plan PRESERVES it during the API refactor. |
| T-02-04b-02 | Tampering | Aliens E2E test wraps parse() in try/except TypeError to "survive whatever signature parse() actually has" — defensive try/except masks signature drift bugs | mitigate | Per checker Warning W1: the parser signature is PINNED to `parse_tree(asset_root, entry_files=None)` (per src/themey/etheme/parse.py:47-73). Task 2 acceptance criterion `grep -c "try:" tests/test_aliens_phase2_e2e.py` returns 0 enforces no defensive wrappers. Signature drift will cause a loud test failure, not a silent miscategorization. |
| T-02-04b-03 | Tampering | The manual checkpoint writes to real ~/.local/share/... — risk of polluting daily desktop | accept | Documented cleanup steps in Step 5 of how-to-verify; user can revert by deleting the named files. Per CLAUDE.md output discipline, "every install path is under ~/.local/share/... so a conversion is fully reversible by deleting the named directories." |
| T-02-04b-04 | Information disclosure | report.txt / preview.html contain the user's HOME path (theme.asset_root is a tempdir under tmpdir or under home) | accept | These files live in the user's own XDG directory; no exfiltration vector. The checkpoint cleanup removes them. |
| T-02-04b-05 | Denial of service | Aliens E2E test loads a 2.4 MB tarball + parses 11 cfg files + opens multiple PNGs in PIL — could be slow | accept | Phase 1 archive caps (32 MB total / 8 MB per file / 500 entries) plus Image.MAX_IMAGE_PIXELS = 100M from 02-02 already bound the worst case. The test runs in <30s on chris's machine. The verify command per checker W5 splits the focused E2E from the suite sweep so the iteration loop stays fast. |
| T-02-04b-06 | Repudiation | A Phase 2 conversion that "looks wrong" needs to be debuggable from report.txt | mitigate | Every notes.append is now categorized; the SKIPPED section explains every dropped feature; the APPROXIMATED section documents lossy mappings (with iclass/state context per checker W7 in 02-02); the user can read this story via Step 4 of the checkpoint. |
</threat_model>

<verification>
- `uv run pytest tests/ -x` passes — all of: existing Phase 1 tests + new IR tests (02-01) + states migration test (02-01) + analyze/background and analyze/colors tests (02-02) + generate/colors and generate/wallpaper tests (02-03) + build_theme integration tests (02-04a) + report tests (02-04a) + preview tests (this plan) + Aliens E2E test (this plan)
- `uv run ruff check src/ tests/` passes across the full Phase 2 surface
- `uv run pyright src/ tests/` reports 0 errors
- The Aliens E2E test produces real-world artifacts in fake_home XDG tree that match all four success criteria in the phase goal
- The manual visual gate (Task 3) passes on chris's Plasma 6.6.4 system
- HTML preview escapes user-controllable strings (per checker Issue 4 — no XSS via theme.display_name, theme.author, activation_command, or note bodies)
- The Aliens E2E test does NOT use try/except around parse_tree (per checker W1 — pinned signature)
- The verify command splits focused E2E + fast suite-sweep (per checker W5 — keeps iteration responsive)
</verification>

<success_criteria>
**Phase 2 success criteria from ROADMAP — every one verified:**

1. `~/.local/share/color-schemes/Aliens.colors` appears, selectable in System Settings → Colors, applies a sampled palette → **Task 3 STEP 2**
2. `~/.local/share/wallpapers/Aliens/` populated with `metadata.json` and `contents/images/`, selectable in Configure Desktop → Wallpaper → **Task 3 STEP 3**
3. HTML preview shows color swatches and a wallpaper thumbnail next to mocked titlebar → **Task 3 STEP 4 (preview.html)**
4. `report.txt` has three populated sections (Preserved / Approximated / Skipped) → **Task 3 STEP 4 (report.txt)**

**Plus internal correctness:**
- All file output is symlink-free (Task 2 Test 9 + Phase 4 LnF prep)
- Idempotent re-run produces byte-equal artefacts (Task 2 Test 8)
- All Wave 1+2+3a tests still pass (no regression to ir/states/background/colors/generate.colors/generate.wallpaper/embed/build_theme/paths/report)
- preview.py preserves the html.escape XSS protection Phase 1 already had (per checker Issue 4)
- The Aliens E2E test uses the pinned parse_tree signature (per checker Warning W1)
</success_criteria>

<output>
After completion, create `.planning/phases/02-colors-wallpaper-full-report/02-04b-SUMMARY.md` documenting:
- Confirmation that the manual visual gate (Task 3) passed; user's reply ("approved" or specifics)
- Confirmation that preview.py preserves the html.escape protection (per checker Issue 4)
- Confirmation that the Aliens E2E test uses the pinned parse_tree signature with no try/except (per checker W1)
- The Aliens conversion's resolved palette (paste a few hex values for posterity)
- The Aliens wallpaper's chosen file (e.g. "artwork/backgrounds/Alien97.jpg") and the count of skipped_alternatives
- The full categorization of theme.notes by section (counts: N preserved, M approximated, K skipped)
- Whether kpackagetool6 reported success on the real Aliens wallpaper package
- Total Phase 2 test count growth (was X tests at end of Phase 1; now Y after Phase 2)
- Any deviation from RESEARCH §2 colour-extraction heuristic that resulted from the visual gate
- Carry-forward issues for Phase 3 (e.g. "Aliens has cursors but xcursorgen integration is Phase 3")
</output>
</content>
</invoke>