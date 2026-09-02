"""Four-tier button binning: __ACLASS name -> its verb -> __ICLASS -> spatial.

A prior E16-to-desktop converter's post-mortem: throwing away __ACLASS and
faking actions by iclass-name pattern shipped a buttons-fire-resize bug.
We capture __ACLASS at parse time and prefer it over name patterns.
Spatial center-of-mass is the LAST resort, used only when the aclass and
iclass-pattern tiers fail to identify the button.

Tier 1 is two-stage. ``ACLASS_TO_BUTTON`` matches the STOCK action-class
names from E16's own ``config/actionclasses.cfg``; when the name is not
one of those, *aclass_verbs* resolves it through the ``__ACLASS __BGN``
block that defined it (see analyze/aclasses.py) and ``VERB_TO_BUTTON``
maps the ``__A_*`` verb. Without that second stage every theme-private
name was an ``unknown_aclass`` drop — Ganymede binds its close button to
``ACTION_GANYMEDE_KILL`` and shipped with no clickable buttons at all, and
68 of the 223 corpus themes have at least one such border part.
"""
from __future__ import annotations

from collections.abc import Mapping

from themey.analyze.coords import REFERENCE_WINDOW_WIDTH
from themey.ir import ButtonPart

# Tier 1: __ACLASS -> Aurorae button code
ACLASS_TO_BUTTON: dict[str, str] = {
    "ACTION_CLOSE": "X",
    "ACTION_KILL": "X",  # no force-quit equivalent; alias to close
    "ACTION_MAX": "A",
    "ACTION_ICONIFY": "I",
    "ACTION_SHADE": "L",
    "ACTION_STICK": "S",
    "ACTION_KEEP_ABOVE": "F",
    "ACTION_KEEP_BELOW": "B",
}
# Aclasses that are NOT buttons (Aurorae handles natively or has no equivalent):
ACLASS_DROP: frozenset[str] = frozenset({
    "ACTION_RESIZE",
    "ACTION_RESIZE_H",
    "ACTION_RESIZE_V",
    "ACTION_MOVE",  # titlebar drag
    # Application/desktop verbs with no Aurorae button equivalent.
    "ACTION_MENU",
    "ACTION_DESKTOP_NEXT",
    "ACTION_DESKTOP_PREV",
    "ACTION_PAGER_NEXT",
    "ACTION_PAGER_PREV",
    "ACTION_EXEC",
})

# Tier 1b: E16 action verb (__A_* macro name) -> Aurorae button code.
# The verb is what the theme's own __ACLASS block actually binds, so it
# resolves names ACLASS_TO_BUTTON has never heard of. Verbs stay unexpanded
# in the AST: parse.py registers only function-like macros from the bundled
# definitions, and `#define __A_KILL wop * close` is object-like.
VERB_TO_BUTTON: dict[str, str] = {
    "__A_KILL": "X",
    "__A_KILL_NASTY": "X",  # no force-quit button; alias to close
    "__A_KILL_NG": "X",
    "__A_ICONIFY": "I",
    "__A_ICONIFY_NG": "I",
    # E16 maximizes per axis; Aurorae has one maximize toggle for all three.
    "__A_MAX_SIZE": "A",
    "__A_MAX_WIDTH": "A",
    "__A_MAX_HEIGHT": "A",
    "__A_ZOOM": "A",
    "__A_FULLSCREEN": "A",
    "__A_SHADE": "L",
    "__A_SHADE_NG": "L",
    "__A_STICK": "S",
    "__A_STICK_NG": "S",
    # E16's raise/lower are one-shot restacks; keepAbove/keepBelow are the
    # nearest Aurorae buttons and are toggles. Approximation, noted by
    # build_theme.
    "__A_RAISE": "F",
    "__A_RAISE_NG": "F",
    "__A_LOWER": "B",
    "__A_LOWER_NG": "B",
    # A slideout is "a bar of more buttons to control the Window with"
    # (Ganymede's own __TOOLTIP_TEXT) — that is KWin's window menu.
    "__A_SLIDEOUT": "M",
    "__A_SHOW_MENU": "M",
}

