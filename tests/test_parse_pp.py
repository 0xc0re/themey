"""Tests for the E16 cfg preprocessor and parser leniency (parse.py).

E16 pipes every top-level cfg file through its bundled cpp (``epp``) before
parsing, and its line-based config reader is lenient about block structure.
These tests pin the constructs found in the real corpus:

- BlueIce: multi-line function-like ``#define`` macros (BP_START/BP_END) that
  expand to ``__BORDER_PART`` blocks, with ``;`` separating statements.
- Warp: object-like value macros (``#define TITLE_SIZE 18``) and a
  ``__BORDER`` block whose closing ``__END`` lives in an ``#include``d file.
- Tubular: an empty dangling ``__BORDER_PART __BGN`` implicitly closed when
  the next same-keyword block opens (E16's flat parser tolerates this).
- No_Frills/Spitfire2: a doubled ``__END`` at top level (pops nothing in E16).

Run:  uv run pytest tests/test_parse_pp.py -q
"""
from __future__ import annotations

from pathlib import Path

from themey.etheme.ast import Block, KeyVal
from themey.etheme.parse import parse_file, parse_tree

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_str(text: str, tmp_path: Path) -> list:
    p = tmp_path / "synthetic.cfg"
    p.write_text(text)
    return parse_file(p)


def _blocks(nodes: list, keyword: str) -> list[Block]:
    return [n for n in nodes if isinstance(n, Block) and n.keyword == keyword]


def _kv(block: Block, keyword: str) -> KeyVal | None:
    return next(
        (c for c in block.children if isinstance(c, KeyVal) and c.keyword == keyword),
        None,
    )


# ---------------------------------------------------------------------------
# Parser leniency (No_Frills / Spitfire2 / Tubular / EOF shapes)
# ---------------------------------------------------------------------------


def test_stray_top_level_end_is_tolerated(tmp_path: Path) -> None:
    """A doubled __END at top level pops nothing (epplets.cfg shape)."""
    text = (
        "__ICLASS __BGN\n"
        "__NAME EPPLET_POPUP_ENTRY\n"
        "__END\n"
        "__END\n"
        "__ICLASS __BGN\n"
        "__NAME EPPLET_HBAR_BASE\n"
        "__END\n"
    )
    nodes = _parse_str(text, tmp_path)
    iclasses = _blocks(nodes, "__ICLASS")
    assert len(iclasses) == 2
    names = [_kv(b, "__NAME").values[0] for b in iclasses]  # type: ignore[union-attr]
    assert names == ["EPPLET_POPUP_ENTRY", "EPPLET_HBAR_BASE"]


def test_unclosed_block_closes_at_eof(tmp_path: Path) -> None:
    """A block left open at EOF is closed implicitly (E16 tolerates this)."""
    text = "__BORDER __BGN\n__NAME DEFAULT\n"
    nodes = _parse_str(text, tmp_path)
    borders = _blocks(nodes, "__BORDER")
    assert len(borders) == 1
    kv = _kv(borders[0], "__NAME")
    assert kv is not None and kv.values == ("DEFAULT",)


def test_dangling_same_keyword_block_implicitly_closed(tmp_path: Path) -> None:
    """An empty __BORDER_PART __BGN is closed when the next part opens.

    Tubular's default.cfg has this typo; E16's flat parser treats a new
    __BORDER_PART as ending the previous one, so the real parts must land as
    direct children of the __BORDER block, and the final __END must close the
    border itself (not be swallowed by the dangler).
    """
    text = (
        "__BORDER __BGN\n"
        "  __NAME DEFAULT\n"
        "  __BORDER_PART __BGN\n"
        "\n"
        "  __BORDER_PART __BGN\n"
        "    __ICLASS VERTBARLEFT\n"
        "  __END\n"
        "  __BORDER_PART __BGN\n"
        "    __ICLASS VERTBARRIGHT\n"
        "  __END\n"
        "__END\n"
    )
    nodes = _parse_str(text, tmp_path)
    borders = _blocks(nodes, "__BORDER")
    assert len(borders) == 1
    parts = _blocks(list(borders[0].children), "__BORDER_PART")
    assert len(parts) == 3  # dangler + two real parts, all direct children
    iclasses = [_kv(p, "__ICLASS") for p in parts]
    assert [kv.values[0] for kv in iclasses if kv is not None] == [
        "VERTBARLEFT",
        "VERTBARRIGHT",
    ]


# ---------------------------------------------------------------------------
# Preprocessor: object-like and function-like #define (Warp / BlueIce shapes)
# ---------------------------------------------------------------------------


