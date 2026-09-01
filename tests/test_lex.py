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


def test_semicolon_is_statement_separator() -> None:
    """';' separates statements like a newline (E16 config.c treats it so;
    cpp macro bodies join statements with ';' on one physical line)."""
    tokens = tokenize("__ICLASS FOO ; __ACLASS BAR")
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.IDENT,
        TokenKind.IDENT,
        TokenKind.NEWLINE,
        TokenKind.IDENT,
        TokenKind.IDENT,
        TokenKind.EOF,
    ]


def test_hash_comment_with_continuation_skips_next_line() -> None:
    """A '#' directive line ending in '\\' continues onto the next line —
    multi-line #define bodies must not leak tokens (BlueIce definitions.cfg)."""
    tokens = _content(tokenize("#define BP_START(x) \\\n__BORDER_PART __BGN ; \\\n__ICLASS x\nQUX"))
    assert len(tokens) == 1
    assert tokens[0].value == "QUX"


def test_line_numbers_track_newlines() -> None:
    """Line counter increments across newlines; second-line token has line==2."""
    tokens = tokenize("FOO\nBAR")
    bar = next(t for t in tokens if t.kind == TokenKind.IDENT and t.value == "BAR")
    assert bar.line == 2


# ---------------------------------------------------------------------------
# Bare words: E16 reads every value with sscanf("%s") (config.c:185), so a
# value is ANY whitespace-delimited word — lowercase names, mixed case, and
# unquoted paths all count. Names are matched with strcmp (iclass.c:341),
# case-sensitively and verbatim.
# ---------------------------------------------------------------------------


def test_lowercase_identifier_is_ident() -> None:
    """WashedBlue/eLap name their iclasses in lowercase German
    (``titelleiste``, ``knopf_kill``); the old [_A-Z] regex dropped them."""
    tokens = _content(tokenize("__ICLASS titelleiste"))
    assert [(t.kind, t.value) for t in tokens] == [
        (TokenKind.IDENT, "__ICLASS"),
        (TokenKind.IDENT, "titelleiste"),
    ]


def test_mixed_case_identifier_is_one_ident() -> None:
    tokens = _content(tokenize("__NAME MyBorder_v2"))
    assert [(t.kind, t.value) for t in tokens] == [
        (TokenKind.IDENT, "__NAME"),
        (TokenKind.IDENT, "MyBorder_v2"),
    ]


def test_unquoted_path_is_a_single_string_token() -> None:
    """``__NORMAL artwork/borders/left_u.png`` without quotes (Tubular,
    SilverMania): one STRING carrying the whole word, not IDENT fragments."""
    tokens = _content(tokenize("__NORMAL artwork/borders/left_u.png"))
    assert [(t.kind, t.value) for t in tokens] == [
        (TokenKind.IDENT, "__NORMAL"),
        (TokenKind.STRING, "artwork/borders/left_u.png"),
    ]


def test_bare_word_with_trailing_punctuation_keeps_it() -> None:
    """WashedBlue's ``pager_titelleiste-`` (trailing hyphen) is one word to
    sscanf and must round-trip verbatim so the __ICLASS reference in the
    border matches the declaration."""
    tokens = _content(tokenize("__ICLASS pager_titelleiste-"))
    assert [(t.kind, t.value) for t in tokens] == [
        (TokenKind.IDENT, "__ICLASS"),
        (TokenKind.STRING, "pager_titelleiste-"),
    ]


def test_bare_word_stops_at_semicolon_and_quote() -> None:
    tokens = tokenize('__ICLASS foo;__NAME bar"x"')
    assert [(t.kind, t.value) for t in tokens] == [
        (TokenKind.IDENT, "__ICLASS"),
        (TokenKind.IDENT, "foo"),
        (TokenKind.NEWLINE, None),
        (TokenKind.IDENT, "__NAME"),
        (TokenKind.IDENT, "bar"),
        (TokenKind.STRING, "x"),
        (TokenKind.EOF, None),
    ]


def test_numbers_still_lex_as_numbers_inside_bare_words() -> None:
    """The bare-word path must not swallow the NUMBER classification."""
    tokens = _content(tokenize("__EDGE_SCALING 4 -4 0 0"))
    assert [t.kind for t in tokens][1:] == [TokenKind.NUMBER] * 4
    assert [t.value for t in tokens][1:] == [4, -4, 0, 0]


def test_double_slash_is_a_line_comment() -> None:
    """E16's epp enables C++ comments by default (epp/cpplib.c:817), so
    SilverMania's ``//__ACLASS ACTION_RESIZE_H`` is dead text. The old
    lexer skipped the slashes and ACTIVATED the statement."""
    tokens = _content(tokenize("__ICLASS FOO //__ACLASS ACTION_RESIZE_H\n__NAME BAR"))
    assert [(t.kind, t.value) for t in tokens] == [
        (TokenKind.IDENT, "__ICLASS"),
        (TokenKind.IDENT, "FOO"),
        (TokenKind.IDENT, "__NAME"),
        (TokenKind.IDENT, "BAR"),
    ]


def test_double_slash_inside_quotes_is_not_a_comment() -> None:
    tokens = _content(tokenize('__EXEC "http://heagy.com/etheme/"'))
    assert tokens[1].value == "http://heagy.com/etheme/"
