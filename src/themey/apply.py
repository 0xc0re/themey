"""Point the live KWin session at an installed theme (``themey apply``).

Two applies live here:

- :func:`apply` — the original, deco-only path (CLI ``--deco-only``, and
  the only path for ``--backend svg``): writes ``kwinrc``
  ``[org.kde.kdecoration2]`` via ``kwriteconfig6`` and asks KWin to
  reconfigure over D-Bus. Both Aurorae plugins clamp the theme's
  ``BorderLeft/Right/Bottom`` to the System Settings "Border size"
  bracket, so unless ``--border-size`` is given the bracket is chosen from
  the installed ``<name>rc`` (``render.recommended_border_size``).
  ``--legacy-plugin`` selects the v1 QML plugin ``org.kde.kwin.aurorae``
  (which also reads the text-shadow keys) instead of the default ``.v2``.
- :func:`apply_full` — the CLI default: applies the whole installed
  Look-and-Feel bundle (colors, cursors, wallpaper, deco) via
  ``plasma-apply-lookandfeel``, then re-asserts the deco keys explicitly
  (the LnF apply lands in the ``~/.config/kdedefaults/`` layer, which the
  *explicit* kwinrc write in the user layer overrides), then applies the
  default wallpaper's E16 fill mode (:func:`_set_wallpaper_fill` — Plasma's
  Image wallpaper plugin does not read fill-mode from the wallpaper
  package) and — because plasmashell never repaints a scripted fill-mode
  change, and applets compute some KSvg metrics ONCE at load
  (``KickoffSingleton.lineSvg.horLineHeight``, ``listItemMetrics``) so a
  freshly applied Plasma Style keeps the previous theme's separator
  thickness until the shell restarts (verified live 2026-09-01: Kickoff
  drew the previous theme's 6 px rule over StarEnli's 3 px art) — ends
  a tiled apply OR a Plasma Style apply with an automatic plasmashell
  restart (:func:`_restart_plasmashell`, opt-out ``restart_shell=False``
  / CLI ``--no-restart-shell``). Between the colour/icon writes and the
  Plasma Style it also writes the Qt APPLICATION style — kdeglobals
  ``[KDE] widgetStyle``, from the bundle's ``X-Themey-WidgetStyle`` stamp
  (``themey convert --widget-style``) or the ``widget_style`` argument
  that overrides it — plus a ``KGlobalSettings`` StyleChanged broadcast
  (:func:`_notify_style_changed`); no stamp and no argument leaves the
  application style entirely alone.

Both applies share the decoration-writing logic (``_write_deco``) and the
button-order snapshot/restore machinery. Button ORDER is global kwinrc
state (``ButtonsOnLeft/Right``) that no theme file can carry, so an SVG
apply also writes the theme's binning from the installed rc's ``[Themey]``
section — e13 stacks all four buttons on the left; without this the
desktop keeps its previous layout and the theme's buttons appear on the
wrong side. The user's previous layout is recorded once in a
``ThemeyPrevButtons`` marker key (``@unset`` when a key was absent) and
restored by ``themey apply Breeze`` or ``themey apply --revert``;
``keep_buttons=True`` (CLI ``--keep-buttons``) skips button handling
entirely. The QML backend never touches button order or BorderSize — the
theme draws its own.

:func:`apply_full` additionally snapshots, once, the pre-themey global
theme (kdeglobals ``[KDE] LookAndFeelPackage``, marker
``[Themey] PrevLookAndFeelPackage``), the pre-themey deco triple
(kwinrc ``[org.kde.kdecoration2] library|theme|BorderSize``, marker
``ThemeyPrevDeco``) and — when the matching artifacts are installed — the
user-layer color scheme (``PrevColorScheme``), Plasma Style (plasmarc
``[Theme] name``, marker ``PrevPlasmaTheme``) and, when a Qt application
style is going to be written at all, the user-layer kdeglobals ``[KDE]
widgetStyle`` (``PrevWidgetStyle``) — all ``@unset``-sentineled,
all written only once,
so a second ``themey apply`` never clobbers the ORIGINAL baseline with an
already-themey'd one. :func:`revert` (CLI ``themey apply --revert``) reads
those markers back, reapplies the recorded Look-and-Feel package (no
special-casing — a real user's baseline is typically a third-party theme,
not Breeze), restores the deco triple and the button layout, then deletes
both markers. No markers present means no prior full apply on this
machine: a friendly no-op, not an error.

:func:`apply_full` also creates E16's furniture via plasmashell desktop
scripting (:func:`_ensure_furniture`), as selected and sized by
:class:`FurnitureOptions`: TWO vertical content-sized
left-edge panels — a thick pager panel hugging the top-left corner
(E16's pager window spot, hosting themey's OWN ``org.themey.pager``
applet; two panels because pager cell size is panel thickness ÷
desktop-grid columns while task-icon size IS the panel thickness, so one
shared panel cannot serve both) and a slim iconbox panel hugging the
bottom-left whose icons-only task manager shows only MINIMIZED windows,
E16's iconbox behavior — plus E16's DRAGBAR: a full-width top panel
``scale_px(16)`` px thick (the bundle's ``X-Themey-Scale``; floor 24 px)
carrying ``org.themey.deskbutton`` next/prev ends around the tray and
clock. The top edge is E16's dragbar alone, so
:func:`_park_top_panels` first moves every pre-existing top panel to a
nonexistent screen index (config kept, never shown — verified live
2026-09-01) and records ``id=screen:location:hiding`` once in
``[Themey] PrevTopPanels``; :func:`revert` puts them back. The
``[Themey] PagerPanel``/``IconboxPanel``/``DragbarPanel`` markers are the
ones that are NOT ``Prev*`` baselines: each records a themey-CREATED
artifact (that panel's containment id), so it is overwritten when the
recorded panel no longer exists (recreate), left alone when it does
(idempotent second apply) — a pager panel still hosting the STOCK pager
counts as stale and is recreated — and deleted when :func:`revert`
removes the panel. Existing panels are never touched beyond the
fit-content step and the parking. The applet packages the ENABLED panels
host must be installed (any ``themey convert`` installs them; apply
refuses otherwise and warns
when their ``X-Themey-Runtime`` is behind). The desktop grid is set to one
column (kwinrc ``[Desktops] Rows = Number`` plus the live D-Bus rows —
:func:`_set_desktop_grid_column`) so the stacked pager cells fill the
panel box; ``PrevDesktopRows`` is the record-once baseline and
:func:`revert` restores it, since this changes desktop-switching
direction.

The panels are E16-sized, from the 1.0.31 source: the pager's cells are
48 px tall (``pager.c:788-796``) and the panel is ONE aspect-true cell
thick (:func:`pager_thickness_px` over the live
:func:`_read_screen_aspect` — 85 px on 16:9), the iconbox is E16's
``iconsize = 48`` (``container.c:103``). Both are re-asserted on every
apply, so the 130/60 px panels earlier applies created shrink without a
revert. Both also default to plasmashell's WindowsGoBelow visibility
(E16's default maximize was ``MAX_AVAILABLE``, which stepped around the
pager rather than shrinking every window for it): the scripting engine
has no string for that mode, so the creation/re-assert scripts leave
``hiding`` alone and :func:`_write_furniture_visibility` writes
``plasmashellrc [PlasmaViews][Panel <id>] panelVisibility = 3`` AFTER
every script that touches a panel's ``hiding`` — the furniture ones and
the dragbar-opt-out unparking alike, since plasmashell flushes a scripted
``hiding`` lazily and would rewrite the file over an earlier write. That mode is only read at
plasmashell start-up, so an apply that does not end in a restart warns.
``FurnitureOptions.strut`` puts the panels back to NormalPanel and the
scripted ``hiding = 'none'``.

Any of the three panels can be left out (:class:`FurnitureOptions`, CLI
``--no-pager``/``--no-iconbox``/``--no-dragbar``): an already-created one
is removed and its marker cleared (:func:`_remove_furniture`, shared with
:func:`revert`), and the step that exists only for it is skipped and its
baseline restored — the stacked desktop grid for the pager
(:func:`_undo_desktop_grid_column`), the top-panel parking for the
dragbar (:func:`_undo_top_panel_parking`).

Legacy revert path: ``themey apply Breeze`` (which selects
``org.kde.breeze``, restores the recorded button layout) or System
Settings → Window Decorations. That path is untouched by the above.
"""
from __future__ import annotations

import configparser
import json
import logging
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from . import paths
from .generate import plasmoids
from .generate.lookandfeel import WIDGET_STYLES
from .generate.qmldeco.resolver import scale_px
from .install import clear_style_cache
from .kwin import BORDER_SIZES, PLUGINS, recommended_border_size
from .slug import plugin_id

log = logging.getLogger(__name__)

GROUP = "org.kde.kdecoration2"

#: kdeglobals file name and the vanilla group Plasma itself writes/reads
#: the active Look-and-Feel package to/from.
_KDEGLOBALS = "kdeglobals"
_KDE_GROUP = "KDE"
_LOOKANDFEEL_PACKAGE_KEY = "LookAndFeelPackage"
_GENERAL_GROUP = "General"
_COLORSCHEME_KEY = "ColorScheme"
#: kdeglobals group/key of the active icon theme.
_ICONS_GROUP = "Icons"
_ICON_THEME_KEY = "Theme"
#: kdeglobals key of the active Qt application (widget) style, in the
#: ``[KDE]`` group — the same key KDE's own Look-and-Feel bundles set.
_WIDGET_STYLE_KEY = "widgetStyle"
#: themey's own kdeglobals group for its one marker key.
_THEMEY_GROUP = "Themey"
#: Vanilla plasmarc location of the active Plasma Style (desktop theme).
_PLASMARC = "plasmarc"
_PLASMA_THEME_GROUP = "Theme"
_PLASMA_NAME_KEY = "name"
#: Plasma Style to bounce through when the themey style is already the
#: current one (Breeze's package id, present on every install).
_STYLE_BOUNCE = "default"

#: themey fill mode (``X-Themey-FillMode``, ``analyze.wallpaper.FILL_MODES``)
#: -> the ``plasma-apply-wallpaperimage -f`` token. Only the camelCase QML
#: names stretch/preserveAspectFit/preserveAspectCrop/pad are accepted on
#: Plasma 6.6.6 (verified live 2026-08-31: every spelling of tile is
#: "Invalid fill mode"), so the three tile modes are absent here and go
#: through :data:`_WALLPAPER_FILL_MODE_INTS` instead.
_WALLPAPER_FILL_MODE_TOKENS: dict[str, str] = {
    "stretch": "stretch",
    "fit": "preserveAspectFit",
    "pad": "pad",
}
#: themey fill mode -> the QML ``Image.fillMode`` enum int Plasma's Image
#: wallpaper plugin stores as ``FillMode`` (Qt: Stretch=0,
#: PreserveAspectFit=1, PreserveAspectCrop=2, Tile=3, TileVertically=4,
#: TileHorizontally=5, Pad=6). ``tile-h`` is E16's "scaled to screen
#: height, repeated across" = Qt's TileHorizontally ("stretched vertically
#: and tiled horizontally"); ``tile-v`` the transpose. Written through
#: plasmashell's scripting D-Bus — the same mechanism the tool itself uses
#: internally — for the modes the tool cannot express.
_WALLPAPER_FILL_MODE_INTS: dict[str, int] = {
    "tile": 3,
    "tile-v": 4,
    "tile-h": 5,
}
#: Pre-vocabulary packages (converted before the six-mode fill vocabulary)
#: carry these two values; read them as their nearest modern mode so an
#: old install still applies.
_LEGACY_FILL_MODES: dict[str, str] = {"tiled": "tile", "scaled": "stretch"}


class ApplyError(Exception):
    pass


def _which(*names: str) -> str:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    raise ApplyError(f"none of {names} found on PATH")


def _cfg_write(kw: str, file: str, group: str, key: str, value: str) -> None:
    _run_checked(
        [kw, "--file", file, "--group", group, "--key", key, value],
        f"writing {file} [{group}] {key}",
    )


def _cfg_delete(kw: str, file: str, group: str, key: str) -> None:
    _run_checked(
        [kw, "--file", file, "--group", group, "--key", key, "--delete"],
        f"deleting {file} [{group}] {key}",
    )


def _cfg_read(kr: str, file: str, group: str, key: str) -> str | None:
    """Current value of ``file``'s ``[group] key``, or None when unset.

    ``kreadconfig6`` prints an empty line for an unset key, which conflates
    "absent" with "explicitly empty". Every caller here accepts that: an
    empty read is treated as unset (e.g. the button/deco/LnF snapshots are
    recorded as ``@unset`` and restored as a key deletion rather than an
    empty value).
    """
    out = subprocess.run(
        [kr, "--file", file, "--group", group, "--key", key],
        capture_output=True,
        text=True,
        env=paths.subprocess_env(),
    )
    v = (out.stdout or "").rstrip("\n")
    return v if v else None


