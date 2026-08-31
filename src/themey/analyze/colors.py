"""Sample a KDE color scheme out of the theme's own border artwork.

The contract this module satisfies: **every color KDE will paint text on
is legible**. E16 themes carry no color-scheme concept — they carry
pixels — so the whole scheme is inferred, and an inferred palette that
puts white text on near-white chrome is worse than no palette at all.
Every ``ForegroundNormal`` we emit clears ``MIN_CONTRAST`` (WCAG AA, 4.5:1)
against its own group's ``BackgroundNormal``.

Where the colors come from:

* **[WM]** — the title-bearing part's iclass. ``normal_active`` gives the
  focused titlebar, ``normal`` the unfocused one. Foregrounds prefer the
  theme's own ``TEXT1`` tclass colors and only get overridden when they
  fail the contrast guard.
* **Window / View / Button / Tooltip / Header** — a luminance ladder
  tinted from the dominant color of the side and bottom border art. The
  frame edges are the theme's quietest, most representative surface; the
  titlebar is usually its loudest, so it is deliberately not the source
  for the desktop-wide backgrounds.
* **Selection / DecorationFocus / DecorationHover** — the most saturated
  cluster in that same art, i.e. the theme's accent. Falls back to Breeze
  blue when the art is entirely neutral.
* **Link / Visited / Negative / Neutral / Positive** — NOT sampled. Those
  are semantic ("this is an error", "this link is unvisited"); tinting
  them to a 2009 window border makes them lie. ``generate/colors.py``
  emits Breeze stock for them.

Two sampling pitfalls this module exists to avoid:

1. E16 border art is mostly transparent. Converting RGBA straight to RGB
   turns every transparent pixel into pure black and black wins the
   count — hence compositing over a neutral mat first.
2. Median-cut ranks by pixel count alone, so a large neutral field beats
   the small saturated accent that actually characterizes the theme.
   Clusters are therefore ranked by count weighted by saturation.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

from PIL import Image

from themey.analyze.buttons import title_part
from themey.analyze.coords import (
    REFERENCE_WINDOW_HEIGHT,
    REFERENCE_WINDOW_WIDTH,
    resolve,
)
from themey.ir import BorderSpec, ColorGroup, ColorScheme, IClassSpec, Palette, TClassSpec

log = logging.getLogger(__name__)

RGB = tuple[int, int, int]

# Decompression-bomb guard. Checked against the header dimensions before any
# pixel is decoded, so a crafted .etheme cannot make us allocate gigabytes.
# Deliberately an explicit check rather than raising Pillow's global
# ``Image.MAX_IMAGE_PIXELS``: mutating that would relax the guard for every
# other Pillow user in the process.
MAX_IMAGE_PIXELS: int = 100_000_000

# Neutral mat that transparent pixels are composited over (see pitfall 1).
NEUTRAL_MAT: RGB = (128, 128, 128)

# Pixels at or below this alpha carry no color worth sampling.
_ALPHA_FLOOR: int = 32

# Cluster weight = count * (1 + SATURATION_WEIGHT * saturation). At 2.0 a
# fully saturated cluster outranks a neutral one up to 3x its size.
SATURATION_WEIGHT: float = 2.0

# A cluster must be at least this saturated to serve as the theme's accent.
_MIN_ACCENT_SATURATION: float = 0.25

# WCAG AA for body text. Every emitted ForegroundNormal clears it.
MIN_CONTRAST: float = 4.5

# Breeze's accent (61,174,233) — the fallback when the art is all neutral.
BREEZE_ACCENT: RGB = (61, 174, 233)

# Neutral chrome for themes we cannot sample at all. The WM pair matches the
# greys themey shipped before sampling existed.
DEFAULT_TINT: RGB = (128, 128, 128)
DEFAULT_WM_ACTIVE_BG: RGB = (64, 64, 64)
DEFAULT_WM_INACTIVE_BG: RGB = (128, 128, 128)

# Background luminance ladder, as steps AWAY from mid-grey relative to the
# sampled base. View is the reading surface and sits at the far end; Window
# sits on the sampled luminance itself; Header steps back toward mid-grey.
# Mirrors how Breeze Light (View 255 > Window 239 > Header 222) and Breeze
# Dark (View 20 < Window 32) are laid out.
_LADDER: dict[str, float] = {
    "view": 0.07,
    "tooltip": 0.045,
    "button": 0.02,
    "window": 0.0,
    "header_inactive": -0.015,
    "header": -0.035,
}

# Alternate-row background: one step toward mid-grey from its own group.
# (Breeze Light View 255 -> 247; Breeze Dark View 20 -> 29.)
_ALTERNATE_STEP: float = 0.02

# Complementary is a flat inversion, not a ladder step — Breeze Light's
# Complementary background is 42,46,50 against a 239 window.
_COMPLEMENTARY_DARK: float = 0.03
_COMPLEMENTARY_LIGHT: float = 0.93

# Backgrounds never reach pure black or white: the ladder needs headroom on
# both sides or adjacent groups collapse onto each other.
_LUMA_FLOOR: float = 0.02
_LUMA_CEIL: float = 0.98

# How far ForegroundInactive is dimmed toward its background before the
# contrast guard walks it back.
_INACTIVE_DIM: float = 0.45


# --------------------------------------------------------------------- #
# Color math
# --------------------------------------------------------------------- #


def _srgb_to_linear(channel: float) -> float:
    """sRGB 0..1 -> linear 0..1 (WCAG 2.x transfer function)."""
    if channel <= 0.04045:
        return channel / 12.92
    return ((channel + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: RGB) -> float:
    """WCAG relative luminance in 0..1.

    Gamma-correct, unlike ``aurorae_rc._luminance`` — that one only needs a
    cheap brightness ordering, this one feeds a ratio with a fixed
    threshold, so the transfer function has to be right.
    """
    r, g, b = (_srgb_to_linear(c / 255.0) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(a: RGB, b: RGB) -> float:
    """WCAG contrast ratio between two colors — 1.0 (identical) to 21.0."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lo, hi = min(la, lb), max(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _saturation(rgb: RGB) -> float:
    """HSV saturation in 0..1; 0 for any shade of grey."""
    hi = max(rgb)
    if hi == 0:
        return 0.0
    return (hi - min(rgb)) / hi


