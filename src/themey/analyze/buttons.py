"""Three-tier button binning: __ACLASS first -> __ICLASS pattern -> spatial.

Wilbs's gap-matrix post-mortem (e16-architecture-and-gap-matrix.md):
throwing away __ACLASS and faking actions by iclass-name pattern shipped a
buttons-fire-resize bug. We capture __ACLASS at parse time and prefer it
over name patterns. Spatial center-of-mass is the LAST resort, used only
when both aclass and iclass-pattern fail to identify the button.
"""
from __future__ import annotations

# Tier 1: __ACLASS -> Aurorae button code
ACLASS_TO_BUTTON: dict[str, str] = {
    "ACTION_CLOSE": "X",
    "ACTION_KILL": "X",  # no force-quit equivalent; alias to close
    "ACTION_MAX": "A",
    "ACTION_ICONIFY": "I",
    "ACTION_SHADE": "L",
    "ACTION_STICK": "S",
}
# Aclasses that are NOT buttons (Aurorae handles natively):
ACLASS_DROP: frozenset[str] = frozenset({
    "ACTION_RESIZE",
    "ACTION_RESIZE_H",
    "ACTION_RESIZE_V",
    "ACTION_MOVE",  # titlebar drag
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
) -> tuple[str | None, str]:
    """Return (button_code, source).

    source in {'aclass', 'iclass', 'spatial', 'drop'}
    - 'aclass' / 'iclass': matched in tier 1 / tier 2; code is set
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


def bin_left_right(
    buttons: list[tuple[str, int]],
    titlebar_min_x: int,
    titlebar_max_x: int,
) -> tuple[str, str, list[tuple[str, int]]]:
    """Bin (code, x_center) buttons into (left_str, right_str, overlap_list).

    Each list is sorted by x ascending. Overlap items (titlebar_min <= x <=
    titlebar_max) are returned for the caller to log.
    """
    left = sorted([b for b in buttons if b[1] < titlebar_min_x], key=lambda b: b[1])
    right = sorted([b for b in buttons if b[1] > titlebar_max_x], key=lambda b: b[1])
    overlap = [b for b in buttons if titlebar_min_x <= b[1] <= titlebar_max_x]
    return (
        "".join(b[0] for b in left),
        "".join(b[0] for b in right),
        overlap,
    )
