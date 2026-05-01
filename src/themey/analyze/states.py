"""E16 -> Aurorae image-state collapse. Lossy by design; logs every drop.

E16 has up to 16 image-state cells; Aurorae has 2 (active, inactive)
plus 3 button SVG sub-states (default, hover, pressed). The 8-state
practical model (per WILBS-REFERENCE.md Section 2) maps as below.

Sticky variants and disabled drop with logged notes — Aurorae has no
per-desktop button state and no separate disabled rendering.
"""
from __future__ import annotations

from pathlib import Path

# Decoration states (titlebar/border per-focus)
DECORATION_STATE_MAP: dict[str, list[str]] = {
    "decoration-active": ["__NORMAL_ACTIVE", "__NORMAL"],  # fallback chain
    "decoration-inactive": ["__NORMAL"],  # never use _ACTIVE
}

# Per-button state (in button SVG; not decoration.svg)
BUTTON_STATE_MAP: dict[str, list[str]] = {
    "button-default": ["__NORMAL_ACTIVE", "__NORMAL"],
    "button-hover": ["__HILITED_ACTIVE", "__HILITED"],
    "button-pressed": ["__CLICKED_ACTIVE", "__CLICKED"],
}

# Always-dropped E16 states (no Aurorae target):
DROPPED_STATES: frozenset[str] = frozenset({
    "__NORMAL_STICKY",
    "__NORMAL_ACTIVE_STICKY",
    "__CLICKED_STICKY",
    "__CLICKED_ACTIVE_STICKY",
    "__HILITED_STICKY",
    "__HILITED_ACTIVE_STICKY",
    "__NORMAL_ACTIVE_CLICKED",
    "__DISABLED",
})


def collapse_image_states(
    state_dict: dict[str, Path | None],
    target: str,
    notes: list[str],
    context_label: str,
) -> Path | None:
    """Pick the source path for a given Aurorae target via fallback chain.

    Args:
        state_dict: maps E16 state keyword (e.g. "__NORMAL_ACTIVE") to a
                    Path or None. Keys not present in the dict are treated
                    as "not declared" by the source theme.
        target: Aurorae target key — one of DECORATION_STATE_MAP or
                BUTTON_STATE_MAP.
        notes: mutable list to append drop-records to. (Theme.notes is
               passed in by the analyze pipeline.)
        context_label: e.g. "TITLE_BAR_HORIZONTAL" or "BUTTON_KILL" — used
                       in note text so the user knows which iclass dropped
                       which state.

    Returns:
        The first path in the chain that is non-None and exists in the
        state_dict, or None if no chain member resolves.
    """
    chain = DECORATION_STATE_MAP.get(target) or BUTTON_STATE_MAP.get(target) or []
    result: Path | None = None
    for src_state in chain:
        path = state_dict.get(src_state)
        if path is not None:
            result = path
            break

    # Log dropped states — every state in state_dict that is in DROPPED_STATES
    for src_state, path in state_dict.items():
        if src_state in DROPPED_STATES and path is not None:
            notes.append(
                f"{context_label}: {src_state} dropped "
                f"(no Aurorae target for sticky/disabled/clicked-active variants)"
            )
    return result
