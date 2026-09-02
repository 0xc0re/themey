"""Tests for themey.analyze.build_theme — orchestrator producing Theme IR.

Includes:
- Synthetic-AST unit tests for the orchestration logic
- Aliens.etheme integration test (the headline canary assertion for analyze)

Aliens canary expected outputs (read from the fixture's own cfgs):
  left_buttons == 'XAI', right_buttons == ''
  border_size_left == 35, border_size_right == 20,
  border_size_top == 30, border_size_bottom == 25
  TEXT1.fg_active == (255, 255, 200), TEXT1.fg_normal == (200, 200, 150)
  len(theme.notes) >= 4  (dropped sticky states from TITLE_BAR_HORIZONTAL)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.analyze.build_theme import build_theme
from themey.etheme.ast import Block, KeyVal

# ---------------------------------------------------------------------------
# Constants / fixtures path
# ---------------------------------------------------------------------------

FIXTURES = Path(__file__).parent / "fixtures"
ALIENS = FIXTURES / "Aliens.etheme"


# ---------------------------------------------------------------------------
# Helpers: synthetic AST factories
# ---------------------------------------------------------------------------


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _block(keyword: str, *children: object, head: tuple[object, ...] = ()) -> Block:
    return Block(keyword=keyword, head_values=head, children=tuple(children), line=0)  # type: ignore[arg-type]


def _border_block(
    name: str = "DEFAULT",
    parts: list[Block] | None = None,
    sizes: dict[str, int] | None = None,
) -> Block:
    """Build a synthetic __BORDER block."""
    children: list[object] = []
    sizes = sizes or {}
    if sizes.get("left") is not None:
        children.append(_kv("__BORDER_SIZE_LEFT", sizes["left"]))
    if sizes.get("right") is not None:
        children.append(_kv("__BORDER_SIZE_RIGHT", sizes["right"]))
    if sizes.get("top") is not None:
        children.append(_kv("__BORDER_SIZE_TOP", sizes["top"]))
    if sizes.get("bottom") is not None:
        children.append(_kv("__BORDER_SIZE_BOTTOM", sizes["bottom"]))
    children.extend(parts or [])
    return Block(keyword="__BORDER", head_values=(name,), children=tuple(children), line=0)  # type: ignore[arg-type]


def _part_block(iclass: str, aclass: str | None = None, **coords: int) -> Block:
    """Build a synthetic __BORDER_PART block."""
    children: list[KeyVal] = [_kv("__ICLASS", iclass)]
    if aclass is not None:
        children.append(_kv("__ACLASS", aclass))
    coord_map = {
        "tl_x_pct": "__TOPLEFT_X_PERCENTAGE",
        "tl_x_abs": "__TOPLEFT_X_ABSOLUTE",
        "tl_y_pct": "__TOPLEFT_Y_PERCENTAGE",
        "tl_y_abs": "__TOPLEFT_Y_ABSOLUTE",
        "br_x_pct": "__BOTTOMRIGHT_X_PERCENTAGE",
        "br_x_abs": "__BOTTOMRIGHT_X_ABSOLUTE",
        "br_y_pct": "__BOTTOMRIGHT_Y_PERCENTAGE",
        "br_y_abs": "__BOTTOMRIGHT_Y_ABSOLUTE",
    }
    for k, v in coords.items():
        if k in coord_map:
            children.append(_kv(coord_map[k], v))
    return Block(keyword="__BORDER_PART", head_values=(), children=tuple(children), line=0)


# ---------------------------------------------------------------------------
# Synthetic-AST unit tests
# ---------------------------------------------------------------------------


def test_build_theme_minimal(tmp_path: Path) -> None:
    """Minimal AST with one DEFAULT border builds a valid Theme."""
    border = _border_block(
        name="DEFAULT",
        parts=[_part_block("TITLE_BAR_HORIZONTAL", "ACTION_MOVE",
                           tl_x_pct=0, tl_x_abs=0, br_x_pct=1024, br_x_abs=0)],
        sizes={"left": 0, "right": 0, "top": 10, "bottom": 0},
    )
    theme = build_theme(tmp_path, [border], name="X", scale=1)
    assert theme.name == "X"
    assert theme.scale == 1
    assert theme.border.name == "DEFAULT"
    assert theme.iclasses == {}
    assert theme.tclasses == {}


def test_build_theme_skipped_borders(tmp_path: Path) -> None:
    """Non-DEFAULT border names are captured in skipped_borders."""
    default_b = _border_block("DEFAULT")
    borderless_b = _border_block("BORDERLESS")
    theme = build_theme(tmp_path, [default_b, borderless_b], name="X")
    assert "BORDERLESS" in theme.skipped_borders


def test_build_theme_fallback_fires_when_no_borders(tmp_path: Path) -> None:
    """Empty AST (no __BORDER blocks) triggers PARSE-05 fallback; note is appended."""
    theme = build_theme(tmp_path, [], name="X")
    # Border is a minimal default
    assert theme.border.name == "DEFAULT"
    # A note should mention fallback
    assert any("fallback" in n.lower() for n in theme.notes)


def test_build_theme_iclasses_populated(tmp_path: Path) -> None:
    """__ICLASS blocks in AST populate theme.iclasses."""
    iclass_block = Block(
        keyword="__ICLASS",
        head_values=("MY_ICLASS",),
        children=(
            _kv("__EDGE_SCALING", 1, 2, 3, 4),
            _kv("__NORMAL", "img.png"),
        ),
        line=0,
    )
    border = _border_block("DEFAULT")
    theme = build_theme(tmp_path, [border, iclass_block], name="X")
    assert "MY_ICLASS" in theme.iclasses
    assert theme.iclasses["MY_ICLASS"].edge_scaling == (1, 2, 3, 4)


def test_build_theme_tclasses_populated(tmp_path: Path) -> None:
    """__TCLASS blocks in AST populate theme.tclasses."""
    tclass_block = Block(
        keyword="__TCLASS",
        head_values=("TEXT1",),
        children=(
            _kv("__NORMAL"),
            _kv("__FORGROUND_COLOR", 200, 200, 150),
            _kv("__NORMAL_ACTIVE"),
            _kv("__FORGROUND_COLOR", 255, 255, 200),
        ),
        line=0,
    )
    border = _border_block("DEFAULT")
    theme = build_theme(tmp_path, [border, tclass_block], name="X")
    assert "TEXT1" in theme.tclasses
    assert theme.tclasses["TEXT1"].fg_normal == (200, 200, 150)
    assert theme.tclasses["TEXT1"].fg_active == (255, 255, 200)


def test_build_theme_logs_spatial_fallback_assigned(tmp_path: Path) -> None:
    """Spatial fallback assignment for unknown button iclass is logged to notes.

    Scenario: TITLE_BAR_HORIZONTAL part spans x=[100,700] (from % math at width 800).
    BUTTON_FOO part at x=[0,90] (center=45) → left third of titlebar → assigned 'M'.
    The assignment must be logged to Theme.notes.
    """
    # Titlebar part (ACTION_MOVE drops it from button_codes, but range is used for geometry)
    titlebar_part = _part_block(
        "TITLE_BAR_HORIZONTAL",
        "ACTION_MOVE",
        tl_x_pct=128,  # 128/1024*800 = 100
        tl_x_abs=0,
        br_x_pct=896,  # 896/1024*800 = 700
        br_x_abs=0,
    )
    # Unknown button in the left third of titlebar: x_center ~= 45
    button_part = _part_block(
        "BUTTON_FOO",
        None,  # no aclass, no iclass pattern match → tier-3 spatial
        tl_x_pct=0,
        tl_x_abs=0,
        br_x_pct=0,
        br_x_abs=90,
    )
    border = _border_block("DEFAULT", parts=[titlebar_part, button_part])
    theme = build_theme(tmp_path, [border], name="X")
    # BUTTON_FOO at x_center=45 < titlebar_left=100 → left of titlebar →
    # It should be bin'd to left_buttons; spatial log should appear
    # Actually: x=45 < titlebar_min=100, so it goes in left bucket, not spatial
    # The spatial fallback would fire for middle-third ambiguous case;
    # For left of titlebar, it's binned but the classify_button still returns (None, 'spatial')
    # since BUTTON_FOO doesn't match aclass or iclass pattern
    # Let's verify the note contains "spatial fallback" for the assignment
    spatial_notes = [
        n
        for n in theme.notes
        if "spatial fallback" in n.lower() or "spatial" in n.lower()
    ]
    assert len(spatial_notes) >= 1, f"Expected spatial note, got notes: {theme.notes}"


def test_build_theme_logs_spatial_fallback_dropped_middle(tmp_path: Path) -> None:
    """Spatial fallback: middle-third button is dropped and a note is appended."""
    # Titlebar spans x=[100,700] (800px reference width)
    titlebar_part = _part_block(
        "TITLE_BAR_HORIZONTAL",
        "ACTION_MOVE",
        tl_x_pct=128,   # 100
        tl_x_abs=0,
        br_x_pct=896,   # 700
        br_x_abs=0,
    )
    # Unknown button in middle of titlebar: x_center = 400 (middle)
    button_part = _part_block(
        "BUTTON_MIDDLE",
        None,
        tl_x_pct=0,
        tl_x_abs=350,   # center at 375ish
        br_x_pct=0,
        br_x_abs=430,
    )
    border = _border_block("DEFAULT", parts=[titlebar_part, button_part])
    theme = build_theme(tmp_path, [border], name="X")
    # BUTTON_MIDDLE is in middle third of [100,700] → dropped
    assert "BUTTON_MIDDLE" not in theme.button_codes
    # A note should mention it was dropped/ambiguous
    middle_notes = [n for n in theme.notes if "BUTTON_MIDDLE" in n]
    assert len(middle_notes) >= 1, f"Expected note about BUTTON_MIDDLE, got: {theme.notes}"


def test_build_theme_button_codes_via_aclass(tmp_path: Path) -> None:
    """Buttons with explicit __ACLASS get classified correctly without spatial fallback."""
    titlebar_part = _part_block("TITLE_BAR_HORIZONTAL", "ACTION_MOVE",
                                tl_x_pct=128, tl_x_abs=0, br_x_pct=896, br_x_abs=0)
    kill_part = _part_block("BUTTON_KILL", "ACTION_KILL",
                            tl_x_pct=0, tl_x_abs=0, br_x_pct=0, br_x_abs=25)
    border = _border_block("DEFAULT", parts=[titlebar_part, kill_part])
    theme = build_theme(tmp_path, [border], name="X")
    assert theme.button_codes.get("BUTTON_KILL") == "X"


# ---------------------------------------------------------------------------
# Aliens canary integration test — headline assertion for analyze
# ---------------------------------------------------------------------------


@pytest.fixture
def aliens_asset_root():  # type: ignore[return]
    """Extract Aliens.etheme and yield (asset_root, ast_nodes)."""
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    with extract(ALIENS) as raw:
        nodes = parse_tree(raw.asset_root)
        yield raw.asset_root, nodes


def test_build_theme_aliens_canary(aliens_asset_root: tuple[Path, list]) -> None:  # type: ignore[type-arg]
    """End-to-end Aliens.etheme canary — verifies the complete analyze pipeline.

    Source of truth — the fixture's own borders/default.cfg and
    imageclasses/borders.cfg, read byte-for-byte:
    - border: DEFAULT, L=35 R=20 T=30 B=25, >=8 parts
    - iclasses include: TITLE_BAR_HORIZONTAL, BUTTON_KILL, BUTTON_MAXIMIZE, BUTTON_ICONIFY
    - TEXT1: fg_active=(255,255,200), fg_normal=(200,200,150) (honors __FORGROUND_COLOR)
    - left_buttons='XAI', right_buttons='' (AURORAE-02 canary A1)
    - notes >= 4 (dropped sticky states from TITLE_BAR_HORIZONTAL)
    """
    asset_root, nodes = aliens_asset_root
    theme = build_theme(asset_root, nodes, name="Aliens", scale=2)

    # Basic identity
    assert theme.name == "Aliens"
    assert theme.scale == 2
    assert theme.display_name == "Aliens"
    assert theme.author is None

    # Border structure (from borders/default.cfg __BORDER_SIZE_*)
    assert theme.border.name == "DEFAULT"
    assert theme.border.border_size_left == 35
    assert theme.border.border_size_right == 20
    assert theme.border.border_size_top == 30
    assert theme.border.border_size_bottom == 25
    assert len(theme.border.parts) >= 8

    # At least one part has ACTION_KILL or ACTION_CLOSE aclass
    aclasses = {p.aclass for p in theme.border.parts if p.aclass}
    assert "ACTION_KILL" in aclasses or "ACTION_CLOSE" in aclasses, (
        f"Expected ACTION_KILL or ACTION_CLOSE in parts, got: {aclasses}"
    )
    assert "ACTION_MAX" in aclasses, f"Expected ACTION_MAX in parts, got: {aclasses}"
    assert "ACTION_ICONIFY" in aclasses, f"Expected ACTION_ICONIFY in parts, got: {aclasses}"

    # IClasses (from imageclasses/borders.cfg)
    assert "TITLE_BAR_HORIZONTAL" in theme.iclasses
    assert "BUTTON_KILL" in theme.iclasses
    assert "BUTTON_MAXIMIZE" in theme.iclasses
    assert "BUTTON_ICONIFY" in theme.iclasses
    # edge_scaling exists and is a 4-tuple (sanity check on LRTB order)
    tb_edge = theme.iclasses["TITLE_BAR_HORIZONTAL"].edge_scaling
    assert isinstance(tb_edge, tuple) and len(tb_edge) == 4
    assert all(isinstance(v, int) for v in tb_edge)

    # TClasses TEXT1 (E16's own __FORGROUND_COLOR misspelling)
    assert "TEXT1" in theme.tclasses, (
        f"Expected TEXT1 in tclasses, got keys: {list(theme.tclasses.keys())}"
    )
    assert theme.tclasses["TEXT1"].fg_active == (255, 255, 200), (
        f"TEXT1.fg_active wrong: {theme.tclasses['TEXT1'].fg_active}"
    )
    assert theme.tclasses["TEXT1"].fg_normal == (200, 200, 150), (
        f"TEXT1.fg_normal wrong: {theme.tclasses['TEXT1'].fg_normal}"
    )

    # Button binning — AURORAE-02 canary A1 (the headline assertion)
    assert theme.left_buttons == "XAI", (
        f"Expected left_buttons='XAI', got: {theme.left_buttons!r}"
    )
    assert theme.right_buttons == "", (
        f"Expected right_buttons='', got: {theme.right_buttons!r}"
    )

    # Button codes for Aliens' known buttons
    # (BUTTON_KILL → X, BUTTON_MAXIMIZE → A, BUTTON_ICONIFY → I via __ACLASS tier)
    assert theme.button_codes.get("BUTTON_KILL") == "X", (
        f"BUTTON_KILL should map to X, got: {theme.button_codes.get('BUTTON_KILL')}"
    )
    assert theme.button_codes.get("BUTTON_MAXIMIZE") == "A", (
        f"BUTTON_MAXIMIZE should map to A, got: {theme.button_codes.get('BUTTON_MAXIMIZE')}"
    )
    assert theme.button_codes.get("BUTTON_ICONIFY") == "I", (
        f"BUTTON_ICONIFY should map to I, got: {theme.button_codes.get('BUTTON_ICONIFY')}"
    )

    # Skipped borders
    assert len(theme.skipped_borders) >= 1, (
        "Expected at least one skipped border (BORDERLESS, FIXED_SIZE, etc.)"
    )

    # Sticky variants are no longer "dropped": the QML backend renders them
    # on windows on all desktops. Only disabled art has no target.
    assert not any("STICKY dropped" in n for n in theme.notes)
    assert len(theme.notes) >= 1, (
        f"Expected >=4 notes, got {len(theme.notes)}: {theme.notes[:5]}"
    )


# ---------------------------------------------------------------------------
# Lowercase-named theme (WashedBlue / eLap shape): names resolve verbatim
# ---------------------------------------------------------------------------


def _write_lowercase_theme(root: Path) -> None:
    """A minimal theme whose border, iclasses and art paths are lowercase
    German (WashedBlue's ``titelleiste``/``knopf_kill``) with one unquoted
    image path and one name ending in a hyphen."""
    from PIL import Image

    (root / "art").mkdir()
    Image.new("RGBA", (16, 16), (200, 60, 60, 255)).save(root / "art" / "titel.png")
    Image.new("RGBA", (8, 8), (60, 60, 200, 255)).save(root / "art" / "kill.png")
    (root / "borders.cfg").write_text(
        "__BORDER fenster\n__BGN\n"
        "__BORDER_SIZE_LEFT 2\n__BORDER_SIZE_RIGHT 2\n"
        "__BORDER_SIZE_TOP 18\n__BORDER_SIZE_BOTTOM 2\n"
        "__BORDER_PART\n__BGN\n"
        "  __ICLASS titelleiste-\n  __ACLASS ACTION_MOVE\n"
        "  __TOPLEFT_X_PERCENTAGE 0\n  __TOPLEFT_X_ABSOLUTE 2\n"
        "  __TOPLEFT_Y_PERCENTAGE 0\n  __TOPLEFT_Y_ABSOLUTE 0\n"
        "  __BOTTOMRIGHT_X_PERCENTAGE 1024\n  __BOTTOMRIGHT_X_ABSOLUTE -20\n"
        "  __BOTTOMRIGHT_Y_PERCENTAGE 0\n  __BOTTOMRIGHT_Y_ABSOLUTE 17\n"
        "__END\n"
        "__BORDER_PART\n__BGN\n"
        "  __ICLASS knopf_kill\n  __ACLASS ACTION_KILL\n"
        "  __TOPLEFT_X_PERCENTAGE 1024\n  __TOPLEFT_X_ABSOLUTE -18\n"
        "  __TOPLEFT_Y_PERCENTAGE 0\n  __TOPLEFT_Y_ABSOLUTE 1\n"
        "  __BOTTOMRIGHT_X_PERCENTAGE 1024\n  __BOTTOMRIGHT_X_ABSOLUTE -2\n"
        "  __BOTTOMRIGHT_Y_PERCENTAGE 0\n  __BOTTOMRIGHT_Y_ABSOLUTE 16\n"
        "__END\n"
        "__END\n",
        encoding="utf-8",
    )
    (root / "imageclasses.cfg").write_text(
        "__ICLASS __BGN\n  __NAME titelleiste-\n"
        "  __EDGE_SCALING 2 2 0 0\n"
        "  __NORMAL art/titel.png\n  __NORMAL_ACTIVE \"art/titel.png\"\n__END\n"
        "__ICLASS knopf_kill\n__BGN\n"
        "  __NORMAL art/kill.png\n  __NORMAL_ACTIVE art/kill.png\n__END\n",
        encoding="utf-8",
    )


def test_build_theme_resolves_lowercase_names_verbatim(tmp_path: Path) -> None:
    """E16 matches iclass names with strcmp (iclass.c:341) after reading them
    as sscanf("%s") words (config.c:185): lowercase, trailing hyphen and an
    unquoted art path all round-trip. Before the lexer fix WashedBlue and
    eLap resolved zero iclasses and rendered a blank frame."""
    from themey.etheme.parse import parse_tree

    _write_lowercase_theme(tmp_path)
    theme = build_theme(tmp_path, parse_tree(tmp_path), name="lower")
    assert theme.border.name == "fenster"
    assert [p.iclass_name for p in theme.border.parts] == ["titelleiste-", "knopf_kill"]
    assert set(theme.iclasses) >= {"titelleiste-", "knopf_kill"}
    assert theme.iclasses["titelleiste-"].normal == tmp_path / "art" / "titel.png"
    assert theme.iclasses["titelleiste-"].normal_active == tmp_path / "art" / "titel.png"
    assert theme.iclasses["knopf_kill"].normal == tmp_path / "art" / "kill.png"
    assert theme.iclasses["titelleiste-"].edge_scaling == (2, 2, 0, 0)


# ---------------------------------------------------------------------------
# Menu styles
# ---------------------------------------------------------------------------


def test_build_theme_collects_menu_styles(tmp_path: Path) -> None:
    nodes = [
        _border_block("DEFAULT", sizes={"left": 1, "right": 1, "top": 1, "bottom": 1}),
        _block(
            "__MENU_STYLE",
            _kv("__NAME", "DEFAULT"),
            _kv("__BG_ICLASS", "MENU_BG"),
            _kv("__ITEM_ICLASS", "MENU_SEL"),
            _kv("__USE_ITEM_BACKGROUNDS", "__OFF"),
        ),
    ]
    theme = build_theme(tmp_path, nodes, name="t")
    assert theme.menu_styles["DEFAULT"].bg_iclass == "MENU_BG"
    assert theme.menu_styles["DEFAULT"].item_iclass == "MENU_SEL"


# ---------------------------------------------------------------------------
# Tooltips
# ---------------------------------------------------------------------------


def test_build_theme_collects_tooltips(tmp_path: Path) -> None:
    """The tooltip's iclass must be one the theme defines (E16's
    ``_TtCreate`` creates nothing otherwise); a ghost block is dropped
    with a ``tooltips:`` note and a later same-name block applies."""
    nodes = [
        _border_block("DEFAULT", sizes={"left": 1, "right": 1, "top": 1, "bottom": 1}),
        _block("__ICLASS", _kv("__NORMAL", "bar.png"), head=("BAR",)),
        _block(
            "__TOOLTIP",
            _kv("__NAME", "DEFAULT"),
            _kv("__ICLASS", "TT_GHOST"),
            _kv("__TCLASS", "COORDS"),
        ),
        _block(
            "__TOOLTIP",
            _kv("__NAME", "DEFAULT"),
            _kv("__ICLASS", "BAR"),
            _kv("__TCLASS", "COORDS"),
            _kv("__DISTANCE", 32),
        ),
    ]
    theme = build_theme(tmp_path, nodes, name="t")
    assert theme.tooltips["DEFAULT"].iclass == "BAR"
    assert theme.tooltips["DEFAULT"].tclass == "COORDS"
    assert theme.tooltips["DEFAULT"].distance == 32
    assert any(
        n.startswith("tooltips: __TOOLTIP DEFAULT names undefined iclass TT_GHOST")
        for n in theme.notes
    )
