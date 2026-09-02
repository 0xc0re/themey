"""AST ``__MATCH_WINDOW`` blocks → the theme's per-app icon rules.

E16's ``windowmatches.cfg`` (``windowmatch.c``) is the ONLY theme hook for
custom application icons in 1.0.31 — there is no ``icondefs.cfg``; icons
otherwise come from the app itself (``icons.c`` mode 2: IMG, APP, SNAP).
A match block pairs one criterion with one effect; themey reads the
``__USE_ICON image`` effect against ``__HAS_CLASS`` (WM_CLASS class),
``__HAS_NAME`` (WM_CLASS instance) or ``__HAS_TITLE`` (window title),
which the bundled ``config/definitions`` macros
``USE_ICON_IMAGE_FOR_CLIENT_{CLASS,NAME,TITLE}(pattern, image)`` expand
to (``e16_definitions:559-578``). E16 matches with plain ``fnmatch``
(``regex.c:29-35``, flags 0) — so does ``generate/icons.py``.

Dropped, each with an ``icons:`` note: a block whose ``__USE_ICON`` names
no readable image under the archive (Egradient names an iclass,
``DESKTOP_EXEC_X11AMP`` — E16 would show nothing either), a catch-all
pattern (``*``/empty — Hazard's ``__HAS_TITLE *`` would re-icon every
window), and a block with no usable criterion. ``__USE_BORDER``-only
blocks are not this module's concern (per-class borders are backlog).
A block with several criteria keeps the first in class > name > title
order and notes the approximation (E16 ANDs them).
"""
from __future__ import annotations

from pathlib import Path

from themey.etheme.ast import Block, KeyVal
from themey.ir import IconMatchSpec

#: E16 criterion keyword -> IconMatchSpec.kind, in priority order.
_CRITERIA: tuple[tuple[str, str], ...] = (
    ("__HAS_CLASS", "class"),
    ("__HAS_NAME", "name"),
    ("__HAS_TITLE", "title"),
)
_CATCH_ALL = frozenset({"", "*", "?*", "*?", "**"})


def _resolve_image(asset_root: Path, image: str) -> Path | None:
    """*image* under *asset_root*, or None when absent or escaping the
    archive (T-05-01 traversal guard, the ``build_iclasses`` rule)."""
    if not image or image.startswith("/"):
        return None
    try:
        root = asset_root.resolve()
        path = (asset_root / image).resolve()
        path.relative_to(root)
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def build_icon_matches(
    blocks: list[Block],
    *,
    asset_root: Path,
    notes: list[str] | None = None,
) -> tuple[IconMatchSpec, ...]:
    """``__MATCH_WINDOW`` blocks → the usable ``__USE_ICON`` rules, in
    declaration order (first rule wins downstream, as E16's first match
    did)."""
    out: list[IconMatchSpec] = []

    def note(msg: str) -> None:
        if notes is not None and msg not in notes:
            notes.append(msg)

    for block in blocks:
        image: str | None = None
        criteria: dict[str, str] = {}
        block_name = str(block.head_values[0]) if block.head_values else ""
        for child in block.children:
            if not isinstance(child, KeyVal) or not child.values:
                continue
            value = str(child.values[0])
            if child.keyword == "__NAME" and not block_name:
                block_name = value
            elif child.keyword == "__USE_ICON":
                image = value
            else:
                for keyword, kind in _CRITERIA:
                    if child.keyword == keyword:
                        criteria[kind] = value
        if image is None:
            continue  # __USE_BORDER / sticky / size rules: not icons
        label = block_name or image
        path = _resolve_image(asset_root, image)
        if path is None:
            note(
                f"icons: match {label!r} names __USE_ICON {image!r}, which is "
                "not an image file in the archive (an iclass name, or "
                "missing); dropped — E16 showed no icon for it either"
            )
            continue
        chosen: tuple[str, str] | None = None
        for _keyword, kind in _CRITERIA:
            if kind in criteria:
                chosen = (kind, criteria[kind])
                break
        if chosen is None:
            note(
                f"icons: match {label!r} has __USE_ICON but no "
                "__HAS_CLASS/__HAS_NAME/__HAS_TITLE criterion; dropped"
            )
            continue
        kind, pattern = chosen
        if pattern.strip() in _CATCH_ALL:
            note(
                f"icons: match {label!r} pattern {pattern!r} is a catch-all "
                "(it would re-icon every application); dropped"
            )
            continue
        if len(criteria) > 1:
            note(
                f"icons: match {label!r} combines {len(criteria)} criteria "
                f"(E16 ANDs them); only the {kind} pattern {pattern!r} is used"
            )
        out.append(IconMatchSpec(kind=kind, pattern=pattern, image=path))
    return tuple(out)
