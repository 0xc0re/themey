"""Plasma Style (desktop theme) generator — panel/popup/tooltip chrome.

The contract this module satisfies is KSvg's FrameSvg element-ID lookup
inside a ``Plasma/Theme`` KPackage under
``~/.local/share/plasma/desktoptheme/<id>/``:

* Ship an SVG **only for elements with real E16 counterpart art**. Plasma
  falls back to Breeze **per missing file** and re-tints Breeze's art
  through this package's bundled ``colors`` file (Breeze SVGs carry a
  ``current-color-scheme`` stylesheet rewritten from the active theme's
  ``colors``), so a sparse package is first-class — ``breeze-dark`` itself
  is colors-only.
* Every shipped SVG is mirrored **byte-identically** into ``solid/`` and
  ``opaque/``: ``Panel.qml`` loads ``solid/widgets/panel-background`` for
  opaque panels, and a missing ``solid/`` copy would fall back to
  *Breeze's* solid art next to our chrome. The ONE exception is the panel
  background itself: the base rendition is a translucent flat tint
  (``PANEL_ALPHA``), so its ``solid/``/``opaque/`` mirrors are re-rendered
  at alpha 1 — AdaptiveTransparency swaps to ``solid/`` when a window
  touches the panel, and that variant must be genuinely opaque.
* The panel background is NOT sourced from E16 art: dragbar/iconbox art
  carries baked-in wordmarks ("ENLIGHTENMENT", theme logos) exactly in the
  cap regions, which stretched across a 40 px Plasma panel makes every
  widget unreadable (verified live 2026-08-31). Instead the panel is a
  flat translucent tint of the art's dominant color (scheme fallback),
  letting the wallpaper show through — see :func:`build_panel_background`.
* 9-part sets use FrameSvg's element names (``topleft`` … ``bottomright``,
  optionally ``<prefix>-``-prefixed); zero-extent slices are simply not
  emitted (FrameSvg then reports a 0 border, which is correct — the Aliens
  dragbar's ``133 28 0 0`` edge yields a left/center/right-only set).
  ``hint-tile-center`` is NEVER emitted — E16 stretches middles, and that
  hint would switch FrameSvg to tiling.
* Margin hints (``hint-<side>-margin``) come from the iclass ``__PADDING``
  and are emitted per non-zero side only.
* The package ``plasmarc`` enables AdaptiveTransparency and the contrast
  effect (Breeze's own values) so the translucent panel gets blur/contrast
  behind it. No ``translucent/`` variant dir is shipped: the base rendition
  already is the translucent one (exactly Breeze's arrangement, where
  ``translucent/`` and base are equivalent). The still-opaque E16
  dialog/tooltip art fully covers its own blur region (the region derives
  from each surface's alpha mask), so enabling the effects theme-wide only
  becomes visible behind the panel.
* Art is upscaled at generate time by ``theme.scale`` (NEAREST via
  ``upscale_part``) and sliced at edge-consistent scaled boundaries
  (``scale_px``, the same rounding the QML deco uses) so the panel chrome
  and the pre-scaled window chrome stay coherent; FrameSvg treats SVG
  units as logical px, so unscaled 2-4 px caps would render as hairlines.
  Middles are never pre-stretched — FrameSvg stretches at runtime.

State map (whole module): E16 ``normal`` → ``normal``, ``hilited`` →
``hover``, ``clicked`` → ``pressed``/``selected``; a missing state reuses
``normal`` at generate time, and non-``_active`` variants are preferred
(these are non-window surfaces).

Naming: the package dir name, ``KPlugin.Id`` and the ``plasmarc [Theme]
name=`` value are all ``slug.plugin_id(theme.name)`` — the same deliberate
cross-namespace reuse as the deco/LnF/colors artifacts (see CLAUDE.md).

Fidelity notes append to ``theme.notes`` with the ``plasmastyle:`` prefix;
``report.py`` surfaces them in the Approximated section.
"""
from __future__ import annotations

import json
import logging
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from PIL import Image, ImageEnhance

from themey.analyze.colors import (
    MIN_CONTRAST,
    _at_lightness,
    _dimmed,
    _legible,
    contrast_ratio,
    default_scheme,
    extract_dominant,
)
from themey.generate.colors import build_sections
from themey.generate.desktop_writer import write_desktop
from themey.generate.qmldeco.resolver import scale_px
from themey.images.embed import image_to_b64_uri
from themey.images.ninepatch import slice_9patch
from themey.images.upscale import upscale_part
from themey.ir import ColorGroup, ColorScheme, IClassSpec, Theme
from themey.slug import plugin_id

log = logging.getLogger(__name__)

RGB = tuple[int, int, int]

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"

#: Gap between element bounding boxes on one canvas, in px. FrameSvg looks
#: elements up by ID, but non-overlapping bboxes keep the file inspectable
#: and match how Breeze lays its sets out.
_GAP = 2

#: Package plasmarc — Breeze's own values. The contrast/blur region derives
#: from each surface's FrameSvg alpha mask, so the still-opaque E16
#: dialog/tooltip art fully covers its blurred region; the effects only
#: become visible behind the translucent panel. AdaptiveTransparency makes
#: Plasma swap to ``solid/`` when a window touches the panel, which is why
#: write() re-renders that variant genuinely opaque.
_PACKAGE_PLASMARC: dict[str, dict[str, str]] = {
    "AdaptiveTransparency": {"enabled": "true"},
    "ContrastEffect": {"enabled": "true", "contrast": "1.0", "saturation": "1.5"},
}

#: Alpha of the base panel tint — Breeze's own panel center opacity
#: (widgets/panel-background.svgz, verified on this machine 2026-08-31).
PANEL_ALPHA = 0.85

#: Ref-px content margin for the flat panel (E16 dragbars were flush
#: strips; 2 px keeps widgets off the very edge without Breeze's chrome).
PANEL_MARGIN_REF = 2

