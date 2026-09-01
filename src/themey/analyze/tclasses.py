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

from themey.analyze.buttons import title_part
from themey.etheme.ast import Block, KeyVal
from themey.ir import BorderSpec, TClassSpec


def _to_int(v: object) -> int:
    """Coerce an AST value (int | str) to int for pyright basic compatibility."""
    return int(v)  # type: ignore[arg-type]


def _block_name(block: Block) -> str | None:
    """Extract block name from head_values or legacy __NAME KeyVal child.

    Handles BOTH naming conventions found in E16 themes:
    - Modern: ``__TCLASS TEXT1 __BGN`` → head_values = ("TEXT1",)
    - Legacy macro (Aliens.etheme): ``__TCLASS __BGN __NAME TEXT1 ...``
      → head_values = (), child KeyVal keyword="__NAME", values=("TEXT1",)
    """
    if block.head_values:
        return str(block.head_values[0])
    for child in block.children:
        if isinstance(child, KeyVal) and child.keyword == "__NAME" and child.values:
            return str(child.values[0])
    return None


def title_tclass(
    border: BorderSpec,
    tclasses: dict[str, TClassSpec],
) -> TClassSpec | None:
    """The tclass that styles this border's title text.

    The title part's declared ``__TCLASS`` wins when it names a known tclass
    (OPENSTEP: ``__TCLASS TITLEBAR_TEXT``); the conventional ``TEXT1`` is the
    fallback. Hardcoding ``TEXT1`` silently dropped OPENSTEP's title colors —
    ``qmldeco/theme_js.py`` always resolved the declared name; this helper
    gives the other consumers the same behavior.
    """
    tp = title_part(border.parts)
    if tp is not None and tp.tclass_name:
        spec = tclasses.get(tp.tclass_name)
        if spec is not None:
            return spec
    return tclasses.get("TEXT1")


FG_COLOR_KEYS: tuple[str, ...] = (
    "__FORGROUND_COLOR",  # E16's misspelling — primary form
    "__FOREGROUND_COLOR",  # correct spelling — fallback
    "__COLOR",  # alternate alias
)


def _normalize_alignment(value: object) -> str | None:
    """Map an E16 __JUSTIFICATION value to Aurorae's "Left"/"Center"/"Right".

    E16 accepts both literal tokens (``__LEFT``, ``__CENTER``, ``__RIGHT``)
    and numeric forms (0 = left, 512 = center, 1024 = right; the same
    Q10 fixed-point pct scheme used elsewhere). Anything we don't
    recognize returns None (the writer falls back to its default).
    """
    if isinstance(value, str):
        upper = value.upper()
        if upper in ("__LEFT", "LEFT"):
            return "Left"
        if upper in ("__CENTER", "CENTER"):
            return "Center"
        if upper in ("__RIGHT", "RIGHT"):
            return "Right"
        # Numeric written as a string
        try:
            value = int(value)
        except ValueError:
            return None
    if isinstance(value, int):
        if value <= 256:
            return "Left"
        if value >= 768:
            return "Right"
        return "Center"
    return None

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


def _raw_justification(value: object) -> int | None:
    """Raw Q10 justification: numeric passes through; the literal tokens map
    to their canonical Q10 values. Unrecognized → None (ignored)."""
    if isinstance(value, str):
        upper = value.upper()
        token_map = {"__LEFT": 0, "LEFT": 0, "__CENTER": 512, "CENTER": 512,
                     "__RIGHT": 1024, "RIGHT": 1024}
        if upper in token_map:
            return token_map[upper]
        try:
            return int(value)
        except ValueError:
            return None
    if isinstance(value, int):
        return value
    return None


def build_tclasses(tclass_blocks: list[Block]) -> dict[str, TClassSpec]:
    """Convert __TCLASS blocks to a TClassSpec dict keyed by tclass name.

    Only ``__NORMAL`` (→ ``fg_normal``) and ``__NORMAL_ACTIVE``
    (→ ``fg_active``) contribute colors; other states' colors are silently
    skipped (no Aurorae target for them).
    """
    out: dict[str, TClassSpec] = {}
    for block in tclass_blocks:
        name = _block_name(block)
        if name is None:
            continue
        current_state: str | None = None
        colors: dict[str, tuple[int, int, int]] = {}
        fonts: dict[str, str] = {}  # state keyword -> raw font token
        alignment: str | None = None
        justification_q10: int | None = None  # E16 last-wins across the block
        effect: str | None = None
        effect_color: tuple[int, int, int] | None = None

        for kv in block.children:
            if not isinstance(kv, KeyVal):
                continue
            # State context setter: recognized state keyword sets context.
            # May have values (e.g. __NORMAL '*font-default' in Aliens) or no
            # values (pure marker form). Both forms set the state context.
            if kv.keyword in TCLASS_STATE_CONTEXT_KEYS:
                current_state = kv.keyword
                if kv.values and kv.keyword not in fonts:
                    fonts[kv.keyword] = str(kv.values[0])
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
            elif kv.keyword == "__JUSTIFICATION" and kv.values:
                if alignment is None:
                    alignment = _normalize_alignment(kv.values[0])
                raw = _raw_justification(kv.values[0])
                if raw is not None:
                    justification_q10 = raw
            elif kv.keyword == "__DRAWING_EFFECT" and kv.values and effect is None:
                effect = str(kv.values[0])
            elif (
                kv.keyword == "__EFFECT_COLOR"
                and len(kv.values) >= 3
                and effect_color is None
            ):
                try:
                    effect_color = (
                        _to_int(kv.values[0]),
                        _to_int(kv.values[1]),
                        _to_int(kv.values[2]),
                    )
                except (ValueError, TypeError):
                    pass

        font_normal = fonts.get("__NORMAL")
        font_active = fonts.get("__NORMAL_ACTIVE")
        font_alias: str | None = None
        for token in (font_active, font_normal):
            if token is not None and token.startswith("*"):
                font_alias = token[1:]
                break

        out[name] = TClassSpec(
            name=name,
            fg_normal=colors.get("__NORMAL"),
            fg_active=colors.get("__NORMAL_ACTIVE"),
            alignment=alignment,
            effect=effect,
            effect_color=effect_color,
            justification_q10=justification_q10,
            font_normal=font_normal,
            font_active=font_active,
            font_alias=font_alias,
        )
    return out