def _kwrite(kw: str, key: str, value: str) -> None:
    _cfg_write(kw, "kwinrc", GROUP, key, value)


def _kdelete(kw: str, key: str) -> None:
    _cfg_delete(kw, "kwinrc", GROUP, key)


def _kread(kr: str, key: str) -> str | None:
    return _cfg_read(kr, "kwinrc", GROUP, key)


def border_size_for_installed(theme_dir: Path, name: str) -> str | None:
    """Recommended BorderSize from ``<name>rc`` [Layout], or None if unreadable."""
    rc = theme_dir / f"{name}rc"
    if not rc.is_file():
        return None
    cp = configparser.RawConfigParser()
    cp.optionxform = staticmethod(str)  # type: ignore[assignment]
    try:
        cp.read(rc, encoding="utf-8")
        layout = cp["Layout"]
        return recommended_border_size(
            int(layout.get("BorderLeft", "0")),
            int(layout.get("BorderRight", "0")),
            int(layout.get("BorderBottom", "0")),
        )
    except (KeyError, ValueError, configparser.Error):
        return None


_PREV_BUTTONS_KEY = "ThemeyPrevButtons"
_UNSET = "@unset"


def buttons_for_installed(theme_dir: Path, name: str) -> tuple[str, str] | None:
    """(LeftButtons, RightButtons) from the installed rc's [Themey] section.

    None when the rc has no such section — themes converted before button
    binning was persisted, or a non-themey Aurorae theme.
    """
    rc = theme_dir / f"{name}rc"
    if not rc.is_file():
        return None
    cp = configparser.RawConfigParser()
    cp.optionxform = staticmethod(str)  # type: ignore[assignment]
    try:
        cp.read(rc, encoding="utf-8")
        sec = cp["Themey"]
        return (sec.get("LeftButtons", ""), sec.get("RightButtons", ""))
    except (KeyError, configparser.Error):
        return None


def _apply_theme_buttons(kw: str, kr: str, left: str, right: str) -> None:
    """Write the theme's button layout, snapshotting the original once."""
    if _kread(kr, _PREV_BUTTONS_KEY) is None:
        prev_l = _kread(kr, "ButtonsOnLeft") or _UNSET
        prev_r = _kread(kr, "ButtonsOnRight") or _UNSET
        _kwrite(kw, _PREV_BUTTONS_KEY, f"{prev_l}|{prev_r}")
    _kwrite(kw, "ButtonsOnLeft", left)
    _kwrite(kw, "ButtonsOnRight", right)


def _restore_buttons(kw: str, kr: str) -> None:
    """Put the snapshotted pre-themey button layout back (Breeze revert)."""
    marker = _kread(kr, _PREV_BUTTONS_KEY)
    if marker is None or "|" not in marker:
        return
    prev_l, prev_r = marker.split("|", 1)
    for key, prev in (("ButtonsOnLeft", prev_l), ("ButtonsOnRight", prev_r)):
        if prev == _UNSET:
            _kdelete(kw, key)
        else:
            _kwrite(kw, key, prev)
    _kdelete(kw, _PREV_BUTTONS_KEY)


_PREV_LNF_KEY = "PrevLookAndFeelPackage"
_PREV_DECO_KEY = "ThemeyPrevDeco"
_PREV_COLORS_KEY = "PrevColorScheme"
_PREV_PLASMA_KEY = "PrevPlasmaTheme"
_PREV_ICONS_KEY = "PrevIconTheme"
_PREV_WIDGET_STYLE_KEY = "PrevWidgetStyle"
_PREV_PANELS_KEY = "PrevPanelLengthModes"
_PREV_FLOATING_KEY = "PrevPanelFloating"

# The iconbox marker is NOT a Prev* baseline: it records a themey-CREATED
# artifact (the dedicated iconbox panel's containment id), so it is
# overwritten whenever the recorded panel no longer exists and deleted when
# revert removes the panel.
#: E16 furniture: themey-created panels on the LEFT screen edge. On a
#: vertical panel plasmashell's 'left' alignment means TOP and 'right'
#: means BOTTOM — the pager panel hugs the top-left corner exactly where
#: E16 kept its pager window, the iconbox the bottom-left where E16 kept
#: its iconbox. Two panels, not one: pager cell size is panel thickness ÷
#: desktop-grid columns while task-icon size IS the panel thickness, so a
#: shared panel cannot give the pager readable cells without ballooning
#: the icons (verified live 2026-08-31 — a shared 60px panel shrank the
#: pager cells to ~26px slivers).
_ICONBOX_KEY = "IconboxPanel"
_ICONBOX_WIDGET = "org.kde.plasma.icontasks"
#: E16's own iconbox size: ``iconsize = 48`` (container.c:103-106). The
#: panel thickness IS the task-icon size, so this is the whole spec.
_ICONBOX_HEIGHT = 48
_PAGER_KEY = "PagerPanel"
#: themey's own pager applet (``generate/plasmoids``): E16's LIVE pager
#: replayed. A recorded pager panel still hosting the STOCK
#: ``org.kde.plasma.pager`` (pre-2026-09-01 applies) is 'stale' — removed
#: and recreated (:func:`_ensure_furniture`).
_PAGER_WIDGET = plasmoids.PAGER_ID
#: E16's own first-run pager size (pager.c:788-796): ``h = 48 * ay``,
#: ``w = 48 * screenW/screenH * ax`` — 48 px CELLS, the panel thickness
#: derived from them and the screen aspect
#: (:func:`pager_thickness_px`), not a fixed panel width. The 130 px
#: panel earlier applies created stole a fifth of a 1080p screen from
#: every maximized window.
_PAGER_CELL_PX = 48
#: Screen aspect assumed when plasmashell cannot answer
#: :func:`_read_screen_aspect` — today's overwhelmingly common one.
_DEFAULT_SCREEN_ASPECT = 16 / 9
#: E16's desktop dragbar (desktops.c:95-346): a strip along the top of
#: every desktop, ``dragbar_width`` (16) px thick — RAISEBUTTON ("desk
#: next") at the start, the DRAGBUTTON strip across, LOWERBUTTON ("desk
#: prev") at the end. themey recreates it as a full-width top panel of
#: ``scale_px(16, scale)`` px (the conversion's ``X-Themey-Scale``; the
#: ``north-`` Plasma Style set dresses it), floored at ``_DRAGBAR_MIN_PX``
#: so the tray icons stay usable at scale 1, hosting the two
#: ``org.themey.deskbutton`` ends around the tray and clock that the
#: parked top panel used to carry.
_DRAGBAR_KEY = "DragbarPanel"
_DRAGBAR_WIDGET = plasmoids.DESKBUTTON_ID
_DRAGBAR_THICKNESS_REF = 16
_DRAGBAR_MIN_PX = 24
#: Widgets re-homed into the dragbar between the two desk buttons.
_DRAGBAR_MIDDLE_WIDGETS: tuple[str, ...] = (
    "org.kde.plasma.panelspacer",
    "org.kde.plasma.systemtray",
    "org.kde.plasma.digitalclock",
)
#: Baseline for the parked pre-themey TOP panels (record-once):
#: ``id=<screen>:<location>:<hiding>|...``. A parked panel is moved to a
#: screen index that does not exist (``screenCount``) — plasmashell keeps
#: its config and never shows it while no such screen exists (the
#: mechanism behind KDE bug 512005; verified live 2026-09-01: assigning
#: a nonexistent screen leaves ``p.screen == -1``, assigning the old
#: index back re-attaches it). Fallback when the assignment does not
#: take: right edge + autohide.
_PREV_TOP_PANELS_KEY = "PrevTopPanels"
_PANEL_LOCATIONS = frozenset({"top", "bottom", "left", "right"})
#: Conversion scale assumed for a bundle without an ``X-Themey-Scale``
#: stamp (bundles written before the stamp existed) — the pipeline's
#: default ``scale``.
_DEFAULT_THEME_SCALE = 2.0
#: Baseline for the desktop-grid change (kwinrc [Desktops] Rows): one
#: desktop per pager row so the stacked cells fill the panel box.
_PREV_ROWS_KEY = "PrevDesktopRows"
_DESKTOPS_GROUP = "Desktops"

#: plasmashell's own panel-visibility config (``PanelView::VisibilityMode``
#: in ``shell/panelview.h``): NormalPanel 0, AutoHide 1, DodgeWindows 2,
#: WindowsGoBelow 3. It is written into ``plasmashellrc``
#: ``[PlasmaViews][Panel <id>] panelVisibility`` because the SCRIPTING
#: engine has no string for WindowsGoBelow — every spelling
#: (``windowsgobelow``/``windowsbelow``/``WindowsGoBelow``/``windowscover``)
#: reads back ``'none'`` on Plasma 6.6.6 and the binary carries no
#: lowercase token for that enum member (verified live 2026-09-01). The
#: written value SURVIVES a plasmashell restart and is in force
#: afterwards — the spike measured KWin's MaximizeArea moving from x=130
#: to x=60 only AFTER ``systemctl --user restart plasma-plasmashell``.
#: Whether the write takes effect without that restart is untested, so
#: the mode is treated as landing at the next plasmashell start
#: (:func:`_write_furniture_visibility`).
_PLASMASHELLRC = "plasmashellrc"
_PLASMA_VIEWS_GROUP = "PlasmaViews"
_PANEL_VISIBILITY_KEY = "panelVisibility"
_VISIBILITY_NORMAL = 0
_VISIBILITY_WINDOWS_GO_BELOW = 3


@dataclass(frozen=True)
class FurnitureOptions:
    """Which E16 furniture panels ``apply_full`` builds, and how big.

    The defaults are E16 1.0.31's own: a 48 px pager cell
    (:data:`_PAGER_CELL_PX`), a 48 px iconbox (:data:`_ICONBOX_HEIGHT`),
    all three panels on. *strut* is off by default — E16's default
    maximize was ``MAX_AVAILABLE`` (mod-misc.c:160), which stepped around
    the pager instead of shrinking every window for it, so themey's
    left-edge panels let windows go below them; ``strut=True`` keeps them
    reserving screen space like an ordinary Plasma panel.
    """

    pager: bool = True
    iconbox: bool = True
    dragbar: bool = True
    strut: bool = False
    pager_cell_px: int = _PAGER_CELL_PX
    iconbox_px: int = _ICONBOX_HEIGHT

    def __post_init__(self) -> None:
        for field, value in (
            ("pager_cell_px", self.pager_cell_px),
            ("iconbox_px", self.iconbox_px),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                raise ApplyError(f"{field} must be a positive number of pixels")

    def enabled(self, key: str) -> bool:
        """Whether the panel behind the marker *key* is wanted."""
        return {
            _PAGER_KEY: self.pager,
            _ICONBOX_KEY: self.iconbox,
            _DRAGBAR_KEY: self.dragbar,
        }[key]


#: The default furniture selection and sizes, as a module-level singleton
#: so the frozen dataclass can safely be an argument default (ruff B008).
DEFAULT_FURNITURE = FurnitureOptions()


def _is_panel_id(value: str) -> bool:
    """True when *value* is safe to interpolate into a plasmashell script.

    ``str.isdigit()`` alone accepts non-ASCII digit-property characters
    ("³01"), which carry no injection risk but would throw inside the
    script — and a thrown removal script must not read as success.
    """
    return value.isascii() and value.isdigit()


def _record_prev_lookandfeel(kw: str, kr: str) -> None:
    """Snapshot kdeglobals ``[KDE] LookAndFeelPackage`` once, before the
    first ``apply_full`` overwrites it — the revert baseline."""
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_LNF_KEY) is not None:
        return
    prev = _cfg_read(kr, _KDEGLOBALS, _KDE_GROUP, _LOOKANDFEEL_PACKAGE_KEY) or _UNSET
    _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_LNF_KEY, prev)


def _record_prev_colorscheme(kw: str, kr: str) -> None:
    """Snapshot the user-layer kdeglobals ``[General] ColorScheme`` once,
    before the first ``apply_full`` overwrites it via
    ``plasma-apply-colorscheme`` — the color half of the revert baseline.

    Needed because ``plasma-apply-lookandfeel -a`` does NOT apply the
    bundle's color scheme past an explicit user-layer ``ColorScheme``
    (verified live on Plasma 6.6.6, 2026-08-31: it updated kcminputrc's
    cursor theme but left both the user layer and even
    ``~/.config/kdedefaults/kdeglobals`` on the old scheme), so
    ``apply_full`` must write the user layer itself — and therefore must
    record what it is about to overwrite."""
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_COLORS_KEY) is not None:
        return
    prev = _cfg_read(kr, _KDEGLOBALS, _GENERAL_GROUP, _COLORSCHEME_KEY) or _UNSET
    _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_COLORS_KEY, prev)


