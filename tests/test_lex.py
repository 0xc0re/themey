"""Tests for the E16 cfg lexer (src/themey/etheme/lex.py).

Run:  uv run pytest tests/test_lex.py -q
"""
from __future__ import annotations

from themey.etheme.lex import Token, TokenKind, tokenize

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _content(tokens: list[Token]) -> list[Token]:
    """Filter out NEWLINE and EOF tokens (not relevant to most tests)."""
    return [t for t in tokens if t.kind not in (TokenKind.NEWLINE, TokenKind.EOF)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_skips_c_comments() -> None:
    """Multi-line C-style /* ... */ comments are silently dropped."""
    tokens = _content(tokenize("FOO /* multi\nline */ BAR"))
    assert len(tokens) == 2
    assert tokens[0].kind == TokenKind.IDENT
    assert tokens[0].value == "FOO"
    assert tokens[1].kind == TokenKind.IDENT
    assert tokens[1].value == "BAR"


def test_skips_hash_comments() -> None:
    """# ... newline comments are silently dropped (line after survives)."""
    tokens = _content(tokenize("FOO # this is a comment\nBAR"))
    assert len(tokens) == 2
    assert tokens[0].value == "FOO"
    assert tokens[1].value == "BAR"


def test_negative_integers() -> None:
    """Signed negative integers tokenize as NUMBER with int value < 0."""
    tokens = _content(tokenize("__X -27"))
    assert len(tokens) == 2
    assert tokens[1].kind == TokenKind.NUMBER
    assert tokens[1].value == -27


def test_quoted_strings() -> None:
    """Double-quoted strings produce a STRING token; surrounding quotes excluded."""
    tokens = _content(tokenize('__NAME "Aliens Theme"'))
    assert len(tokens) == 2
    assert tokens[1].kind == TokenKind.STRING
    assert tokens[1].value == "Aliens Theme"


def test_idents_with_double_underscore() -> None:
    """Identifiers starting with __ are valid IDENT tokens."""
    tokens = _content(tokenize("__BORDER_PART"))
    assert len(tokens) == 1
    assert tokens[0].kind == TokenKind.IDENT
    assert tokens[0].value == "__BORDER_PART"


def test_include_directive_tokenizes() -> None:
    """#include <definitions> yields INCLUDE + ANGLE_PATH tokens."""
    tokens = _content(tokenize("#include <definitions>"))
    assert len(tokens) == 2
    assert tokens[0].kind == TokenKind.INCLUDE
    assert tokens[1].kind == TokenKind.ANGLE_PATH
    assert tokens[1].value == "definitions"


def test_include_quoted_path() -> None:
    """#include "borders/default.cfg" yields INCLUDE + QUOTED_PATH tokens."""
    tokens = _content(tokenize('#include "borders/default.cfg"'))
    assert len(tokens) == 2
    assert tokens[0].kind == TokenKind.INCLUDE
    assert tokens[1].kind == TokenKind.QUOTED_PATH
    assert tokens[1].value == "borders/default.cfg"


def test_line_numbers_track_newlines() -> None:
    """Line counter increments across newlines; second-line token has line==2."""
    tokens = tokenize("FOO\nBAR")
    bar = next(t for t in tokens if t.kind == TokenKind.IDENT and t.value == "BAR")
    assert bar.line == 2
