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


#: ``IClassSpec.fill_for`` vocabulary (E16 iclass.h FILL_* → themey names).
FILL_STRETCH = "stretch"
FILL_TILE = "tile"
FILL_TILE_H = "tile-h"
FILL_TILE_V = "tile-v"
FILL_RULES = (FILL_STRETCH, FILL_TILE, FILL_TILE_H, FILL_TILE_V)


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
    # E16 keeps FOUR ImageState arrays — norm, active, sticky, sticky_active
    # (iclass.c ImageclassGetImageState) — each with normal/hilited/clicked.
    # config/definitions gives the sticky keywords these ids:
    #   __NORMAL_STICKY 359, __CLICKED_STICKY 360, __HILITED_STICKY 361,
    #   __NORMAL_ACTIVE_STICKY 362,
    #   __NORMAL_ACTIVE_CLICKED == __CLICKED_ACTIVE_STICKY == 363,
    #   __NORMAL_ACTIVE_HILITED == __HILITED_ACTIVE_STICKY == 364.
    # So ``normal_active_hilited`` IS sticky_active.hilited (the hover art of
    # an active window on all desktops), not a hover-of-active alias — e13
    # and OldE ship it identical to __HILITED_ACTIVE, 40 corpus themes do
    # not. ImageclassPopulate fallbacks: hilited/clicked → that group's
    # normal; active.normal, sticky.normal AND sticky_active.normal → norm.normal.
    normal_active_hilited: Path | None = None
    hilited_sticky: Path | None = None
    clicked_sticky: Path | None = None
    clicked_active_sticky: Path | None = None
    # __PADDING l r t b: inner-content padding for this image class. Distinct
    # from __EDGE_SCALING, which is the 9-patch slice configuration. No
    # consumer yet — captured for a future fidelity pass.
    padding: tuple[int, int, int, int] = (0, 0, 0, 0)
    # Per-state __EDGE_SCALING. E16 attaches the edge to the most recently
    # opened image state (iclass.c ICLASS_LRTB writes ``is->border``), so
    # hover/pressed/inactive art may slice differently from normal art.
    # Keyed by the state ATTRIBUTE name (``"normal"``, ``"hilited_active"``,
    # …; states not on this dataclass such as ``"disabled"`` are kept too).
    # ``edge_scaling`` above stays the last-wins iclass-wide value —
    # consumers go through :meth:`edge_for`.
    edge_by_state: dict[str, tuple[int, int, int, int]] = field(default_factory=dict)
    # Per-state __FILLRULE (iclass.c ICLASS_FILLRULE → is->pixmapfillstyle):
    # one of FILL_RULES. Same attribute-name keys as edge_by_state; a state
    # without a rule is E16's default FILL_STRETCH (ImagestateCreate).
    fill_by_state: dict[str, str] = field(default_factory=dict)

    def fill_for(self, state: str) -> str:
        """``"stretch" | "tile" | "tile-h" | "tile-v"`` for *state*'s art.

        E16 (iclass.c ImagestateMakeBg/MakePmapMask): stretch scales the
        whole image (honouring the 9-patch border); ``__TILE`` repeats it
        at native size on both axes, ``__TILE_H`` at native width but
        stretched to the target height (tiled across), ``__TILE_V`` the
        transpose. Default FILL_STRETCH.
        """
        key = state[2:].lower() if state.startswith("__") else state
        return self.fill_by_state.get(key, FILL_STRETCH)

    def edge_for(self, state: str) -> tuple[int, int, int, int]:
        """The 9-patch edge E16 used for *state*'s art.

        *state* is a state attribute name (``"hilited"``) or the E16
        keyword (``"__HILITED"``). A state without its own ``__EDGE_SCALING``
        falls back to the iclass-wide ``edge_scaling`` (last declared edge —
        the pre-per-state behaviour every consumer relied on; E16 itself
        would draw such a state unsliced, but the corpus overwhelmingly
        declares one edge after the first state and means it for all).
        """
        key = state[2:].lower() if state.startswith("__") else state
        return self.edge_by_state.get(key, self.edge_scaling)


