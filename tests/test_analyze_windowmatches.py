"""analyze/windowmatches.py — ``__MATCH_WINDOW`` ``__USE_ICON`` rules.

E16's windowmatches.cfg is the only theme hook for per-app icons; the
bundled definitions expand ``USE_ICON_IMAGE_FOR_CLIENT_{CLASS,NAME,TITLE}``
to a block with ``__NAME``/``__USE_ICON``/``__HAS_*``. Rules naming a
non-image (an iclass), a catch-all pattern or no criterion are dropped
with an ``icons:`` note.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from themey.analyze.windowmatches import build_icon_matches
from themey.etheme.archive import extract
from themey.etheme.ast import Block, KeyVal
from themey.etheme.parse import parse_tree

FIXTURES = Path(__file__).parent / "fixtures"


def _kv(keyword: str, *values: object) -> KeyVal:
    return KeyVal(keyword=keyword, values=tuple(values), line=0)


def _match(*children: KeyVal) -> Block:
    return Block(keyword="__MATCH_WINDOW", head_values=(), children=children, line=0)


def _icon(tmp_path: Path, rel: str = "icons/app.png") -> Path:
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (4, 4), (10, 200, 10, 255)).save(p)
    return p


def test_class_name_title_rules(tmp_path: Path) -> None:
    icon = _icon(tmp_path)
    notes: list[str] = []
    specs = build_icon_matches([
        _match(_kv("__NAME", "a_MATCH"), _kv("__USE_ICON", "icons/app.png"),
               _kv("__HAS_CLASS", "XTerm")),
        _match(_kv("__USE_ICON", "icons/app.png"), _kv("__HAS_NAME", "+gmc+")),
        _match(_kv("__USE_ICON", "icons/app.png"), _kv("__HAS_TITLE", "*Midnight*")),
    ], asset_root=tmp_path, notes=notes)
    assert [(s.kind, s.pattern) for s in specs] == [
        ("class", "XTerm"), ("name", "+gmc+"), ("title", "*Midnight*"),
    ]
    assert all(s.image == icon.resolve() for s in specs)
    assert notes == []


def test_border_only_blocks_ignored(tmp_path: Path) -> None:
    notes: list[str] = []
    specs = build_icon_matches([
        _match(_kv("__NAME", "B_MATCH"), _kv("__USE_BORDER", "BORDERLESS"),
               _kv("__HAS_CLASS", "XClock")),
    ], asset_root=tmp_path, notes=notes)
    assert specs == () and notes == []


def test_iclass_or_missing_image_dropped_with_note(tmp_path: Path) -> None:
    notes: list[str] = []
    specs = build_icon_matches([
        # Egradient: __USE_ICON names an iclass, not a file.
        _match(_kv("__NAME", "X11AMP"), _kv("__HAS_TITLE", "X11Amp*"),
               _kv("__USE_ICON", "DESKTOP_EXEC_X11AMP")),
        _match(_kv("__USE_ICON", "icons/nope.png"), _kv("__HAS_CLASS", "X")),
        _match(_kv("__USE_ICON", "../../etc/passwd"), _kv("__HAS_CLASS", "X")),
    ], asset_root=tmp_path, notes=notes)
    assert specs == ()
    assert len(notes) == 3 and all(n.startswith("icons: ") and "dropped" in n for n in notes)
    assert "X11AMP" in notes[0] and "DESKTOP_EXEC_X11AMP" in notes[0]


def test_catch_all_pattern_dropped(tmp_path: Path) -> None:
    _icon(tmp_path)
    notes: list[str] = []
    specs = build_icon_matches([
        # Hazard: __HAS_TITLE * would re-icon everything.
        _match(_kv("__USE_ICON", "icons/app.png"), _kv("__HAS_TITLE", "*")),
        _match(_kv("__USE_ICON", "icons/app.png"), _kv("__HAS_CLASS", "")),
        _match(_kv("__USE_ICON", "icons/app.png"), _kv("__HAS_CLASS", "Emacs")),
    ], asset_root=tmp_path, notes=notes)
    assert [s.pattern for s in specs] == ["Emacs"]
    assert sum("catch-all" in n for n in notes) == 2


def test_no_criterion_dropped_and_multi_criterion_prefers_class(tmp_path: Path) -> None:
    _icon(tmp_path)
    notes: list[str] = []
    specs = build_icon_matches([
        _match(_kv("__USE_ICON", "icons/app.png")),
        _match(_kv("__USE_ICON", "icons/app.png"), _kv("__HAS_TITLE", "T*"),
               _kv("__HAS_CLASS", "C"), _kv("__HAS_NAME", "n")),
    ], asset_root=tmp_path, notes=notes)
    assert [(s.kind, s.pattern) for s in specs] == [("class", "C")]
    assert any("no __HAS_CLASS" in n for n in notes)
    assert any("combines 3 criteria" in n for n in notes)


def test_tiny_fixture_macro_expands_through_bundled_definitions() -> None:
    """``USE_ICON_IMAGE_FOR_CLIENT_CLASS(...)`` in windowmatches.cfg expands
    via ``#include <definitions>`` into a real ``__MATCH_WINDOW`` block."""
    with extract(FIXTURES / "tiny.etheme") as raw:
        nodes = parse_tree(raw.asset_root)
        blocks = [n for n in nodes if isinstance(n, Block) and n.keyword == "__MATCH_WINDOW"]
        assert len(blocks) == 2
        notes: list[str] = []
        specs = build_icon_matches(blocks, asset_root=raw.asset_root, notes=notes)
        assert len(specs) == 1
        assert specs[0].kind == "class" and specs[0].pattern == "TinyApp"
        assert specs[0].image.name == "tiny_app.png" and specs[0].image.is_file()
        assert notes == []
