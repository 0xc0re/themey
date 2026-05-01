"""Tests for the E16 cfg parser (src/themey/etheme/parse.py).

Run:  uv run pytest tests/test_parse.py -q
"""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.etheme.ast import Block, Include, KeyVal
from themey.etheme.parse import parse_file, parse_tree

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _walk(nodes: list) -> list:
    """Depth-first walk over a node list, yielding every node (Block + children)."""
    result = []
    for n in nodes:
        result.append(n)
        if isinstance(n, Block):
            result.extend(_walk(list(n.children)))
    return result


def _parse_str(text: str) -> list:
    """Parse a string as if it were a cfg file using a tmp path (via parse_file workaround)."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".cfg", delete=False) as f:
        f.write(text)
        tmp = Path(f.name)
    try:
        return parse_file(tmp)
    finally:
        tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Synthetic string tests
# ---------------------------------------------------------------------------


def test_parse_simple_block() -> None:
    """Simple block: keyword __BGN ... __END yields Block with one KeyVal child."""
    nodes = _parse_str("__BORDER\n__BGN\n__NAME DEFAULT\n__END\n")
    assert len(nodes) == 1
    blk = nodes[0]
    assert isinstance(blk, Block)
    assert blk.keyword == "__BORDER"
    assert blk.head_values == ()
    # Find __NAME KeyVal child
    kv = next((c for c in blk.children if isinstance(c, KeyVal) and c.keyword == "__NAME"), None)
    assert kv is not None
    assert kv.values == ("DEFAULT",)


def test_parse_nested_blocks() -> None:
    """Nested __BORDER_PART block inside __BORDER block."""
    text = "__BORDER\n__BGN\n__BORDER_PART\n__BGN\n__NAME P1\n__END\n__END\n"
    nodes = _parse_str(text)
    assert len(nodes) == 1
    outer = nodes[0]
    assert isinstance(outer, Block)
    assert outer.keyword == "__BORDER"
    inner = next((c for c in outer.children if isinstance(c, Block)), None)
    assert inner is not None
    assert inner.keyword == "__BORDER_PART"


def test_parse_aclass_field() -> None:
    """__ACLASS inside __BORDER_PART body is captured as a regular KeyVal child."""
    text = (
        "__BORDER_PART\n"
        "__BGN\n"
        "__ICLASS BUTTON_CLOSE\n"
        "__ACLASS ACTION_CLOSE\n"
        "__END\n"
    )
    nodes = _parse_str(text)
    assert len(nodes) == 1
    blk = nodes[0]
    assert isinstance(blk, Block)
    kv = next((c for c in blk.children if isinstance(c, KeyVal) and c.keyword == "__ACLASS"), None)
    assert kv is not None
    assert kv.values == ("ACTION_CLOSE",)


def test_parse_negative_integer() -> None:
    """__BOTTOMRIGHT_X_ABSOLUTE -27 yields a KeyVal with int value -27."""
    nodes = _parse_str("__BORDER\n__BGN\n__BOTTOMRIGHT_X_ABSOLUTE -27\n__END\n")
    all_nodes = _walk(nodes)
    kv = next(
        (n for n in all_nodes if isinstance(n, KeyVal) and n.keyword == "__BOTTOMRIGHT_X_ABSOLUTE"),
        None,
    )
    assert kv is not None
    assert kv.values == (-27,)


def test_parse_string_value() -> None:
    """__NAME "Aliens Theme" yields KeyVal with string value (no surrounding quotes)."""
    nodes = _parse_str('__BORDER\n__BGN\n__NAME "Aliens Theme"\n__END\n')
    all_nodes = _walk(nodes)
    kv = next(
        (n for n in all_nodes if isinstance(n, KeyVal) and n.keyword == "__NAME"),
        None,
    )
    assert kv is not None
    assert kv.values == ("Aliens Theme",)


def test_parse_skips_unknown_blocks() -> None:
    """Unknown keywords (__DESKTOP etc.) do NOT raise — generic-block-store rule."""
    text = (
        "__DESKTOP\n"
        "__BGN\n"
        "__BACKGROUND_LAYER 0\n"
        "__USE_ON_DESKTOP 0\n"
        "__END\n"
    )
    nodes = _parse_str(text)
    assert len(nodes) == 1
    blk = nodes[0]
    assert isinstance(blk, Block)
    assert blk.keyword == "__DESKTOP"
    # Two KeyVal children
    kvs = [c for c in blk.children if isinstance(c, KeyVal)]
    assert len(kvs) == 2


def test_parse_tolerates_misspelled_forground_color() -> None:
    """Parser preserves __FORGROUND_COLOR misspelling; analyze tier handles aliases."""
    text = (
        "__TCLASS TEXT1\n"
        "__BGN\n"
        "__NORMAL\n"
        "__FORGROUND_COLOR 200 200 150\n"
        "__END\n"
    )
    nodes = _parse_str(text)
    assert len(nodes) == 1
    blk = nodes[0]
    assert isinstance(blk, Block)
    assert blk.keyword == "__TCLASS"
    assert blk.head_values == ("TEXT1",)
    # __FORGROUND_COLOR KeyVal with three int values
    kv = next(
        (c for c in blk.children if isinstance(c, KeyVal) and c.keyword == "__FORGROUND_COLOR"),
        None,
    )
    assert kv is not None
    assert kv.values == (200, 200, 150)


def test_parse_top_level_kv() -> None:
    """Top-level key-value (not inside a block) produces a top-level KeyVal node."""
    nodes = _parse_str("__E_CFG_VERSION 21\n")
    assert len(nodes) == 1
    assert isinstance(nodes[0], KeyVal)
    assert nodes[0].keyword == "__E_CFG_VERSION"
    assert nodes[0].values == (21,)


# ---------------------------------------------------------------------------
# Fixture-based tests using tiny.etheme
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"
TINY = FIXTURES / "tiny.etheme"
ALIENS = FIXTURES / "Aliens.etheme"


@pytest.fixture(scope="module")
def tiny_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Extract tiny.etheme to a shared tmp dir; return asset_root."""

    tmp = tmp_path_factory.mktemp("tiny")
    # We need to return the asset_root while inside the context.
    # Use a persistent tmpdir approach: extract manually.
    import tarfile

    with tarfile.open(TINY, "r:gz") as tf:
        tf.extractall(tmp)
    return tmp  # borders.cfg is at tmp root directly


