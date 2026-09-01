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
  *Breeze's* solid art next to our chrome. The ONE exception is the TINT
  rendition of the panel background: that base is a translucent flat tint
  (``PANEL_ALPHA``), so its ``solid/``/``opaque/`` mirrors are re-rendered
  at alpha 1 — AdaptiveTransparency swaps to ``solid/`` when a window
  touches the panel, and that variant must be genuinely opaque. An art
  panel is opaque E16 art and mirrors byte-identically like everything
  else.
* The panel background ships real dragbar/iconbox art when a candidate
  passes two guards (:func:`_panel_art_guard`): not shaped, and cap sums ≤
  ``PANEL_MAX_REF_CAPS`` per axis. The guards exist because E16 authors
  baked wordmarks ("ENLIGHTENMENT", theme logos) into the CAP regions —
  stretched across a 40 px Plasma panel they make every widget unreadable
  (verified live 2026-08-31) — so wordmark-sized caps fall through to the
  next candidate and ultimately to a flat translucent tint of the art's
  dominant color (scheme fallback), letting the wallpaper show through.
  The art panel's middle STRETCHES like every E16 iclass middle (no
  ``hint-tile-center``; tiling repeated photographic troughs across the
  bar — HandOfGod, NorthernLights, live 2026-09-01); a vertical bar
  iclass adds ``west-``/``east-`` sets for the left-edge furniture panels.
* 9-part sets use FrameSvg's element names (``topleft`` … ``bottomright``,
  optionally ``<prefix>-``-prefixed); zero-extent slices are simply not
  emitted (FrameSvg then reports a 0 border, which is correct — the Aliens
  dragbar's ``133 28 0 0`` edge yields a left/center/right-only set) —
  EXCEPT the center: FrameSvg's ``hasElementPrefix`` checks exactly
  ``<prefix>center`` and paints NOTHING for a center-less set, so caps
  that consume the whole image are shaved one px to keep a real center
  (:func:`_frame_group`).
  ``hint-tile-center`` is never emitted — E16 stretches middles
  everywhere, and FrameSvg's center default already is stretch. The same
  E16 rule covers borders:
  FrameSvg tiles border elements by DEFAULT, so every file containing a
  sliced-art frame set carries one unprefixed ``hint-stretch-borders``
  (gradient edge art visibly repeats when tiled — live HandOfGod pager,
  2026-08-31); flat-rect sets are stretch/tile invariant and skip it.
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
  Middles are never pre-stretched — FrameSvg stretches at runtime. The
  ONE scaling exception: art whose caps sum past
  ``SURFACE_MAX_REF_CHROME`` per axis renders at source scale (see that
  constant — giant frame art like HandOfGod's tooltip cloud must not be
  doubled on top of Plasma-sized content).

State map (whole module): E16 ``normal`` → ``normal``, ``hilited`` →
``hover``, ``clicked`` → ``pressed``/``selected``; a missing state reuses
``normal`` at generate time, and non-``_active`` variants are preferred
(these are non-window surfaces). The ONE inversion: in E16's dialog
widgets ``__NORMAL_ACTIVE`` means CHECKED, not window-active — every
fixture authors the checked box/radio as ``*_ACTIVE`` art — so the
``checked`` chain prefers ``*_active`` fields and deliberately never
falls back to ``normal`` (a checked mark reusing unchecked art makes the
states indistinguishable, worse than the Breeze fallback; those builders
skip their file instead).

Deliberately NOT shipped even where E16 has art: ``widgets/lineedit.svg``
(E16 dialogs have no text-entry widget; focus/hover would be invented),
``widgets/switch.svg`` (no E16 counterpart), the ``SETTINGS_*_AREA``
iclasses, and the slider knobs' ``__CLICKED`` art (Plasma's slider has no
pressed-handle element).

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

from PIL import Image

from themey.analyze.colors import (
    MIN_CONTRAST,
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

#: ``Kirigami.Units.smallSpacing`` — Plasma's Panel.qml pads panel content
#: by ``min(fixedMargins.side + smallSpacing, spacingAtMinSize)`` per side
#: (Plasma 6.6 Panel.qml l. 59-62), so a margin hint of ``cap − 4`` lands
#: the effective padding exactly on the cap art's inner edge.
_PANEL_SMALL_SPACING = 4

#: Cell geometry of the flat 3x3 panel grid: 4 px edges, 24 px center
#: (32 px tile, mirroring Breeze's edge/center proportions; cosmetic —
#: FrameSvg reads border thickness from the edge cells' size, and a 4 px
#: flat border is invisible against the identical-color center).
_PANEL_EDGE, _PANEL_CENTER = 4, 24

#: Relative SVG paths (also the ``shipped`` vocabulary and the mirror set).
PANEL_SVG = "widgets/panel-background.svg"
PAGER_SVG = "widgets/pager.svg"
TASKS_SVG = "widgets/tasks.svg"
DIALOG_SVG = "dialogs/background.svg"
TOOLTIP_SVG = "widgets/tooltip.svg"
BUTTON_SVG = "widgets/button.svg"
VIEWITEM_SVG = "widgets/viewitem.svg"
SCROLLBAR_SVG = "widgets/scrollbar.svg"
ARROWS_SVG = "widgets/arrows.svg"
CHECKMARKS_SVG = "widgets/checkmarks.svg"
RADIOBUTTON_SVG = "widgets/radiobutton.svg"
SLIDER_SVG = "widgets/slider.svg"
LINE_SVG = "widgets/line.svg"
FRAME_SVG = "widgets/frame.svg"

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
    # dialog-widget-only: __NORMAL_ACTIVE means CHECKED for the
    # DIALOG_WIDGET check/radio iclasses (module docstring). Deliberately
    # does NOT terminate on normal — a checked mark falling back to
    # unchecked art makes the states indistinguishable, so _state_image
    # returning None means "omit the element / skip the file".
    "checked": ("normal_active", "hilited_active", "clicked", "clicked_active"),
}

#: FrameSvg 9-part element names by (row, col) of the slice grid.
_GRID = (
    ("topleft", "top", "topright"),
    ("left", "center", "right"),
    ("bottomleft", "bottom", "bottomright"),
)

#: Ref-px ceiling for a surface's fixed chrome per axis (cap sums, after
#: ``_fit_caps``). Art whose caps already sum past this at SOURCE size is
#: "the art IS the surface" chrome — HandOfGod's 249x126 tooltip cloud
#: declares 20-25 ref-px caps, so its frame alone is ~40-47 px per axis
#: before any content. E16 rendered such art at 1x around tiny text;
#: multiplying it by ``theme.scale`` doubled an already-imposing frame
#: around Plasma's much larger tooltip content (live HandOfGod tooltip,
#: 2026-08-31). Such art (and its margins) renders at source scale
#: instead; it is never downscaled below 1x — a giant frame at 1x is the
#: theme's authored look. Pixel-art chrome (a few ref px) is unaffected.
SURFACE_MAX_REF_CHROME = 32

