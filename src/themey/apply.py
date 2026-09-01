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
  change — ends a tiled apply with an automatic plasmashell restart
  (:func:`_restart_plasmashell`, opt-out ``restart_shell=False`` / CLI
  ``--no-restart-shell``).

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
user-layer color scheme (``PrevColorScheme``) and Plasma Style (plasmarc
``[Theme] name``, marker ``PrevPlasmaTheme``) — all ``@unset``-sentineled,
all written only once,
so a second ``themey apply`` never clobbers the ORIGINAL baseline with an
already-themey'd one. :func:`revert` (CLI ``themey apply --revert``) reads
those markers back, reapplies the recorded Look-and-Feel package (no
special-casing — a real user's baseline is typically a third-party theme,
not Breeze), restores the deco triple and the button layout, then deletes
both markers. No markers present means no prior full apply on this
machine: a friendly no-op, not an error.

:func:`apply_full` also creates E16's left-edge furniture — TWO vertical
content-sized panels via plasmashell desktop scripting
(:func:`_ensure_furniture`): a thick pager panel hugging the top-left
corner (E16's pager window spot; two panels because pager cell size is
panel thickness ÷ desktop-grid columns while task-icon size IS the panel
thickness, so one shared panel cannot serve both) and a slim iconbox
panel hugging the bottom-left whose icons-only task manager shows only
MINIMIZED windows, E16's iconbox behavior. The ``[Themey] PagerPanel``
and ``IconboxPanel`` markers are the ones that are NOT ``Prev*``
baselines: each records a themey-CREATED artifact (that panel's
containment id), so it is overwritten when the recorded panel no longer
exists (recreate), left alone when it does (idempotent second apply), and
deleted when :func:`revert` removes the panel. Existing panels are never
touched beyond the fit-content step. The desktop grid is set to one
column (kwinrc ``[Desktops] Rows = Number`` plus the live D-Bus rows —
:func:`_set_desktop_grid_column`) so the stacked pager cells fill the
panel box; ``PrevDesktopRows`` is the record-once baseline and
:func:`revert` restores it, since this changes desktop-switching
direction.

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
from pathlib import Path

from . import paths
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
#: themey's own kdeglobals group for its one marker key.
_THEMEY_GROUP = "Themey"
#: Vanilla plasmarc location of the active Plasma Style (desktop theme).
_PLASMARC = "plasmarc"
_PLASMA_THEME_GROUP = "Theme"
_PLASMA_NAME_KEY = "name"

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
_ICONBOX_HEIGHT = 60
_PAGER_KEY = "PagerPanel"
_PAGER_WIDGET = "org.kde.plasma.pager"
#: Thick enough that two side-by-side cells (a 1x2 desktop grid) land
#: near E16's ~64px pager cells.
_PAGER_HEIGHT = 130
#: Baseline for the desktop-grid change (kwinrc [Desktops] Rows): one
#: desktop per pager row so the stacked cells fill the panel box.
_PREV_ROWS_KEY = "PrevDesktopRows"
_DESKTOPS_GROUP = "Desktops"


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


def _panel_script(alignment: str, height: int, widgets: str) -> str:
    """Creation script for one furniture panel; prints the new panel id.

    ``qdbus`` exits 0 even when the script throws, so the printed id is
    the real success signal. ``p.floating`` is wrapped in try/catch: an
    unscriptable property assignment would otherwise kill the whole
    script.
    """
    return (
        "var p = new Panel;"
        " p.location = 'left';"
        f" p.alignment = '{alignment}';"
        f" p.height = {height};"
        " p.hiding = 'none';"
        " p.lengthMode = 'fit';"
        # A scripted `new Panel` starts with minimumLength == maximumLength
        # == the full screen dimension, and setting lengthMode='fit' does
        # NOT clear them — the panel then draws as a full-height column
        # around a few px of content (verified live 2026-08-31). Only the
        # minimum needs clearing; fit computes the real length.
        " p.minimumLength = 0;"
        " try { p.floating = false; } catch (e) {}"
        f"{widgets}"
        " print(p.id);"
    )