def test_object_like_define_expands_to_number(tmp_path: Path) -> None:
    """#define TITLE_SIZE 18 substitutes into values (Warp sizes.cfg shape)."""
    (tmp_path / "borders.cfg").write_text(
        "#define TITLE_SIZE 18\n"
        "__BORDER __BGN\n"
        "__NAME DEFAULT\n"
        "__BORDER_SIZE_TOP TITLE_SIZE\n"
        "__END\n"
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    border = _blocks(nodes, "__BORDER")[0]
    kv = _kv(border, "__BORDER_SIZE_TOP")
    assert kv is not None
    assert kv.values == (18,)


def test_function_like_multiline_define_expands(tmp_path: Path) -> None:
    """BP_START-style macros with backslash continuations and ';' separators."""
    (tmp_path / "borders.cfg").write_text(
        "#define BP_START(name,action,shade) \\\n"
        "__BORDER_PART  __BGN ; \\\n"
        "    __ICLASS name ; \\\n"
        "    __ACLASS action ; \\\n"
        "    __KEEP_WHEN_SHADED shade\n"
        "#define BP_END  __END\n"
        "__BORDER __BGN\n"
        "__NAME DEFAULT\n"
        " BP_START(SNOW_UPPER_LEFT, ACTION_RESIZE,  __ON)\n"
        " BP_END\n"
        "__END\n"
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    border = _blocks(nodes, "__BORDER")[0]
    parts = _blocks(list(border.children), "__BORDER_PART")
    assert len(parts) == 1
    assert _kv(parts[0], "__ICLASS").values == ("SNOW_UPPER_LEFT",)  # type: ignore[union-attr]
    assert _kv(parts[0], "__ACLASS").values == ("ACTION_RESIZE",)  # type: ignore[union-attr]
    assert _kv(parts[0], "__KEEP_WHEN_SHADED").values == ("__ON",)  # type: ignore[union-attr]


def test_defines_carry_across_includes(tmp_path: Path) -> None:
    """A macro defined in an included file expands in a later included file."""
    (tmp_path / "borders.cfg").write_text(
        '#include "sizes.cfg"\n#include "default.cfg"\n'
    )
    (tmp_path / "sizes.cfg").write_text("#define BORDER_SIZE 5\n")
    (tmp_path / "default.cfg").write_text(
        "__BORDER __BGN\n__NAME DEFAULT\n__BORDER_SIZE_LEFT BORDER_SIZE\n__END\n"
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    border = _blocks(nodes, "__BORDER")[0]
    assert _kv(border, "__BORDER_SIZE_LEFT").values == (5,)  # type: ignore[union-attr]


def test_macro_not_expanded_inside_strings(tmp_path: Path) -> None:
    """Quoted strings are opaque to macro expansion (cpp semantics)."""
    (tmp_path / "borders.cfg").write_text(
        "#define DEFAULT 99\n"
        '__BORDER __BGN\n__ANNOTATION "DEFAULT"\n__END\n'
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    border = _blocks(nodes, "__BORDER")[0]
    assert _kv(border, "__ANNOTATION").values == ("DEFAULT",)  # type: ignore[union-attr]


def test_commented_out_include_is_not_spliced(tmp_path: Path) -> None:
    """A /* commented out */ #include line must not be resolved."""
    (tmp_path / "borders.cfg").write_text(
        "/*\n#include \"gone.cfg\"\n*/\n__E_CFG_VERSION 1\n"
    )
    (tmp_path / "gone.cfg").write_text("__BORDER __BGN\n__NAME NOPE\n__END\n")
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    assert _blocks(nodes, "__BORDER") == []


# ---------------------------------------------------------------------------
# Preprocessor: include splicing (Warp shape)
# ---------------------------------------------------------------------------


def test_block_spanning_include_boundary(tmp_path: Path) -> None:
    """A __BORDER opened in one file may be closed in an #include'd file.

    Warp's default.cfg opens __BORDER, then ``#include <borders/edges.cfg>``
    supplies more parts and the closing __END arrives via a further include.
    cpp splices text, so the block must balance across files.
    """
    (tmp_path / "borders.cfg").write_text("#include <borders/default.cfg>\n")
    bdir = tmp_path / "borders"
    bdir.mkdir()
    (bdir / "default.cfg").write_text(
        "__BORDER __BGN\n"
        "__NAME DEFAULT\n"
        "__BORDER_PART __BGN\n__ICLASS TITLEBAR\n__END\n"
        "#include <borders/edges.cfg>\n"
    )
    (bdir / "edges.cfg").write_text(
        "__BORDER_PART __BGN\n__ICLASS ST\n__END\n"
        "__END\n"
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    borders = _blocks(nodes, "__BORDER")
    assert len(borders) == 1
    parts = _blocks(list(borders[0].children), "__BORDER_PART")
    names = [_kv(p, "__ICLASS").values[0] for p in parts]  # type: ignore[union-attr]
    assert names == ["TITLEBAR", "ST"]


def test_angle_include_resolves_from_asset_root(tmp_path: Path) -> None:
    """<path> includes resolve against the theme root, not the including file's
    directory (epp is invoked with -I <themedir>)."""
    (tmp_path / "borders.cfg").write_text("#include <borders/default.cfg>\n")
    bdir = tmp_path / "borders"
    bdir.mkdir()
    # From borders/default.cfg, <borders/edges.cfg> must mean root/borders/edges.cfg
    (bdir / "default.cfg").write_text("#include <borders/edges.cfg>\n")
    (bdir / "edges.cfg").write_text("__E_CFG_VERSION 7\n")
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    kvs = [n for n in nodes if isinstance(n, KeyVal) and n.keyword == "__E_CFG_VERSION"]
    assert len(kvs) == 1
    assert kvs[0].values == (7,)


def test_include_escaping_root_is_dropped(tmp_path: Path) -> None:
    """T-03-01: an include resolving outside asset_root is silently dropped."""
    outside = tmp_path / "outside.cfg"
    outside.write_text("__BORDER __BGN\n__NAME EVIL\n__END\n")
    root = tmp_path / "theme"
    root.mkdir()
    (root / "borders.cfg").write_text('#include "../outside.cfg"\n__E_CFG_VERSION 1\n')
    nodes = parse_tree(root, ["borders.cfg"])
    assert _blocks(nodes, "__BORDER") == []


def test_repeated_include_splices_again(tmp_path: Path) -> None:
    """cpp splices a file on every include — Warp's pager_bottom.cfg and
    transient.cfg both re-include borders/edges.cfg, whose chain carries
    each border's closing __END. A permanent dedup would break the second
    border's structure."""
    (tmp_path / "borders.cfg").write_text(
        '#include "one.cfg"\n#include "two.cfg"\n'
    )
    (tmp_path / "one.cfg").write_text(
        '__BORDER __BGN\n__NAME ONE\n#include "tail.cfg"\n'
    )
    (tmp_path / "two.cfg").write_text(
        '__BORDER __BGN\n__NAME TWO\n#include "tail.cfg"\n'
    )
    (tmp_path / "tail.cfg").write_text(
        "__BORDER_PART __BGN\n__ICLASS ST\n__END\n__END\n"
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    borders = _blocks(nodes, "__BORDER")
    assert len(borders) == 2
    for border in borders:
        parts = _blocks(list(border.children), "__BORDER_PART")
        assert len(parts) == 1  # both borders got their spliced part + __END


def test_include_cycle_terminates(tmp_path: Path) -> None:
    """T-03-02: mutually-including files terminate instead of looping."""
    (tmp_path / "borders.cfg").write_text('#include "a.cfg"\n')
    (tmp_path / "a.cfg").write_text('#include "b.cfg"\n__E_CFG_VERSION 1\n')
    (tmp_path / "b.cfg").write_text('#include "a.cfg"\n__E_CFG_VERSION 2\n')
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    versions = [n.values[0] for n in nodes if isinstance(n, KeyVal)]
    assert versions == [2, 1]


def test_definitions_include_still_skipped(tmp_path: Path) -> None:
    """#include <definitions> (E16's built-in macro file) is still dropped."""
    (tmp_path / "borders.cfg").write_text(
        "#include <definitions>\n__E_CFG_VERSION 21\n"
    )
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    kvs = [n for n in nodes if isinstance(n, KeyVal)]
    assert len(kvs) == 1
    assert kvs[0].keyword == "__E_CFG_VERSION"


def test_macro_body_with_adjacent_quoted_pieces_yields_one_name(tmp_path: Path) -> None:
    """Base's BUTTON_IMAGE(name,graphic) macro spells the iclass name as
    ``"BUTTON_"name`` and the art as ``"artwork/button_"graphic"_1.png"``.
    E16's GetLine drops quote characters (config.c:122-131), so both are
    single words; before this the name lexed as ("BUTTON_", "ICONIFY") and
    six themes of that family lost every button image."""
    (tmp_path / "imageclasses.cfg").write_text(
        "#define BUTTON_IMAGE(name,graphic) \\\n"
        "__ICLASS __BGN; \\\n"
        '  __NAME "BUTTON_"name;\\\n'
        '  __NORMAL "artwork/button_"graphic"_1.png";\\\n'
        "  __EDGE_SCALING 2 2 2 2;\\\n"
        "__END\n"
        "BUTTON_IMAGE(ICONIFY,iconify);\n"
    )
    nodes = parse_tree(tmp_path, ["imageclasses.cfg"])
    iclass = _blocks(nodes, "__ICLASS")[0]
    name = _kv(iclass, "__NAME")
    normal = _kv(iclass, "__NORMAL")
    assert name is not None and name.values == ("BUTTON_ICONIFY",)
    assert normal is not None and normal.values == ("artwork/button_iconify_1.png",)


# ---------------------------------------------------------------------------
# E16's own <definitions> macro file (bundled copy)
# ---------------------------------------------------------------------------

_MENUSTYLE_CFG = (
    "#include <definitions>\n"
    "__E_CFG_VERSION 1\n"
    'NORMAL_MENU_STYLE_VERTICAL("DEFAULT", "MENU", "MENU_TEXT", "MENU_BG", '
    '"MENU_SEL", "MENU_SUB", 40)\n'
)


def test_angle_definitions_expands_e16_menu_style_macro(tmp_path: Path) -> None:
    """Every corpus menustyles.cfg (223/223) declares its styles through
    the NORMAL_/NEXTSTEP_MENU_STYLE_* macros of E16's ``config/definitions``
    — a file no archive ships. The bundled copy must expand them."""
    (tmp_path / "menustyles.cfg").write_text(_MENUSTYLE_CFG)
    nodes = parse_tree(tmp_path, ["menustyles.cfg"])
    styles = _blocks(nodes, "__MENU_STYLE")
    assert len(styles) == 1
    style = styles[0]
    assert _kv(style, "__NAME") is not None
    assert _kv(style, "__NAME").values == ("DEFAULT",)
    assert _kv(style, "__BG_ICLASS").values == ("MENU_BG",)
    assert _kv(style, "__ITEM_ICLASS").values == ("MENU_SEL",)
    assert _kv(style, "__MAXIMUM_NUMBER_OF_ROWS").values == (40,)


def test_definitions_keyword_ids_stay_identifiers(tmp_path: Path) -> None:
    """definitions also ``#define``s every ``__KEYWORD`` (and ``__BGN``/
    ``__END``/``__ON``/``__OFF``) as E16's numeric config id. Those must
    NOT be expanded — themey's grammar is keyword-based, and ``__OFF`` in a
    macro body has to reach the analyzer as the identifier."""
    (tmp_path / "menustyles.cfg").write_text(
        _MENUSTYLE_CFG + "__ICLASS __BGN\n  __NAME MENU_BG\n__END\n"
    )
    nodes = parse_tree(tmp_path, ["menustyles.cfg"])
    assert len(_blocks(nodes, "__ICLASS")) == 1
    style = _blocks(nodes, "__MENU_STYLE")[0]
    assert _kv(style, "__USE_ITEM_BACKGROUNDS").values == ("__OFF",)


def test_theme_define_overrides_bundled_definitions(tmp_path: Path) -> None:
    """A theme's own ``#define`` of a definitions macro name wins (cpp:
    last definition in effect), so hand-rolled variants keep working."""
    (tmp_path / "menustyles.cfg").write_text(
        "#include <definitions>\n"
        "#define NORMAL_MENU_STYLE_VERTICAL(a,b,c,d,e,f,g) __MENU_STYLE __BGN;"
        " __NAME a; __BG_ICLASS f; __END\n"
        'NORMAL_MENU_STYLE_VERTICAL("X", "B", "T", "BG", "IT", "SUB", 1)\n'
    )
    nodes = parse_tree(tmp_path, ["menustyles.cfg"])
    style = _blocks(nodes, "__MENU_STYLE")[0]
    assert _kv(style, "__BG_ICLASS").values == ("SUB",)


def test_default_entry_files_include_menustyles(tmp_path: Path) -> None:
    """E16's ThemeConfigLoad (config.c) loads menustyles.cfg; so must the
    default entry list."""
    (tmp_path / "menustyles.cfg").write_text(_MENUSTYLE_CFG)
    nodes = parse_tree(tmp_path)
    assert len(_blocks(nodes, "__MENU_STYLE")) == 1