# Verbs that are definitively not a window button: KWin/KDecoration handles
# them natively (move/resize on plain decoration area) or they are desktop
# and launcher verbs with no titlebar equivalent. Dropped SILENTLY, the same
# way ACLASS_DROP treats their stock names.
VERB_DROP: frozenset[str] = frozenset({
    "__A_MOVE",
    "__A_MOVE_NG",
    "__A_RESIZE",
    "__A_RESIZE_H",
    "__A_RESIZE_V",
    "__A_NONE",
    "__A_CMD",
    "__A_EXEC",
    "__A_HIDE_MENU",
    "__A_DRAG_BUTTON",
    "__A_HIDESHOW_BUTTON",
    "__A_DESKTOP_NEXT",
    "__A_DESKTOP_PREV",
    "__A_DESKTOP_RAISE",
    "__A_DESKTOP_LOWER",
    "__A_DESKTOP_DRAG",
    "__A_DESKTOP_INPLACE",
    "__A_GOTO_DESK",
    "__A_AREA_SET",
    "__A_AREA_MOVE_BY",
    "__A_BACKGROUND_SET",
    "__A_FOCUS_NEXT",
    "__A_FOCUS_PREV",
})

# Tier 2: __ICLASS name pattern -> button code (case-insensitive substring match)
# Order matters: BUTTON_MAXIMIZE before BUTTON_MAX so MAXIMIZE wins for
# iclass="BUTTON_MAXIMIZE_FOO". (Both map to A; precedence isn't a bug.)
ICLASS_PATTERN_TO_BUTTON: list[tuple[str, str]] = [
    ("BUTTON_CLOSE", "X"),
    ("BUTTON_KILL", "X"),
    ("BUTTON_MAXIMIZE", "A"),
    ("BUTTON_MAX", "A"),
    ("BUTTON_ICONIFY", "I"),
    ("BUTTON_MINIMIZE", "I"),
    ("BUTTON_SHADE", "L"),
    ("BUTTON_STICK", "S"),
]


def classify_button(
    aclass: str | None,
    iclass: str,
    *,
    x_center: int | None = None,
    titlebar_left: int | None = None,
    titlebar_right: int | None = None,
    aclass_verbs: Mapping[str, str] | None = None,
) -> tuple[str | None, str]:
    """Return (button_code, source).

    *aclass_verbs* is ``{action-class name: __A_* verb}`` from
    analyze/aclasses.py — the theme's own ``__ACLASS`` blocks plus E16's
    stock ones. It is consulted only for names ``ACLASS_TO_BUTTON`` does
    not already cover, so the curated stock mapping always wins.

    source in {'aclass', 'verb', 'iclass', 'spatial', 'drop'}
    - 'aclass' / 'verb' / 'iclass': matched in tier 1a / 1b / 2; code is set
    - 'drop': aclass is in ACLASS_DROP (titlebar/resize handle, not a button)
    - 'spatial': tier 3. When the geometry kwargs are all supplied AND
                 titlebar_right > titlebar_left, x_center is binned into
                 thirds of the titlebar range:
                   leftmost third  -> ('M', 'spatial')   (menu)
                   rightmost third -> ('X', 'spatial')   (close)
                   middle third    -> (None, 'spatial')  (caller drops and logs)
                 When geometry is not supplied (any kwarg is None or
                 range is non-positive), returns (None, 'spatial') and
                 the caller must drop with an "ambiguous" note.
    AURORAE-02 mandate: every (code, 'spatial') decision MUST be logged
    to report.txt by the caller (build_theme appends to Theme.notes).
    """
    if aclass in ACLASS_DROP:
        return (None, "drop")
    if aclass is not None and aclass in ACLASS_TO_BUTTON:
        return (ACLASS_TO_BUTTON[aclass], "aclass")
    # Tier 1b: resolve the name through the __ACLASS block that defined it
    # and map the verb it binds.
    if aclass is not None and aclass_verbs is not None:
        verb = aclass_verbs.get(aclass)
        if verb is not None:
            if verb in VERB_DROP:
                return (None, "drop")
            code = VERB_TO_BUTTON.get(verb)
            if code is not None:
                return (code, "verb")
    # An ACLASS we don't recognize is not the same as "no ACLASS at all" —
    # iclass-pattern matching is unreliable when the theme has expressed
    # an opinion about the action via __ACLASS but we don't speak that
    # verb. Surface the case so build_theme can log it.
    if (
        aclass is not None
        and aclass.startswith("ACTION_")
        and aclass not in ACLASS_TO_BUTTON
        and aclass not in ACLASS_DROP
    ):
        return (None, "unknown_aclass")
    iclass_upper = iclass.upper()
    for pattern, code in ICLASS_PATTERN_TO_BUTTON:
        if pattern in iclass_upper:
            return (code, "iclass")
    # Tier 3: spatial center-of-mass against titlebar thirds
    if (
        x_center is not None
        and titlebar_left is not None
        and titlebar_right is not None
        and titlebar_right > titlebar_left
    ):
        tb_w = titlebar_right - titlebar_left
        third = tb_w / 3.0
        left_boundary = titlebar_left + third
        right_boundary = titlebar_right - third
        if x_center < left_boundary:
            return ("M", "spatial")
        if x_center > right_boundary:
            return ("X", "spatial")
        # ambiguous middle — drop and let caller log
        return (None, "spatial")
    return (None, "spatial")


