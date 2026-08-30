"""Region compositor — render Aurorae 9-patch regions from E16 border parts.

E16 themes encode a *composited* decoration: each ``__BORDER_PART`` references
one iclass and positions it inside the border zone with a hybrid pct+abs
coordinate. The Aliens DEFAULT border, for example, places a 124x179
``CORNER_TL`` alien-head logo at (0,0), a ``TITLE_BAR_HORIZONTAL`` strip
between x=153 and x=W-27, button iclasses at fixed positions, and resize
handles along the edges. The previous one-iclass-per-region mapping discarded
all of this layout data and rendered only a single image per region.

This module composites *all* non-interactive parts that overlap an Aurorae
region's bbox into a single RGBA PNG. Interactive parts (close/min/max
buttons) are excluded because Aurorae renders those natively from the
per-button SVGs; their ORDER is global (kwinrc ``ButtonsOnLeft`` /
``ButtonsOnRight``), not something the theme controls — the theme only
decides which button SVGs exist.

Each region's bbox in reference (unscaled) window coordinates:

- ``topleft``    : (0,             0)           → (BSL,            BST)
- ``top``        : (cx-MID/2,      0)           → (cx+MID/2,       BST)
- ``topright``   : (RW-BSR,        0)           → (RW,             BST)
- ``left``       : (0,             cy-MID/2)    → (BSL,            cy+MID/2)
- ``center``     : (cx-MID/2,      cy-MID/2)    → (cx+MID/2,       cy+MID/2)
- ``right``      : (RW-BSR,        cy-MID/2)    → (RW,             cy+MID/2)
- ``bottomleft`` : (0,             RH-BSB)      → (BSL,            RH)
- ``bottom``     : (cx-MID/2,      RH-BSB)      → (cx+MID/2,       RH)
- ``bottomright``: (RW-BSR,        RH-BSB)      → (RW,             RH)

where BSL/BSR/BST/BSB are E16 ``__BORDER_SIZE_*`` values, RW/RH are
``REFERENCE_W/H`` (800x600 — same as analyze/coords.py), and ``cx``/``cy`` are
the window center. MID is the middle-slice width for the stretchable strips.

Output PNGs are upscaled by ``theme.scale`` using NEAREST resampling.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from themey.analyze.buttons import (
    ACLASS_DROP,
    ACLASS_TO_BUTTON,
    ICLASS_PATTERN_TO_BUTTON,
    title_part,
)
from themey.analyze.coords import resolve
from themey.ir import ButtonPart, IClassSpec, Theme

REFERENCE_W: int = 800
REFERENCE_H: int = 600

# Width/height of the centered slice used to render the stretchable strips
# (top, bottom, left, right, center). decoration.svg sets
# ``decoration-hint-stretch-borders`` so KWin STRETCHES (not tiles) the
# slice across the window; a wide slice therefore carries the theme's real
# horizontal gradient instead of a 64-px sample repeated with a seam.
MIDDLE_REF: int = 256

# Corner art is allowed to extend this far (reference px) into the top band
# when it is folded out of a clamped side (see ``corner_extents``).
CORNER_FOLD_CAP_REF: int = 256


def is_interactive(part: ButtonPart) -> bool:
    """True iff Aurorae renders this part natively (close/max/iconify/etc.).

    Mirrors the aclass + iclass-pattern logic used by
    ``analyze.buttons.classify_button``: anything that produces a non-``drop``
    button code via ACLASS or iclass-name match is considered interactive.
    Parts whose ACLASS is in ``ACLASS_DROP`` are decorative drag/resize
    handles — included in the composite.
    """
    if part.aclass in ACLASS_DROP:
        return False
    if part.aclass is not None and part.aclass in ACLASS_TO_BUTTON:
        return True
    iclass_upper = part.iclass_name.upper()
    for pattern, _code in ICLASS_PATTERN_TO_BUTTON:
        if pattern in iclass_upper:
            return True
    return False


def _normalize_bbox(x0: int, y0: int, x1: int, y1: int) -> tuple[int, int, int, int]:
    """Ensure (x0,y0) is the top-left and (x1,y1) the bottom-right.

    Aliens CORNER_BL has tl_y=530, br_y=470 at H=600 — the part's coords are
    "inverted" from the simple top-left-to-bottom-right convention. We always
    treat the bbox as the geometric rectangle spanning min(x)→max(x) by
    min(y)→max(y).
    """
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _typo_corrected_pct_abs(
    tl_pct: int, tl_abs: int, br_pct: int, br_abs: int
) -> tuple[int, int, int, int]:
    """Repair a known E16 theme-file typo class before resolving.

    Pattern: top-left is right-edge anchored (``pct=1024``) but bottom-right
    declares ``pct=0`` with a *negative* literal absolute. Aliens' default.cfg
    ``CORNER_TR`` has ``__TOPLEFT_X_PERCENTAGE 1024 __TOPLEFT_X_ABSOLUTE -68``
    paired with ``__BOTTOMRIGHT_X_PERCENTAGE 0 __BOTTOMRIGHT_X_ABSOLUTE -3``
    — under literal resolution the bottom-right ends up at x=-3 (off the
    window) and the bbox spans the entire width, which makes the corner art
    fail to render in the topright zone. The intent is clearly that the BR
    point is also right-anchored. Same pattern can occur on the y axis.

    The repair: if ``tl_pct == 1024`` and ``br_pct == 0`` and ``br_abs < 0``,
    treat ``br_pct`` as 1024.
    """
    if tl_pct == 1024 and br_pct == 0 and br_abs < 0:
        return (tl_pct, tl_abs, 1024, br_abs)
    return (tl_pct, tl_abs, br_pct, br_abs)


def _pin_min_sizes(
    part: ButtonPart,
    bbox: tuple[int, int, int, int],
    win_w: int,
    win_h: int,
) -> tuple[int, int, int, int]:
    """Inflate a bbox to the part's __MIN_WIDTH/__MIN_HEIGHT pins.

    E16 lets a part declare a degenerate rect (both coords on the same edge)
    and carry its real extent only in the MIN/MAX pins — e13's WIN_BOTTOM has
    both y coords at H-6 and ``__MIN_HEIGHT 6``. Without pinning, the zero-
    extent bbox fails every ``x1 <= x0`` / ``y1 <= y0`` guard downstream and
    the part silently never composites.

    Inflation is anchored top-left and shifted back inside the window when it
    would spill past the far edge. No ``max_*`` clamping happens here — MAX
    pins constrain live E16 geometry, not the reference-window snapshot.
    """
    x0, y0, x1, y1 = bbox
    if part.min_w > 0 and (x1 - x0) < part.min_w:
        x1 = x0 + part.min_w
        if x1 > win_w:
            x0 = max(0, x0 - (x1 - win_w))
            x1 = min(win_w, x0 + part.min_w)
    if part.min_h > 0 and (y1 - y0) < part.min_h:
        y1 = y0 + part.min_h
        if y1 > win_h:
            y0 = max(0, y0 - (y1 - win_h))
            y1 = min(win_h, y0 + part.min_h)
    return (x0, y0, x1, y1)


def _part_window_relative_bbox(
    part: ButtonPart, win_w: int, win_h: int
) -> tuple[int, int, int, int]:
    """Resolve a window-relative ButtonPart to (x0, y0, x1, y1)."""
    tlx_p, tlx_a, brx_p, brx_a = _typo_corrected_pct_abs(
        part.tl_x_pct, part.tl_x_abs, part.br_x_pct, part.br_x_abs
    )
    tly_p, tly_a, bry_p, bry_a = _typo_corrected_pct_abs(
        part.tl_y_pct, part.tl_y_abs, part.br_y_pct, part.br_y_abs
    )
    tl_x = resolve(tlx_p, tlx_a, win_w)
    tl_y = resolve(tly_p, tly_a, win_h)
    br_x = resolve(brx_p, brx_a, win_w)
    br_y = resolve(bry_p, bry_a, win_h)
    bbox = _normalize_bbox(tl_x, tl_y, br_x, br_y)
    return _pin_min_sizes(part, bbox, win_w, win_h)


def resolve_parts(
    parts: tuple[ButtonPart, ...],
    win_w: int,
    win_h: int,
    notes: list[str] | None = None,
) -> dict[int, tuple[int, int, int, int]]:
    """Resolve each part's bbox to (x0, y0, x1, y1) in window coords.

    Supports E16's ``__TOPLEFT_ORIGIN`` / ``__BOTTOMRIGHT_ORIGIN`` part-index
    reference: ``origin = -1`` means window-relative (the default in all
    current fixture themes); ``origin >= 0`` means the coordinate is relative
    to the bbox of part N.

    Resolution is iterative — parts referencing other parts are deferred until
    their origin is resolved. Cyclic references are logged to ``notes`` (if
    provided) and dropped (returned as zero-sized rectangles).

    Returns a mapping ``{part_index: (x0, y0, x1, y1)}``.
    """
    resolved: dict[int, tuple[int, int, int, int]] = {}
    pending: list[int] = list(range(len(parts)))
    progressed = True
    while pending and progressed:
        progressed = False
        still_pending: list[int] = []
        for idx in pending:
            p = parts[idx]
            tl_origin = p.tl_origin
            br_origin = p.br_origin
            # Both coordinate corners are window-relative
            if tl_origin == -1 and br_origin == -1:
                resolved[idx] = _part_window_relative_bbox(p, win_w, win_h)
                progressed = True
                continue
            # If either origin refers to a part not yet resolved, defer
            if (tl_origin != -1 and tl_origin not in resolved) or (
                br_origin != -1 and br_origin not in resolved
            ):
                still_pending.append(idx)
                continue
            # Both origins now resolvable
            tl_ref = resolved.get(tl_origin) if tl_origin != -1 else None
            br_ref = resolved.get(br_origin) if br_origin != -1 else None
            tl_x_dim = (tl_ref[2] - tl_ref[0]) if tl_ref else win_w
            tl_y_dim = (tl_ref[3] - tl_ref[1]) if tl_ref else win_h
            br_x_dim = (br_ref[2] - br_ref[0]) if br_ref else win_w
            br_y_dim = (br_ref[3] - br_ref[1]) if br_ref else win_h
            tl_x_off = tl_ref[0] if tl_ref else 0
            tl_y_off = tl_ref[1] if tl_ref else 0
            br_x_off = br_ref[0] if br_ref else 0
            br_y_off = br_ref[1] if br_ref else 0
            tl_x = tl_x_off + resolve(p.tl_x_pct, p.tl_x_abs, tl_x_dim)
            tl_y = tl_y_off + resolve(p.tl_y_pct, p.tl_y_abs, tl_y_dim)
            br_x = br_x_off + resolve(p.br_x_pct, p.br_x_abs, br_x_dim)
            br_y = br_y_off + resolve(p.br_y_pct, p.br_y_abs, br_y_dim)
            resolved[idx] = _normalize_bbox(tl_x, tl_y, br_x, br_y)
            progressed = True
        pending = still_pending

    # Anything still pending forms a cycle. Log and drop.
    for idx in pending:
        if notes is not None:
            notes.append(
                f"composite: cyclic origin reference in part {idx} "
                f"(iclass={parts[idx].iclass_name}); dropping"
            )
        resolved[idx] = (0, 0, 0, 0)
    return resolved


def required_border_extents(theme: Theme) -> dict[str, int]:
    """Return the grown border extents (in REFERENCE coords) for each side.

    A part is allowed to grow a side ONLY when it genuinely belongs to that
    side — defined as "spans the perpendicular center" of the reference
    window. A part anchored only to a corner (e.g. CORNER_TL at x=0..124,
    y=0..179) is excluded from both the TOP and LEFT growth budgets,
    because admitting it inflates BorderLeft/BorderTop far beyond what the
    SIDE strips between corners actually contain — Aurorae reserves the
    grown width across the whole side, and the strip between corners gets
    rendered as mostly-empty (8% opaque for Aliens).

    This is the canonical "Aurorae chrome model" trade-off: corner art
    that doesn't fit gets clipped to the corner slot rather than
    inflating the side widths. The result is a chrome that visibly wraps
    the window content rather than reserving huge transparent zones.
    """
    bs = theme.border
    req_top = bs.border_size_top
    req_bot = bs.border_size_bottom
    req_left = bs.border_size_left
    req_right = bs.border_size_right

    half_w = REFERENCE_W // 2
    half_h = REFERENCE_H // 2

    # Corner art is allowed to nudge the TOP/BOTTOM strip thickness up,
    # bounded by this cap. Aliens (bst=30) gets cap=60: enough vertical
    # room to render the alien-head's face/eyes, but capped so the cell
    # height doesn't blow out into the window-content area.
    top_corner_cap = min(2 * bs.border_size_top, 96)
    bot_corner_cap = min(2 * bs.border_size_bottom, 96)

    for part in theme.border.parts:
        if is_interactive(part):
            continue
        if part.tl_origin != -1 or part.br_origin != -1:
            continue
        tlx_p, tlx_a, brx_p, brx_a = _typo_corrected_pct_abs(
            part.tl_x_pct, part.tl_x_abs, part.br_x_pct, part.br_x_abs
        )
        tly_p, tly_a, bry_p, bry_a = _typo_corrected_pct_abs(
            part.tl_y_pct, part.tl_y_abs, part.br_y_pct, part.br_y_abs
        )
        tl_x = resolve(tlx_p, tlx_a, REFERENCE_W)
        tl_y = resolve(tly_p, tly_a, REFERENCE_H)
        br_x = resolve(brx_p, brx_a, REFERENCE_W)
        br_y = resolve(bry_p, bry_a, REFERENCE_H)
        x0, x1 = min(tl_x, br_x), max(tl_x, br_x)
        y0, y1 = min(tl_y, br_y), max(tl_y, br_y)
        spans_x_center = x0 < half_w < x1
        spans_y_center = y0 < half_h < y1
        top_anchored = tly_p == 0 and bry_p == 0
        bot_anchored = tly_p == 1024 and bry_p == 1024
        left_anchored = tlx_p == 0 and brx_p == 0
        right_anchored = tlx_p == 1024 and brx_p == 1024
        height = max(0, y1 - y0)

        # TOP growth: part is anchored to top AND spans the horizontal
        # center — i.e. it's a TOP strip, not a top-left/top-right corner.
        if top_anchored and spans_x_center:
            req_top = max(req_top, max(tl_y, br_y))
        elif bot_anchored and spans_x_center:
            req_bot = max(req_bot, REFERENCE_H - min(tl_y, br_y))

        # TOP/BOTTOM corner growth (capped): a corner anchored to a
        # vertical edge AND a horizontal side may nudge that side's
        # required extent up to the cap, but NOT the perpendicular side.
        # That keeps the post-45b6690 invariant: corners don't inflate
        # side widths.
        if top_anchored and (left_anchored or right_anchored) and not spans_x_center:
            req_top = max(req_top, min(height, top_corner_cap))
        if bot_anchored and (left_anchored or right_anchored) and not spans_x_center:
            req_bot = max(req_bot, min(height, bot_corner_cap))

        # LEFT/RIGHT growth: part is anchored to a side AND spans the
        # vertical center — i.e. it's a SIDE strip, not a corner.
        if left_anchored and spans_y_center:
            req_left = max(req_left, max(tl_x, br_x))
        elif right_anchored and spans_y_center:
            req_right = max(req_right, REFERENCE_W - min(tl_x, br_x))

    return {
        "top": max(2, min(200, req_top)),
        "bottom": max(2, min(200, req_bot)),
        "left": max(2, min(200, req_left)),
        "right": max(2, min(200, req_right)),
    }


def capped_border_extents(
    theme: Theme, max_border_output: int, max_side_output: int | None = None
) -> dict[str, int]:
    """Return border extents in REFERENCE coords, capped to match
    ``strip_thicknesses``'s output-pixel caps. Used so the composite PNG
    dimensions agree with the SVG <image> slot dimensions — without this,
    KWin would stretch a 248x358 alien-head PNG into a 120x120 slot and
    squash it. Capping clips the source art instead.

    ``max_border_output`` caps the top band; ``max_side_output`` (defaults
    to the same value) caps left/right/bottom — Aurorae v2 clamps those to
    the System Settings border bracket, so keeping them small avoids a
    squashed frame.
    """
    s = theme.scale
    if max_side_output is None:
        max_side_output = max_border_output
    cap_top = max(2, max_border_output // s)
    cap_side = max(2, max_side_output // s)
    ext = required_border_extents(theme)
    return {
        "top": min(cap_top, ext["top"]),
        "bottom": min(cap_side, ext["bottom"]),
        "left": min(cap_side, ext["left"]),
        "right": min(cap_side, ext["right"]),
    }


def corner_extents(theme: Theme) -> dict[str, int]:
    """Horizontal reach (reference px) of top-left / top-right corner art.

    Returns ``{"left": x1_of_widest_top_left_corner_part,
    "right": width_from_right_edge_of_widest_top_right_corner_part}``. A
    corner part is a non-interactive, window-relative part anchored to the
    top AND to one horizontal edge that does not span the horizontal
    center. Zero when a side has no corner art. Capped at
    ``CORNER_FOLD_CAP_REF``.
    """
    half_w = REFERENCE_W // 2
    left = 0
    right = 0
    for part in theme.border.parts:
        if is_interactive(part):
            continue
        if part.tl_origin != -1 or part.br_origin != -1:
            continue
        tlx_p, tlx_a, brx_p, brx_a = _typo_corrected_pct_abs(
            part.tl_x_pct, part.tl_x_abs, part.br_x_pct, part.br_x_abs
        )
        tly_p, _tly_a, bry_p, _bry_a = _typo_corrected_pct_abs(
            part.tl_y_pct, part.tl_y_abs, part.br_y_pct, part.br_y_abs
        )
        if not (tly_p == 0 and bry_p == 0):
            continue
        tl_x = resolve(tlx_p, tlx_a, REFERENCE_W)
        br_x = resolve(brx_p, brx_a, REFERENCE_W)
        x0, x1 = min(tl_x, br_x), max(tl_x, br_x)
        if x0 < half_w < x1:
            continue
        if tlx_p == 0 and brx_p == 0:
            left = max(left, x1)
        elif tlx_p == 1024 and brx_p == 1024:
            right = max(right, REFERENCE_W - x0)
    return {
        "left": min(CORNER_FOLD_CAP_REF, left),
        "right": min(CORNER_FOLD_CAP_REF, right),
    }


def folded_corner_widths(
    theme: Theme, max_border_output: int, max_side_output: int | None = None
) -> dict[str, int]:
    """Width (reference px) of the topleft / topright cells.

    Normally these equal the capped left/right extents. When a side is
    clamped BELOW what its corner art needs (Aliens: 35-ref left border
    but 124-ref-wide CORNER_TL, sides capped at 24 ref), the corner cell is
    widened to hold the art — it lives in the unclamped top band, so both
    Aurorae plugins render it in full.
    """
    ext = capped_border_extents(theme, max_border_output, max_side_output)
    corner = corner_extents(theme)
    return {
        side: max(ext[side], corner[side]) for side in ("left", "right")
    }


def region_bbox_reference(
    theme: Theme,
    region: str,
    max_border_output: int | None = None,
    max_side_output: int | None = None,
) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) for *region* in reference (unscaled) coords.

    If ``max_border_output`` is given, the extents are capped so the
    composite canvas matches the SVG/rc dimensions; corner art that
    exceeds the cap is clipped (showing the natural top-left portion of
    the source image rather than a squashed-to-fit version) — except the
    top corners, which widen to hold folded corner art (see
    ``folded_corner_widths``).
    """
    if max_border_output is not None:
        ext = capped_border_extents(theme, max_border_output, max_side_output)
        cw = folded_corner_widths(theme, max_border_output, max_side_output)
    else:
        ext = required_border_extents(theme)
        cw = {"left": ext["left"], "right": ext["right"]}
    bsl = ext["left"]
    bsr = ext["right"]
    bst = ext["top"]
    bsb = ext["bottom"]
    tlw = cw["left"]
    trw = cw["right"]
    cx = REFERENCE_W // 2
    cy = REFERENCE_H // 2
    mid = MIDDLE_REF
    mx0 = cx - mid // 2
    mx1 = cx + mid // 2
    my0 = cy - mid // 2
    my1 = cy + mid // 2

    # Inner-edge anchoring for capped sides. When the left/right/bottom
    # strip is narrower than the E16 zone (v2-friendly 48 px cap), keep the
    # ``cap`` reference px ADJACENT TO THE CLIENT rather than the outer
    # ones: E16 themes put the visible resize strip at the inner edge of
    # the zone (Aliens' BUTTONL is x=30..35 of a 35-wide zone) and leave the
    # outer part transparent for the corner art to breathe. Cropping from
    # the outer edge would throw the only visible side art away.
    # The left/right frame COLUMNS are as wide as the folded corner cells
    # (``tlw``/``trw`` >= ``bsl``/``bsr``); the strips and bottom corners
    # share that width so the column is one continuous, unstretched piece
    # of the E16 frame. When a column/bottom is narrower than the E16 zone
    # (48-px cap), the crop window is anchored on the zone's actual art
    # (see ``_capped_window``) so the visible strip is never cropped away.
    req = required_border_extents(theme)
    lw = max(bsl, tlw)
    rw = max(bsr, trw)
    lx0, lx1 = _capped_window(theme, "left", req["left"], lw)
    rx0, rx1 = _capped_window(theme, "right", req["right"], rw)
    by0, by1 = _capped_window(theme, "bottom", req["bottom"], bsb)

    regions: dict[str, tuple[int, int, int, int]] = {
        "topleft": (0, 0, tlw, bst),
        "top": (mx0, 0, mx1, bst),
        "topright": (REFERENCE_W - trw, 0, REFERENCE_W, bst),
        "left": (lx0, my0, lx1, my1),
        "center": (mx0, my0, mx1, my1),
        "right": (rx0, my0, rx1, my1),
        "bottomleft": (lx0, by0, lx1, by1),
        "bottom": (mx0, by0, mx1, by1),
        "bottomright": (rx0, by0, rx1, by1),
    }
    return regions[region]


