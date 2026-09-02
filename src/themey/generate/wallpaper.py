"""Plasma wallpaper package writer — one package per E16 background image.

Format (byte-verified against an installed Plasma wallpaper package):

    <pkg>/metadata.json          KPlugin only (no KPackageStructure); a
                                  custom top-level X-Themey-FillMode key
                                  (one of analyze.wallpaper.FILL_MODES:
                                  stretch/tile/tile-h/tile-v/pad/fit) so
                                  `apply` can dispatch the fill without
                                  re-parsing the E16 source, plus
                                  X-Themey-SolidColor ("r,g,b" — KConfig's
                                  QColor spelling) when the block carried a
                                  SET_SOLID, the letterbox color `apply`
                                  hands to the Image wallpaper's Color key
                                  for fit/pad.
    <pkg>/contents/images/<W>x<H>.<ext>   the wallpaper at its REAL
                                  measured dimensions — Plasma's Image
                                  wallpaper plugin keys art by resolution
                                  bucket, not by a fixed filename.

Most E16 background images are already PNG/JPEG/BMP and are copied
through byte-for-byte at those dimensions. GIF and anything else Pillow
can open but Plasma cannot (an animation, an XBM, ...) is decoded and
re-saved as a static PNG — first frame only, since a wallpaper package
holds one image, not an animation.

Two SET_SOLID-driven exceptions (see ``analyze/wallpaper.py``):

* a source with an alpha channel whose spec carries ``solid_rgb`` is
  flattened over that solid before saving — E16 composites the tile over
  the solid, so shipping the raw RGBA leaves Plasma tiling transparency
  over an undefined color (e13's ``tanbg.png``);
* a solid-only spec (``path=None``) becomes a small flat
  ``_SOLID_WALLPAPER_SIZE``² PNG — deliberately small so
  :func:`pick_default`'s area ranking (belt) plus the explicit ``solid``
  flag (suspenders) never prefer it over real art.

Under ``--upscale waifu2x`` (and ONLY then — hqx on a photograph is the
wrong tool, and NEAREST would be absurd) a source smaller than
``WALLPAPER_UPSCALE_MAX_WIDTH`` is run through the CNN at 2x before being
saved. E16 wallpapers are 512-1024 px, desktops are not, and Plasma
upsamples whatever it is given: doubling first means it DOWNsamples
instead, which is the direction that does not invent detail. Measured
2026-09-02 against LANCZOS-straight-to-1920x1080 on five corpus
wallpapers spanning 512x400 to 1280x1024 — waifu2x won every one, most
visibly on text and fine mechanical detail. Denoise stays at the chrome
setting (``-n 0``): ``-n 1`` cleans up JPEG mosquito noise on flat dark
art but visibly waxes over the grain in textured art (rust, stone,
scanlines), which lost 4 of those 5 comparisons.

Upscaled wallpapers are written as lossless PNG whatever the source
container was (``_save_upscaled``) — the format is ours to pick once the
passthrough is forfeit, and a JPEG re-encode would stack a second
generation of loss on a CNN's reconstruction of an already-lossy source.
That is the expensive choice and it is deliberate: Aliens' four
wallpapers dominate the package, taking it to roughly 14 MB.

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

from themey.external import Waifu2xError
from themey.images.waifu2x import waifu2x
from themey.ir import Theme, WallpaperSpec
from themey.slug import wallpaper_id

log = logging.getLogger(__name__)

MAX_IMAGE_PIXELS: int = 100_000_000

# Upscale only sources narrower than this. 1920 is the width at which a
# wallpaper already covers the common desktop, so doubling it would only
# bloat the package; below it Plasma is upsampling today. The corpus sits
# well under: 1024x768 (23 of 60 themes surveyed), 512x512, 512x400,
# 800x600, 1280x1024 — and the 1280 case still measurably benefited, so
# the cut is deliberately at the screen width rather than lower.
WALLPAPER_UPSCALE_MAX_WIDTH: int = 1920

# waifu2x scales by powers of two; 2 is the only factor worth using here
# (4x a 1024-wide source is 4096 px for a 1920 px screen).
_WALLPAPER_UPSCALE_FACTOR = 2

# Unused while upscaled wallpapers ship as lossless PNG (see
# _save_upscaled); kept as the knob for the size/quality trade if a
# package ever needs to shrink.
# Re-encode quality when an upscaled JPEG source is saved back as JPEG.
# Upscaling forfeits the byte-for-byte passthrough, and a photographic
# 2048x1536 PNG is several MB against ~100 KB for the JPEG it replaces.
_WALLPAPER_JPEG_QUALITY = 92

# Formats copied through at their own extension and dimensions. Anything
# else is decoded and re-saved as PNG (see module docstring).
_PASSTHROUGH_EXTENSIONS: dict[str, str] = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "BMP": ".bmp",
}

# Solid-only wallpapers are a flat color; any size works, small keeps the
# area ranking from ever preferring one over real art.
_SOLID_WALLPAPER_SIZE = 128


def _has_alpha(im: Image.Image) -> bool:
    return im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info


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
    # True for a SET_SOLID-only package; never outranks real art as the
    # Look-and-Feel default.
    solid: bool = False



def _maybe_upscale(
    theme: Theme, spec: WallpaperSpec, im: Image.Image
) -> Image.Image | None:
    """Return a 2x waifu2x version of *im*, or None to ship it as-is.

    None is the normal answer: any mode but ``waifu2x``, a source that
    already covers a desktop width, or one whose doubled size would
    breach the decompression guard. A scaler FAILURE is also None — with
    a ``wallpaper:`` note — because a wallpaper that could not be
    enlarged is still a perfectly good wallpaper, and losing the whole
    conversion over it would be absurd (same reasoning as the hqx
    fallback in ``pipeline.convert``).
    """
    if theme.upscale != "waifu2x":
        return None
    if im.width >= WALLPAPER_UPSCALE_MAX_WIDTH:
        return None
    factor = _WALLPAPER_UPSCALE_FACTOR
    if (im.width * factor) * (im.height * factor) > MAX_IMAGE_PIXELS:
        theme.notes.append(
            f"wallpaper: {spec.path.name if spec.path else spec.stem} not "
            f"upscaled: {factor}x would exceed the {MAX_IMAGE_PIXELS}-pixel "
            "guard"
        )
        return None
    try:
        return waifu2x(im, factor)
    except (Waifu2xError, OSError, ValueError) as exc:
        name = spec.path.name if spec.path else spec.stem
        theme.notes.append(
            f"wallpaper: {name} kept at {im.width}x{im.height}; waifu2x "
            f"upscale failed ({exc})"
        )
        log.warning("wallpaper upscale failed for %s: %s", name, exc)
        return None


def _save_upscaled(
    img: Image.Image, images_dir: Path, source_format: str
) -> tuple[Path, int, int]:
    """Write *img* losslessly, as PNG, whatever the source container was.

    Upscaling forfeits the byte-for-byte passthrough, so the format is
    ours to choose again — and the choice is quality, per chris
    2026-09-02 ("store the images as whatever looks best"). Re-encoding
    to JPEG is the only lossy step left in the wallpaper path, and it is
    a *second* generation of loss stacked on an already-JPEG source and
    then on a CNN's reconstruction of it. Measured on a doubled 800x600
    corpus wallpaper: q92 costs 0.85 mean / 13 max RGB error for 415 KB,
    q98 costs 0.44 / 9 for 730 KB, PNG costs nothing for 2302 KB.

    The price is package size, and it is not small: Aliens goes ~8 MB to
    ~14 MB. If that ever matters more than the pixels, restoring the
    JPEG branch for ``source_format == "JPEG"`` is a four-line change and
    ``_WALLPAPER_JPEG_QUALITY`` is still here for it. ``source_format``
    is retained for that reason and for callers that log it.
    """
    width, height = img.width, img.height
    dest = images_dir / f"{width}x{height}.png"
    img.save(dest, format="PNG", optimize=True)
    return dest, width, height


def write_package(theme: Theme, spec: WallpaperSpec, pkg_dir: Path) -> WallpaperPackage:
    """Write one wallpaper package for *spec* under *pkg_dir*.

    ``pkg_dir``'s basename MUST be ``slug.wallpaper_id(theme.name,
    spec.path.stem)`` — Plasma matches wallpaper packages by
    ``KPlugin.Id``, same contract as every other themey package.

    Raises WallpaperError if *spec.path* can't be opened/decoded, or is
    over the decompression-bomb guard. On ANY failure — the guard, a copy/
    decode error, or a metadata-write error — *pkg_dir* is removed again
    before the error propagates: a failed conversion leaves no filesystem
    trace, not just the pre-write guard case. ``pkg_dir`` must therefore be
    a directory this call owns exclusively (the pipeline stages/clears it
    first); nothing pre-existing under it survives a failure.
    """
    stem = spec.stem
    pkg_id = wallpaper_id(theme.name, stem)
    images_dir = pkg_dir / "contents" / "images"
    solid_only = spec.path is None

    try:
        if spec.path is None:
            if spec.solid_rgb is None:
                raise WallpaperError(
                    f"solid-only spec {stem!r} carries no solid_rgb"
                )
            images_dir.mkdir(parents=True, exist_ok=True)
            width = height = _SOLID_WALLPAPER_SIZE
            dest = images_dir / f"{width}x{height}.png"
            Image.new("RGB", (width, height), spec.solid_rgb).save(
                dest, format="PNG"
            )
        else:
            with Image.open(spec.path) as im:
                if im.width * im.height > MAX_IMAGE_PIXELS:
                    raise WallpaperError(
                        f"{spec.path.name} is {im.width}x{im.height} — over "
                        f"the {MAX_IMAGE_PIXELS}-pixel guard"
                    )
                images_dir.mkdir(parents=True, exist_ok=True)
                fmt = im.format or ""
                if _has_alpha(im) and spec.solid_rgb is not None:
                    # E16 composites the (partially transparent) image over
                    # the block's SET_SOLID; Plasma has no such underlay.
                    frame = im.convert("RGBA")
                    base = Image.new("RGBA", frame.size, (*spec.solid_rgb, 255))
                    flat = Image.alpha_composite(base, frame).convert("RGB")
                    # Flatten BEFORE upscaling: the CNN would otherwise
                    # feather the alpha it is meant to be compositing away.
                    bigger = _maybe_upscale(theme, spec, flat)
                    flat = bigger.convert("RGB") if bigger is not None else flat
                    width, height = flat.width, flat.height
                    dest = images_dir / f"{width}x{height}.png"
                    flat.save(dest, format="PNG")
                    theme.notes.append(
                        f"wallpaper: {spec.path.name} has transparency; "
                        f"flattened over SET_SOLID rgb{spec.solid_rgb} — E16 "
                        "composites the tile over the solid"
                    )
                elif fmt in _PASSTHROUGH_EXTENSIONS:
                    bigger = _maybe_upscale(theme, spec, im)
                    if bigger is None:
                        # The documented contract at every other mode:
                        # copied through byte-for-byte, dimensions intact.
                        width, height = im.width, im.height
                        dest = (
                            images_dir
                            / f"{width}x{height}{_PASSTHROUGH_EXTENSIONS[fmt]}"
                        )
                        shutil.copyfile(spec.path, dest)
                    else:
                        dest, width, height = _save_upscaled(
                            bigger, images_dir, fmt
                        )
                else:
                    frame = im.convert("RGBA")
                    bigger = _maybe_upscale(theme, spec, frame)
                    if bigger is not None:
                        frame = bigger
                    width, height = frame.width, frame.height
                    dest = images_dir / f"{width}x{height}.png"
                    frame.save(dest, format="PNG")

        meta = {
            "KPlugin": {
                "Id": pkg_id,
                "Name": f"{theme.display_name}: {stem} (themey)",
            },
            "X-Themey-FillMode": spec.fill_mode,
        }
        if spec.solid_rgb is not None:
            meta["X-Themey-SolidColor"] = ",".join(map(str, spec.solid_rgb))
        (pkg_dir / "metadata.json").write_text(
            json.dumps(meta, indent=4, sort_keys=True) + "\n"
        )
    except WallpaperError:
        shutil.rmtree(pkg_dir, ignore_errors=True)
        raise
    except (OSError, ValueError) as exc:
        shutil.rmtree(pkg_dir, ignore_errors=True)
        raise WallpaperError(f"cannot convert {spec.path}: {exc}") from exc

    return WallpaperPackage(
        id=pkg_id,
        dir=pkg_dir,
        width=width,
        height=height,
        fill_mode=spec.fill_mode,
        solid=solid_only,
    )


def pick_default(packages: Sequence[WallpaperPackage]) -> WallpaperPackage | None:
    """The largest-area package — the Look-and-Feel default (Phase D).

    Solid-only packages never outrank real art (a flat SET_SOLID color is a
    fallback, not the theme's face); one wins only when it's all there is
    (OPENSTEP). None when *packages* is empty (themes with no wallpapers
    leave the desktop wallpaper alone, per the Phase B/D contract).
    """
    if not packages:
        return None
    return max(packages, key=lambda p: (not p.solid, p.width * p.height))
