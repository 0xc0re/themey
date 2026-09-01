"""Frozen IR — the only contract crossing the analyze/generate seam.

All types in this module are frozen dataclasses. Code on the analyze side
populates them; code on the generate side reads them. The only mutable
accumulator is ``Theme.notes`` (a ``list[str]``), which exists specifically
so analysis-stage code can append fidelity notes that ``report.py`` and
``preview.py`` later read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Palette:
    """Sampled dominant colors from the theme imagery."""

    titlebar_active: tuple[int, int, int]  # RGB 0-255
    titlebar_inactive: tuple[int, int, int]
    text_active: tuple[int, int, int]
    text_inactive: tuple[int, int, int]


@dataclass(frozen=True)
class ColorGroup:
    """The theme-derived half of one KColorScheme ``[Colors:*]`` group.

    A ``.colors`` group holds 12 keys; these are the 7 that carry the
    theme's own cast. The other 5 (``ForegroundLink``/``Visited``/
    ``Negative``/``Neutral``/``Positive``) are semantic — "this link is
    unvisited", "this value is an error" — so they stay Breeze stock and
    live in ``generate/colors.py`` rather than here.
    """

    background_normal: tuple[int, int, int]  # RGB 0-255
    background_alternate: tuple[int, int, int]
    foreground_normal: tuple[int, int, int]
    foreground_inactive: tuple[int, int, int]
    foreground_active: tuple[int, int, int]
    decoration_focus: tuple[int, int, int]
    decoration_hover: tuple[int, int, int]


@dataclass(frozen=True)
class ColorScheme:
    """A whole KColorScheme sampled from the theme's border art.

    One field per ``[Colors:*]`` group in the 13-group ``.colors`` file,
    plus the four ``[WM]`` colors (the titlebar pair KWin reads). The
    ``header_inactive`` group is emitted under the literal nested section
    ``[Colors:Header][Inactive]``.

    ``Palette`` is derived from the ``wm_*`` fields (see
    ``analyze/colors.build_scheme``) so the decoration backends and the
    color scheme cannot disagree about the titlebar.
    """

    view: ColorGroup
    window: ColorGroup
    button: ColorGroup
    selection: ColorGroup
    tooltip: ColorGroup
    complementary: ColorGroup
    header: ColorGroup
    header_inactive: ColorGroup
    wm_active_background: tuple[int, int, int]
    wm_active_foreground: tuple[int, int, int]
    wm_inactive_background: tuple[int, int, int]
    wm_inactive_foreground: tuple[int, int, int]


@dataclass(frozen=True)
class IClassSpec:
    """E16 image class — one border-region image with up to 8 state variants."""

    name: str  # e.g. "TITLE_BAR_HORIZONTAL"
    edge_scaling: tuple[int, int, int, int]  # (left, right, top, bottom) from __EDGE_SCALING
    normal: Path | None  # path under asset_root, may be None
    normal_active: Path | None
    hilited: Path | None
    hilited_active: Path | None
    clicked: Path | None
    clicked_active: Path | None
    normal_sticky: Path | None
    normal_active_sticky: Path | None
    # __NORMAL_ACTIVE_HILITED: E16's hover-of-active alias. e13 declares it
    # alongside __HILITED_ACTIVE (identical art); themes may ship it alone.
    normal_active_hilited: Path | None = None
    # __PADDING l r t b: inner-content padding for this image class. Distinct
    # from __EDGE_SCALING, which is the 9-patch slice configuration. No
    # consumer yet — captured for a future fidelity pass.
    padding: tuple[int, int, int, int] = (0, 0, 0, 0)


@dataclass(frozen=True)
class FontSpec:
    """One E16 font alias from ``fonts.theme.cfg`` / ``fonts.cfg``.

    ``ttf_path`` points under asset_root for ``name/size`` TTF entries and is
    None for XLFD-only entries (no shippable font file). ``family`` is the
    face's real family name (read from the TTF when possible, else a
    best-effort guess) — QML ``FontLoader.name`` reports the same family, so
    consumers can pre-fill it. ``size`` is E16's pixel-ish size; the QML
    runtime maps it to ``font.pixelSize = size * scale``.
    """

    alias: str  # e.g. "font-default"
    ttf_path: Path | None  # under asset_root; None for XLFD entries
    family: str | None
    size: int


@dataclass(frozen=True)
class TClassSpec:
    """E16 text class — titlebar text style per state.

    ``alignment`` is normalized to Aurorae's vocabulary ("Left", "Center",
    "Right") at parse time so the writer can pass it through as-is.
    ``effect`` is the raw E16 token (e.g. ``"__EFFECT_SHADOW"`` /
    ``"__EFFECT_NONE"``); the writer interprets it. ``effect_color`` is
    the optional ``__EFFECT_COLOR R G B`` triple — defaults to ``None``
    because most themes leave it implicit.
    """

    name: str  # e.g. "TEXT1"
    fg_normal: tuple[int, int, int] | None  # __FORGROUND_COLOR after __NORMAL
    fg_active: tuple[int, int, int] | None  # __FORGROUND_COLOR after __NORMAL_ACTIVE
    alignment: str | None = None  # "Left" | "Center" | "Right"
    effect: str | None = None  # raw __DRAWING_EFFECT token, e.g. __EFFECT_SHADOW
    effect_color: tuple[int, int, int] | None = None
    # Raw Q10 __JUSTIFICATION (0 = left, 512 = center, 1024 = right), E16
    # last-wins semantics across the whole block (E16 keeps one justification
    # per tclass, not per state). ``alignment`` above stays the normalized
    # first-seen value the SVG backend has always used.
    justification_q10: int | None = None
    # Raw per-state font tokens (e.g. "*font-default" — a '*' prefix
    # references a __FONTS alias; anything else is a direct font string).
    font_normal: str | None = None  # value of __NORMAL
    font_active: str | None = None  # value of __NORMAL_ACTIVE
    # Alias name (without '*') from font_active or font_normal, when either
    # is an alias reference. Key into Theme.fonts.
    font_alias: str | None = None


@dataclass(frozen=True)
class ButtonPart:
    """One button within a border — position encoded in E16's hybrid pct+abs coordinate."""

    iclass_name: str
    aclass: str | None  # null sentinel when E16 source omits __ACLASS
    tl_x_pct: int  # Q10 fixed-point: 1024 == 100%
    tl_x_abs: int  # signed; may be negative
    tl_y_pct: int
    tl_y_abs: int
    br_x_pct: int
    br_x_abs: int
    br_y_pct: int
    br_y_abs: int
    # Origin part index for hybrid coords. -1 = window-relative (the default
    # in all fixture themes); >=0 = relative to the bbox of that part.
    tl_origin: int = -1
    br_origin: int = -1
    # __FLAGS tokens verbatim (e.g. ("__FLAG_TITLE",) or ("__FLAG_MINIICON",)).
    # Per the E16 config grammar, __FLAGS is a
    # whitespace-separated list of tokens. We retain ordering so consumers can
    # use simple membership tests.
    flags: tuple[str, ...] = ()
    # Optional E16 BORDERPART decorations (no Aurorae equivalent — captured
    # so a future emission pass can use them).
    cursor_name: str | None = None  # __CURSOR ICONIFY
    tclass_name: str | None = None  # __TCLASS TEXT1
    keep_when_shaded: bool = False  # __KEEP_WHEN_SHADED __ON|__OFF
    keep_on_top: bool = False  # __KEEP_ON_TOP __ON|__OFF
    # __MIN_/__MAX_ size constraints in reference pixels. 0 = unspecified.
    min_w: int = 0
    min_h: int = 0
    max_w: int = 0
    max_h: int = 0