#: Ref-px ceiling for the scrollbar track thickness (``hint-scrollbar-size``).
#: E16 stretched knob art INTO a slim configured track — the image's own
#: width is NOT the widget width (e13's vertical knob image is ~28 ref px,
#: which rendered as a 57 px-wide scrollbar column through Kickoff, verified
#: live 2026-08-31). 12 ref px ≈ Breeze's logical scrollbar thickness.
SCROLLBAR_MAX_REF_THICKNESS = 12

#: Ref-px ceiling for the separator rule's thickness. LiteGnome authors a
#: real 120x4 hline; Aliens/e13 point DIALOG_WIDGET_SEPARATOR at a ~64 px
#: bevel box that E16 squeezed into a thin rule at layout time — the same
#: image-dimension-is-not-widget-size trap SCROLLBAR_MAX_REF_THICKNESS
#: documents. The art is squeezed (NEAREST) to this thickness.
LINE_MAX_REF_THICKNESS = 4

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


def _state_attr(spec: IClassSpec | None, state: str) -> tuple[str, Path] | None:
    """``(state attribute, image)`` — the first existing image for *state*
    on *spec* along its fallback chain. The attribute is what
    ``IClassSpec.edge_for`` needs: E16's ``__EDGE_SCALING`` is per state."""
    if spec is None:
        return None
    for field in _STATE_CHAINS[state]:
        p = getattr(spec, field)
        if p is not None and p.is_file():
            return field, p
    return None


def _state_image(spec: IClassSpec | None, state: str) -> Path | None:
    """First existing image for *state* on *spec* along its fallback chain."""
    found = _state_attr(spec, state)
    return found[1] if found is not None else None


def _iclass_with_art(theme: Theme, *names: str) -> IClassSpec | None:
    """First of *names* present in ``theme.iclasses`` with normal-state art."""
    for name in names:
        spec = theme.iclasses.get(name)
        if spec is not None and _state_image(spec, "normal") is not None:
            return spec
    return None


#: Candidate iclasses for the panel's art, horizontal/vertical, in order.
_PANEL_ART_SOURCES: tuple[str, ...] = (
    "DESKTOP_DRAGBUTTON_HORIZ", "ICONBOX_HORIZONTAL", "DEFAULT_DOCK_BUTTON",
)
_PANEL_VERT_SOURCES: tuple[str, ...] = (
    "DESKTOP_DRAGBUTTON_VERT", "ICONBOX_VERTICAL",
)

#: Ref-px ceiling for the panel art's cap sum per axis. Caps become fixed
#: FrameSvg borders, and themey's furniture panels are fit-content — a
#: 133-px wordmark cap (Aliens' dragbar) would be a giant dead margin
#: swallowing the whole iconbox. Census: Aliens dragbar 133+28 rejected →
#: its ICONBOX_HORIZONTAL (4/4) accepted; e13 dragbar 60/60 (post-_fit_caps)
#: rejected → iconbox trough (5/5); OPENSTEP DragBar 24+2 accepted (the
#: NeXT cube stays pinned left, exactly its E16 look).
PANEL_MAX_REF_CAPS = 32


def _panel_source(theme: Theme) -> IClassSpec | None:
    return _iclass_with_art(theme, *_PANEL_ART_SOURCES)


#: Fraction of sub-128-alpha pixels above which art counts as SHAPED —
#: E16's 1-bit shape mask cut the WINDOW to the art's outline, so heavily
#: transparent art was never a rectangular texture. Stretched over a
#: rectangular Plasma popup its transparent regions become see-through
#: holes (wallpaper blurring through) while the opaque art smears huge
#: (Aliens' bone-rod MENU_BG over the Brightness popup, verified live
#: 2026-08-31). 10% cleanly splits the fixture census: Aliens MENU_BG is
#: 34% transparent, every other MENU_BG/DIALOG ≤ 2% (rounded ends).
SHAPED_ART_MAX_TRANSPARENT = 0.10


def _transparent_fraction(path: Path) -> float:
    """Fraction of pixels with alpha < 128 (DR16's shape-mask cutoff)."""
    with Image.open(path) as im:
        alpha = im.convert("RGBA").getchannel("A").tobytes()
    return sum(1 for a in alpha if a < 128) / len(alpha)


def _dialog_source(theme: Theme) -> IClassSpec | None:
    """MENU_BG, else DIALOG — skipping SHAPED art (see
    ``SHAPED_ART_MAX_TRANSPARENT``): E16 shaped the menu window to such
    art's outline, but a Plasma popup is a rectangle. The note is
    deduplicated because ``style_scheme`` resolves the source again.
    """
    for name in ("MENU_BG", "DIALOG"):
        spec = theme.iclasses.get(name)
        path = _state_image(spec, "normal")
        if spec is None or path is None:
            continue
        try:
            frac = _transparent_fraction(path)
        except OSError:
            return spec  # unreadable art fails later with a skip note
        if frac > SHAPED_ART_MAX_TRANSPARENT:
            note = (
                f"plasmastyle: {name} art is shaped ({frac:.0%} transparent"
                " — E16 cut the menu window to its outline); unfit for a "
                "rectangular popup background, trying the next source"
            )
            if note not in theme.notes:
                theme.notes.append(note)
            continue
        return spec
    return None


def _panel_art_guard(spec: IClassSpec) -> str | None:
    """None when *spec*'s normal art may back the panel, else the reason.

    Two guards (the ``_dialog_source`` idiom): shaped art
    (``SHAPED_ART_MAX_TRANSPARENT`` — a 1-bit-masked bar over a rectangular
    panel leaks wallpaper through its holes) and giant caps
    (``PANEL_MAX_REF_CAPS`` — cap sums become fixed FrameSvg borders, i.e.
    dead margins on fit-content panels; measured after ``_fit_caps`` so an
    E16 overlapping-cap declaration is judged by what would render).
    """
    found = _state_attr(spec, "normal")
    if found is None:
        return "no art"
    state_attr, path = found
    try:
        frac = _transparent_fraction(path)
    except OSError:
        return None  # unreadable art degrades later, in the builder
    if frac > SHAPED_ART_MAX_TRANSPARENT:
        return (
            f"shaped ({frac:.0%} transparent — E16 cut the bar window to "
            "its outline)"
        )
    w, h = _source_size(path)
    declared = spec.edge_for(state_attr)
    edge = _fit_caps(declared, w, h) or declared
    left, right, top, bottom = edge
    if left + right > PANEL_MAX_REF_CAPS or top + bottom > PANEL_MAX_REF_CAPS:
        return (
            f"caps {left}+{right} h / {top}+{bottom} v ref px exceed "
            f"{PANEL_MAX_REF_CAPS} (giant caps become dead FrameSvg margins "
            "on fit-content panels)"
        )
    return None


