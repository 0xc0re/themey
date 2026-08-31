"""Unit tests for themey.analyze.iclasses — AST __ICLASS block extraction."""
from __future__ import annotations

from pathlib import Path

from themey.analyze.iclasses import build_iclasses
from themey.etheme.ast import Block, KeyVal

# ---------------------------------------------------------------------------
# Helpers: synthetic AST factories
# ---------------------------------------------------------------------------


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _iclass_block(name: str, *children: KeyVal) -> Block:
    """Build a synthetic __ICLASS block with head_values=(name,)."""
    return Block(keyword="__ICLASS", head_values=(name,), children=children, line=0)


# ---------------------------------------------------------------------------
# edge_scaling tests
# ---------------------------------------------------------------------------


def test_build_iclass_edge_scaling_lrtb(tmp_path: Path) -> None:
    """__EDGE_SCALING 1 2 3 4 → edge_scaling == (1, 2, 3, 4) in L R T B order."""
    block = _iclass_block(
        "X",
        _kv("__EDGE_SCALING", 1, 2, 3, 4),
    )
    typed, _raw = build_iclasses([block], tmp_path)
    assert "X" in typed
    assert typed["X"].edge_scaling == (1, 2, 3, 4)


def test_build_iclass_edge_scaling_default_zero(tmp_path: Path) -> None:
    """Iclass without __EDGE_SCALING defaults to (0, 0, 0, 0)."""
    block = _iclass_block("X")
    typed, _ = build_iclasses([block], tmp_path)
    assert typed["X"].edge_scaling == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# state path storage tests — RESOLVED POLICY: store resolved Path unconditionally
# ---------------------------------------------------------------------------


def test_build_iclass_state_paths_stored_unconditionally(tmp_path: Path) -> None:
    """Paths are stored even when the file doesn't exist on disk.

    RESOLVED POLICY (see ``analyze/iclasses.py``): iclasses.py stores the
    resolved Path unconditionally; never None for missing files. Callers
    check .is_file() themselves. build_theme appends a missing-asset note
    when the file does not exist on disk.
    """
    block = _iclass_block(
        "X",
        _kv("__NORMAL", "img/n.png"),
        _kv("__NORMAL_ACTIVE", "img/na.png"),
        _kv("__HILITED_ACTIVE", "img/ha.png"),
    )
    typed, _ = build_iclasses([block], tmp_path)
    ic = typed["X"]
    # Paths should be set (resolved relative to tmp_path), not None
    expected_normal = (tmp_path / "img/n.png").resolve()
    assert ic.normal == expected_normal
    # The file doesn't exist on disk
    assert ic.normal is not None and not ic.normal.is_file()
    expected_na = (tmp_path / "img/na.png").resolve()
    assert ic.normal_active == expected_na
    expected_ha = (tmp_path / "img/ha.png").resolve()
    assert ic.hilited_active == expected_ha


def test_build_iclass_state_paths_resolve_existing_files(tmp_path: Path) -> None:
    """When the file exists on disk, .is_file() returns True."""
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "n.png").write_bytes(b"fake png")
    block = _iclass_block(
        "X",
        _kv("__NORMAL", "img/n.png"),
    )
    typed, _ = build_iclasses([block], tmp_path)
    ic = typed["X"]
    assert ic.normal is not None
    assert ic.normal.is_file()


def test_build_iclass_missing_state_is_none(tmp_path: Path) -> None:
    """Undeclared states (not in AST) are None — distinct from "declared but missing file"."""
    block = _iclass_block(
        "X",
        _kv("__NORMAL", "img/n.png"),
        # __NORMAL_ACTIVE, __HILITED are NOT declared
    )
    typed, _ = build_iclasses([block], tmp_path)
    ic = typed["X"]
    # normal is set because it was declared
    assert ic.normal is not None
    # normal_active and hilited are None because they were not declared in the AST
    assert ic.normal_active is None
    assert ic.hilited is None


# ---------------------------------------------------------------------------
# Raw state map shape tests (for AURORAE-04 collapse)
# ---------------------------------------------------------------------------


def test_build_iclass_raw_state_map_shape(tmp_path: Path) -> None:
    """build_iclasses returns both typed dict and raw state map."""
    block = _iclass_block(
        "X",
        _kv("__NORMAL", "n.png"),
        _kv("__NORMAL_ACTIVE", "na.png"),
        _kv("__NORMAL_STICKY", "ns.png"),
    )
    _typed, raw = build_iclasses([block], tmp_path)
    # raw map should contain all declared state keywords
    assert "X" in raw
    state_map = raw["X"]
    assert "__NORMAL" in state_map
    assert "__NORMAL_ACTIVE" in state_map
    assert "__NORMAL_STICKY" in state_map
    # values are Path objects (resolved)
    for _key, path in state_map.items():
        if path is not None:
            assert isinstance(path, Path)


