"""Recursive-descent parser + mini-cpp preprocessor for E16 cfg files.

Generic-block-store: any keyword followed by __BGN ... __END forms a Block;
keys not starting a block form KeyVal lines. Unknown keywords do NOT raise —
the analyze layer in src/themey/analyze/ picks the blocks it understands.

**Preprocessing (parse_tree only).** E16 pipes every top-level cfg file
through its bundled cpp (``epp -I <themedir>``) before parsing, so real
themes rely on cpp semantics the token grammar alone cannot express:

- ``#define`` macros — object-like value constants (Warp's
  ``#define TITLE_SIZE 18`` in borders/sizes.cfg) and multi-line
  function-like macros with backslash continuations (BlueIce's
  ``BP_START(name,action,shade)`` in borders/definitions.cfg, whose body
  joins statements with ';' — the lexer emits NEWLINE for ';').
- ``#include`` splices *text*, so a ``__BORDER`` block may open in one file
  and close in another (Warp: default.cfg -> edges.cfg -> corners.cfg).
  Angle includes resolve against asset_root (epp's -I dir), quoted includes
  against the including file's directory first. ``#include <definitions>``
  (E16's built-in macro file, never shipped in archives) resolves to the
  bundled copy in ``data/e16_definitions`` — but ONLY its function-like
  macros are registered (``NORMAL_MENU_STYLE_VERTICAL``, ``DEFINE_TOOLTIP``,
  ...; every corpus menustyles.cfg depends on them). Its object-like
  defines are E16's numeric config ids (``__BGN 999``, ``__ON 1``) and X
  cursor constants; expanding those would turn the keyword grammar into
  numbers, so ``__OFF`` in a macro body reaches the analyzer as itself.

Macro expansion never touches quoted strings, and comments are stripped
before directive scanning so a commented-out ``#include`` is not spliced.
``#if``/``#ifdef``/``#ifndef``/``#elif``/``#else``/``#endif`` are honoured
(integer literals, ``defined(X)``, macro names; E16's always-present epp
symbols count as defined, ``_PREDEFINED``) — eMac keeps its base colour
art instead of the last ``#ifdef`` variant, and ``#if 0`` blocks vanish.

**Leniency.** E16's own config reader (config.c) is line-based and lenient;
the parser mirrors three tolerated corpus shapes instead of raising, each
logged as a warning (and appended to ``parse_tree``'s optional ``notes``):

- a stray top-level ``__END`` pops nothing (No_Frills/Spitfire2
  imageclasses/epplets.cfg carry a doubled ``__END``);
- a block still open at EOF is closed implicitly;
- a block whose own keyword re-opens inside it (``__BORDER_PART __BGN``
  directly inside a dangling empty ``__BORDER_PART`` — Tubular's
  borders/default.cfg) implicitly closes the current block first, matching
  E16's flat parser. E16 grammar never legitimately nests a block kind
  inside itself.

Grammar:

    file     := (toplevel)*
    toplevel := include | block | top_kv
    include  := '#include' ('<' path '>' | '"' path '"') NEWLINE
    block    := keyword head_value* '__BGN' (statement)* '__END'
    statement:= include | block | top_kv
    top_kv   := keyword value* NEWLINE
    keyword  := IDENT
    value    := IDENT | NUMBER | STRING

Security mitigations:
- T-03-01: include resolution rejects any candidate whose resolved path does
  not start with the resolved ``asset_root`` prefix.
- T-03-02: ``seen: set[Path]`` guards re-entry so recursive ``#include``
  cycles splice nothing instead of looping indefinitely.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from .ast import AstNode, Block, Include, KeyVal
from .lex import Token, TokenKind, tokenize

log = logging.getLogger(__name__)


class ParseError(Exception):
    """Raised on truly malformed input the lenient parser cannot represent.

    Kept as the subsystem's typed error; the corpus-tolerated shapes
    (stray __END, unclosed block at EOF) no longer raise it.
    """


def parse_file(path: Path) -> list[AstNode]:
    """Parse one cfg file, WITHOUT preprocessing (no #define / #include).

    Returns top-level nodes (Blocks, KeyVals, Includes). ``parse_tree`` is
    the preprocessing entry point used by the pipeline.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    tokens = tokenize(text)
    return _Parser(tokens, source=str(path)).parse_program()


def parse_tree(
    asset_root: Path,
    entry_files: list[str] | None = None,
    notes: list[str] | None = None,
) -> list[AstNode]:
    """Preprocess and parse a theme tree starting from entry_files.

    Each entry file is run through the mini-cpp preprocessor (see module
    docstring): includes are spliced textually, ``#define`` macros are
    collected and expanded. Missing entry files are silently skipped (some
    themes omit textclasses.cfg).

    The macro table is shared across entry files: macros defined under
    borders.cfg stay visible to later entry files (lenient superset of
    E16's per-file epp runs). Repeated includes splice again, as cpp does;
    only an include cycle is cut short.

    ``notes`` (optional) collects human-readable leniency notes; they are
    always also logged as warnings.

    Returns a flat list of all top-level AstNode entries from all parsed
    files, in entry-file declaration order, with includes inlined at their
    position.
    """
    if entry_files is None:
        entry_files = [
            "borders.cfg",
            "imageclasses.cfg",
            "textclasses.cfg",
            "cursors.cfg",
            # E16's ThemeConfigLoad (config.c:593-594) also loads
            # tooltips.cfg (its __TOOLTIP blocks name the tooltip art and
            # text) and menustyles.cfg (__MENU_STYLE names the menu
            # background iclass), in that order.
            "tooltips.cfg",
            "menustyles.cfg",
            # windowmatches.cfg: __MATCH_WINDOW blocks — the __USE_ICON
            # rules feed the per-app icon theme (analyze/windowmatches.py);
            # the bundled definitions expand USE_ICON_IMAGE_FOR_CLIENT_*.
            "windowmatches.cfg",
        ]
    seen: set[Path] = set()
    defines: _Defines = {}
    nodes: list[AstNode] = []
    for entry in entry_files:
        p = asset_root / entry
        if p.is_file():
            text = _preprocess(p, asset_root, seen, defines)
            tokens = tokenize(text)
            nodes.extend(
                _Parser(tokens, source=str(p), notes=notes).parse_program()
            )
    return nodes


# ---------------------------------------------------------------------------
# Mini-cpp preprocessor (the epp subset real themes use)
# ---------------------------------------------------------------------------

# name -> (params or None for object-like, body text)
_Defines = dict[str, tuple[tuple[str, ...] | None, str]]

# '(' must follow the name with no space for a function-like macro (cpp rule)
_RE_DEFINE = re.compile(
    r"^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)(\([^)]*\))?[ \t]*(.*)$"
)
_RE_INCLUDE_LINE = re.compile(r'^\s*#\s*include\s+(?:<([^>]+)>|"([^"]+)")')
_RE_COND = re.compile(r"^\s*#\s*(ifdef|ifndef|if|elif|else|endif)\b\s*(.*)$")
_RE_DEFINED = re.compile(r"defined\s*\(?\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)?")

#: Symbols E16's epp run predefines (config.c:243-255) that a theme can
#: test with #ifdef: the version/path symbols are always set. The
#: SCREEN_RESOLUTION_WxH / SCREEN_WIDTH_W / SCREEN_HEIGHT_H / SCREEN_DEPTH_D
#: and THEME_VARIANT_<name> symbols depend on the user's display/choice
#: and are left undefined (the corpus only ever tests THEME_VARIANT_
#: colour names — eMac — whose default build has none defined).
_PREDEFINED = frozenset({
    "ENLIGHTENMENT_VERSION", "ENLIGHTENMENT_ROOT", "ENLIGHTENMENT_BIN",
    "ENLIGHTENMENT_THEME", "ECONFDIR", "ECACHEDIR",
})
_RE_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

#: Verbatim E16 1.0.31 ``config/definitions`` (see data/README.md).
_BUNDLED_DEFINITIONS = Path(__file__).parent / "data" / "e16_definitions"
# Object-like defines in <definitions> that must reach the parser verbatim:
# E16 keyword ids and __A_* action names (__*), X cursor ids (XC_*).
_IDENTITY_DEFINE = re.compile(r"(?:__|XC_)")
_bundled_macros: _Defines | None = None


def _bundled_definitions() -> _Defines:
    """The bundled definitions file's usable macros, parsed once.

    Every FUNCTION-like macro is registered. Of the object-like ones only
    those NOT named ``__*`` or ``XC_*`` are (see ``_IDENTITY_DEFINE``):
    that prefix pair is exactly E16's own vocabulary — the numeric config
    ids (``__BGN 999``, ``__ON 1``, ``__NORMAL 402``), the ``XC_*`` X
    cursor constants, and the ``__A_*`` action macros whose bodies are IPC
    command strings (``__A_KILL`` -> ``wop * close``). Expanding any of
    those would replace the keyword grammar with numbers and replace an
    action's identity with a command line (analyze/aclasses.py reads the
    ``__A_*`` NAME).

    The 36 object-like macros that remain are all block-structure sugar —
    ``END_SLIDEOUT``/``END_BORDER``/``END_IMAGE`` -> ``__END``,
    ``BEGIN_FONTS`` -> ``__FONTS __BGN``, ``TEXT_JUSTIFY_CENTER`` ->
    ``__JUSTIFICATION 512``, the ``__ON`` flag shorthands. Skipping them
    left every ``BEGIN_*``/``END_*`` pair in the corpus unterminated, so
    the block swallowed everything after it: Ganymede's ``__ACLASS``
    blocks ended up inside an unclosed ``__SLIDEOUT`` and its window
    buttons were dropped.
    """
    global _bundled_macros
    if _bundled_macros is None:
        macros: _Defines = {}
        text = _BUNDLED_DEFINITIONS.read_text(encoding="utf-8", errors="replace")
        for ln in _join_continuations(_strip_c_comments(text)).split("\n"):
            m = _RE_DEFINE.match(ln)
            if m is None:
                continue
            if m.group(2) is not None:
                params: tuple[str, ...] | None = tuple(
                    p.strip() for p in m.group(2)[1:-1].split(",") if p.strip()
                )
            elif _IDENTITY_DEFINE.match(m.group(1)):
                continue  # E16's own keyword / cursor / action vocabulary
            else:
                params = None
            macros[m.group(1)] = (params, m.group(3).strip())
        _bundled_macros = macros
    return _bundled_macros
_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _strip_c_comments(text: str) -> str:
    """Remove /* ... */ comments, preserving line count (cpp strips comments
    before directives — a commented-out #include must not be spliced)."""
    text = _RE_BLOCK_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    idx = text.find("/*")
    if idx != -1:  # unterminated comment — drop to end, like the lexer
        text = text[:idx] + "\n" * text[idx:].count("\n")
    return text


def _join_continuations(text: str) -> str:
    """Join backslash-continued lines, padding to preserve line numbering."""
    out: list[str] = []
    buf = ""
    joined = 0
    for ln in text.split("\n"):
        r = ln.rstrip()
        if r.endswith("\\"):
            buf += r[:-1] + " "
            joined += 1
        else:
            out.append(buf + ln)
            out.extend([""] * joined)
            buf = ""
            joined = 0
    if buf:
        out.append(buf)
    return "\n".join(out)


def _resolve_include(
    angle: str | None,
    quoted: str | None,
    including_file: Path,
    root: Path,
) -> Path | None:
    """Resolve an include path, or None to drop it.

    Angle form searches asset_root first (epp runs with -I <themedir>),
    quoted form the including file's directory first; each falls back to
    the other. T-03-01: candidates escaping asset_root are rejected.
    """
    name = angle if angle is not None else quoted
    if name is None:
        return None
    if angle is not None and name == "definitions":
        return _BUNDLED_DEFINITIONS  # E16's macro file, never in archives
    root_resolved = str(root.resolve())
    if angle is not None:
        candidates = [root / name, including_file.parent / name]
    else:
        candidates = [including_file.parent / name, root / name]
    for candidate in candidates:
        target = candidate.resolve()
        if not (
            str(target) == root_resolved
            or str(target).startswith(root_resolved + "/")
        ):
            continue  # T-03-01: silently drop path-traversal attempts
        if target.is_file():
            return target
    return None  # missing file — silently drop (stale includes in legacy themes)


def _split_args(argstr: str) -> list[str]:
    """Split a macro argument list on top-level commas."""
    args: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in argstr:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            args.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    args.append("".join(cur))
    return args


def _expand_once(line: str, defines: _Defines) -> str:
    """One macro-substitution pass over a line; quoted strings are opaque."""
    out: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == '"':
            j = line.find('"', i + 1)
            j = n if j == -1 else j + 1
            out.append(line[i:j])
            i = j
            continue
        m = _RE_WORD.match(line, i)
        if not m:
            out.append(ch)
            i += 1
            continue
        word = m.group(0)
        i = m.end()
        entry = defines.get(word)
        if entry is None:
            out.append(word)
            continue
        params, body = entry
        if params is None:  # object-like
            out.append(body)
            continue
        # Function-like: need '(' args ')' on this line, else leave untouched
        k = i
        while k < n and line[k] in " \t":
            k += 1
        if k >= n or line[k] != "(":
            out.append(word)
            continue
        depth = 0
        end = -1
        for e in range(k, n):
            if line[e] == "(":
                depth += 1
            elif line[e] == ")":
                depth -= 1
                if depth == 0:
                    end = e
                    break
        if end == -1:  # unbalanced call — leave untouched
            out.append(word)
            continue
        args = _split_args(line[k + 1 : end])
        i = end + 1
        expansion = body
        # Arity mismatch (malformed theme): substitute the pairs that exist
        for param, arg in zip(params, args, strict=False):
            expansion = re.sub(
                rf"\b{re.escape(param)}\b", arg.strip(), expansion
            )
        out.append(expansion)
    return "".join(out)


def _expand_line(line: str, defines: _Defines) -> str:
    """Expand macros to a fixpoint (bounded — self-referential defines stop)."""
    for _ in range(8):
        new = _expand_once(line, defines)
        if new == line:
            break
        line = new
    return line


def _cond_value(expr: str, defines: _Defines) -> bool:
    """Evaluate a ``#if``/``#elif`` expression the way the corpus uses them:
    an integer literal (``#if 0`` — ThiNicE/Spring/Summer disable an
    iclass), ``defined(X)``/``defined X`` with optional ``!``, and
    object-like macro names (their value, atoi). Anything richer is
    treated as false, matching epp's result for undefined identifiers."""
    e = expr.strip()
    if not e:
        return False
    m = re.fullmatch(r"([+-]?\d+)", e)
    if m:
        return int(m.group(1)) != 0
    neg = e.startswith("!")
    if neg:
        e = e[1:].strip()
    m = _RE_DEFINED.fullmatch(e)
    if m:
        name = m.group(1)
        val = name in defines or name in _PREDEFINED
        return (not val) if neg else val
    m = re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", e)
    if m:
        macro = defines.get(e)
        val = False
        if macro is not None and macro[0] is None:
            body = macro[1].strip()
            mm = re.match(r"[+-]?\d+", body)
            val = bool(mm and int(mm.group(0)) != 0)
        elif e in _PREDEFINED:
            val = True
        return (not val) if neg else val
    return False


def _preprocess(
    path: Path,
    root: Path,
    seen: set[Path],
    defines: _Defines,
) -> str:
    """Read ``path``, splice includes, collect #defines, expand macros.

    T-03-02: ``seen`` holds the include chain currently being spliced, so a
    cycle splices nothing instead of looping. It is NOT a permanent dedup: cpp
    splices a file again on every repeated include, and Warp depends on it —
    pager_bottom.cfg and transient.cfg each re-include borders/edges.cfg,
    whose chain carries their borders' closing __END.
    """
    rp = path.resolve()
    if rp in seen:
        return ""
    seen.add(rp)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        text = _join_continuations(_strip_c_comments(text))

        out_lines: list[str] = []
        # Conditional stack: (this arm active, some arm of this #if already
        # taken, enclosing region active). epp honours #if/#ifdef/#ifndef/
        # #elif/#else/#endif; before this every arm was parsed, so eMac's
        # six #ifdef colour variants all applied and the LAST one won.
        cond: list[tuple[bool, bool, bool]] = []
        for ln in text.split("\n"):
            if ln.lstrip().startswith("#"):
                mc = _RE_COND.match(ln)
                if mc:
                    kind, arg = mc.group(1), mc.group(2)
                    outer = cond[-1][0] if cond else True
                    if kind in ("if", "ifdef", "ifndef"):
                        if kind == "if":
                            val = _cond_value(arg, defines)
                        else:
                            name = arg.strip().split()[0] if arg.strip() else ""
                            val = name in defines or name in _PREDEFINED
                            if kind == "ifndef":
                                val = not val
                        cond.append((outer and val, val, outer))
                    elif kind == "elif" and cond:
                        _active, taken, enclosing = cond[-1]
                        val = (not taken) and _cond_value(arg, defines)
                        cond[-1] = (enclosing and val, taken or val, enclosing)
                    elif kind == "else" and cond:
                        _active, taken, enclosing = cond[-1]
                        cond[-1] = (enclosing and not taken, True, enclosing)
                    elif kind == "endif" and cond:
                        cond.pop()
                    out_lines.append("")
                    continue
                if cond and not cond[-1][0]:
                    out_lines.append("")  # directive inside an inactive arm
                    continue
                m = _RE_DEFINE.match(ln)
                if m:
                    name, paren, body = m.group(1), m.group(2), m.group(3)
                    params: tuple[str, ...] | None = None
                    if paren is not None:
                        params = tuple(
                            p.strip() for p in paren[1:-1].split(",") if p.strip()
                        )
                    defines[name] = (params, body.strip())
                    out_lines.append("")
                    continue
                m = _RE_INCLUDE_LINE.match(ln)
                if m:
                    target = _resolve_include(m.group(1), m.group(2), path, root)
                    if target == _BUNDLED_DEFINITIONS:
                        # Macros only, and never over a theme's own
                        # earlier definition of the same name (cpp keeps
                        # the LAST definition; a theme's #define after the
                        # include also overwrites — dict assignment order).
                        for name, macro in _bundled_definitions().items():
                            defines.setdefault(name, macro)
                        out_lines.append("")
                    elif target is not None:
                        out_lines.append(
                            _preprocess(target, root, seen, defines)
                        )
                    else:
                        out_lines.append("")
                    continue
                out_lines.append("")  # any other '#' line is a plain comment
                continue
            if cond and not cond[-1][0]:
                out_lines.append("")
                continue
            out_lines.append(_expand_line(ln, defines) if defines else ln)
        return "\n".join(out_lines)
    finally:
        seen.discard(rp)


# ---------------------------------------------------------------------------
# Internal parser class
# ---------------------------------------------------------------------------


class _Parser:
    """Token-stream consumer for the E16 cfg grammar.

    Implements the BNF in the module docstring, with the E16-faithful
    leniency rules from the module docstring.
    """

    def __init__(
        self,
        tokens: list[Token],
        source: str = "<string>",
        notes: list[str] | None = None,
    ) -> None:
        self._tokens = tokens
        self._pos = 0
        self.source = source
        self._notes = notes

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def _note(self, msg: str) -> None:
        """Record a leniency note: always logged, optionally collected."""
        log.warning("%s", msg)
        if self._notes is not None:
            self._notes.append(msg)

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

    def _peek_after_current_skipping_newlines(self) -> Token:
        """Return the first non-NEWLINE token after the current one."""
        i = self._pos + 1
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

    def _parse_ident_production(self) -> AstNode | None:
        """Dispatch: block or top_kv depending on whether __BGN follows.

        A production starting with IDENT is a block if __BGN appears after the
        keyword and any head-value tokens.  Otherwise it is a top-level KeyVal.

        Strategy: collect the keyword + head-values, peeking to find __BGN.
        """
        keyword_tok = self._advance()  # consume the keyword IDENT
        keyword = str(keyword_tok.value)

        # A stray __END at this level pops nothing — E16 tolerates it
        # (doubled __END in No_Frills/Spitfire2 imageclasses/epplets.cfg)
        if keyword == "__END":
            self._note(
                f"parse: stray __END at line {keyword_tok.line} in "
                f"{self.source} ignored"
            )
            return None

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
                # Unclosed block — close implicitly, as E16 does
                self._note(
                    f"parse: block '{keyword}' (opened at line {line}) in "
                    f"{self.source} not closed by __END; closed at EOF"
                )
                break
            if self._is_end(tok):
                self._advance()  # consume __END
                break
            if (
                tok.kind == TokenKind.IDENT
                and tok.value == keyword
                and self._is_bgn(self._peek_after_current_skipping_newlines())
            ):
                # The block's own keyword re-opens inside it: E16's flat
                # parser treats this as the current block ending (Tubular's
                # dangling empty __BORDER_PART).  Return without consuming;
                # the parent loop parses the sibling.
                self._note(
                    f"parse: '{keyword}' re-opened at line {tok.line} in "
                    f"{self.source} before the one at line {line} was closed; "
                    f"closing the earlier block implicitly"
                )
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
