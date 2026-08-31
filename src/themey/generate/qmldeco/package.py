"""QML decoration KPackage assembly.

Layout (per the KWin/Decoration KPackage structure — Plastik is the
reference package):

    <pkg>/metadata.json              KPlugin Id == themey_<slug> == dir name
    <pkg>/contents/ui/               runtime (verbatim) + theme.js
    <pkg>/contents/images/*.png      raw part art, upscaled to scale_px dims
    <pkg>/contents/fonts/*.ttf       theme TTFs referenced by title parts

Invariants: images go through images/upscale.upscale_part (NEAREST by
default; hqx behind --upscale quality — see the CLAUDE.md carve-out) so
art dims always match the resolver/insets rounding; the runtime files
ship from package data via
importlib.resources so an installed wheel works identically to the src
tree; the KPlugin Id MUST equal the package directory basename or the
Aurorae plugin will not resolve ``theme=<id>``.
"""
from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

from PIL import Image

from themey.images.upscale import upscale_part
from themey.ir import Theme
from themey.slug import plugin_id

RUNTIME_FILES: tuple[str, ...] = (
    "main.qml",
    "ThemeyPart.qml",
    "ThemeyButton.qml",
    "resolver.js",
)


def write_metadata_json(theme: Theme, pkg_dir: Path) -> Path:
    meta = {
        "KPackageStructure": "KWin/Decoration",
        "KPlugin": {
            "Id": plugin_id(theme.name),
            "Name": theme.display_name,
            "Description": (
                f"E16 theme '{theme.display_name}' converted by themey "
                "(QML decoration backend)"
            ),
            "Authors": [{"Name": theme.author or "unknown"}],
            "License": "GPL",
            "Version": "1.0",
        },
    }
    out = pkg_dir / "metadata.json"
    out.write_text(json.dumps(meta, indent=4, sort_keys=True) + "\n")
    return out


def copy_runtime(pkg_dir: Path) -> list[Path]:
    ui_dir = pkg_dir / "contents" / "ui"
    ui_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    runtime_root = resources.files("themey.generate.qmldeco") / "runtime"
    for name in RUNTIME_FILES:
        target = ui_dir / name
        target.write_text((runtime_root / name).read_text(encoding="utf-8"))
        written.append(target)
    return written


def export_images(
    manifest: dict[str, Path],
    pkg_dir: Path,
    scale: float,
    upscale: str = "nearest",
) -> list[Path]:
    """Export part art as raw PNGs upscaled to scale_px dims (NEAREST by
    default; ``upscale="quality"`` runs the opt-in hqx path)."""
    img_dir = pkg_dir / "contents" / "images"
    img_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for relname, source in sorted(manifest.items()):
        with Image.open(source) as im:
            out_img = upscale_part(im.convert("RGBA"), scale, upscale)
        target = img_dir / relname
        out_img.save(target)
        written.append(target)
    return written


def copy_fonts(font_sources: list[Path], pkg_dir: Path) -> list[Path]:
    if not font_sources:
        return []
    font_dir = pkg_dir / "contents" / "fonts"
    font_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for source in font_sources:
        target = font_dir / source.name
        target.write_bytes(source.read_bytes())
        written.append(target)
    return written
