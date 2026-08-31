"""E16 ``__CURSOR`` blocks → an installable XCursor pointer theme.

Output layout (byte-verified against an installed Plasma cursor theme):

    <themey_<slug>-cursors>/index.theme     [Icon Theme] Name= + Inherits=
    <themey_<slug>-cursors>/cursors/<name>  XCursor binaries, modern names
    <themey_<slug>-cursors>/cursors/<alias> symlink -> a modern name

Modern names (``default``, ``size_hor``, ...) are canonical on Plasma 6.6
and the legacy X11 names (``left_ptr``, ``sb_h_double_arrow``, ...) are
symlinks pointing AT them — the reverse of the pre-6 convention. Symlinks
are correct here; the zero-symlink rule in the Global-Theme plan applies
to the Look-and-Feel bundle tree, not to cursor themes. Aliases are only
created for shapes this theme actually ships, so ``Inherits=breeze_cursors``
still supplies Breeze art for everything E16 never defined.

Three contracts govern this module:

1. **Polarity.** Each cursor is an X11 bitmap pair, per
   ``XCreatePixmapCursor``: mask bit SET = the pixel is drawn, CLEAR =
   transparent; within a drawn pixel the image bit picks foreground
   (set) or background (clear). E16 ships the mask as a sibling
   ``<file>.xbm.mask`` — ``CursorSpec`` has no field for it, so it is
   derived here. With no mask file the image is foreground over
   transparent. Inverting either polarity ruins every cursor in every
   theme; ``tests/test_cursors_xbm.py`` is the guard.

2. **We parse XBM ourselves, not with Pillow.** CLAUDE.md's stack table
   nominates ``PIL.XbmImagePlugin``, and it cannot read these files.
   Measured on the fixtures: its header regex is anchored at ``#define``
   so Mac3D's GIMP-authored cursors (``/* Made with GIMP */`` on line 1)
   raise UnidentifiedImageError, and its hotspot sub-pattern
   (``[^_]*_x_hot``) cannot match ``resize_h_x_hot``, which is the form
   nearly every fixture uses. Since the hotspot is the one piece of data
   that only the XBM carries (see 3), silently losing it is worse than
   the ~40 lines of parser below.

3. **The hotspot comes from the XBM, not the cfg.** No fixture theme
   sets ``__HOT_X``/``__HOT_Y``; all 41 fixture XBMs carry ``_x_hot`` /
   ``_y_hot`` defines, which is what X itself reads. ``CursorSpec``
   cannot distinguish "declared 0" from "absent", so a nonzero cfg
   hotspot wins (an explicit override) and otherwise the XBM's own value
   is used. Out-of-range values are clamped into the image — Mac3D's
   ``pin.xbm`` really does declare ``y_hot 20`` on a 20px-tall bitmap,
   and xcursorgen rejects that outright.

Scaling: three nominal sizes at x1/x2/x3, NEAREST only. The
``--upscale quality`` hqx path is deliberately ignored here — hqx
interpolates edges between color regions, which is meaningless for 1-bit
art and would soften the one-pixel outlines these cursors are made of.
Nominal size is the scaled art's own larger dimension, so a 16px source
yields 16/32/48 and Mac3D's 25px ``move.xbm`` yields 25/50/75 rather than
being resampled off its pixel grid.
"""
from __future__ import annotations

import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from themey.external import XcursorgenError, run_xcursorgen, xcursorgen_available
from themey.generate.desktop_writer import write_desktop
from themey.generate.qmldeco.resolver import scale_px
from themey.images.upscale import upscale_part
from themey.ir import CursorSpec, Theme

log = logging.getLogger(__name__)

#: Upscale factors emitted for every cursor; also the nominal-size multipliers.
SCALES: tuple[int, ...] = (1, 2, 3)

#: Cursor art is 16-25 px in practice; anything larger is a malformed or
#: hostile header, not a pointer (same discipline as the wallpaper guard).
MAX_CURSOR_DIM = 512

INHERITS = "breeze_cursors"


class CursorError(Exception):
    """A cursor source could not be read or converted."""


# --------------------------------------------------------------------- #
# XBM reading
# --------------------------------------------------------------------- #

