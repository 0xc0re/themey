"""Recursive-descent parser for E16 cfg files.

Generic-block-store: any keyword followed by __BGN ... __END forms a Block;
keys not starting a block form KeyVal lines. Unknown keywords do NOT raise —
the analyze layer in src/themey/analyze/ picks the blocks it understands.

``#include <definitions>`` is silently skipped (E16's built-in macro file is
not shipped in .etheme archives). Other includes are resolved relative to
asset_root.

Grammar (from 01-RESEARCH.md Pattern 1):

    file     := (toplevel)*
    toplevel := include | block | top_kv
    include  := '#include' ('<' path '>' | '"' path '"') NEWLINE
    block    := keyword head_value* '__BGN' (statement)* '__END'
    statement:= include | block | top_kv
    top_kv   := keyword value* NEWLINE
    keyword  := IDENT
    value    := IDENT | NUMBER | STRING

Security mitigations (T-03-01, T-03-02 from plan threat model):
- T-03-01: ``_parse_with_includes`` rejects includes whose resolved path does
  not start with the resolved ``asset_root`` prefix.
- T-03-02: ``seen: set[Path]`` guards re-entry so recursive ``#include`` cycles
  return an empty list instead of looping indefinitely.
"""
from __future__ import annotations

from pathlib import Path

from .ast import AstNode, Block, Include, KeyVal
from .lex import Token, TokenKind, tokenize


class ParseError(Exception):
    """Raised on truly malformed input (e.g. mismatched __BGN/__END)."""