def _capped_window(theme: Theme, side: str, zone: int, cap: int) -> tuple[int, int]:
    """Return the (start, end) reference span of a possibly-capped side.

    ``zone`` is the E16 border extent on that side, ``cap`` the width we
    can emit. When ``cap >= zone`` the whole zone is used. Otherwise the
    ``cap``-wide window is placed where the zone's non-interactive art is:
    E16 themes put the visible resize strip anywhere in the zone (Aliens'
    BUTTONL is at the inner edge of the left zone, BUTTONB at the outer
    edge of the bottom zone), and cropping blindly from either edge throws
    the only visible art away.
    """
    if side == "left":
        lo, hi = 0, zone
    elif side == "right":
        lo, hi = REFERENCE_W - zone, REFERENCE_W
    else:  # bottom
        lo, hi = REFERENCE_H - zone, REFERENCE_H
    if cap >= zone:
        # Column wider than (or equal to) the zone: span the whole column
        # from the outer edge so the composite is 1:1 with the SVG slot.
        if side == "left":
            return (0, cap)
        if side == "right":
            return (REFERENCE_W - cap, REFERENCE_W)
        return (REFERENCE_H - cap, REFERENCE_H)

    cx, cy = REFERENCE_W // 2, REFERENCE_H // 2
    half = MIDDLE_REF // 2
    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)
    art_min: int | None = None
    art_max: int | None = None
    for idx, part in enumerate(theme.border.parts):
        if is_interactive(part):
            continue
        x0, y0, x1, y1 = bboxes.get(idx, (0, 0, 0, 0))
        if x1 <= x0 or y1 <= y0:
            continue
        if side == "bottom":
            # must intersect the zone AND the horizontal middle slice
            if y1 <= lo or y0 >= hi or x1 <= cx - half or x0 >= cx + half:
                continue
            a0, a1 = max(y0, lo), min(y1, hi)
        else:
            if x1 <= lo or x0 >= hi or y1 <= cy - half or y0 >= cy + half:
                continue
            a0, a1 = max(x0, lo), min(x1, hi)
        art_min = a0 if art_min is None else min(art_min, a0)
        art_max = a1 if art_max is None else max(art_max, a1)

    if side == "left":
        # Prefer to start at the art's near (outer) edge, else keep the inner
        # ``cap`` px.
        start = hi - cap if art_min is None else min(art_min, hi - cap)
        start = max(lo, start)
    else:
        # right/bottom: prefer to end at the art's far (outer) edge.
        end = lo + cap if art_max is None else max(art_max, lo + cap)
        end = min(hi, end)
        start = end - cap
    return (start, start + cap)


