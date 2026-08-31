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

from .generate.decoration_svg import strip_thicknesses
from .ir import Theme
from .kwin import recommended_border_size


def write(theme: Theme, out_path: Path) -> Path:
    """Write report.txt for *theme* to *out_path*.

    Returns *out_path* so callers can chain.
    """
    lines: list[str] = []
    lines.append(f"# themey conversion report: {theme.display_name}")
    lines.append("")
    lines.append(f"Source theme: {theme.name}")
    lines.append(f"Scale: {theme.scale}x")
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
    lines.append("")

    # ------------------------------------------------------------------ #
    # Approximated
    # ------------------------------------------------------------------ #
    lines.append("## Approximated")
    lines.append(
        "- Title font: Aurorae cannot override the title font; "
        "system default is used. Source font preserved as a "
        "name-only note (Aurorae limitation)."
    )

    # Surface layout-decision notes (aurorae_rc:, composite:, etc.) BEFORE
    # the truncated-state-drop bucket so they don't get buried past line 20.
    layout_notes = [n for n in theme.notes if n.startswith(("aurorae_rc:", "composite:"))]
    state_notes = [n for n in theme.notes if not n.startswith(("aurorae_rc:", "composite:"))]
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
        "- Color scheme: deferred to later phase (COLORS-01 / Phase 2)."
    )
    if theme.wallpapers:
        lines.append(
            f"- Wallpaper: {len(theme.wallpapers)} background image(s) "
            "found in desktops.cfg; install deferred to Phase 2."
        )
    else:
        lines.append(
            "- Wallpaper: deferred to later phase (WALLPAPER-01 / Phase 2)."
        )
    if theme.cursors:
        lines.append(
            f"- XCursor pointer theme: {len(theme.cursors)} __CURSOR "
            "block(s) parsed but emission deferred to Phase 3."
        )
    else:
        lines.append(
            "- XCursor pointer theme: deferred to later phase "
            "(CURSORS-01 / Phase 3)."
        )
    lines.append(
        "- Plasma Look-and-Feel bundle: deferred to later phase "
        "(BUNDLE-01 / Phase 4)."
    )
    lines.append("")

    # ------------------------------------------------------------------ #
    # Apply
    # ------------------------------------------------------------------ #
    lines.append("## Apply")
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
        f"- This theme's sides are {thick['left']}/{thick['right']}/"
        f"{thick['bottom']} px (L/R/B) -> set Window Decorations -> Border "
        f"size = {rec}, or run `themey apply {theme.name}` (picks {rec}; "
        "override with --border-size, add --legacy-plugin for the v1 QML "
        "plugin, which also honours the text-shadow keys)."
    )
    lines.append(
        "- Button order is global kwinrc state; `themey apply` sets it to "
        f"this theme's E16 binning (Left={theme.left_buttons or '(none)'} "
        f"Right={theme.right_buttons or '(none)'}), records your previous "
        "layout, and `themey apply Breeze` restores it. Skip with "
        "--keep-buttons or adjust under Window Decorations -> Titlebar "
        "Buttons."
    )
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