#: Cell geometry of the flat 3x3 panel grid: 4 px edges, 24 px center
#: (32 px tile, mirroring Breeze's edge/center proportions; cosmetic —
#: FrameSvg reads border thickness from the edge cells' size, and a 4 px
#: flat border is invisible against the identical-color center).
_PANEL_EDGE, _PANEL_CENTER = 4, 24

#: Pager thumbnail width — crisp at real pager-cell sizes, and three
#: embedded copies of a 256-px photo PNG stay in the low hundreds of KB.
#: The single knob if file size ever matters.
PAGER_THUMB_WIDTH = 256

#: Pillow Brightness factors per pager state: normal desks dimmed, active
#: full, hover slightly lifted (mirrors E16's pager where only the current
#: desk reads at full brightness).
_PAGER_BRIGHTNESS: dict[str, float] = {"normal-": 0.6, "active-": 1.0, "hover-": 1.15}

#: Fallback pager frame stroke, ref px (scaled via scale_px, floor 1).
PAGER_FRAME_REF = 1

#: Relative SVG paths (also the ``shipped`` vocabulary and the mirror set).
PANEL_SVG = "widgets/panel-background.svg"
PAGER_SVG = "widgets/pager.svg"
DIALOG_SVG = "dialogs/background.svg"
TOOLTIP_SVG = "widgets/tooltip.svg"
BUTTON_SVG = "widgets/button.svg"
VIEWITEM_SVG = "widgets/viewitem.svg"
SCROLLBAR_SVG = "widgets/scrollbar.svg"
ARROWS_SVG = "widgets/arrows.svg"

#: E16 state → the IClassSpec fields tried in order. Non-``_active``
#: variants first (module docstring); every chain ends on the normal pair
#: so a missing state reuses normal.
_STATE_CHAINS: dict[str, tuple[str, ...]] = {
    "normal": ("normal", "normal_active"),
    "hover": ("hilited", "hilited_active", "normal", "normal_active"),
    "pressed": ("clicked", "clicked_active", "normal", "normal_active"),
    # viewitem-only: a selected menu row falls back to the hilite art —
    # MENU_SEL's hilited state IS E16's selection highlight, so a theme
    # with no clicked art must still ship its selected-* sets.
    "selected": (
        "clicked", "clicked_active", "hilited", "hilited_active",
        "normal", "normal_active",
    ),
}

#: FrameSvg 9-part element names by (row, col) of the slice grid.
_GRID = (
    ("topleft", "top", "topright"),
    ("left", "center", "right"),
    ("bottomleft", "bottom", "bottomright"),
)

#: Ref-px ceiling for the scrollbar track thickness (``hint-scrollbar-size``).
#: E16 stretched knob art INTO a slim configured track — the image's own
#: width is NOT the widget width (e13's vertical knob image is ~28 ref px,
#: which rendered as a 57 px-wide scrollbar column through Kickoff, verified
#: live 2026-08-31). 12 ref px ≈ Breeze's logical scrollbar thickness.
SCROLLBAR_MAX_REF_THICKNESS = 12

_ARROW_SOURCES: tuple[tuple[str, str], ...] = (
    ("up-arrow", "ICONBOX_ARROW_UP"),
    ("down-arrow", "ICONBOX_ARROW_DOWN"),
    ("left-arrow", "ICONBOX_ARROW_LEFT"),
    ("right-arrow", "ICONBOX_ARROW_RIGHT"),
)


class PlasmaStyleError(Exception):
    """The Plasma Style package could not be written; out_dir was removed."""


@dataclass(frozen=True)
class PlasmaStyle:
    """One written Plasma Style package — what the pipeline installs."""

    id: str
    dir: Path
    shipped: tuple[str, ...]  # relative SVG paths actually written


# --------------------------------------------------------------------- #
# Source resolution
# --------------------------------------------------------------------- #


def _state_image(spec: IClassSpec | None, state: str) -> Path | None:
    """First existing image for *state* on *spec* along its fallback chain."""
    if spec is None:
        return None
    for field in _STATE_CHAINS[state]:
        p = getattr(spec, field)
        if p is not None and p.is_file():
            return p
    return None


def _iclass_with_art(theme: Theme, *names: str) -> IClassSpec | None:
    """First of *names* present in ``theme.iclasses`` with normal-state art."""
    for name in names:
        spec = theme.iclasses.get(name)
        if spec is not None and _state_image(spec, "normal") is not None:
            return spec
    return None


def _panel_source(theme: Theme) -> IClassSpec | None:
    return _iclass_with_art(
        theme, "DESKTOP_DRAGBUTTON_HORIZ", "ICONBOX_HORIZONTAL", "DEFAULT_DOCK_BUTTON"
    )


def _dialog_source(theme: Theme) -> IClassSpec | None:
    return _iclass_with_art(theme, "MENU_BG", "DIALOG")


# --------------------------------------------------------------------- #
# SVG emission
# --------------------------------------------------------------------- #


class _Canvas:
    """One SVG document; rows of element sets stacked top-to-bottom."""

    def __init__(self) -> None:
        ET.register_namespace("", SVG_NS)
        ET.register_namespace("xlink", XLINK_NS)
        self.root = ET.Element(f"{{{SVG_NS}}}svg", {"version": "1.1"})
        self.y = 0
        self.w = 0

    def advance(self, width: int, height: int) -> None:
        self.w = max(self.w, width)
        self.y += height + _GAP

    def finish(self) -> ET.Element:
        self.root.set("width", str(max(1, self.w)))
        self.root.set("height", str(max(1, self.y)))
        return self.root


def _load_scaled(path: Path, scale: float) -> Image.Image:
    """Open *path* as RGBA and upscale it by *scale* (NEAREST).

    Raises OSError/ValueError on unreadable art — the caller skips the
    whole file with a ``plasmastyle:`` note.
    """
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
    return upscale_part(rgba, scale)