def parse_file(path: Path) -> list[AstNode]:
    """Parse one cfg file.  Returns top-level nodes (Blocks, KeyVals, Includes)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    tokens = tokenize(text)
    return _Parser(tokens, source=str(path)).parse_program()


def parse_tree(
    asset_root: Path,
    entry_files: list[str] | None = None,
) -> list[AstNode]:
    """Parse a theme tree starting from entry_files; resolve #include directives.

    Resolves ``#include "path"`` by reading the referenced file (relative to
    the current file's directory) and inlining its top-level nodes at the
    include position.

    ``#include <definitions>`` is silently skipped (E16's built-in macro file
    is not shipped in .etheme archives).

    Missing entry files are silently skipped (some themes omit textclasses.cfg).

    Returns a flat list of all top-level AstNode entries from all parsed files,
    in entry-file declaration order, with includes inlined at their position.
    """
    if entry_files is None:
        entry_files = ["borders.cfg", "imageclasses.cfg", "textclasses.cfg"]
    seen: set[Path] = set()
    nodes: list[AstNode] = []
    for entry in entry_files:
        p = asset_root / entry
        if p.is_file():
            nodes.extend(_parse_with_includes(p, asset_root, seen))
    return nodes


def _parse_with_includes(
    path: Path,
    root: Path,
    seen: set[Path],
) -> list[AstNode]:
    """Parse ``path`` and recursively inline #include directives.

    T-03-01: Silently drops any include whose resolved path escapes ``root``.
    T-03-02: ``seen`` prevents re-entering the same file (cycle guard).
    """
    rp = path.resolve()
    if rp in seen:
        return []  # cycle guard (T-03-02)
    seen.add(rp)

    root_resolved = str(root.resolve())
    out: list[AstNode] = []

    for node in parse_file(path):
        if isinstance(node, Include):
            # Silently skip the built-in E16 macro file
            if node.is_angle and node.path == "definitions":
                continue
            # Resolve relative to the including file's directory
            target = (path.parent / node.path).resolve()
            # T-03-01: reject includes that escape asset_root
            if not (
                str(target) == root_resolved
                or str(target).startswith(root_resolved + "/")
            ):
                continue  # silently drop path-traversal attempts
            if target.is_file():
                out.extend(_parse_with_includes(target, root, seen))
            # If file missing — silently drop (stale includes in legacy themes)
        else:
            out.append(node)

    return out


# ---------------------------------------------------------------------------
# Internal parser class
# ---------------------------------------------------------------------------


class _Parser:
    """Token-stream consumer for the E16 cfg grammar.

    Implements the BNF from 01-RESEARCH.md Pattern 1.
    """

    def __init__(self, tokens: list[Token], source: str = "<string>") -> None:
        self._tokens = tokens
        self._pos = 0
        self.source = source

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _peek(self) -> Token:
        """Return current token without advancing."""
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        # Should never happen because EOF is always last, but be safe
        return Token(kind=TokenKind.EOF, value=None, line=0)

    def _advance(self) -> Token:
        """Consume and return current token."""
        tok = self._peek()
        self._pos += 1
        return tok

    def _skip_newlines(self) -> None:
        """Discard consecutive NEWLINE tokens."""
        while self._peek().kind == TokenKind.NEWLINE:
            self._advance()

    def _peek_skipping_newlines(self) -> Token:
        """Return the next non-NEWLINE token without consuming any tokens."""
        i = self._pos
        while i < len(self._tokens) and self._tokens[i].kind == TokenKind.NEWLINE:
            i += 1
        if i < len(self._tokens):
            return self._tokens[i]
        return Token(kind=TokenKind.EOF, value=None, line=0)

    def _is_bgn(self, tok: Token) -> bool:
        return tok.kind == TokenKind.IDENT and tok.value == "__BGN"

    def _is_end(self, tok: Token) -> bool:
        return tok.kind == TokenKind.IDENT and tok.value == "__END"

    # ------------------------------------------------------------------
    # Grammar productions
    # ------------------------------------------------------------------

    def parse_program(self) -> list[AstNode]:
        """file := (toplevel)*"""
        nodes: list[AstNode] = []
        self._skip_newlines()
        while self._peek().kind != TokenKind.EOF:
            node = self._parse_toplevel()
            if node is not None:
                nodes.append(node)
            self._skip_newlines()
        return nodes

    def _parse_toplevel(self) -> AstNode | None:
        """toplevel := include | block | top_kv"""
        tok = self._peek()

        if tok.kind == TokenKind.INCLUDE:
            return self._parse_include()

        if tok.kind == TokenKind.IDENT:
            return self._parse_ident_production()

        # Unexpected token — skip and continue
        self._advance()
        return None

    def _parse_include(self) -> Include | None:
        """include := '#include' ('<' path '>' | '"' path '"')"""
        inc_tok = self._advance()  # consume INCLUDE
        path_tok = self._peek()
        if path_tok.kind == TokenKind.ANGLE_PATH:
            self._advance()
            return Include(path=str(path_tok.value), is_angle=True, line=inc_tok.line)
        if path_tok.kind == TokenKind.QUOTED_PATH:
            self._advance()
            return Include(path=str(path_tok.value), is_angle=False, line=inc_tok.line)
        # Malformed include (no path token) — skip
        return None

    def _parse_ident_production(self) -> AstNode:
        """Dispatch: block or top_kv depending on whether __BGN follows.

        A production starting with IDENT is a block if __BGN appears after the
        keyword and any head-value tokens.  Otherwise it is a top-level KeyVal.

        Strategy: collect the keyword + head-values, peeking to find __BGN.
        """
        keyword_tok = self._advance()  # consume the keyword IDENT
        keyword = str(keyword_tok.value)

        # Special case: __END at this level is a parse error (mismatched block)
        if keyword == "__END":
            raise ParseError(
                f"unexpected __END at line {keyword_tok.line} in {self.source}"
            )

        # Collect head-values (tokens between keyword and __BGN or NEWLINE/EOF)
        head_values: list[object] = []
        while True:
            nxt = self._peek()
            if nxt.kind == TokenKind.EOF:
                break
            if nxt.kind == TokenKind.NEWLINE:
                # Check if the next non-NL token is __BGN
                lookahead = self._peek_skipping_newlines()
                if self._is_bgn(lookahead):
                    # Block whose keyword/head and __BGN are on separate lines
                    self._skip_newlines()  # consume the NEWLINEs
                    break
                # Not a block — it's a top_kv; stop collecting values
                break
            if self._is_bgn(nxt):
                # __BGN on same line as keyword
                break
            if self._is_end(nxt):
                # __END appeared where we expected values — stop (likely a bare
                # keyword line at end of a block)
                break
            # Value tokens: IDENT, NUMBER, STRING
            if nxt.kind in (TokenKind.IDENT, TokenKind.NUMBER, TokenKind.STRING):
                self._advance()
                head_values.append(nxt.value)
            else:
                # Unexpected token type — skip
                self._advance()

        # Now peek (after head-values consumed, NEWLINEs before __BGN skipped)
        nxt = self._peek()
        if self._is_bgn(nxt):
            # It's a block
            return self._parse_block_body(keyword, tuple(head_values), keyword_tok.line)

        # It's a top-level KeyVal (line ended without __BGN)
        # Consume the terminating NEWLINE if present
        if self._peek().kind == TokenKind.NEWLINE:
            self._advance()
        return KeyVal(keyword=keyword, values=tuple(head_values), line=keyword_tok.line)

    def _parse_block_body(
        self,
        keyword: str,
        head_values: tuple[object, ...],
        line: int,
    ) -> Block:
        """block := '__BGN' (statement)* '__END'

        Called after the keyword + head_values have been consumed.
        The current token should be __BGN.
        """
        bgn_tok = self._advance()  # consume __BGN
        _ = bgn_tok  # line info available if needed for error messages

        children: list[AstNode] = []
        self._skip_newlines()

        while True:
            tok = self._peek()
            if tok.kind == TokenKind.EOF:
                # Unclosed block — raise informative error
                raise ParseError(
                    f"unexpected EOF inside block '{keyword}' "
                    f"(opened at line {line}) in {self.source}"
                )
            if self._is_end(tok):
                self._advance()  # consume __END
                break
            child = self._parse_toplevel()
            if child is not None:
                children.append(child)
            self._skip_newlines()

        return Block(
            keyword=keyword,
            head_values=head_values,
            children=tuple(children),
            line=line,
        )
