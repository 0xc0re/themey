"""Theme → theme.js part model for the generic QML runtime.

Contract: the emitted ``theme.js`` is pure data (``var theme = {...};``,
imported by main.qml via ``import "theme.js" as ThemeData`` — never
runtime JSON/XHR, which Qt6 gates behind QML_XHR_ALLOW_FILE_READ).
Geometry fields (anchors, min/max, pads) stay in UNSCALED E16 reference
pixels — the resolver computes in ref space and multiplies by scale at
the end (see resolver.py: output-space math shifts max-clamped parts).
Display-only fields ARE pre-scaled: ``borders``, ``insets`` /
``slotInsets`` (BorderImage insets on the upscaled PNGs — PER IMAGE SLOT,
because E16's ``__EDGE_SCALING`` is per image state: ``slotInsets[slot]``
is the edge of the state that slot resolved to, ``insets`` the normal
slot's for old readers) and ``text.pixelSize``. Image state fallbacks are
resolved HERE so the runtime only ever binds concrete filenames; origin
topology is validated HERE (an origin must reference an earlier-declared
part — violations degrade to window-relative with a ``qmldeco:`` note).

Caption text: ``text.effect`` is ``"none" | "shadow" | "outline"``
(E16 ``__DRAWING_EFFECT``; ``text.c`` TsTextDraw draws the shadow at
+1,+1 and the outline at the four neighbours) painted in
``text.effectColorNormal`` / ``effectColorActive`` — the tclass state's
``__BACKGROUND_COLOR`` (E16 ``bg_col``, black when undeclared). The
part's ``justification`` (Q10) positions the caption INSIDE the part
exactly like E16 (``xx = x + ((limit - textw) * justh) >> 10``): 512
centers, 1024 right-aligns, whatever the part's width.

The part model keys are the shared vocabulary with runtime/resolver.js and
resolver.py — change all three together and bump RUNTIME_VERSION.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from themey.ir import ButtonPart, IClassSpec, Theme

from .actions import button_kind
from .resolver import RUNTIME_VERSION, part_geometry, scale_px

# Reference frame (ref px, pre-scale) for the emitter-side maximized
# side-zone detection — mirrors analyze/coords.py's binning reference.
REFERENCE_W = 800
REFERENCE_H = 600
# Caption width stand-in for the reference resolve; only title parts read
# it and they always live in the top band, so precision is irrelevant here.
REFERENCE_TITLE_W = 120

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_]+")

# E16 TextclassCreate default justification (Q10 center).
DEFAULT_JUSTIFICATION = 512
DEFAULT_TITLE_SIZE = 10

# (model key, filename suffix) per E16 state; fallback chains below.
_STATE_ATTRS: tuple[tuple[str, str], ...] = (
    ("normal", "normal"),
    ("normal_active", "normal_active"),
    ("hilited", "hilited"),
    ("hilited_active", "hilited_active"),
    ("normal_active_hilited", "normal_active_hilited"),
    ("clicked", "clicked"),
    ("clicked_active", "clicked_active"),
    ("normal_sticky", "normal_sticky"),
    ("normal_active_sticky", "normal_active_sticky"),
)

# Runtime image slot → E16 state fallback chain (first existing wins).
_SLOT_CHAINS: dict[str, tuple[str, ...]] = {
    "normal": ("normal",),
    "normalActive": ("normal_active", "normal"),
    "hover": ("hilited", "normal"),
    # normal_active_hilited is E16's hover-of-active alias; when a theme
    # declares both, hilited_active wins (e13 ships identical art in both).
    "hoverActive": (
        "hilited_active",
        "normal_active_hilited",
        "hilited",
        "normal_active",
        "normal",
    ),
    "pressed": ("clicked", "normal"),
    "pressedActive": ("clicked_active", "clicked", "normal_active", "normal"),
    # Toggle buttons (stick/shade): sticky art first, then clicked so themes
    # whose sticky art is absent still show a visibly pressed-in toggle.
    "toggled": ("normal_sticky", "clicked", "normal"),
    "toggledActive": (
        "normal_active_sticky",
        "normal_sticky",
        "clicked_active",
        "clicked",
        "normal_active",
        "normal",
    ),
}
_BUTTON_SLOTS = tuple(_SLOT_CHAINS)
_CHROME_SLOTS = ("normal", "normalActive")

# --shade-button values (Phase F): KWin removed window shading in Plasma 6,
# so a "shade" part's dead slot is remapped to another action by default.
# "maximize" (default) / keepAbove / keepBelow / menu swap the QML button
# kind directly — the runtime (ThemeyButton.qml) already drives tooltip,
# enabled-gating and toggled art off `kind` for all of these, so no runtime
# change is needed. "hide" nulls the part's button+images (invisible
# chrome; the part index is kept — origin chains reference parts by
# index). "none" preserves today's inert disabled-shade-button behavior.
SHADE_BUTTON_MODES = ("maximize", "keepAbove", "keepBelow", "menu", "hide", "none")

_SHADE_KIND_REMAP: dict[str, str] = {
    "maximize": "maximizeRestore",
    "keepAbove": "keepAbove",
    "keepBelow": "keepBelow",
    "menu": "menu",
}


def safe_name(iclass_name: str) -> str:
    """Filesystem-safe lowercase image basename stem for an iclass."""
    return _SAFE_NAME_RE.sub("_", iclass_name).strip("_").lower() or "part"


def _existing_states(ic: IClassSpec) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for attr, suffix in _STATE_ATTRS:
        path = getattr(ic, attr)
        if path is not None and path.is_file():
            out[suffix] = path
    return out


def _resolve_slots(
    ic: IClassSpec | None, slots: tuple[str, ...]
) -> dict[str, str] | None:
    """Resolve slot → the E16 state attribute whose art backs it.

    Returns None when the iclass has no usable image at all.
    """
    if ic is None:
        return None
    states = _existing_states(ic)
    if not states:
        return None
    resolved: dict[str, str] = {}
    for slot in slots:
        for state in _SLOT_CHAINS[slot]:
            if state in states:
                resolved[slot] = state
                break
        else:
            # No chain member exists; fall back to any existing state so the
            # slot is never absent (the runtime binds unconditionally).
            resolved[slot] = next(iter(states))
    return resolved


def _resolve_images(
    ic: IClassSpec | None,
    slots: tuple[str, ...],
    manifest: dict[str, Path],
) -> dict[str, str] | None:
    """Resolve slot → package-relative image URL, registering exports.

    Returns None when the iclass has no usable image at all.
    """
    slot_states = _resolve_slots(ic, slots)
    if ic is None or slot_states is None:
        return None
    states = _existing_states(ic)
    stem = safe_name(ic.name)
    resolved: dict[str, str] = {}
    for slot, state in slot_states.items():
        relname = f"{stem}_{state}.png"
        manifest[relname] = states[state]
        resolved[slot] = f"../images/{relname}"
    return resolved


def _rgb(color: tuple[int, int, int] | None, fallback: str) -> str:
    if color is None:
        return fallback
    r, g, b = (max(0, min(255, c)) for c in color)
    return f"#{r:02x}{g:02x}{b:02x}"


def _clamped_insets(
    ic: IClassSpec | None, scale: float, state: str | None = None
) -> dict[str, int]:
    """BorderImage insets = scale_px(__EDGE_SCALING), clamped to the source
    image so left+right ≤ width and top+bottom ≤ height (Qt renders a
    zero-width middle fine; negative middles it does not). scale_px keeps
    the insets aligned with the shipped art dimensions (upscale_part
    targets the same rounding). *state* (an image state attribute) picks
    that state's own edge and image — E16 slices per state; None keeps
    the iclass-wide last-wins edge against the first available art."""
    if ic is None:
        return {"left": 0, "right": 0, "top": 0, "bottom": 0}
    edge = ic.edge_for(state) if state is not None else ic.edge_scaling
    left, right, top, bottom = (scale_px(v, scale) for v in edge)
    img: Path | None = getattr(ic, state, None) if state is not None else None
    if img is None:
        img = ic.normal or ic.normal_active or ic.hilited or ic.clicked
    if img is not None and img.is_file():
        try:
            from PIL import Image

            with Image.open(img) as im:
                iw = scale_px(im.width, scale)
                ih = scale_px(im.height, scale)
            if left + right > iw:
                over = left + right - iw
                right = max(0, right - over)
                left = min(left, iw - right)
            if top + bottom > ih:
                over = top + bottom - ih
                bottom = max(0, bottom - over)
                top = min(top, ih - bottom)
        except OSError:
            pass
    return {"left": left, "right": right, "top": top, "bottom": bottom}


def _font_index(
    theme: Theme,
    part: ButtonPart,
    fonts_model: list[dict],
    font_sources: list[Path],
) -> tuple[int, int]:
    """Return (fontIndex, pixelSize) for a title part; fontIndex -1 = system."""
    tclass = theme.tclasses.get(part.tclass_name or "")
    alias = tclass.font_alias if tclass is not None else None
    spec = theme.fonts.get(alias) if alias else None
    if spec is None or spec.ttf_path is None:
        size = spec.size if spec is not None else DEFAULT_TITLE_SIZE
        return (-1, scale_px(size, theme.scale))
    for i, src in enumerate(font_sources):
        if src == spec.ttf_path:
            return (i, scale_px(spec.size, theme.scale))
    style = ""
    try:
        from PIL import ImageFont

        style = (ImageFont.truetype(str(spec.ttf_path)).getname()[1] or "").lower()
    except OSError:
        pass
    fonts_model.append(
        {
            "source": f"../fonts/{spec.ttf_path.name}",
            "family": spec.family or spec.ttf_path.stem,
            "italic": "italic" in style or "oblique" in style,
            "bold": "bold" in style,
        }
    )
    font_sources.append(spec.ttf_path)
    return (len(fonts_model) - 1, scale_px(spec.size, theme.scale))


def build_theme_data(
    theme: Theme,
    *,
    shade_button: str = "maximize",
) -> tuple[dict, dict[str, Path], list[Path]]:
    """Build the theme.js data dict + image manifest + font source list.

    Appends ``qmldeco:`` fidelity notes to ``theme.notes``. Must run inside
    the ``with extract(...)`` block — it reads part images and TTFs from
    ``theme.asset_root``.

    ``shade_button`` (one of ``SHADE_BUTTON_MODES``) remaps E16's shade
    part, which Plasma 6 can no longer act on (KWin removed window
    shading): see the module-level comment above ``SHADE_BUTTON_MODES``.
    """
    if shade_button not in SHADE_BUTTON_MODES:
        raise ValueError(
            f"shade_button must be one of {SHADE_BUTTON_MODES} "
            f"(got {shade_button!r})"
        )
    scale = theme.scale
    manifest: dict[str, Path] = {}
    fonts_model: list[dict] = []
    font_sources: list[Path] = []
    parts: list[dict] = []

    for i, part in enumerate(theme.border.parts):
        orig_kind = button_kind(part)
        kind = orig_kind
        hidden_shade = False
        if orig_kind == "shade":
            if shade_button == "hide":
                kind = None
                hidden_shade = True
            elif shade_button != "none":
                kind = _SHADE_KIND_REMAP[shade_button]
            # "none": kind stays "shade" — today's behavior, unchanged.

        ic = theme.iclasses.get(part.iclass_name)
        slot_states: dict[str, str] | None = None
        if hidden_shade:
            # Invisible chrome: no art resolved/exported for a button
            # nobody can click. The part index — and its origin chain —
            # stay exactly where they were.
            images = None
        else:
            slots = _BUTTON_SLOTS if kind is not None else _CHROME_SLOTS
            images = _resolve_images(ic, slots, manifest)
            slot_states = _resolve_slots(ic, slots)
            if images is None:
                theme.notes.append(
                    f"qmldeco: part '{part.iclass_name}' has no usable image "
                    "— rendered as empty space"
                )

        if orig_kind == "shade":
            if shade_button == "none":
                theme.notes.append(
                    f"qmldeco: shade button '{part.iclass_name}' generated, "
                    "but KWin removed window shading in Plasma 6 — the "
                    "button is disabled and absorbs clicks (E16 art still "
                    "renders)"
                )
            elif shade_button == "hide":
                theme.notes.append(
                    f"qmldeco: shade button '{part.iclass_name}' hidden — "
                    "Plasma 6 removed window shading; --shade-button to "
                    "override"
                )
            else:
                theme.notes.append(
                    f"qmldeco: shade button '{part.iclass_name}' remapped "
                    f"to {shade_button} — Plasma 6 removed shading; "
                    "--shade-button to override"
                )

        tl_origin, br_origin = part.tl_origin, part.br_origin
        for label, origin in (("topleft", tl_origin), ("bottomright", br_origin)):
            if origin >= i:
                theme.notes.append(
                    f"qmldeco: part '{part.iclass_name}' {label} origin {origin} "
                    "does not reference an earlier-declared part — "
                    "degraded to window-relative"
                )
        if tl_origin >= i:
            tl_origin = -1
        if br_origin >= i:
            br_origin = -1

        is_title = "__FLAG_TITLE" in part.flags
        vertical = bool(is_title and part.max_w > 0 and part.max_h == 0)

        pad_l = pad_r = pad_t = pad_b = 0
        if ic is not None:
            pad_l, pad_r, pad_t, pad_b = ic.padding

        text: dict | None = None
        justification = DEFAULT_JUSTIFICATION
        if is_title:
            tclass = theme.tclasses.get(part.tclass_name or "")
            if tclass is not None and tclass.justification_q10 is not None:
                justification = tclass.justification_q10
            font_index, pixel_size = _font_index(
                theme, part, fonts_model, font_sources
            )
            bg_normal = tclass.bg_normal if tclass else None
            bg_active = (tclass.bg_active or tclass.bg_normal) if tclass else None
            text = {
                "colorNormal": _rgb(
                    tclass.fg_normal if tclass else None, "#c0c0c0"
                ),
                "colorActive": _rgb(
                    (tclass.fg_active or tclass.fg_normal) if tclass else None,
                    "#ffffff",
                ),
                "effect": tclass.effect_kind if tclass else "none",
                # E16 bg_col defaults to calloc'ed black.
                "effectColorNormal": _rgb(bg_normal, "#000000"),
                "effectColorActive": _rgb(bg_active, "#000000"),
                "fontIndex": font_index,
                "pixelSize": pixel_size,
            }

        parts.append(
            {
                "id": part.iclass_name,
                "tlXP": part.tl_x_pct,
                "tlXA": part.tl_x_abs,
                "tlYP": part.tl_y_pct,
                "tlYA": part.tl_y_abs,
                "brXP": part.br_x_pct,
                "brXA": part.br_x_abs,
                "brYP": part.br_y_pct,
                "brYA": part.br_y_abs,
                "tlOrigin": tl_origin,
                "brOrigin": br_origin,
                "minW": part.min_w,
                "maxW": part.max_w,
                "minH": part.min_h,
                "maxH": part.max_h,
                "isTitle": is_title,
                "vertical": vertical,
                "padLeft": pad_l,
                "padRight": pad_r,
                "padTop": pad_t,
                "padBottom": pad_b,
                "justification": justification,
                "keepWhenShaded": part.keep_when_shaded,
                "hideWhenMaximized": False,  # filled below
                "button": kind,
                "insets": _clamped_insets(
                    ic, scale, slot_states.get("normal") if slot_states else None
                ),
                "slotInsets": {
                    slot: _clamped_insets(ic, scale, state)
                    for slot, state in (slot_states or {}).items()
                },
                "images": images,
                "text": text,
            }
        )

    border = theme.border
    data = {
        "runtimeVersion": RUNTIME_VERSION,
        "name": theme.name,
        "scale": scale,
        "borders": {
            "left": scale_px(border.border_size_left, scale),
            "right": scale_px(border.border_size_right, scale),
            "top": scale_px(border.border_size_top, scale),
            "bottom": scale_px(border.border_size_bottom, scale),
        },
        "fonts": fonts_model,
        "parts": parts,
    }

    _mark_hidden_when_maximized(theme, data)
    return data, manifest, font_sources


def _mark_hidden_when_maximized(theme: Theme, data: dict) -> None:
    """When maximized only the title band survives (side/bottom borders
    collapse to 0), so any part that does not fit inside the band — the
    side rails, the bottom strip, side-stack buttons below the band — is
    hidden. Detection resolves every part at the reference frame with the
    shared resolver; a corner button that lives within the band's rows
    (e13's KILL) stays visible."""
    scale = theme.scale
    frame_w = scale_px(REFERENCE_W, scale)
    frame_h = scale_px(REFERENCE_H, scale)
    band_h = data["borders"]["top"]
    for i, p in enumerate(data["parts"]):
        _x, y, _w, h = part_geometry(
            data, i, frame_w, frame_h,
            lambda _i: scale_px(REFERENCE_TITLE_W, scale),
        )
        if y + h > band_h:
            p["hideWhenMaximized"] = True
            if p["button"] is not None:
                theme.notes.append(
                    f"qmldeco: button '{p['id']}' sits below the title band "
                    "and is hidden while the window is maximized (side and "
                    "bottom borders collapse to 0 there)"
                )


def render_theme_js(data: dict) -> str:
    """Render the theme.js source text (stable, snapshot-friendly)."""
    payload = json.dumps(data, indent=2, sort_keys=True)
    return (
        f"// Generated by themey — QML decoration data (runtime v{RUNTIME_VERSION}).\n"
        "// Pure data: imported by main.qml as ThemeData; no runtime I/O.\n"
        f"var theme = {payload};\n"
    )