@dataclass(frozen=True)
class BorderSpec:
    """One E16 border definition (DEFAULT, BORDERLESS, DIALOG, …)."""

    name: str  # "DEFAULT" in practice; other borders are SKIPPED
    border_size_left: int
    border_size_right: int
    border_size_top: int
    border_size_bottom: int
    parts: tuple[ButtonPart, ...]


@dataclass(frozen=True)
class CursorSpec:
    """One ``__CURSOR`` block: an XBM cursor with its hotspot and fg/bg colors.

    E16 cursors.c parses __CURSOR blocks with optional __NAME, __XBM_FILE,
    __NATIVE_ID, __HOT_X, __HOT_Y, __FG_COLOR, __BG_COLOR. Hotspots
    default to 0 when the cfg omits them. Foreground/background default to
    white/black (the E16 source default). xbm_path is None when the cfg
    references a file outside asset_root or that doesn't exist on disk —
    emission code is responsible for handling that case. native_id carries
    an X11 cursor-font glyph name (``XC_LEFT_PTR``) for blocks that
    recolor a stock cursor instead of shipping XBM art (Obsidian's whole
    pointer set); the emitter cannot convert those (no cursor-font
    rasterizer) but must report them truthfully.
    """

    name: str  # E16 cursor name (e.g. "DEFAULT", "MOVE", "RESIZE_BR")
    xbm_path: Path | None
    hot_x: int
    hot_y: int
    fg_rgb: tuple[int, int, int]
    bg_rgb: tuple[int, int, int]
    native_id: str | None = None


