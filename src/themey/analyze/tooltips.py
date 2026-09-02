"""AST ``__TOOLTIP`` blocks → TooltipSpec dict.

Mirrors E16's ``TooltipConfigLoad`` (tooltips.c:140-210): ``__NAME``,
``__ICLASS``, ``__BUBBLE1_ICLASS``..``__BUBBLE4_ICLASS``, ``__TCLASS`` and
``__TOOLTIP_HELP_ICON`` are names, ``__DISTANCE`` goes through ``atoi``. A
tooltip is created only when name, iclass AND tclass are all set
(``_TtCreate`` guard at ``CONFIG_CLOSE``) and the iclass EXISTS —
``_TtCreate`` does ``ImageclassAlloc(ic0, 0)`` (tooltips.c:102, no
fallback) and returns NULL otherwise, so a block naming an undefined
iclass registers nothing (a ``tooltips:`` note records it when *iclasses*
is given). At the ``__NAME`` line the loader calls ``TooltipFind`` and
skips the rest of a block whose name is already REGISTERED — so the first
definition that actually created a tooltip wins, the opposite of
``__MENU_STYLE``'s last-wins list. Every corpus theme (223/223) defines
``DEFAULT``, ``ICONBOX`` and ``PAGER`` through the ``DEFINE_TOOLTIP*``
macros in the bundled ``config/definitions``; ``TooltipShow``
(tooltips.c:752) resolves ``DEFAULT`` for every window/button tooltip.

The block name comes from a ``__NAME`` child (the macros' form; E16's
``ConfigFileRead`` opens a block only on a bare ``__TOOLTIP __BGN`` line).
A name in ``head_values`` (``__TOOLTIP X __BGN``) is themey leniency shared
with ``menus.py``. The bubbles are positional so an unset middle slot is
an empty string and later slots keep their index; trailing unset slots are
dropped.
"""
from __future__ import annotations

from collections.abc import Collection

from themey.etheme.ast import Block, KeyVal, atoi
from themey.ir import TooltipSpec

_BUBBLE_KEYS = {
    "__BUBBLE1_ICLASS": 0,
    "__BUBBLE2_ICLASS": 1,
    "__BUBBLE3_ICLASS": 2,
    "__BUBBLE4_ICLASS": 3,
}


def build_tooltips(
    blocks: list[Block],
    *,
    iclasses: Collection[str] | None = None,
    notes: list[str] | None = None,
) -> dict[str, TooltipSpec]:
    """``__TOOLTIP`` blocks → ``{name: TooltipSpec}``. With *iclasses* (the
    theme's defined iclass names) a block naming an unknown iclass is
    dropped as E16's ``_TtCreate`` drops it, and *notes* gets a
    ``tooltips:`` line for it."""
    tips: dict[str, TooltipSpec] = {}
    for block in blocks:
        name = str(block.head_values[0]) if block.head_values else None
        iclass: str | None = None
        tclass: str | None = None
        help_icon: str | None = None
        distance = 0
        bubbles = ["", "", "", ""]
        for child in block.children:
            if not isinstance(child, KeyVal) or not child.values:
                continue
            value = child.values[0]
            if child.keyword == "__NAME" and name is None:
                name = str(value)
            elif child.keyword == "__ICLASS":
                iclass = str(value)
            elif child.keyword == "__TCLASS":
                tclass = str(value)
            elif child.keyword == "__TOOLTIP_HELP_ICON":
                help_icon = str(value)
            elif child.keyword == "__DISTANCE":
                distance = atoi(value)
            elif child.keyword in _BUBBLE_KEYS:
                bubbles[_BUBBLE_KEYS[child.keyword]] = str(value)
        if not name or not iclass or not tclass or name in tips:
            continue
        if iclasses is not None and iclass not in iclasses:
            if notes is not None:
                notes.append(
                    f"tooltips: __TOOLTIP {name} names undefined iclass {iclass}; "
                    "ignored as E16 does (ImageclassAlloc with no fallback "
                    "creates no tooltip), so a later block of that name may apply"
                )
            continue
        while bubbles and not bubbles[-1]:
            bubbles.pop()
        tips[name] = TooltipSpec(
            name=name, iclass=iclass, tclass=tclass, bubbles=tuple(bubbles),
            distance=distance, help_icon=help_icon,
        )
    return tips
