"""AST __ICLASS blocks → IClassSpec dict + raw state map for AURORAE-04 collapse.

EDGE_SCALING order is L R T B (verified in E16's iclass.c sscanf order).
The four values in __EDGE_SCALING map to indices 0..3 as (left, right,
top, bottom).

__EDGE_SCALING is PER IMAGE STATE in E16 (iclass.c ``ICLASS_LRTB`` writes
``is->border`` on the most recently opened state, and is an error before
any state). ``IClassSpec.edge_by_state`` records each state's own edge
(keyed by attribute name — ``"normal"``, ``"hilited_active"`` …), and
``edge_scaling`` keeps the last-wins iclass-wide value that states without
an edge of their own fall back to through ``IClassSpec.edge_for`` (E16
would draw those unsliced; the corpus declares one edge after the first
state and means it for all, so the lenient reading stays).

Storage policy:
    iclasses.py stores the resolved Path unconditionally — never None for
    missing files. build_theme.py is responsible for appending a missing-asset
    Theme.notes entry when not path.is_file(). This module ONLY computes paths;
    existence checking happens later in the pipeline.

    Exception: paths that resolve *outside* asset_root are set to None
    (T-05-01 mitigation — belt-and-suspenders since safe_extract already
    prevents writes outside asset_root, but cfg paths can still reference
    outside files).
"""
from __future__ import annotations

from pathlib import Path

from themey.etheme.ast import Block, KeyVal
from themey.ir import IClassSpec


def _to_int(v: object) -> int:
    """Coerce an AST value (int | str) to int for pyright basic compatibility."""
    return int(v)  # type: ignore[arg-type]


def _block_name(block: Block) -> str | None:
    """Extract block name from head_values or legacy __NAME KeyVal child.

    Handles BOTH naming conventions found in E16 themes:
    - Modern: ``__ICLASS DEFAULT __BGN`` → head_values = ("DEFAULT",)
    - Legacy macro (Aliens.etheme): ``__ICLASS __BGN __NAME DEFAULT ...``
      → head_values = (), child KeyVal keyword="__NAME", values=("DEFAULT",)
    """
    if block.head_values:
        return str(block.head_values[0])
    for child in block.children:
        if isinstance(child, KeyVal) and child.keyword == "__NAME" and child.values:
            return str(child.values[0])
    return None


# State keywords whose presence as a KeyVal with one string value sets the
# iclass image for that state (E16 ICLASS uses the inline path form).
ICLASS_STATE_KEYS: frozenset[str] = frozenset({
    "__NORMAL",
    "__NORMAL_ACTIVE",
    "__HILITED",
    "__HILITED_ACTIVE",
    "__CLICKED",
    "__CLICKED_ACTIVE",
    "__NORMAL_STICKY",
    "__NORMAL_ACTIVE_STICKY",
    "__CLICKED_STICKY",
    "__CLICKED_ACTIVE_STICKY",
    "__HILITED_STICKY",
    "__HILITED_ACTIVE_STICKY",
    "__NORMAL_ACTIVE_CLICKED",
    "__NORMAL_ACTIVE_HILITED",
    "__DISABLED",
})


def build_iclasses(
    iclass_blocks: list[Block],
    asset_root: Path,
) -> tuple[dict[str, IClassSpec], dict[str, dict[str, Path | None]]]:
    """Convert __ICLASS blocks to a typed dict and a raw state map.

    Returns:
        typed: name → IClassSpec (subset of states surfaced on the dataclass)
        raw:   name → {state_keyword: Path | None}  — full state map for
               AURORAE-04 collapse via collapse_image_states; includes
               sticky/disabled/clicked-active variants not on the dataclass.
    """
    asset_root_resolved = str(asset_root.resolve())
    typed: dict[str, IClassSpec] = {}
    raw: dict[str, dict[str, Path | None]] = {}

    for block in iclass_blocks:
        name = _block_name(block)
        if name is None:
            continue
        edge = (0, 0, 0, 0)  # left, right, top, bottom — LRTB order per E16 iclass.c
        edge_by_state: dict[str, tuple[int, int, int, int]] = {}
        current_state: str | None = None  # attribute-name form
        padding = (0, 0, 0, 0)
        states: dict[str, Path | None] = {}

        for kv in block.children:
            if not isinstance(kv, KeyVal):
                continue
            if kv.keyword == "__EDGE_SCALING" and len(kv.values) >= 4:
                edge = (
                    _to_int(kv.values[0]),
                    _to_int(kv.values[1]),
                    _to_int(kv.values[2]),
                    _to_int(kv.values[3]),
                )
                if current_state is not None:
                    edge_by_state[current_state] = edge
            elif kv.keyword == "__PADDING" and len(kv.values) >= 4:
                padding = (
                    _to_int(kv.values[0]),
                    _to_int(kv.values[1]),
                    _to_int(kv.values[2]),
                    _to_int(kv.values[3]),
                )
            elif kv.keyword in ICLASS_STATE_KEYS and kv.values:
                current_state = kv.keyword[2:].lower()
                p = str(kv.values[0])
                full = (asset_root / p).resolve()
                # T-05-01: reject paths that escape asset_root
                if not (
                    str(full) == asset_root_resolved
                    or str(full).startswith(asset_root_resolved + "/")
                ):
                    states[kv.keyword] = None
                else:
                    # RESOLVED POLICY: store resolved Path unconditionally.
                    # build_theme.py logs missing-asset notes when not is_file().
                    states[kv.keyword] = full

        raw[name] = states
        typed[name] = IClassSpec(
            name=name,
            edge_scaling=edge,
            normal=states.get("__NORMAL"),
            normal_active=states.get("__NORMAL_ACTIVE"),
            hilited=states.get("__HILITED"),
            hilited_active=states.get("__HILITED_ACTIVE"),
            clicked=states.get("__CLICKED"),
            clicked_active=states.get("__CLICKED_ACTIVE"),
            normal_sticky=states.get("__NORMAL_STICKY"),
            normal_active_sticky=states.get("__NORMAL_ACTIVE_STICKY"),
            normal_active_hilited=states.get("__NORMAL_ACTIVE_HILITED"),
            padding=padding,
            edge_by_state=edge_by_state,
        )

    return typed, raw