@dataclass(frozen=True)
class FontSpec:
    """One E16 font alias from ``fonts.theme.cfg`` / ``fonts.cfg``.

    ``ttf_path`` points under asset_root for ``name/size`` TTF entries and is
    None for XLFD/xft entries (no shippable font file). ``family`` is the
    face's real family name (read from the TTF when possible, else a
    best-effort guess) — QML ``FontLoader.name`` reports the same family, so
    consumers can pre-fill it.

    ``size`` is the raw number from the alias; ``points`` says what unit it
    is. E16 hands ``name/size`` to ``imlib_load_font`` (text_ift.c:67) and
    Imlib2 sets ``FT_Set_Char_Size(size*64, 96, 96)`` — POINTS at 96 dpi,
    so ``ariali/9`` is 12 px (113 corpus themes title with a TTF; every
    caption was ~25% too small before 2026-09-01). ``xft:family-size``
    patterns are points too (fontconfig). An XLFD's pixel field (7) is
    pixels; its point field (8, deci-points) is points. ``pixel_size``
    resolves the unit; the QML runtime uses ``pixel_size * scale``.
    ``bold``/``italic`` come from the XLFD weight/slant fields or xft
    ``:bold``/``:italic`` (XCreateFontSet/XftFontOpenName honour them).
    ``source_family`` records the authored family when ``family`` was
    aliased to a fontconfig name for a face no modern system carries.
    """

    alias: str  # e.g. "font-default"
    ttf_path: Path | None  # under asset_root; None for XLFD/xft entries
    family: str | None
    size: int
    points: bool = False
    bold: bool = False
    italic: bool = False
    # The XLFD/xft family as written, when ``family`` is an alias for it
    # (``analyze/fonts.py`` ``XLFD_FAMILY_ALIASES``: lucida → DejaVu Sans);
    # None when ``family`` is the authored name.
    source_family: str | None = None

    @property
    def pixel_size(self) -> int:
        """``size`` in pixels: points × 96/72 (half-up), else as is."""
        if self.points:
            return max(1, int(self.size * 96 / 72 + 0.5))
        return self.size


