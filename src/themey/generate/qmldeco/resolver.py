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

Scale may be FRACTIONAL (e.g. 1.5), including sub-1 values down to 0.5.
All ref→output conversion goes through ``scale_px`` — floor(v*scale +
0.5), half-up in both implementations (Python ``round()`` is banker's, JS
``Math.round()`` is half-up; they disagree by 1 px on odd values at .5) —
and the final multiply is EDGE-based: ``x_out = scale_px(x)``, ``w_out =
scale_px(x+w) - x_out``, so parts adjacent in ref space stay seamless in
output space. At integer scales this is arithmetically identical to
``v * scale``. Known cosmetic consequence at scale < 1: a 1-ref-px part
can land as a 0-width sliver (edge-based rounding is parity-dependent);
BorderImage then renders nothing for it, which is correct exact-cover
behavior — its neighbors still abut — not an overlap.
"""
from __future__ import annotations

import math
from collections.abc import Callable

RUNTIME_VERSION = 2

_MAX_ORIGIN_DEPTH = 8


def scale_px(v: float, scale: float) -> int:
    """Ref px → output px: floor(v*scale + 0.5). Mirrors resolver.js
    scalePx exactly — keep the two in lockstep."""
    return math.floor(v * scale + 0.5)


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
    scale = float(data["scale"])
    ref_w = math.floor(frame_w / scale + 0.5)
    ref_h = math.floor(frame_h / scale + 0.5)

    def ref_title_width(i: int) -> int:
        return math.ceil(title_width(i) / scale)

    x, y, w, h = _geom_ref(data, index, ref_w, ref_h, ref_title_width, 0)
    x_out = scale_px(x, scale)
    y_out = scale_px(y, scale)
    return (
        x_out,
        y_out,
        scale_px(x + w, scale) - x_out,
        scale_px(y + h, scale) - y_out,
    )


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
