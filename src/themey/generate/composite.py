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
buttons) are excluded because Aurorae renders those natively from the rc's
``LeftButtons``/``RightButtons`` strings.

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
# (top, bottom, left, right, center). KWin tiles/stretches the slice anyway,
# so its exact size doesn't matter for rendering — but it has to be big enough
# to hold any tileable iclass content. 64 in reference coords matches the
# previous decoration_svg ``_MIDDLE_REF`` value.
MIDDLE_REF: int = 64


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
    return _normalize_bbox(tl_x, tl_y, br_x, br_y)


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

    Same anchoring rule as ``decoration_svg.strip_thicknesses`` but without
    the scale multiplication or clamping — used by ``region_bbox_reference``
    to size composite canvases consistently with the SVG/rc dimensions.
    """
    bs = theme.border
    req_top = bs.border_size_top
    req_bot = bs.border_size_bottom
    req_left = bs.border_size_left
    req_right = bs.border_size_right

    for part in theme.border.parts:
        if is_interactive(part):
            continue
        if part.tl_origin != -1 or part.br_origin != -1:
            continue
        # Apply the same typo-correction the compositor uses.
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

        if tly_p == 0 and bry_p == 0:
            req_top = max(req_top, max(tl_y, br_y))
        elif tly_p == 1024 and bry_p == 1024:
            req_bot = max(req_bot, REFERENCE_H - min(tl_y, br_y))

        if tlx_p == 0 and brx_p == 0:
            req_left = max(req_left, max(tl_x, br_x))
        elif tlx_p == 1024 and brx_p == 1024:
            req_right = max(req_right, REFERENCE_W - min(tl_x, br_x))

    return {
        "top": max(2, min(200, req_top)),
        "bottom": max(2, min(200, req_bot)),
        "left": max(2, min(200, req_left)),
        "right": max(2, min(200, req_right)),
    }


def capped_border_extents(theme: Theme, max_border_output: int) -> dict[str, int]:
    """Return border extents in REFERENCE coords, capped to match
    ``strip_thicknesses``'s output-pixel cap. Used so the composite PNG
    dimensions agree with the SVG <image> slot dimensions — without this,
    KWin would stretch a 248x358 alien-head PNG into a 120x120 slot and
    squash it. Capping clips the source art instead.
    """
    s = theme.scale
    cap_ref = max(2, max_border_output // s)
    ext = required_border_extents(theme)
    return {side: min(cap_ref, ext[side]) for side in ("top", "bottom", "left", "right")}


def region_bbox_reference(
    theme: Theme, region: str, max_border_output: int | None = None
) -> tuple[int, int, int, int]:
    """Return (x0, y0, x1, y1) for *region* in reference (unscaled) coords.

    If ``max_border_output`` is given, the extents are capped so the
    composite canvas matches the SVG/rc dimensions; corner art that
    exceeds the cap is clipped (showing the natural top-left portion of
    the source image rather than a squashed-to-fit version).
    """
    if max_border_output is not None:
        ext = capped_border_extents(theme, max_border_output)
    else:
        ext = required_border_extents(theme)
    bsl = ext["left"]
    bsr = ext["right"]
    bst = ext["top"]
    bsb = ext["bottom"]
    cx = REFERENCE_W // 2
    cy = REFERENCE_H // 2
    mid = MIDDLE_REF
    mx0 = cx - mid // 2
    mx1 = cx + mid // 2
    my0 = cy - mid // 2
    my1 = cy + mid // 2
    regions: dict[str, tuple[int, int, int, int]] = {
        "topleft": (0, 0, bsl, bst),
        "top": (mx0, 0, mx1, bst),
        "topright": (REFERENCE_W - bsr, 0, REFERENCE_W, bst),
        "left": (0, my0, bsl, my1),
        "center": (mx0, my0, mx1, my1),
        "right": (REFERENCE_W - bsr, my0, REFERENCE_W, my1),
        "bottomleft": (0, REFERENCE_H - bsb, bsl, REFERENCE_H),
        "bottom": (mx0, REFERENCE_H - bsb, mx1, REFERENCE_H),
        "bottomright": (REFERENCE_W - bsr, REFERENCE_H - bsb, REFERENCE_W, REFERENCE_H),
    }
    return regions[region]


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

    Returns:
        PNG bytes of the composited region at output (scaled) size.
    """
    scale = theme.scale
    rx0, ry0, rx1, ry1 = region_bbox_reference(theme, region, max_border_output)
    region_w_ref = max(1, rx1 - rx0)
    region_h_ref = max(1, ry1 - ry0)
    canvas_w = region_w_ref * scale
    canvas_h = region_h_ref * scale

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)

    for idx, part in enumerate(theme.border.parts):
        if is_interactive(part):
            continue
        px0, py0, px1, py1 = bboxes[idx]
        if px1 <= px0 or py1 <= py0:
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
        max_w = max(max_w, x1 - x0)
        max_h = max(max_h, y1 - y0)

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
