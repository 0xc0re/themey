"""AST node dataclasses for the E16 cfg parser.

The parser (parse.py) returns a flat ``list[AstNode]`` of top-level nodes.
Blocks contain children (also AstNode) in their ``children`` tuple, so the
result is a tree despite being returned as a flat top-level list.

All dataclasses are frozen (immutable after construction) and hashable.

``AstNode`` is a type alias used by the parser and analysis layers:

  from themey.etheme.ast import AstNode, Block, Include, KeyVal
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Include:
    """An E16 ``#include`` directive.

    Attributes:
        path:     The path string inside the directive (e.g. ``definitions``,
                  ``borders/default.cfg``).
        is_angle: ``True`` for angle-bracket form ``<path>`` (used for the
                  built-in E16 macro file ``<definitions>``); ``False`` for
                  double-quote form ``"path"`` (used for relative includes).
        line:     1-based source line number — for human-readable error messages.
    """

    path: str
    is_angle: bool
    line: int


@dataclass(frozen=True)
class KeyVal:
    """A single key → values line inside a block (or at the top level).

    E16 key-value lines have the form::

        __KEYWORD value1 value2 ...

    where values are integers, unquoted identifiers, or double-quoted strings.
    The ``values`` tuple may be empty for bare flag lines (e.g. ``__NORMAL``).

    Attributes:
        keyword: The leading E16 keyword (e.g. ``"__EDGE_SCALING"``,
                 ``"__ACLASS"``, ``"__FORGROUND_COLOR"``).
                 Misspellings (``__FORGROUND_COLOR``) are stored verbatim —
                 the analyze layer in ``src/themey/analyze/`` handles aliases.
        values:  Tuple of parsed values.  Each element is an ``int`` (for
                 NUMBER tokens) or a ``str`` (for IDENT / STRING tokens).
        line:    1-based source line number.
    """

    keyword: str
    values: tuple[object, ...]
    line: int


@dataclass(frozen=True)
class Block:
    """A ``__KEYWORD ... __BGN ... __END`` block node.

    E16 cfg blocks can nest (e.g. ``__BORDER_PART`` inside ``__BORDER``).
    Children are stored as a tuple of ``AstNode`` so blocks are recursively
    typed.

    Attributes:
        keyword:     The opening keyword (e.g. ``"__BORDER"``, ``"__ICLASS"``).
        head_values: Values between the opening keyword and ``__BGN`` — e.g.
                     for ``__BORDER DEFAULT __BGN`` this is ``("DEFAULT",)``;
                     for ``__BORDER_PART __BGN`` this is ``()``.
        children:    Ordered tuple of top-level nodes inside this block —
                     may include nested ``Block``, ``KeyVal``, or ``Include``.
        line:        1-based source line of the opening keyword.
    """

    keyword: str
    head_values: tuple[object, ...]
    children: tuple[AstNode, ...]
    line: int


# Union type alias used throughout the codebase
AstNode = Block | KeyVal | Include