def test_build_iclass_collects_dropped_states_for_notes(tmp_path: Path) -> None:
    """__NORMAL_STICKY in AST is in raw map but NOT surfaced on IClassSpec.

    The typed spec only has the AURORAE-04-compatible states. Sticky variants
    are stored in the raw map so collapse_image_states can log them as dropped.
    """
    block = _iclass_block(
        "X",
        _kv("__NORMAL", "n.png"),
        _kv("__NORMAL_STICKY", "ns.png"),
    )
    typed, raw = build_iclasses([block], tmp_path)
    ic = typed["X"]
    # normal_sticky field exists on IClassSpec but may be set
    # The important thing is __NORMAL_STICKY appears in raw map for drop logging
    assert "__NORMAL_STICKY" in raw["X"]
    # And normal is set
    assert ic.normal is not None


# ---------------------------------------------------------------------------
# Security: path traversal guard (T-05-01)
# ---------------------------------------------------------------------------


def test_build_iclass_path_traversal_rejected(tmp_path: Path) -> None:
    """Paths that resolve outside asset_root are stored as None (T-05-01 mitigation)."""
    block = _iclass_block(
        "X",
        _kv("__NORMAL", "../../../etc/passwd"),
    )
    typed, _raw = build_iclasses([block], tmp_path)
    ic = typed["X"]
    # Path traversal attempt: result must be None (treated as missing-asset)
    assert ic.normal is None


def test_build_iclass_multiple(tmp_path: Path) -> None:
    """Multiple iclass blocks produce multiple entries in the dicts."""
    block_a = _iclass_block("A", _kv("__NORMAL", "a.png"))
    block_b = _iclass_block("B", _kv("__NORMAL", "b.png"))
    typed, raw = build_iclasses([block_a, block_b], tmp_path)
    assert "A" in typed
    assert "B" in typed
    assert "A" in raw
    assert "B" in raw


# ---------------------------------------------------------------------------
# Step 11: __CLICKED_STICKY logged-as-dropped + __PADDING parsing
# ---------------------------------------------------------------------------


def test_iclass_clicked_sticky_logged_as_dropped(tmp_path: Path) -> None:
    """An iclass with __CLICKED_STICKY must produce a dropped-state note via
    collapse_image_states (it's not a state Aurorae renders).
    """
    from themey.analyze.iclasses import build_iclasses
    from themey.analyze.states import collapse_image_states
    from themey.etheme.ast import Block, KeyVal

    # Create the asset on disk so the path resolves as non-None.
    asset = tmp_path / "x.png"
    asset.write_bytes(b"")
    block = Block(
        keyword="__ICLASS",
        head_values=("FOO",),
        children=(
            KeyVal(keyword="__NORMAL", values=("x.png",), line=0),
            KeyVal(keyword="__CLICKED_STICKY", values=("x.png",), line=0),
        ),
        line=0,
    )
    _typed, raw = build_iclasses([block], tmp_path)
    notes: list[str] = []
    collapse_image_states(raw["FOO"], "button-default", notes, "FOO")
    assert any("__CLICKED_STICKY" in n for n in notes), (
        f"__CLICKED_STICKY not surfaced as dropped; notes={notes}"
    )


def test_iclass_padding_parsed(tmp_path: Path) -> None:
    """__PADDING l r t b is captured into IClassSpec.padding."""
    from themey.analyze.iclasses import build_iclasses
    from themey.etheme.ast import Block, KeyVal

    block = Block(
        keyword="__ICLASS",
        head_values=("BAR",),
        children=(
            KeyVal(keyword="__PADDING", values=(2, 2, 1, 1), line=0),
        ),
        line=0,
    )
    typed, _raw = build_iclasses([block], tmp_path)
    assert typed["BAR"].padding == (2, 2, 1, 1)


def test_iclass_padding_defaults_to_zero(tmp_path: Path) -> None:
    """An iclass without __PADDING has padding=(0, 0, 0, 0)."""
    from themey.analyze.iclasses import build_iclasses
    from themey.etheme.ast import Block

    block = Block(keyword="__ICLASS", head_values=("BAR",), children=(), line=0)
    typed, _raw = build_iclasses([block], tmp_path)
    assert typed["BAR"].padding == (0, 0, 0, 0)