def _iclass_image(ic: IClassSpec | None, prefer_active: bool) -> Image.Image | None:
    """Open the iclass's primary image, preferring active if requested.

    Returns an unscaled RGBA Image, or None if no image is available.
    """
    if ic is None:
        return None
    candidates: tuple[Path | None, ...]
    if prefer_active:
        candidates = (ic.normal_active, ic.normal)
    else:
        candidates = (ic.normal, ic.normal_active)
    for p in candidates:
        if p is None or not p.is_file():
            continue
        try:
            with Image.open(p) as src:
                return src.convert("RGBA")
        except Exception:
            continue
    return None


def compose_region(
    theme: Theme,
    region: str,
    *,
    prefer_active: bool = True,
    max_border_output: int | None = None,
    max_side_output: int | None = None,
) -> bytes:
    """Render *region* as a RGBA PNG composited from overlapping border parts.

    All non-interactive parts whose resolved bbox overlaps the region's bbox
    (in reference window coords) are drawn. The output is upscaled by
    ``theme.scale`` using NEAREST resampling. Returns the PNG as bytes.

    Args:
        theme: Frozen Theme IR.
        region: One of ``topleft``, ``top``, ``topright``, ``left``, ``center``,
            ``right``, ``bottomleft``, ``bottom``, ``bottomright``.
        prefer_active: When True (default), use ``normal_active`` iclass
            variants where available; used for the active-frame composite.
        max_border_output: When given, region size is capped to match the
            same cap used by ``strip_thicknesses``. Corner art that exceeds
            the cap is clipped (showing the top-left portion of the source)
            instead of stretched.
        max_side_output: Separate cap for left/right/bottom (defaults to
            ``max_border_output``).

    Returns:
        PNG bytes of the composited region at output (scaled) size.
    """
    scale = theme.scale
    rx0, ry0, rx1, ry1 = region_bbox_reference(
        theme, region, max_border_output, max_side_output
    )
    region_w_ref = max(1, rx1 - rx0)
    region_h_ref = max(1, ry1 - ry0)
    canvas_w = region_w_ref * scale
    canvas_h = region_h_ref * scale

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)

    # Stretchable strips only take strip-like parts — those spanning the
    # window centre on the strip's axis. Corner art (e.g. Aliens' CORNER_TL
    # reaching 179 ref px down the left edge) belongs to the corner cells;
    # letting a sliver of it into the left strip would be stretched down the
    # whole window height by ``hint-stretch-borders``.
    cx, cy = REFERENCE_W // 2, REFERENCE_H // 2
    for idx, part in enumerate(theme.border.parts):
        if is_interactive(part):
            continue
        px0, py0, px1, py1 = bboxes[idx]
        if px1 <= px0 or py1 <= py0:
            continue
        if region in ("left", "right") and not (py0 < cy < py1):
            continue
        if region in ("top", "bottom") and not (px0 < cx < px1):
            continue
        # Intersect part bbox with region bbox (reference coords)
        ix0 = max(px0, rx0)
        iy0 = max(py0, ry0)
        ix1 = min(px1, rx1)
        iy1 = min(py1, ry1)
        if ix1 <= ix0 or iy1 <= iy0:
            continue
        ic = theme.iclasses.get(part.iclass_name)
        img = _iclass_image(ic, prefer_active)
        if img is None:
            continue

        part_w_ref = px1 - px0
        part_h_ref = py1 - py0
        # Resize the iclass image to the part's bbox (at scaled output size)
        target_w = max(1, part_w_ref * scale)
        target_h = max(1, part_h_ref * scale)
        if img.size != (target_w, target_h):
            img = img.resize((target_w, target_h), Image.Resampling.NEAREST)

        # Source crop within the resized image: portion that lies in region
        src_x = (ix0 - px0) * scale
        src_y = (iy0 - py0) * scale
        src_x_end = (ix1 - px0) * scale
        src_y_end = (iy1 - py0) * scale
        cropped = img.crop((src_x, src_y, src_x_end, src_y_end))

        # Destination paste position within the region canvas
        dst_x = (ix0 - rx0) * scale
        dst_y = (iy0 - ry0) * scale
        canvas.alpha_composite(cropped, (dst_x, dst_y))

    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