def _furniture_specs() -> tuple[tuple[str, str, str], ...]:
    """``(marker key, human name, creation script)`` per themey panel.

    Pager panel: top-left, thick, one pager — E16's pager window spot.
    Iconbox panel: bottom-left, slim, an icons-only task manager showing
    ONLY minimized windows — E16's iconbox: icons appear on iconify,
    vanish on restore. ``launchers`` is cleared because icontasks ships
    default pinned launchers.
    """
    pager = _panel_script(
        "left",
        _PAGER_HEIGHT,
        f" var w = p.addWidget('{_PAGER_WIDGET}');"
        # Multi-head virtual desktops are ultrawide (two 16:9 screens =
        # 3.55:1) and squash the cells to slivers; per-screen cells keep
        # desktop aspect readable (verified live 2026-08-31).
        " w.currentConfigGroup = ['General'];"
        " w.writeConfig('showOnlyCurrentScreen', true);"
        " w.reloadConfig();",
    )
    iconbox = _panel_script(
        "right",
        _ICONBOX_HEIGHT,
        f" var w = p.addWidget('{_ICONBOX_WIDGET}');"
        " w.currentConfigGroup = ['General'];"
        " w.writeConfig('showOnlyMinimized', true);"
        " w.writeConfig('launchers', '');"
        " w.reloadConfig();",
    )
    return (
        (_PAGER_KEY, "pager panel", pager),
        (_ICONBOX_KEY, "iconbox panel", iconbox),
    )


def _ensure_furniture(kw: str, kr: str) -> None:
    """Create each E16 furniture panel unless its recorded one is alive.

    Each marker is validated :func:`_is_panel_id` before it is ever
    interpolated into a plasmashell script — kdeglobals is user-editable,
    and a tampered marker must not become script injection. A non-digit
    or dead-panel marker is simply overwritten by the fresh panel's id,
    written only AFTER a successful create so a failed create leaves no
    stale marker (an earlier panel's marker survives the failure, so a
    retry skips it instead of doubling it).
    """
    for key, name, script in _furniture_specs():
        marker = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, key)
        if marker is not None and _is_panel_id(marker):
            alive = _evaluate_plasma_script(
                f"print(panelById({marker}) ? 'exists' : 'missing');",
                f"plasmashell {name} existence check",
            )
            if alive == "exists":
                continue
        reply = _evaluate_plasma_script(
            script, f"plasmashell {name} creation script"
        )
        if not _is_panel_id(reply):
            raise ApplyError(
                f"plasmashell {name} creation script did not print a "
                f"panel id (got {reply!r}) — the {name} was not created"
            )
        _cfg_write(kw, _KDEGLOBALS, _THEMEY_GROUP, key, reply)


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


def _restart_plasmashell() -> None:
    """Restart plasmashell so a tiled wallpaper actually repaints.

    plasmashell 6.6.6 does NOT repaint fill-mode from any scripting write
    (verified live 2026-08-31: FillMode alone, +Image rewrite,
    +reloadConfig, even an Image swap-away-and-back all left the render
    pixel-identical) — only the first paint after a shell restart or a
    manual KCM toggle honors the new mode. The theme is fully applied by
    the time this runs, so a failure (or a machine without systemd) is a
    logged warning telling the user to restart manually, never a failed
    apply.
    """
    systemctl = shutil.which("systemctl")
    if systemctl is None:
        log.warning(
            "systemctl not found — restart plasmashell manually (or log "
            "out and back in) for the tiled wallpaper to repaint"
        )
        return
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


