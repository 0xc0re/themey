"""KWin / Aurorae facts shared by render, apply and report (leaf module).

Values come from the Plasma 6.6.6 sources (KDE/aurorae: v1/lib/auroraetheme.cpp
and v2/decorationtheme.cpp). Keep this module free of themey imports so both
``report`` (inside the pipeline) and ``render`` (which drives the pipeline)
can use it without an import cycle.
"""
from __future__ import annotations

PLUGINS: dict[str, str] = {
    "legacy": "org.kde.kwin.aurorae",
    "v2": "org.kde.kwin.aurorae.v2",
}
BORDER_SIZES: tuple[str, ...] = (
    "None", "NoSides", "Tiny", "Normal", "Large", "VeryLarge", "Huge",
    "VeryHuge", "Oversized",
)
# KWin's per-BorderSize clamp brackets for BorderLeft/Right/Bottom, from
# aurorae v1/lib/auroraetheme.cpp + v2/decorationtheme.cpp (Plasma 6.6.6).
# Both plugins apply them; only the title band is theme-controlled.
BORDER_SIZE_BRACKETS: dict[str, tuple[int, int]] = {
    "Tiny": (1, 4),
    "Normal": (4, 6),
    "Large": (6, 8),
    "VeryLarge": (8, 12),
    "Huge": (12, 20),
    "VeryHuge": (23, 30),
    "Oversized": (36, 48),
}


def recommended_border_size(border_left: int, border_right: int, border_bottom: int) -> str:
    """Smallest KWin BorderSize whose bracket ceiling fits the theme's sides.

    KWin clamps each side into ``[min, max]`` of the selected bracket, so the
    bracket whose ``max`` first covers the theme's widest side shows it
    unsquashed with the least padding.
    """
    need = max(border_left, border_right, border_bottom, 0)
    for name, (_lo, hi) in BORDER_SIZE_BRACKETS.items():
        if need <= hi:
            return name
    return "Oversized"