def button_dims(theme: Theme) -> tuple[int, int]:
    """Return (ButtonWidth, ButtonHeight) for *theme* in output (scaled) pixels.

    Width comes from the max bbox width across the theme's interactive
    (button) parts that live in the top zone; height from the max bbox
    height. The bbox is the *rendered* slot the part will occupy — E16
    source PNGs are often larger sprite sheets, so reading raw image dims
    would over-estimate.

    Canonical grammar: a "titlebar button" is any part where
    ``is_interactive(part)`` is True (canonical ``__ACLASS`` → button code
    mapping, with iclass-pattern fallback for themes that omit __ACLASS)
    AND whose resolved bbox lies within the top zone (filters out
    BUTTON_KILL-style iclasses positioned in the left/right border for
    kill-from-side).

    ButtonHeight is capped at the title-bar height (the vertical span of the
    title-bearing part, falling back to ``BORDER_SIZE_TOP``). If the buttons
    are taller than the title bar, Aurorae clips them.
    """
    s = theme.scale
    bst = theme.border.border_size_top
    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)

    # A real titlebar button is at most a quarter of the reference window
    # wide; anything wider is a spatial-fallback part (e.g. OPENSTEP's
    # BORDER_PIXEL iclass spans the full window) and would poison the
    # max-width search if admitted. Discard those candidates.
    BUTTON_WIDTH_CAP_REF = REFERENCE_W // 4  # 200 ref → 400 output at scale=2

    # Honor every interactive part's __MAX_WIDTH (when set) as an upper
    # bound on the ButtonWidth — a theme that says "no button should be
    # wider than 20 ref px" must not get a 200-px slot from us.
    part_max_w_cap = 0
    max_w = 0
    max_h = 0
    for idx, part in enumerate(theme.border.parts):
        if not is_interactive(part):
            continue
        bb = bboxes.get(idx)
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        # Only count buttons that live within the top zone (title bar).
        if y0 < 0 or y1 > bst:
            continue
        width_ref = x1 - x0
        if width_ref > BUTTON_WIDTH_CAP_REF:
            continue
        max_w = max(max_w, width_ref)
        max_h = max(max_h, y1 - y0)
        if part.max_w > 0:
            part_max_w_cap = (
                part.max_w
                if part_max_w_cap == 0
                else max(part_max_w_cap, part.max_w)
            )
    if part_max_w_cap > 0:
        max_w = min(max_w, part_max_w_cap) if max_w > 0 else max_w

    if max_w == 0 and max_h == 0:
        # Fallback: scan iclasses referenced by interactive parts. Use the
        # smallest image, capped at 24 — matches earlier behavior without
        # name-pattern coupling.
        seen_iclasses: set[str] = {
            part.iclass_name for part in theme.border.parts if is_interactive(part)
        }
        for name in seen_iclasses:
            ic = theme.iclasses.get(name)
            if ic is None:
                continue
            p = ic.normal_active or ic.normal
            if p is None or not p.is_file():
                continue
            try:
                with Image.open(p) as im:
                    w, h = im.size
                    max_w = max(max_w, min(w, 24))
                    max_h = max(max_h, min(h, 24))
            except Exception:
                continue
    if max_w == 0:
        max_w = 12
    if max_h == 0:
        max_h = 12

    # Cap ButtonHeight by title-bar height (the part's resolved span),
    # leaving a 1-px reference margin so the title-bar edge is still visible.
    title_h_ref = _title_bar_height_ref(theme)
    if title_h_ref > 0:
        max_h = min(max_h, max(2, title_h_ref - 1))

    return (max_w * s, max_h * s)


