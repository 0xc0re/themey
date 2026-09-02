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
  passes the guards (:func:`_panel_art_guard`). Three layers in one file:
  the UNPREFIXED set (every orientation's fallback) only ever carries art
  with small caps on BOTH axes (``PANEL_MAX_REF_CAPS``) or the flat tint,
  because plasmashell turns the unprefixed set's caps into EVERY panel's
  minimum thickness regardless of prefix (verified live 2026-09-01: e13's
  60 px wordmark caps forced the 60 px iconbox panel to 120 px although a
  ``west-`` set existed); the ``north-``/``south-`` sets carry the
  wordmark bar art ("AE", "ALIENS", "Enlightenment" baked into the
  length-axis caps, which E16 pinned at the bar's start and FrameSvg pins
  the same way, ``_panel_margins`` hugging them) — allowed up to
  ``PANEL_MAX_REF_LENGTH_CAPS``; the ``south-`` set (foreign bottom
  bars) additionally wants the bar at least
  ``PANEL_WORDMARK_MIN_THICKNESS_REF`` thick, since such a panel
  stretches the bar (wordmark included) to its own 40-60 px and a 6 px
  strip smears, while ``north-`` is exempt because themey's apply
  creates the top dragbar panel at exactly ``scale_px(16)`` — E16's own
  dragbar thickness; the ``west-``/``east-`` sets dress the left-edge furniture from
  the iconbox trough first (``_PANEL_VERT_SOURCES``). Shaped art is
  rejected everywhere (a 1-bit-masked bar over a rectangular panel leaks
  wallpaper through its holes). Middles STRETCH when E16 stretched them
  (the default ``__FILLRULE``; tiling repeated photographic troughs —
  HandOfGod, NorthernLights, live 2026-09-01) and TILE only when E16
  itself tiled (``__FILLRULE __TILE*`` → ``<prefix>hint-tile-center``).
* 9-part sets use FrameSvg's element names (``topleft`` … ``bottomright``,
  optionally ``<prefix>-``-prefixed); zero-extent slices are simply not
  emitted (FrameSvg then reports a 0 border, which is correct — the Aliens
  dragbar's ``133 28 0 0`` edge yields a left/center/right-only set) —
  EXCEPT the center: FrameSvg's ``hasElementPrefix`` checks exactly
  ``<prefix>center`` and paints NOTHING for a center-less set, so caps
  that consume the whole image are shaved one px to keep a real center
  (:func:`_frame_group`).
  ``hint-tile-center`` is never emitted for stretched E16 middles
  (FrameSvg's center default already is stretch) and emitted exactly when
  E16 itself tiled the state's art (``IClassSpec.fill_for`` ≠ stretch —
  ``__FILLRULE __TILE`` / ``__TILE_H`` / ``__TILE_V``, per image state).
  The same E16 rule covers borders:
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

Two files serve themey's OWN applets (``generate/plasmoids.py``) and have
no Breeze counterpart or fallback semantics: ``widgets/themey-dragbar.svg``
(:func:`build_dragbar`, the dragbar's desk-next/prev buttons) and the
``window-``/``window-active-`` prefixes in ``widgets/pager.svg``
(:func:`build_pager`, E16's PAGER_WIN rect art for the live pager).

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

import contextvars
import hashlib
import json
import logging
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

from themey.analyze.colors import (
    MIN_CONTRAST,
    _dimmed,
    _legible,
    contrast_ratio,
    default_scheme,
    extract_dominant,
    view_from_window,
)
from themey.generate.colors import build_sections
from themey.generate.desktop_writer import write_desktop
from themey.generate.qmldeco.resolver import scale_px
from themey.images.embed import image_to_b64_uri
from themey.images.ninepatch import slice_9patch
from themey.images.upscale import upscale_part
from themey.ir import FILL_STRETCH, ColorGroup, ColorScheme, IClassSpec, MenuStyleSpec, Theme
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
#: themey's own file (no Breeze counterpart): the E16 dragbar's desk
#: buttons, read only by the ``org.themey.deskbutton`` applet.
DRAGBAR_SVG = "widgets/themey-dragbar.svg"
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

#: Ref-px ceiling for the separator rule's thickness. E16 sizes a separator
#: from the iclass ``__PADDING``, not the art (``dialog.c:1048-1056``:
#: ``w = pad.l + pad.r``, ``h = pad.t + pad.b``): 127 corpus themes declare
#: 2 px, 73 declare 4, ten declare nothing. The art is squeezed (NEAREST)
#: into that thickness — LiteGnome's 120x4 hline and Aliens/e13's ~64 px
#: bevel box alike, the same image-dimension-is-not-widget-size trap
#: SCROLLBAR_MAX_REF_THICKNESS documents. The ceiling catches the outliers
#: (LCARS declares 8+8) and serves as the cap for the art-height fallback
#: when no padding is declared.
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
#: Horizontal: the user's own bar is E16's desktop drag bar analog, so
#: the dragbar art (wordmark cap and all) leads. Vertical: the
#: ``west-``/``east-`` sets dress themey's LEFT-EDGE FURNITURE — the
#: pager and iconbox panels ``apply.py`` creates — which are E16's
#: iconbox/pager windows, NOT a drag bar, so the iconbox trough art leads
#: and the vertical dragbar is only the fallback. With the vertical
#: dragbar first, e13's 12-px-wide bar (kept at 1x by
#: ``SURFACE_MAX_REF_CHROME``, its 50 px knob cap) was stretched across a
#: 60 px iconbox panel and read as a smeared rotated E (live 2026-09-01).
_PANEL_ART_SOURCES: tuple[str, ...] = (
    "DESKTOP_DRAGBUTTON_HORIZ", "ICONBOX_HORIZONTAL", "DEFAULT_DOCK_BUTTON",
)
_PANEL_VERT_SOURCES: tuple[str, ...] = (
    "ICONBOX_VERTICAL", "DESKTOP_DRAGBUTTON_VERT",
)

#: Ref-px ceiling for the panel art's cap sum across the bar's THICKNESS
#: axis (T+B for a horizontal source, L+R for a vertical one). A cap on
#: this axis is stretched to the panel's thickness, so a giant one smears
#: unreadably across a 40 px panel; measured after ``_fit_caps``.
PANEL_MAX_REF_CAPS = 32

#: Ref-px ceiling for the cap sum along the bar's LENGTH axis. These caps
#: are the theme's wordmarks ("AE" 50 px, "Enlightenment" ~60 px) which
#: E16 pinned at the bar's start; FrameSvg pins them identically and the
#: cap-hugging margin hints put the first widget right after them, so
#: they render exactly as E16 did (chris, 2026-09-01). Beyond this the
#: pinned art would swallow a fit-content furniture panel outright.
#: Census: AE 50+4 accepted; e13 60+60 (post-_fit_caps) accepted; Aliens
#: 133+28 = 161 still rejected → its ICONBOX_HORIZONTAL (4/4) backs the
#: panel; OPENSTEP DragBar 24+2 accepted (the NeXT cube stays pinned).
PANEL_MAX_REF_LENGTH_CAPS = 160

#: Ref-px minimum THICKNESS of bar art before its wordmark caps are worth
#: shipping on a FOREIGN panel (the ``south-`` set). A cap is painted at
#: the art's own scale and the panel then stretches the whole bar to its
#: thickness (40-60 px): e13's 6 px-tall dragbar smeared its "E" ten
#: times taller across the bottom bar (live 2026-09-01); the corpus
#: median dragbar is 16 px. At 24 ref px the stretch stays ≤ 2.5x on a
#: 60 px panel. The ``north-`` set is EXEMPT (``thin_ok``): themey's
#: apply creates the top dragbar panel at exactly ``scale_px(16)`` px, so
#: whatever stretch the strip gets there is the one E16 gave it.
PANEL_WORDMARK_MIN_THICKNESS_REF = 24


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


#: Menu style names tried for the popup source, in order: E16 opens every
#: app/desktop menu with DEFAULT; ROOT dresses the root menu.
_MENU_STYLE_ORDER = ("DEFAULT", "ROOT")


def _menu_style(theme: Theme) -> MenuStyleSpec | None:
    for name in _MENU_STYLE_ORDER:
        if name in theme.menu_styles:
            return theme.menu_styles[name]
    return next(iter(theme.menu_styles.values()), None)


def _dialog_candidates(theme: Theme) -> list[tuple[str, bool]]:
    """``(iclass name, tiled)`` sources for the popup background, best
    first.

    The parsed ``__MENU_STYLE`` leads because it names what E16 actually
    painted the menu window with (menus.c ``MenuRedraw``), whatever the
    iclass is called: its ``__BG_ICLASS`` stretched like any frame, or —
    ``__USE_ITEM_BACKGROUNDS __ON``, the NeXTSTEP style (OldE, 8 corpus
    themes) — the ``__ITEM_ICLASS`` normal art, which E16 applied to every
    menu row so the menu was a stack of those strips and never had a
    background of its own; FrameSvg can only repeat it (``tiled``), at the
    strip's own height rather than per row. Then the classic name
    convention: ``MENU_BG``, then ``DIALOG``.
    """
    out: list[tuple[str, bool]] = []
    style = _menu_style(theme)
    if style is not None:
        if style.use_item_bg and style.item_iclass:
            out.append((style.item_iclass, True))
        elif style.bg_iclass:
            out.append((style.bg_iclass, False))
    for name in ("MENU_BG", "DIALOG"):
        if all(name != n for n, _ in out):
            out.append((name, False))
    return out


def _resolve_dialog_source(theme: Theme) -> tuple[IClassSpec, bool] | None:
    """First :func:`_dialog_candidates` entry with unshaped normal art, as
    ``(spec, tiled)`` — skipping SHAPED art (``SHAPED_ART_MAX_TRANSPARENT``):
    E16 shaped the menu window to such art's outline, but a Plasma popup is
    a rectangle. Notes are deduplicated because ``style_scheme`` resolves
    the source again.
    """
    for name, tiled in _dialog_candidates(theme):
        spec = theme.iclasses.get(name)
        path = _state_image(spec, "normal")
        if spec is None or path is None:
            continue
        try:
            frac = _transparent_fraction(path)
        except OSError:
            return spec, tiled  # unreadable art fails later with a skip note
        if frac > SHAPED_ART_MAX_TRANSPARENT:
            note = (
                f"plasmastyle: {name} art is shaped ({frac:.0%} transparent"
                " — E16 cut the menu window to its outline); unfit for a "
                "rectangular popup background, trying the next source"
            )
            if note not in theme.notes:
                theme.notes.append(note)
            continue
        return spec, tiled
    return None


def _dialog_source(theme: Theme) -> IClassSpec | None:
    """The popup background iclass (see :func:`_resolve_dialog_source`)."""
    found = _resolve_dialog_source(theme)
    return found[0] if found is not None else None


def _item_background_note(spec: IClassSpec) -> str:
    return (
        f" (E16 item backgrounds — __USE_ITEM_BACKGROUNDS: the menu had no "
        f"background of its own, every row wore {spec.name}'s normal art; the "
        "popup keeps that strip's bevel as its frame around a flat center in "
        "the strip's dominant color — repeating the strip painted its bevel "
        "rows as stripes across a tall launcher)"
    )


def _flat_center(path: Path) -> RGB | None:
    """*path*'s dominant color, for a flat popup center behind
    item-background (NeXTSTEP-style) menu strips. E16 never painted
    a menu background for those styles — every row wore the strip — and a
    FrameSvg center can only stretch or repeat, so repeating the strip
    stacked its bevel rows into stripes across a 600 px Kickoff (OldE,
    live 2026-09-01). The flat fill is the same ``extract_dominant`` the
    ``colors`` Window group samples, so popup art and text guards agree.
    None when the art yields no dominant color (the caller keeps tiling).
    """
    return extract_dominant(path)


def _panel_art_guard(
    spec: IClassSpec, *, wordmark: bool = False, thin_ok: bool = False
) -> str | None:
    """None when *spec*'s normal art may back a panel set, else the reason.

    Guards (the ``_dialog_source`` idiom): shaped art
    (``SHAPED_ART_MAX_TRANSPARENT`` — a 1-bit-masked bar over a rectangular
    panel leaks wallpaper through its holes); thickness-axis caps (T+B for
    a horizontal source, L+R for a ``_PANEL_VERT_SOURCES`` one) past
    ``PANEL_MAX_REF_CAPS`` — a cap across the bar is stretched to the
    panel's thickness; and length-axis caps: the STRICT default keeps
    ``PANEL_MAX_REF_CAPS`` there too, because the unprefixed set's caps
    become EVERY panel's minimum thickness in Plasma (verified live
    2026-09-01: e13's 60 px wordmark caps forced the 60 px iconbox panel
    to 120 px even with a ``west-`` set present — plasmashell sizes the
    minimum from the unprefixed frame regardless of prefix). With
    ``wordmark=True`` (the ``north-``/``south-`` sets, which no vertical
    panel reads) length caps are allowed up to
    ``PANEL_MAX_REF_LENGTH_CAPS`` — they stay pinned exactly as E16 drew
    them — provided the bar is at least ``PANEL_WORDMARK_MIN_THICKNESS_REF``
    thick, since the panel stretches the bar (wordmark included) to its
    own thickness — unless ``thin_ok`` (the ``north-`` set: themey's own
    16 ref px dragbar panel, where the strip is not stretched beyond what
    E16 did). Measured after ``_fit_caps`` so an E16 overlapping-cap
    declaration is judged by what would render.
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
    if spec.name in _PANEL_VERT_SOURCES:
        length, thickness, thick_px = (top, bottom, "v"), (left, right, "h"), w
    else:
        length, thickness, thick_px = (left, right, "h"), (top, bottom, "v"), h
    if thickness[0] + thickness[1] > PANEL_MAX_REF_CAPS:
        return (
            f"thickness-axis caps {thickness[0]}+{thickness[1]} {thickness[2]} "
            f"ref px exceed {PANEL_MAX_REF_CAPS} (a cap across the bar is "
            "stretched to the panel's thickness and turns unreadable)"
        )
    length_sum = length[0] + length[1]
    if not wordmark:
        if length_sum > PANEL_MAX_REF_CAPS:
            return (
                f"length-axis caps {length[0]}+{length[1]} {length[2]} ref px "
                f"exceed {PANEL_MAX_REF_CAPS} for the shared set (Plasma "
                "makes the unprefixed caps every panel's minimum thickness)"
            )
        return None
    if length_sum > PANEL_MAX_REF_LENGTH_CAPS:
        return (
            f"length-axis caps {length[0]}+{length[1]} {length[2]} ref px "
            f"exceed {PANEL_MAX_REF_LENGTH_CAPS} (pinned caps this large "
            "swallow a fit-content panel)"
        )
    if (
        not thin_ok
        and length_sum > PANEL_MAX_REF_CAPS
        and thick_px < PANEL_WORDMARK_MIN_THICKNESS_REF
    ):
        return (
            f"wordmark caps on a {thick_px} ref px thin bar (under "
            f"{PANEL_WORDMARK_MIN_THICKNESS_REF}; the panel would stretch the "
            "wordmark to its thickness and smear it)"
        )
    return None


def _panel_art_source(
    theme: Theme,
    names: tuple[str, ...] = _PANEL_ART_SOURCES,
    *,
    wordmark: bool = False,
    thin_ok: bool = False,
) -> IClassSpec | None:
    """First of *names* whose normal art passes :func:`_panel_art_guard`
    (strict by default; ``wordmark=True`` for the ``south-`` set,
    ``wordmark=True, thin_ok=True`` for the ``north-`` one).

    Every rejection appends one deduplicated ``plasmastyle:`` note (the
    function is re-resolved by ``style_scheme`` and ``write``).
    """
    if not wordmark:
        role = "panel background"
    elif thin_ok:
        role = "wordmark (north-) set"
    else:
        role = "wordmark (south-) set"
    for name in names:
        spec = theme.iclasses.get(name)
        if spec is None or _state_image(spec, "normal") is None:
            continue
        reason = _panel_art_guard(spec, wordmark=wordmark, thin_ok=thin_ok)
        if reason is None:
            return spec
        note = (
            f"plasmastyle: {name} art rejected for the {role}: "
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

    @property
    def is_empty(self) -> bool:
        """No element has been emitted (every set was skipped) — the builder
        must return None so Plasma falls back to Breeze for the file; a
        shipped-but-blank SVG paints nothing and blocks that fallback."""
        return len(self.root) == 0

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


# Per-``write()`` memo for the EXPENSIVE scalers. Plasma Style art is
# reused across prefixed sets and states — e13 makes 50 upscale calls for
# 30 distinct (image, scale, mode) triples, 40% redundant — and a waifu2x
# call is a ~0.8 s subprocess, so the duplicates cost more than the rest
# of the package put together. A ContextVar rather than a parameter for
# the same reason ``upscale`` rides on Theme: the builders are a fixed
# ``Callable[[Theme], Element | None]`` and the call sites are ~35 deep.
# Scoped by ``write()`` with a token reset, so nothing leaks between
# packages or themes.
_upscale_memo: contextvars.ContextVar[dict[object, Image.Image] | None] = (
    contextvars.ContextVar("_upscale_memo", default=None)
)


def _scaled(img: Image.Image, scale: float, mode: str) -> Image.Image:
    """``upscale_part`` with the per-write memo in front of it.

    NEAREST is left entirely alone — it is far cheaper than hashing the
    image would be, and keeping the default path byte-for-byte on the
    original code path is what lets the corpus survey stay comparable.
    Returns a COPY, because callers composite and transform in place and
    a shared cached Image would alias across sets.
    """
    if mode == "nearest":
        return upscale_part(img, scale, mode)
    memo = _upscale_memo.get()
    if memo is None:
        return upscale_part(img, scale, mode)
    key = (hashlib.sha256(img.tobytes()).digest(), img.size, scale, mode)
    hit = memo.get(key)
    if hit is None:
        hit = upscale_part(img, scale, mode)
        memo[key] = hit
    return hit.copy()


def _load_scaled(
    path: Path, scale: float, mode: str = "nearest"
) -> Image.Image:
    """Open *path* as RGBA and upscale it by *scale* using *mode*.

    *mode* is a ``images.upscale.UPSCALE_MODES`` token — callers pass
    ``theme.upscale`` so the panel and the popup wear the same scaler the
    window decoration does. *scale* stays a separate argument because
    several callers override it below ``theme.scale`` (the viewitem row
    and menu-frame source-scale rules).

    Raises OSError/ValueError on unreadable art — the caller skips the
    whole file with a ``plasmastyle:`` note.
    """
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
    return _scaled(rgba, scale, mode)


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
    *,
    tile_center: bool = False,
) -> None:
    """Emit one FrameSvg 9-part set at the canvas cursor.

    ``tile_center`` emits ``<prefix>hint-tile-center`` so FrameSvg repeats
    the center at native size — ONLY for art E16 itself tiled
    (``__FILLRULE __TILE*``, ``IClassSpec.fill_for``); never for stretched
    E16 middles, where tiling repeated photographic troughs across whole
    bars (HandOfGod, NorthernLights; verified live 2026-09-01).

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
    if tile_center:
        ET.SubElement(
            canvas.root,
            f"{{{SVG_NS}}}rect",
            {
                "id": f"{prefix}hint-tile-center",
                "x": "0",
                "y": str(canvas.y),
                "width": "1",
                "height": "1",
                "style": "opacity:0",
            },
        )
        canvas.advance(1, 1)


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
) -> tuple[Image.Image, tuple[int, int, int, int], tuple[int, int, int, int] | None] | None:
    """Crop fully transparent margins (E16 shape-mask padding) off *img*.

    E16 cut the widget window to the art's opaque outline, so art was often
    authored on a larger transparent canvas (Yellow's MENU_SEL: a 44x18
    pill on a 58x22 canvas). Sliced untrimmed, a cap that overlaps the
    blank margin paints little or nothing — the live missing-right-border
    highlight (desktop icons/Kickoff/systray, 2026-09-01). Returns the
    cropped image, the declared edge re-anchored into the cropped frame
    (caps lose exactly the blank part the mask hid), and the trimmed
    margin widths (L R T B) — or the inputs unchanged and None when there
    is nothing to trim. Returns None outright when the art is FULLY
    transparent below the cutoff (Aphex2's ``blank.png`` MENU_SEL): there
    is nothing to slice, and a shipped-but-blank set would block Plasma's
    per-file Breeze fallback. Alpha ≥ 128 is DR16's shape-mask cutoff, the
    same threshold ``_transparent_fraction`` uses.
    """
    mask = img.getchannel("A").point([0] * 128 + [255] * 128)
    bbox = mask.getbbox()
    if bbox is None:
        return None
    if bbox == (0, 0, img.width, img.height):
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


#: Ref-px cross-section (post-trim ``min(w, h)``) at or below which
#: MENU_SEL art is a highlight PILL — a strip authored at item height,
#: whose rounded ends and vertical shading the radius pin keeps crisp.
#: Anything larger is a menu BACKGROUND pointed at MENU_SEL (47 corpus
#: themes: 64x64 tiles up to Ganymede's 484x400).
VIEWITEM_PILL_MAX_REF = 40

#: Ref-px ceiling for any viewitem cap. A Kickoff row is ~30 px; the old
#: unclamped radius gave 94/215 corpus themes caps past this (IceBerg's
#: 256x256 background → 127 px caps, StarEnli 64 left / 14 right) with
#: no stretching middle left at all.
VIEWITEM_MAX_REF_CAP = 12

#: OUTPUT-px ceiling for a viewitem set's top+bottom caps. Kickoff's
#: sidebar rows are ~30-34 px at 1x and FrameSvg needs a centre row to
#: paint at all: StarEnli's 27 px MENU_SEL pill at 1.5x carried 18+18 px
#: of caps into a 30 px row and painted a degenerate half-pill sliver
#: (chris's screenshot 2026-09-01). Past this the set stays at source
#: scale — ``VIEWITEM_MAX_REF_CAP`` guarantees 12+12 ref px always fits.
VIEWITEM_MAX_ROW_CHROME_PX = 24

#: Per-pixel contrast (0-1: luminance delta for two painted pixels, 1.0
#: when the shape mask cuts exactly one of them) at or above which a pixel
#: pair counts as OUTLINE — a painted rim or a rounded end's alpha edge.
_RIM_PIXEL_CONTRAST = 0.25
#: Share of a side's painted span that must be outline pixels (outer line
#: vs the line ``cap // 2`` inward) for the side to count as RIMMED.
#: Yellow's rounded left end scores 1.0; Detroit's soft pill bottom, whose
#: only contrast is a 4-px decorative mark, scores ~0.2.
_RIM_MIN_FRACTION = 0.5
#: Share at or below which a side is flat fill running to the edge.
_OPEN_MAX_FRACTION = 0.15

_SIDE_INDEX = {"left": 0, "right": 1, "top": 2, "bottom": 3}
_OPPOSITE = {"left": "right", "right": "left", "top": "bottom", "bottom": "top"}

RGBA = tuple[int, int, int, int]


def _edge_line(img: Image.Image, side: str, offset: int) -> list[RGBA]:
    """RGBA pixels of the row/column *offset* px inward from *side*."""
    w, h = img.size
    if side == "left":
        box = (offset, 0, offset + 1, h)
    elif side == "right":
        box = (w - 1 - offset, 0, w - offset, h)
    elif side == "top":
        box = (0, offset, w, offset + 1)
    else:
        box = (0, h - 1 - offset, w, h - offset)
    data = img.crop(box).tobytes()
    return [
        (data[i], data[i + 1], data[i + 2], data[i + 3])
        for i in range(0, len(data), 4)
    ]


def _pixel_contrast(p: RGBA, q: RGBA) -> float | None:
    """0-1 contrast of a pixel pair; None when neither is painted."""
    cut_p, cut_q = p[3] < 128, q[3] < 128
    if cut_p and cut_q:
        return None
    if cut_p != cut_q:
        return 1.0
    return abs((p[0] + p[1] + p[2]) - (q[0] + q[1] + q[2])) / 765


def _edge_profile(img: Image.Image, side: str, cap: int) -> tuple[bool, float]:
    """``(flat, rim_fraction)`` of *side*'s outermost line against the line
    ``cap // 2`` inward: *flat* — both lines have the same shape mask (a
    straight cut, no rounding); *rim_fraction* — share of the painted span
    whose pixel pairs are outline (``_RIM_PIXEL_CONTRAST``)."""
    depth = img.width if side in ("left", "right") else img.height
    inward = min(max(1, cap // 2), depth - 1)
    if inward <= 0:
        return False, 0.0
    outer = _edge_line(img, side, 0)
    inner = _edge_line(img, side, inward)
    contrasts = [_pixel_contrast(p, q) for p, q in zip(outer, inner, strict=True)]
    painted = [c for c in contrasts if c is not None]
    if not painted:
        return False, 0.0
    flat = all((p[3] < 128) == (q[3] < 128) for p, q in zip(outer, inner, strict=True))
    rim = sum(1 for c in painted if c >= _RIM_PIXEL_CONTRAST) / len(painted)
    return flat, rim


def _cut_carries_rims(img: Image.Image, side: str) -> bool:
    """True when the outermost line's first and last painted pixels
    contrast with its middle third — the perpendicular sides' rims run
    straight into the cut, the signature of a rimmed shape sliced open
    (Yellow's right end: dark top/bottom rows, fill between). A bevel's lit
    edge (Nebula) or a soft pill (Detroit) is uniform end to end."""
    painted = [p for p in _edge_line(img, side, 0) if p[3] >= 128]
    n = len(painted)
    if n < 3:
        return False
    third = painted[n // 3 : n - n // 3] or painted
    lum = sum(p[0] + p[1] + p[2] for p in third) / len(third)
    mid: RGBA = (int(lum / 3), int(lum / 3), int(lum / 3), 255)
    return all(
        (_pixel_contrast(end, mid) or 0.0) >= _RIM_PIXEL_CONTRAST
        for end in (painted[0], painted[-1])
    )


def _mirror_cap_onto(img: Image.Image, side: str, cap: int) -> Image.Image:
    """Copy of *img* with the OPPOSITE side's *cap*-px band mirrored onto
    *side* (pixels replaced, alpha included — a rounded end brings its
    transparent corners along)."""
    w, h = img.size
    out = img.copy()
    if side == "right":
        out.paste(ImageOps.mirror(img.crop((0, 0, cap, h))), (w - cap, 0))
    elif side == "left":
        out.paste(ImageOps.mirror(img.crop((w - cap, 0, w, h))), (0, 0))
    elif side == "bottom":
        out.paste(ImageOps.flip(img.crop((0, 0, w, cap))), (0, h - cap))
    else:
        out.paste(ImageOps.flip(img.crop((0, h - cap, w, h))), (0, 0))
    return out


def _close_open_edges(
    img: Image.Image,
    caps: tuple[int, int, int, int],
    trims: tuple[int, int, int, int] | None,
) -> tuple[Image.Image, tuple[int, int, int, int], tuple[str, ...]]:
    """Close a pill's OPEN end with its bordered opposite end, mirrored.

    Yellow's MENU_SEL (``m_selected.png``, 58x22) is authored with a
    rounded, rimmed LEFT end, rimmed top/bottom rows, and a flat OPEN
    right end at x=43 — fill straight to the edge, then 14 fully
    transparent columns. E16 drew that as authored: the highlight's right
    end was open, with the menu background showing through the gap. That
    exact look was on the desktop before f85b1cf (a see-through gutter)
    and was reported as a missing right border; after f85b1cf the trimmed
    8 px right cap was cut from columns 36-43 — pure fill, no rim — and was
    reported again. The rim was never painted, so no slicing fix can
    restore it: this repair DIVERGES FROM E16 on purpose and is noted in
    ``report.txt``.

    Only PILL art (``min(w, h) <= VIEWITEM_PILL_MAX_REF``) is considered;
    full-canvas art (``trims`` None — pager ``p_sel.png``/``bg_win.png``
    bevels, whose light bottom/right edges are authored asymmetry) is
    returned as-is. Per axis, a side is closed only when ALL of: it was
    TRIMMED (``trims[side] > 0`` — the art stopped short of its canvas
    there); it is a straight cut with fill running to the edge
    (:func:`_edge_profile`: flat mask, rim fraction ≤
    ``_OPEN_MAX_FRACTION``); the perpendicular rims run into that cut
    (:func:`_cut_carries_rims`); and the opposite side is rimmed (rim
    fraction ≥ ``_RIM_MIN_FRACTION``). The opposite cap band is then
    mirrored onto it and the side's cap becomes the opposite cap (Yellow:
    10/8 → 10/10). The rim-into-cut test is what separates a sliced-open
    rimmed pill from art that is merely lit on one side: a raised bevel
    with alpha margins (Nebula — light top/left, dark right/bottom
    shadow) and a soft pill whose only bottom contrast is a decorative
    mark (Detroit) were closed by a looser rule (corpus audit
    2026-09-01) and came out boxed in. *caps* are the source-px caps in
    force (post ``edge_override``). Returns ``(image, caps, closed
    sides)``.
    """
    if trims is None or min(img.size) > VIEWITEM_PILL_MAX_REF:
        return img, caps, ()
    out = img
    new_caps = list(caps)
    closed: list[str] = []
    for side in ("left", "right", "top", "bottom"):
        i = _SIDE_INDEX[side]
        opp = _OPPOSITE[side]
        o = _SIDE_INDEX[opp]
        depth = out.width if side in ("left", "right") else out.height
        if trims[i] <= 0 or new_caps[o] <= 0 or new_caps[o] > depth:
            continue
        flat, rim = _edge_profile(out, side, new_caps[i])
        if not flat or rim > _OPEN_MAX_FRACTION or not _cut_carries_rims(out, side):
            continue
        if _edge_profile(out, opp, new_caps[o])[1] < _RIM_MIN_FRACTION:
            continue
        out = _mirror_cap_onto(out, side, new_caps[o])
        new_caps[i] = new_caps[o]
        closed.append(side)
    return out, (new_caps[0], new_caps[1], new_caps[2], new_caps[3]), tuple(closed)


def _emit_set(
    theme: Theme,
    canvas: _Canvas,
    prefix: str,
    spec: IClassSpec,
    state: str,
    *,
    hints: bool = False,
    edge_override: Callable[
        [tuple[int, int, int, int], int, int, Image.Image], tuple[int, int, int, int]
    ]
    | None = None,
    close_open_edges: bool = False,
    tile_center: bool | None = None,
    flat_center: RGB | None = None,
    max_v_chrome_px: int | None = None,
    clear_center: bool = False,
    transform: Callable[[Image.Image], Image.Image] | None = None,
) -> tuple[int, int, int, int] | None:
    """One prefixed 9-part set (+ optional margin hints) for *spec*/*state*.

    Returns the painted cap sizes (L R T B, output px, post-shave) so the
    panel builder can derive cap-hugging margin hints, or None when the
    state resolves to no image at all OR the art is fully transparent
    (nothing emitted, ``plasmastyle:`` note — the builder must then leave
    the file to Breeze via ``_Canvas.is_empty``). The art is first trimmed
    to its opaque box (:func:`_opaque_trim` — shape-mask padding must not
    become invisible border slices); oversized caps degrade to a
    center-only set with a ``plasmastyle:`` note rather than failing (per
    the mapping contract). ``edge_override`` maps ``(edge, src_w, src_h,
    img)`` — post-trim values and the trimmed RGBA art — to the edge
    actually used; the viewitem builder
    pins synthetic caps with it. ``close_open_edges`` (viewitem only)
    runs :func:`_close_open_edges` on the overridden caps. ``tile_center``
    overrides the ``__FILLRULE``-derived choice (the popup builder tiles
    E16 item-background art the menu repeated per row). ``flat_center``
    (a solid color) is painted over the art's center box — everything
    inside the caps — before slicing, so the set keeps the art's own
    bevel and gets a flat, stretchable center; it forces ``tile_center``
    off. ``max_v_chrome_px`` (viewitem only) is the most OUTPUT px of
    top+bottom caps the set may carry: past it the set is kept at source
    scale with a note — FrameSvg cannot fit 36 px of caps into a ~30 px
    Plasma list row and paints a degenerate sliver (StarEnli's 27 px
    MENU_SEL pill at 1.5x, chris's Kickoff screenshot 2026-09-01).
    ``clear_center`` (frame only) makes everything inside the caps — or
    inside the scaled ``__PADDING`` when that ring is wider — fully
    transparent, the way E16's ``DITEM_AREA`` covers the interior with
    its area window; the ring caps grow to the padding so the ``center``
    element (which must exist — a center-less set paints nothing) is
    entirely transparent. ``transform`` recolors the trimmed RGBA art
    before any of that (the viewitem builder's :func:`_brighten`); it must
    not resize — every cap and hint below is measured on its result.
    """
    found = _state_attr(spec, state)
    if found is None:
        return None
    state_attr, path = found
    with Image.open(path) as im:
        src = im.convert("RGBA")
    trimmed = _opaque_trim(src, spec.edge_for(state_attr))
    if trimmed is None:
        note = (
            f"plasmastyle: {spec.name} {path.name} is fully transparent "
            "below the shape-mask cutoff; set not shipped (Breeze fills in)"
        )
        if note not in theme.notes:
            theme.notes.append(note)
        return None
    src, edge, trims = trimmed
    if transform is not None:
        src = transform(src)
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
        edge = edge_override(edge, src_w, src_h, src)
    if close_open_edges:
        src, edge, closed = _close_open_edges(src, edge, trims)
        for side in closed:
            note = (
                f"plasmastyle: {spec.name} {path.name} {side} end was open "
                "(fill to the edge, no rim — E16 showed the menu background "
                f"through the gap); closed with the mirrored {_OPPOSITE[side]} "
                f"cap ({side} cap now {edge[_SIDE_INDEX[side]]} ref px), "
                "diverging from E16 on purpose (the open end read as a "
                "missing border)"
            )
            if note not in theme.notes:
                theme.notes.append(note)
    fitted = _fit_caps(edge, src_w, src_h)
    if fitted is not None:
        theme.notes.append(
            f"plasmastyle: {spec.name} edge_scaling {edge} exceeds its "
            f"{path.name} image; caps shrunk to {fitted} (E16 overlapping-"
            "cap art)"
        )
        edge = fitted
    scale = _surface_scale(theme, spec, edge)
    if max_v_chrome_px is not None and scale > 1:
        _, _, top_px, bottom_px = _scaled_caps(edge, src_w, src_h, scale)
        if top_px + bottom_px > max_v_chrome_px:
            note = (
                f"plasmastyle: menu/list selection art kept at source scale: "
                f"{top_px + bottom_px} px of caps would not fit a Plasma list "
                f"row (FrameSvg paints a sliver past {max_v_chrome_px} px; "
                "E16 rows were the art's own height)"
            )
            if note not in theme.notes:
                theme.notes.append(note)
            scale = 1.0
    img = _scaled(src, scale, theme.upscale)
    caps = _scaled_caps(edge, src_w, src_h, scale)
    if clear_center:
        pad = tuple(
            max(1, scale_px(v, scale)) if v > 0 else 0 for v in spec.padding
        )
        ring_l, ring_r = _shave_for_center(
            max(caps[0], pad[0]), max(caps[1], pad[1]), img.width
        )
        ring_t, ring_b = _shave_for_center(
            max(caps[2], pad[2]), max(caps[3], pad[3]), img.height
        )
        caps = (ring_l, ring_r, ring_t, ring_b)
        box = (ring_l, ring_t, img.width - ring_r, img.height - ring_b)
        if box[2] > box[0] and box[3] > box[1]:
            img = img.copy()
            img.paste((0, 0, 0, 0), box)
        tile_center = False
    if flat_center is not None:
        box = (caps[0], caps[2], img.width - caps[1], img.height - caps[3])
        if box[2] > box[0] and box[3] > box[1]:
            img = img.copy()
            img.paste((*flat_center, 255), box)
        tile_center = False
    if tile_center is None:
        tile_center = spec.fill_for(state_attr) != FILL_STRETCH
    try:
        _frame_group(canvas, prefix, img, caps, tile_center=tile_center)
    except ValueError:
        # Last resort only — _fit_caps should have prevented this.
        theme.notes.append(
            f"plasmastyle: {spec.name} edge_scaling {spec.edge_scaling} "
            f"exceeds its {path.name} image; whole image stretched instead"
        )
        _frame_group(canvas, prefix, img, (0, 0, 0, 0), tile_center=tile_center)
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
    canvas = _Canvas()
    _panel_tint_set(theme, canvas, alpha)
    return canvas.finish()


def _panel_tint_set(theme: Theme, canvas: _Canvas, alpha: float) -> None:
    """Emit the unprefixed flat-tint set (+ margin hints) onto *canvas*."""
    tint, _ = _panel_tint(theme)
    fill = f"fill:{_hex(tint)}"
    if alpha != 1:
        fill += f";opacity:{alpha}"
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


def _emit_panel_prefix_sets(
    theme: Theme,
    canvas: _Canvas,
    src: IClassSpec,
    prefixes: tuple[str, ...],
) -> bool:
    """Prefixed 9-part sets (+ cap-hugging margins) from *src*; False when
    the art turned out fully transparent (nothing emitted)."""
    for prefix in prefixes:
        caps = _emit_set(theme, canvas, prefix, src, "normal")
        if caps is None:
            return False
        _panel_margins(canvas, prefix, caps, theme.scale)
    return True


def build_panel_background(
    theme: Theme, *, alpha: float = PANEL_ALPHA, quiet: bool = False
) -> ET.Element:
    """``widgets/panel-background.svg`` — real E16 bar art where it passes
    the guards, a flat translucent tint (at *alpha*) where it does not.

    Three layers, one file (Panel.qml's ``[pre, ""]`` prefix list):

    * The UNPREFIXED set serves every orientation and is the fallback for
      all of them; its caps are also what plasmashell turns into EVERY
      panel's minimum thickness (verified live 2026-09-01: e13's 60 px
      wordmark caps forced the 60 px iconbox panel to 120 px although a
      ``west-`` set existed), so it only ever carries art passing the
      STRICT :func:`_panel_art_guard` — small caps on both axes — else the
      tint. Middle stretched when E16 stretched it, tiled when E16 tiled.
    * ``north-``/``south-`` sets carry the wordmark bar art
      (``_panel_art_guard(wordmark=True)``: length caps up to
      ``PANEL_MAX_REF_LENGTH_CAPS``) when that differs from the
      unprefixed source — the horizontal bar shows E16's pinned wordmark,
      the vertical furniture never sees those caps. ``south-`` (foreign
      bottom bars) additionally requires the bar to be at least
      ``PANEL_WORDMARK_MIN_THICKNESS_REF`` thick; ``north-`` is exempt
      (``thin_ok``) because themey's own dragbar panel is 16 ref px
      thick — the corpus-median strip is exactly that.
    * ``west-``/``east-`` sets from the vertical bar art (iconbox trough
      first, ``_PANEL_VERT_SOURCES``), strict guard, then wordmark rules.

    Never returns None — a colors-only theme still gets a scheme-tinted
    panel. *quiet* suppresses the fidelity notes (the opaque mirror
    re-render in :func:`write`).
    """
    notes: list[str] = []
    canvas = _Canvas()
    src = _panel_art_source(theme)
    if src is not None:
        try:
            caps = _emit_set(theme, canvas, "", src, "normal")
        except (OSError, ValueError) as exc:
            caps = None
            notes.append(
                f"plasmastyle: panel art from {src.name} unreadable "
                f"({exc}); falling back to the flat tint"
            )
        if caps is None:
            src = None
        else:
            _panel_margins(canvas, "", caps, theme.scale)
    if src is None:
        _panel_tint_set(theme, canvas, alpha)

    # north- (themey's own 16 ref px dragbar panel; thin strips allowed)
    # and south- (foreign bottom bars; thickness guard kept) resolve
    # separately — e13's 6 px strip ships north but not south.
    north = _panel_art_source(theme, wordmark=True, thin_ok=True)
    if north is not None and (src is None or north.name != src.name):
        if not _emit_panel_prefix_sets(theme, canvas, north, ("north-",)):
            north = None
    else:
        north = None
    south = _panel_art_source(theme, wordmark=True)
    if south is not None and (src is None or south.name != src.name):
        if not _emit_panel_prefix_sets(theme, canvas, south, ("south-",)):
            south = None
    else:
        south = None

    vert = _panel_art_source(theme, _PANEL_VERT_SOURCES)
    if vert is None:
        vert = _panel_art_source(theme, _PANEL_VERT_SOURCES, wordmark=True)
    if vert is not None:
        if not _emit_panel_prefix_sets(theme, canvas, vert, ("west-", "east-")):
            vert = None

    if src is not None:
        notes.append(
            f"plasmastyle: panel background from iclass {src.name} art "
            "(shared set; caps stay pinned, middle stretched unless E16 "
            "tiled it)"
        )
    else:
        tint, source = _panel_tint(theme)
        notes.append(
            f"plasmastyle: panel background is a translucent tint rgb{tint} "
            f"(alpha {alpha}) of {source} — no E16 bar art passed the "
            "shaped/cap guards for the shared set"
        )
    if north is not None and south is not None and north.name == south.name:
        notes.append(
            f"plasmastyle: horizontal panels wear the {north.name} "
            "wordmark art (north-/south- sets; the shared set stays "
            "cap-free because Plasma makes its caps every panel's minimum "
            "thickness)"
        )
    else:
        if north is not None:
            notes.append(
                f"plasmastyle: top panels wear the {north.name} wordmark "
                "art (north- set only — themey's dragbar panel is 16 ref px "
                "thick, so the strip is not stretched past what E16 did)"
            )
        if south is not None:
            notes.append(
                f"plasmastyle: bottom panels wear the {south.name} wordmark "
                "art (south- set)"
            )
    if vert is not None:
        notes.append(f"plasmastyle: vertical panels from {vert.name}")
    if src is not None or north is not None or south is not None or vert is not None:
        notes.append(
            "plasmastyle: panel margin hints hug the cap art (cap − 4 px per "
            "side; E16 __PADDING dropped — Plasma pads panel content on top "
            "of the frame margins, and the sum read as an empty trough)"
        )
    if not quiet:
        for n in notes:
            if n not in theme.notes:
                theme.notes.append(n)
    return canvas.finish()


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
        side: _load_scaled(p, scale, theme.upscale) for side, p in strips.items()
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
        loaded[corner] = _load_scaled(path, scale, theme.upscale)

    resolved = _resolve_dialog_source(theme)
    center_src, center_tiled = resolved if resolved is not None else (None, False)
    center_path = (
        _state_image(center_src, "normal") if center_src is not None else None
    )
    center_img: Image.Image | None = None
    if center_path is not None:
        center_img = _load_scaled(center_path, scale, theme.upscale)
        if center_tiled:
            flat = _flat_center(center_path)
            if flat is not None:
                center_img = Image.new("RGBA", (4, 4), (*flat, 255))
                center_tiled = False

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
    if center_img is not None and center_tiled:
        ET.SubElement(
            canvas.root,
            f"{{{SVG_NS}}}rect",
            {
                "id": "hint-tile-center",
                "x": "0",
                "y": str(canvas.y),
                "width": "1",
                "height": "1",
                "style": "opacity:0",
            },
        )
        canvas.advance(1, 1)
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
        resolved = _resolve_dialog_source(theme)
        center_src, tiled = resolved if resolved is not None else (None, False)
        theme.notes.append(
            "plasmastyle: popup/dialog frame composed from menu frame "
            f"pieces {piece_names}"
            + (
                f" around a {center_src.name} center"
                + (_item_background_note(center_src) if tiled else "")
                if center_src is not None
                else " around a flat center (no unshaped background art)"
            )
            + "; no shadow set is shipped, so popups render shadowless "
            "(E16 drew none)"
        )
        return canvas.finish()

    resolved = _resolve_dialog_source(theme)
    if resolved is None:
        return None
    src, tiled = resolved
    canvas = _Canvas()
    flat = _flat_center(_state_image(src, "normal") or Path()) if tiled else None
    _emit_set(
        theme, canvas, "", src, "normal", hints=True,
        tile_center=True if tiled and flat is None else None,
        flat_center=flat,
    )
    if canvas.is_empty:
        return None
    theme.notes.append(
        f"plasmastyle: popup/dialog background from iclass {src.name}"
        + (_item_background_note(src) if tiled else "")
        + "; no shadow set is shipped, so popups render shadowless (E16 drew none)"
    )
    return canvas.finish()


#: The tooltip E16 shows for every window/button hint — ``TooltipShow``
#: (tooltips.c:752) looks ``DEFAULT`` up by name; ``ICONBOX``/``PAGER``
#: dress only those two windows.
_TOOLTIP_NAME = "DEFAULT"


def _tooltip_sources(theme: Theme) -> tuple[str, ...]:
    """Iclass names for the tooltip art, best first: the parsed ``DEFAULT``
    ``__TOOLTIP`` block's ``__ICLASS`` (11/223 corpus themes name TT_MINI,
    BAR, COORDS or TT_CLOUD there), then the ``TT_MAIN`` convention."""
    tip = theme.tooltips.get(_TOOLTIP_NAME)
    names: list[str] = [tip.iclass] if tip is not None else []
    if "TT_MAIN" not in names:
        names.append("TT_MAIN")
    return tuple(names)


def _tooltip_tclass_name(theme: Theme) -> str:
    """The DEFAULT tooltip's own ``__TCLASS`` when the theme defines it
    (88/223 corpus blocks name TEXT1/TEXT2/COORDS/... rather than TT_TEXT),
    else the ``TT_TEXT`` convention. Two corpus blocks name an iclass by
    mistake: E16 painted those with its built-in fallback tclass
    (``TextclassAlloc(name, 1)`` → ``TextclassGetFallback``), themey with
    TT_TEXT, and a note says so."""
    tip = theme.tooltips.get(_TOOLTIP_NAME)
    if tip is not None:
        if tip.tclass in theme.tclasses:
            return tip.tclass
        _note_once(
            theme,
            f"plasmastyle: DEFAULT tooltip names undefined tclass {tip.tclass} "
            "(E16 painted its built-in fallback text); tooltip text from TT_TEXT",
        )
    return "TT_TEXT"


def _note_once(theme: Theme, note: str) -> None:
    if note not in theme.notes:
        theme.notes.append(note)


def _resolve_tooltip_source(theme: Theme) -> IClassSpec | None:
    """First :func:`_tooltip_sources` entry with normal art, noting when the
    DEFAULT tooltip's own iclass is passed over for lack of it.

    No shaped-art rejection here, unlike :func:`_resolve_dialog_source`:
    45/223 corpus ``TT_MAIN`` images (Aliens, e13, OldE, ...) are 10-31%
    transparent — rounded corners and clear margins that ``_emit_set``'s
    opaque trim already handles — and rejecting them would drop the tooltip
    frame those themes have shipped since the Plasma Style landed. Notes
    are deduplicated because ``style_scheme`` resolves again.
    """
    names = _tooltip_sources(theme)
    for i, name in enumerate(names):
        spec = theme.iclasses.get(name)
        if spec is not None and _state_image(spec, "normal") is not None:
            return spec
        if i == 0 and len(names) > 1:
            _note_once(
                theme,
                f"plasmastyle: DEFAULT tooltip iclass {name} has no normal "
                "art; tooltip background from TT_MAIN instead",
            )
    return None


def build_tooltip(theme: Theme) -> ET.Element | None:
    """``widgets/tooltip.svg`` from the DEFAULT tooltip's iclass
    (:func:`_resolve_tooltip_source`)."""
    src = _resolve_tooltip_source(theme)
    if src is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "", src, "normal", hints=True)
    if canvas.is_empty:
        return None
    theme.notes.append(f"plasmastyle: tooltip background from iclass {src.name}")
    return canvas.finish()


#: Push-button art, in preference order: ``DIALOG_WIDGET_BUTTON`` is E16's
#: real dialog push button (dialog.c:844 ``DITEM_BUTTON``); ``DIALOG_BUTTON``
#: dresses the background-chooser thumbnails (backgrounds.c:1689) and only
#: falls back to the widget button. 62/229 corpus themes author them
#: differently (2026-09-01 census), so the order matters.
_BUTTON_SOURCES: tuple[str, ...] = ("DIALOG_WIDGET_BUTTON", "DIALOG_BUTTON")


def build_button(theme: Theme) -> ET.Element | None:
    """``widgets/button.svg`` from ``_BUTTON_SOURCES``.

    ``focus-`` reuses the hilited art — E16 has no focus-ring concept. No
    ``toolbutton-*`` sets: PC3 falls back per-prefix to Breeze for those.
    """
    src = _iclass_with_art(theme, *_BUTTON_SOURCES)
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
    if canvas.is_empty:
        return None
    theme.notes.append(
        f"plasmastyle: widget buttons from iclass {src.name} "
        "(focus ring reuses the hilited art)"
    )
    return canvas.finish()


def _is_rounded(img: Image.Image) -> bool:
    """True when any corner of the (post-trim) art is cut by E16's shape
    mask (alpha < 128) — a rounded pill rather than a rectangular strip."""
    w, h = img.size
    alpha = img.convert("RGBA").getchannel("A")
    return any(
        int(alpha.getpixel((x, y)) or 0) < 128  # type: ignore[arg-type]
        for x, y in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1))
    )


#: Luminance std (0-255) a strip's middle band must show as RESIDUAL
#: grain to count as textured, and the three ways a gradient disqualifies
#: it. VERTICAL drift is capped twice — absolutely, and relative to the
#: grain — because repeating a vertical gradient bands even under heavy
#: grain (Aliens' bone-textured glow, drift_v 13.5, banded in the tall
#: selected cell, live render 2026-09-01). HORIZONTAL drift is capped only
#: RELATIVE to the grain: it disqualifies art whose sweep dominates
#: (Metallique's 21/2.4/33 sheen, ShinyMetal's 3.8/2.6/36.9 — tiled ~4x
#: down a Kickoff grid cell and seamed across a wide row, chris
#: 2026-09-01) but not merely streaky texture, since real grain is
#: directional (OldE's rust strip 10.4/4.0/10.2, whose smearing under a
#: stretch chris confirmed live the same day). Further calibration, as
#: grain/drift_v/drift_h: Luddite 32.1/5.0/28.7 and OldE-Black
#: 14.6/5.8/14.5 stay tiled; Hazard 0/0/8.5, LW2 0/0/30.7 and Mac3D
#: 0.5/4.0/22.4 are bevels with no grain at all and stretch.
_TEXTURE_MIN_GRAIN = 8.0
_TEXTURE_GRAIN_OVER_DRIFT_V = 1.5
_TEXTURE_MAX_DRIFT_V = 8.0
_TEXTURE_MAX_DRIFT_H_OVER_GRAIN = 1.5


def _band_stats(
    img: Image.Image, caps: tuple[int, int, int, int]
) -> tuple[float, float, float] | None:
    """``(grain, drift_v, drift_h)`` for the band inside *caps*, or None
    when that band is smaller than 2x2.

    All three are luminance standard deviations in 0-255. ``drift_v`` is
    the spread of the band's ROW means (a vertical gradient), ``drift_h``
    the spread of its COLUMN means (a horizontal one). ``grain`` is the
    mean per-row spread of the RESIDUAL — pixel minus its column mean
    minus its row mean plus the band mean — so a smooth gradient along
    EITHER axis leaves no grain behind. Measuring the raw within-row
    spread instead (the pre-2026-09-01 form) read ShinyMetal's
    left-to-right sheen as heavy grain.
    """
    import statistics

    left, right, top, bottom = caps
    lum = img.convert("L")
    w, h = lum.size
    bw, bh = w - left - right, h - top - bottom
    if bw < 2 or bh < 2:
        return None
    data = lum.crop((left, top, w - right, h - bottom)).tobytes()
    rows = [list(data[y * bw:(y + 1) * bw]) for y in range(bh)]
    row_means = [statistics.fmean(r) for r in rows]
    col_means = [statistics.fmean([row[x] for row in rows]) for x in range(bw)]
    mean = statistics.fmean(row_means)
    grains = [
        statistics.pstdev(
            [row[x] - col_means[x] - row_mean + mean for x in range(bw)]
        )
        for row, row_mean in zip(rows, row_means, strict=True)
    ]
    return (
        statistics.fmean(grains),
        statistics.pstdev(row_means),
        statistics.pstdev(col_means),
    )


def _middle_is_textured(img: Image.Image, caps: tuple[int, int, int, int]) -> bool:
    """True when the band between the caps is grain rather than a gradient
    on either axis or a flat fill — the case where repeating the middle
    keeps the art's look and stretching it smears it. See
    :func:`_band_stats` for the three measurements."""
    stats = _band_stats(img, caps)
    if stats is None:
        return False
    grain, drift_v, drift_h = stats
    return (
        grain >= _TEXTURE_MIN_GRAIN
        and drift_v <= _TEXTURE_MAX_DRIFT_V
        and grain > _TEXTURE_GRAIN_OVER_DRIFT_V * drift_v
        and drift_h <= _TEXTURE_MAX_DRIFT_H_OVER_GRAIN * grain
    )


#: How much brighter ``selected+hover-`` is than ``selected-``. Kickoff
#: paints the combined prefix ONLY while the mouse is held down on a
#: hovered item; E16 had no such state, so a byte-identical set left the
#: two indistinguishable. 8% is enough to read as "pressed under the
#: cursor" without inventing art the theme does not have.
VIEWITEM_PRESSED_HOVER_BRIGHTNESS = 1.08


def _brighten(img: Image.Image) -> Image.Image:
    """*img* brightened by :data:`VIEWITEM_PRESSED_HOVER_BRIGHTNESS`.

    A per-pixel channel multiply on the RGB planes with the alpha plane
    put back untouched — E16's shape mask must survive verbatim, and
    nothing is resampled, so this stays clear of the NEAREST-only rule for
    pixel art.
    """
    rgba = img.convert("RGBA")
    out = ImageEnhance.Brightness(rgba.convert("RGB")).enhance(
        VIEWITEM_PRESSED_HOVER_BRIGHTNESS
    ).convert("RGBA")
    out.putalpha(rgba.getchannel("A"))
    return out


def _viewitem_caps(
    edge: tuple[int, int, int, int], w: int, h: int, *, rounded: bool = True
) -> tuple[tuple[int, int, int, int], str]:
    """Synthetic caps for highlight art, in source ref px, plus the branch
    taken (``"pill"`` / ``"bevel"`` / ``"declared"``) for the fidelity note.

    E16 only ever stretched menu-item art HORIZONTALLY — an item's height
    equals the art's height — but Plasma paints ``widgets/viewitem`` over
    grid cells and wide dropdown rows, stretching both axes. A glow pill
    stretched whole (MENU_SEL commonly declares ``__EDGE_SCALING 0 0 0 0``)
    smears into a blurry bright blob (verified live on e13's Kickoff,
    2026-08-31).

    Two branches on the post-trim art's cross-section:

    * PILL (``min(w, h) <= VIEWITEM_PILL_MAX_REF``): caps are pinned at
      the cross-section radius (declared caps larger than it survive) so
      the rounded ends and vertical shading stay crisp; only the
      near-uniform middle band stretches. Applies to ROUNDED art (a corner
      cut by the shape mask, ``_is_rounded``) and to any axis whose
      declared caps are zero (E16 stretched the whole strip there).
    * BEVEL (pill-sized but rectangular — OldE's opaque 213x16 bevel strip
      with ``__EDGE_SCALING 3 3 3 3``): the declared caps are honored on
      every axis that declares them. The radius pin left a 2-row middle
      that Kickoff stretched ten times taller into a flat band (chris,
      2026-09-01); E16 kept exactly those 3 px bevels crisp and stretched
      the textured middle.
    * DECLARED (larger art — a whole menu background): the declared edge
      is honored. E16 squished such art into the item, and the declared
      caps are exactly what it kept crisp; the radius heuristic turned a
      64x64 tile into 31 px caps and IceBerg's 256x256 into 127.

    In both branches every cap is clamped to ``VIEWITEM_MAX_REF_CAP`` and
    to ``(dim - 1) // 2`` so a real center always survives; the clamp also
    symmetrizes asymmetric ``__EDGE_SCALING`` (StarEnli 64/14 → 12/12).
    """
    left, right, top, bottom = edge
    if min(w, h) <= VIEWITEM_PILL_MAX_REF:
        radius = max(1, (min(w, h) - 2) // 2)
        pin_x = rounded or (left == 0 and right == 0)
        pin_y = rounded or (top == 0 and bottom == 0)
        if pin_x:
            left, right = max(left, radius), max(right, radius)
        if pin_y:
            top, bottom = max(top, radius), max(bottom, radius)
        branch = "pill" if (pin_x and pin_y) else "bevel"
    else:
        branch = "declared"
    max_x = min(VIEWITEM_MAX_REF_CAP, (w - 1) // 2)
    max_y = min(VIEWITEM_MAX_REF_CAP, (h - 1) // 2)
    caps = (min(left, max_x), min(right, max_x), min(top, max_y), min(bottom, max_y))
    return caps, branch


def build_viewitem(theme: Theme) -> ET.Element | None:
    """``widgets/viewitem.svg`` from ``MENU_SEL``.

    Only ``hover-``/``selected-``/``selected+hover-`` are emitted, never
    ``normal-``: Plasma's ``PlasmaExtras.Highlight`` paints the ``normal``
    prefix for a current-but-unhovered item (Kicker, folder views — Kickoff
    forces ``hovered: true``) at 0.6 opacity, whereas E16 painted MENU_SEL's
    normal art on EVERY row; neither semantic matches the other and Breeze
    ships no ``normal`` prefix either. Every set is capped at
    ``VIEWITEM_MAX_ROW_CHROME_PX`` output px of vertical chrome (kept at
    source scale past it) so it fits a Plasma list row. All sets use
    :func:`_viewitem_caps` in place of the declared edge — see its
    docstring for why the declared edge cannot be trusted here — and are
    the ONE caller of :func:`_close_open_edges` (an open pill end reads as
    a missing border on a Plasma list). Fully transparent art (five corpus
    themes) leaves the file to Breeze.
    """
    src = theme.iclasses.get("MENU_SEL")
    if _state_image(src, "hover") is None or src is None:
        return None
    canvas = _Canvas()
    decisions: dict[tuple[str, tuple[int, int, int, int], bool], None] = {}

    def caps_override(
        edge: tuple[int, int, int, int], w: int, h: int, img: Image.Image
    ) -> tuple[int, int, int, int]:
        caps, branch = _viewitem_caps(edge, w, h, rounded=_is_rounded(img))
        tiled = branch == "bevel" and _middle_is_textured(img, caps)
        decisions[(branch, caps, tiled)] = None
        return caps

    def repeats_middle(state: str) -> bool | None:
        """Decide the tile hint up front (``_emit_set`` needs it before the
        override runs): a rectangular strip whose middle is grain repeats
        — E16 rows were the art's own height, so the grain was never
        stretched, while a Kickoff row is about twice as tall (OldE's rust
        strip smeared, chris 2026-09-01). Gradient middles (Aliens' glow)
        keep stretching: tiling a gradient shows seams."""
        found = _state_attr(src, state)
        if found is None:
            return None
        state_attr, path = found
        try:
            with Image.open(path) as im:
                trimmed = _opaque_trim(im.convert("RGBA"), src.edge_for(state_attr))
        except (OSError, ValueError):
            return None
        if trimmed is None:
            return None
        img, edge, _ = trimmed
        caps, branch = _viewitem_caps(edge, img.width, img.height, rounded=_is_rounded(img))
        return True if branch == "bevel" and _middle_is_textured(img, caps) else None

    # ``selected+hover-`` is the same art lightened when the theme HAS
    # clicked art to press; without it the "selected" chain has already
    # fallen back to the hover art and lightening would invent a state.
    pressed = _state_attr(src, "selected")
    lit = pressed is not None and pressed[0].startswith("clicked")
    sets = [("hover-", "hover", None), ("selected-", "selected", None),
            # Literal "+" in the id — FrameSvg's combined-state prefix.
            ("selected+hover-", "selected", _brighten if lit else None)]
    for prefix, state, transform in sets:
        _emit_set(
            theme, canvas, prefix, src, state,
            edge_override=caps_override, close_open_edges=True,
            tile_center=repeats_middle(state),
            max_v_chrome_px=VIEWITEM_MAX_ROW_CHROME_PX,
            transform=transform,
        )
    if canvas.is_empty:
        return None
    if lit:
        theme.notes.append(
            f"plasmastyle: selected+hover from {src.name}'s clicked art "
            f"lightened {(VIEWITEM_PRESSED_HOVER_BRIGHTNESS - 1) * 100:.0f}% "
            "(Kickoff paints that prefix only while the mouse is held down on "
            "a hovered item; E16 had no such state and an identical set left "
            "it indistinguishable from the pressed one)"
        )
    for branch, caps, tiled in decisions:
        if branch == "pill":
            why = (
                "pinned at the art's cross-section radius (pill art; E16 never "
                "stretched item height)"
            )
        elif branch == "bevel":
            why = (
                "the declared __EDGE_SCALING (rectangular strip; E16 kept "
                "those bevels crisp and stretched the middle)"
            )
        else:
            why = (
                "the declared __EDGE_SCALING (menu-background art E16 "
                "squished into the item)"
            )
        theme.notes.append(
            f"plasmastyle: menu/list selection from iclass {src.name}; caps "
            f"{why}, clamped to {VIEWITEM_MAX_REF_CAP} ref px → "
            f"{caps[0]}/{caps[1]}/{caps[2]}/{caps[3]} (L/R/T/B)"
            + (
                "; middle repeated (textured strip — E16 rows were the art's "
                "own height, Plasma rows are taller, and repeating keeps the "
                "grain instead of smearing it)"
                if tiled
                else ""
            )
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
    if _emit_set(theme, canvas, "slider-", knob, "normal") is None:
        return None
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
        img = _load_scaled(sources[element], theme.scale, theme.upscale)
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

    themey's own pager applet (``org.themey.pager``, E16's LIVE mode
    replayed at runtime) reads the same file and adds two prefixes:
    ``window-`` from ``PAGER_WIN`` normal art (E16's window-rect art,
    223/223 corpus themes) and ``window-active-`` from its explicit
    hilited art when authored (:func:`_hilited_image`), so the active
    window's rect can differ. The applet falls back to stock-style
    ``Kirigami.Theme.textColor`` rects when ``window-center`` is absent.
    Both the stock and the themey pager keep a MISSING ``normal-`` layer
    invisible — intended for a transparent/absent ``PAGER_BACKGROUND``:
    the applet paints the live wallpaper mini there instead.
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
    if _emit_set(theme, canvas, "active-", sel, "normal") is None:
        return None
    _emit_set(theme, canvas, "hover-", sel, "hover")
    theme.notes.append(
        f"plasmastyle: pager cells from iclass {sel.name}"
        + (f" (normal desks from {bg.name})" if bg is not None else "")
        + "; cells carry no baked desktop preview — themey's pager applet "
        "paints the live wallpaper at runtime (a baked mini would go stale)"
    )
    win = _iclass_with_art(theme, "PAGER_WIN")
    if win is not None and _emit_set(theme, canvas, "window-", win, "normal") is not None:
        hilited = _hilited_image(win)
        active = ""
        if hilited is not None:
            _emit_set(theme, canvas, "window-active-", win, "hover")
            active = " (active window from its hilited art)"
        theme.notes.append(
            f"plasmastyle: pager window rects from iclass {win.name}{active}"
        )
    return canvas.finish()


#: ((direction element, orientation), (E16 iclass)) for the dragbar desk
#: buttons. E16's DEFAULT dragbar ordering (desktops.c, ordering 1) puts
#: DESKTOP_RAISEBUTTON at the bar's START running ``desk next`` and
#: DESKTOP_LOWERBUTTON at its END running ``desk prev`` — so the elements
#: are named by ACTION (what the applet needs), not by the iclass's
#: raise/lower name.
_DRAGBAR_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("next", "horiz", "DESKTOP_RAISEBUTTON_HORIZ"),
    ("prev", "horiz", "DESKTOP_LOWERBUTTON_HORIZ"),
    ("next", "vert", "DESKTOP_RAISEBUTTON_VERT"),
    ("prev", "vert", "DESKTOP_LOWERBUTTON_VERT"),
)
_DRAGBAR_STATES: tuple[str, ...] = ("normal", "hover", "pressed")


def build_dragbar(theme: Theme) -> ET.Element | None:
    """``widgets/themey-dragbar.svg`` — the E16 dragbar's desk buttons.

    E16 synthesizes its top bar in C (desktops.c:95-346): a 16 px strip
    per desktop made of DESKTOP_RAISEBUTTON (start, ``desk next``),
    DESKTOP_DRAGBUTTON (stretched across — the ``north-`` panel set) and
    DESKTOP_LOWERBUTTON (end, ``desk prev``). This file carries the two
    end buttons as plain elements ``<next|prev>-<horiz|vert>-<normal|
    hover|pressed>`` (states via the module state map; a missing state
    reuses normal as E16 does), scaled by ``theme.scale`` like every
    glyph here. Only themey's ``org.themey.deskbutton`` applet reads it:
    no Breeze fallback semantics apply (the applet falls back to
    ``widgets/arrows`` per missing element), so a single horizontal
    button ships alone and no shaped-art guard runs (these are 16×16
    glyphs, transparent corners and all). Skipped, with a note, when
    neither HORIZ iclass has normal art — the dragbar panel is
    horizontal; the ``vert`` quartet is optional extra.
    """
    horiz = [
        (d, o, name) for d, o, name in _DRAGBAR_SOURCES
        if o == "horiz" and _state_image(theme.iclasses.get(name), "normal") is not None
    ]
    if not horiz:
        theme.notes.append(
            "plasmastyle: no DESKTOP_RAISEBUTTON_HORIZ/DESKTOP_LOWERBUTTON_HORIZ "
            "art; the dragbar desk buttons fall back to widgets/arrows"
        )
        return None
    canvas = _Canvas()
    shipped: list[str] = []
    for direction, orient, name in _DRAGBAR_SOURCES:
        spec = theme.iclasses.get(name)
        if _state_image(spec, "normal") is None:
            continue
        assert spec is not None
        items: list[tuple[str, Image.Image]] = []
        for state in _DRAGBAR_STATES:
            path = _state_image(spec, state)
            assert path is not None  # normal exists, every chain ends there
            items.append((
                f"{direction}-{orient}-{state}",
                _load_scaled(path, theme.scale, theme.upscale),
            ))
        _emit_plain_row(canvas, items)
        if orient == "horiz":
            shipped.append(name)
    theme.notes.append(
        f"plasmastyle: dragbar desk buttons from iclass {'+'.join(shipped)} "
        "(E16 desktops.c: raise = desk next at the bar's start, lower = "
        "desk prev at its end)"
    )
    return canvas.finish()


#: ``--iconbox-frames``: ``off`` (the DEFAULT) replays E16's own iconbox —
#: ``container.c:98-114`` ``draw_icon_base = 0``: no per-icon plate, bare
#: icons on the trough; ``on`` ships the iconbox button art as task frames
#: (``DEFAULT_ICON_BUTTON`` art is seen nowhere else, so it is worth an
#: opt-in). Off is the default since 2026-09-01: a plate under every icon
#: on the bottom bar most users keep is E16's own look only by accident.
ICONBOX_FRAME_MODES: tuple[str, ...] = ("off", "on")

#: OUTPUT-px thickness of the synthesized focus bar. Not scaled: it is a
#: Plasma affordance (Breeze paints the same 2 px accent), not E16 art.
TASKS_FOCUS_BAR_PX = 2
#: How far toward white the synthesized hover plate is blended from the
#: normal one, and the alpha of the equivalent white wash in frames-OFF
#: mode.
TASKS_HOVER_LIGHTEN = 0.12
#: How far toward white the synthesized attention plate is blended from
#: the HOVER one (not from normal) — attention must read distinctly
#: ABOVE hover, and 25 % off the normal plate lands only 13 % above it.
#: Compounded that is 1 − 0.88 × 0.75 = 34 % toward white. In frames-OFF
#: mode it is the white wash's alpha, straight off the trough.
TASKS_ATTENTION_LIGHTEN = 0.25
#: Alpha the synthesized ``minimized-`` plate keeps — E16 has no such
#: state, and a faded plate reads as "put away" at a glance.
TASKS_MINIMIZED_ALPHA = 0.55

#: KSvg stylesheet class for the active colour scheme's selection
#: background (``.ColorScheme-Highlight``; the full class list is built
#: from ``.ColorScheme-%1{color:%2;}`` in ksvg 6.24 ``imageset.cpp``).
_HIGHLIGHT_CLASS = "ColorScheme-Highlight"

#: Task-manager prefixes that ship in every ``widgets/tasks.svg``
#: (per-FILE fallback — a missing prefix would paint nothing), as
#: ``(prefix, E16 state, synthesized state)``. The synthesized state
#: stands in whenever the E16 chain for that prefix falls back to the
#: NORMAL art — most corpus iconbox buttons declare only ``__NORMAL``,
#: which used to make all seven sets byte-identical (Aliens, e13,
#: ShinyMetal): active/minimized/hover were indistinguishable. ``None``
#: never synthesizes (the normal plate IS the right art there).
_TASKS_PREFIXES: tuple[tuple[str, str, str | None], ...] = (
    ("normal-", "normal", None),
    ("minimized-", "normal", "minimized"),  # no E16 counterpart at all
    ("", "normal", None),  # launcher frame
    ("hover-", "hover", "hover"),
    ("attention-", "hover", "attention"),
    ("progress-", "hover", "progress"),
    ("focus-", "pressed", "focus"),
)
#: Hover-on-state prefixes, shipped only when the iconbox button has its
#: own hilited art: a pinned launcher under the mouse reads
#: ``launcher-hover-`` and never falls back to plain ``hover-``; the
#: active task under the mouse reads ``focus-hover-`` (clicked chain —
#: the depressed button stays depressed) and its synthesized recipe is
#: BOTH — hover on top of focus, or the depressed plate would give no
#: hover feedback at all.
_TASKS_HOVER_PREFIXES: tuple[tuple[str, str, str | None], ...] = (
    ("launcher-hover-", "hover", "hover"),
    ("focus-hover-", "pressed", "focus-hover"),
)
#: Synthesized states that wear the accent bar, one set per
#: ``_TASKS_FOCUS_EDGES`` entry — every state that means "this is the
#: active task".
_TASKS_BAR_STATES: tuple[str, ...] = ("focus", "focus-hover")
#: (FrameSvg edge prefix, panel-adjacent side) for the focus sets.
#: ``Task.qml``'s prefix chain is ``["<edge>-<p>", "<p>"]``, so the
#: UNPREFIXED set is the one a bottom panel gets — the common case — and
#: its bar sits on the BOTTOM edge; Breeze ships exactly the other three
#: edge variants, which is why themey ships those names and no ``south-``.
_TASKS_FOCUS_EDGES: tuple[tuple[str, str], ...] = (
    ("", "bottom"),
    ("north-", "top"),
    ("west-", "left"),
    ("east-", "right"),
)
#: The three 9-patch slices along each edge, outermost cap first — the
#: focus bar is painted across all three so it spans the whole item.
_BAR_GRID: dict[str, tuple[str, str, str]] = {
    "top": ("topleft", "top", "topright"),
    "bottom": ("bottomleft", "bottom", "bottomright"),
    "left": ("topleft", "left", "bottomleft"),
    "right": ("topright", "right", "bottomright"),
}
#: White-wash alpha per synthesized state in frames-OFF mode. States not
#: listed (``focus``, ``minimized``) stay fully transparent — focus wears
#: the accent bar instead, and a minimized icon is already dimmed by the
#: task manager itself.
_TASKS_OFF_ALPHA: dict[str, float] = {
    "hover": TASKS_HOVER_LIGHTEN,
    "progress": TASKS_HOVER_LIGHTEN,
    "attention": TASKS_ATTENTION_LIGHTEN,
    # The active task under the mouse wears the bar AND the hover wash.
    "focus-hover": TASKS_HOVER_LIGHTEN,
}
#: Iconbox trough iclasses whose ``__PADDING`` spaces the bare icons in
#: frames-off mode (E16 ``container.c``: icons sit ``__PADDING`` apart
#: inside the trough).
_ICONBOX_TROUGH_SOURCES: tuple[str, ...] = ("ICONBOX_VERTICAL", "ICONBOX_HORIZONTAL")

#: (element direction, ICONBOX arrow iclass) for the task-group expanders.
_EXPANDER_SOURCES: tuple[tuple[str, str], ...] = (
    ("left", "ICONBOX_ARROW_LEFT"),
    ("right", "ICONBOX_ARROW_RIGHT"),
    ("top", "ICONBOX_ARROW_UP"),
    ("bottom", "ICONBOX_ARROW_DOWN"),
)


def _tasks_source(theme: Theme) -> IClassSpec | None:
    """The iconbox button iclass the task frames come from."""
    return _iclass_with_art(theme, "DEFAULT_ICON_BUTTON", "DEFAULT_DOCK_BUTTON")


def tasks_hover(theme: Theme, *, iconbox_frames: str = "off") -> bool:
    """Whether the shipped ``widgets/tasks.svg`` has a hover frame of its
    own — the value apply writes into the iconbox task manager's
    ``taskHoverEffect`` (``metadata.json`` ``X-Themey-TasksHover``).

    True whenever a tasks.svg ships at all since 2026-09-01: the hover
    frame is either the iclass's own hilited art or synthesized from the
    normal plate (:func:`_synth_task_states` — a 12 % lightened plate, or
    a 12 %-alpha white wash in frames-OFF mode), so the hover animation
    always has something of its own to show. It used to require explicit
    ``__HILITED`` art, which the corpus almost never declares. False only
    when no file ships (frames ON with no iconbox button art) and Plasma
    paints Breeze's frames instead.
    """
    return iconbox_frames == "off" or _tasks_source(theme) is not None


def _lighten(img: Image.Image, fraction: float) -> Image.Image:
    """Blend *img*'s RGB *fraction* of the way to white, alpha untouched."""
    r, g, b, a = img.split()
    white = Image.new("L", img.size, 255)
    return Image.merge(
        "RGBA",
        (
            Image.blend(r, white, fraction),
            Image.blend(g, white, fraction),
            Image.blend(b, white, fraction),
            a,
        ),
    )


def _fade(img: Image.Image, fraction: float) -> Image.Image:
    """Multiply *img*'s alpha channel by *fraction*."""
    r, g, b, a = img.split()
    return Image.merge("RGBA", (r, g, b, a.point(lambda v: int(v * fraction))))


def _synth_task_states(src: Image.Image) -> dict[str, Image.Image]:
    """The task states E16's iconbox button never authored, derived from
    the normal plate *src* (already opaque-trimmed and scaled).

    E16's iconbox knows one button look plus optional ``__HILITED`` /
    ``__CLICKED`` art, and most corpus themes declare neither — so
    Plasma's seven task prefixes all resolved to the same plate and an
    active, a minimized and a hovered task were indistinguishable. These
    are pure pixel ops on the theme's own art, never invented chrome:
    hover blends toward white (the plate reads "lit", the way E16's own
    hilited art always did), ``attention`` blends the HOVER plate
    further so it stays distinct from a mere hover, ``focus`` flips the
    plate VERTICALLY so a bevel's light and dark edges swap — E16's
    depressed button in one operation — ``focus-hover`` lightens THAT
    flipped plate so the active task still answers the mouse (as plain
    ``focus`` it was byte-identical to the unhovered active task), and
    ``minimized`` fades it out. Every ``_TASKS_BAR_STATES`` entry
    additionally wears the accent bar :func:`_emit_task_frame` paints.
    """
    hover = _lighten(src, TASKS_HOVER_LIGHTEN)
    focus = ImageOps.flip(src)
    return {
        "hover": hover,
        "progress": hover,
        "attention": _lighten(hover, TASKS_ATTENTION_LIGHTEN),
        "minimized": _fade(src, TASKS_MINIMIZED_ALPHA),
        "focus": focus,
        "focus-hover": _lighten(focus, TASKS_HOVER_LIGHTEN),
    }


@dataclass(frozen=True)
class _TaskPlate:
    """The normal plate every synthesized task state derives from."""

    #: Trimmed, scaled RGBA art.
    img: Image.Image
    #: OUTPUT-px 9-patch caps (L R T B), post-shave.
    caps: tuple[int, int, int, int]
    #: The scale ``_surface_scale`` chose for this art.
    scale: float
    #: Whether E16 TILED the normal state (``__FILLRULE __TILE*``). The
    #: synthesized sets MUST carry the same choice: a tiled ``normal-``
    #: next to stretched hover/focus sets changes the frame's texture
    #: the moment the mouse touches it.
    tile_center: bool


def _task_plate(theme: Theme, spec: IClassSpec) -> _TaskPlate | None:
    """The normal plate, its caps, scale and fill rule — see :class:`_TaskPlate`.

    Mirrors :func:`_emit_set`'s art pipeline (opaque trim → cap fit →
    surface scale → cap shave → ``fill_for``) without re-emitting its
    notes: :func:`build_tasks` always emits the ``normal-`` set from this
    very art through ``_emit_set`` first, so whatever notes it earns are
    on ``theme.notes`` already.
    """
    found = _state_attr(spec, "normal")
    if found is None:
        return None
    state_attr, path = found
    with Image.open(path) as im:
        raw = im.convert("RGBA")
    trimmed = _opaque_trim(raw, spec.edge_for(state_attr))
    if trimmed is None:
        return None
    art, edge, _ = trimmed
    edge = _fit_caps(edge, art.width, art.height) or edge
    scale = _surface_scale(theme, spec, edge)
    img = _scaled(art, scale, theme.upscale)
    caps = _scaled_caps(edge, art.width, art.height, scale)
    left, right = _shave_for_center(caps[0], caps[1], img.width)
    top, bottom = _shave_for_center(caps[2], caps[3], img.height)
    return _TaskPlate(
        img=img,
        caps=(left, right, top, bottom),
        scale=scale,
        tile_center=spec.fill_for(state_attr) != FILL_STRETCH,
    )


def _grow_for_bar(
    img: Image.Image, caps: tuple[int, int, int, int], edge: str
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    """Add a ``TASKS_FOCUS_BAR_PX`` transparent strip on *edge* and widen
    that cap to cover it, so the bar becomes its own 9-patch row/column
    and the plate's own bevel cap survives underneath."""
    bar = TASKS_FOCUS_BAR_PX
    left, right, top, bottom = caps
    if edge in ("top", "bottom"):
        out = Image.new("RGBA", (img.width, img.height + bar), (0, 0, 0, 0))
        out.paste(img, (0, bar if edge == "top" else 0))
        top, bottom = (top + bar, bottom) if edge == "top" else (top, bottom + bar)
    else:
        out = Image.new("RGBA", (img.width + bar, img.height), (0, 0, 0, 0))
        out.paste(img, (bar if edge == "left" else 0, 0))
        left, right = (left + bar, right) if edge == "left" else (left, right + bar)
    return out, (left, right, top, bottom)


def _paint_edge_bar(canvas: _Canvas, prefix: str, edge: str) -> None:
    """Overlay the highlight bar on the outer ``TASKS_FOCUS_BAR_PX`` of
    every slice along *edge* of the set just emitted for *prefix*.

    A classed rect inside the border ``<g>`` — exactly how Breeze's own
    ``widgets/tasks.svg`` paints its focus accent — so KSvg re-tints it
    from the ACTIVE colour scheme rather than from baked pixels. All
    three slices are painted (cap, middle, cap) so the bar spans the
    whole item instead of stopping at the corners.
    """
    bar = TASKS_FOCUS_BAR_PX
    for name in _BAR_GRID[edge]:
        group = _find_element(canvas, f"{prefix}{name}")
        if group is None:
            continue
        image = group.find(f"{{{SVG_NS}}}image")
        if image is None:
            continue
        x, y = int(image.get("x", "0")), int(image.get("y", "0"))
        w, h = int(image.get("width", "0")), int(image.get("height", "0"))
        # min() keeps the rect inside a slice that _shave_for_center made
        # thinner than the bar; the bar then IS the whole cap.
        if edge in ("top", "bottom"):
            thick = min(bar, h)
            box = (x, y + h - thick if edge == "bottom" else y, w, thick)
        else:
            thick = min(bar, w)
            box = (x + w - thick if edge == "right" else x, y, thick, h)
        ET.SubElement(
            group,
            f"{{{SVG_NS}}}rect",
            {
                "x": str(box[0]), "y": str(box[1]),
                "width": str(box[2]), "height": str(box[3]),
                "class": _HIGHLIGHT_CLASS,
                "style": "fill:currentColor",
            },
        )


def _find_element(canvas: _Canvas, element_id: str) -> ET.Element | None:
    """The top-level canvas element with *element_id*, or None."""
    for el in canvas.root:
        if el.get("id") == element_id:
            return el
    return None


def _color_stylesheet(root: ET.Element, highlight: RGB) -> None:
    """Prepend the ``current-color-scheme`` stylesheet KSvg rewrites.

    KSvg looks for an element with exactly this id and, when it is there,
    swaps the sheet's body for the ACTIVE colour scheme's
    ``.ColorScheme-*`` classes before handing the file to QSvgRenderer —
    the mechanism every Breeze widget SVG uses. The authored declaration
    is only the fallback for renderers that do NOT substitute (plain
    rsvg, themey's own probe), so it carries the theme's own sampled
    selection background rather than a Breeze blue.
    """
    style = ET.Element(
        f"{{{SVG_NS}}}style",
        {"id": "current-color-scheme", "type": "text/css"},
    )
    style.text = f".{_HIGHLIGHT_CLASS} {{ color:{_hex(highlight)}; }}"
    root.insert(0, style)


def _emit_task_frame(
    canvas: _Canvas,
    prefix: str,
    img: Image.Image,
    plate: _TaskPlate,
    padding: tuple[int, int, int, int],
    *,
    bar_edge: str | None = None,
) -> None:
    """Emit one SYNTHESIZED task set: *img* sliced at *plate*'s caps.

    Not :func:`_emit_set`: the art has no file path — it is derived from
    the normal plate by :func:`_synth_task_states`, whose notes and cap
    math the ``normal-`` set already carried. The plate's ``tile_center``
    comes along so a ``__FILLRULE __TILE*`` iclass does not change
    texture between its normal and its synthesized states. *bar_edge*
    adds the focus accent (:func:`_grow_for_bar` + :func:`_paint_edge_bar`).
    """
    caps = plate.caps
    if bar_edge is not None:
        img, caps = _grow_for_bar(img, caps, bar_edge)
    try:
        _frame_group(canvas, prefix, img, caps, tile_center=plate.tile_center)
    except ValueError:  # last resort — _task_plate already fitted the caps
        _frame_group(canvas, prefix, img, (0, 0, 0, 0), tile_center=plate.tile_center)
    else:
        if bar_edge is not None:
            _paint_edge_bar(canvas, prefix, bar_edge)
    _margin_hints(canvas, prefix, padding, plate.scale)


def _bar_margins(
    spec: IClassSpec, plate: _TaskPlate | None, focus_synthesized: bool
) -> tuple[int, int, int, int] | None:
    """OUTPUT-px margin hints every frames-ON task set must carry, or None
    when the sets already agree without them.

    FrameSvg falls back to a set's own BORDER THICKNESS for a side with no
    ``hint-<side>-margin``, and :func:`_grow_for_bar` makes the focus
    set's bar edge ``TASKS_FOCUS_BAR_PX`` thicker than every other set's.
    With a declared ``__PADDING`` that never shows — ``_emit_set`` and
    :func:`_emit_task_frame` both emit the same padding hints, which win.
    With NO padding there are no hints at all, so the active task would
    inset its icon 2 px further than the rest and the icon would visibly
    shift the moment a window took focus. Returning the plate's own caps
    (floored at 1 px — a zero-size hint rect has no bounds for FrameSvg
    to read) pins every set to the same margins.
    """
    if plate is None or not focus_synthesized or spec.padding != (0, 0, 0, 0):
        return None
    return (
        max(1, plate.caps[0]), max(1, plate.caps[1]),
        max(1, plate.caps[2]), max(1, plate.caps[3]),
    )


def _emit_tint_set(
    canvas: _Canvas,
    prefix: str,
    padding: tuple[int, int, int, int],
    scale: float,
    *,
    white_alpha: float = 0.0,
    bar_edge: str | None = None,
) -> None:
    """A 1 px center-only set for *prefix* plus its margin hints from
    *padding* — the frames-OFF task set.

    NOT :func:`_emit_set`: its transparent-art refusal must not fire
    here, the transparency IS the point (E16 drew no plate). FrameSvg
    needs a ``<prefix>center`` to paint anything at all, and painting a
    0-alpha rect is exactly nothing. *white_alpha* raises that to the
    synthesized hover/attention wash, and *bar_edge* adds the focus
    accent as a ``TASKS_FOCUS_BAR_PX``-thick border element on that side
    — with no side caps there are no corner slices, so the bar already
    spans the whole item.
    """
    ET.SubElement(
        canvas.root,
        f"{{{SVG_NS}}}rect",
        {
            "id": f"{prefix}center",
            "x": "0",
            "y": str(canvas.y),
            "width": "1",
            "height": "1",
            "style": (
                f"fill:#ffffff;opacity:{white_alpha:g}" if white_alpha else "opacity:0"
            ),
        },
    )
    canvas.advance(1, 1)
    if bar_edge is not None:
        w, h = (
            (1, TASKS_FOCUS_BAR_PX)
            if bar_edge in ("top", "bottom")
            else (TASKS_FOCUS_BAR_PX, 1)
        )
        ET.SubElement(
            canvas.root,
            f"{{{SVG_NS}}}rect",
            {
                "id": f"{prefix}{bar_edge}",
                "x": "0",
                "y": str(canvas.y),
                "width": str(w),
                "height": str(h),
                "class": _HIGHLIGHT_CLASS,
                "style": "fill:currentColor",
            },
        )
        canvas.advance(w, h)
    _margin_hints(canvas, prefix, padding, scale)


def _iconbox_trough_padding(theme: Theme) -> tuple[int, int, int, int]:
    """``__PADDING`` of the iconbox trough (first of
    ``_ICONBOX_TROUGH_SOURCES`` defined), else E16's default 2 px."""
    for name in _ICONBOX_TROUGH_SOURCES:
        spec = theme.iclasses.get(name)
        if spec is not None and spec.padding != (0, 0, 0, 0):
            return spec.padding
    return (2, 2, 2, 2)


def build_tasks(theme: Theme, *, iconbox_frames: str = "off") -> ET.Element | None:
    """``widgets/tasks.svg`` — task-manager frames from the iconbox button.

    themey's own apply creates the iconbox panel with an icons-only task
    manager, and most users keep a stock icons-only bar of their own, so
    these frames land exactly where E16's iconbox buttons lived. The
    taskmanager plasmoid (icontasks shares its Task.qml) reads prefixes
    ``normal``/``minimized``/``hover``/``focus``/``attention``/
    ``progress`` plus the unprefixed launcher set; ALL of them ship
    (per-FILE fallback — a partial set paints nothing for missing
    prefixes). ``focus-`` wears the CLICKED chain — E16's active iconbox
    button is the depressed one; ``attention-``/``progress-`` approximate
    with the hilited chain (E16 has no such states — noted).
    ``launcher-hover-``/``focus-hover-`` ship only with explicit hilited
    art (``_TASKS_HOVER_PREFIXES``); synthesized, ``focus-hover-``
    composes both — the hover recipe over the focus one — so the active
    task still answers the mouse. ``group-expander-*`` come from the
    four ``ICONBOX_ARROW_*`` when all exist (the ``build_arrows`` census),
    else they are omitted with a note.

    A prefix whose E16 chain falls back to the NORMAL art is
    SYNTHESIZED instead (:func:`_synth_task_states`, one
    ``plasmastyle:`` note listing which) — nearly every corpus iconbox
    button declares only ``__NORMAL``, which used to make all seven sets
    byte-identical and left the active, minimized and hovered task
    indistinguishable. ``focus`` additionally wears a
    ``TASKS_FOCUS_BAR_PX`` accent bar on the panel-adjacent edge, one
    set per ``_TASKS_FOCUS_EDGES`` entry, painted through KSvg's
    ``ColorScheme-Highlight`` class so it tracks the active scheme.

    ``iconbox_frames="off"`` (the DEFAULT, ``ICONBOX_FRAME_MODES``)
    replays E16's own iconbox — ``container.c`` ``draw_icon_base = 0``,
    no per-icon plate: every prefix ships as a 1 px center-only set
    (:func:`_emit_tint_set`) with margin hints from the iconbox trough's
    ``__PADDING`` so the icons keep E16's spacing, and the expanders
    stay. Skipping the file instead would bring Breeze's plates back —
    worse than either E16 look. The synthesized states survive that mode
    as a white wash (``_TASKS_OFF_ALPHA``) and the same accent bar, so
    the task states stay readable without a plate. ``on`` ships the
    button art as per-icon plates.
    """
    if iconbox_frames not in ICONBOX_FRAME_MODES:
        raise PlasmaStyleError(
            f"iconbox_frames must be one of {ICONBOX_FRAME_MODES} (got {iconbox_frames!r})"
        )
    src = _tasks_source(theme)
    canvas = _Canvas()
    synthesized: list[str] = []
    if iconbox_frames == "off":
        padding = _iconbox_trough_padding(theme)
        for prefix, _state, synth in _TASKS_PREFIXES + _TASKS_HOVER_PREFIXES:
            alpha = _TASKS_OFF_ALPHA.get(synth or "", 0.0)
            if synth in _TASKS_BAR_STATES:
                for edge_prefix, edge in _TASKS_FOCUS_EDGES:
                    _emit_tint_set(
                        canvas, edge_prefix + prefix, padding, theme.scale,
                        white_alpha=alpha, bar_edge=edge,
                    )
            else:
                _emit_tint_set(
                    canvas, prefix, padding, theme.scale, white_alpha=alpha
                )
            if synth is not None:
                synthesized.append(synth)
        from_trough = any(
            (spec := theme.iclasses.get(n)) is not None and spec.padding != (0, 0, 0, 0)
            for n in _ICONBOX_TROUGH_SOURCES
        )
        theme.notes.append(
            "plasmastyle: task frames OFF (--iconbox-frames off, the "
            "default): E16's iconbox draws no per-icon plate (container.c "
            f"draw_icon_base = 0); transparent sets with {padding} "
            "__PADDING margins"
            + (" from the iconbox trough" if from_trough else " (E16 default)")
        )
    else:
        if src is None:
            return None
        plate = _task_plate(theme, src)
        normal_art = _state_image(src, "normal")
        states = _synth_task_states(plate.img) if plate is not None else {}
        # `required`: a base prefix that cannot be emitted kills the whole
        # file (Breeze's per-FILE fallback beats a half-painted one). The
        # hover-on-state extras ship only with real hilited art and fall
        # back to the plain hover set, so a failure there is harmless.
        sets = [(p, s, y, True) for p, s, y in _TASKS_PREFIXES]
        if _hilited_image(src) is not None:
            sets += [(p, s, y, False) for p, s, y in _TASKS_HOVER_PREFIXES]
        clicked = _state_image(src, "pressed")
        bar_margins = _bar_margins(src, plate, clicked in (None, normal_art))
        for prefix, state, synth, required in sets:
            real = _state_image(src, state)
            if synth is None or (real is not None and real != normal_art):
                emitted = _emit_set(theme, canvas, prefix, src, state, hints=True)
                if emitted is None and required:
                    return None  # transparent button art: the file is Breeze's
            elif plate is None:
                return None
            elif synth in _TASKS_BAR_STATES:
                for edge_prefix, edge in _TASKS_FOCUS_EDGES:
                    _emit_task_frame(
                        canvas, edge_prefix + prefix, states[synth], plate,
                        src.padding, bar_edge=edge,
                    )
                    if bar_margins is not None:
                        _margin_hints(
                            canvas, edge_prefix + prefix, bar_margins, 1.0
                        )
                synthesized.append(synth)
                continue
            else:
                _emit_task_frame(
                    canvas, prefix, states[synth], plate, src.padding
                )
                synthesized.append(synth)
            if bar_margins is not None:
                _margin_hints(canvas, prefix, bar_margins, 1.0)

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
            [(el, _load_scaled(p, theme.scale, theme.upscale)) for el, p in expanders],
        )
    else:
        theme.notes.append(
            "plasmastyle: not all four ICONBOX_ARROW_* have art; task "
            "group expanders left to the Breeze fallback"
        )
    if iconbox_frames == "on" and src is not None:
        theme.notes.append(
            f"plasmastyle: task frames from iclass {src.name} (E16 iconbox "
            "button; focus wears the clicked art — the active task shows the "
            "depressed button; attention/progress approximate with the "
            "hilited art; E16's own iconbox default draws NO per-icon plate, "
            "which --iconbox-frames off — the default — replays)"
        )
    if synthesized:
        theme.notes.append(
            "plasmastyle: task states "
            + "/".join(dict.fromkeys(synthesized))
            + " synthesized (E16's iconbox button authors no such state, so "
            "every task frame would otherwise be the normal one); focus "
            f"wears a {TASKS_FOCUS_BAR_PX} px accent bar on the "
            "panel-adjacent edge in the active scheme's Highlight colour"
        )
    root = canvas.finish()
    # The accent bar is the only classed element.
    if any(s in _TASKS_BAR_STATES for s in synthesized):
        scheme = theme.scheme if theme.scheme is not None else default_scheme()
        _color_stylesheet(root, scheme.selection.background_normal)
    return root


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
            ("checkbox", _load_scaled(check_path, theme.scale, theme.upscale)),
            ("radiobutton", _load_scaled(radio_path or check_path, theme.scale, theme.upscale)),
        ],
    )
    theme.notes.append(
        "plasmastyle: check/radio marks from the DIALOG_WIDGET check/radio "
        "checked art; the UNchecked checkbox wears the widgets/button "
        "normal frame (Plasma's CheckIndicator hardcodes it) — still this "
        "theme's push-button art, just not the authored unchecked box"
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
    normal_img = _load_scaled(normal_path, theme.scale, theme.upscale)
    items = [
        ("normal", normal_img),
        ("checked", _load_scaled(checked_path, theme.scale, theme.upscale)),
    ]
    hover_path = _hilited_image(spec)
    if hover_path is not None:
        items.append(("hover", _load_scaled(hover_path, theme.scale, theme.upscale)))
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
        edge: tuple[int, int, int, int], w: int, h: int, _img: Image.Image
    ) -> tuple[int, int, int, int]:
        return _groove_caps(edge, w, h, horizontal=horizontal)

    canvas = _Canvas()
    # hints=False: nothing lays out inside a groove.
    if _emit_set(theme, canvas, "groove-", base, "normal", edge_override=groove_caps) is None:
        return None
    _emit_set(
        theme, canvas, "groove-highlight-", base, "hover", edge_override=groove_caps
    )

    h_spec = knob_h if knob_h is not None else knob_v
    v_spec = knob_v if knob_v is not None else knob_h
    assert h_spec is not None and v_spec is not None
    h_path = _state_image(h_spec, "normal")
    v_path = _state_image(v_spec, "normal")
    assert h_path is not None and v_path is not None  # _iclass_with_art
    h_img = _load_scaled(h_path, theme.scale, theme.upscale)
    items = [
        ("horizontal-slider-handle", h_img),
        ("vertical-slider-handle", _load_scaled(v_path, theme.scale, theme.upscale)),
    ]
    hover_missing = []
    for element, spec in (
        ("horizontal-slider-hover", h_spec),
        ("vertical-slider-hover", v_spec),
    ):
        hover = _hilited_image(spec)
        if hover is not None:
            items.append((element, _load_scaled(hover, theme.scale, theme.upscale)))
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


def _rule_thickness(padding_sum: int, art_px: int) -> tuple[int, str]:
    """Separator thickness in ref px, and the note fragment explaining it.

    E16 (``dialog.c:1048-1056``) sizes the rule from the iclass
    ``__PADDING`` — ``pad.t + pad.b`` for a horizontal rule, ``pad.l +
    pad.r`` for a vertical one — and squeezes the art into it; the art's
    own dimension is used only when no padding is declared (ten corpus
    themes). Both are capped at ``LINE_MAX_REF_THICKNESS``.
    """
    if padding_sum > 0:
        if padding_sum > LINE_MAX_REF_THICKNESS:
            return LINE_MAX_REF_THICKNESS, (
                f"__PADDING declares {padding_sum} ref px, clamped to "
                f"{LINE_MAX_REF_THICKNESS} — E16 drew {padding_sum}"
            )
        return padding_sum, (
            f"{padding_sum} ref px thick from __PADDING, as E16 sized them"
            + (f"; art {art_px} px squeezed" if art_px > padding_sum else "")
        )
    if art_px > LINE_MAX_REF_THICKNESS:
        return LINE_MAX_REF_THICKNESS, (
            f"no __PADDING; {art_px} ref px of art squeezed to "
            f"{LINE_MAX_REF_THICKNESS} — E16 squeezed this art into a thin "
            "rule at layout time"
        )
    return art_px, f"no __PADDING; {art_px} ref px thick from the art"


def _rule_art(
    rgba: Image.Image, padding_sum: int, scale: float, *, horizontal: bool
) -> tuple[Image.Image, str]:
    """One rule element: the art fitted into E16's separator thickness.

    The art is first trimmed to its opaque span on the THICKNESS axis
    (LCARS's ``widget_separator.png`` is 1x16 with ONE opaque hairline
    row inside ``__PADDING 2 2 8 8`` — a NEAREST squeeze of 16 rows into
    4 dropped that row and the rule vanished). A trimmed span that fits
    the thickness is centred in a transparent canvas of that thickness
    (the hairline keeps its 1 px and some of E16's breathing room); a
    larger one (Aliens/e13's 64 px bevel box) is squeezed (NEAREST) into
    it. The other axis is scaled as is.
    """
    # Same alpha threshold as _opaque_trim (a lookup table — pyright
    # rejects the lambda form).
    mask = rgba.getchannel("A").point([0] * 128 + [255] * 128)
    bbox = mask.getbbox()
    if bbox is not None:
        if horizontal:
            rgba = rgba.crop((0, bbox[1], rgba.width, bbox[3]))
        else:
            rgba = rgba.crop((bbox[0], 0, bbox[2], rgba.height))
    art_px = rgba.height if horizontal else rgba.width
    ref, why = _rule_thickness(padding_sum, art_px)
    thick = max(1, scale_px(ref, scale))
    length = max(1, scale_px(rgba.width if horizontal else rgba.height, scale))
    if art_px < ref:
        art_thick = max(1, scale_px(art_px, scale))
        size = (length, art_thick) if horizontal else (art_thick, length)
        art = rgba.resize(size, resample=Image.Resampling.NEAREST)
        canvas_size = (length, thick) if horizontal else (thick, length)
        out = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
        offset = (0, (thick - art_thick) // 2) if horizontal else ((thick - art_thick) // 2, 0)
        out.paste(art, offset)
        return out, why + f"; {art_px} px of art centred in it"
    size = (length, thick) if horizontal else (thick, length)
    return rgba.resize(size, resample=Image.Resampling.NEAREST), why


def build_line(theme: Theme) -> ET.Element | None:
    """``widgets/line.svg`` — section separators in tray popups/SpinBox.

    Thickness comes from the iclass ``__PADDING`` like E16's
    ``DITEM_SEPARATOR`` (:func:`_rule_thickness`), NOT from the art: the
    art is fitted into it (:func:`_rule_art`). StarEnli's 46x2 magenta
    strip with ``__PADDING 1 1 1 1`` is a 2 ref px rule on both axes; the
    earlier art-width vertical rule painted it 4 ref px (6 px at 1.5x,
    chris's Kickoff screenshot 2026-09-01). ``vertical-line`` is the
    ``__CLICKED`` art when authored (``dialog.c:1380-1383``, 107 corpus
    themes), else the horizontal rule rotated 90°; always shipped with the
    file (per-FILE fallback: a missing element renders nothing).
    """
    src = _iclass_with_art(theme, "DIALOG_WIDGET_SEPARATOR")
    if src is None:
        return None
    path = _state_image(src, "normal")
    assert path is not None  # _iclass_with_art guarantees it
    with Image.open(path) as im:
        rgba = im.convert("RGBA")
    pad_l, pad_r, pad_t, pad_b = src.padding
    line, h_why = _rule_art(rgba, pad_t + pad_b, theme.scale, horizontal=True)
    # dialog.c:1380-1383: E16 draws a VERTICAL separator with the iclass's
    # STATE_CLICKED art (107 corpus themes author one); without it, the
    # horizontal art rotated.
    vertical: Image.Image
    clicked_path = src.clicked or src.clicked_active
    if clicked_path is not None and clicked_path.is_file():
        with Image.open(clicked_path) as im:
            vr = im.convert("RGBA")
        vertical, v_why = _rule_art(vr, pad_l + pad_r, theme.scale, horizontal=False)
        vertical_note = (
            f"; vertical rule from the __CLICKED art, as E16 drew it ({v_why})"
        )
    else:
        vertical = line.transpose(Image.Transpose.ROTATE_90)
        vertical_note = "; the vertical rule is the same art rotated"
    canvas = _Canvas()
    for element, img in (
        ("horizontal-line", line),
        ("vertical-line", vertical),
    ):
        _emit_plain_row(canvas, [(element, img)])
    theme.notes.append(
        f"plasmastyle: separators from iclass {src.name} ({h_why})" + vertical_note
    )
    return canvas.finish()


def build_frame(theme: Theme) -> ET.Element | None:
    """``widgets/frame.svg`` — PC3 Frame/GroupBox chrome.

    ONE unprefixed 9-part set + unprefixed margin hints: PC3 requests the
    ``plain`` prefix and FrameSvg's ``adjustPrefix`` falls back to the
    unprefixed set (the same mechanism the panel builder relies on).
    Breeze's ``base``/``raised-``/``sunken-`` sets are deliberately not
    emitted — E16 has one dialog-area look.

    Ring only: E16's ``DITEM_AREA`` covers everything inside the padding
    with a child window (``dialog.c:776-783``), so of StarEnli's 256x256
    solid-magenta ``DIALOG_WIDGET_AREA`` only the 1 px ring ever showed;
    14 corpus themes have solid area art and all 223 an opaque centre,
    which shipped whole as the PC3 Frame/GroupBox background. The
    ``clear_center`` set keeps the caps/padding ring and a transparent
    centre (the mirrors stay byte copies — Breeze's ``opaque/`` frame has
    a transparent centre too).
    """
    src = _iclass_with_art(theme, "DIALOG_WIDGET_AREA", "DIALOG_WIDGET_TABLE")
    if src is None:
        return None
    canvas = _Canvas()
    _emit_set(theme, canvas, "", src, "normal", hints=True, clear_center=True)
    if canvas.is_empty:
        return None
    theme.notes.append(
        f"plasmastyle: group frames from iclass {src.name} (ring only — "
        "E16's DITEM_AREA covers the interior with the area window; one "
        "unprefixed set, FrameSvg's adjustPrefix serves it for PC3's plain "
        "prefix)"
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
    (DRAGBAR_SVG, build_dragbar),
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


def _menu_tclass_name(theme: Theme) -> str:
    """The DEFAULT/ROOT menu style's own ``__TCLASS`` (6 corpus blocks name
    ``MENU``), else the ``MENU_TEXT`` convention."""
    style = _menu_style(theme)
    if style is not None and style.tclass and style.tclass in theme.tclasses:
        return style.tclass
    return "MENU_TEXT"


def _menu_hover_fg(theme: Theme) -> RGB | None:
    """menus.c:1000 draws a hovered item with STATE_HILITED and active=0:
    tclass norm.hilited → norm.normal. __NORMAL_ACTIVE is never consulted."""
    t = theme.tclasses.get(_menu_tclass_name(theme))
    if t is None:
        return None
    fg = t.fg_for("hilited")
    return fg if fg is not None else t.fg_normal


def _menu_pressed_fg(theme: Theme) -> RGB | None:
    """The menu tclass's CLICKED colour — what Kickoff's pressed row wants.

    Only an EXPLICIT clicked state counts: ``TextclassPopulate`` resolves
    an absent one to that group's normal, which is the colour of an
    untouched row, so a theme that declares no clicked text keeps the
    hilited pick (:func:`_menu_hover_fg`) instead.
    """
    t = theme.tclasses.get(_menu_tclass_name(theme))
    if t is not None:
        fg = t.fg_by_state.get("clicked")
        if fg is not None:
            return fg
    return _menu_hover_fg(theme)


#: ``ColorScheme`` field names of the eight ``[Colors:*]`` groups.
_COLOR_GROUPS: tuple[str, ...] = (
    "view", "window", "button", "selection", "tooltip", "complementary",
    "header", "header_inactive",
)


def style_scheme(theme: Theme, *, shipped: frozenset[str]) -> ColorScheme:
    """``theme.scheme`` with the panel-facing groups re-anchored to the art
    this package actually ships.

    Art-derived background overrides fire only for surfaces whose SVG
    shipped (the ``shipped`` gate) — the bundled ``colors`` file is what
    tints the *Breeze fallback* art, so a group whose art we ship must
    match that art, and a group whose art we don't must stay on the
    sampled scheme. Text prefers the theme's own tclass colors
    (``MENU_TEXT``/the DEFAULT tooltip's tclass/``DIALOG_*``), WCAG-guarded; every override
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

    # Colors:View — reading surfaces behind menus/lists. When the popup
    # surface itself came from art, View is re-derived one ladder step from
    # THAT rather than from the sampled border tint: ShinyMetal's black
    # BUTTON tint put View at rgb(6,6,6) behind a 148-grey Kickoff, i.e. a
    # near-black search field inside a light popup.
    if dialog_bg is not None:
        scheme = replace(scheme, view=view_from_window(
            scheme.window.background_normal,
            scheme.view.decoration_focus,
            scheme.view.foreground_normal,
        ))
        theme.notes.append(
            "plasmastyle: colors View from the popup surface — "
            f"rgb{scheme.view.background_normal}, one ladder step from the "
            f"Window override rgb{scheme.window.background_normal}"
        )

    menu_fg = _tclass_fg(theme, "MENU_TEXT")
    if menu_fg is not None:
        fg = _legible(menu_fg, scheme.view.background_normal)
        if fg != scheme.view.foreground_normal:
            scheme = replace(scheme, view=_regroup(scheme.view, None, fg))
            theme.notes.append(
                "plasmastyle: colors View text from tclass MENU_TEXT"
                + ("" if fg == menu_fg else f" (guarded to rgb{fg})")
            )

    # Colors:Tooltip — the same DEFAULT-tooltip sources build_tooltip used.
    if TOOLTIP_SVG in shipped:
        src = _resolve_tooltip_source(theme)
        path = _state_image(src, "normal")
        bg = extract_dominant(path) if path is not None else None
        if bg is not None and src is not None:
            tt_tclass = _tooltip_tclass_name(theme)
            fg, forced = _fg_for(
                _tclass_fg(theme, tt_tclass),
                scheme.tooltip.foreground_normal, (bg,),
            )
            scheme = replace(scheme, tooltip=_regroup(scheme.tooltip, bg, fg))
            theme.notes.append(
                f"plasmastyle: colors Tooltip background from {src.name} art; text "
                + (
                    f"forced to rgb{fg} for contrast"
                    if forced
                    else f"from tclass {tt_tclass}"
                )
            )

    # Colors:Selection — the art Kickoff paints while the mouse is DOWN.
    # Kickoff's Highlight shows the `hover` viewitem prefix for the current
    # item and switches to Selection's colours only on press, at which
    # point the plate under them is MENU_SEL's clicked art and the icon is
    # washed toward this background (Kirigami.Icon.selected). Sampling the
    # hover art instead left ShinyMetal washing a 119-grey pressed plate
    # toward a 137-grey Selection: a muddy icon under a black label. The
    # text is guarded against BOTH plates, since the hover prefix stays
    # painted underneath.
    selection_bg: RGB | None = None
    if VIEWITEM_SVG in shipped:
        sel = theme.iclasses.get("MENU_SEL")
        found = _state_attr(sel, "selected")
        bg = extract_dominant(found[1]) if found is not None else None
        hover_path = _state_image(sel, "hover")
        hover_bg = extract_dominant(hover_path) if hover_path is not None else None
        if bg is not None and found is not None:
            guards = tuple(c for c in (bg, hover_bg) if c is not None)
            fallback = scheme.selection.foreground_normal
            candidate = _menu_pressed_fg(theme)
            fg, forced = _fg_for(candidate, fallback, guards)
            both_plates = all(contrast_ratio(fg, b) >= MIN_CONTRAST for b in guards)
            if not both_plates:
                # Plates at opposite ends of the range (a near-white hover
                # over a near-black clicked, 8 corpus themes) admit no
                # colour legible on both. The pressed plate wins — Kickoff
                # paints `selected+hover` OVER the hover set, so that is
                # what is actually behind the label.
                fg, forced = _fg_for(candidate, fallback, (bg,))
            scheme = replace(scheme, selection=_regroup(scheme.selection, bg, fg))
            selection_bg = bg
            theme.notes.append(
                f"plasmastyle: colors Selection from MENU_SEL {found[0]} art "
                "(what Kickoff paints while the mouse is held down, not the "
                f"hover art); text from tclass {_menu_tclass_name(theme)}"
                + (f", forced to rgb{fg} for contrast" if forced else "")
                + (
                    ""
                    if both_plates
                    else "; no color clears AA on both the pressed and the "
                    "hover plate, so only the pressed one is guaranteed"
                )
            )

    # Colors:Button.
    if BUTTON_SVG in shipped:
        src = _iclass_with_art(theme, *_BUTTON_SOURCES)
        path = _state_image(src, "normal")
        bg = extract_dominant(path) if path is not None else None
        if bg is not None and src is not None:
            # dialog.c pairs the push button's tclass with its iclass name.
            candidate = _tclass_fg(theme, src.name) or _tclass_fg(
                theme, "DIALOG_WIDGET_TEXT"
            )
            fg, forced = _fg_for(candidate, scheme.button.foreground_normal, (bg,))
            scheme = replace(scheme, button=_regroup(scheme.button, bg, fg))
            theme.notes.append(
                f"plasmastyle: colors Button from {src.name} art"
                + (f"; text forced to rgb{fg} for contrast" if forced else "")
            )

    # decoration_focus/hover across every group: analyze/colors falls back
    # to Breeze blue when no cluster of the border art is saturated enough
    # to be an accent, which paints stock-Plasma focus rings all over a
    # grey or brown theme. The Selection background above is a colour the
    # theme actually contains.
    if scheme.accent_fallback and selection_bg is not None:
        scheme = replace(scheme, **{
            name: replace(
                getattr(scheme, name),
                decoration_focus=selection_bg,
                decoration_hover=selection_bg,
            )
            for name in _COLOR_GROUPS
        })
        theme.notes.append(
            f"plasmastyle: colors focus rings from rgb{selection_bg} (the "
            "Selection background) — the border art had no saturated cluster "
            "and the sampled scheme fell back to Breeze blue"
        )

    return scheme


# --------------------------------------------------------------------- #
# Package writer
# --------------------------------------------------------------------- #


def _write_metadata(theme: Theme, out_dir: Path, iconbox_frames: str) -> None:
    """``metadata.json``: KPlugin block + top-level ``X-Plasma-API`` "5.0"
    (the shape every theme on the reference machine ships, Plasma-6 Breeze
    included); ``KPackageStructure`` added for symmetry with the
    Look-and-Feel writer. ``Version`` keys the SVG cache
    (``plasma_theme_<id>*.kcache``) — apply clears that cache explicitly
    because a re-convert never bumps this Version. ``X-Themey-TasksHover``
    (:func:`tasks_hover`) tells apply whether the iconbox task manager
    should animate hover.
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
        "X-Themey-TasksHover": tasks_hover(theme, iconbox_frames=iconbox_frames),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(meta, indent=4, sort_keys=True) + "\n"
    )


def write(theme: Theme, out_dir: Path, *, iconbox_frames: str = "off") -> PlasmaStyle:
    """Write the Plasma Style package for *theme* under *out_dir*.

    ``out_dir``'s basename MUST be ``slug.plugin_id(theme.name)`` — the
    dir name is the ``plasmarc [Theme] name=`` value Plasma matches on.
    ``iconbox_frames`` (``ICONBOX_FRAME_MODES``, default ``"off"``) is
    threaded into :func:`build_tasks` and ``metadata.json``'s
    ``X-Themey-TasksHover``.
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
    if iconbox_frames not in ICONBOX_FRAME_MODES:
        raise PlasmaStyleError(
            f"iconbox_frames must be one of {ICONBOX_FRAME_MODES} (got {iconbox_frames!r})"
        )
    builders: list[tuple[str, Callable[[Theme], ET.Element | None]]] = [
        (rel, partial(build_tasks, iconbox_frames=iconbox_frames) if rel == TASKS_SVG else b)
        for rel, b in _BUILDERS
    ]
    memo_token = _upscale_memo.set({})
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _write_metadata(theme, out_dir, iconbox_frames)
        write_desktop(out_dir / "plasmarc", _PACKAGE_PLASMARC)

        shipped: list[str] = []
        panel_is_tint = False
        for rel, builder in builders:
            try:
                svg = builder(theme)
            except (OSError, ValueError) as exc:
                theme.notes.append(f"plasmastyle: skipped {rel}: {exc}")
                continue
            if svg is None:
                continue
            if rel == PANEL_SVG:
                # A tint UNPREFIXED set (its center is a flat rect, not an
                # embedded image) is translucent and needs the opaque
                # re-render below; prefixed wordmark/vertical art sets may
                # sit alongside it in the same file.
                panel_is_tint = any(
                    el.tag.endswith("rect") and el.get("id") == "center"
                    for el in svg.iter()
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
                    ET.ElementTree(
                        build_panel_background(theme, alpha=1.0, quiet=True)
                    ).write(
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
    finally:
        # The memo holds one scaled Image per distinct source; drop it with
        # the call so nothing survives into the next package.
        _upscale_memo.reset(memo_token)

    log.info(
        "Plasma Style %s: %d svg(s) shipped (%s)",
        pkg_id, len(shipped), ", ".join(shipped) or "colors-only",
    )
    return PlasmaStyle(id=pkg_id, dir=out_dir, shipped=tuple(shipped))