def _record_prev_icontheme(kw: str, kr: str) -> None:
    """Snapshot the user-layer kdeglobals ``[Icons] Theme`` once, before
    the first ``apply_full`` overwrites it — same user-layer shadowing as
    the color scheme: the reference machine's kdeglobals carries an
    explicit ``Theme=Fluency`` a Look-and-Feel apply would not displace,
    so ``apply_full`` writes the key itself and must record what it is
    about to overwrite."""
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ICONS_KEY) is not None:
        return
    prev = _cfg_read(kr, _KDEGLOBALS, _ICONS_GROUP, _ICON_THEME_KEY) or _UNSET
    _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ICONS_KEY, prev)


def _notify_icons_changed() -> None:
    """Broadcast KIconLoader's ``iconChanged(0)`` so running apps reload
    their icons — KF6 has no icon disk cache to clear. A failure is a
    warning: the theme is applied, only the live refresh is missing."""
    dbus_send = shutil.which("dbus-send")
    if dbus_send is None:
        log.warning("dbus-send not found — running apps show the new icons after a relogin")
        return
    try:
        _run_checked(
            [
                dbus_send, "--session", "--type=signal", "/KIconLoader",
                "org.kde.KIconLoader.iconChanged", "int32:0",
            ],
            "KIconLoader iconChanged broadcast",
        )
    except ApplyError as exc:
        log.warning(
            "could not broadcast the icon change (%s) — running apps show the "
            "new icons after a relogin", exc,
        )


def _record_prev_widget_style(kw: str, kr: str) -> None:
    """Snapshot the user-layer kdeglobals ``[KDE] widgetStyle`` once,
    before the first ``apply_full`` that has a style to write overwrites
    it — the application-style half of the revert baseline.

    Recorded only when a style will actually be written (the bundle was
    converted with ``--widget-style``, or one was given on the command
    line), exactly like :func:`_record_prev_colorscheme`: an apply that
    leaves the application style alone must leave no marker for
    :func:`revert` to act on.

    Same user-layer shadowing as the color scheme and icon theme: the
    bundle's own ``[kdeglobals][KDE]`` group lands in
    ``~/.config/kdedefaults/``, which an explicit user-layer
    ``widgetStyle`` would shadow — so ``apply_full`` writes the user layer
    itself and must record what it is about to overwrite."""
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_WIDGET_STYLE_KEY) is not None:
        return
    prev = _cfg_read(kr, _KDEGLOBALS, _KDE_GROUP, _WIDGET_STYLE_KEY) or _UNSET
    _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_WIDGET_STYLE_KEY, prev)


def _notify_style_changed() -> None:
    """Broadcast KGlobalSettings' ``StyleChanged`` (change type 2) so
    running Qt apps re-read ``widgetStyle`` instead of waiting for a
    relogin. A failure is a warning, not a failed apply: the style is
    written, only the live refresh is missing — same contract as
    :func:`_notify_icons_changed`."""
    dbus_send = shutil.which("dbus-send")
    if dbus_send is None:
        log.warning(
            "dbus-send not found — running apps show the new application "
            "style after a relogin"
        )
        return
    try:
        _run_checked(
            [
                dbus_send, "--session", "--type=signal", "/KGlobalSettings",
                "org.kde.KGlobalSettings.notifyChange", "int32:2", "int32:0",
            ],
            "KGlobalSettings StyleChanged broadcast",
        )
    except ApplyError as exc:
        log.warning(
            "could not broadcast the application-style change (%s) — running "
            "apps show the new style after a relogin", exc,
        )


def _record_prev_plasmatheme(kw: str, kr: str) -> None:
    """Snapshot the user-layer plasmarc ``[Theme] name`` once, before the
    first ``apply_full`` overwrites it via ``plasma-apply-desktoptheme`` —
    the Plasma Style half of the revert baseline.

    Same layer-shadowing reason as :func:`_record_prev_colorscheme`: the
    reference machine's plasmarc carries an explicit ``name=Otto``, which a
    Look-and-Feel apply would not displace — so ``apply_full`` calls
    ``plasma-apply-desktoptheme`` explicitly and must record what it is
    about to overwrite."""
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PLASMA_KEY) is not None:
        return
    prev = _cfg_read(kr, _PLASMARC, _PLASMA_THEME_GROUP, _PLASMA_NAME_KEY) or _UNSET
    _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PLASMA_KEY, prev)


def _evaluate_plasma_script(script: str, what: str) -> str:
    """Run *script* through plasmashell's scripting D-Bus; returns stdout.

    Same typed-failure shape as :func:`_run_checked` — plasmashell absent
    or the script erroring surfaces as an :class:`ApplyError`.
    """
    proc = subprocess.run(
        [
            _which_qdbus(),
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            script,
        ],
        capture_output=True,
        text=True,
        env=paths.subprocess_env(),
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-500:]
        raise ApplyError(f"{what} failed (exit {proc.returncode}): {tail}")
    return (proc.stdout or "").strip()


def _read_screen_aspect() -> float:
    """The primary screen's width/height, or :data:`_DEFAULT_SCREEN_ASPECT`.

    E16 sized its pager from the screen shape (``w = 48 * screenW/screenH``,
    pager.c:788-796), so the pager panel's thickness needs the live
    geometry. Everything can go wrong here without hurting the apply — no
    plasmashell, a scripting engine that answers something else — so both
    a failed script and an unparsable reply fall back to 16:9 with a
    warning rather than raising.
    """
    try:
        out = _evaluate_plasma_script(
            "var g = screenGeometry(0); print(g.width + 'x' + g.height);",
            "plasmashell screen-geometry read script",
        )
    except ApplyError as exc:
        log.warning(
            "could not read the screen geometry (%s) — sizing the pager "
            "panel for a 16:9 screen", exc,
        )
        return _DEFAULT_SCREEN_ASPECT
    width, _, height = out.partition("x")
    if (
        width.isascii() and width.isdigit()
        and height.isascii() and height.isdigit()
        and int(width) > 0 and int(height) > 0
    ):
        return int(width) / int(height)
    log.warning(
        "could not parse the screen geometry (%r) — sizing the pager "
        "panel for a 16:9 screen", out,
    )
    return _DEFAULT_SCREEN_ASPECT


def _read_panel_length_modes() -> dict[str, str]:
    """``{panel_id: lengthMode}`` for every plasmashell panel."""
    out = _evaluate_plasma_script(
        "var out = [];"
        "for (const p of panels()) { out.push(p.id + '=' + p.lengthMode); }"
        "print(out.join('|'));",
        "plasmashell panel-length read script",
    )
    modes: dict[str, str] = {}
    for pair in out.split("|"):
        if "=" in pair:
            pid, mode = pair.split("=", 1)
            if pid.strip().isdigit() and mode.strip():
                modes[pid.strip()] = mode.strip()
    return modes


def _read_panel_floating() -> dict[str, str]:
    """``{panel_id: 'true'|'false'}`` for every plasmashell panel.

    ``p.floating`` is read inside try/catch like the creation script sets
    it: a plasmashell without the property must not kill the whole read.
    """
    out = _evaluate_plasma_script(
        "var out = [];"
        "for (const p of panels()) {"
        " var f = false; try { f = p.floating; } catch (e) {}"
        " out.push(p.id + '=' + f); }"
        "print(out.join('|'));",
        "plasmashell panel floating read script",
    )
    floating: dict[str, str] = {}
    for pair in out.split("|"):
        if "=" in pair:
            pid, value = pair.split("=", 1)
            if pid.strip().isdigit() and value.strip() in ("true", "false"):
                floating[pid.strip()] = value.strip()
    return floating


def _set_panels_fit(kw: str, kr: str) -> None:
    """Set every panel's length mode to ``fit`` (content-sized) and
    ``floating`` off (docked), the E16 iconbox/dragbar feel, snapshotting
    the previous modes once.

    E16 bars are docked strips — a floating panel adds an 8 px transparent
    halo that rounds the E16 look away. The markers mirror the other
    ``[Themey]`` baselines: written only on the first themey apply
    (``id=mode`` / ``id=true|false`` pairs joined by ``|``), restored and
    cleared by :func:`revert`. No panels (plasmashell not running is
    caught earlier by the read script) means nothing to do.
    """
    modes = _read_panel_length_modes()
    if not modes:
        return
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PANELS_KEY) is None:
        marker = "|".join(f"{pid}={mode}" for pid, mode in sorted(modes.items()))
        _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PANELS_KEY, marker)
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_FLOATING_KEY) is None:
        floating = _read_panel_floating()
        if floating:
            marker = "|".join(
                f"{pid}={value}" for pid, value in sorted(floating.items())
            )
            _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_FLOATING_KEY, marker)
    _evaluate_plasma_script(
        "for (const p of panels()) {"
        " p.lengthMode = 'fit';"
        " try { p.floating = false; } catch (e) {}"
        " }",
        "plasmashell panel fit-content script",
    )


def _restore_panel_length_modes(kw: str, marker: str) -> None:
    """Put the recorded per-panel length modes back (revert path)."""
    entries = [
        pair.split("=", 1) for pair in marker.split("|") if "=" in pair
    ]
    valid = {
        pid: mode
        for pid, mode in entries
        if pid.isdigit() and mode in ("fill", "fit", "custom")
    }
    if not valid:
        return
    assignments = "".join(
        f"if (p.id == {pid}) {{ p.lengthMode = '{mode}'; }}"
        for pid, mode in sorted(valid.items())
    )
    _evaluate_plasma_script(
        f"for (const p of panels()) {{ {assignments} }}",
        "plasmashell panel length-mode restore script",
    )


def _restore_panel_floating(kw: str, marker: str) -> None:
    """Put the recorded per-panel floating states back (revert path)."""
    entries = [
        pair.split("=", 1) for pair in marker.split("|") if "=" in pair
    ]
    valid = {
        pid: value
        for pid, value in entries
        if pid.isdigit() and value in ("true", "false")
    }
    if not valid:
        return
    assignments = "".join(
        f"if (p.id == {pid}) {{ try {{ p.floating = {value}; }} catch (e) {{}} }}"
        for pid, value in sorted(valid.items())
    )
    _evaluate_plasma_script(
        f"for (const p of panels()) {{ {assignments} }}",
        "plasmashell panel floating restore script",
    )


def _panel_script(
    alignment: str,
    height: int,
    widgets: str,
    *,
    location: str = "left",
    length_mode: str = "fit",
    visibility: int = _VISIBILITY_NORMAL,
) -> str:
    """Creation script for one furniture panel; prints the new panel id.

    ``qdbus`` exits 0 even when the script throws, so the printed id is
    the real success signal. ``p.floating`` is wrapped in try/catch: an
    unscriptable property assignment would otherwise kill the whole
    script. ``length_mode='fill'`` (the dragbar) spans the screen edge
    like E16's strip; ``'fit'`` (pager/iconbox) is content-sized.

    ``hiding`` is written ONLY for a normal (strut-bearing) panel: a
    windows-go-below panel has no scripting spelling at all
    (:data:`_VISIBILITY_WINDOWS_GO_BELOW`), and a scripted
    ``p.hiding = 'none'`` would be flushed to plasmashellrc after the
    ``panelVisibility`` write that sets the mode and undo it.
    """
    return (
        "var p = new Panel;"
        f" p.location = '{location}';"
        f" p.alignment = '{alignment}';"
        f" p.height = {height};"
        + (" p.hiding = 'none';" if visibility == _VISIBILITY_NORMAL else "")
        + f" p.lengthMode = '{length_mode}';"
        # A scripted `new Panel` starts with minimumLength == maximumLength
        # == the full screen dimension, and setting lengthMode='fit' does
        # NOT clear them — the panel then draws as a full-height column
        # around a few px of content (verified live 2026-08-31). Only the
        # minimum needs clearing; fit computes the real length.
        + (" p.minimumLength = 0;" if length_mode == "fit" else "")
        + " try { p.floating = false; } catch (e) {}"
        f"{widgets}"
        " print(p.id);"
    )


def dragbar_thickness_px(scale: float) -> int:
    """Dragbar panel thickness: E16's 16 ref px at the conversion scale,
    floored at ``_DRAGBAR_MIN_PX``."""
    return max(scale_px(_DRAGBAR_THICKNESS_REF, scale), _DRAGBAR_MIN_PX)


def pager_thickness_px(cell_px: int, screen_aspect: float) -> int:
    """Pager panel thickness for *cell_px*-tall cells on a *screen_aspect*
    screen — E16's own ``w = 48 * screenW/screenH`` (pager.c:788-796).

    The panel is one cell wide (the desktops are stacked one per row, see
    :func:`_set_desktop_grid_column`), so its thickness is the width of a
    single aspect-true mini: 85 px for E16's 48 px cell on 16:9.
    """
    return max(1, round(cell_px * screen_aspect))