# Aurorae rc key suffix per button code (``ButtonWidth<Suffix>``).
BUTTON_CODE_TO_RC_SUFFIX: dict[str, str] = {
    "X": "Close",
    "I": "Minimize",
    "A": "MaximizeRestore",
    # Aurorae reads these with this exact (odd) casing — see
    # aurorae v1/lib/themeconfig.cpp + v2/decorationtheme.cpp.
    "S": "Alldesktops",
    "L": "Shade",
    "F": "Keepabove",
    "B": "Keepbelow",
    "M": "Menu",
}


def button_widths_by_code(theme: Theme) -> dict[str, int]:
    """Per-button ``ButtonWidth<Suffix>`` values in output pixels.

    Each interactive part's resolved bbox width x scale, keyed by Aurorae
    button code (via ``__ACLASS`` or the iclass-name pattern). Codes with
    no part fall back to the shared ``ButtonWidth`` from ``button_dims``.
    """
    s = theme.scale
    bst = theme.border.border_size_top
    default_w, _ = button_dims(theme)
    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)
    widths: dict[str, int] = {}
    cap_ref = REFERENCE_W // 4
    for idx, part in enumerate(theme.border.parts):
        if not is_interactive(part):
            continue
        code: str | None = None
        if part.aclass is not None and part.aclass in ACLASS_TO_BUTTON:
            code = ACLASS_TO_BUTTON[part.aclass]
        else:
            up = part.iclass_name.upper()
            for pattern, c in ICLASS_PATTERN_TO_BUTTON:
                if pattern in up:
                    code = c
                    break
        if code is None:
            continue
        bb = bboxes.get(idx)
        if bb is None:
            continue
        x0, y0, x1, y1 = bb
        if y0 < 0 or y1 > bst:
            continue
        w = x1 - x0
        if w <= 0 or w > cap_ref:
            continue
        if part.max_w > 0:
            w = min(w, part.max_w)
        widths[code] = max(widths.get(code, 0), w * s)
    return {
        code: widths.get(code, default_w) for code in BUTTON_CODE_TO_RC_SUFFIX
    }