_DEFINE_RE = re.compile(r"#define\s+\S*?_(width|height|x_hot|y_hot)\s+(-?\d+)")
_BITS_RE = re.compile(r"_bits\s*\[\s*\]\s*=\s*\{(.*?)\}", re.DOTALL)
_BYTE_RE = re.compile(r"0[xX]([0-9a-fA-F]{1,2})")


@dataclass(frozen=True)
class Xbm:
    """One X11 bitmap: dimensions, optional hotspot, and its packed bits.

    ``bits`` is row-major with each row padded to a whole number of bytes
    and the least significant bit of each byte leftmost (X11 XBM order).
    """

    width: int
    height: int
    hot_x: int | None
    hot_y: int | None
    bits: bytes

    @property
    def stride(self) -> int:
        return (self.width + 7) // 8

    def bit(self, x: int, y: int) -> bool:
        return bool(self.bits[y * self.stride + (x >> 3)] & (1 << (x & 7)))


def read_xbm(path: Path) -> Xbm:
    """Parse an X11 XBM file. Raises :class:`CursorError` if malformed."""
    try:
        text = path.read_text(encoding="latin-1")
    except OSError as exc:
        raise CursorError(f"cannot read {path}: {exc}") from exc

    fields: dict[str, int] = {
        m.group(1): int(m.group(2)) for m in _DEFINE_RE.finditer(text)
    }
    width = fields.get("width")
    height = fields.get("height")
    if width is None or height is None:
        raise CursorError(f"{path.name}: no _width/_height defines")
    if not 0 < width <= MAX_CURSOR_DIM or not 0 < height <= MAX_CURSOR_DIM:
        raise CursorError(
            f"{path.name}: {width}x{height} is outside 1..{MAX_CURSOR_DIM}"
        )

    body = _BITS_RE.search(text)
    if body is None:
        raise CursorError(f"{path.name}: no _bits[] array")
    bits = bytes(int(m.group(1), 16) for m in _BYTE_RE.finditer(body.group(1)))
    expected = ((width + 7) // 8) * height
    if len(bits) < expected:
        raise CursorError(
            f"{path.name}: expected {expected} bytes of bit data, got {len(bits)}"
        )

    return Xbm(
        width=width,
        height=height,
        hot_x=fields.get("x_hot"),
        hot_y=fields.get("y_hot"),
        bits=bits[:expected],
    )


def rasterize(
    image: Xbm,
    mask: Xbm | None,
    fg: tuple[int, int, int],
    bg: tuple[int, int, int],
) -> Image.Image:
    """Colorize *image* through *mask* into an RGBA Image.

    Polarity per ``XCreatePixmapCursor`` — see contract 1 in the module
    docstring. With ``mask=None`` set bits are *fg* and clear bits are
    transparent (the background would otherwise paint a solid rectangle
    around the pointer).
    """
    if mask is not None and (mask.width, mask.height) != (image.width, image.height):
        raise CursorError(
            f"mask is {mask.width}x{mask.height} but image is "
            f"{image.width}x{image.height}"
        )
    fg_px = (*fg, 255)
    bg_px = (*bg, 255)
    clear = (0, 0, 0, 0)
    out = Image.new("RGBA", (image.width, image.height), clear)
    pixels = out.load()
    assert pixels is not None
    for y in range(image.height):
        for x in range(image.width):
            if mask is not None and not mask.bit(x, y):
                continue
            on = image.bit(x, y)
            if mask is None:
                if on:
                    pixels[x, y] = fg_px
            else:
                pixels[x, y] = fg_px if on else bg_px
    return out


# --------------------------------------------------------------------- #
# E16 → modern XCursor names
# --------------------------------------------------------------------- #

#: Themes are inconsistent about suffixing cursor names (Mac3D uses
#: ``MOVE_CUR``, everyone else ``MOVE``); E16 matches on the stem.
_CUR_SUFFIX_RE = re.compile(r"_CUR$")

#: Some themes name the diagonal resize pointers by the corner they point
#: FROM (upper-left/right) rather than the corner they sit ON.
_DIRECTION_ALIASES = {"RESIZE_UL": "RESIZE_TL", "RESIZE_UR": "RESIZE_TR"}

#: E16 shape → the modern (Plasma 6.6 canonical) XCursor name.
_MODERN_NAMES: dict[str, str] = {
    "DEFAULT": "default",
    "MOVE": "fleur",
    "RESIZE_H": "size_hor",
    "RESIZE_V": "size_ver",
    "RESIZE_BR": "size_fdiag",
    "RESIZE_TL": "size_fdiag",
    "RESIZE_BL": "size_bdiag",
    "RESIZE_TR": "size_bdiag",
}

#: Legacy X11 names that applications still request for each shape. Written
#: as symlinks pointing AT the modern name, and only for shapes the theme
#: actually ships — an alias to a missing file would shadow the Breeze
#: fallback with a broken link.
_LEGACY_ALIASES: dict[str, tuple[str, ...]] = {
    "default": ("left_ptr", "top_left_arrow", "arrow"),
    "fleur": ("move",),
    "size_hor": ("sb_h_double_arrow", "h_double_arrow"),
    "size_ver": ("sb_v_double_arrow", "v_double_arrow"),
    "size_fdiag": ("bottom_right_corner", "top_left_corner"),
    "size_bdiag": ("bottom_left_corner", "top_right_corner"),
}


def modern_name(e16_name: str) -> str | None:
    """The modern XCursor name for an E16 ``__CURSOR`` name, or None.

    None means E16-only: ICONIFY, KILL, MAX, STICK, PIN, SO and friends
    are window-operation pointers with no X11 shape to map onto, so they
    are skipped and ``Inherits=breeze_cursors`` covers the gap.
    """
    stem = _CUR_SUFFIX_RE.sub("", e16_name.strip().upper())
    stem = _DIRECTION_ALIASES.get(stem, stem)
    return _MODERN_NAMES.get(stem)


# --------------------------------------------------------------------- #
# Emission
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class CursorTheme:
    """One written XCursor theme — what the pipeline installs."""

    name: str  # the directory name, == kcminputrc cursorTheme=
    dir: Path
    shapes: tuple[str, ...]  # modern names with a real binary
    aliases: tuple[str, ...]  # legacy symlink names created


def hotspot_for(spec: CursorSpec, image: Xbm) -> tuple[int, int]:
    """Resolve the hotspot for *spec*, clamped inside *image*.

    Contract 3 in the module docstring: a nonzero cfg hotspot is an
    explicit override, otherwise the XBM's own ``_x_hot``/``_y_hot`` wins,
    otherwise the origin. The clamp is not defensive padding — Mac3D's
    ``pin.xbm`` declares ``y_hot 20`` on a 20px bitmap, and xcursorgen
    refuses a hotspot outside the image.
    """
    if spec.hot_x or spec.hot_y:
        x, y = spec.hot_x, spec.hot_y
    else:
        x = image.hot_x if image.hot_x is not None else 0
        y = image.hot_y if image.hot_y is not None else 0
    return (
        min(max(x, 0), image.width - 1),
        min(max(y, 0), image.height - 1),
    )


def _mask_path(xbm_path: Path) -> Path:
    """E16 ships the cursor mask beside the image as ``<file>.xbm.mask``."""
    return xbm_path.with_name(xbm_path.name + ".mask")


def _build_one(
    spec: CursorSpec, shape: str, out: Path, work: Path
) -> Path:
    """Rasterize *spec* at every scale and assemble the XCursor binary.

    Raises CursorError / XcursorgenError; the caller turns either into a
    ``cursors:`` note and carries on with the remaining shapes.
    """
    assert spec.xbm_path is not None
    image = read_xbm(spec.xbm_path)
    mask_path = _mask_path(spec.xbm_path)
    mask = read_xbm(mask_path) if mask_path.is_file() else None
    if mask is None:
        log.debug("cursor %s: no %s; drawing fg over transparent",
                  spec.name, mask_path.name)
    base = rasterize(image, mask, spec.fg_rgb, spec.bg_rgb)
    hot_x, hot_y = hotspot_for(spec, image)

    lines: list[str] = []
    for scale in SCALES:
        frame = upscale_part(base, scale, "nearest")
        png = work / f"{shape}_{scale}.png"
        frame.save(png, format="PNG")
        # Nominal size is the art's own larger dimension so 16px sources
        # give 16/32/48 and Mac3D's 25px move gives 25/50/75 — resampling
        # to a fixed 16/32/48 would take the art off its pixel grid.
        nominal = max(frame.width, frame.height)
        # Same rounding upscale_part used for the art, so the hotspot
        # cannot drift off the pixel it names.
        lines.append(
            f"{nominal} {scale_px(hot_x, scale)} {scale_px(hot_y, scale)} {png.name}"
        )
    config = work / f"{shape}.cfg"
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return run_xcursorgen(config, out, work)


def write_theme(theme: Theme, out_dir: Path) -> CursorTheme | None:
    """Write the XCursor theme for *theme* under *out_dir*.

    ``out_dir``'s basename MUST be ``slug.cursor_theme_dir(theme.name)`` —
    for an XCursor theme the directory name IS the theme name that
    ``kcminputrc``'s ``cursorTheme=`` refers to.

    Returns None (leaving no directory behind) when there is nothing to
    install: the theme declares no ``__CURSOR`` blocks, xcursorgen is not
    on PATH, or every source failed to convert. Each case appends a
    ``cursors:`` note to ``theme.notes``; a partial failure keeps the
    shapes that did convert and notes the ones that did not.
    """
    if not theme.cursors:
        theme.notes.append(
            "cursors: no __CURSOR blocks in this theme; the pointer theme "
            "is left alone."
        )
        return None
    if not xcursorgen_available():
        theme.notes.append(
            f"cursors: skipped {len(theme.cursors)} __CURSOR block(s) — "
            "xcursorgen is not on PATH (install xorg-xcursorgen, or "
            "x11-apps on Debian/Ubuntu) and there is no pure-Python "
            "XCursor writer."
        )
        return None

    # First mapping wins: RESIZE_BR and RESIZE_TL both mean size_fdiag, and
    # a theme that declares both would otherwise overwrite its own art.
    chosen: dict[str, CursorSpec] = {}
    skipped: list[str] = []
    for spec in theme.cursors:
        shape = modern_name(spec.name)
        if shape is None:
            skipped.append(spec.name)
            continue
        if spec.xbm_path is None or not spec.xbm_path.is_file():
            theme.notes.append(
                f"cursors: {spec.name} has no readable __XBM_FILE; skipped."
            )
            continue
        if shape in chosen:
            theme.notes.append(
                f"cursors: {spec.name} also maps to '{shape}'; kept the "
                "earlier block's art."
            )
            continue
        chosen[shape] = spec

    if skipped:
        theme.notes.append(
            f"cursors: {len(skipped)} E16-only pointer(s) have no X11 "
            f"equivalent and were skipped ({', '.join(skipped)}); "
            f"Inherits={INHERITS} covers them."
        )

    cursors_dir = out_dir / "cursors"
    cursors_dir.mkdir(parents=True, exist_ok=True)
    shapes: list[str] = []
    with tempfile.TemporaryDirectory(prefix="themey-cursors-") as work_str:
        work = Path(work_str)
        for shape, spec in chosen.items():
            try:
                _build_one(spec, shape, cursors_dir / shape, work)
            except (CursorError, XcursorgenError, OSError) as exc:
                theme.notes.append(
                    f"cursors: {spec.name} -> {shape} could not be "
                    f"converted: {exc}"
                )
                (cursors_dir / shape).unlink(missing_ok=True)
                continue
            shapes.append(shape)

    if not shapes:
        theme.notes.append(
            "cursors: no pointer could be converted; the pointer theme is "
            "left alone."
        )
        shutil.rmtree(out_dir, ignore_errors=True)
        return None

    aliases: list[str] = []
    for shape in shapes:
        for alias in _LEGACY_ALIASES.get(shape, ()):
            link = cursors_dir / alias
            link.unlink(missing_ok=True)
            # Relative target: the theme dir is staged and then renamed
            # into ~/.local/share/icons/, so an absolute link would dangle.
            link.symlink_to(shape)
            aliases.append(alias)

    write_desktop(
        out_dir / "index.theme",
        {
            "Icon Theme": {
                "Name": f"{theme.display_name} (themey)",
                "Inherits": INHERITS,
            }
        },
    )
    log.info(
        "cursor theme %s: %d shape(s), %d legacy alias(es)",
        out_dir.name, len(shapes), len(aliases),
    )
    return CursorTheme(
        name=out_dir.name,
        dir=out_dir,
        shapes=tuple(shapes),
        aliases=tuple(aliases),
    )