def _scaled_caps(
    edge: tuple[int, int, int, int], src_w: int, src_h: int, scale: float
) -> tuple[int, int, int, int]:
    """Edge-consistent scaled cap sizes for a source-grid ``__EDGE_SCALING``.

    Left/top caps scale directly; right/bottom are anchored to the far edge
    (``scale_px(w) - scale_px(w - r)``) so caps + middle sum exactly to the
    scaled image at fractional scales — the same edge-based rounding the
    QML resolver uses.
    """
    left, right, top, bottom = edge
    return (
        scale_px(left, scale),
        scale_px(src_w, scale) - scale_px(src_w - right, scale),
        scale_px(top, scale),
        scale_px(src_h, scale) - scale_px(src_h - bottom, scale),
    )


def _embed_image(
    parent: ET.Element, img: Image.Image, x: int, y: int
) -> None:
    ET.SubElement(
        parent,
        f"{{{SVG_NS}}}image",
        {
            f"{{{XLINK_NS}}}href": image_to_b64_uri(img),
            "x": str(x),
            "y": str(y),
            "width": str(img.width),
            "height": str(img.height),
            "preserveAspectRatio": "none",
        },
    )


def _frame_group(
    canvas: _Canvas,
    prefix: str,
    img: Image.Image,
    caps: tuple[int, int, int, int],
) -> None:
    """Emit one FrameSvg 9-part set at the canvas cursor.

    Slices *img* at *caps* (already-scaled L R T B) via ``slice_9patch``;
    zero-extent slices are not emitted, so a ``(l, r, 0, 0)`` edge yields
    left/center/right only and ``(0, 0, 0, 0)`` yields a lone ``center``
    (E16 no-slice semantics — the whole image stretches). Slices sit at
    source-grid coordinates so bounding boxes never overlap.

    Raises ValueError when the caps exceed the image (``slice_9patch``'s
    guard) — the caller degrades to center-only with a note.
    """
    left, right, top, bottom = caps
    regions = slice_9patch(img, left, right, top, bottom)
    center_w = img.width - left - right
    center_h = img.height - top - bottom
    xs = (0, left, left + center_w)
    ys = (0, top, top + center_h)
    widths = (left, center_w, right)
    heights = (top, center_h, bottom)
    by_name = {
        "topleft": regions.topleft, "top": regions.top, "topright": regions.topright,
        "left": regions.left, "center": regions.center, "right": regions.right,
        "bottomleft": regions.bottomleft, "bottom": regions.bottom,
        "bottomright": regions.bottomright,
    }
    for row in range(3):
        for col in range(3):
            if widths[col] <= 0 or heights[row] <= 0:
                continue
            name = _GRID[row][col]
            g = ET.SubElement(
                canvas.root, f"{{{SVG_NS}}}g", {"id": f"{prefix}{name}"}
            )
            _embed_image(g, by_name[name], xs[col], canvas.y + ys[row])
    canvas.advance(img.width, img.height)


def _margin_hints(
    canvas: _Canvas,
    prefix: str,
    padding: tuple[int, int, int, int],
    scale: float,
) -> None:
    """Emit ``<prefix>hint-<side>-margin`` rects from an iclass ``__PADDING``.

    Per non-zero side only: FrameSvg falls back to the border element's own
    thickness for a side with no hint, and E16 padding is L R T B like
    edge_scaling. FrameSvg only reads the element's *size*, so the rects
    are invisible and parked in their own canvas row.
    """
    if padding == (0, 0, 0, 0):
        return
    x = 0
    row_h = 0
    for side, value in zip(("left", "right", "top", "bottom"), padding, strict=True):
        if value <= 0:
            continue
        size = max(1, scale_px(value, scale))
        ET.SubElement(
            canvas.root,
            f"{{{SVG_NS}}}rect",
            {
                "id": f"{prefix}hint-{side}-margin",
                "x": str(x),
                "y": str(canvas.y),
                "width": str(size),
                "height": str(size),
                "style": "opacity:0",
            },
        )
        x += size + _GAP
        row_h = max(row_h, size)
    if row_h:
        canvas.advance(x, row_h)


def _emit_set(
    theme: Theme,
    canvas: _Canvas,
    prefix: str,
    spec: IClassSpec,
    state: str,
    *,
    hints: bool = False,
    edge_override: Callable[[tuple[int, int, int, int], int, int], tuple[int, int, int, int]]
    | None = None,
) -> bool:
    """One prefixed 9-part set (+ optional margin hints) for *spec*/*state*.

    Returns False when the state resolves to no image at all. Oversized
    caps degrade to a center-only set with a ``plasmastyle:`` note rather
    than failing (per the mapping contract). ``edge_override`` maps
    ``(declared_edge, src_w, src_h)`` to the edge actually used — the
    viewitem builder pins synthetic caps with it.
    """
    path = _state_image(spec, state)
    if path is None:
        return False
    img = _load_scaled(path, theme.scale)
    src_w, src_h = _source_size(path)
    edge = spec.edge_scaling
    if edge_override is not None:
        edge = edge_override(edge, src_w, src_h)
    fitted = _fit_caps(edge, src_w, src_h)
    if fitted is not None:
        theme.notes.append(
            f"plasmastyle: {spec.name} edge_scaling {edge} exceeds its "
            f"{path.name} image; caps shrunk to {fitted} (E16 overlapping-"
            "cap art)"
        )
        edge = fitted
    caps = _scaled_caps(edge, src_w, src_h, theme.scale)
    try:
        _frame_group(canvas, prefix, img, caps)
    except ValueError:
        # Last resort only — _fit_caps should have prevented this.
        theme.notes.append(
            f"plasmastyle: {spec.name} edge_scaling {spec.edge_scaling} "
            f"exceeds its {path.name} image; whole image stretched instead"
        )
        _frame_group(canvas, prefix, img, (0, 0, 0, 0))
    if hints:
        _margin_hints(canvas, prefix, spec.padding, theme.scale)
    return True


def _source_size(path: Path) -> tuple[int, int]:
    """Header-only (width, height) of the source image."""
    with Image.open(path) as im:
        return im.size


