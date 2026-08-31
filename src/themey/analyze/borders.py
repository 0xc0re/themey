"""AST __BORDER block → BorderSpec + ButtonPart extraction.

DEFAULT-only selection per CLAUDE.md: E16 themes ship many __BORDER blocks
(BORDERLESS, DIALOG, MENU, ...) but Aurorae has only one window decoration.
"""
from __future__ import annotations

from themey.etheme.ast import Block, KeyVal
from themey.ir import BorderSpec, ButtonPart


def _to_int(v: object) -> int:
    """Coerce an AST value (int | str) to int for pyright basic compatibility."""
    return int(v)  # type: ignore[arg-type]


def _block_name(block: Block) -> str | None:
    """Extract block name from head_values or legacy __NAME KeyVal child.

    Handles BOTH naming conventions found in E16 themes:
    - Modern: ``__BORDER DEFAULT __BGN`` → head_values = ("DEFAULT",)
    - Legacy macro (Aliens.etheme): ``__BORDER __BGN __NAME DEFAULT ...``
      → head_values = (), child KeyVal keyword="__NAME", values=("DEFAULT",)
    """
    if block.head_values:
        return str(block.head_values[0])
    for child in block.children:
        if isinstance(child, KeyVal) and child.keyword == "__NAME" and child.values:
            return str(child.values[0])
    return None


def select_default_border(borders: list[Block]) -> Block | None:
    """Pick the DEFAULT border. Selection rule:

    1. Block with name == 'DEFAULT' (from head_values or __NAME child)
    2. First block with at least one __BORDER_PART child
    3. None
    """
    if not borders:
        return None
    for b in borders:
        if _block_name(b) == "DEFAULT":
            return b
    for b in borders:
        for c in b.children:
            if isinstance(c, Block) and c.keyword == "__BORDER_PART":
                return b
    return None


def extract_button_parts(border: Block) -> tuple[ButtonPart, ...]:
    """Extract all __BORDER_PART children from a __BORDER block."""
    parts: list[ButtonPart] = []
    for child in border.children:
        if not (isinstance(child, Block) and child.keyword == "__BORDER_PART"):
            continue
        iclass = ""
        aclass: str | None = None  # null sentinel — distinguishes "no __ACLASS" from missing
        flags: tuple[str, ...] = ()
        cursor_name: str | None = None
        tclass_name: str | None = None
        keep_when_shaded = False
        keep_on_top = False
        min_w = 0
        min_h = 0
        max_w = 0
        max_h = 0
        coords: dict[str, int] = {
            "tl_x_pct": 0,
            "tl_x_abs": 0,
            "tl_y_pct": 0,
            "tl_y_abs": 0,
            "br_x_pct": 0,
            "br_x_abs": 0,
            "br_y_pct": 0,
            "br_y_abs": 0,
            "tl_origin": -1,
            "br_origin": -1,
        }
        for kv in child.children:
            if not isinstance(kv, KeyVal):
                continue
            k = kv.keyword
            if k == "__ICLASS" and kv.values:
                iclass = str(kv.values[0])
            elif k == "__ACLASS" and kv.values:
                aclass = str(kv.values[0])
            elif k == "__TOPLEFT_X_PERCENTAGE" and kv.values:
                coords["tl_x_pct"] = _to_int(kv.values[0])
            elif k == "__TOPLEFT_X_ABSOLUTE" and kv.values:
                coords["tl_x_abs"] = _to_int(kv.values[0])
            elif k == "__TOPLEFT_Y_PERCENTAGE" and kv.values:
                coords["tl_y_pct"] = _to_int(kv.values[0])
            elif k == "__TOPLEFT_Y_ABSOLUTE" and kv.values:
                coords["tl_y_abs"] = _to_int(kv.values[0])
            elif k == "__BOTTOMRIGHT_X_PERCENTAGE" and kv.values:
                coords["br_x_pct"] = _to_int(kv.values[0])
            elif k == "__BOTTOMRIGHT_X_ABSOLUTE" and kv.values:
                coords["br_x_abs"] = _to_int(kv.values[0])
            elif k == "__BOTTOMRIGHT_Y_PERCENTAGE" and kv.values:
                coords["br_y_pct"] = _to_int(kv.values[0])
            elif k == "__BOTTOMRIGHT_Y_ABSOLUTE" and kv.values:
                coords["br_y_abs"] = _to_int(kv.values[0])
            elif k == "__TOPLEFT_ORIGIN" and kv.values:
                coords["tl_origin"] = _to_int(kv.values[0])
            elif k == "__BOTTOMRIGHT_ORIGIN" and kv.values:
                coords["br_origin"] = _to_int(kv.values[0])
            elif k == "__FLAGS" and kv.values:
                flags = tuple(str(v) for v in kv.values)
            elif k == "__CURSOR" and kv.values:
                cursor_name = str(kv.values[0])
            elif k == "__TCLASS" and kv.values:
                tclass_name = str(kv.values[0])
            elif k == "__KEEP_WHEN_SHADED" and kv.values:
                keep_when_shaded = str(kv.values[0]).upper() == "__ON"
            elif k == "__KEEP_ON_TOP" and kv.values:
                keep_on_top = str(kv.values[0]).upper() == "__ON"
            elif k == "__MIN_WIDTH" and kv.values:
                min_w = _to_int(kv.values[0])
            elif k == "__MAX_WIDTH" and kv.values:
                max_w = _to_int(kv.values[0])
            elif k == "__MIN_HEIGHT" and kv.values:
                min_h = _to_int(kv.values[0])
            elif k == "__MAX_HEIGHT" and kv.values:
                max_h = _to_int(kv.values[0])
        parts.append(
            ButtonPart(
                iclass_name=iclass,
                aclass=aclass,
                flags=flags,
                cursor_name=cursor_name,
                tclass_name=tclass_name,
                keep_when_shaded=keep_when_shaded,
                keep_on_top=keep_on_top,
                min_w=min_w,
                min_h=min_h,
                max_w=max_w,
                max_h=max_h,
                **coords,
            )
        )
    return tuple(parts)


def build_border(border_block: Block) -> BorderSpec:
    """Build a BorderSpec from a __BORDER block.

    Reads __BORDER_SIZE_{LEFT,RIGHT,TOP,BOTTOM} KeyVals and all
    __BORDER_PART children via extract_button_parts.
    """
    sizes: dict[str, int] = {"left": 0, "right": 0, "top": 0, "bottom": 0}
    for kv in border_block.children:
        if not isinstance(kv, KeyVal) or not kv.values:
            continue
        if kv.keyword == "__BORDER_SIZE_LEFT":
            sizes["left"] = _to_int(kv.values[0])
        elif kv.keyword == "__BORDER_SIZE_RIGHT":
            sizes["right"] = _to_int(kv.values[0])
        elif kv.keyword == "__BORDER_SIZE_TOP":
            sizes["top"] = _to_int(kv.values[0])
        elif kv.keyword == "__BORDER_SIZE_BOTTOM":
            sizes["bottom"] = _to_int(kv.values[0])
    name = _block_name(border_block) or "DEFAULT"
    return BorderSpec(
        name=name,
        border_size_left=sizes["left"],
        border_size_right=sizes["right"],
        border_size_top=sizes["top"],
        border_size_bottom=sizes["bottom"],
        parts=extract_button_parts(border_block),
    )
