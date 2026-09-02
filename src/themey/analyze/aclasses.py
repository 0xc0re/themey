"""AST ``__ACLASS __BGN`` blocks → the primary E16 action verb per name.

E16's ``ThemeConfigLoad`` (config.c:580) loads ``actionclasses.cfg``,
``buttons.cfg`` and ``slideouts.cfg`` BEFORE ``borders.cfg``, so a border
part's ``__ACLASS <name>`` reference names an action class the theme (or
E16's own stock config) already registered. themey used to read that
reference as an opaque string and match it against a fixed table of stock
names, which dropped every theme-private name — Ganymede's title bar has a
close button bound to ``ACTION_GANYMEDE_KILL`` and shipped with no buttons
at all.

The verb is the ``__A_*`` macro name, kept verbatim: parse.py registers
only the FUNCTION-like macros from the bundled ``definitions``, and
``#define __A_KILL wop * close`` is object-like, so the AST never sees the
expanded IPC string.

``__NAME`` opens a class; the LAST definition of a name wins, mirroring
``ConfigFileRead``'s ``CONFIG_CLASSNAME`` case (aclass.c:321-332), which
calls ``ActionclassEmpty`` on an existing name and refills it. The primary
verb is the FIRST ``__ACTION`` in the block: E16 writes the button-1
binding first and the later ``__NEXT_ACTION`` stanzas are the alternate
mouse buttons, which an Aurorae button has no way to express.
"""
from __future__ import annotations

from pathlib import Path

from themey.etheme.ast import Block, KeyVal

# E16's own config/actionclasses.cfg, bundled verbatim beside the macro file.
# ConfigFileLoad("actionclasses.cfg", theme_path, ...) falls back to E16's
# config dir when the theme ships none (config.c ConfigFileFind -> FindFile),
# which is how a 2009 theme binds a border part to ACTION_WINDOW_SLIDEOUT
# without ever defining it — 100 of the corpus's border __ACLASS references.
_BUNDLED_ACTIONCLASSES = (
    Path(__file__).parent.parent / "etheme" / "data" / "e16_actionclasses.cfg"
)
_stock: dict[str, str] | None = None


def stock_aclasses() -> dict[str, str]:
    """E16 1.0.31's stock action classes → their primary verb (cached).

    themey loads these UNCONDITIONALLY as the lowest-precedence layer,
    where E16 skips them entirely once the theme ships its own
    actionclasses.cfg. The two differ only for a stock name the theme's
    file omits, and resolving such a name is strictly better than dropping
    the part; a name the theme does define still overrides, since the
    theme's blocks are merged on top.
    """
    global _stock
    if _stock is None:
        # Imported here: etheme.parse imports nothing from analyze, but
        # keeping the dependency lazy avoids a module-load cycle if that
        # ever changes.
        from themey.etheme.parse import parse_tree

        nodes = parse_tree(
            _BUNDLED_ACTIONCLASSES.parent, [_BUNDLED_ACTIONCLASSES.name]
        )
        _stock = build_aclasses(
            [n for n in nodes if isinstance(n, Block) and n.keyword == "__ACLASS"]
        )
    return dict(_stock)


def build_aclasses(blocks: list[Block]) -> dict[str, str]:
    """``__ACLASS`` blocks → ``{name: primary __A_* verb}``.

    A block without a ``__NAME`` or without any ``__ACTION`` contributes
    nothing — E16 registers the class but a part bound to it fires no
    window operation, which is the same as plain chrome to us.
    """
    verbs: dict[str, str] = {}
    for block in blocks:
        name: str | None = None
        verb: str | None = None
        for child in block.children:
            if not isinstance(child, KeyVal) or not child.values:
                continue
            if child.keyword == "__NAME" and name is None:
                name = str(child.values[0])
            elif child.keyword == "__ACTION" and verb is None:
                verb = str(child.values[0])
        if name is not None and verb is not None:
            verbs[name] = verb
    return verbs