def _fit_caps(
    edge: tuple[int, int, int, int], w: int, h: int
) -> tuple[int, int, int, int] | None:
    """Shrink caps that exceed the image proportionally, or None if they fit.

    E16 tolerates overlapping caps — e13's dragbar declares ``__EDGE_SCALING
    70 70 5 5`` on a 121-px-wide image and still renders the E-logo cap at
    natural size — so degrading to a whole-image stretch smears the cap art
    across the panel (verified live 2026-08-31). Shrinking both caps by the
    same factor keeps the cap art pinned and crisp. Caps that sum to
    EXACTLY the image size are left alone: that is authored cap-only art
    (the middle legitimately has zero source pixels).
    """
    left, right, top, bottom = edge
    changed = False
    if left + right > w:
        f = w / (left + right)
        left, right = int(left * f), int(right * f)
        changed = True
    if top + bottom > h:
        f = h / (top + bottom)
        top, bottom = int(top * f), int(bottom * f)
        changed = True
    return (left, right, top, bottom) if changed else None


# --------------------------------------------------------------------- #
# Builders — one per shipped SVG; None means "don't ship, Breeze wins"
# --------------------------------------------------------------------- #


def _hex(rgb: RGB) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _panel_tint(theme: Theme) -> tuple[RGB, str]:
    """(tint rgb, human-readable source) for the flat panel.

    Dominant color of the E16 panel-source art when present (keeps theme
    character), else the sampled scheme's Window background.
    """
    src = _panel_source(theme)
    path = _state_image(src, "normal")
    if path is not None and src is not None:
        rgb = extract_dominant(path)
        if rgb is not None:
            return rgb, f"iclass {src.name} art"
    scheme = theme.scheme if theme.scheme is not None else default_scheme()
    return scheme.window.background_normal, "the sampled color scheme"


def _panel_svg(theme: Theme, alpha: float) -> ET.Element:
    """Flat 3x3 grid of rects, all filled with the tint at *alpha*.

    ``opacity:`` in the rect's ``style`` is the FrameSvg alpha encoding
    Breeze itself uses (its panel center is ``opacity:0.85;fill:...``);
    it is omitted entirely at alpha 1, matching Breeze's solid variant
    byte-shape. The unprefixed set serves every orientation —
    ``adjustPrefix()`` falls back to unprefixed when a ``north-``/… set
    is absent — and a flat tint has no orientation to encode.
    """
    tint, _ = _panel_tint(theme)
    fill = f"fill:{_hex(tint)}"
    if alpha != 1:
        fill += f";opacity:{alpha}"
    canvas = _Canvas()
    offsets = (0, _PANEL_EDGE, _PANEL_EDGE + _PANEL_CENTER)
    sizes = (_PANEL_EDGE, _PANEL_CENTER, _PANEL_EDGE)
    for row in range(3):
        for col in range(3):
            ET.SubElement(
                canvas.root,
                f"{{{SVG_NS}}}rect",
                {
                    "id": _GRID[row][col],
                    "x": str(offsets[col]),
                    "y": str(canvas.y + offsets[row]),
                    "width": str(sizes[col]),
                    "height": str(sizes[row]),
                    "style": fill,
                },
            )
    side = 2 * _PANEL_EDGE + _PANEL_CENTER
    canvas.advance(side, side)
    margin = (PANEL_MARGIN_REF, PANEL_MARGIN_REF, PANEL_MARGIN_REF, PANEL_MARGIN_REF)
    _margin_hints(canvas, "", margin, theme.scale)
    return canvas.finish()


def build_panel_background(theme: Theme) -> ET.Element:
    """``widgets/panel-background.svg`` — a flat translucent tint.

    Deliberately NOT the dragbar/iconbox art: E16 authors baked wordmarks
    into exactly the cap regions ``_fit_caps`` preserves, and stretched
    across a Plasma panel they bury every widget (module docstring). The
    tint keeps the theme's color character while the wallpaper shows
    through; never returns None — a colors-only theme still gets a
    scheme-tinted panel.
    """
    tint, source = _panel_tint(theme)
    svg = _panel_svg(theme, PANEL_ALPHA)
    theme.notes.append(
        f"plasmastyle: panel background is a translucent tint rgb{tint} "
        f"(alpha {PANEL_ALPHA}) of {source} — E16 dragbar art carries "
        "baked-in wordmarks that make panel widgets unreadable"
    )
    return svg


def build_dialog_background(theme: Theme) -> ET.Element | None:
    """``dialogs/background.svg`` (applet popups, Kickoff, calendar)."""
    src = _dialog_source(theme)
    if src is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "", src, "normal", hints=True)
    theme.notes.append(
        f"plasmastyle: popup/dialog background from iclass {src.name}; no "
        "shadow set is shipped, so popups render shadowless (E16 drew none)"
    )
    return canvas.finish()


def build_tooltip(theme: Theme) -> ET.Element | None:
    """``widgets/tooltip.svg`` from ``TT_MAIN``."""
    src = _iclass_with_art(theme, "TT_MAIN")
    if src is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "", src, "normal", hints=True)
    theme.notes.append(f"plasmastyle: tooltip background from iclass {src.name}")
    return canvas.finish()


def build_button(theme: Theme) -> ET.Element | None:
    """``widgets/button.svg`` from ``DIALOG_BUTTON``.

    ``focus-`` reuses the hilited art — E16 has no focus-ring concept. No
    ``toolbutton-*`` sets: PC3 falls back per-prefix to Breeze for those.
    """
    src = _iclass_with_art(theme, "DIALOG_BUTTON")
    if src is None:
        return None
    canvas = _Canvas()
    for prefix, state in (
        ("normal-", "normal"),
        ("hover-", "hover"),
        ("pressed-", "pressed"),
        ("focus-", "hover"),
    ):
        _emit_set(theme, canvas, prefix, src, state, hints=True)
    theme.notes.append(
        f"plasmastyle: widget buttons from iclass {src.name} "
        "(focus ring reuses the hilited art)"
    )
    return canvas.finish()