@dataclass(frozen=True)
class TClassSpec:
    """E16 text class — titlebar text style per state.

    ``alignment`` is normalized to Aurorae's vocabulary ("Left", "Center",
    "Right") at parse time so the writer can pass it through as-is.
    ``effect`` is the raw E16 ``__DRAWING_EFFECT`` value (token such as
    ``"__EFFECT_SHADOW"`` or the numeric form from ``config/definitions``:
    0 none/normal, 1 shadow, 2 outline); :attr:`effect_kind` normalizes
    it. E16 paints the shadow/outline in the state's ``bg_col``
    (``text.c`` TsTextDraw), which ``__BACKGROUND_COLOR`` sets after the
    state keyword (``tclass.c`` TEXT_BG_COL) — ``bg_normal``/``bg_active``
    carry those; ``effect_color`` is the derived single color the legacy
    SVG backend keys off. There is no ``__EFFECT_COLOR`` keyword in E16.
    E16's default ``bg_col`` is calloc'ed black; consumers fall back to
    black when the fields are ``None``.
    """

    name: str  # e.g. "TEXT1"
    fg_normal: tuple[int, int, int] | None  # __FORGROUND_COLOR after __NORMAL
    fg_active: tuple[int, int, int] | None  # __FORGROUND_COLOR after __NORMAL_ACTIVE
    alignment: str | None = None  # "Left" | "Center" | "Right"
    effect: str | None = None  # raw __DRAWING_EFFECT value, e.g. __EFFECT_SHADOW
    bg_normal: tuple[int, int, int] | None = None  # __BACKGROUND_COLOR after __NORMAL
    bg_active: tuple[int, int, int] | None = None  # … after __NORMAL_ACTIVE
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
    # E16 keeps FOUR TextState groups (norm/active/sticky/sticky_active ×
    # normal/hilited/clicked — tclass.c TextclassGetTextState) and picks one
    # per WINDOW (borders.c:164: active + EoIsSticky). These dicts are the
    # raw per-state values keyed by the state attribute name ("normal",
    # "normal_active", "normal_sticky", "normal_active_sticky", "hilited",
    # ...); ``fg_for``/``bg_for``/``effect_for``/``font_for`` resolve them
    # through TextclassPopulate's chain (tclass.c:187-204): hilited/clicked →
    # that group's normal; active.normal, sticky.normal AND
    # sticky_active.normal → norm.normal. The scalar fields above stay the
    # legacy first-wins view the SVG backend reads.
    fg_by_state: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    bg_by_state: dict[str, tuple[int, int, int]] = field(default_factory=dict)
    effect_by_state: dict[str, str] = field(default_factory=dict)
    font_by_state: dict[str, str] = field(default_factory=dict)
    # __ORIENTATION (tclass.c:324, per block last-wins): config/definitions
    # FONT_TO_RIGHT 0, DOWN 1 (reads top-to-bottom), UP 2 (bottom-to-top),
    # LEFT 3; undefined tokens (``__UP``) are atoi 0.
    orientation: int = 0

    @staticmethod
    def state_chain(state: str) -> tuple[str, ...]:
        """TextclassPopulate's fallback order for *state* (attribute name)."""
        key = state[2:].lower() if state.startswith("__") else state
        group_normal = {
            "normal": "normal", "hilited": "normal", "clicked": "normal",
            "normal_active": "normal_active", "hilited_active": "normal_active",
            "clicked_active": "normal_active",
            "normal_sticky": "normal_sticky", "hilited_sticky": "normal_sticky",
            "clicked_sticky": "normal_sticky",
            "normal_active_sticky": "normal_active_sticky",
            "hilited_active_sticky": "normal_active_sticky",
            "clicked_active_sticky": "normal_active_sticky",
        }.get(key, "normal")
        chain = [key]
        if group_normal != key:
            chain.append(group_normal)
        if group_normal != "normal":
            chain.append("normal")
        return tuple(chain)

    def _resolve(self, table: dict, state: str):
        for key in self.state_chain(state):
            if key in table:
                return table[key]
        return None

    def fg_for(self, state: str) -> tuple[int, int, int] | None:
        return self._resolve(self.fg_by_state, state)

    def bg_for(self, state: str) -> tuple[int, int, int] | None:
        return self._resolve(self.bg_by_state, state)

    def font_for(self, state: str) -> str | None:
        return self._resolve(self.font_by_state, state)

    def effect_for(self, state: str) -> str:
        """``"none"`` | ``"shadow"`` | ``"outline"`` for *state* (chain)."""
        return _effect_kind(self._resolve(self.effect_by_state, state))

    @property
    def effect_color(self) -> tuple[int, int, int] | None:
        """Single effect color for consumers without per-state text (the SVG
        backend's Aurorae rc): the normal state's ``bg_col``, else active."""
        return self.bg_normal if self.bg_normal is not None else self.bg_active

    @property
    def effect_kind(self) -> str:
        """``"none"`` | ``"shadow"`` | ``"outline"`` from ``effect``.

        Accepts the ``__EFFECT_*`` tokens and E16's numeric encoding
        (``config/definitions``: NONE/NORMAL 0, SHADOW 1, OUTLINE 2). Any
        other token (``__EFFECT_NICE``, ``__NONE``) is what E16's ``atoi``
        makes of an undefined macro: 0, no effect.
        """
        return _effect_kind(self.effect)


