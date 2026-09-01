"""AST node dataclasses for the E16 cfg parser.

The parser (parse.py) returns a flat ``list[AstNode]`` of top-level nodes.
Blocks contain children (also AstNode) in their ``children`` tuple, so the
result is a tree despite being returned as a flat top-level list.

All dataclasses are frozen (immutable after construction) and hashable.

``AstNode`` is a type alias used by the parser and analysis layers:

  from themey.etheme.ast import AstNode, Block, Include, KeyVal

``atoi`` is the one value-coercion helper: E16 reads every numeric field
with C ``atoi``/``sscanf("%i")`` on a whitespace-delimited word
(borders.c:1220 ``i2 = atoi(s2)``, iclass.c:446), so AluminE's
``__TOPLEFT_Y_ABSOLUTE 19P`` is 19 and AeonFlux's ``--`` is 0. The lexer
hands such words over as STRING values; analyzers must not ``int()`` them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_RE_ATOI = re.compile(r"\s*([+-]?[0-9]+)")


def atoi(value: object) -> int:
    """C ``atoi`` over an AST value: the leading integer, else 0.

    NUMBER tokens arrive as ``int`` and pass through; STRING/IDENT values
    yield their leading ``[+-]?digits`` prefix (``"19P"`` → 19) or 0 when
    there is none (``"--"`` → 0), exactly as E16's ``atoi(s2)`` does.
    """
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    m = _RE_ATOI.match(str(value))
    return int(m.group(1)) if m else 0


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