def _read_default_wallpaper_id(lnf_dir: Path) -> str | None:
    """The ``[Wallpaper] Image=`` value from an installed bundle's
    ``contents/defaults``, or None when the bundle has no wallpaper group
    (unreadable file, or a theme with no convertible wallpaper)."""
    defaults = lnf_dir / "contents" / "defaults"
    if not defaults.is_file():
        return None
    cp = configparser.RawConfigParser()
    cp.optionxform = staticmethod(str)  # type: ignore[assignment]
    try:
        cp.read(defaults, encoding="utf-8")
        return cp.get("Wallpaper", "Image")
    except (configparser.Error, KeyError):
        return None


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
) -> None:
    """Apply the whole installed Look-and-Feel bundle for *name* (the CLI
    default), always via the QML deco backend.

    Order (see module docstring): verify both the Look-and-Feel bundle and
    the QML decoration package are installed → record the pre-themey
    baselines (once) → ``plasma-apply-lookandfeel -a themey_<slug>`` (NEVER
    ``--resetLayout``, which would blow away unrelated layout state) →
    ``plasma-apply-colorscheme themey_<slug>`` when the scheme is installed
    (REQUIRED: the LnF apply does not touch an explicit user-layer
    ``[General] ColorScheme`` — see :func:`_record_prev_colorscheme`) →
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
    :data:`_WALLPAPER_FILL_MODE_INTS`) → one ``qdbus`` reconfigure,
    last. Every panel is set to fit-content and un-floated just BEFORE the
    wallpaper fix-up (:func:`_set_panels_fit` — E16's iconbox/dragbar are
    content-sized docked strips, and a full-width or floating bar reads as
    Plasma, not E16; previous modes recorded once in
    ``PrevPanelLengthModes``/``PrevPanelFloating``): the wallpaper step
    is the likeliest to raise, and a failed apply should still have
    delivered the panel feel. The dedicated iconbox panel is created right
    after the fit step (:func:`_ensure_iconbox` — after, so it never
    pollutes the ``PrevPanelLengthModes`` baseline; before the wallpaper
    fix-up for the same survive-a-wallpaper-failure reason).

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

    scheme_file = paths.color_schemes() / f"{pkg_id}.colors"
    has_colors = scheme_file.is_file()
    has_style = (paths.desktop_themes() / pkg_id / "metadata.json").is_file()

    _record_prev_lookandfeel(kw, kr)
    _record_prev_deco(kw, kr)
    if has_colors:
        _record_prev_colorscheme(kw, kr)
    if has_style:
        _record_prev_plasmatheme(kw, kr)

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

    if has_style:
        # Same user-layer shadowing as the color scheme (the reference
        # machine's plasmarc has an explicit name=Otto), so the explicit
        # apply is required, not belt-and-braces. The cache clear must come
        # first: plasmashell would otherwise repaint from the stale
        # Version-keyed kcache of a previous conversion.
        clear_style_cache(pkg_id)
        plasma_apply_style = _which("plasma-apply-desktoptheme")
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
    _set_desktop_grid_column(kw, kr)
    _ensure_furniture(kw, kr)

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
    # Only when a tile mode was scripted: nothing else needs the repaint,
    # and a tool-applied fill should not flicker the desktop.
    if restart_shell and needs_restart:
        _restart_plasmashell()


def revert() -> bool:
    """``themey apply --revert``: restore the pre-``apply_full`` state.

    Reads the markers :func:`_record_prev_lookandfeel`/
    :func:`_record_prev_deco`/:func:`_record_prev_colorscheme`/
    :func:`_record_prev_plasmatheme` left behind
    (the color scheme and Plasma Style restores mirror the Look-and-Feel
    one: ``@unset`` → delete the user-layer key; a failure keeps the
    marker so a later revert retries it), reapplies the recorded
    Look-and-Feel package (no special-casing here — a real user's baseline
    is typically a third-party theme, e.g.
    ``com.github.vinceliuice.MacVentura-Dark``, not Breeze), restores the
    deco triple (deleting any key that was ``@unset`` before), restores
    the button layout, removes the themey-created iconbox panel (before
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
    prev_panels = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_PANELS_KEY)
    prev_floating = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_FLOATING_KEY)
    prev_furniture = {
        key: _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, key)
        for key, _name, _script in _furniture_specs()
    }
    prev_rows = _cfg_read(kr, _KDEGLOBALS, _THEMEY_GROUP, _PREV_ROWS_KEY)
    if (
        prev_deco is None
        and prev_lnf is None
        and prev_colors is None
        and prev_plasma is None
        and prev_panels is None
        and prev_floating is None
        and prev_rows is None
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
    # script iterates only surviving panels. A missing panel prints
    # 'absent' — still success, marker deleted. The printed sentinel is
    # the real success signal (qdbus exits 0 even when the script throws,
    # and the marker is the ONLY handle on the created panel — deleting it
    # on a thrown script would leak the panel with no retry). A non-digit
    # (tampered) marker is never interpolated: just dropped.
    iconbox_error: ApplyError | None = None
    for key, name, _script in _furniture_specs():
        prev_panel = prev_furniture[key]
        if prev_panel is None:
            continue
        if _is_panel_id(prev_panel):
            try:
                reply = _evaluate_plasma_script(
                    f"var p = panelById({prev_panel});"
                    " if (p) { p.remove(); print('removed'); }"
                    " else { print('absent'); }",
                    f"plasmashell {name} removal script",
                )
                if reply not in ("removed", "absent"):
                    raise ApplyError(
                        f"plasmashell {name} removal script did not "
                        f"confirm removal (got {reply!r}) — the {name} "
                        "may still be present"
                    )
                _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, key)
            except ApplyError as exc:
                iconbox_error = exc if iconbox_error is None else iconbox_error
                log.warning(
                    "could not remove the themey %s (%s) — keeping the "
                    "marker so a later `themey apply --revert` can retry "
                    "it",
                    name, exc,
                )
        else:
            _cfg_delete(kw, _KDEGLOBALS, _THEMEY_GROUP, key)

    # Desktop grid back to the recorded shape — config AND live rows
    # (see _set_live_desktop_rows); '@unset' deletes the key and restores
    # KWin's default single row.
    rows_error: ApplyError | None = None
    if prev_rows is not None:
        try:
            if prev_rows == _UNSET:
                _cfg_delete(kw, "kwinrc", _DESKTOPS_GROUP, "Rows")
                _set_live_desktop_rows("1")
            elif prev_rows.isascii() and prev_rows.isdigit():
                _cfg_write(kw, "kwinrc", _DESKTOPS_GROUP, "Rows", prev_rows)
                _set_live_desktop_rows(prev_rows)
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
        plasma_error,
        iconbox_error,
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
