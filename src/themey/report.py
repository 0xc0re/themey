"""report.txt scaffold (Phase 1 — Phase 2 fills full semantics).

Three sections (per REPORT-01):
  - Preserved: what mapped 1:1 from E16 to KDE
  - Approximated: what was lossy and how (e.g. dropped states)
  - Skipped: what we couldn't convert and why (e.g. non-DEFAULT borders)

Hard limit ~50 lines (per UX Pitfalls in PITFALLS.md). Phase 1 ships the
scaffold; Phase 2 fills the full Preserved/Approximated/Skipped semantics
for color and wallpaper.
"""
from __future__ import annotations

from pathlib import Path

from .ir import Theme


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
            f"- Button layout: LeftButtons={theme.left_buttons or '(empty)'}"
            f"  RightButtons={theme.right_buttons or '(empty)'}"
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
    lines.append(
        "- Wallpaper: deferred to later phase (WALLPAPER-01 / Phase 2)."
    )
    lines.append(
        "- XCursor pointer theme: deferred to later phase "
        "(CURSORS-01 / Phase 3)."
    )
    lines.append(
        "- Plasma Look-and-Feel bundle: deferred to later phase "
        "(BUNDLE-01 / Phase 4)."
    )
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
