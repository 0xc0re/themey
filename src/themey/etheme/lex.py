"""Tokenizer for E16 cfg files.

Recognized tokens:
  IDENT       — identifiers in any case, may begin with __ (e.g. __EDGE_SCALING,
                __BGN, __END, but also WashedBlue's ``titelleiste``).
                Regex: [A-Za-z_][A-Za-z0-9_]*
  NUMBER      — signed integers; floats are not used in E16 cfg.
                Regex: -?[0-9]+
  STRING      — double-quoted; no escape sequences in E16 source (verified
                against the E16 1.0.31 source).
                Regex: "([^"]*)"   (value stored without surrounding quotes)
                ALSO any bare word that is neither an IDENT nor a NUMBER —
                an unquoted path (``artwork/borders/left_u.png``, Tubular),
                a name with punctuation (``pager_titelleiste-``, WashedBlue).
  INCLUDE     — '#include' keyword token (not a comment — lexer checks literal
                'include' before entering the # comment path)
  ANGLE_PATH  — <path> immediately after INCLUDE (e.g. <definitions>)
  QUOTED_PATH — "path" immediately after INCLUDE (e.g. "borders/default.cfg")
  NEWLINE     — significant line-break token; the parser uses it to terminate
                top-level key-value lines.  Only emitted between non-whitespace
                tokens (consecutive blank lines collapse to one NEWLINE).
                ';' also emits NEWLINE: E16 treats it as a statement separator
                (cpp macro bodies join several statements on one physical line
                with ';' — see BlueIce's BP_START in borders/definitions.cfg).
  EOF         — sentinel at end of input.

Skipped:
  /* ... */  (multi-line C-style comments)  — newlines inside counted
  // ... \n  (C++ line comments) — E16's epp is run with C++ comments ON
              (e16-1.0.31 epp/cpplib.c:817 ``cplusplus_comments = 1``), so
              SilverMania's ``//__ACLASS ACTION_RESIZE_H`` is dead text.
              Quoted strings are lexed first, so a ``//`` inside quotes
              (URLs) survives, as it does in cpp.
  # ... \\n  (single-line hash comments)    — EXCEPT '#include' which starts
              an INCLUDE token, not a comment.  A hash line ending in a
              backslash continues onto the next line (multi-line #define
              bodies must not leak tokens).

Design notes:
  • Words are E16's unit. After epp, E16 reads every statement with
    ``sscanf(str, "%i %n%4000s %n", ...)`` (e16-1.0.31 config.c:185): the
    value is one whitespace-delimited word, whatever characters it holds,
    and names are matched verbatim with strcmp (iclass.c:341). So the scan
    loop grabs a whole bare word (up to whitespace, ';', '"', '#' or a
    ``/*`` comment opener) and classifies it afterwards — IDENT if it is
    entirely identifier characters, NUMBER if it is an integer, STRING
    otherwise. Splitting a word into an IDENT prefix plus junk would lose
    the value (the pre-2026-09 lexer only knew [_A-Z] identifiers and
    dropped ``titelleiste`` outright, leaving WashedBlue and eLap with zero
    resolvable iclasses and a blank frame).
  • Keywords stay the ``__UPPER`` set: the parser dispatches on the token
    text, so a lowercase IDENT is just a value (or a harmless top-level key
    when it starts a line — fonts.theme.cfg's ``font-default`` lines).
  • Hand-rolled state machine; uses stdlib re only for the master token regex.
  • A single compiled master-regex is scanned with re.Scanner / pos-based scan
    for simplicity and speed.  The alternative (re.Scanner) requires a class;
    we use a simple while-loop advancing self._pos.
  • '#include' is detected by checking whether the '#' character is immediately
    followed by the literal 'include' (case-sensitive) + at least one space or
    tab before the path.  If not, the '#' starts a line comment.
  • QUOTED_PATH and ANGLE_PATH are only valid immediately after INCLUDE.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum


class TokenKind(Enum):
    IDENT = "IDENT"
    NUMBER = "NUMBER"
    STRING = "STRING"
    INCLUDE = "INCLUDE"
    ANGLE_PATH = "ANGLE_PATH"
    QUOTED_PATH = "QUOTED_PATH"
    NEWLINE = "NEWLINE"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: object  # str for IDENT/STRING/PATH; int for NUMBER; None for NEWLINE/EOF/INCLUDE
    line: int  # 1-based


# Compiled regex patterns used inside the scan loop
_RE_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_RE_NUMBER = re.compile(r"-?[0-9]+")
#: One sscanf("%s") word: runs to whitespace, a ';' statement separator, a
#: quote, a '#' or the start of a /* or // comment.
_RE_BARE_WORD = re.compile(r'(?:(?!/[*/])[^\s;"#])+')
_RE_STRING = re.compile(r'"([^"]*)"')
_RE_ANGLE_PATH = re.compile(r"<([^>]*)>")
_RE_QUOTED_PATH = re.compile(r'"([^"]*)"')
_RE_C_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
_RE_WHITESPACE = re.compile(r"[ \t\r]+")  # horizontal whitespace (no newline)


def tokenize(text: str) -> list[Token]:
    """Tokenize an E16 cfg text string.  Returns a flat list of Token objects.

    The list always ends with a single EOF token.  NEWLINE tokens appear at
    most once between two non-whitespace-content positions (i.e. multiple blank
    lines produce a single NEWLINE token).
    """
    tokens: list[Token] = []
    pos = 0
    n = len(text)
    line = 1
    last_was_newline = False  # collapse consecutive newlines

    def _append(kind: TokenKind, value: object, tok_line: int) -> None:
        nonlocal last_was_newline
        if kind == TokenKind.NEWLINE:
            if last_was_newline:
                return  # collapse consecutive newlines
            last_was_newline = True
        else:
            last_was_newline = False
        tokens.append(Token(kind=kind, value=value, line=tok_line))

    while pos < n:
        ch = text[pos]

        # ------------------------------------------------------------------ #
        # Newline
        # ------------------------------------------------------------------ #
        if ch == "\n":
            _append(TokenKind.NEWLINE, None, line)
            line += 1
            pos += 1
            continue

        # ------------------------------------------------------------------ #
        # ';' — statement separator, same effect as a newline (E16 config.c)
        # ------------------------------------------------------------------ #
        if ch == ";":
            _append(TokenKind.NEWLINE, None, line)
            pos += 1
            continue

        # ------------------------------------------------------------------ #
        # Horizontal whitespace
        # ------------------------------------------------------------------ #
        m = _RE_WHITESPACE.match(text, pos)
        if m:
            pos = m.end()
            continue

        # ------------------------------------------------------------------ #
        # C-style block comment: /* ... */
        # ------------------------------------------------------------------ #
        if text[pos : pos + 2] == "/*":
            m = _RE_C_COMMENT.match(text, pos)
            if m:
                # Count newlines inside the comment
                line += m.group(0).count("\n")
                pos = m.end()
            else:
                # Unterminated comment — skip to end of text
                line += text[pos:].count("\n")
                pos = n
            continue

        # ------------------------------------------------------------------ #
        # C++ line comment: // ... (epp default, cpplib.c:817)
        # ------------------------------------------------------------------ #
        if text[pos : pos + 2] == "//":
            while pos < n and text[pos] != "\n":
                pos += 1
            continue  # main loop emits the NEWLINE

        # ------------------------------------------------------------------ #
        # '#' — either '#include' or a line comment
        # ------------------------------------------------------------------ #
        if ch == "#":
            # Check for '#include'
            if text[pos : pos + 8] == "#include" and pos + 8 < n and text[pos + 8] in " \t":
                _append(TokenKind.INCLUDE, None, line)
                pos += 8  # skip '#include'
                # Skip horizontal whitespace after '#include'
                m = _RE_WHITESPACE.match(text, pos)
                if m:
                    pos = m.end()
                # Now expect < or "
                if pos < n and text[pos] == "<":
                    m2 = _RE_ANGLE_PATH.match(text, pos)
                    if m2:
                        _append(TokenKind.ANGLE_PATH, m2.group(1), line)
                        pos = m2.end()
                elif pos < n and text[pos] == '"':
                    m2 = _RE_QUOTED_PATH.match(text, pos)
                    if m2:
                        _append(TokenKind.QUOTED_PATH, m2.group(1), line)
                        pos = m2.end()
                continue
            # Otherwise it's a line comment — skip to end of line.  A trailing
            # backslash continues the comment onto the next line (cpp-style
            # multi-line #define bodies).
            while True:
                start = pos
                while pos < n and text[pos] != "\n":
                    pos += 1
                if pos >= n or not text[start:pos].rstrip().endswith("\\"):
                    break
                pos += 1  # consume the newline, keep skipping the next line
                line += 1
            # Do NOT consume the final newline itself — main loop handles it
            continue

        # ------------------------------------------------------------------ #
        # Quoted string (only in non-include context)
        # ------------------------------------------------------------------ #
        if ch == '"':
            m = _RE_STRING.match(text, pos)
            if m:
                _append(TokenKind.STRING, m.group(1), line)
                pos = m.end()
            else:
                # Unterminated string — skip to EOL
                while pos < n and text[pos] != "\n":
                    pos += 1
            continue

        # ------------------------------------------------------------------ #
        # Bare word (E16 sscanf "%s"), classified after the fact:
        #   IDENT   [A-Za-z_][A-Za-z0-9_]*      (keywords and plain names)
        #   NUMBER  -?[0-9]+                    (signed integers)
        #   STRING  anything else               (unquoted paths, odd names)
        # ------------------------------------------------------------------ #
        m = _RE_BARE_WORD.match(text, pos)
        if m:
            word = m.group(0)
            if _RE_IDENT.fullmatch(word):
                _append(TokenKind.IDENT, word, line)
            elif _RE_NUMBER.fullmatch(word):
                _append(TokenKind.NUMBER, int(word), line)
            else:
                _append(TokenKind.STRING, word, line)
            pos = m.end()
            continue

        # ------------------------------------------------------------------ #
        # Unrecognized character (a lone '/' before '*' cannot happen — the
        # comment branch ran first; anything left is skipped silently)
        # ------------------------------------------------------------------ #
        pos += 1

    tokens.append(Token(kind=TokenKind.EOF, value=None, line=line))
    return tokens