@pytest.fixture
def aliens_extracted():  # type: ignore[return]
    """Extract Aliens.etheme; yield asset_root inside the context manager."""
    from themey.etheme.archive import extract

    with extract(ALIENS) as raw:
        yield raw.asset_root


def test_parse_tree_resolves_include(tiny_root: Path) -> None:
    """parse_tree resolves #include "borders/default.cfg" and inlines its nodes."""
    nodes = parse_tree(tiny_root, ["borders.cfg"])
    all_nodes = _walk(nodes)
    borders = [n for n in all_nodes if isinstance(n, Block) and n.keyword == "__BORDER"]
    assert len(borders) >= 1
    default_border = next(
        (b for b in borders if b.head_values and b.head_values[0] == "DEFAULT"),
        None,
    )
    assert default_border is not None


def test_parse_tree_skips_definitions_include(tmp_path: Path) -> None:
    """#include <definitions> is silently dropped; does not raise."""
    cfg = tmp_path / "borders.cfg"
    cfg.write_text("#include <definitions>\n__E_CFG_VERSION 21\n")
    nodes = parse_tree(tmp_path, ["borders.cfg"])
    # Should have at most one node (the version KV), definitely no crash
    include_nodes = [n for n in nodes if isinstance(n, Include)]
    assert len(include_nodes) == 0  # definitions include was dropped
    kv_nodes = [n for n in nodes if isinstance(n, KeyVal)]
    assert len(kv_nodes) == 1
    assert kv_nodes[0].keyword == "__E_CFG_VERSION"


def _block_name(blk: Block) -> str | None:
    """Return block name from either head_values[0] or __NAME child KeyVal.

    Aliens.etheme uses the legacy E16 macro style where block names come from
    a ``__NAME <NAME>`` KeyVal inside the block body (not as head_values before
    ``__BGN``).  Newer/synthetic cfg files often include the name as a head
    value.  This helper checks both forms.
    """
    if blk.head_values:
        return str(blk.head_values[0])
    name_kv = next(
        (c for c in blk.children if isinstance(c, KeyVal) and c.keyword == "__NAME"),
        None,
    )
    if name_kv and name_kv.values:
        return str(name_kv.values[0])
    return None


def test_parse_tree_aliens_default_cfg(aliens_extracted: Path) -> None:
    """Aliens borders/default.cfg parses to >=1 __BORDER with >=8 __BORDER_PART children.

    Additionally verifies that at least one __BORDER_PART has an __ACLASS child
    of ACTION_CLOSE or ACTION_KILL.

    Note: Aliens uses the legacy macro style — block names appear as __NAME
    KeyVals inside the body, not as head_values before __BGN.
    """
    nodes = parse_tree(aliens_extracted, ["borders.cfg"])
    all_nodes = _walk(nodes)
    border_blocks = [n for n in all_nodes if isinstance(n, Block) and n.keyword == "__BORDER"]
    assert len(border_blocks) >= 1

    # Find DEFAULT border by __NAME child KeyVal (Aliens macro style) or head_values
    default_border = next(
        (b for b in border_blocks if _block_name(b) == "DEFAULT"),
        None,
    )
    assert default_border is not None, "No DEFAULT border found"

    part_blocks = [
        c
        for c in default_border.children
        if isinstance(c, Block) and c.keyword == "__BORDER_PART"
    ]
    assert len(part_blocks) >= 8

    # At least one part has __ACLASS ACTION_CLOSE or ACTION_KILL
    def _aclass_of(part: Block) -> str | None:
        kv = next(
            (c for c in part.children if isinstance(c, KeyVal) and c.keyword == "__ACLASS"),
            None,
        )
        return str(kv.values[0]) if kv and kv.values else None

    aclasses = [_aclass_of(p) for p in part_blocks]
    assert any(a in ("ACTION_CLOSE", "ACTION_KILL") for a in aclasses)


def test_parse_tree_aliens_imageclasses(aliens_extracted: Path) -> None:
    """Aliens imageclasses.cfg contains __ICLASS for four required names.

    Note: Aliens uses legacy macro style — __ICLASS names appear as __NAME
    KeyVals inside the block body, not as head_values before __BGN.
    """
    nodes = parse_tree(aliens_extracted, ["imageclasses.cfg"])
    all_nodes = _walk(nodes)
    iclasses = [n for n in all_nodes if isinstance(n, Block) and n.keyword == "__ICLASS"]
    # Collect names from either head_values or __NAME child KeyVal
    names = {_block_name(b) for b in iclasses} - {None}
    required = {"TITLE_BAR_HORIZONTAL", "BUTTON_KILL", "BUTTON_ICONIFY", "BUTTON_MAXIMIZE"}
    missing = required - names  # type: ignore[arg-type]
    assert not missing, f"Missing __ICLASS blocks: {missing}"