def _effect_kind(raw: object) -> str:
    if raw is None:
        return "none"
    token = str(raw).strip().upper()
    if token in ("__EFFECT_SHADOW", "1"):
        return "shadow"
    if token in ("__EFFECT_OUTLINE", "2"):
        return "outline"
    return "none"


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

    ``fill_mode`` is one of ``analyze.wallpaper.FILL_MODES`` — ``stretch``,
    ``tile``, ``tile-h`` (scaled to screen height, tiled across),
    ``tile-v``, ``pad`` (native, centered), ``fit`` (aspect kept) — derived
    from the ``__BACKGROUND_LAYER`` 6-int tuple by
    ``analyze.wallpaper.fill_mode_for_layer``. It becomes the wallpaper
    package's ``X-Themey-FillMode`` (see ``generate/wallpaper.py``), so
    ``apply`` can dispatch on it without re-parsing the E16 source.

    ``solid_rgb`` carries the enclosing block's ``SET_SOLID("r g b")`` — E16
    composites the (often partially transparent) background image over that
    solid, so the generator flattens RGBA sources over it, and for
    ``fit``/``pad`` it is the letterbox color (``X-Themey-SolidColor``). A
    spec with ``path=None`` is solid-only (OPENSTEP declares nothing but
    SET_SOLID); ``name`` is then the ``BEGIN_BACKGROUND`` block name and
    feeds ``stem``.
    """

    path: Path | None  # under asset_root; None for a SET_SOLID-only block
    fill_mode: str  # analyze.wallpaper.FILL_MODES
    solid_rgb: tuple[int, int, int] | None = None  # SET_SOLID underneath
    name: str = ""  # BEGIN_BACKGROUND block name (stem source when path=None)

    @property
    def stem(self) -> str:
        """Package-naming stem: the image's stem, else the block name."""
        if self.path is not None:
            return self.path.stem
        return self.name or "solid"


@dataclass(frozen=True)
class MenuStyleSpec:
    """E16 ``__MENU_STYLE`` — which iclasses dress a menu (menus.c).

    ``bg_iclass`` is what ``MenuRedraw`` paints the menu window with. With
    ``use_item_bg`` (``__USE_ITEM_BACKGROUNDS __ON``, the NeXTSTEP style)
    the window has NO background: every item window wears ``item_iclass``
    (menus.c:928-950, 976-985) and the loader frees any named bg iclass
    (menus.c:1739-1746) — so ``bg_iclass`` is None in that case.
    """

    name: str  # "DEFAULT", "ROOT", "DESK_MENU", ...
    bg_iclass: str | None = None
    item_iclass: str | None = None
    submenu_iclass: str | None = None
    use_item_bg: bool = False
    border: str | None = None
    tclass: str | None = None


@dataclass(frozen=True)
class TooltipSpec:
    """E16 ``__TOOLTIP`` — which iclass/tclass dress a tooltip (tooltips.c).

    ``iclass`` is the tooltip window's own art (guaranteed defined in the
    theme when built by ``build_theme``); ``bubbles`` are the up-to-four
    cloud iclasses E16 drew between pointer and tooltip (positional —
    ``bubbles[i]`` is ``__BUBBLE<i+1>_ICLASS``, an unset middle slot is an
    empty string, trailing unset slots are dropped). ``tclass`` paints the
    text, ``distance`` is the pointer offset in px and ``help_icon`` the
    ``__TOOLTIP_HELP_ICON`` iclass, if any. ``TooltipShow`` looks up
    ``DEFAULT`` for every window/button tooltip; ``ICONBOX``/``PAGER`` dress
    only those two. Only ``iclass``/``tclass`` have a consumer today (the
    Plasma Style tooltip frame and colour group); the rest is carried for
    fidelity reporting.
    """

    name: str  # "DEFAULT", "ICONBOX", "PAGER"
    iclass: str
    tclass: str
    bubbles: tuple[str, ...] = ()
    distance: int = 0
    help_icon: str | None = None


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
    # __MENU_STYLE blocks (menustyles.cfg) keyed by style name.
    menu_styles: dict[str, MenuStyleSpec] = field(default_factory=dict)
    # __TOOLTIP blocks (tooltips.cfg) keyed by tooltip name.
    tooltips: dict[str, TooltipSpec] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)  # ONLY mutable accumulator
    skipped_borders: tuple[str, ...] = ()