def _title_bar_height_ref(theme: Theme) -> int:
    """Resolved title-bar height in reference coords (falls back to BST).

    Canonical: looks up the part with ``__FLAG_TITLE``. If absent, returns
    ``BORDER_SIZE_TOP`` so callers still get a non-zero cap.
    """
    tp = title_part(theme.border.parts)
    if tp is None:
        return theme.border.border_size_top
    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)
    idx = theme.border.parts.index(tp)
    bb = bboxes.get(idx)
    if bb is None:
        return theme.border.border_size_top
    h = bb[3] - bb[1]
    return h if h > 0 else theme.border.border_size_top


def button_size(theme: Theme) -> int:
    """Backwards-compatible: max(ButtonWidth, ButtonHeight) for SVG canvas use."""
    w, h = button_dims(theme)
    return max(w, h)


def button_layout(theme: Theme) -> dict[str, int]:
    """Return ButtonWidth/ButtonHeight/ButtonMarginTop/ButtonSpacing for *theme*.

    All values are in output (scaled) pixels. Derived from the interactive
    parts' resolved positions where possible — the rc and the per-button SVG
    canvases must agree on size so KWin doesn't have to downsample.

    Falls back to ``button_size(theme)`` for the width/height and
    ``4 x scale`` for the inter-button gap when the parts list has no
    interactive entries.
    """
    s = theme.scale
    btn_w, btn_h = button_dims(theme)
    # Find interactive parts and their vertical positions to derive
    # ButtonMarginTop and ButtonSpacing.
    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)
    interactive: list[tuple[int, int, int, int, int]] = []  # (x0, y0, x1, y1, idx)
    for idx, part in enumerate(theme.border.parts):
        if not is_interactive(part):
            continue
        bb = bboxes.get(idx)
        if bb is None:
            continue
        interactive.append((bb[0], bb[1], bb[2], bb[3], idx))

    if interactive:
        ys = [b[1] for b in interactive]
        margin_top_ref = min(ys)
        margin_top = max(0, margin_top_ref * s)
        # Compute typical inter-button x spacing as median gap between adjacent
        # x-sorted buttons.
        xs_sorted = sorted(interactive, key=lambda b: b[0])
        gaps = [
            xs_sorted[i + 1][0] - xs_sorted[i][2]
            for i in range(len(xs_sorted) - 1)
        ]
        gap = min(g for g in gaps if g > 0) if any(g > 0 for g in gaps) else 4
        spacing = max(0, gap * s)
    else:
        margin_top = 2 * s
        spacing = 4 * s

    return {
        "ButtonWidth": btn_w,
        "ButtonHeight": btn_h,
        "ButtonMarginTop": margin_top,
        "ButtonSpacing": spacing,
    }
