"""Tests for the __CURSOR block parser (analyze/cursors.py)."""
from __future__ import annotations

from pathlib import Path

from themey.analyze.cursors import extract_cursors
from themey.etheme.ast import Block, KeyVal


def _kv(keyword: str, *values: object, line: int = 1) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=line)


def _cursor_block(
    name: str,
    *,
    xbm: str | None = "artwork/cursors/x.xbm",
    fg: tuple[int, int, int] = (255, 255, 255),
    bg: tuple[int, int, int] = (0, 0, 0),
    hot_x: int | None = None,
    hot_y: int | None = None,
    native_id: str | None = None,
) -> Block:
    """Build an AST __CURSOR block of the form found in Aliens cursors.cfg."""
    children: list[KeyVal] = [_kv("__NAME", name)]
    if xbm is not None:
        children.append(_kv("__XBM_FILE", xbm))
    if native_id is not None:
        children.append(_kv("__NATIVE_ID", native_id))
    children.append(_kv("__FG_COLOR", *fg))
    children.append(_kv("__BG_COLOR", *bg))
    if hot_x is not None:
        children.append(_kv("__HOT_X", hot_x))
    if hot_y is not None:
        children.append(_kv("__HOT_Y", hot_y))
    return Block(
        keyword="__CURSOR",
        head_values=(),
        children=tuple(children),
        line=1,
    )


def test_extract_cursors_returns_one_spec_per_block(tmp_path: Path) -> None:
    asset_root = tmp_path
    (asset_root / "artwork" / "cursors").mkdir(parents=True)
    (asset_root / "artwork" / "cursors" / "x.xbm").write_text("#define x 1\n")

    nodes = [_cursor_block("DEFAULT")]
    cursors = extract_cursors(nodes, asset_root)
    assert len(cursors) == 1
    c = cursors[0]
    assert c.name == "DEFAULT"
    assert c.xbm_path is not None and c.xbm_path.name == "x.xbm"
    assert c.fg_rgb == (255, 255, 255)
    assert c.bg_rgb == (0, 0, 0)
    assert c.hot_x == 0  # default when unspecified
    assert c.hot_y == 0


def test_extract_cursors_with_hotspot(tmp_path: Path) -> None:
    nodes = [_cursor_block("MOVE", hot_x=4, hot_y=8)]
    cursors = extract_cursors(nodes, tmp_path)
    assert cursors[0].hot_x == 4
    assert cursors[0].hot_y == 8


def test_extract_cursors_parses_native_id(tmp_path: Path) -> None:
    """Obsidian-style blocks: no __XBM_FILE, an X11 cursor-font glyph name
    plus theme colors. native_id must survive into the spec so the
    emitter can explain WHY the shape was skipped."""
    nodes = [_cursor_block("DEFAULT", xbm=None, native_id="XC_LEFT_PTR")]
    cursors = extract_cursors(nodes, tmp_path)
    assert cursors[0].xbm_path is None
    assert cursors[0].native_id == "XC_LEFT_PTR"


def test_extract_cursors_native_id_defaults_to_none(tmp_path: Path) -> None:
    nodes = [_cursor_block("MOVE")]
    cursors = extract_cursors(nodes, tmp_path)
    assert cursors[0].native_id is None


def test_extract_cursors_rejects_path_traversal(tmp_path: Path) -> None:
    """An __XBM_FILE path that escapes asset_root must produce xbm_path=None."""
    nodes = [_cursor_block("EVIL", xbm="../../etc/passwd")]
    cursors = extract_cursors(nodes, tmp_path)
    assert cursors[0].xbm_path is None


def test_extract_cursors_skips_unnamed_blocks(tmp_path: Path) -> None:
    """A __CURSOR block with no __NAME and no head_values is unusable."""
    unnamed = Block(
        keyword="__CURSOR",
        head_values=(),
        children=(_kv("__FG_COLOR", 255, 255, 255),),
        line=1,
    )
    cursors = extract_cursors([unnamed], tmp_path)
    assert cursors == ()


def test_extract_cursors_ignores_non_cursor_blocks(tmp_path: Path) -> None:
    other = Block(
        keyword="__ICLASS",
        head_values=("FOO",),
        children=(),
        line=1,
    )
    cursors = extract_cursors([other, _cursor_block("X")], tmp_path)
    assert len(cursors) == 1
    assert cursors[0].name == "X"


def test_aliens_cursors_parsed_count(tmp_path: Path) -> None:
    """Aliens cursors.cfg has 10 __CURSOR blocks (canonical inventory)."""
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    fixture = Path(__file__).parent / "fixtures" / "Aliens.etheme"
    if not fixture.exists():
        import pytest
        pytest.skip("Aliens.etheme fixture not available")

    with extract(fixture) as raw:
        nodes = parse_tree(raw.asset_root)
        cursors = extract_cursors(nodes, raw.asset_root)
    assert len(cursors) == 10, f"Aliens has 10 cursors; extracted {len(cursors)}"
    names = {c.name for c in cursors}
    # Sanity: the canonical names from cursors.cfg
    assert "DEFAULT" in names
    assert "MOVE" in names


def test_aliens_theme_cursors_populated(tmp_path: Path) -> None:
    """End-to-end: build_theme exposes the parsed cursors on Theme.cursors."""
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    fixture = Path(__file__).parent / "fixtures" / "Aliens.etheme"
    if not fixture.exists():
        import pytest
        pytest.skip("Aliens.etheme fixture not available")

    with extract(fixture) as raw:
        nodes = parse_tree(raw.asset_root)
        theme = build_theme(raw.asset_root, nodes, name="Aliens", scale=2)
        assert len(theme.cursors) == 10