def _viewitem_caps(
    edge: tuple[int, int, int, int], w: int, h: int
) -> tuple[int, int, int, int]:
    """Synthetic caps for highlight art, in source ref px.

    E16 only ever stretched menu-item art HORIZONTALLY — an item's height
    equals the art's height — but Plasma paints ``widgets/viewitem`` over
    grid cells and wide dropdown rows, stretching both axes. A glow pill
    stretched whole (MENU_SEL commonly declares ``__EDGE_SCALING 0 0 0 0``)
    smears into a blurry bright blob (verified live on e13's Kickoff,
    2026-08-31). Pinning caps at roughly the art's cross-section radius
    keeps the pill's rounded ends and its vertical shading crisp at any
    rendered size; only the near-uniform middle band stretches. Declared
    caps larger than the radius are kept.
    """
    radius = max(1, (min(w, h) - 2) // 2)
    left, right, top, bottom = edge
    return (
        min(max(left, radius), (w - 1) // 2),
        min(max(right, radius), (w - 1) // 2),
        min(max(top, radius), (h - 1) // 2),
        min(max(bottom, radius), (h - 1) // 2),
    )


def build_viewitem(theme: Theme) -> ET.Element | None:
    """``widgets/viewitem.svg`` from ``MENU_SEL``.

    ``normal-`` is emitted only when MENU_SEL has explicit normal art —
    an always-painted normal set would draw menu-row chrome under every
    unhovered list row, which most E16 themes leave to the background.
    All sets use :func:`_viewitem_caps` in place of the declared edge —
    see its docstring for why the declared edge cannot be trusted here.
    """
    src = theme.iclasses.get("MENU_SEL")
    if _state_image(src, "hover") is None or src is None:
        return None
    canvas = _Canvas()
    has_normal_art = (src.normal is not None and src.normal.is_file()) or (
        src.normal_active is not None and src.normal_active.is_file()
    )
    if has_normal_art:
        _emit_set(theme, canvas, "normal-", src, "normal", edge_override=_viewitem_caps)
    _emit_set(theme, canvas, "hover-", src, "hover", edge_override=_viewitem_caps)
    _emit_set(theme, canvas, "selected-", src, "selected", edge_override=_viewitem_caps)
    # Literal "+" in the id — FrameSvg's combined-state prefix.
    _emit_set(
        theme, canvas, "selected+hover-", src, "selected", edge_override=_viewitem_caps
    )
    theme.notes.append(
        f"plasmastyle: menu/list selection from iclass {src.name}; caps "
        "pinned at the art's cross-section so highlights stay crisp at "
        "grid-cell sizes (E16 never stretched item height)"
    )
    return canvas.finish()


def build_scrollbar(theme: Theme) -> ET.Element | None:
    """``widgets/scrollbar.svg`` from the ICONBOX scrollbar art.

    One slider set (from the vertical knob when it has art) serves both
    orientations — FrameSvg stretches it either way; noted as an
    approximation. ``hint-scrollbar-size`` carries the scaled knob
    thickness.
    """
    knob = _iclass_with_art(
        theme, "ICONBOX_SCROLLBAR_KNOB_VERTICAL", "ICONBOX_SCROLLBAR_KNOB_HORIZONTAL"
    )
    if knob is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "slider-", knob, "normal")
    _emit_set(theme, canvas, "mouseover-slider-", knob, "hover")
    base_v = _iclass_with_art(theme, "ICONBOX_SCROLLBAR_BASE_VERTICAL")
    if base_v is not None:
        _emit_set(theme, canvas, "background-vertical-", base_v, "normal")
    base_h = _iclass_with_art(theme, "ICONBOX_SCROLLBAR_BASE_HORIZONTAL")
    if base_h is not None:
        _emit_set(theme, canvas, "background-horizontal-", base_h, "normal")

    # Knob thickness: the across-the-track dimension of the knob art (width
    # of a vertical knob, height of a horizontal one), CLAMPED to
    # SCROLLBAR_MAX_REF_THICKNESS — see that constant for why the image's
    # own dimension cannot be trusted as a widget width.
    knob_path = _state_image(knob, "normal")
    assert knob_path is not None  # _iclass_with_art guarantees it
    src_w, src_h = _source_size(knob_path)
    across = src_w if knob.name.endswith("VERTICAL") else src_h
    if across > SCROLLBAR_MAX_REF_THICKNESS:
        theme.notes.append(
            f"plasmastyle: scrollbar knob art is {across} ref px across; "
            f"track thickness clamped to {SCROLLBAR_MAX_REF_THICKNESS} "
            "(E16 stretched knob art into a slim track)"
        )
        across = SCROLLBAR_MAX_REF_THICKNESS
    size = max(1, scale_px(across, theme.scale))
    ET.SubElement(
        canvas.root,
        f"{{{SVG_NS}}}rect",
        {
            "id": "hint-scrollbar-size",
            "x": "0",
            "y": str(canvas.y),
            "width": str(size),
            "height": str(size),
            "style": "opacity:0",
        },
    )
    canvas.advance(size, size)
    theme.notes.append(
        f"plasmastyle: scrollbar slider from iclass {knob.name}; the one "
        "set serves both orientations (E16 kept separate art per axis)"
    )
    return canvas.finish()


def build_arrows(theme: Theme) -> ET.Element | None:
    """``widgets/arrows.svg`` from the four ``ICONBOX_ARROW_*`` iclasses.

    All four or skip: Plasma's fallback is per-FILE, so a partial file
    would render nothing at all for the missing directions.
    """
    sources: dict[str, Path] = {}
    for element, name in _ARROW_SOURCES:
        path = _state_image(theme.iclasses.get(name), "normal")
        if path is None:
            return None
        sources[element] = path
    canvas = _Canvas()
    x = 0
    row_h = 0
    for element, _ in _ARROW_SOURCES:
        img = _load_scaled(sources[element], theme.scale)
        g = ET.SubElement(canvas.root, f"{{{SVG_NS}}}g", {"id": element})
        _embed_image(g, img, x, canvas.y)
        x += img.width + _GAP
        row_h = max(row_h, img.height)
    canvas.advance(x, row_h)
    theme.notes.append(
        "plasmastyle: scroll/expander arrows from the ICONBOX_ARROW_* iclasses"
    )
    return canvas.finish()


def _pager_set(
    theme: Theme,
    canvas: _Canvas,
    prefix: str,
    thumb: Image.Image,
    frame_spec: IClassSpec | None,
    fallback: RGB,
) -> str:
    """One pager 9-part set: a frame around the wallpaper thumbnail.

    The frame comes from *frame_spec*'s art when it has one with non-zero
    caps (the eight border cells are the art's slices at natural size —
    FrameSvg only reads per-id bounding boxes, so art-sized edges around a
    thumb-sized center are legal); a missing spec, missing art, or a
    ``(0,0,0,0)`` edge (PAGER_SEL is commonly stretched whole) falls back
    to eight 1-ref-px *fallback*-colored rect strokes. The center cell is
    always the thumbnail ``<image>``. Returns the human-readable frame
    source for the caller's note.
    """
    path = _state_image(frame_spec, "normal")
    if path is not None and frame_spec is not None:
        img = _load_scaled(path, theme.scale)
        src_w, src_h = _source_size(path)
        edge = frame_spec.edge_scaling
        fitted = _fit_caps(edge, src_w, src_h)
        if fitted is not None:
            edge = fitted
        left, right, top, bottom = _scaled_caps(edge, src_w, src_h, theme.scale)
        if (left, right, top, bottom) != (0, 0, 0, 0):
            regions = slice_9patch(img, left, right, top, bottom)
            by_name = {
                "topleft": regions.topleft, "top": regions.top,
                "topright": regions.topright, "left": regions.left,
                "right": regions.right, "bottomleft": regions.bottomleft,
                "bottom": regions.bottom, "bottomright": regions.bottomright,
            }
            art_widths = (left, img.width - left - right, right)
            art_heights = (top, img.height - top - bottom, bottom)
            xs = (0, left, left + thumb.width)
            ys = (0, top, top + thumb.height)
            for row in range(3):
                for col in range(3):
                    if row == 1 and col == 1:
                        continue
                    if art_widths[col] <= 0 or art_heights[row] <= 0:
                        continue
                    name = _GRID[row][col]
                    g = ET.SubElement(
                        canvas.root, f"{{{SVG_NS}}}g", {"id": f"{prefix}{name}"}
                    )
                    _embed_image(g, by_name[name], xs[col], canvas.y + ys[row])
            g = ET.SubElement(
                canvas.root, f"{{{SVG_NS}}}g", {"id": f"{prefix}center"}
            )
            _embed_image(g, thumb, left, canvas.y + top)
            canvas.advance(left + thumb.width + right, top + thumb.height + bottom)
            return f"iclass {frame_spec.name} art"

    stroke = max(1, scale_px(PAGER_FRAME_REF, theme.scale))
    xs = (0, stroke, stroke + thumb.width)
    ys = (0, stroke, stroke + thumb.height)
    widths = (stroke, thumb.width, stroke)
    heights = (stroke, thumb.height, stroke)
    for row in range(3):
        for col in range(3):
            if row == 1 and col == 1:
                continue
            ET.SubElement(
                canvas.root,
                f"{{{SVG_NS}}}rect",
                {
                    "id": f"{prefix}{_GRID[row][col]}",
                    "x": str(xs[col]),
                    "y": str(canvas.y + ys[row]),
                    "width": str(widths[col]),
                    "height": str(heights[row]),
                    "style": f"fill:{_hex(fallback)}",
                },
            )
    g = ET.SubElement(canvas.root, f"{{{SVG_NS}}}g", {"id": f"{prefix}center"})
    _embed_image(g, thumb, stroke, canvas.y + stroke)
    canvas.advance(2 * stroke + thumb.width, 2 * stroke + thumb.height)
    return "a scheme-color stroke"


def build_pager(theme: Theme, wallpaper_image: Path | None) -> ET.Element | None:
    """``widgets/pager.svg`` — each desktop cell a wallpaper miniature.

    Real E16 pagers showed the live desk; a static miniature of the theme's
    default wallpaper is the closest Plasma equivalent. Skipped entirely
    when the conversion ships no wallpaper — Breeze's pager (re-tinted by
    this package's ``colors``) beats empty frames. The window rects inside
    cells come from Kirigami.Theme, which the bundled colors file already
    governs — no SVG work needed there. No ``hint-tile-center``, no margin
    hints (cells must stretch, and the applet spaces cells itself).
    """
    if wallpaper_image is None:
        theme.notes.append(
            "plasmastyle: no wallpaper to miniature; widgets/pager left to "
            "the Breeze fallback"
        )
        return None
    with Image.open(wallpaper_image) as im:
        thumb = im.convert("RGB")
    if thumb.width > PAGER_THUMB_WIDTH:
        # LANCZOS is the sanctioned wallpaper carve-out (photographic
        # sources); a smaller source (likely tiled pixel art) is never
        # upscaled — it embeds at native size.
        thumb = thumb.resize(
            (
                PAGER_THUMB_WIDTH,
                max(1, round(thumb.height * PAGER_THUMB_WIDTH / thumb.width)),
            ),
            Image.Resampling.LANCZOS,
        )
    scheme = theme.scheme if theme.scheme is not None else default_scheme()
    active_art = theme.iclasses.get("PAGER_SEL")
    normal_art = theme.iclasses.get("PAGER_BACKGROUND")
    active_fallback = scheme.selection.background_normal
    normal_fallback = _at_lightness(scheme.window.background_normal, 0.12)
    canvas = _Canvas()
    descs: dict[str, str] = {}
    for prefix, factor in _PAGER_BRIGHTNESS.items():
        cell = ImageEnhance.Brightness(thumb).enhance(factor)
        spec = normal_art if prefix == "normal-" else active_art
        fallback = normal_fallback if prefix == "normal-" else active_fallback
        descs[prefix] = _pager_set(theme, canvas, prefix, cell, spec, fallback)
    theme.notes.append(
        "plasmastyle: pager desktops miniature the default wallpaper "
        f"{wallpaper_image.name} (normal dimmed, active full brightness); "
        f"active frame from {descs['active-']}; normal frame from "
        f"{descs['normal-']}"
    )
    return canvas.finish()


#: (relative path, builder) in package order. Also the mirror census.
_BUILDERS: tuple[tuple[str, Callable[[Theme], ET.Element | None]], ...] = (
    (PANEL_SVG, build_panel_background),
    (DIALOG_SVG, build_dialog_background),
    (TOOLTIP_SVG, build_tooltip),
    (BUTTON_SVG, build_button),
    (VIEWITEM_SVG, build_viewitem),
    (SCROLLBAR_SVG, build_scrollbar),
    (ARROWS_SVG, build_arrows),
)


# --------------------------------------------------------------------- #
# Bundled colors file
# --------------------------------------------------------------------- #


def _fg_for(
    candidate: RGB | None,
    fallback: RGB,
    backgrounds: tuple[RGB, ...],
) -> tuple[RGB, bool]:
    """Pick a foreground legible on EVERY background in *backgrounds*.

    Returns ``(color, forced)``: *candidate* (or *fallback*) when it clears
    ``MIN_CONTRAST`` against all of them, else the one of black/white that
    maximizes the minimum contrast, with ``forced=True`` so the caller can
    note the override.
    """
    fg = candidate if candidate is not None else fallback
    if all(contrast_ratio(fg, bg) >= MIN_CONTRAST for bg in backgrounds):
        return fg, False
    white, black = (255, 255, 255), (0, 0, 0)
    best = max(
        (white, black), key=lambda c: min(contrast_ratio(c, bg) for bg in backgrounds)
    )
    return best, True


def _regroup(group: ColorGroup, bg: RGB | None, fg: RGB) -> ColorGroup:
    """*group* with a new bg/fg, derived fields recomputed for legibility."""
    background = bg if bg is not None else group.background_normal
    return replace(
        group,
        background_normal=background,
        background_alternate=(
            background if bg is not None else group.background_alternate
        ),
        foreground_normal=fg,
        foreground_inactive=_dimmed(fg, background),
        foreground_active=_legible(group.foreground_active, background),
    )


def _tclass_fg(theme: Theme, name: str, field: str = "fg_normal") -> RGB | None:
    t = theme.tclasses.get(name)
    return getattr(t, field) if t is not None else None


def style_scheme(theme: Theme, *, shipped: frozenset[str]) -> ColorScheme:
    """``theme.scheme`` with the panel-facing groups re-anchored to the art
    this package actually ships.

    Art-derived background overrides fire only for surfaces whose SVG
    shipped (the ``shipped`` gate) — the bundled ``colors`` file is what
    tints the *Breeze fallback* art, so a group whose art we ship must
    match that art, and a group whose art we don't must stay on the
    sampled scheme. Text prefers the theme's own tclass colors
    (``MENU_TEXT``/``TT_TEXT``/``DIALOG_*``), WCAG-guarded; every override
    appends a ``plasmastyle:`` note naming its source.
    """
    scheme = theme.scheme if theme.scheme is not None else default_scheme()

    # The panel is a flat tint, so the color actually painted IS the tint —
    # not the raw art's dominant (they agree when art exists, but the tint
    # falls back to the scheme for colors-only themes).
    panel_bg: RGB | None = _panel_tint(theme)[0] if PANEL_SVG in shipped else None

    # Colors:Window — panel + popup text share this group.
    dialog_src = _dialog_source(theme) if DIALOG_SVG in shipped else None
    dialog_bg: RGB | None = None
    if dialog_src is not None:
        path = _state_image(dialog_src, "normal")
        if path is not None:
            dialog_bg = extract_dominant(path)
    if dialog_bg is not None or panel_bg is not None:
        fg_source = "MENU_TEXT"
        if dialog_src is not None and dialog_src.name == "DIALOG":
            fg_source = "DIALOG_WIDGET_TEXT"
        candidate = _tclass_fg(theme, fg_source)
        guards = tuple(
            bg
            for bg in (
                dialog_bg if dialog_bg is not None else scheme.window.background_normal,
                panel_bg,
            )
            if bg is not None
        )
        fg, forced = _fg_for(candidate, scheme.window.foreground_normal, guards)
        scheme = replace(scheme, window=_regroup(scheme.window, dialog_bg, fg))
        theme.notes.append(
            "plasmastyle: colors Window (panel/popup) "
            + (
                f"background from {dialog_src.name} art; "
                if dialog_bg is not None and dialog_src is not None
                else "background kept from the sampled scheme; "
            )
            + (
                f"text forced to rgb{fg} for contrast over the shipped art"
                if forced
                else f"text from tclass {fg_source}"
            )
        )

    # Colors:View — reading surfaces behind menus/lists.
    menu_fg = _tclass_fg(theme, "MENU_TEXT")
    if menu_fg is not None:
        fg = _legible(menu_fg, scheme.view.background_normal)
        if fg != scheme.view.foreground_normal:
            scheme = replace(scheme, view=_regroup(scheme.view, None, fg))
            theme.notes.append(
                "plasmastyle: colors View text from tclass MENU_TEXT"
                + ("" if fg == menu_fg else f" (guarded to rgb{fg})")
            )

    # Colors:Tooltip.
    if TOOLTIP_SVG in shipped:
        src = _iclass_with_art(theme, "TT_MAIN")
        path = _state_image(src, "normal")
        bg = extract_dominant(path) if path is not None else None
        if bg is not None:
            fg, forced = _fg_for(
                _tclass_fg(theme, "TT_TEXT"),
                scheme.tooltip.foreground_normal, (bg,),
            )
            scheme = replace(scheme, tooltip=_regroup(scheme.tooltip, bg, fg))
            theme.notes.append(
                "plasmastyle: colors Tooltip background from TT_MAIN art; text "
                + (f"forced to rgb{fg} for contrast" if forced else "from tclass TT_TEXT")
            )

    # Colors:Selection — MENU_SEL hover art; fg_active is the closest thing
    # the IR carries to a "selected text" color (approximation).
    if VIEWITEM_SVG in shipped:
        sel = theme.iclasses.get("MENU_SEL")
        path = _state_image(sel, "hover")
        bg = extract_dominant(path) if path is not None else None
        if bg is not None:
            fg, forced = _fg_for(
                _tclass_fg(theme, "MENU_TEXT", "fg_active"),
                scheme.selection.foreground_normal, (bg,),
            )
            scheme = replace(scheme, selection=_regroup(scheme.selection, bg, fg))
            theme.notes.append(
                "plasmastyle: colors Selection from MENU_SEL hover art; text "
                "approximated from MENU_TEXT's active color"
                + (f", forced to rgb{fg} for contrast" if forced else "")
            )

    # Colors:Button.
    if BUTTON_SVG in shipped:
        src = _iclass_with_art(theme, "DIALOG_BUTTON")
        path = _state_image(src, "normal")
        bg = extract_dominant(path) if path is not None else None
        if bg is not None:
            candidate = _tclass_fg(theme, "DIALOG_BUTTON") or _tclass_fg(
                theme, "DIALOG_WIDGET_TEXT"
            )
            fg, forced = _fg_for(candidate, scheme.button.foreground_normal, (bg,))
            scheme = replace(scheme, button=_regroup(scheme.button, bg, fg))
            theme.notes.append(
                "plasmastyle: colors Button from DIALOG_BUTTON art"
                + (f"; text forced to rgb{fg} for contrast" if forced else "")
            )

    return scheme


# --------------------------------------------------------------------- #
# Package writer
# --------------------------------------------------------------------- #


def _write_metadata(theme: Theme, out_dir: Path) -> None:
    """``metadata.json``: KPlugin block + top-level ``X-Plasma-API`` "5.0"
    (the shape every theme on the reference machine ships, Plasma-6 Breeze
    included); ``KPackageStructure`` added for symmetry with the
    Look-and-Feel writer. ``Version`` keys the SVG cache
    (``plasma_theme_<id>*.kcache``) — apply clears that cache explicitly
    because a re-convert never bumps this Version.
    """
    meta = {
        "KPackageStructure": "Plasma/Theme",
        "KPlugin": {
            "Authors": [{"Name": theme.author or "unknown"}],
            "EnabledByDefault": True,
            "Id": plugin_id(theme.name),
            "License": "GPL",
            "Name": f"{theme.display_name} (themey)",
            "Version": "1.0",
        },
        "X-Plasma-API": "5.0",
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, indent=4, sort_keys=True) + "\n"
    )


def write(
    theme: Theme, out_dir: Path, *, default_wallpaper_image: Path | None = None
) -> PlasmaStyle:
    """Write the Plasma Style package for *theme* under *out_dir*.

    ``out_dir``'s basename MUST be ``slug.plugin_id(theme.name)`` — the
    dir name is the ``plasmarc [Theme] name=`` value Plasma matches on.
    A single SVG whose source art cannot be read skips that one file with
    a ``plasmastyle:`` note; an EMPTY SVG set is legitimate (colors-only
    package, like breeze-dark). Any other failure removes ``out_dir`` and
    raises :class:`PlasmaStyleError`. *default_wallpaper_image* is the
    already-deployed default wallpaper's image file — the pager miniature
    source (pager skipped when None).
    """
    pkg_id = plugin_id(theme.name)
    if out_dir.name != pkg_id:
        raise PlasmaStyleError(
            f"out_dir basename must be {pkg_id!r} (got {out_dir.name!r}) — "
            "the dir name is the plasmarc Theme name Plasma matches on"
        )
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_metadata(theme, out_dir)
        write_desktop(out_dir / "plasmarc", _PACKAGE_PLASMARC)

        # Pager rides the builder loop so it inherits the skip-on-bad-image
        # handling and the solid/opaque mirroring (its content is opaque).
        builders = (
            *_BUILDERS,
            (PAGER_SVG, lambda t: build_pager(t, default_wallpaper_image)),
        )
        shipped: list[str] = []
        for rel, builder in builders:
            try:
                svg = builder(theme)
            except (OSError, ValueError) as exc:
                theme.notes.append(f"plasmastyle: skipped {rel}: {exc}")
                continue
            if svg is None:
                continue
            out = out_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            ET.ElementTree(svg).write(out, xml_declaration=True, encoding="utf-8")
            shipped.append(rel)

        # Byte-identical mirrors: Panel.qml loads solid/ for opaque panels
        # (and opaque/ exists as the same contract for other consumers); a
        # missing mirror would fall back to Breeze's art there. The ONE
        # exception: the panel's base rendition is translucent, so its
        # mirrors are re-rendered at alpha 1 — AdaptiveTransparency swaps
        # to solid/ when a window touches the panel, and that variant must
        # be genuinely opaque.
        for rel in shipped:
            for variant in ("solid", "opaque"):
                dst = out_dir / variant / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if rel == PANEL_SVG:
                    ET.ElementTree(_panel_svg(theme, 1.0)).write(
                        dst, xml_declaration=True, encoding="utf-8"
                    )
                else:
                    shutil.copyfile(out_dir / rel, dst)

        scheme = style_scheme(theme, shipped=frozenset(shipped))
        write_desktop(
            out_dir / "colors",
            build_sections(scheme, stem=pkg_id, display_name=theme.display_name),
        )
    except PlasmaStyleError:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise PlasmaStyleError(f"could not write Plasma Style {pkg_id}: {exc}") from exc

    log.info(
        "Plasma Style %s: %d svg(s) shipped (%s)",
        pkg_id, len(shipped), ", ".join(shipped) or "colors-only",
    )
    return PlasmaStyle(id=pkg_id, dir=out_dir, shipped=tuple(shipped))