@dataclass(frozen=True)
class FurnitureSpec:
    """One themey-created panel: marker key, human name, creation script,
    thickness, length mode, plasmashell visibility mode, and the widget
    its recorded panel MUST host to count as alive (None = any live panel
    counts)."""

    key: str
    name: str
    script: str
    height: int
    length_mode: str = "fit"
    required_widget: str | None = None
    visibility: int = _VISIBILITY_NORMAL


def _furniture_specs(
    *,
    scale: float = _DEFAULT_THEME_SCALE,
    tasks_hover: bool = True,
    furniture: FurnitureOptions = DEFAULT_FURNITURE,
    screen_aspect: float = _DEFAULT_SCREEN_ASPECT,
) -> tuple[FurnitureSpec, ...]:
    """The themey panels, in creation order.

    Pager panel: top-left, thick, themey's own pager — E16's pager window
    spot. Iconbox panel: bottom-left, slim, an icons-only task manager
    showing ONLY minimized windows — E16's iconbox: icons appear on
    iconify, vanish on restore. ``launchers`` is cleared because icontasks
    ships default pinned launchers; ``taskHoverEffect`` follows the Plasma
    Style's ``X-Themey-TasksHover`` (*tasks_hover*: whether the style
    ships hilited iconbox art). Dragbar panel: E16's top strip
    (``_DRAGBAR_KEY``) — full width, ``dragbar_thickness_px(scale)``
    thick, desk-next button, spacer, tray, clock, desk-prev button (E16's
    default ordering: RAISE at the start, LOWER at the end). Created LAST
    so it comes after :func:`_park_top_panels` and is never parked.

    ALL three specs are returned whatever *furniture* says — :func:`revert`
    enumerates them to find its markers, and :func:`_ensure_furniture`
    filters. *furniture* only shapes the panels: their sizes and, for the
    two left-edge ones, whether they reserve screen space
    (:data:`_VISIBILITY_WINDOWS_GO_BELOW` unless ``strut``; the dragbar is
    E16's own top strip and always keeps its strut).
    """
    side_visibility = (
        _VISIBILITY_NORMAL if furniture.strut else _VISIBILITY_WINDOWS_GO_BELOW
    )
    pager_px = pager_thickness_px(furniture.pager_cell_px, screen_aspect)
    pager = _panel_script(
        "left",
        pager_px,
        f" var w = p.addWidget('{_PAGER_WIDGET}');"
        # Multi-head virtual desktops are ultrawide (two 16:9 screens =
        # 3.55:1) and squash the cells to slivers; per-screen cells keep
        # desktop aspect readable (verified live 2026-08-31).
        " w.currentConfigGroup = ['General'];"
        " w.writeConfig('showOnlyCurrentScreen', true);"
        " w.reloadConfig();",
        visibility=side_visibility,
    )
    hover = "true" if tasks_hover else "false"
    iconbox = _panel_script(
        "right",
        furniture.iconbox_px,
        f" var w = p.addWidget('{_ICONBOX_WIDGET}');"
        " w.currentConfigGroup = ['General'];"
        " w.writeConfig('showOnlyMinimized', true);"
        " w.writeConfig('launchers', '');"
        f" w.writeConfig('taskHoverEffect', {hover});"
        " w.reloadConfig();",
        visibility=side_visibility,
    )
    dragbar_px = dragbar_thickness_px(scale)
    middle = "".join(f" p.addWidget('{w}');" for w in _DRAGBAR_MIDDLE_WIDGETS)
    dragbar = _panel_script(
        "left",
        dragbar_px,
        f" var w = p.addWidget('{_DRAGBAR_WIDGET}');"
        " w.currentConfigGroup = ['General'];"
        " w.writeConfig('direction', 'next');"
        " w.reloadConfig();"
        f"{middle}"
        f" var w2 = p.addWidget('{_DRAGBAR_WIDGET}');"
        " w2.currentConfigGroup = ['General'];"
        " w2.writeConfig('direction', 'prev');"
        " w2.reloadConfig();",
        location="top",
        length_mode="fill",
    )
    return (
        FurnitureSpec(_PAGER_KEY, "pager panel", pager, pager_px,
                      required_widget=_PAGER_WIDGET,
                      visibility=side_visibility),
        FurnitureSpec(_ICONBOX_KEY, "iconbox panel", iconbox,
                      furniture.iconbox_px, visibility=side_visibility),
        FurnitureSpec(_DRAGBAR_KEY, "dragbar panel", dragbar, dragbar_px,
                      length_mode="fill"),
    )


def _furniture_reassert_script(
    panel_id: str,
    height: int,
    length_mode: str = "fit",
    visibility: int = _VISIBILITY_NORMAL,
) -> str:
    """Bring a live furniture panel back to themey's spec.

    A skipped-because-alive panel kept whatever thickness it had drifted
    to — chris's iconbox panel sat at 120 px (twice ``_ICONBOX_HEIGHT``)
    across several applies (live 2026-09-01), and the panels earlier
    applies created are 130/60 px rather than the E16 sizes. Thickness,
    length mode, visibility and (for fit panels) the cleared minimum are
    themey's spec, so every apply re-asserts them; widget config and
    alignment are left to the user.

    ``hiding`` is written only for a strut-bearing panel, for the same
    reason as in :func:`_panel_script` — a windows-go-below panel is
    switched through plasmashellrc instead, and reads back ``'none'``
    anyway.
    """
    return (
        f"var p = panelById({panel_id});"
        f" if (p) {{ p.height = {height};"
        f" p.lengthMode = '{length_mode}';"
        + (" p.hiding = 'none';" if visibility == _VISIBILITY_NORMAL else "")
        + (" p.minimumLength = 0;" if length_mode == "fit" else "")
        + " try { p.floating = false; } catch (e) {} }"
        " print(p ? 'reasserted' : 'missing');"
    )


def _furniture_exists_script(panel_id: str, required_widget: str | None) -> str:
    """Existence check: ``exists`` / ``missing``, or ``stale`` when the
    recorded panel is alive but no longer hosts *required_widget* (a
    pager panel from before themey's own pager applet still carrying the
    stock ``org.kde.plasma.pager``)."""
    if required_widget is None:
        return f"print(panelById({panel_id}) ? 'exists' : 'missing');"
    return (
        f"var p = panelById({panel_id});"
        f" print(p ? (p.widgets('{required_widget}').length ? 'exists' : 'stale')"
        " : 'missing');"
    )


def _remove_furniture(
    kw: str, kr: str, specs: tuple[FurnitureSpec, ...]
) -> ApplyError | None:
    """Remove each *specs* panel that a marker still names, clearing the
    marker; returns the first failure instead of raising.

    Shared by :func:`revert` (removing everything themey created) and
    :func:`_ensure_furniture` (removing a panel the user has just opted
    out of). A missing panel prints ``absent`` — still success, marker
    deleted. The printed sentinel is the real success signal (``qdbus``
    exits 0 even when the script throws, and the marker is the ONLY
    handle on the created panel, so deleting it on a thrown script would
    leak the panel with no retry): on a failure the marker is KEPT and a
    warning logged. A non-digit (tampered) marker is never interpolated,
    just dropped.
    """
    first_error: ApplyError | None = None
    for spec in specs:
        marker = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, spec.key)
        if marker is None:
            continue
        if not _is_panel_id(marker):
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, spec.key)
            continue
        try:
            reply = _evaluate_plasma_script(
                f"var p = panelById({marker});"
                " if (p) { p.remove(); print('removed'); }"
                " else { print('absent'); }",
                f"plasmashell {spec.name} removal script",
            )
            if reply not in ("removed", "absent"):
                raise ApplyError(
                    f"plasmashell {spec.name} removal script did not "
                    f"confirm removal (got {reply!r}) — the {spec.name} "
                    "may still be present"
                )
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, spec.key)
        except ApplyError as exc:
            first_error = first_error or exc
            log.warning(
                "could not remove the themey %s (%s) — keeping the marker "
                "so a later `themey apply --revert` can retry it",
                spec.name, exc,
            )
    return first_error


def _write_furniture_visibility(
    kw: str, live: tuple[tuple[FurnitureSpec, str], ...]
) -> bool:
    """Write each live furniture panel's ``panelVisibility`` into
    plasmashellrc; True when any panel was set to a non-strut mode.

    Must run AFTER every script that assigns a panel's ``hiding`` — the
    furniture scripts and the ``--no-dragbar`` unparking alike:
    plasmashell flushes a scripted ``hiding`` to the file lazily, and a
    flush landing after this write would put the panel back to ``none``
    (verified live 2026-09-01). The mode itself is only known to take at
    the next plasmashell start, which is why the caller warns when this
    apply is not ending in one; the written value does survive that
    restart.
    """
    pending = False
    for spec, panel_id in live:
        _run_checked(
            [
                kw, "--file", _PLASMASHELLRC,
                "--group", _PLASMA_VIEWS_GROUP,
                "--group", f"Panel {panel_id}",
                "--key", _PANEL_VISIBILITY_KEY, str(spec.visibility),
            ],
            f"writing {_PLASMASHELLRC} [{_PLASMA_VIEWS_GROUP}]"
            f"[Panel {panel_id}] {_PANEL_VISIBILITY_KEY}",
        )
        pending = pending or spec.visibility != _VISIBILITY_NORMAL
    return pending


def _ensure_furniture(
    kw: str,
    kr: str,
    *,
    scale: float = _DEFAULT_THEME_SCALE,
    tasks_hover: bool = True,
    furniture: FurnitureOptions = DEFAULT_FURNITURE,
    screen_aspect: float = _DEFAULT_SCREEN_ASPECT,
) -> tuple[tuple[FurnitureSpec, str], ...]:
    """Create each WANTED E16 furniture panel unless its recorded one is
    alive — in which case its thickness/length/visibility spec is
    re-asserted (:func:`_furniture_reassert_script`). A recorded panel
    that is alive but ``stale`` (:func:`_furniture_exists_script` —
    hosting the stock pager instead of themey's) is removed and
    recreated, its marker overwritten. Returns ``(spec, panel_id)`` for
    every panel that is now live, for :func:`_write_furniture_visibility`.

    A panel *furniture* does NOT want is removed if a marker names one
    (:func:`_remove_furniture`, which warns rather than raising — an
    opt-out that cannot take must not fail the whole apply).

    Each marker is validated :func:`_is_panel_id` before it is ever
    interpolated into a plasmashell script — kdeglobals is user-editable,
    and a tampered marker must not become script injection. A non-digit
    or dead-panel marker is simply overwritten by the fresh panel's id,
    written only AFTER a successful create so a failed create leaves no
    stale marker (an earlier panel's marker survives the failure, so a
    retry skips it instead of doubling it).
    """
    specs = _furniture_specs(
        scale=scale, tasks_hover=tasks_hover,
        furniture=furniture, screen_aspect=screen_aspect,
    )
    unwanted = tuple(s for s in specs if not furniture.enabled(s.key))
    if unwanted:
        _remove_furniture(kw, kr, unwanted)
    live: list[tuple[FurnitureSpec, str]] = []
    for spec in (s for s in specs if furniture.enabled(s.key)):
        marker = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, spec.key)
        if marker is not None and _is_panel_id(marker):
            alive = _evaluate_plasma_script(
                _furniture_exists_script(marker, spec.required_widget),
                f"plasmashell {spec.name} existence check",
            )
            if alive == "exists":
                _evaluate_plasma_script(
                    _furniture_reassert_script(
                        marker, spec.height, spec.length_mode, spec.visibility
                    ),
                    f"plasmashell {spec.name} re-assert script",
                )
                live.append((spec, marker))
                continue
            if alive == "stale":
                log.info(
                    "%s %s no longer hosts %s — recreating it",
                    spec.name, marker, spec.required_widget,
                )
                _evaluate_plasma_script(
                    f"var p = panelById({marker}); if (p) {{ p.remove(); }}",
                    f"plasmashell stale {spec.name} removal script",
                )
        reply = _evaluate_plasma_script(
            spec.script, f"plasmashell {spec.name} creation script"
        )
        if not _is_panel_id(reply):
            raise ApplyError(
                f"plasmashell {spec.name} creation script did not print a "
                f"panel id (got {reply!r}) — the {spec.name} was not created"
            )
        _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, spec.key, reply)
        live.append((spec, reply))
    return tuple(live)


