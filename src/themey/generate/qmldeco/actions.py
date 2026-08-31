"""E16 part action → QML DecorationButton kind mapping.

Unlike the SVG backend (which bins buttons into Aurorae's global
LeftButtons/RightButtons strings), the QML backend keeps every part at its
declared position and only needs to know *which window request* a click
fires. The mapping mirrors chris's plan: KILL/CLOSE→close,
ICONIFY→minimize, MAX→maximizeRestore, SHADE→shade, STICK→onAllDesktops,
KEEP_ABOVE/BELOW→keepAbove/keepBelow, MENU→menu.

ACTION_MOVE / ACTION_RESIZE* / unknown aclasses are plain chrome —
KDecoration gives move-drag and edge-resize on non-button decoration area
for free, so those parts render as passive imagery.

The fallback tier reuses the SVG backend's iclass-pattern table
(analyze/buttons.py ICLASS_PATTERN_TO_BUTTON) so both backends agree on
what counts as a button when __ACLASS is absent.
"""
from __future__ import annotations

from themey.analyze.buttons import ICLASS_PATTERN_TO_BUTTON
from themey.ir import ButtonPart

# Kind strings are the runtime vocabulary: ThemeyButton.qml maps them onto
# DecorationOptions.DecorationButton* enum values.
ACLASS_TO_KIND: dict[str, str] = {
    "ACTION_CLOSE": "close",
    "ACTION_KILL": "close",
    "ACTION_ICONIFY": "minimize",
    "ACTION_MAX": "maximizeRestore",
    "ACTION_SHADE": "shade",
    "ACTION_STICK": "onAllDesktops",
    "ACTION_KEEP_ABOVE": "keepAbove",
    "ACTION_KEEP_BELOW": "keepBelow",
    "ACTION_MENU": "menu",
}

# SVG-backend button codes → QML kinds (for the iclass-pattern fallback tier).
CODE_TO_KIND: dict[str, str] = {
    "X": "close",
    "A": "maximizeRestore",
    "I": "minimize",
    "L": "shade",
    "S": "onAllDesktops",
    "F": "keepAbove",
    "B": "keepBelow",
    "M": "menu",
}


def button_kind(part: ButtonPart) -> str | None:
    """Return the QML button kind for a part, or None for plain chrome."""
    if part.aclass is not None:
        kind = ACLASS_TO_KIND.get(part.aclass)
        if kind is not None:
            return kind
        # The theme expressed an action we don't map (move/resize/exec/...):
        # honor that opinion — plain chrome, don't guess from the name.
        if part.aclass.startswith("ACTION_"):
            return None
    iclass_upper = part.iclass_name.upper()
    for pattern, code in ICLASS_PATTERN_TO_BUTTON:
        if pattern in iclass_upper:
            return CODE_TO_KIND.get(code)
    return None
