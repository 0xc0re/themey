"""report.txt scaffold (Phase 1 — Phase 2 fills full semantics).

Four sections (per REPORT-01):
  - Preserved: what mapped 1:1 from E16 to KDE
  - Approximated: what was lossy and how (e.g. dropped states)
  - Skipped: what we couldn't convert and why (e.g. non-DEFAULT borders)
  - Apply: how to make KWin actually show the borders (v2 clamp caveat)

Hard limit ~50 lines (per UX Pitfalls in PITFALLS.md). Phase 1 ships the
scaffold; Phase 2 fills the full Preserved/Approximated/Skipped semantics
for color and wallpaper.
"""
from __future__ import annotations

from pathlib import Path

from .generate.cursors import CursorTheme
from .generate.decoration_svg import strip_thicknesses
from .ir import Theme, WallpaperSpec
from .kwin import recommended_border_size


def write(
    theme: Theme,
    out_path: Path,
    backend: str = "svg",
    wallpaper_specs: tuple[WallpaperSpec, ...] | None = None,
    cursor_theme: CursorTheme | None = None,
    lnf_id: str | None = None,
    lnf_dir: Path | None = None,
    desktop_theme_id: str | None = None,
) -> Path:
    """Write report.txt for *theme* to *out_path*.

    ``backend`` ("svg" | "qml" | "both") selects which Apply guidance is
    emitted. ``wallpaper_specs`` is the set of wallpapers *actually
    installed* — pipeline.py passes the subset of ``theme.wallpaper_specs``
    that survived ``write_package`` (some may fail: oversized, corrupt,
    unopenable) so the status line below never overstates what's on disk.
    Defaults to ``theme.wallpaper_specs`` itself for callers that report
    straight from analysis (no install step ran, so there's nothing to
    have failed). ``cursor_theme`` is the written XCursor theme, or None
    when there was nothing to install — the ``cursors:`` notes say why.
    ``lnf_id``/``lnf_dir`` are the assembled Look-and-Feel bundle's
    ``KPlugin.Id`` and install path (Phase D); pass None for a caller that
    never assembled one (e.g. reporting straight from analysis, no install
    step ran). ``desktop_theme_id`` is the installed Plasma Style package's
    id, or None when the style failed to build (the ``plasmastyle:`` notes
    say why). Returns *out_path* so callers can chain.
    """
    want_qml = backend in ("qml", "both")
    want_svg = backend in ("svg", "both")
    lines: list[str] = []
    lines.append(f"# themey conversion report: {theme.display_name}")
    lines.append("")
    lines.append(f"Source theme: {theme.name}")
    lines.append(f"Scale: {theme.scale}x")
    lines.append(f"Backend: {backend}")
    lines.append("")

    # ------------------------------------------------------------------ #
    # Preserved
    # ------------------------------------------------------------------ #
    lines.append("## Preserved")
    lines.append(
        f"- DEFAULT border ({theme.border.name}) "
        f"with {len(theme.border.parts)} parts"
    )
    if theme.left_buttons or theme.right_buttons:
        lines.append(
            f"- Buttons found: left={theme.left_buttons or '(none)'}"
            f"  right={theme.right_buttons or '(none)'} "
            "(order on screen follows kwinrc ButtonsOnLeft/Right, not the theme)"
        )
    if "TEXT1" in theme.tclasses:
        t = theme.tclasses["TEXT1"]
        if t.fg_active:
            lines.append(
                f"- Titlebar text colors: "
                f"active={t.fg_active} inactive={t.fg_normal}"
            )
    lines.append(
        f"- {len(theme.iclasses)} image class(es) parsed; "
        "borders embedded as base64 PNG inside decoration.svg"
    )
    lines.append(
        "- Color scheme sampled from the border art and installed as "
        f"'{theme.display_name} (themey)' — pick it under System "
        "Settings -> Colors. Sources are listed below."
    )
    if theme.wallpaper_specs:
        found = theme.wallpaper_specs
        installed = wallpaper_specs if wallpaper_specs is not None else found
        if installed:
            tiled = sum(1 for w in installed if w.fill_mode == "tiled")
            scaled = len(installed) - tiled
            if len(installed) == len(found):
                lines.append(
                    f"- Wallpaper: {len(installed)} background image(s) "
                    f"installed as Plasma wallpaper packages ({tiled} "
                    f"tiled, {scaled} scaled) — pick one under System "
                    "Settings -> Wallpaper."
                )
            else:
                failed = len(found) - len(installed)
                lines.append(
                    f"- Wallpaper: {len(installed)} of {len(found)} "
                    "background image(s) installed as Plasma wallpaper "
                    f"packages ({tiled} tiled, {scaled} scaled); {failed} "
                    "failed to convert — see wallpaper: notes below. Pick "
                    "one under System Settings -> Wallpaper."
                )
        else:
            lines.append(
                f"- Wallpaper: {len(found)} background image(s) found in "
                "desktops.cfg but none could be converted — see "
                "wallpaper: notes below."
            )
    else:
        lines.append(
            "- Wallpaper: no background images found in desktops.cfg; "
            "the desktop wallpaper is left alone."
        )
    if cursor_theme is not None:
        lines.append(
            f"- Pointer theme: {len(cursor_theme.shapes)} cursor shape(s) "
            f"({', '.join(sorted(cursor_theme.shapes))}) converted to "
            f"XCursor at 1x/2x/3x and installed as "
            f"'{theme.display_name} (themey)' — pick it under System "
            "Settings -> Colors & Themes -> Cursors. Shapes E16 never "
            "defined fall back to Breeze."
        )
    else:
        lines.append(
            "- Pointer theme: not installed; the system cursor is left "
            "alone — see cursors: notes below."
        )
    if desktop_theme_id is not None:
        lines.append(
            f"- Plasma Style: panel, popup, tooltip and widget chrome "
            f"generated from the theme's own art (id {desktop_theme_id}); "
            "anything without E16 counterpart art falls back to Breeze, "
            "tinted by the bundled colors. Pick it under System Settings "
            "-> Colors & Themes -> Plasma Style."
        )
    else:
        lines.append(
            "- Plasma Style: not installed; the panel and popups keep "
            "their current look — see plasmastyle: notes below."
        )
    if lnf_id is not None:
        lines.append(
            f"- Everything above is bundled as one Plasma Global Theme "
            f"('{theme.display_name} (themey)', id {lnf_id}) — apply the "
            f"whole desktop look in one step with `themey apply "
            f"{theme.name}`, or pick it under System Settings -> "
            "Appearance -> Global Theme."
        )
    lines.append("")

    # ------------------------------------------------------------------ #
    # Approximated
    # ------------------------------------------------------------------ #
    lines.append("## Approximated")
    if want_qml:
        lines.append(
            "- QML backend: E16 part geometry, text-sized title plaques, "
            "side-border buttons and theme TTF fonts are reproduced 1:1; "
            "borders are NOT clamped by the KWin Border-size bracket."
        )
        lines.append(
            "- Cursor & drag: the cursor is an arrow over every themed "
            "button (the decoration extends KWin's titleBar rect to cover "
            "them); border strips hosting buttons act as titlebar for "
            "drag/double-click; resize stays on the bottom border and on "
            "side borders below the lowest button."
        )
    if want_svg:
        lines.append(
            "- Title font (SVG backend): Aurorae cannot override the title "
            "font; system default is used. Source font preserved as a "
            "name-only note (Aurorae limitation)."
        )

    # Surface layout-decision notes (aurorae_rc:, colors:, composite:,
    # qmldeco:) BEFORE the truncated-state-drop bucket so they don't get
    # buried past line 20.
    _layout_prefixes = (
        "aurorae_rc:", "bundle:", "colors:", "composite:", "cursors:",
        "plasmastyle:", "qmldeco:", "wallpaper:",
    )
    layout_notes = [n for n in theme.notes if n.startswith(_layout_prefixes)]
    state_notes = [n for n in theme.notes if not n.startswith(_layout_prefixes)]
    for note in layout_notes:
        lines.append(f"- {note}")

    lines.append(
        "- E16's 8-state image model collapsed to Aurorae's 2-state "
        "model. Sticky and disabled variants are dropped:"
    )
    # First 20 dropped-state notes (from Theme.notes)
    for note in state_notes[:20]:
        lines.append(f"  - {note}")
    if len(state_notes) > 20:
        lines.append(f"  ... ({len(state_notes) - 20} more)")
    lines.append(
        f"- Pixel-art borders upscaled {theme.scale}x with NEAREST. "
        "Pixel-perfect on 1.0x/2.0x/3.0x display scales; "
        "approximate at fractional 1.25x/1.5x/1.75x."
    )
    lines.append("")

    # ------------------------------------------------------------------ #
    # Skipped
    # ------------------------------------------------------------------ #
    lines.append("## Skipped")
    if theme.skipped_borders:
        lines.append(
            f"- Non-DEFAULT borders: "
            f"{', '.join(theme.skipped_borders)} "
            "(Aurorae has only one window decoration; DEFAULT was used.)"
        )
    else:
        lines.append("- No additional border types found.")
    lines.append(
        "- Semantic colors (link / visited / error / warning / success) "
        "stay Breeze stock: tinting them to the theme would make them "
        "misreport meaning."
    )
    lines.append("")

    # ------------------------------------------------------------------ #
    # Apply
    # ------------------------------------------------------------------ #
    lines.append("## Apply")
    if lnf_id is not None and want_qml:
        lines.append(
            f"- `themey apply {theme.name}` applies the full Global Theme "
            f"(id {lnf_id}) in one step: decoration, colors, wallpaper and "
            "cursors together. Add --deco-only for the old deco-only "
            "behavior, or `themey apply --revert` to restore whatever "
            "global theme was active before. Manual equivalent: System "
            "Settings -> Appearance -> Global Theme."
        )
    elif lnf_id is not None:
        lines.append(
            f"- `themey apply {theme.name} --deco-only --backend svg` "
            "applies this theme's decoration — the full `themey apply "
            "NAME` needs the QML decoration package, which this svg-only "
            f"convert didn't build. The installed Global Theme (id {lnf_id}) "
            "still carries the color scheme, wallpaper, and cursors; apply "
            "those via System Settings -> Appearance -> Global Theme, or "
            "`themey apply --revert` to undo."
        )
    if want_qml:
        lines.append(
            "- Decoration only (QML backend): installed as a KWin/"
            "Decoration package under ~/.local/share/kwin/decorations/ and "
            "loaded by the v1 Aurorae plugin (org.kde.kwin.aurorae — "
            "legacy but present in Plasma master; QML packages are exempt "
            "from the v1->v2 migration). Pick it in Window Decorations for "
            "deco-only control. Border sizes come from the theme, unclamped."
        )
    if want_svg:
        lines.append(
            "- Both Aurorae plugins in Plasma 6.6 (org.kde.kwin.aurorae and "
            ".v2) clamp BorderLeft/Right/Bottom to the System Settings 'Border "
            "size' bracket (Normal = 4-6 px ... Oversized = 36-48 px); only the "
            "title band is theme-controlled. Corner art wider than the side is "
            "folded into the title band so it survives the clamp."
        )
        thick = strip_thicknesses(theme)
        rec = recommended_border_size(thick["left"], thick["right"], thick["bottom"])
        lines.append(
            f"- SVG backend: this theme's sides are {thick['left']}/{thick['right']}/"
            f"{thick['bottom']} px (L/R/B) -> set Window Decorations -> Border "
            f"size = {rec}, or run `themey apply {theme.name} --deco-only "
            f"--backend svg` (picks {rec}; override with --border-size, add "
            "--legacy-plugin for the v1 QML plugin, which also honours the "
            "text-shadow keys)."
        )
        lines.append(
            "- Button order is global kwinrc state; `themey apply` (SVG "
            "backend) sets it to this theme's E16 binning "
            f"(Left={theme.left_buttons or '(none)'} "
            f"Right={theme.right_buttons or '(none)'}), records your previous "
            "layout, and `themey apply Breeze` restores it. Skip with "
            "--keep-buttons or adjust under Window Decorations -> Titlebar "
            "Buttons. The QML backend draws its own buttons and ignores this."
        )
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