def _parse_top_panels_marker(marker: str) -> dict[str, tuple[str, str, str]]:
    """``{id: (screen, location, hiding)}`` from a ``PrevTopPanels``
    marker; malformed entries (a tampered kdeglobals) are dropped, never
    interpolated."""
    out: dict[str, tuple[str, str, str]] = {}
    for entry in marker.split("|"):
        if "=" not in entry:
            continue
        pid, rest = entry.split("=", 1)
        parts = rest.split(":")
        if len(parts) != 3:
            continue
        screen, location, hiding = parts
        if (
            _is_panel_id(pid)
            and screen.isascii() and screen.isdigit()
            and location in _PANEL_LOCATIONS
            and hiding.isascii() and hiding.isalpha()
        ):
            out[pid] = (screen, location, hiding)
    return out


def _read_top_panels(exclude: set[str]) -> dict[str, tuple[str, str, str]]:
    """``{id: (screen, location, hiding)}`` for every live top panel not
    in *exclude*."""
    out = _evaluate_plasma_script(
        "var out = [];"
        "for (const p of panels()) {"
        " if (p.location == 'top') {"
        " out.push(p.id + '=' + p.screen + ':' + p.location + ':' + p.hiding); } }"
        "print(out.join('|'));",
        "plasmashell top-panel read script",
    )
    found = _parse_top_panels_marker(out)
    return {pid: v for pid, v in found.items() if pid not in exclude}


def _park_top_panels(kw: str, kr: str) -> None:
    """Park every pre-themey TOP panel so the dragbar owns the top edge.

    E16 has exactly one thing along the top: the dragbar. The user's
    existing top panel (a kicker/tray/clock bar on the reference machine)
    is moved to a screen index that does not exist — plasmashell keeps
    its whole config and simply never shows it (verified live 2026-09-01,
    see ``_PREV_TOP_PANELS_KEY``) — and its ``screen:location:hiding``
    recorded once in ``PrevTopPanels`` so :func:`revert` can put it back
    exactly. A second apply parks only panels not yet recorded (a new top
    panel the user added since) and appends them; the themey dragbar's
    own marker id is always excluded. Fallback when the screen assignment
    does not take: right edge + autohide (still recorded, still
    restorable).
    """
    recorded_raw = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_TOP_PANELS_KEY)
    recorded = _parse_top_panels_marker(recorded_raw) if recorded_raw else {}
    exclude = set(recorded)
    dragbar = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _DRAGBAR_KEY)
    if dragbar is not None and _is_panel_id(dragbar):
        exclude.add(dragbar)
    to_park = _read_top_panels(exclude)
    if not to_park:
        return
    for pid, (screen, _location, _hiding) in sorted(to_park.items()):
        reply = _evaluate_plasma_script(
            f"var p = panelById({pid});"
            " if (!p) { print('absent'); } else {"
            " var ok = false;"
            f" try {{ p.screen = screenCount; ok = (p.screen != {screen}); }} catch (e) {{}}"
            " if (!ok) { p.location = 'right'; p.hiding = 'autohide'; }"
            " print(ok ? 'parked' : 'fallback'); }",
            f"plasmashell top panel {pid} parking script",
        )
        if reply not in ("parked", "fallback", "absent"):
            raise ApplyError(
                f"plasmashell top panel {pid} parking script did not confirm "
                f"(got {reply!r})"
            )
        if reply == "fallback":
            log.warning(
                "panel %s could not be moved off-screen; parked at the right "
                "edge (autohide) instead", pid,
            )
    merged = {**recorded, **to_park}
    marker = "|".join(
        f"{pid}={screen}:{location}:{hiding}"
        for pid, (screen, location, hiding) in sorted(merged.items())
    )
    _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_TOP_PANELS_KEY, marker)


def _unpark_top_panels(marker: str) -> None:
    """Put the recorded top panels back (revert path): screen, location
    and hiding exactly as recorded; an absent panel is simply skipped."""
    for pid, (screen, location, hiding) in sorted(
        _parse_top_panels_marker(marker).items()
    ):
        reply = _evaluate_plasma_script(
            f"var p = panelById({pid});"
            " if (!p) { print('absent'); } else {"
            f" try {{ p.screen = {screen}; }} catch (e) {{}}"
            f" p.location = '{location}'; p.hiding = '{hiding}';"
            " print('unparked'); }",
            f"plasmashell top panel {pid} unparking script",
        )
        if reply not in ("unparked", "absent"):
            raise ApplyError(
                f"plasmashell top panel {pid} unparking script did not "
                f"confirm (got {reply!r})"
            )


def _undo_top_panel_parking(kw: str, kr: str) -> None:
    """Unpark the recorded pre-themey top panels when the dragbar is
    opted out — nothing of themey's owns the top edge then, so the user's
    own bar comes back (the same restore :func:`revert` does). Cosmetic:
    a failure warns and keeps the marker rather than failing the apply.
    """
    marker = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_TOP_PANELS_KEY)
    if marker is None:
        return
    try:
        _unpark_top_panels(marker)
        _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_TOP_PANELS_KEY)
    except ApplyError as exc:
        log.warning(
            "could not restore the parked top panel(s) (%s) — keeping the "
            "marker so a later `themey apply --revert` can retry it", exc,
        )


def _set_live_desktop_rows(rows: str) -> None:
    """Change KWin's live desktop-grid rows over D-Bus.

    KWin reads kwinrc ``[Desktops] Rows`` only at startup — a config
    write plus ``reconfigure`` leaves the live layout unchanged (verified
    live 2026-08-31); the writable ``VirtualDesktopManager.rows`` D-Bus
    property is what actually reshapes the grid (and the pager).
    """
    _run_checked(
        [
            _which_qdbus(),
            "org.kde.KWin",
            "/VirtualDesktopManager",
            "org.freedesktop.DBus.Properties.Set",
            "org.kde.KWin.VirtualDesktopManager",
            "rows",
            rows,
        ],
        "KWin desktop-rows D-Bus set",
    )


def _set_desktop_grid_column(kw: str, kr: str) -> None:
    """One desktop per pager row: kwinrc ``[Desktops] Rows = Number``.

    The stacked cells fill the pager panel (whose box cannot shrink below
    plasmashell's ~130px minimum panel length) at double the width of the
    side-by-side layout. The previous ``Rows`` is recorded once in
    ``PrevDesktopRows`` (``@unset`` when absent) and restored by
    :func:`revert` — this changes desktop-switching direction, so it must
    be revertible. Skipped when the desktop count is unreadable.
    """
    number = _cfg_read(kr, "kwinrc", _DESKTOPS_GROUP, "Number")
    if number is None or not (number.isascii() and number.isdigit()):
        return
    if _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY) is None:
        prev = _cfg_read(kr, "kwinrc", _DESKTOPS_GROUP, "Rows") or _UNSET
        _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY, prev)
    _cfg_write(kw, "kwinrc", _DESKTOPS_GROUP, "Rows", number)
    _set_live_desktop_rows(number)


def _restore_desktop_rows(kw: str, prev_rows: str) -> None:
    """Put the recorded ``[Desktops] Rows`` back — config AND live rows
    (see :func:`_set_live_desktop_rows`); ``@unset`` deletes the key and
    restores KWin's default single row."""
    if prev_rows == _UNSET:
        _cfg_delete(kw, "kwinrc", _DESKTOPS_GROUP, "Rows")
        _set_live_desktop_rows("1")
    elif prev_rows.isascii() and prev_rows.isdigit():
        _cfg_write(kw, "kwinrc", _DESKTOPS_GROUP, "Rows", prev_rows)
        _set_live_desktop_rows(prev_rows)


def _undo_desktop_grid_column(kw: str, kr: str) -> None:
    """Give the user's desktop grid back when the pager is opted out.

    The stacked one-per-row grid exists only to fill the pager panel, so
    ``--no-pager`` restores the recorded baseline the way :func:`revert`
    does and clears the marker. Cosmetic: a failure warns rather than
    failing the apply.
    """
    prev_rows = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY)
    if prev_rows is None:
        return
    try:
        _restore_desktop_rows(kw, prev_rows)
        _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY)
    except ApplyError as exc:
        log.warning(
            "could not restore the previous desktop grid (%s) — keeping "
            "the marker so a later `themey apply --revert` can retry it", exc,
        )


def _record_prev_deco(kw: str, kr: str) -> None:
    """Snapshot kwinrc ``[org.kde.kdecoration2] library|theme|BorderSize``
    once, mirroring ``_apply_theme_buttons``'s ``ThemeyPrevButtons`` shape
    and once-only lifecycle."""
    if _kread(kr, _PREV_DECO_KEY) is not None:
        return
    prev_library = _kread(kr, "library") or _UNSET
    prev_theme = _kread(kr, "theme") or _UNSET
    prev_border = _kread(kr, "BorderSize") or _UNSET
    _kwrite(kw, _PREV_DECO_KEY, f"{prev_library}|{prev_theme}|{prev_border}")


def _write_deco(
    name: str,
    kw: str,
    kr: str,
    *,
    legacy_plugin: bool = False,
    border_size: str | None = None,
    keep_buttons: bool = False,
    backend: str = "qml",
) -> None:
    """Write the kwinrc keys so KWin loads *name*'s decoration.

    Shared body of :func:`apply` and :func:`apply_full` — no ``which()``
    lookups (callers pass the resolved tool paths) and no ``qdbus``
    reconfigure (callers issue that once, at their own tail, after any
    other work — e.g. ``apply_full``'s wallpaper fix-up — has run).

    ``backend="qml"`` selects the QML decoration package
    ``themey_<slug>`` under ``kwin/decorations/``: it writes
    ``library=org.kde.kwin.aurorae`` + the raw package id as ``theme=``,
    and deliberately touches NEITHER ButtonsOnLeft/Right NOR BorderSize —
    the QML theme draws its own buttons and sets its own (unclamped)
    borders. The snapshot/restore machinery stays in place for SVG applies
    and the ``apply Breeze`` / ``apply --revert`` reverts.
    """
    if backend not in ("svg", "qml"):
        raise ApplyError(f"backend must be 'svg' or 'qml' (got {backend!r})")
    if border_size is not None and border_size not in BORDER_SIZES:
        raise ApplyError(f"unknown border size {border_size!r}; expected one of {BORDER_SIZES}")
    if name.lower() == "breeze":
        _kwrite(kw, "library", "org.kde.breeze")
        _kwrite(kw, "theme", "Breeze")
        if not keep_buttons:
            _restore_buttons(kw, kr)
    elif backend == "qml":
        pkg_id = name if name.startswith("themey_") else plugin_id(name)
        pkg_dir = paths.kwin_decorations() / pkg_id
        if not (pkg_dir / "metadata.json").is_file():
            raise ApplyError(
                f"QML decoration {pkg_id!r} is not installed under "
                f"{paths.kwin_decorations()} — run `themey convert` with the "
                "qml backend first"
            )
        _kwrite(kw, "library", PLUGINS["legacy"])
        _kwrite(kw, "theme", pkg_id)
        border_size = None  # theme-controlled; never write BorderSize
    else:
        theme_dir = paths.aurorae_themes() / name
        if not theme_dir.is_dir():
            raise ApplyError(f"{name!r} is not installed under {paths.aurorae_themes()}")
        _kwrite(kw, "library", PLUGINS["legacy" if legacy_plugin else "v2"])
        _kwrite(kw, "theme", f"__aurorae__svg__{name}")
        if border_size is None:
            border_size = border_size_for_installed(theme_dir, name)
        if not keep_buttons:
            btns = buttons_for_installed(theme_dir, name)
            if btns is not None:
                _apply_theme_buttons(kw, kr, btns[0], btns[1])
    if border_size is not None:
        _kwrite(kw, "BorderSize", border_size)
        _kwrite(kw, "BorderSizeAuto", "false")


def _which_qdbus() -> str:
    return _which("qdbus6", "qdbus-qt6", "qdbus")


def _reconfigure() -> None:
    subprocess.run(
        [_which_qdbus(), "org.kde.KWin", "/KWin", "reconfigure"],
        check=False,
        env=paths.subprocess_env(),
    )


#: Seconds to wait after the Breeze flip for KWin to recreate every
#: decoration (destroying the Aurorae ones and, with them, the cached QML
#: engine) before the target theme is written back.
_AURORAE_FLUSH_WAIT_S = 2.0