def _mix(a: RGB, b: RGB, t: float) -> RGB:
    """Linear blend of *a* toward *b* by *t* in 0..1, rounded half-up."""
    return (
        int(a[0] + (b[0] - a[0]) * t + 0.5),
        int(a[1] + (b[1] - a[1]) * t + 0.5),
        int(a[2] + (b[2] - a[2]) * t + 0.5),
    )


def _at_luminance(base: RGB, target: float) -> RGB:
    """Return *base* mixed toward black or white until it hits *target* luma.

    Solved by bisection rather than algebra: mixing happens in gamma-encoded
    sRGB (that is what keeps the hue looking like the source art) while
    luminance is measured in linear light, so there is no closed form.
    """
    target = min(max(target, 0.0), 1.0)
    current = relative_luminance(base)
    if abs(current - target) < 1e-4:
        return base
    toward: RGB = (255, 255, 255) if target > current else (0, 0, 0)
    lo, hi = 0.0, 1.0
    mixed = base
    for _ in range(20):
        mid = (lo + hi) / 2
        mixed = _mix(base, toward, mid)
        if (relative_luminance(mixed) < target) == (target > current):
            lo = mid
        else:
            hi = mid
    return mixed


def _legible(fg: RGB, bg: RGB, minimum: float = MIN_CONTRAST) -> RGB:
    """Return *fg* if it clears *minimum* against *bg*, else black or white."""
    if contrast_ratio(fg, bg) >= minimum:
        return fg
    white, black = (255, 255, 255), (0, 0, 0)
    return white if contrast_ratio(white, bg) >= contrast_ratio(black, bg) else black


def _dimmed(fg: RGB, bg: RGB) -> RGB:
    """ForegroundInactive: *fg* faded toward *bg*, walked back until legible."""
    t = _INACTIVE_DIM
    while t > 0:
        candidate = _mix(fg, bg, t)
        if contrast_ratio(candidate, bg) >= MIN_CONTRAST:
            return candidate
        t -= 0.05
    return fg


