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
  *Breeze's* solid art next to our translucency-free chrome.
* 9-part sets use FrameSvg's element names (``topleft`` … ``bottomright``,
  optionally ``<prefix>-``-prefixed); zero-extent slices are simply not
  emitted (FrameSvg then reports a 0 border, which is correct — the Aliens
  dragbar's ``133 28 0 0`` edge yields a left/center/right-only set).
  ``hint-tile-center`` is NEVER emitted — E16 stretches middles, and that
  hint would switch FrameSvg to tiling.
* Margin hints (``hint-<side>-margin``) come from the iclass ``__PADDING``
  and are emitted per non-zero side only.
* The package ``plasmarc`` disables AdaptiveTransparency and the contrast
  effect — E16 chrome is opaque pixel art — which also makes the
  ``translucent/`` variant set unreachable (so it is not shipped).
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

#: Package plasmarc: E16 chrome is opaque pixel art, so both runtime
#: translucency effects are off. This also makes the ``translucent/``
#: variant directory unreachable, which is why write() never emits one.
_PACKAGE_PLASMARC: dict[str, dict[str, str]] = {
    "AdaptiveTransparency": {"enabled": "false"},
    "ContrastEffect": {"enabled": "false"},
}

#: Relative SVG paths (also the ``shipped`` vocabulary and the mirror set).
PANEL_SVG = "widgets/panel-background.svg"
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


def _panel_vertical_source(theme: Theme) -> IClassSpec | None:
    return _iclass_with_art(theme, "DESKTOP_DRAGBUTTON_VERT", "ICONBOX_VERTICAL")


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
) -> bool:
    """One prefixed 9-part set (+ optional margin hints) for *spec*/*state*.

    Returns False when the state resolves to no image at all. Oversized
    caps degrade to a center-only set with a ``plasmastyle:`` note rather
    than failing (per the mapping contract).
    """
    path = _state_image(spec, state)
    if path is None:
        return False
    img = _load_scaled(path, theme.scale)
    caps = _scaled_caps(spec.edge_scaling, *_source_size(path), theme.scale)
    try:
        _frame_group(canvas, prefix, img, caps)
    except ValueError:
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


# --------------------------------------------------------------------- #
# Builders — one per shipped SVG; None means "don't ship, Breeze wins"
# --------------------------------------------------------------------- #


def build_panel_background(theme: Theme) -> ET.Element | None:
    """``widgets/panel-background.svg`` from the dragbar/iconbox/dock art.

    Unprefixed set serves every orientation (``adjustPrefix()`` falls back
    to unprefixed when a ``north-``/``south-``/… set is absent); ``east-``
    and ``west-`` sets come from the vertical variant art when the theme
    has one.
    """
    src = _panel_source(theme)
    if src is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "", src, "normal", hints=True)
    vert = _panel_vertical_source(theme)
    if vert is not None:
        _emit_set(theme, canvas, "east-", vert, "normal", hints=True)
        _emit_set(theme, canvas, "west-", vert, "normal", hints=True)
    theme.notes.append(
        f"plasmastyle: panel background from iclass {src.name}"
        + (f"; vertical panels from {vert.name}" if vert is not None else "")
    )
    return canvas.finish()


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


def build_viewitem(theme: Theme) -> ET.Element | None:
    """``widgets/viewitem.svg`` from ``MENU_SEL``.

    ``normal-`` is emitted only when MENU_SEL has explicit normal art —
    an always-painted normal set would draw menu-row chrome under every
    unhovered list row, which most E16 themes leave to the background.
    """
    src = theme.iclasses.get("MENU_SEL")
    if _state_image(src, "hover") is None or src is None:
        return None
    canvas = _Canvas()
    has_normal_art = (src.normal is not None and src.normal.is_file()) or (
        src.normal_active is not None and src.normal_active.is_file()
    )
    if has_normal_art:
        _emit_set(theme, canvas, "normal-", src, "normal")
    _emit_set(theme, canvas, "hover-", src, "hover")
    _emit_set(theme, canvas, "selected-", src, "selected")
    # Literal "+" in the id — FrameSvg's combined-state prefix.
    _emit_set(theme, canvas, "selected+hover-", src, "selected")
    theme.notes.append(
        f"plasmastyle: menu/list selection from iclass {src.name}"
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

    # Knob thickness: the across-the-track dimension of the scaled knob art
    # (width of a vertical knob, height of a horizontal one).
    knob_path = _state_image(knob, "normal")
    assert knob_path is not None  # _iclass_with_art guarantees it
    src_w, src_h = _source_size(knob_path)
    across = src_w if knob.name.endswith("VERTICAL") else src_h
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

    panel_bg: RGB | None = None
    if PANEL_SVG in shipped:
        src = _panel_source(theme)
        path = _state_image(src, "normal")
        if path is not None:
            panel_bg = extract_dominant(path)

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
        for rel, builder in _BUILDERS:
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
        # missing mirror would fall back to Breeze's art there.
        for rel in shipped:
            for variant in ("solid", "opaque"):
                dst = out_dir / variant / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
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