def _flush_aurorae_qml_cache(kw: str) -> None:
    """Flip the live decoration to Breeze so KWin drops its Aurorae QML cache.

    Aurorae v1 (plasma/aurorae ``v1/aurorae.cpp``) compiles a theme's QML
    package once per compositor process and caches the ``QQmlComponent``
    per theme *name* (``Helper::m_components``); the shared ``QQmlEngine``
    — and with it every compiled main.qml/theme.js and loaded PNG — is
    torn down only when the last Aurorae decoration is destroyed
    (``Helper::unref`` refcount 0). A reconfigure with an unchanged
    ``theme=`` therefore keeps rendering the copy loaded when the theme
    first appeared, no matter how many times ``themey convert`` has
    rewritten the package on disk (verified live, Plasma 6.6.6,
    2026-08-31). Flipping to Breeze + reconfigure destroys every Aurorae
    decoration, zeroing that refcount; the wait gives KWin time to finish
    recreating decorations before the caller points ``theme=`` back at
    the package. Switching between two Aurorae themes does NOT flush —
    both stay cached — which is why the bounce goes through Breeze.
    """
    _kwrite(kw, "library", "org.kde.breeze")
    _kwrite(kw, "theme", "Breeze")
    _reconfigure()
    time.sleep(_AURORAE_FLUSH_WAIT_S)


#: How long to wait for plasmashell to exit after a graceful quit request
#: before restarting it anyway.
_SHELL_QUIT_WAIT_S = 10.0


