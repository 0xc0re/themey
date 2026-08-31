"""Plasma wallpaper package writer — one package per E16 background image.

Format (byte-verified against an installed Plasma wallpaper package):

    <pkg>/metadata.json          KPlugin only (no KPackageStructure); a
                                  custom top-level X-Themey-FillMode key so
                                  `apply` can read tiled-ness back out of
                                  the installed package without re-parsing
                                  the E16 source.
    <pkg>/contents/images/<W>x<H>.<ext>   the wallpaper at its REAL
                                  measured dimensions — Plasma's Image
                                  wallpaper plugin keys art by resolution
                                  bucket, not by a fixed filename.

Most E16 background images are already PNG/JPEG/BMP and are copied
through byte-for-byte at those dimensions. GIF and anything else Pillow
can open but Plasma cannot (an animation, an XBM, ...) is decoded and
re-saved as a static PNG — first frame only, since a wallpaper package
holds one image, not an animation.

Guards the same decompression-bomb pitfall as ``analyze/colors.py``: an
explicit width*height check against the header before any pixel is
decoded, deliberately not ``Image.MAX_IMAGE_PIXELS`` (that would relax the
guard for every other Pillow user in the process).
"""
from __future__ import annotations

import json
import logging
import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from themey.ir import Theme, WallpaperSpec
from themey.slug import wallpaper_id

log = logging.getLogger(__name__)

MAX_IMAGE_PIXELS: int = 100_000_000

# Formats copied through at their own extension and dimensions. Anything
# else is decoded and re-saved as PNG (see module docstring).
_PASSTHROUGH_EXTENSIONS: dict[str, str] = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "BMP": ".bmp",
}


class WallpaperError(Exception):
    """A wallpaper source image could not be converted into a package."""


@dataclass(frozen=True)
class WallpaperPackage:
    """One written wallpaper package — what :func:`pick_default` ranks."""

    id: str
    dir: Path
    width: int
    height: int
    fill_mode: str


def write_package(theme: Theme, spec: WallpaperSpec, pkg_dir: Path) -> WallpaperPackage:
    """Write one wallpaper package for *spec* under *pkg_dir*.

    ``pkg_dir``'s basename MUST be ``slug.wallpaper_id(theme.name,
    spec.path.stem)`` — Plasma matches wallpaper packages by
    ``KPlugin.Id``, same contract as every other themey package.

    Raises WallpaperError if *spec.path* can't be opened/decoded, or is
    over the decompression-bomb guard.
    """
    stem = spec.path.stem
    pkg_id = wallpaper_id(theme.name, stem)
    images_dir = pkg_dir / "contents" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    try:
        with Image.open(spec.path) as im:
            if im.width * im.height > MAX_IMAGE_PIXELS:
                raise WallpaperError(
                    f"{spec.path.name} is {im.width}x{im.height} — over "
                    f"the {MAX_IMAGE_PIXELS}-pixel guard"
                )
            fmt = im.format or ""
            if fmt in _PASSTHROUGH_EXTENSIONS:
                width, height = im.width, im.height
                dest = images_dir / f"{width}x{height}{_PASSTHROUGH_EXTENSIONS[fmt]}"
                shutil.copyfile(spec.path, dest)
            else:
                frame = im.convert("RGBA")
                width, height = frame.width, frame.height
                dest = images_dir / f"{width}x{height}.png"
                frame.save(dest, format="PNG")
    except (OSError, ValueError) as exc:
        raise WallpaperError(f"cannot convert {spec.path}: {exc}") from exc

    meta = {
        "KPlugin": {
            "Id": pkg_id,
            "Name": f"{theme.display_name}: {stem} (themey)",
        },
        "X-Themey-FillMode": spec.fill_mode,
    }
    (pkg_dir / "metadata.json").write_text(
        json.dumps(meta, indent=4, sort_keys=True) + "\n"
    )
    return WallpaperPackage(
        id=pkg_id, dir=pkg_dir, width=width, height=height, fill_mode=spec.fill_mode
    )


def pick_default(packages: Sequence[WallpaperPackage]) -> WallpaperPackage | None:
    """The largest-area package — the Look-and-Feel default (Phase D).

    None when *packages* is empty (themes with no wallpapers leave the
    desktop wallpaper alone, per the Phase B/D contract).
    """
    if not packages:
        return None
    return max(packages, key=lambda p: p.width * p.height)