def _panel_art_source(
    theme: Theme, names: tuple[str, ...] = _PANEL_ART_SOURCES
) -> IClassSpec | None:
    """First of *names* whose normal art passes :func:`_panel_art_guard`.

    Every rejection appends one deduplicated ``plasmastyle:`` note (the
    function is re-resolved by ``style_scheme`` and ``write``).
    """
    for name in names:
        spec = theme.iclasses.get(name)
        if spec is None or _state_image(spec, "normal") is None:
            continue
        reason = _panel_art_guard(spec)
        if reason is None:
            return spec
        note = (
            f"plasmastyle: {name} art rejected for the panel background: "
            f"{reason}; trying the next source"
        )
        if note not in theme.notes:
            theme.notes.append(note)
    return None


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
        #: Set by art-frame emitters; finish() then adds the file-global
        #: hint-stretch-borders. FrameSvg TILES border elements by default,
        #: and E16 always stretched — gradient edge art visibly repeats
        #: when tiled (live HandOfGod pager, 2026-08-31). Unprefixed, like
        #: Breeze's own hints in prefixed files. Flat-rect sets skip the
        #: flag (stretch/tile invariant), keeping those files minimal.
        self.stretch_borders = False

    def advance(self, width: int, height: int) -> None:
        self.w = max(self.w, width)
        self.y += height + _GAP

    def finish(self) -> ET.Element:
        if self.stretch_borders:
            ET.SubElement(
                self.root,
                f"{{{SVG_NS}}}rect",
                {
                    "id": "hint-stretch-borders",
                    "x": "0",
                    "y": str(self.y),
                    "width": "1",
                    "height": "1",
                    "style": "opacity:0",
                },
            )
            self.advance(1, 1)
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


