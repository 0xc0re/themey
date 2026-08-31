"""QML decoration backend — true-1:1 E16 fidelity via a KWin/Decoration
KPackage loaded by the Aurorae v1 plugin (``org.kde.kwin.aurorae``).

Where the SVG backend approximates (full-width stretched title band,
buttons rebinned into the global titlebar row, BorderSize-clamped sides),
this backend replays E16's own part model: a generic QML runtime (copied
verbatim into every package) resolves every ``__BORDER_PART`` live with
E16's BorderWinpartCalc semantics from a generated ``theme.js``. Borders
are UNclamped, text-sized title plaques track the caption, and side-border
button stacks stay where the theme put them.

Single-import contract (mirrors generate/aurorae.py)::

    from themey.generate import qmldeco
    qmldeco.write(theme, package_dir)   # package_dir basename must be the
                                        # plugin id (slug.plugin_id)
"""
from __future__ import annotations

from pathlib import Path

from themey.ir import Theme

from . import package
from .theme_js import build_theme_data, render_theme_js


def write(theme: Theme, pkg_dir: Path) -> list[Path]:
    """Write the full QML decoration package under ``pkg_dir``.

    Must be called inside the ``with extract(...)`` block: part images and
    TTFs are read from ``theme.asset_root``.
    """
    pkg_dir.mkdir(parents=True, exist_ok=True)
    data, manifest, font_sources = build_theme_data(theme)

    files: list[Path] = []
    files.append(package.write_metadata_json(theme, pkg_dir))
    files.extend(package.copy_runtime(pkg_dir))
    files.extend(package.export_images(manifest, pkg_dir, theme.scale))
    files.extend(package.copy_fonts(font_sources, pkg_dir))

    ui_dir = pkg_dir / "contents" / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    theme_js = ui_dir / "theme.js"
    theme_js.write_text(render_theme_js(data))
    files.append(theme_js)
    return files
