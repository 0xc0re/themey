"""E16 part action → QML DecorationButton kind mapping.

Unlike the SVG backend (which bins buttons into Aurorae's global
LeftButtons/RightButtons strings), the QML backend keeps every part at its
declared position and only needs to know *which window request* a click
fires. The mapping mirrors chris's plan: KILL/CLOSE→close,
ICONIFY→minimize, MAX→maximizeRestore, SHADE→shade, STICK→onAllDesktops,
KEEP_ABOVE/BELOW→keepAbove/keepBelow, MENU→menu.

An __ACLASS name the stock table doesn't cover is resolved through the
``__ACLASS __BGN`` block that defined it (analyze/aclasses.py) and mapped
by its ``__A_*`` verb — the same tier the SVG backend gained, sharing
analyze/buttons.py's VERB_TO_BUTTON/VERB_DROP tables so both backends
agree. Ganymede's ACTION_GANYMEDE_KILL is a close button this way.

ACTION_MOVE / ACTION_RESIZE* / unresolvable aclasses are plain chrome —
KDecoration gives move-drag and edge-resize on non-button decoration area
for free, so those parts render as passive imagery.

The fallback tier reuses the SVG backend's iclass-pattern table
(analyze/buttons.py ICLASS_PATTERN_TO_BUTTON) so both backends agree on
what counts as a button when __ACLASS is absent.
"""
from __future__ import annotations

from collections.abc import Mapping

from themey.analyze.buttons import (
    ICLASS_PATTERN_TO_BUTTON,
    VERB_DROP,
    VERB_TO_BUTTON,
)
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


def button_kind(
    part: ButtonPart,
    aclass_verbs: Mapping[str, str] | None = None,
) -> str | None:
    """Return the QML button kind for a part, or None for plain chrome.

    *aclass_verbs* is ``{action-class name: __A_* verb}`` from
    analyze/aclasses.py; it resolves names ACLASS_TO_KIND does not cover.
    """
    if part.aclass is not None:
        kind = ACLASS_TO_KIND.get(part.aclass)
        if kind is not None:
            return kind
        if aclass_verbs is not None:
            verb = aclass_verbs.get(part.aclass)
            if verb is not None and verb not in VERB_DROP:
                code = VERB_TO_BUTTON.get(verb)
                if code is not None:
                    return CODE_TO_KIND.get(code)
        # The theme expressed an action we don't map (move/resize/exec/...):
        # honor that opinion — plain chrome, don't guess from the name.
        if part.aclass.startswith("ACTION_"):
            return None
    iclass_upper = part.iclass_name.upper()
    for pattern, code in ICLASS_PATTERN_TO_BUTTON:
        if pattern in iclass_upper:
            return CODE_TO_KIND.get(code)
    return None
