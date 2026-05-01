"""AST __TCLASS blocks → TClassSpec dict.

Tolerates E16's misspelled ``__FORGROUND_COLOR`` (the primary form emitted by
E16) plus ``__FOREGROUND_COLOR`` (correct spelling) and ``__COLOR`` (alternate
alias). FG_COLOR_KEYS defines the precedence order: misspelling first, because
that is what E16 actually emits in practice.

TCLASS uses a "state context" pattern:
- A bare KeyVal like ``__NORMAL`` (zero values) sets the current state context.
- Subsequent KeyVals like ``__FORGROUND_COLOR R G B`` attach to that state.
This is different from ICLASS where ``__NORMAL "path.png"`` carries the path
as an inline value (one value).
"""
from __future__ import annotations

from themey.etheme.ast import Block, KeyVal
from themey.ir import TClassSpec


def _to_int(v: object) -> int:
    """Coerce an AST value (int | str) to int for pyright basic compatibility."""
    return int(v)  # type: ignore[arg-type]

FG_COLOR_KEYS: tuple[str, ...] = (
    "__FORGROUND_COLOR",  # E16's misspelling — primary form
    "__FOREGROUND_COLOR",  # correct spelling — fallback
    "__COLOR",  # alternate alias
)

TCLASS_STATE_CONTEXT_KEYS: frozenset[str] = frozenset({
    "__NORMAL",
    "__NORMAL_ACTIVE",
    "__HILITED",
    "__HILITED_ACTIVE",
    "__CLICKED",
    "__CLICKED_ACTIVE",
    "__NORMAL_STICKY",
    "__NORMAL_ACTIVE_STICKY",
})


def build_tclasses(tclass_blocks: list[Block]) -> dict[str, TClassSpec]:
    """Convert __TCLASS blocks to a TClassSpec dict keyed by tclass name.

    Only ``fg_normal`` (from ``__NORMAL`` state) and ``fg_active`` (from
    ``__NORMAL_ACTIVE`` state) are surfaced on TClassSpec for Phase 1.
    Other states are silently skipped (no Aurorae target for them).
    """
    out: dict[str, TClassSpec] = {}
    for block in tclass_blocks:
        if not block.head_values:
            continue
        name = str(block.head_values[0])
        current_state: str | None = None
        colors: dict[str, tuple[int, int, int]] = {}

        for kv in block.children:
            if not isinstance(kv, KeyVal):
                continue
            # State context setter: bare keyword with no values
            if kv.keyword in TCLASS_STATE_CONTEXT_KEYS and not kv.values:
                current_state = kv.keyword
            # Foreground color: any FG_COLOR_KEYS keyword with at least 3 values
            elif kv.keyword in FG_COLOR_KEYS and len(kv.values) >= 3:
                if current_state is not None:
                    try:
                        rgb = (
                            _to_int(kv.values[0]),
                            _to_int(kv.values[1]),
                            _to_int(kv.values[2]),
                        )
                    except (ValueError, TypeError):
                        continue
                    # First color seen for this state wins; don't overwrite
                    if current_state not in colors:
                        colors[current_state] = rgb

        out[name] = TClassSpec(
            name=name,
            fg_normal=colors.get("__NORMAL"),
            fg_active=colors.get("__NORMAL_ACTIVE"),
        )
    return out
