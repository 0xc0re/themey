"""HTML preview (PREVIEW-01).

A static HTML page with: mocked titlebar, list of dropped E16 states,
and the activation instructions. Plasma 6.6.4 supports applying an
Aurorae theme via System Settings > Window Decorations directly; the
Look-and-Feel bundle (Phase 4) ships the plasma-apply-lookandfeel
one-liner.

All theme-derived strings are html.escape()'d for XSS prevention
(see T-08-02 in 01-08-PLAN.md threat model).
"""
from __future__ import annotations

import html
from pathlib import Path

from .ir import Theme


def render(theme: Theme, out_path: Path) -> Path:
    """Write an HTML preview of *theme* to *out_path*.

    Returns *out_path* so callers can chain.
    """
    notes_html = "\n".join(
        f"  <li><code>{html.escape(n)}</code></li>"
        for n in theme.notes[:50]  # cap at 50 (T-08-04 DoS mitigation)
    )
    more_notes = ""
    if len(theme.notes) > 50:
        more_notes = (
            f"<p><em>... and {len(theme.notes) - 50} more "
            "(see report.txt for full list)</em></p>"
        )

    # Mocked titlebar styling driven by theme palette (RGB tuples, 0-255)
    ta = theme.palette.text_active
    tb_a = theme.palette.titlebar_active
    tb_active_rgb = f"{tb_a[0]},{tb_a[1]},{tb_a[2]}"
    text_active_rgb = f"{ta[0]},{ta[1]},{ta[2]}"

    name_safe = html.escape(theme.display_name)
    plugin_id_safe = html.escape(theme.name)
    skipped_safe = html.escape(
        ", ".join(theme.skipped_borders) if theme.skipped_borders else "none"
    )
    # Build the kwriteconfig6 commands as a separate string to stay under line-length limit
    kwrite_cmd = (
        "kwriteconfig6 --file kwinrc --group org.kde.kdecoration2"
        " --key library org.kde.kwin.aurorae\n"
        "kwriteconfig6 --file kwinrc --group org.kde.kdecoration2"
        f" --key theme __aurorae__svg__{plugin_id_safe}\n"
        "qdbus org.kde.KWin /KWin reconfigure"
    )

    doc = f"""<!doctype html>
<html><head>
<meta charset="utf-8">
<title>themey: {name_safe}</title>
<style>
  body {{ font: 14px sans-serif; max-width: 720px; margin: 2em auto; padding: 1em; }}
  .titlebar {{ background: rgb({tb_active_rgb}); color: rgb({text_active_rgb});
               padding: 0.5em 1em; border-radius: 4px 4px 0 0;
               font-weight: bold; }}
  .body {{ border: 1px solid #ccc; border-top: none;
           padding: 2em; min-height: 100px; background: #f9f9f9; }}
  pre {{ background: #f4f4f4; padding: 0.75em; border-radius: 4px;
         user-select: all; overflow-x: auto; }}
  ul.notes {{ font-size: 12px; color: #555; max-height: 30em; overflow-y: auto; }}
  .meta {{ color: #777; font-size: 12px; margin-top: 2em; }}
</style></head><body>
<h1>{name_safe}</h1>
<p>Converted from <code>{plugin_id_safe}.etheme</code> at scale {theme.scale}x.</p>

<div class="titlebar">{name_safe} - example window</div>
<div class="body">window contents go here</div>

<h2>Apply this theme</h2>
<p>Open <strong>System Settings &rarr; Window Decorations</strong> and select
   <strong>{name_safe}</strong> from the list, OR run from a terminal:</p>
<pre>{kwrite_cmd}</pre>

<h2>Conversion notes ({len(theme.notes)} entries)</h2>
<ul class="notes">
{notes_html}
</ul>
{more_notes}

<p class="meta">Skipped borders: {skipped_safe}.
   Color scheme, wallpaper, cursor, and Look-and-Feel bundle are deferred to later phases.
   See report.txt for full fidelity details.</p>

</body></html>
"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(doc, encoding="utf-8")
    return out_path