# --------------------------------------------------------------------- #
# Sampling
# --------------------------------------------------------------------- #


def extract_clusters(path: Path, k: int = 8) -> tuple[tuple[int, RGB], ...]:
    """Median-cut *path* into at most *k* clusters as ``(pixel_count, rgb)``.

    Transparent pixels are composited over ``NEUTRAL_MAT`` first (pitfall 1
    in the module docstring). Returns an empty tuple when the file is
    missing, unreadable, oversized, or has no pixel above ``_ALPHA_FLOOR``.
    """
    try:
        with Image.open(path) as im:
            if im.width * im.height > MAX_IMAGE_PIXELS:
                log.warning(
                    "colors: %s is %dx%d — over the %d-pixel guard; not sampled",
                    path.name, im.width, im.height, MAX_IMAGE_PIXELS,
                )
                return ()
            rgba = im.convert("RGBA")
    except (OSError, ValueError) as exc:
        log.debug("colors: cannot sample %s: %s", path, exc)
        return ()

    # Single-band image: getextrema() is (min, max); the stub also allows the
    # per-band nesting a multi-band image would return.
    alpha_max = cast("tuple[int, int]", rgba.getchannel("A").getextrema())[1]
    if alpha_max <= _ALPHA_FLOOR:
        return ()  # nothing but transparency — no color to report

    mat = Image.new("RGBA", rgba.size, (*NEUTRAL_MAT, 255))
    flat = Image.alpha_composite(mat, rgba).convert("RGB")
    quantized = flat.quantize(colors=max(1, k), method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette() or []
    # quantize() always returns mode "P", so getcolors() yields (count,
    # palette_index) pairs — Pillow's stub also allows the (count, RGB) shape
    # it would return for an RGB image.
    counts = cast("list[tuple[int, int]]", quantized.getcolors() or [])

    out: list[tuple[int, RGB]] = []
    for count, index in counts:
        base = index * 3
        if base + 2 >= len(palette):
            continue
        out.append((count, (palette[base], palette[base + 1], palette[base + 2])))
    out.sort(key=lambda entry: (-entry[0], entry[1]))
    return tuple(out)


def extract_dominant(path: Path, k: int = 8) -> RGB | None:
    """Dominant color of *path*, or None when there is nothing to sample.

    "Dominant" is pixel count weighted by saturation (pitfall 2): a theme's
    character lives in its accent, not in the largest neutral field.
    """
    clusters = extract_clusters(path, k)
    if not clusters:
        return None
    return max(
        clusters,
        key=lambda entry: entry[0] * (1.0 + SATURATION_WEIGHT * _saturation(entry[1])),
    )[1]


def _accent_from(clusters: tuple[tuple[int, RGB], ...]) -> RGB | None:
    """Most saturated cluster, or None if the art is entirely neutral."""
    candidates = [c for c in clusters if _saturation(c[1]) >= _MIN_ACCENT_SATURATION]
    if not candidates:
        return None
    return max(candidates, key=lambda entry: (_saturation(entry[1]), entry[0]))[1]


# --------------------------------------------------------------------- #
# Zone classification — which parts are the frame's quiet chrome
# --------------------------------------------------------------------- #

# A part counts as a side/bottom border when it runs along an edge: long in
# one axis, thin in the other, measured at the reference window size.
_EDGE_LONG: float = 0.4
_EDGE_THIN: float = 0.25


def _chrome_iclass_names(border: BorderSpec) -> list[str]:
    """Iclass names of the side and bottom border parts, sides first.

    Sorted within each zone by name so the sampled source — and therefore
    the whole scheme — is deterministic for a given theme.
    """
    title = title_part(border.parts)
    ranked: list[tuple[int, str]] = []
    for part in border.parts:
        if title is not None and part is title:
            continue
        tl_x = resolve(part.tl_x_pct, part.tl_x_abs, REFERENCE_WINDOW_WIDTH)
        br_x = resolve(part.br_x_pct, part.br_x_abs, REFERENCE_WINDOW_WIDTH)
        tl_y = resolve(part.tl_y_pct, part.tl_y_abs, REFERENCE_WINDOW_HEIGHT)
        br_y = resolve(part.br_y_pct, part.br_y_abs, REFERENCE_WINDOW_HEIGHT)
        w = abs(br_x - tl_x)
        h = abs(br_y - tl_y)
        is_side = (
            h >= _EDGE_LONG * REFERENCE_WINDOW_HEIGHT
            and w <= _EDGE_THIN * REFERENCE_WINDOW_WIDTH
        )
        is_bottom = (
            w >= _EDGE_LONG * REFERENCE_WINDOW_WIDTH
            and h <= _EDGE_THIN * REFERENCE_WINDOW_HEIGHT
            and min(tl_y, br_y) >= REFERENCE_WINDOW_HEIGHT // 2
        )
        if is_side:
            ranked.append((0, part.iclass_name))
        elif is_bottom:
            ranked.append((1, part.iclass_name))
    seen: set[str] = set()
    out: list[str] = []
    for _, name in sorted(ranked):
        if name not in seen:
            seen.add(name)
            out.append(name)
    return out


def _first_image(spec: IClassSpec, states: tuple[str, ...]) -> tuple[Path, str] | None:
    """First existing image among *states* on *spec*, as (path, state_name)."""
    for state in states:
        path = getattr(spec, state)
        if path is not None and path.is_file():
            return (path, state)
    return None


# --------------------------------------------------------------------- #
# Scheme composition
# --------------------------------------------------------------------- #


def _group(base: RGB, target: float, accent: RGB, text: RGB | None) -> ColorGroup:
    """One [Colors:*] group at *target* luminance, tinted from *base*."""
    background = _at_luminance(base, min(max(target, _LUMA_FLOOR), _LUMA_CEIL))
    background_luma = relative_luminance(background)
    toward_mid = _ALTERNATE_STEP if background_luma < 0.5 else -_ALTERNATE_STEP
    alternate = _at_luminance(
        base, min(max(background_luma + toward_mid, _LUMA_FLOOR), _LUMA_CEIL)
    )
    foreground = _legible(
        text if text is not None else (255, 255, 255), background
    )
    return ColorGroup(
        background_normal=background,
        background_alternate=alternate,
        foreground_normal=foreground,
        foreground_inactive=_dimmed(foreground, background),
        foreground_active=_legible(accent, background),
        decoration_focus=accent,
        decoration_hover=accent,
    )


def _compose(
    *,
    tint: RGB,
    accent: RGB,
    wm_active_bg: RGB,
    wm_inactive_bg: RGB,
    text_active: RGB | None,
    text_inactive: RGB | None,
) -> ColorScheme:
    """Build the full 8-group scheme + [WM] pair from the sampled inputs."""
    base_luma = relative_luminance(tint)
    # Direction "away from mid-grey": a dark theme's View goes darker still,
    # a light theme's View goes lighter. See _LADDER.
    away = 1.0 if base_luma >= 0.5 else -1.0

    def rung(name: str) -> ColorGroup:
        return _group(tint, base_luma + away * _LADDER[name], accent, text_active)

    complementary_target = (
        _COMPLEMENTARY_DARK if base_luma >= 0.5 else _COMPLEMENTARY_LIGHT
    )
    selection_bg = accent
    return ColorScheme(
        view=rung("view"),
        window=rung("window"),
        button=rung("button"),
        tooltip=rung("tooltip"),
        header=rung("header"),
        header_inactive=rung("header_inactive"),
        complementary=_group(tint, complementary_target, accent, None),
        selection=_group(selection_bg, relative_luminance(selection_bg), accent, None),
        wm_active_background=wm_active_bg,
        wm_active_foreground=_legible(
            text_active if text_active is not None else (255, 255, 255), wm_active_bg
        ),
        wm_inactive_background=wm_inactive_bg,
        wm_inactive_foreground=_legible(
            text_inactive if text_inactive is not None else (255, 255, 255),
            wm_inactive_bg,
        ),
    )


def default_scheme() -> ColorScheme:
    """Neutral grey scheme for themes with no sampleable artwork."""
    return _compose(
        tint=DEFAULT_TINT,
        accent=BREEZE_ACCENT,
        wm_active_bg=DEFAULT_WM_ACTIVE_BG,
        wm_inactive_bg=DEFAULT_WM_INACTIVE_BG,
        text_active=None,
        text_inactive=None,
    )


def palette_from_scheme(scheme: ColorScheme) -> Palette:
    """Derive the decoration ``Palette`` from the scheme's [WM] colors.

    The single source of truth for titlebar color: preview, button SVGs and
    the Aurorae rc all read ``Theme.palette``, and KDE reads ``[WM]``. They
    are the same four colors by construction.
    """
    return Palette(
        titlebar_active=scheme.wm_active_background,
        titlebar_inactive=scheme.wm_inactive_background,
        text_active=scheme.wm_active_foreground,
        text_inactive=scheme.wm_inactive_foreground,
    )


def build_scheme(
    border: BorderSpec,
    iclasses: dict[str, IClassSpec],
    tclasses: dict[str, TClassSpec],
    notes: list[str],
) -> ColorScheme:
    """Sample a full color scheme from *border*'s artwork.

    Appends ``colors:``-prefixed fidelity notes to *notes* naming every
    sampled source (``report.py`` surfaces them). Returns
    :func:`default_scheme` when nothing in the theme can be sampled.
    """
    # --- [WM]: the title-bearing part ---------------------------------- #
    wm_active_bg: RGB | None = None
    wm_inactive_bg: RGB | None = None
    title = title_part(border.parts)
    title_spec = iclasses.get(title.iclass_name) if title is not None else None
    if title_spec is not None:
        active = _first_image(title_spec, ("normal_active", "normal"))
        inactive = _first_image(title_spec, ("normal", "normal_active"))
        if active is not None:
            wm_active_bg = extract_dominant(active[0])
        if inactive is not None:
            wm_inactive_bg = extract_dominant(inactive[0])
        if wm_active_bg is not None or wm_inactive_bg is not None:
            notes.append(
                f"colors: titlebar colors sampled from iclass "
                f"{title_spec.name} (active={wm_active_bg}, "
                f"inactive={wm_inactive_bg})"
            )

    # --- Backgrounds + accent: the side and bottom chrome --------------- #
    tint: RGB | None = None
    accent: RGB | None = None
    for name in _chrome_iclass_names(border):
        spec = iclasses.get(name)
        if spec is None:
            continue
        found = _first_image(spec, ("normal", "normal_active"))
        if found is None:
            continue
        clusters = extract_clusters(found[0])
        if not clusters:
            continue
        tint = extract_dominant(found[0])
        accent = _accent_from(clusters)
        notes.append(
            f"colors: desktop backgrounds tinted from iclass {name} "
            f"({found[1]}) rgb{tint}"
        )
        break

    if tint is None and wm_active_bg is not None:
        tint = wm_active_bg
        notes.append(
            "colors: no side or bottom border art to sample; desktop "
            "backgrounds tinted from the title bar instead"
        )

    if tint is None and wm_active_bg is None and wm_inactive_bg is None:
        notes.append(
            "colors: fallback — no sampleable border art in this theme; "
            "emitting the neutral default scheme"
        )
        return default_scheme()

    if accent is None:
        accent = BREEZE_ACCENT
        notes.append(
            "colors: border art has no saturated cluster; selection and "
            f"focus fall back to Breeze blue rgb{BREEZE_ACCENT}"
        )

    text1 = tclasses.get("TEXT1")
    return _compose(
        tint=tint if tint is not None else DEFAULT_TINT,
        accent=accent,
        wm_active_bg=wm_active_bg
        if wm_active_bg is not None
        else (wm_inactive_bg if wm_inactive_bg is not None else DEFAULT_WM_ACTIVE_BG),
        wm_inactive_bg=wm_inactive_bg
        if wm_inactive_bg is not None
        else (wm_active_bg if wm_active_bg is not None else DEFAULT_WM_INACTIVE_BG),
        text_active=text1.fg_active if text1 is not None else None,
        text_inactive=text1.fg_normal if text1 is not None else None,
    )