def title_part(parts: tuple[ButtonPart, ...]) -> ButtonPart | None:
    """Return the canonical title-bearing part, identified by __FLAG_TITLE.

    Per the E16 config grammar, the title region is marked semantically —
    *any* iclass name is permitted (e.g. Aliens uses TITLE_BAR_HORIZONTAL,
    e13 uses TITLEBAR without underscore).
    Name-pattern matching is unreliable; this flag is canonical.

    Returns the first part with __FLAG_TITLE in its flags tuple, or None.
    """
    for p in parts:
        if "__FLAG_TITLE" in p.flags:
            return p
    return None


def bin_left_right(
    buttons: list[tuple[str, int]],
    titlebar_min_x: int,
    titlebar_max_x: int,
) -> tuple[str, str, list[tuple[str, int]]]:
    """Bin (code, x_center) buttons into (left_str, right_str, overlap_list).

    Each list is sorted by x ascending. Overlap items (titlebar_min <= x <=
    titlebar_max) are returned for the caller to log.

    Sentinel fallback: when ``titlebar_max_x <= titlebar_min_x`` (no title
    bar identified — e.g. e13's __FLAG_TITLE missed by old name-pattern code),
    split at REFERENCE_WINDOW_WIDTH/2. Without this, the original predicate
    ``x < min AND x > max`` was *both* true for every x at the sentinel
    (min=800, max=0), placing each button into BOTH sides.
    """
    if titlebar_max_x <= titlebar_min_x:
        midpoint = REFERENCE_WINDOW_WIDTH // 2
        left = sorted([b for b in buttons if b[1] < midpoint], key=lambda b: b[1])
        right = sorted([b for b in buttons if b[1] >= midpoint], key=lambda b: b[1])
        return (
            "".join(b[0] for b in left),
            "".join(b[0] for b in right),
            [],
        )

    left = sorted([b for b in buttons if b[1] < titlebar_min_x], key=lambda b: b[1])
    right = sorted([b for b in buttons if b[1] > titlebar_max_x], key=lambda b: b[1])
    overlap = [b for b in buttons if titlebar_min_x <= b[1] <= titlebar_max_x]
    return (
        "".join(b[0] for b in left),
        "".join(b[0] for b in right),
        overlap,
    )
