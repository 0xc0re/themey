"""AST ``__MENU_STYLE`` blocks → MenuStyleSpec dict.

Mirrors E16's ``MenuStyleConfigLoad`` (menus.c:1701-1760): ``__BG_ICLASS``,
``__ITEM_ICLASS``, ``__SUBMENU_ICLASS``, ``__BORDER``, ``__TCLASS`` are
names; ``__USE_ITEM_BACKGROUNDS`` is read with ``atoi`` (``__ON``/``__OFF``
arrive as identifiers from the bundled definitions file, so those words
are mapped first). When item backgrounds are on the menu window has no
background of its own — ``MenuRedraw`` never touches ``bg_iclass`` and the
loader frees it — so the spec's ``bg_iclass`` is None regardless of key
order (E16 only frees a bg named BEFORE the flag, but one named after is
never drawn either).

The block name sits in ``head_values`` (``__MENU_STYLE X __BGN``) or in a
``__NAME`` child (the definitions macros); nameless blocks are skipped and
a repeated name keeps the last block, as E16's list lookup does.
"""
from __future__ import annotations

from themey.etheme.ast import Block, KeyVal, atoi
from themey.ir import MenuStyleSpec

_NAME_KEYS = {
    "__BG_ICLASS": "bg_iclass",
    "__ITEM_ICLASS": "item_iclass",
    "__SUBMENU_ICLASS": "submenu_iclass",
    "__BORDER": "border",
    "__TCLASS": "tclass",
}


def _flag(value: object) -> bool:
    if isinstance(value, str):
        if value == "__ON":
            return True
        if value == "__OFF":
            return False
    return atoi(value) != 0


def build_menu_styles(blocks: list[Block]) -> dict[str, MenuStyleSpec]:
    styles: dict[str, MenuStyleSpec] = {}
    for block in blocks:
        name = str(block.head_values[0]) if block.head_values else None
        fields: dict[str, object] = {}
        use_item_bg = False
        for child in block.children:
            if not isinstance(child, KeyVal) or not child.values:
                continue
            if child.keyword == "__NAME" and name is None:
                name = str(child.values[0])
            elif child.keyword in _NAME_KEYS:
                fields[_NAME_KEYS[child.keyword]] = str(child.values[0])
            elif child.keyword == "__USE_ITEM_BACKGROUNDS":
                use_item_bg = _flag(child.values[0])
        if not name:
            continue
        if use_item_bg:
            fields.pop("bg_iclass", None)
        styles[name] = MenuStyleSpec(name=name, use_item_bg=use_item_bg, **fields)  # type: ignore[arg-type]
    return styles