@dataclass(frozen=True)
class WallpaperSpec:
    """One background image declared in ``desktops.cfg``, with its fill mode.

    ``fill_mode`` is ``"tiled"`` for ``ADD_BACKGROUND_TILED*`` macros and
    ``"scaled"`` for ``ADD_BACKGROUND_SCALED``/``BG_FILE`` — it becomes the
    wallpaper package's ``X-Themey-FillMode`` (see
    ``generate/wallpaper.py``), so ``apply`` can read tiled-ness back out of
    the installed package without re-parsing the E16 source.
    """

    path: Path  # under asset_root
    fill_mode: str  # "tiled" | "scaled"


@dataclass(frozen=True)
class Theme:
    """Complete analyzed representation of one E16 theme.

    Frozen except for ``notes``, which is intentionally mutable so that
    analysis-stage code can accumulate fidelity warnings without violating
    the frozen contract on all other fields.
    """

    name: str  # slug from filename, e.g. "Aliens"
    display_name: str  # human label, may equal name
    author: str | None
    # In [0.5, 3], quantized to 2 decimals; int-valued scales are stored as
    # int. Fractional values are QML-backend-only (pipeline enforces it).
    scale: float
    asset_root: Path  # extracted tmpdir; valid only during convert()
    border: BorderSpec
    iclasses: dict[str, IClassSpec]  # by IClass name
    tclasses: dict[str, TClassSpec]
    button_codes: dict[str, str]  # part.iclass_name -> "X"|"A"|"I"|"L"|"S"
    left_buttons: str  # final Aurorae LeftButtons string, e.g. "XAI"
    right_buttons: str
    palette: Palette
    cursors: tuple[CursorSpec, ...] = ()
    wallpapers: tuple[Path, ...] = ()
    # Additive alongside `wallpapers` (which stays the bare-path view some
    # older call sites read); carries the fill-mode `wallpapers` cannot.
    wallpaper_specs: tuple[WallpaperSpec, ...] = ()
    # Sampled KDE color scheme. ``palette`` above is derived from it, so the
    # two always agree. Defaulted so hand-built Themes in existing tests stay
    # valid; ``generate/colors.py`` falls back to the sampler's default when
    # it is None.
    scheme: ColorScheme | None = None
    # __FONTS aliases (fonts.theme.cfg / fonts.cfg) keyed by alias name.
    # Defaulted so hand-built Themes in existing tests stay valid.
    fonts: dict[str, FontSpec] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)  # ONLY mutable accumulator
    skipped_borders: tuple[str, ...] = ()
