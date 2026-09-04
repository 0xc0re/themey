// themey QML runtime v1 — E16 BorderWinpartCalc geometry resolver.
// KEEP IN LOCKSTEP with src/themey/generate/qmldeco/resolver.py (the
// emitter/test-side mirror).
//
// Semantics: anchor = ((pct * ref) >> 10) + abs [+ origin part x/y];
// percent is Q10 (1024 = 100%); bottom-right anchors are INCLUSIVE
// (w = brX - tlX + 1); max clamps RE-CENTER with E16's own expression
// x = ((x + ox) - max) >> 1 (ox = inclusive anchor; one px left of the
// naive x + (span - max) >> 1 when span - max is even), min only grows
// and only when max did not clamp (else-if); __FLAG_TITLE + __MAX_WIDTH 0
// sizes the part to the caption text plus iclass padding, positioned by
// tclass justification, min applied AFTER that span clamp without
// re-centering (vertical analog for __MAX_HEIGHT 0).
//
// ALL math happens in E16 REFERENCE pixels; the result is multiplied by
// theme.scale at the end. Computing in output pixels doubles the
// inclusive "+1" and shifts max-clamped parts — part-model geometry
// fields are UNSCALED ref px (insets/pixelSize/borders are the pre-scaled
// display-only exceptions).
//
// Scale may be FRACTIONAL. Every ref→output conversion uses scalePx
// (floor(v*s + 0.5) — half-up like resolver.py's scale_px, NOT
// Math.round-vs-round() divergent), and the final multiply is EDGE-based
// (x_out = scalePx(x), w_out = scalePx(x+w) - x_out) so adjacent parts
// stay seamless. Identical to v*scale at integer scales.
.pragma library

var RUNTIME_VERSION = 6;
var MAX_ORIGIN_DEPTH = 8;

// Keep in lockstep with resolver.py scale_px.
function scalePx(v, s) {
    return Math.floor(v * s + 0.5);
}

// frameW/frameH and titleWidthFn results are OUTPUT px; so is the result.
function partGeometry(theme, index, frameW, frameH, titleWidthFn) {
    var scale = theme.scale;
    var refW = Math.floor(frameW / scale + 0.5);
    var refH = Math.floor(frameH / scale + 0.5);
    var refTW = function (i) { return Math.ceil(titleWidthFn(i) / scale); };
    var g = _geom(theme, index, refW, refH, refTW, 0);
    var xOut = scalePx(g.x, scale);
    var yOut = scalePx(g.y, scale);
    return {
        x: xOut,
        y: yOut,
        w: scalePx(g.x + g.w, scale) - xOut,
        h: scalePx(g.y + g.h, scale) - yOut
    };
}

function _geom(theme, index, refW, refH, titleWidthFn, depth) {
    if (depth > MAX_ORIGIN_DEPTH)
        return { x: 0, y: 0, w: 0, h: 0 };
    var p = theme.parts[index];

    var tlBX = 0, tlBY = 0, tlRW = refW, tlRH = refH;
    if (p.tlOrigin >= 0) {
        var o = _geom(theme, p.tlOrigin, refW, refH, titleWidthFn, depth + 1);
        tlBX = o.x; tlBY = o.y; tlRW = o.w; tlRH = o.h;
    }
    var brBX = 0, brBY = 0, brRW = refW, brRH = refH;
    if (p.brOrigin >= 0) {
        var o2 = _geom(theme, p.brOrigin, refW, refH, titleWidthFn, depth + 1);
        brBX = o2.x; brBY = o2.y; brRW = o2.w; brRH = o2.h;
    }

    var x = ((p.tlXP * tlRW) >> 10) + p.tlXA + tlBX;
    var y = ((p.tlYP * tlRH) >> 10) + p.tlYA + tlBY;
    var x2 = ((p.brXP * brRW) >> 10) + p.brXA + brBX;
    var y2 = ((p.brYP * brRH) >> 10) + p.brYA + brBY;
    var w = x2 - x + 1;
    var h = y2 - y + 1;

    // borders.c BorderWinpartCalc, kept in its exact clamp order.
    if (p.isTitle && !p.vertical && p.maxW === 0) {
        var tw = titleWidthFn(index) + p.padLeft + p.padRight;
        if (w > tw) { x += ((w - tw) * p.justification) >> 10; w = tw; }
        if (p.minW > 0 && w < p.minW) w = p.minW;  // after the span clamp
    } else if (p.maxW > 0 && w > p.maxW) {
        x = (x + x2 - p.maxW) >> 1; w = p.maxW;
    } else if (p.minW > 0 && w < p.minW) {
        w = p.minW;
    }

    if (p.isTitle && p.vertical && p.maxH === 0) {
        var th = titleWidthFn(index) + p.padTop + p.padBottom;
        if (h > th) { y += ((h - th) * p.justification) >> 10; h = th; }
        if (p.minH > 0 && h < p.minH) h = p.minH;
    } else if (p.maxH > 0 && h > p.maxH) {
        y = (y + y2 - p.maxH) >> 1; h = p.maxH;
    } else if (p.minH > 0 && h < p.minH) {
        h = p.minH;
    }

    return { x: x, y: y, w: w, h: h };
}
