"""Pure-Python mirror of runtime/resolver.js — E16 BorderWinpartCalc.

The QML runtime resolves part geometry live (window resizes, caption
changes); this module is the SAME algorithm over the SAME part-model dicts,
used by the emitter (maximized-band detection) and by tests (e13
ground-truth geometry). Keep the two implementations in lockstep — both
carry RUNTIME_VERSION and tests/test_qmldeco_geometry.py pins the e13
values that KWin must reproduce.

Semantics (verified against E16 borders.c BorderWinpartCalc):
- anchor = ((percent * ref) >> 10) + absolute [+ origin part's x/y];
  percent is Q10 (1024 = 100%), ref is the frame w/h or the origin part's
  box; bottom-right anchors are INCLUSIVE → w = brX - tlX + 1.
- max clamp RE-CENTERS: x += (w - max) >> 1 before w = max; min clamp
  only grows.
- __FLAG_TITLE + __MAX_WIDTH 0: w = clamp(text_w + pad.l + pad.r, min_w,
  span); x = span_x + ((span - w) * justification_q10 >> 10). The
  __MAX_HEIGHT 0 analog handles vertical titles.

ALL math happens in E16 REFERENCE pixels and the result is multiplied by
``theme.scale`` at the very end — computing directly in output pixels
doubles the inclusive "+1" and shifts every max-clamped part by
(scale-1)/2 px (e13's KILL landed at (1,1) instead of (0,0)). The
part-model geometry fields are therefore UNSCALED ref px; only
display-only fields (insets, pixelSize, borders) are pre-scaled.
"""
from __future__ import annotations

from collections.abc import Callable

RUNTIME_VERSION = 1

_MAX_ORIGIN_DEPTH = 8


def part_geometry(
    data: dict,
    index: int,
    frame_w: int,
    frame_h: int,
    title_width: Callable[[int], int],
) -> tuple[int, int, int, int]:
    """Resolve part *index* to ``(x, y, w, h)`` in OUTPUT pixels.

    ``frame_w`` / ``frame_h`` are the decoration frame size in output px.
    ``title_width(i)`` returns the measured caption text width in output
    px (no padding) for title part *i* — the runtime feeds it from a
    hidden ``Text``; tests feed constants.
    """
    scale = int(data["scale"])
    ref_w = round(frame_w / scale)
    ref_h = round(frame_h / scale)

    def ref_title_width(i: int) -> int:
        return -(-title_width(i) // scale)  # ceil division

    x, y, w, h = _geom_ref(data, index, ref_w, ref_h, ref_title_width, 0)
    return (x * scale, y * scale, w * scale, h * scale)


def _geom_ref(
    data: dict,
    index: int,
    ref_w: int,
    ref_h: int,
    title_width: Callable[[int], int],
    depth: int,
) -> tuple[int, int, int, int]:
    if depth > _MAX_ORIGIN_DEPTH:
        return (0, 0, 0, 0)
    p = data["parts"][index]

    tl_bx = tl_by = 0
    tl_rw, tl_rh = ref_w, ref_h
    if p["tlOrigin"] >= 0:
        ox, oy, ow, oh = _geom_ref(
            data, p["tlOrigin"], ref_w, ref_h, title_width, depth + 1
        )
        tl_bx, tl_by, tl_rw, tl_rh = ox, oy, ow, oh
    br_bx = br_by = 0
    br_rw, br_rh = ref_w, ref_h
    if p["brOrigin"] >= 0:
        ox, oy, ow, oh = _geom_ref(
            data, p["brOrigin"], ref_w, ref_h, title_width, depth + 1
        )
        br_bx, br_by, br_rw, br_rh = ox, oy, ow, oh

    x = ((p["tlXP"] * tl_rw) >> 10) + p["tlXA"] + tl_bx
    y = ((p["tlYP"] * tl_rh) >> 10) + p["tlYA"] + tl_by
    x2 = ((p["brXP"] * br_rw) >> 10) + p["brXA"] + br_bx
    y2 = ((p["brYP"] * br_rh) >> 10) + p["brYA"] + br_by
    w = x2 - x + 1
    h = y2 - y + 1

    if p["isTitle"] and not p["vertical"] and p["maxW"] == 0:
        tw = title_width(index) + p["padLeft"] + p["padRight"]
        if p["minW"] > 0 and tw < p["minW"]:
            tw = p["minW"]
        if tw > w:
            tw = w
        x += ((w - tw) * p["justification"]) >> 10
        w = tw
    else:
        if p["maxW"] > 0 and w > p["maxW"]:
            x += (w - p["maxW"]) >> 1
            w = p["maxW"]
        if p["minW"] > 0 and w < p["minW"]:
            w = p["minW"]

    if p["isTitle"] and p["vertical"] and p["maxH"] == 0:
        th = title_width(index) + p["padTop"] + p["padBottom"]
        if p["minH"] > 0 and th < p["minH"]:
            th = p["minH"]
        if th > h:
            th = h
        y += ((h - th) * p["justification"]) >> 10
        h = th
    else:
        if p["maxH"] > 0 and h > p["maxH"]:
            y += (h - p["maxH"]) >> 1
            h = p["maxH"]
        if p["minH"] > 0 and h < p["minH"]:
            h = p["minH"]

    return (x, y, w, h)