def _shave_for_center(a: int, b: int, span: int) -> tuple[int, int]:
    """Reduce the (a, b) cap pair so ≥1 px of center survives on this axis.

    See :func:`_frame_group` — caps that consume the whole span would emit
    a center-less set, which FrameSvg treats as ABSENT. The shave comes
    off the larger cap first (it is the cap's own innermost row/column, so
    the art is visually unchanged); an axis with no caps is left alone
    (the center spans it already).
    """
    if a + b < span or (a == 0 and b == 0):
        return a, b
    excess = a + b - (span - 1)
    first, second = (a, b) if a >= b else (b, a)
    take = min(excess, first)
    first -= take
    second -= min(excess - take, second)
    return (first, second) if a >= b else (second, first)


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

    A ``<prefix>center`` element is ALWAYS emitted when the set has caps:
    FrameSvg's ``hasElementPrefix`` checks exactly ``<prefix>center``
    (ksvg 6.24 framesvg.cpp) and a center-less set paints NOTHING —
    FrameSvgItem::updatePaintNode returns null (verified live 2026-08-31:
    Aliens' full-cross-section slider groove rendered invisible). Caps
    that consume the whole image on an axis are shaved by
    :func:`_shave_for_center` so a ≥1 px center survives; authored
    cap-only ("exact fit") art keeps its look — the shaved px is the
    cap's own innermost row, now stretching as the center.

    Raises ValueError when the caps exceed the image (``slice_9patch``'s
    guard) — the caller degrades to center-only with a note.
    """
    left, right, top, bottom = caps
    left, right = _shave_for_center(left, right, img.width)
    top, bottom = _shave_for_center(top, bottom, img.height)
    caps = (left, right, top, bottom)
    if caps != (0, 0, 0, 0):  # center-only sets have no borders to stretch
        canvas.stretch_borders = True
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


def _opaque_trim(
    img: Image.Image, edge: tuple[int, int, int, int]
) -> tuple[Image.Image, tuple[int, int, int, int], tuple[int, int, int, int] | None]:
    """Crop fully transparent margins (E16 shape-mask padding) off *img*.

    E16 cut the widget window to the art's opaque outline, so art was often
    authored on a larger transparent canvas (Yellow's MENU_SEL: a 44x18
    pill on a 58x22 canvas). Sliced untrimmed, a cap that overlaps the
    blank margin paints little or nothing — the live missing-right-border
    highlight (desktop icons/Kickoff/systray, 2026-09-01). Returns the
    cropped image, the declared edge re-anchored into the cropped frame
    (caps lose exactly the blank part the mask hid), and the trimmed
    margin widths (L R T B) — or the inputs unchanged and None when there
    is nothing to trim. Alpha ≥ 128 is DR16's shape-mask cutoff, the same
    threshold ``_transparent_fraction`` uses.
    """
    mask = img.getchannel("A").point([0] * 128 + [255] * 128)
    bbox = mask.getbbox()
    if bbox is None or bbox == (0, 0, img.width, img.height):
        return img, edge, None
    x0, y0, x1, y1 = bbox
    trims = (x0, img.width - x1, y0, img.height - y1)
    left, right, top, bottom = edge
    edge = (
        max(0, left - trims[0]),
        max(0, right - trims[1]),
        max(0, top - trims[2]),
        max(0, bottom - trims[3]),
    )
    return img.crop(bbox), edge, trims


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
) -> tuple[int, int, int, int] | None:
    """One prefixed 9-part set (+ optional margin hints) for *spec*/*state*.

    Returns the painted cap sizes (L R T B, output px, post-shave) so the
    panel builder can derive cap-hugging margin hints, or None when the
    state resolves to no image at all. The art is first trimmed to its
    opaque box (:func:`_opaque_trim` — shape-mask padding must not become
    invisible border slices); oversized caps degrade to a center-only set
    with a ``plasmastyle:`` note rather than failing (per the mapping
    contract). ``edge_override`` maps ``(edge, src_w, src_h)`` — post-trim
    values — to the edge actually used; the viewitem builder pins
    synthetic caps with it.
    """
    found = _state_attr(spec, state)
    if found is None:
        return None
    state_attr, path = found
    with Image.open(path) as im:
        src = im.convert("RGBA")
    src, edge, trims = _opaque_trim(src, spec.edge_for(state_attr))
    if trims is not None:
        note = (
            f"plasmastyle: {spec.name} {path.name} trimmed by "
            f"{trims[0]}/{trims[1]}/{trims[2]}/{trims[3]} px (L/R/T/B) of "
            "fully transparent margin (E16's shape mask hid it); caps "
            "re-anchored to the visible art"
        )
        if note not in theme.notes:
            theme.notes.append(note)
    src_w, src_h = src.size
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
    scale = _surface_scale(theme, spec, edge)
    img = upscale_part(src, scale)
    caps = _scaled_caps(edge, src_w, src_h, scale)
    try:
        _frame_group(canvas, prefix, img, caps)
    except ValueError:
        # Last resort only — _fit_caps should have prevented this.
        theme.notes.append(
            f"plasmastyle: {spec.name} edge_scaling {spec.edge_scaling} "
            f"exceeds its {path.name} image; whole image stretched instead"
        )
        _frame_group(canvas, prefix, img, (0, 0, 0, 0))
        caps = (0, 0, 0, 0)
    else:
        left, right = _shave_for_center(caps[0], caps[1], img.width)
        top, bottom = _shave_for_center(caps[2], caps[3], img.height)
        caps = (left, right, top, bottom)
    if hints:
        _margin_hints(canvas, prefix, spec.padding, scale)
    return caps


def _surface_scale(
    theme: Theme, spec: IClassSpec, edge: tuple[int, int, int, int]
) -> float:
    """``theme.scale``, or 1.0 for art with dominating chrome.

    See ``SURFACE_MAX_REF_CHROME``. The note is deduplicated because
    multi-state builders emit one set per prefix from the same art.
    """
    left, right, top, bottom = edge
    if left + right <= SURFACE_MAX_REF_CHROME and top + bottom <= SURFACE_MAX_REF_CHROME:
        return theme.scale
    if theme.scale <= 1:
        return theme.scale
    note = (
        f"plasmastyle: {spec.name} caps ({left}+{right} h, {top}+{bottom} v "
        f"ref px) dominate the surface; art kept at source scale instead of "
        f"{theme.scale:g}x (E16 drew this frame at source size around far "
        "smaller content)"
    )
    if note not in theme.notes:
        theme.notes.append(note)
    return 1.0


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


def _panel_margins(
    canvas: _Canvas, prefix: str, caps: tuple[int, int, int, int], scale: float
) -> None:
    """Cap-hugging margin hints for the art panel.

    Per side: ``max(1, cap − _PANEL_SMALL_SPACING)`` output px, so Plasma's
    Panel.qml padding (``margin + smallSpacing``) lands exactly on the cap
    art's inner edge — content hugs the cap with zero empty trough
    (calibrated live on themey_e13, 2026-09-01: 12 px __PADDING hints read
    as a broken empty button before the first task icon). A capless side
    keeps the flat-panel ``PANEL_MARGIN_REF`` default. The 1 px floor
    keeps every rect emitted — a missing hint would fall back to the
    border element's own thickness, resurrecting the trough.
    """
    fallback = max(1, scale_px(PANEL_MARGIN_REF, scale))

    def hint(cap: int) -> int:
        return max(1, cap - _PANEL_SMALL_SPACING) if cap > 0 else fallback

    left, right, top, bottom = caps
    # Values are already output px; scale 1.0 passes them through scale_px
    # unchanged.
    _margin_hints(canvas, prefix, (hint(left), hint(right), hint(top), hint(bottom)), 1.0)


def _panel_art_svg(theme: Theme, src: IClassSpec) -> ET.Element:
    """9-part panel set from real E16 bar art, middle STRETCHED.

    One unprefixed set serves every horizontal panel (``adjustPrefix``
    falls back to unprefixed); a vertical bar iclass that passes the same
    guards adds ``west-``/``east-`` sets so the left-edge pager/iconbox
    furniture panels wear the vertical art (Panel.qml's ``[pre, ""]``
    prefix list). NO ``hint-tile-center``: E16 renders every iclass middle
    by Imlib2 border-scale — caps pinned, middle STRETCHED — and tiling
    repeated photographic troughs (HandOfGod's capless cloud, then
    NorthernLights' 58 px aurora even WITH caps) across the whole bar
    (both verified live 2026-09-01). FrameSvg stretches the center by
    default, so no hint is needed; ``hint-stretch-borders`` still covers
    the border elements (those FrameSvg tiles by default).
    """
    canvas = _Canvas()
    caps = _emit_set(theme, canvas, "", src, "normal") or (0, 0, 0, 0)
    _panel_margins(canvas, "", caps, theme.scale)
    vert = _panel_art_source(theme, _PANEL_VERT_SOURCES)
    if vert is not None:
        for prefix in ("west-", "east-"):
            vcaps = _emit_set(theme, canvas, prefix, vert, "normal") or (0, 0, 0, 0)
            _panel_margins(canvas, prefix, vcaps, theme.scale)
    theme.notes.append(
        f"plasmastyle: panel background from iclass {src.name} art, middle "
        "stretched like every E16 iclass middle (caps stay pinned)"
        + (
            f"; vertical panels from {vert.name}"
            if vert is not None
            else ""
        )
    )
    theme.notes.append(
        "plasmastyle: panel margin hints hug the cap art (cap − 4 px per "
        "side; E16 __PADDING dropped — Plasma pads panel content on top of "
        "the frame margins, and the sum read as an empty trough)"
    )
    return canvas.finish()


def build_panel_background(theme: Theme) -> ET.Element:
    """``widgets/panel-background.svg`` — real E16 bar art when it passes
    the guards, else a flat translucent tint.

    The art path (:func:`_panel_art_svg`) ships the dragbar/iconbox art
    with a stretched middle; :func:`_panel_art_guard` rejects shaped art and
    wordmark-sized caps (the failure mode that originally forced the flat
    tint — a 133-px "ENLIGHTENMENT" cap stretched across a 40 px panel
    buries every widget). The tint fallback keeps the theme's color
    character while the wallpaper shows through; never returns None — a
    colors-only theme still gets a scheme-tinted panel.
    """
    src = _panel_art_source(theme)
    if src is not None:
        try:
            return _panel_art_svg(theme, src)
        except (OSError, ValueError) as exc:
            theme.notes.append(
                f"plasmastyle: panel art from {src.name} unreadable "
                f"({exc}); falling back to the flat tint"
            )
    tint, source = _panel_tint(theme)
    svg = _panel_svg(theme, PANEL_ALPHA)
    theme.notes.append(
        f"plasmastyle: panel background is a translucent tint rgb{tint} "
        f"(alpha {PANEL_ALPHA}) of {source} — no E16 bar art passed the "
        "shaped/cap guards"
    )
    return svg


#: Menu frame piece iclasses: FrameSvg border element -> E16 iclass.
_MENU_STRIP_NAMES: tuple[tuple[str, str], ...] = (
    ("top", "MENU_T"),
    ("bottom", "MENU_B"),
    ("left", "MENU_L"),
    ("right", "MENU_R"),
)
#: (corner element, iclass, adjacent horizontal strip, adjacent vertical
#: strip). A corner paints at exactly (adjacent-left/right width x
#: adjacent-top/bottom height) — FrameSvgHelpers::sectionRect (ksvg
#: 6.24) sizes it from contentRect, never from the corner's own art.
_MENU_CORNER_NAMES: tuple[tuple[str, str, str, str], ...] = (
    ("topleft", "MENU_TL", "top", "left"),
    ("topright", "MENU_TR", "top", "right"),
    ("bottomleft", "MENU_BL", "bottom", "left"),
    ("bottomright", "MENU_BR", "bottom", "right"),
)

#: Max per-dimension stretch factor between a corner piece and the strip
#: thickness it will be painted at, before the piece is dropped. Aliens'
#: MENU_TL is 23 px tall against a 6 px top strip — squashed 4x it is
#: mush, worse than no corner.
CORNER_DIM_TOLERANCE = 1.5


def _emit_composite_frame(
    theme: Theme, canvas: _Canvas, strips: dict[str, Path]
) -> None:
    """One unprefixed frame assembled from per-piece menu art.

    *strips* maps ``top``/``bottom``/``left``/``right`` to their MENU_*
    art; each is emitted WHOLE as that border element (FrameSvg has no
    per-border 9-patch — the strip stretches along its axis, matching
    E16's stretched middles; end caps a strip may carry stretch with it).
    Corners ship only when both adjacent strips exist AND the corner's
    dims are within ``CORNER_DIM_TOLERANCE`` of the strip thicknesses it
    will be stretched to. The center is mandatory (a center-less set
    paints NOTHING): the ``_dialog_source`` art when available, else a
    flat rect in the top strip's dominant color.
    """
    sizes = {side: _source_size(p) for side, p in strips.items()}
    top_h = sizes.get("top", (0, 0))[1]
    bottom_h = sizes.get("bottom", (0, 0))[1]
    left_w = sizes.get("left", (0, 0))[0]
    right_w = sizes.get("right", (0, 0))[0]
    scale = theme.scale
    if scale > 1 and (
        left_w + right_w > SURFACE_MAX_REF_CHROME
        or top_h + bottom_h > SURFACE_MAX_REF_CHROME
    ):
        scale = 1.0
        theme.notes.append(
            "plasmastyle: menu frame strips dominate the surface; kept at "
            "source scale (the SURFACE_MAX_REF_CHROME rule)"
        )

    loaded: dict[str, Image.Image] = {
        side: _load_scaled(p, scale) for side, p in strips.items()
    }
    for corner, name, hstrip, vstrip in _MENU_CORNER_NAMES:
        path = _state_image(theme.iclasses.get(name), "normal")
        if path is None:
            continue
        if hstrip not in strips or vstrip not in strips:
            theme.notes.append(
                f"plasmastyle: {name} corner piece dropped (no adjacent "
                f"{vstrip}/{hstrip} strip to size it against — FrameSvg "
                "paints a corner at the adjacent border thicknesses)"
            )
            continue
        cw, ch = _source_size(path)
        want_w = sizes[vstrip][0]  # left/right strip width
        want_h = sizes[hstrip][1]  # top/bottom strip height
        if (
            max(cw, want_w) > CORNER_DIM_TOLERANCE * min(cw, want_w)
            or max(ch, want_h) > CORNER_DIM_TOLERANCE * min(ch, want_h)
        ):
            theme.notes.append(
                f"plasmastyle: {name} corner piece dropped ({cw}x{ch} art "
                f"would be stretched to the {want_w}x{want_h} border "
                "thicknesses — FrameSvg ignores a corner's own size)"
            )
            continue
        loaded[corner] = _load_scaled(path, scale)

    center_src = _dialog_source(theme)
    center_path = (
        _state_image(center_src, "normal") if center_src is not None else None
    )
    center_img: Image.Image | None = None
    if center_path is not None:
        center_img = _load_scaled(center_path, scale)

    for row in (
        ("topleft", "top", "topright"),
        ("left", "center", "right"),
        ("bottomleft", "bottom", "bottomright"),
    ):
        items: list[tuple[str, Image.Image]] = []
        for element in row:
            if element == "center":
                if center_img is not None:
                    items.append(("center", center_img))
                continue
            img = loaded.get(element)
            if img is not None:
                items.append((element, img))
        if items:
            _emit_plain_row(canvas, items)
    if center_img is None:
        # Mandatory center: a flat rect in the top-most strip's dominant.
        first = next(iter(strips.values()))
        rgb = extract_dominant(first) or (128, 128, 128)
        ET.SubElement(
            canvas.root,
            f"{{{SVG_NS}}}rect",
            {
                "id": "center",
                "x": "0",
                "y": str(canvas.y),
                "width": "16",
                "height": "16",
                "style": f"fill:{_hex(rgb)}",
            },
        )
        canvas.advance(16, 16)
    canvas.stretch_borders = True


def build_dialog_background(theme: Theme) -> ET.Element | None:
    """``dialogs/background.svg`` (applet popups, Kickoff, calendar).

    When the theme authors per-piece menu frame art (``MENU_T``/``B``/
    ``L``/``R``, Aliens), the popup frame is composed from those pieces
    around the ``_dialog_source`` center — richer than stretching one
    background image. Otherwise the classic single 9-part set from
    ``MENU_BG``→``DIALOG``. ``MENU_SUB`` (no Plasma submenu element) and
    ``MENU_TITLE_BAR`` (dresses E16's ROOT menu title only) are recorded
    as skips.
    """
    for name, why in (
        ("MENU_SUB", "Plasma has no submenu background element"),
        ("MENU_TITLE_BAR", "it dresses E16's ROOT menu title bar only"),
    ):
        spec = theme.iclasses.get(name)
        if spec is not None and _state_image(spec, "normal") is not None:
            theme.notes.append(
                f"plasmastyle: {name} art has no Plasma target ({why}); "
                "skipped"
            )

    strips: dict[str, Path] = {}
    for side, name in _MENU_STRIP_NAMES:
        path = _state_image(theme.iclasses.get(name), "normal")
        if path is not None:
            strips[side] = path
    if strips:
        canvas = _Canvas()
        _emit_composite_frame(theme, canvas, strips)
        piece_names = ", ".join(
            name for _, name in _MENU_STRIP_NAMES
            if _state_image(theme.iclasses.get(name), "normal") is not None
        )
        center_src = _dialog_source(theme)
        theme.notes.append(
            "plasmastyle: popup/dialog frame composed from menu frame "
            f"pieces {piece_names}"
            + (
                f" around a {center_src.name} center"
                if center_src is not None
                else " around a flat center (no unshaped background art)"
            )
            + "; no shadow set is shipped, so popups render shadowless "
            "(E16 drew none)"
        )
        return canvas.finish()

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


def build_pager(theme: Theme) -> ET.Element | None:
    """``widgets/pager.svg`` from the E16 pager iclasses, art only.

    ``active-``/``hover-`` cells wear ``PAGER_SEL`` (E16's selected-desk
    highlight; hover reuses its state chain — E16 had no hover concept),
    ``normal-`` cells ``PAGER_BACKGROUND`` when it has art. Standard
    9-part sets: the art's own middle stretches over the cell interior,
    so a transparent middle stays transparent. Deliberately NO baked cell
    content: an earlier build embedded wallpaper miniatures, but a static
    mini cannot track wallpaper changes (chris, 2026-08-31) — better no
    background than a stale one. Window rects come from Kirigami.Theme
    via the bundled colors file. Skipped without ``PAGER_SEL`` art —
    Breeze's pager, re-tinted by this package's colors, beats bare cells.
    """
    sel = _iclass_with_art(theme, "PAGER_SEL")
    if sel is None:
        theme.notes.append(
            "plasmastyle: no PAGER_SEL art; widgets/pager left to the "
            "Breeze fallback"
        )
        return None
    canvas = _Canvas()
    bg = _iclass_with_art(theme, "PAGER_BACKGROUND")
    if bg is not None:
        _emit_set(theme, canvas, "normal-", bg, "normal")
    _emit_set(theme, canvas, "active-", sel, "normal")
    _emit_set(theme, canvas, "hover-", sel, "hover")
    theme.notes.append(
        f"plasmastyle: pager cells from iclass {sel.name}"
        + (f" (normal desks from {bg.name})" if bg is not None else "")
        + "; cells carry no desktop preview — Plasma's pager cannot show "
        "live desktops, and a baked wallpaper mini would go stale"
    )
    return canvas.finish()


#: (element direction, ICONBOX arrow iclass) for the task-group expanders.
_EXPANDER_SOURCES: tuple[tuple[str, str], ...] = (
    ("left", "ICONBOX_ARROW_LEFT"),
    ("right", "ICONBOX_ARROW_RIGHT"),
    ("top", "ICONBOX_ARROW_UP"),
    ("bottom", "ICONBOX_ARROW_DOWN"),
)


def build_tasks(theme: Theme) -> ET.Element | None:
    """``widgets/tasks.svg`` — task-manager frames from the iconbox button.

    themey's own apply creates the iconbox panel with an icons-only task
    manager, so these frames land exactly where E16's iconbox buttons
    lived. The taskmanager plasmoid (icontasks shares its Task.qml) reads
    prefixes ``normal``/``minimized``/``hover``/``focus``/``attention``/
    ``progress`` plus the unprefixed launcher set; ALL of them ship
    (per-FILE fallback — a partial set paints nothing for missing
    prefixes). ``focus-`` wears the CLICKED chain — E16's active iconbox
    button is the depressed one; ``attention-``/``progress-`` approximate
    with the hilited chain (E16 has no such states — noted).
    ``group-expander-*`` come from the four ``ICONBOX_ARROW_*`` when all
    exist (the ``build_arrows`` census), else they are omitted with a
    note.
    """
    src = _iclass_with_art(theme, "DEFAULT_ICON_BUTTON", "DEFAULT_DOCK_BUTTON")
    if src is None:
        return None
    canvas = _Canvas()
    for prefix, state in (
        ("normal-", "normal"),
        ("minimized-", "normal"),
        ("", "normal"),  # launcher frame
        ("hover-", "hover"),
        ("attention-", "hover"),
        ("progress-", "hover"),
        ("focus-", "pressed"),
    ):
        _emit_set(theme, canvas, prefix, src, state, hints=True)

    expanders: list[tuple[str, Path]] = []
    for direction, name in _EXPANDER_SOURCES:
        path = _state_image(theme.iclasses.get(name), "normal")
        if path is None:
            expanders = []
            break
        expanders.append((f"group-expander-{direction}", path))
    if expanders:
        _emit_plain_row(
            canvas,
            [(el, _load_scaled(p, theme.scale)) for el, p in expanders],
        )
    else:
        theme.notes.append(
            "plasmastyle: not all four ICONBOX_ARROW_* have art; task "
            "group expanders left to the Breeze fallback"
        )
    theme.notes.append(
        f"plasmastyle: task frames from iclass {src.name} (E16 iconbox "
        "button; focus wears the clicked art — the active task shows the "
        "depressed button; attention/progress approximate with the "
        "hilited art)"
    )
    return canvas.finish()


# --------------------------------------------------------------------- #
# Dialog-widget builders — check/radio marks, slider, separator, frame
# --------------------------------------------------------------------- #


def _emit_plain_row(
    canvas: _Canvas, items: list[tuple[str, Image.Image]]
) -> None:
    """One row of plain (non-frame) elements — the arrows-builder idiom."""
    x = 0
    row_h = 0
    for element, img in items:
        g = ET.SubElement(canvas.root, f"{{{SVG_NS}}}g", {"id": element})
        _embed_image(g, img, x, canvas.y)
        x += img.width + _GAP
        row_h = max(row_h, img.height)
    canvas.advance(x, row_h)


def _emit_size_hint(canvas: _Canvas, hint_id: str, width: int, height: int) -> None:
    """One invisible size-hint rect (the ``hint-scrollbar-size`` idiom) —
    consumers read only the element's dimensions."""
    ET.SubElement(
        canvas.root,
        f"{{{SVG_NS}}}rect",
        {
            "id": hint_id,
            "x": "0",
            "y": str(canvas.y),
            "width": str(width),
            "height": str(height),
            "style": "opacity:0",
        },
    )
    canvas.advance(width, height)


def _hilited_image(spec: IClassSpec) -> Path | None:
    """Explicit non-checked hilited art only — NOT the ``hover`` chain,
    which for the checked-semantics widgets reaches ``hilited_active``
    (checked-hover art on an unchecked-hover element)."""
    if spec.hilited is not None and spec.hilited.is_file():
        return spec.hilited
    return None


def build_checkmarks(theme: Theme) -> ET.Element | None:
    """``widgets/checkmarks.svg`` — the marks PC3 draws over button frames.

    ``checkbox`` from DIALOG_WIDGET_CHECK_BUTTON's checked (``_ACTIVE``)
    art; ``radiobutton`` from RADIO_BUTTON's, falling back to the check
    art (RadioIndicator's compat path still looks it up here, so the
    element must be present whenever the file ships). No checked art
    skips the whole file — see the ``checked`` chain.
    """
    check = theme.iclasses.get("DIALOG_WIDGET_CHECK_BUTTON")
    check_path = _state_image(check, "checked")
    if check_path is None:
        if check is not None and _state_image(check, "normal") is not None:
            theme.notes.append(
                "plasmastyle: DIALOG_WIDGET_CHECK_BUTTON has no checked "
                "(_ACTIVE) art; widgets/checkmarks left to the Breeze "
                "fallback"
            )
        return None
    radio_path = _state_image(
        theme.iclasses.get("DIALOG_WIDGET_RADIO_BUTTON"), "checked"
    )
    canvas = _Canvas()
    _emit_plain_row(
        canvas,
        [
            ("checkbox", _load_scaled(check_path, theme.scale)),
            ("radiobutton", _load_scaled(radio_path or check_path, theme.scale)),
        ],
    )
    theme.notes.append(
        "plasmastyle: check/radio marks from the DIALOG_WIDGET check/radio "
        "checked art; the UNchecked checkbox wears the widgets/button "
        "normal frame (Plasma's CheckIndicator hardcodes it) — still this "
        "theme's DIALOG_BUTTON art, just not the authored unchecked box"
        + ("" if radio_path is not None else "; radio mark reuses the check art")
    )
    return canvas.finish()


def build_radiobutton(theme: Theme) -> ET.Element | None:
    """``widgets/radiobutton.svg`` — RadioIndicator's newer path (taken as
    soon as this file ships; layers centered at naturalSize).

    ``normal``/``checked`` both required; ``hover`` only with explicit
    hilited art; ``hint-size`` drives the indicator size. Deliberately no
    ``shadow``/``focus`` (E16 has neither) and no ``symbol`` — our
    ``checked`` art carries its own dot.
    """
    spec = theme.iclasses.get("DIALOG_WIDGET_RADIO_BUTTON")
    if spec is None:
        return None
    normal_path = _state_image(spec, "normal")
    checked_path = _state_image(spec, "checked")
    if normal_path is None or checked_path is None:
        if normal_path is not None or checked_path is not None:
            missing = "checked (_ACTIVE)" if checked_path is None else "unchecked"
            theme.notes.append(
                f"plasmastyle: DIALOG_WIDGET_RADIO_BUTTON has no {missing} "
                "art; widgets/radiobutton left to the Breeze fallback"
            )
        return None
    normal_img = _load_scaled(normal_path, theme.scale)
    items = [
        ("normal", normal_img),
        ("checked", _load_scaled(checked_path, theme.scale)),
    ]
    hover_path = _hilited_image(spec)
    if hover_path is not None:
        items.append(("hover", _load_scaled(hover_path, theme.scale)))
    canvas = _Canvas()
    _emit_plain_row(canvas, items)
    _emit_size_hint(canvas, "hint-size", normal_img.width, normal_img.height)
    theme.notes.append(
        "plasmastyle: radio buttons from iclass DIALOG_WIDGET_RADIO_BUTTON"
        + ("" if hover_path is not None else " (no hilited art, hover omitted)")
    )
    return canvas.finish()


def _groove_caps(
    edge: tuple[int, int, int, int], w: int, h: int, *, horizontal: bool
) -> tuple[int, int, int, int]:
    """Groove caps: declared along-axis, full cross-section across.

    Slider.qml sizes a horizontal groove's height to exactly
    ``fixedMargins.top + bottom``, so declared 1-px cross caps (Aliens'
    ``slh.png``, edge ``4 4 1 1``) would collapse the tube to a 2-px
    sliver. Splitting the full cross-section between the two caps renders
    the whole authored tube — the exact-fit caps case ``_fit_caps``
    already blesses. Along-axis caps keep their declared values
    (oversized ones still shrink through ``_fit_caps``).
    """
    left, right, top, bottom = edge
    if horizontal:
        return (left, right, h // 2, h - h // 2)
    return (w // 2, w - w // 2, top, bottom)


def build_slider(theme: Theme) -> ET.Element | None:
    """``widgets/slider.svg`` from the DIALOG_WIDGET slider iclasses.

    One ``groove``/``groove-highlight`` FrameSvg pair serves both
    orientations (Slider.qml uses a single prefix); handles render at
    naturalSize, sized by ``hint-handle-size``. Both a base and a knob are
    required — either alone skips the file with a note. Deliberately no
    ``*-slider-shadow``/``focus`` and never ``hint-tile-center``.
    """
    base = _iclass_with_art(
        theme,
        "DIALOG_WIDGET_SLIDER_BASE_HORIZONTAL",
        "DIALOG_WIDGET_SLIDER_BASE_VERTICAL",
    )
    knob_h = _iclass_with_art(theme, "DIALOG_WIDGET_SLIDER_KNOB_HORIZONTAL")
    knob_v = _iclass_with_art(theme, "DIALOG_WIDGET_SLIDER_KNOB_VERTICAL")
    if base is None or (knob_h is None and knob_v is None):
        if base is not None or knob_h is not None or knob_v is not None:
            missing = "no knob art" if base is not None else "no base art"
            theme.notes.append(
                f"plasmastyle: slider art is partial ({missing}); "
                "widgets/slider left to the Breeze fallback"
            )
        return None
    horizontal = base.name.endswith("HORIZONTAL")

    def groove_caps(
        edge: tuple[int, int, int, int], w: int, h: int
    ) -> tuple[int, int, int, int]:
        return _groove_caps(edge, w, h, horizontal=horizontal)

    canvas = _Canvas()
    # hints=False: nothing lays out inside a groove.
    _emit_set(theme, canvas, "groove-", base, "normal", edge_override=groove_caps)
    _emit_set(
        theme, canvas, "groove-highlight-", base, "hover", edge_override=groove_caps
    )

    h_spec = knob_h if knob_h is not None else knob_v
    v_spec = knob_v if knob_v is not None else knob_h
    assert h_spec is not None and v_spec is not None
    h_path = _state_image(h_spec, "normal")
    v_path = _state_image(v_spec, "normal")
    assert h_path is not None and v_path is not None  # _iclass_with_art
    h_img = _load_scaled(h_path, theme.scale)
    items = [
        ("horizontal-slider-handle", h_img),
        ("vertical-slider-handle", _load_scaled(v_path, theme.scale)),
    ]
    hover_missing = []
    for element, spec in (
        ("horizontal-slider-hover", h_spec),
        ("vertical-slider-hover", v_spec),
    ):
        hover = _hilited_image(spec)
        if hover is not None:
            items.append((element, _load_scaled(hover, theme.scale)))
        else:
            hover_missing.append(element)
    _emit_plain_row(canvas, items)
    _emit_size_hint(canvas, "hint-handle-size", h_img.width, h_img.height)

    notes = [
        f"plasmastyle: slider groove from iclass {base.name}, handles from "
        f"{h_spec.name}"
        + ("" if h_spec is v_spec else f"/{v_spec.name}")
    ]
    if not horizontal:
        notes.append("the vertical groove art serves both orientations")
    if h_spec is v_spec:
        notes.append("one knob serves both orientations")
    if _state_image(base, "hover") == _state_image(base, "normal"):
        notes.append(
            "no E16 fill-highlight art — the groove fill is invisible "
            "(the handle position still shows the value)"
        )
    if hover_missing:
        notes.append("no hilited knob art, hover handles omitted")
    theme.notes.append("; ".join(notes))
    return canvas.finish()


def build_line(theme: Theme) -> ET.Element | None:
    """``widgets/line.svg`` — section separators in tray popups/SpinBox.

    The art is squeezed (NEAREST) to ``LINE_MAX_REF_THICKNESS`` — see that
    constant for why the image's own height is not the rule's thickness.
    ``vertical-line`` is the same image rotated 90°, always shipped with
    the file (per-FILE fallback: a missing element renders nothing).
    """
    src = _iclass_with_art(theme, "DIALOG_WIDGET_SEPARATOR")
    if src is None:
        return None
    path = _state_image(src, "normal")
    assert path is not None  # _iclass_with_art guarantees it
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
    clamped = rgba.height > LINE_MAX_REF_THICKNESS
    target = (
        max(1, scale_px(rgba.width, theme.scale)),
        max(
            1,
            scale_px(min(rgba.height, LINE_MAX_REF_THICKNESS), theme.scale),
        ),
    )
    line = rgba.resize(target, resample=Image.Resampling.NEAREST)
    canvas = _Canvas()
    for element, img in (
        ("horizontal-line", line),
        ("vertical-line", line.transpose(Image.Transpose.ROTATE_90)),
    ):
        _emit_plain_row(canvas, [(element, img)])
    theme.notes.append(
        f"plasmastyle: separators from iclass {src.name}"
        + (
            f" ({rgba.height} ref px tall, squeezed to "
            f"{LINE_MAX_REF_THICKNESS} — E16 squeezed this art into a "
            "thin rule at layout time)"
            if clamped
            else ""
        )
        + "; the vertical rule is the same art rotated"
    )
    return canvas.finish()


def build_frame(theme: Theme) -> ET.Element | None:
    """``widgets/frame.svg`` — PC3 Frame/GroupBox chrome.

    ONE unprefixed 9-part set + unprefixed margin hints: PC3 requests the
    ``plain`` prefix and FrameSvg's ``adjustPrefix`` falls back to the
    unprefixed set (the same mechanism the panel builder relies on).
    Breeze's ``base``/``raised-``/``sunken-`` sets are deliberately not
    emitted — E16 has one dialog-area look.
    """
    src = _iclass_with_art(theme, "DIALOG_WIDGET_AREA", "DIALOG_WIDGET_TABLE")
    if src is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "", src, "normal", hints=True)
    theme.notes.append(
        f"plasmastyle: group frames from iclass {src.name} (one unprefixed "
        "set; FrameSvg's adjustPrefix serves it for PC3's plain prefix)"
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
    (CHECKMARKS_SVG, build_checkmarks),
    (RADIOBUTTON_SVG, build_radiobutton),
    (SLIDER_SVG, build_slider),
    (LINE_SVG, build_line),
    (FRAME_SVG, build_frame),
    (PAGER_SVG, build_pager),
    (TASKS_SVG, build_tasks),
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


def _regroup(
    group: ColorGroup,
    bg: RGB | None,
    fg: RGB,
    guards: tuple[RGB, ...] = (),
) -> ColorGroup:
    """*group* with a new bg/fg, derived fields recomputed for legibility.

    *guards* lists EVERY background this group's text is painted on beyond
    its own ``background_normal`` — for Colors:Window that is the panel
    tint, which shares the group with the popup art. The derived
    ``foreground_inactive``/``foreground_active`` prefer their usual
    single-background derivation but fall back (to *fg*, itself already
    guard-legible by construction, or to the black/white
    maximize-the-minimum pick) when that derivation fails a guard.
    """
    background = bg if bg is not None else group.background_normal
    checks = (background, *guards)
    inactive = _dimmed(fg, background)
    if not all(contrast_ratio(inactive, b) >= MIN_CONTRAST for b in guards):
        inactive = fg
    active = _legible(group.foreground_active, background)
    active, _ = _fg_for(active, active, checks)
    return replace(
        group,
        background_normal=background,
        background_alternate=(
            background if bg is not None else group.background_alternate
        ),
        foreground_normal=fg,
        foreground_inactive=inactive,
        foreground_active=active,
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

    Colors:Window is shared by the panel AND popups, so its ENTIRE
    foreground set — ``ForegroundNormal`` and the derived
    ``ForegroundInactive``/``ForegroundActive`` — is guarded against both
    the popup art's background and the panel tint (see :func:`_regroup`'s
    ``guards``). When both backgrounds cannot be satisfied at once (e.g.
    black popups over a white panel) the black/white
    maximize-the-minimum-contrast pick applies; a ``forced``
    ``plasmastyle:`` note records it for ``ForegroundNormal`` (the derived
    fields adjust silently).
    """
    scheme = theme.scheme if theme.scheme is not None else default_scheme()

    # The color actually painted on the panel: the CHOSEN art's dominant
    # when the panel ships real art (_panel_art_source — may differ from
    # _panel_tint's unguarded first-with-art pick), else the flat tint.
    panel_bg: RGB | None = None
    if PANEL_SVG in shipped:
        art = _panel_art_source(theme)
        art_path = _state_image(art, "normal") if art is not None else None
        if art_path is not None:
            panel_bg = extract_dominant(art_path)
        if panel_bg is None:
            panel_bg = _panel_tint(theme)[0]

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
        # The panel tint joins the guard set for the DERIVED foregrounds
        # too: dimmed/active text is painted on the panel just as much as
        # ForegroundNormal is.
        extra = (panel_bg,) if panel_bg is not None else ()
        scheme = replace(
            scheme, window=_regroup(scheme.window, dialog_bg, fg, guards=extra)
        )
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


def write(theme: Theme, out_dir: Path) -> PlasmaStyle:
    """Write the Plasma Style package for *theme* under *out_dir*.

    ``out_dir``'s basename MUST be ``slug.plugin_id(theme.name)`` — the
    dir name is the ``plasmarc [Theme] name=`` value Plasma matches on.
    A single SVG whose source art cannot be read skips that one file with
    a ``plasmastyle:`` note; an EMPTY SVG set is legitimate (colors-only
    package, like breeze-dark). Any other failure removes ``out_dir`` and
    raises :class:`PlasmaStyleError`.
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

        shipped: list[str] = []
        panel_is_tint = False
        for rel, builder in _BUILDERS:
            try:
                svg = builder(theme)
            except (OSError, ValueError) as exc:
                theme.notes.append(f"plasmastyle: skipped {rel}: {exc}")
                continue
            if svg is None:
                continue
            if rel == PANEL_SVG:
                # The tint rendition carries no embedded art; only it needs
                # the opaque re-render below (art panels are already opaque).
                panel_is_tint = not any(
                    el.tag.endswith("image") for el in svg.iter()
                )
            out = out_dir / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            ET.ElementTree(svg).write(out, xml_declaration=True, encoding="utf-8")
            shipped.append(rel)

        # Byte-identical mirrors: Panel.qml loads solid/ for opaque panels
        # (and opaque/ exists as the same contract for other consumers); a
        # missing mirror would fall back to Breeze's art there. The ONE
        # exception: a TINT panel's base rendition is translucent, so its
        # mirrors are re-rendered at alpha 1 — AdaptiveTransparency swaps
        # to solid/ when a window touches the panel, and that variant must
        # be genuinely opaque. An art panel is opaque already and mirrors
        # byte-identically like everything else.
        for rel in shipped:
            for variant in ("solid", "opaque"):
                dst = out_dir / variant / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if rel == PANEL_SVG and panel_is_tint:
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