def _quit_plasmashell_gracefully(systemctl: str) -> None:
    """Ask plasmashell to quit cleanly and wait for it, so its config
    reaches disk before the restart.

    plasmashell flushes scripted panel writes (the furniture thickness /
    lengthMode / minimumLength from ``_ensure_furniture``, the wallpaper
    FillMode) LAZILY — several seconds after the script — and a
    ``systemctl restart`` SIGTERM does not sync them: the fresh shell
    reloaded plasmashellrc's stale ``thickness=120`` for the iconbox
    panel right after the script had set 60 (live 2026-09-01). A
    ``kquitapp6 plasmashell`` quit runs the corona destructors, which
    sync; the unit goes inactive and the restart below starts it. Best
    effort: no kquitapp, a quit that never completes, or any error just
    falls through to the plain restart.
    """
    kquit = shutil.which("kquitapp6") or shutil.which("kquitapp")
    if kquit is None:
        return
    try:
        subprocess.run(
            [kquit, "plasmashell"], capture_output=True, text=True,
            env=paths.subprocess_env(), check=False, timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return
    deadline = time.monotonic() + _SHELL_QUIT_WAIT_S
    while time.monotonic() < deadline:
        try:
            state = subprocess.run(
                [systemctl, "--user", "is-active", "plasma-plasmashell"],
                capture_output=True, text=True, env=paths.subprocess_env(),
                check=False, timeout=15,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return
        if state != "active":
            return
        time.sleep(0.25)


def _restart_plasmashell() -> None:
    """Restart plasmashell so a tiled wallpaper and a new Plasma Style's
    applet metrics actually take.

    plasmashell 6.6.6 does NOT repaint fill-mode from any scripting write
    (verified live 2026-08-31: FillMode alone, +Image rewrite,
    +reloadConfig, even an Image swap-away-and-back all left the render
    pixel-identical) — only the first paint after a shell restart or a
    manual KCM toggle honors the new mode. Likewise Kickoff computes
    ``KickoffSingleton.lineSvg.horLineHeight`` and ``listItemMetrics``
    once at load (``elementSize()`` is a function call, not a bound
    property), so after ``plasma-apply-desktoptheme`` its separators keep
    the PREVIOUS theme's thickness (verified live 2026-09-01). The theme
    is fully applied by the time this runs, so a failure (or a machine
    without systemd) is a logged warning telling the user to restart
    manually, never a failed apply.
    """
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        log.warning(
            "systemctl not found — restart plasmashell manually (or log "
            "out and back in) for the tiled wallpaper to repaint"
        )
        return
    _quit_plasmashell_gracefully(systemctl)
    try:
        _run_checked(
            [systemctl, "--user", "restart", "plasma-plasmashell"],
            "plasmashell restart",
        )
    except ApplyError as exc:
        log.warning(
            "could not restart plasmashell (%s) — the tiled wallpaper "
            "repaints after the next login or a manual restart", exc,
        )


def _write_image_wallpaper_config(writes: dict[str, str], what: str) -> None:
    """Write *writes* (key -> JS literal) into every desktop's Image
    wallpaper config through plasmashell's scripting D-Bus.

    reloadConfig() is load-bearing: a scripting writeConfig lands in the
    config but the Image wallpaper's bindings are only re-read on a
    wallpaper reload (verified live 2026-08-31 — without it the config
    says tiled while the screen keeps the old fill until next login).
    """
    body = "".join(f" d.writeConfig('{k}', {v});" for k, v in writes.items())
    script = (
        "for (const d of desktops()) {"
        " d.wallpaperPlugin = 'org.kde.image';"
        " d.currentConfigGroup = ['Wallpaper', 'org.kde.image', 'General'];"
        f"{body}"
        " d.reloadConfig();"
        "}"
    )
    _run_checked(
        [
            _which_qdbus(),
            "org.kde.plasmashell",
            "/PlasmaShell",
            "org.kde.PlasmaShell.evaluateScript",
            script,
        ],
        what,
    )


def _set_wallpaper_fill(
    image: Path, mode: str, solid: str | None = None
) -> bool:
    """Set *image* as the wallpaper on all desktops with the E16 fill
    *mode* (``analyze.wallpaper.FILL_MODES``); True when the live render
    needs the plasmashell restart ``apply_full`` runs last.

    Two dispatch paths, because ``plasma-apply-wallpaperimage -f`` only
    knows ``stretch``/``preserveAspectFit``/``pad`` (plus a crop E16 never
    produces): those modes go straight through the tool
    (:data:`_WALLPAPER_FILL_MODE_TOKENS`); the three tile modes set the
    image without ``-f`` and then write the QML ``FillMode`` int
    (:data:`_WALLPAPER_FILL_MODE_INTS`) on every desktop's Image wallpaper
    config. That CONFIG lands (the KCM shows the mode) but the live
    render does not pick a scripted fill-mode up until plasmashell
    restarts — see :func:`_restart_plasmashell`.

    *solid* (``X-Themey-SolidColor``, KConfig's ``r,g,b`` QColor spelling)
    is the block's SET_SOLID; for ``fit``/``pad`` E16 blends the image over
    it, so the Image wallpaper's ``Color`` key — its letterbox color — is
    written through the same scripting call shape. Tiles have no
    letterbox, and their solid was flattened into the art at convert time.
    """
    plasma_apply_wp = _which("plasma-apply-wallpaperimage")
    token = _WALLPAPER_FILL_MODE_TOKENS.get(mode)
    if token is not None:
        _run_checked(
            [plasma_apply_wp, "-f", token, str(image)],
            f"plasma-apply-wallpaperimage -f {token} {image}",
        )
        if solid is not None and mode in ("fit", "pad"):
            _write_image_wallpaper_config(
                {"Color": f"'{solid}'"}, "plasmashell letterbox-Color script"
            )
        return False

    _run_checked(
        [plasma_apply_wp, str(image)], f"plasma-apply-wallpaperimage {image}"
    )
    _write_image_wallpaper_config(
        {"FillMode": str(_WALLPAPER_FILL_MODE_INTS[mode])},
        f"plasmashell {mode}-FillMode script",
    )
    return True


def _run_checked(argv: list[str], what: str) -> None:
    """Run *argv*, raising a typed :class:`ApplyError` (stderr tail
    included) on a non-zero exit instead of letting
    ``subprocess.CalledProcessError`` escape as an unhandled traceback —
    the same external-tool-failure shape as ``external.run_xcursorgen``.

    Every external write in this module funnels through here: the two
    ``plasma-apply-*`` calls (likeliest to fail — a stale/uninstalled
    package id, a bad fill-mode token) and the ``kwriteconfig6`` writes and
    deletes behind ``_cfg_write`` / ``_cfg_delete``. ``cli.py``'s apply
    handler catches only :class:`ApplyError`, so anything that escapes as a
    raw ``CalledProcessError`` reaches the user as a traceback.
    """
    proc = subprocess.run(
        argv, capture_output=True, text=True, env=paths.subprocess_env()
    )
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip()[-500:]
        raise ApplyError(f"{what} failed (exit {proc.returncode}): {tail}")


def apply(
    name: str,
    *,
    legacy_plugin: bool = False,
    border_size: str | None = None,
    keep_buttons: bool = False,
    backend: str = "qml",
) -> None:
    """Point the live KWin at an installed theme's decoration ONLY.

    This is the deco-only path — CLI ``--deco-only``, and the only path
    for ``--backend svg``. See :func:`apply_full` for the CLI default,
    which applies the whole installed Look-and-Feel bundle and then calls
    into the same decoration-writing logic used here.
    """
    kw = _which("kwriteconfig6", "kwriteconfig5")
    kr = _which("kreadconfig6", "kreadconfig5")
    if backend == "qml" and name.lower() != "breeze":
        _flush_aurorae_qml_cache(kw)
    _write_deco(
        name, kw, kr,
        legacy_plugin=legacy_plugin, border_size=border_size,
        keep_buttons=keep_buttons, backend=backend,
    )
    _reconfigure()


def _read_defaults_value(lnf_dir: Path, section: str, key: str) -> str | None:
    """One value from an installed bundle's ``contents/defaults``, or None
    when the file/section/key is absent (a theme without that artifact)."""
    defaults = lnf_dir / "contents" / "defaults"
    if not defaults.is_file():
        return None
    cp = configparser.RawConfigParser()
    cp.optionxform = staticmethod(str)  # type: ignore[assignment]
    try:
        cp.read(defaults, encoding="utf-8")
        return cp.get(section, key)
    except (configparser.Error, KeyError):
        return None


def _read_default_wallpaper_id(lnf_dir: Path) -> str | None:
    """The ``[Wallpaper] Image=`` value from an installed bundle's
    ``contents/defaults``, or None when the bundle has no wallpaper group
    (unreadable file, or a theme with no convertible wallpaper)."""
    return _read_defaults_value(lnf_dir, "Wallpaper", "Image")


def _read_default_icon_theme(lnf_dir: Path) -> str | None:
    """The ``[kdeglobals][Icons] Theme=`` value from an installed bundle
    (the windowmatches icon theme's dir name), or None when the bundle
    shipped none."""
    return _read_defaults_value(lnf_dir, "kdeglobals][Icons", "Theme")


def _read_theme_scale(lnf_dir: Path) -> float:
    """The ``X-Themey-Scale`` stamp from an installed bundle's
    ``metadata.json`` (``generate/lookandfeel.py``), or
    :data:`_DEFAULT_THEME_SCALE` when absent, unreadable or not a
    positive number — the dragbar panel is sized from it."""
    meta = lnf_dir / "metadata.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _DEFAULT_THEME_SCALE
    value = data.get("X-Themey-Scale") if isinstance(data, dict) else None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return _DEFAULT_THEME_SCALE
    return float(value)


def _read_widget_style(lnf_dir: Path) -> str | None:
    """The ``X-Themey-WidgetStyle`` stamp from an installed bundle's
    ``metadata.json`` (``generate/lookandfeel.py``) — the Qt application
    style ``themey convert --widget-style`` chose — or None when the
    bundle carries none (the default: leave the user's style alone), the
    file is unreadable, or the stamp is not a non-empty string."""
    meta = lnf_dir / "metadata.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    value = data.get("X-Themey-WidgetStyle") if isinstance(data, dict) else None
    return value if isinstance(value, str) and value else None


def _read_tasks_hover(style_dir: Path) -> bool:
    """``X-Themey-TasksHover`` from an installed Plasma Style's
    ``metadata.json`` (``generate/plasmastyle._write_metadata``): whether
    the iconbox art has a hilited state worth a hover effect. Absent or
    unreadable → True (Plasma's own default)."""
    meta = style_dir / "metadata.json"
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return True
    value = data.get("X-Themey-TasksHover") if isinstance(data, dict) else None
    return value if isinstance(value, bool) else True


def _wallpaper_metadata(wallpaper_dir: Path) -> dict[str, object]:
    """An installed wallpaper package's ``metadata.json``, or ``{}`` when
    unreadable/absent."""
    meta = wallpaper_dir / "metadata.json"
    if not meta.is_file():
        return {}
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _wallpaper_fill_mode(wallpaper_dir: Path) -> str | None:
    """``X-Themey-FillMode`` from an installed wallpaper package's
    ``metadata.json`` (legacy ``tiled``/``scaled`` mapped to their modern
    mode), or None when unreadable/absent."""
    mode = _wallpaper_metadata(wallpaper_dir).get("X-Themey-FillMode")
    if not isinstance(mode, str):
        return None
    return _LEGACY_FILL_MODES.get(mode, mode)


def _wallpaper_solid_color(wallpaper_dir: Path) -> str | None:
    """``X-Themey-SolidColor`` (``r,g,b``) from an installed wallpaper
    package's ``metadata.json``, or None."""
    solid = _wallpaper_metadata(wallpaper_dir).get("X-Themey-SolidColor")
    return solid if isinstance(solid, str) else None


def _wallpaper_image_path(wallpaper_dir: Path) -> Path | None:
    """The one image file under an installed wallpaper package's
    ``contents/images/``, or None when absent."""
    images_dir = wallpaper_dir / "contents" / "images"
    if not images_dir.is_dir():
        return None
    images = sorted(images_dir.glob("*"))
    return images[0] if images else None


def apply_full(
    name: str,
    *,
    legacy_plugin: bool = False,
    border_size: str | None = None,
    keep_buttons: bool = False,
    restart_shell: bool = True,
    furniture: FurnitureOptions = DEFAULT_FURNITURE,
    widget_style: str | None = None,
) -> None:
    """Apply the whole installed Look-and-Feel bundle for *name* (the CLI
    default), always via the QML deco backend.

    *widget_style* is a ``lookandfeel.WIDGET_STYLES`` token overriding the
    bundle's own ``X-Themey-WidgetStyle`` stamp for this one run (CLI
    ``--widget-style``); None (the default) uses the stamp, and a bundle
    without one leaves the Qt application style untouched.

    *furniture* (:class:`FurnitureOptions`) selects and sizes the E16
    panels: any of the three can be left out (an already-created one is
    then removed, and the steps that exist only for it — the stacked
    desktop grid for the pager, the top-panel parking for the dragbar —
    are skipped and their baselines restored), the pager cell and iconbox
    thicknesses are overridable, and ``strut`` turns the left-edge panels
    back into screen-reserving ones.

    Order (see module docstring): verify both the Look-and-Feel bundle and
    the QML decoration package are installed → record the pre-themey
    baselines (once) → ``plasma-apply-lookandfeel -a themey_<slug>`` (NEVER
    ``--resetLayout``, which would blow away unrelated layout state) →
    ``plasma-apply-colorscheme themey_<slug>`` when the scheme is installed
    (REQUIRED: the LnF apply does not touch an explicit user-layer
    ``[General] ColorScheme`` — see :func:`_record_prev_colorscheme`) →
    the per-app icon theme and then the Qt application style, both written
    straight into user-layer kdeglobals for the same reason and each
    followed by its D-Bus broadcast (:func:`_notify_icons_changed`,
    :func:`_notify_style_changed`) →
    when the Plasma Style package is installed, clear its Version-keyed SVG
    cache (:func:`themey.install.clear_style_cache`) then ``plasma-apply-desktoptheme
    themey_<slug>`` (explicit for the same user-layer-shadowing reason —
    see :func:`_record_prev_plasmatheme`) → the
    same decoration write :func:`apply` uses (REQUIRED even though the LnF
    apply already wrote deco defaults: those land in the
    ``~/.config/kdedefaults/`` layer, and only an explicit user-layer write
    is guaranteed to win) → :func:`_set_wallpaper_fill` with the bundle's
    default wallpaper's ``X-Themey-FillMode`` (Plasma's Image wallpaper
    plugin does not itself read fill-mode from the wallpaper package;
    ``stretch``/``fit``/``pad`` go through the apply tool's ``-f``, the
    tile modes through a scripted ``FillMode`` write — see
    :data:`_WALLPAPER_FILL_MODE_INTS`) → one ``qdbus`` reconfigure →
    dead last, a plasmashell restart when a tile mode was scripted or a
    Plasma Style was applied (:func:`_restart_plasmashell`; *restart_shell*
    ``False`` opts out). Every panel is set to fit-content and un-floated just BEFORE the
    wallpaper fix-up (:func:`_set_panels_fit` — E16's iconbox/dragbar are
    content-sized docked strips, and a full-width or floating bar reads as
    Plasma, not E16; previous modes recorded once in
    ``PrevPanelLengthModes``/``PrevPanelFloating``): the wallpaper step
    is the likeliest to raise, and a failed apply should still have
    delivered the panel feel. The furniture panels are created right
    after the fit step (:func:`_ensure_furniture` — after, so they never
    pollute the ``PrevPanelLengthModes`` baseline; before the wallpaper
    fix-up for the same survive-a-wallpaper-failure reason), the existing
    top panels parked just before them (:func:`_park_top_panels`) so the
    dragbar — created last — is never itself parked, and their
    ``panelVisibility`` written last of the whole panel section
    (:func:`_write_furniture_visibility`, which must follow every script
    that touches a panel's ``hiding`` — the unparking included).

    ``name == "Breeze"`` (case-insensitive) is the one exception: Breeze
    has no Look-and-Feel bundle to verify or baseline to record — it is
    the legacy revert path documented in the README and every generated
    ``report.txt``, so it routes straight through to :func:`apply`'s
    existing special case, unchanged, on BOTH the default and
    ``--deco-only`` paths.
    """
    if name.lower() == "breeze":
        apply(
            name,
            legacy_plugin=legacy_plugin, border_size=border_size,
            keep_buttons=keep_buttons, backend="qml",
        )
        return
    # Validated up front, before any side effect: unlike apply(), this
    # path snapshots markers and runs plasma-apply-lookandfeel before it
    # would otherwise reach _write_deco's own border_size check, and a bad
    # --border-size shouldn't leave those half-done.
    if border_size is not None and border_size not in BORDER_SIZES:
        raise ApplyError(f"unknown border size {border_size!r}; expected one of {BORDER_SIZES}")
    if widget_style is not None and widget_style not in WIDGET_STYLES:
        raise ApplyError(
            f"unknown widget style {widget_style!r}; expected one of "
            f"{sorted(WIDGET_STYLES)}"
        )
    kw = _which("kwriteconfig6", "kwriteconfig5")
    kr = _which("kreadconfig6", "kreadconfig5")

    pkg_id = name if name.startswith("themey_") else plugin_id(name)
    lnf_dir = paths.look_and_feel() / pkg_id
    deco_dir = paths.kwin_decorations() / pkg_id
    if not (lnf_dir / "metadata.json").is_file() or not (deco_dir / "metadata.json").is_file():
        raise ApplyError(
            f"{pkg_id!r} is not fully installed — expected a Look-and-Feel "
            f"bundle under {paths.look_and_feel()} and a QML decoration "
            f"under {paths.kwin_decorations()} — run `themey convert` first"
        )

    # Only the applets the ENABLED panels host are required: with
    # --no-pager/--no-dragbar the missing package is simply never used.
    needed_applets = tuple(
        pid for pid, wanted in (
            (plasmoids.PAGER_ID, furniture.pager),
            (plasmoids.DESKBUTTON_ID, furniture.dragbar),
        ) if wanted
    )
    missing_applets = [
        pid for pid in needed_applets
        if not (paths.plasmoids() / pid / "metadata.json").is_file()
    ]
    if missing_applets:
        raise ApplyError(
            f"themey's applet packages are not installed under "
            f"{paths.plasmoids()} ({', '.join(missing_applets)}) — run "
            "`themey convert` first (any theme installs them)"
        )
    for pid in needed_applets:
        installed_rt = plasmoids.installed_runtime_version(paths.plasmoids() / pid)
        if installed_rt is None or installed_rt < plasmoids.RUNTIME_VERSION:
            log.warning(
                "installed applet %s is runtime %s, this themey is %s — "
                "re-run `themey convert` to refresh it",
                pid, installed_rt, plasmoids.RUNTIME_VERSION,
            )

    scheme_file = paths.color_schemes() / f"{pkg_id}.colors"
    has_colors = scheme_file.is_file()
    style_dir = paths.desktop_themes() / pkg_id
    has_style = (style_dir / "metadata.json").is_file()
    theme_scale = _read_theme_scale(lnf_dir)
    tasks_hover = _read_tasks_hover(style_dir) if has_style else True
    # The command line beats the bundle's stamp; neither = leave the
    # application style alone (no baseline recorded, nothing written).
    qt_widget_style = (
        WIDGET_STYLES[widget_style] if widget_style is not None
        else _read_widget_style(lnf_dir)
    )
    icon_theme = _read_default_icon_theme(lnf_dir)
    if icon_theme is not None and not (
        paths.icon_themes() / icon_theme / "index.theme"
    ).is_file():
        log.warning(
            "bundle names icon theme %s but it is not installed under %s; "
            "leaving the icon theme alone", icon_theme, paths.icon_themes(),
        )
        icon_theme = None

    _record_prev_lookandfeel(kw, kr)
    _record_prev_deco(kw, kr)
    if has_colors:
        _record_prev_colorscheme(kw, kr)
    if has_style:
        _record_prev_plasmatheme(kw, kr)
    if icon_theme is not None:
        _record_prev_icontheme(kw, kr)
    if qt_widget_style is not None:
        _record_prev_widget_style(kw, kr)

    plasma_apply_lnf = _which("plasma-apply-lookandfeel")
    _run_checked([plasma_apply_lnf, "-a", pkg_id], f"plasma-apply-lookandfeel -a {pkg_id}")

    if has_colors:
        # plasma-apply-lookandfeel leaves an explicit user-layer
        # ColorScheme in place (see _record_prev_colorscheme) — the scheme
        # must be applied explicitly, and this also broadcasts the change
        # to running apps.
        plasma_apply_colors = _which("plasma-apply-colorscheme")
        _run_checked(
            [plasma_apply_colors, pkg_id],
            f"plasma-apply-colorscheme {pkg_id}",
        )

    if icon_theme is not None:
        # Same user-layer shadowing as the color scheme (kdeglobals
        # Theme=Fluency on the reference machine): explicit write, then the
        # KIconLoader broadcast so running apps pick the icons up.
        _cfg_write(kw, _KDEGLOBALS, _ICONS_GROUP, _ICON_THEME_KEY, icon_theme)
        _notify_icons_changed()

    if qt_widget_style is not None:
        # Third kdeglobals key with the same user-layer shadowing: the
        # bundle's [kdeglobals][KDE] group lands in kdedefaults, so an
        # explicit user-layer widgetStyle would keep winning. Written
        # here, beside the colours and icons, then broadcast so running
        # apps restyle without a relogin.
        _cfg_write(kw, _KDEGLOBALS, _KDE_GROUP, _WIDGET_STYLE_KEY, qt_widget_style)
        _notify_style_changed()

    if has_style:
        # Same user-layer shadowing as the color scheme (the reference
        # machine's plasmarc has an explicit name=Otto), so the explicit
        # apply is required, not belt-and-braces. The cache clear must come
        # first: plasmashell would otherwise repaint from the stale
        # Version-keyed kcache of a previous conversion.
        clear_style_cache(pkg_id)
        plasma_apply_style = _which("plasma-apply-desktoptheme")
        if _cfg_read(kr, _PLASMARC, _PLASMA_THEME_GROUP, _PLASMA_NAME_KEY) == pkg_id:
            # plasma-apply-desktoptheme with the CURRENT name is a no-op
            # ("already set as the theme"), and plasmashell then keeps the
            # previous conversion's SVGs in memory even though the
            # package on disk and the kcache are fresh (live 2026-09-01:
            # OldE's panel kept a wordmark cap the new guard had rejected
            # until the style was bounced). The read cascades through
            # kdedefaults, so a Look-and-Feel-layer name counts too.
            _run_checked(
                [plasma_apply_style, _STYLE_BOUNCE],
                f"plasma-apply-desktoptheme {_STYLE_BOUNCE} (reload bounce)",
            )
        _run_checked(
            [plasma_apply_style, pkg_id],
            f"plasma-apply-desktoptheme {pkg_id}",
        )

    # The LnF apply above may already have pointed KWin at this package
    # (via kdedefaults), re-caching a stale copy — the flush must come
    # after it and before the final theme write.
    _flush_aurorae_qml_cache(kw)
    _write_deco(
        name, kw, kr,
        legacy_plugin=legacy_plugin, border_size=border_size,
        keep_buttons=keep_buttons, backend="qml",
    )

    # Panels BEFORE the wallpaper fix-up: plasma-apply-wallpaperimage is
    # the most failure-prone external step here (a bad image/fill token
    # raises), and the E16 panel feel must not be lost to it.
    _set_panels_fit(kw, kr)

    # Grid first so the pager panel's fit length is computed against the
    # final (stacked) desktop layout; then the furniture — AFTER the fit
    # step (so the created panels never pollute the PrevPanelLengthModes
    # baseline snapshotted there) and, like it, before the wallpaper
    # fix-up.
    if furniture.pager:
        _set_desktop_grid_column(kw, kr)
    else:
        _undo_desktop_grid_column(kw, kr)
    # Park the pre-themey top panel(s) BEFORE creating the furniture: the
    # dragbar is created last, so it is never itself parked, and after
    # the fit step, so it never enters PrevPanelLengthModes.
    if furniture.dragbar:
        _park_top_panels(kw, kr)
    # Only the pager's thickness depends on the screen shape, so the
    # extra scripting round-trip is skipped when it is opted out.
    screen_aspect = (
        _read_screen_aspect() if furniture.pager else _DEFAULT_SCREEN_ASPECT
    )
    live_furniture = _ensure_furniture(
        kw, kr, scale=theme_scale, tasks_hover=tasks_hover,
        furniture=furniture, screen_aspect=screen_aspect,
    )
    # Without the dragbar nothing of themey's claims the top edge, so the
    # parked panels come back — after the dragbar removal inside
    # _ensure_furniture, like revert does it, so the edge is free when
    # they reappear, and BEFORE the visibility write below: unparking
    # assigns `p.hiding` on the user's panels, and plasmashell's lazy
    # flush of that would rewrite plasmashellrc over the panelVisibility
    # values.
    if not furniture.dragbar:
        _undo_top_panel_parking(kw, kr)
    # Dead last of the panel work — plasmashell flushes a scripted
    # `hiding` lazily and would undo this write.
    visibility_pending = _write_furniture_visibility(kw, live_furniture)

    needs_restart = False
    wallpaper_id = _read_default_wallpaper_id(lnf_dir)
    if wallpaper_id is not None:
        wallpaper_dir = paths.wallpapers() / wallpaper_id
        mode = _wallpaper_fill_mode(wallpaper_dir)
        image = _wallpaper_image_path(wallpaper_dir)
        if mode is not None and image is not None:
            if mode in _WALLPAPER_FILL_MODE_TOKENS or mode in _WALLPAPER_FILL_MODE_INTS:
                needs_restart = _set_wallpaper_fill(
                    image, mode, _wallpaper_solid_color(wallpaper_dir)
                )
            else:
                log.warning(
                    "wallpaper package %s carries unknown X-Themey-FillMode "
                    "%r; leaving the wallpaper fill alone", wallpaper_id, mode,
                )

    _reconfigure()

    # Dead last — a shell restart would race any earlier evaluateScript.
    # Only when a tile mode was scripted OR a Plasma Style was applied:
    # applets compute some KSvg metrics once at load (Kickoff's
    # horLineHeight/listItemMetrics), so without the restart the popups
    # keep the previous theme's separator thickness (live 2026-09-01).
    # A deco/colour/tool-applied-fill-only apply must not flicker the
    # desktop.
    if restart_shell and (needs_restart or has_style):
        _restart_plasmashell()
    elif visibility_pending:
        # plasmashell reads panelVisibility at start-up only, so without
        # the restart the panels keep reserving screen space until the
        # next login (the config itself has landed).
        log.warning(
            "the pager/iconbox panels keep their screen struts until "
            "plasmashell restarts — the windows-go-below panelVisibility "
            "is written but only read at start-up"
        )


def revert() -> bool:
    """``themey apply --revert``: restore the pre-``apply_full`` state.

    Reads the markers :func:`_record_prev_lookandfeel`/
    :func:`_record_prev_deco`/:func:`_record_prev_colorscheme`/
    :func:`_record_prev_plasmatheme`/:func:`_record_prev_widget_style`
    left behind
    (the color scheme, application style and Plasma Style restores mirror
    the Look-and-Feel
    one: ``@unset`` → delete the user-layer key; a failure keeps the
    marker so a later revert retries it), reapplies the recorded
    Look-and-Feel package (no special-casing here — a real user's baseline
    is typically a third-party theme, e.g.
    ``com.github.vinceliuice.MacVentura-Dark``, not Breeze), restores the
    deco triple (deleting any key that was ``@unset`` before), restores
    the button layout, removes the themey-created furniture panels
    (:func:`_remove_furniture`, before
    the panel-mode restore, so that script iterates only surviving
    panels), then deletes the marker(s) for whatever it actually
    restored.

    Returns False (no error, no side effects beyond the ``which()``
    lookups) when NEITHER marker is present — no prior ``apply_full`` on
    this machine — so the CLI can print a friendly "nothing to revert"
    message instead of failing. Returns True when a revert was actually
    performed.

    A failure to reapply the recorded Look-and-Feel package (its most
    plausible cause: the baseline theme was uninstalled since the last
    ``apply_full``) does NOT abandon the rest of the recovery — the deco
    triple and the button layout are still restored, ``ThemeyPrevDeco`` is
    still cleared (that half succeeded), and ``qdbus`` still reconfigures.
    ``PrevLookAndFeelPackage`` is deliberately KEPT in this one case — it
    is the only record of the baseline global theme, so a later
    ``themey apply --revert`` (after the user fixes the underlying
    problem, e.g. reinstalls the missing theme) retries just the
    Look-and-Feel restore and still succeeds, rather than reporting
    "nothing to revert" while the desktop is still on the themey LnF. The
    failure is surfaced either way: raised as an :class:`ApplyError` at
    the end, after everything that could be restored has been.
    """
    kw = _which("kwriteconfig6", "kwriteconfig5")
    kr = _which("kreadconfig6", "kreadconfig5")

    prev_deco = _kread(kr, _PREV_DECO_KEY)
    prev_lnf = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_LNF_KEY)
    prev_colors = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_COLORS_KEY)
    prev_plasma = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PLASMA_KEY)
    prev_icons = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ICONS_KEY)
    prev_widget = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_WIDGET_STYLE_KEY)
    prev_panels = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PANELS_KEY)
    prev_floating = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_FLOATING_KEY)
    prev_furniture = {
        spec.key: _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, spec.key)
        for spec in _furniture_specs()
    }
    prev_rows = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY)
    prev_top = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_TOP_PANELS_KEY)
    if (
        prev_deco is None
        and prev_lnf is None
        and prev_colors is None
        and prev_plasma is None
        and prev_icons is None
        and prev_widget is None
        and prev_panels is None
        and prev_floating is None
        and prev_rows is None
        and prev_top is None
        and all(v is None for v in prev_furniture.values())
    ):
        return False

    lnf_error: ApplyError | None = None
    if prev_lnf is not None and prev_lnf != _UNSET:
        plasma_apply_lnf = _which("plasma-apply-lookandfeel")
        try:
            _run_checked(
                [plasma_apply_lnf, "-a", prev_lnf],
                f"plasma-apply-lookandfeel -a {prev_lnf}",
            )
        except ApplyError as exc:
            lnf_error = exc
            log.warning(
                "could not reapply the previous global theme %r (%s) — "
                "restoring the decoration and button layout anyway; "
                "keeping the marker so a later `themey apply --revert` "
                "can retry it",
                prev_lnf, exc,
            )
    if prev_lnf is not None and lnf_error is None:
        _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_LNF_KEY)

    if prev_deco is not None:
        prev_library, prev_theme, prev_border = prev_deco.split("|", 2)
        for key, prev in (
            ("library", prev_library),
            ("theme", prev_theme),
            ("BorderSize", prev_border),
        ):
            if prev == _UNSET:
                _kdelete(kw, key)
            else:
                _kwrite(kw, key, prev)
        _restore_buttons(kw, kr)
        _kdelete(kw, _PREV_DECO_KEY)

    colors_error: ApplyError | None = None
    if prev_colors is not None:
        if prev_colors == _UNSET:
            # No explicit user-layer scheme before themey: delete the key
            # we wrote so the (restored) Look-and-Feel's kdedefaults layer
            # takes over again.
            _cfg_delete(kw, _KDEGLOBALS, _GENERAL_GROUP, _COLORSCHEME_KEY)
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_COLORS_KEY)
        else:
            plasma_apply_colors = _which("plasma-apply-colorscheme")
            try:
                _run_checked(
                    [plasma_apply_colors, prev_colors],
                    f"plasma-apply-colorscheme {prev_colors}",
                )
                _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_COLORS_KEY)
            except ApplyError as exc:
                colors_error = exc
                log.warning(
                    "could not reapply the previous color scheme %r (%s) — "
                    "keeping the marker so a later `themey apply --revert` "
                    "can retry it",
                    prev_colors, exc,
                )

    icons_error: ApplyError | None = None
    if prev_icons is not None:
        try:
            if prev_icons == _UNSET:
                # No explicit user-layer icon theme before themey: delete
                # the key we wrote so the restored Look-and-Feel's defaults
                # take over again.
                _cfg_delete(kw, _KDEGLOBALS, _ICONS_GROUP, _ICON_THEME_KEY)
            else:
                _cfg_write(kw, _KDEGLOBALS, _ICONS_GROUP, _ICON_THEME_KEY, prev_icons)
            _notify_icons_changed()
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ICONS_KEY)
        except ApplyError as exc:
            icons_error = exc
            log.warning(
                "could not restore the previous icon theme %r (%s) — keeping "
                "the marker so a later `themey apply --revert` can retry it",
                prev_icons, exc,
            )

    widget_error: ApplyError | None = None
    if prev_widget is not None:
        try:
            if prev_widget == _UNSET:
                # No explicit user-layer application style before themey:
                # delete the key we wrote so the restored Look-and-Feel's
                # kdedefaults layer takes over again.
                _cfg_delete(kw, _KDEGLOBALS, _KDE_GROUP, _WIDGET_STYLE_KEY)
            else:
                _cfg_write(
                    kw, _KDEGLOBALS, _KDE_GROUP, _WIDGET_STYLE_KEY, prev_widget
                )
            _notify_style_changed()
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_WIDGET_STYLE_KEY)
        except ApplyError as exc:
            widget_error = exc
            log.warning(
                "could not restore the previous application style %r (%s) — "
                "keeping the marker so a later `themey apply --revert` can "
                "retry it",
                prev_widget, exc,
            )

    plasma_error: ApplyError | None = None
    if prev_plasma is not None:
        if prev_plasma == _UNSET:
            # No explicit user-layer style before themey: delete the key we
            # wrote so the (restored) Look-and-Feel's defaults take over.
            _cfg_delete(kw, _PLASMARC, _PLASMA_THEME_GROUP, _PLASMA_NAME_KEY)
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PLASMA_KEY)
        else:
            plasma_apply_style = _which("plasma-apply-desktoptheme")
            try:
                _run_checked(
                    [plasma_apply_style, prev_plasma],
                    f"plasma-apply-desktoptheme {prev_plasma}",
                )
                _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PLASMA_KEY)
            except ApplyError as exc:
                plasma_error = exc
                log.warning(
                    "could not reapply the previous Plasma Style %r (%s) — "
                    "keeping the marker so a later `themey apply --revert` "
                    "can retry it",
                    prev_plasma, exc,
                )

    # Furniture removal BEFORE the panel-mode restore, so the mode-restore
    # script iterates only surviving panels.
    furniture_error = _remove_furniture(kw, kr, _furniture_specs())

    # Parked top panels back where they were — after the dragbar is gone
    # (so the top edge is free again) and before the length-mode/floating
    # restores, which iterate the now-visible panels.
    top_error: ApplyError | None = None
    if prev_top is not None:
        try:
            _unpark_top_panels(prev_top)
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_TOP_PANELS_KEY)
        except ApplyError as exc:
            top_error = exc
            log.warning(
                "could not restore the parked top panel(s) (%s) — keeping "
                "the marker so a later `themey apply --revert` can retry it",
                exc,
            )

    # Desktop grid back to the recorded shape (_restore_desktop_rows —
    # config AND live rows).
    rows_error: ApplyError | None = None
    if prev_rows is not None:
        try:
            _restore_desktop_rows(kw, prev_rows)
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY)
        except ApplyError as exc:
            rows_error = exc
            log.warning(
                "could not restore the previous desktop grid (%s) — "
                "keeping the marker so a later `themey apply --revert` "
                "can retry it",
                exc,
            )

    panels_error: ApplyError | None = None
    if prev_panels is not None:
        try:
            _restore_panel_length_modes(kw, prev_panels)
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PANELS_KEY)
        except ApplyError as exc:
            panels_error = exc
            log.warning(
                "could not restore the previous panel length modes (%s) — "
                "keeping the marker so a later `themey apply --revert` "
                "can retry it",
                exc,
            )

    floating_error: ApplyError | None = None
    if prev_floating is not None:
        try:
            _restore_panel_floating(kw, prev_floating)
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, _PREV_FLOATING_KEY)
        except ApplyError as exc:
            floating_error = exc
            log.warning(
                "could not restore the previous panel floating states (%s) — "
                "keeping the marker so a later `themey apply --revert` "
                "can retry it",
                exc,
            )

    _reconfigure()

    errors = (
        lnf_error,
        colors_error,
        icons_error,
        widget_error,
        plasma_error,
        furniture_error,
        top_error,
        rows_error,
        panels_error,
        floating_error,
    )
    if any(e is not None for e in errors):
        failed = " and ".join(str(e) for e in errors if e is not None)
        raise ApplyError(
            "everything else was restored, but part of the previous state "
            f"could not be reapplied: {failed} — run "
            "`themey apply --revert` again to retry it"
        )
    return True
