"""Phase-1 font/tclass capture for the QML decoration backend.

Covers analyze/fonts.py (tolerant __FONTS scan — the main lexer cannot
tokenize lowercase aliases) and the raw justification / font-token capture
added to analyze/tclasses.py. e13 ground truth: TEXT1 uses *font-default →
ariali/9 (a real TTF under ttfonts/), justification 25 then 0 (E16 last-wins
→ 0, flush left).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.analyze.fonts import parse_fonts
from themey.etheme.archive import extract
from themey.etheme.parse import parse_tree

E13_PATH = Path(__file__).parent / "fixtures" / "e13.etheme"

needs_e13 = pytest.mark.skipif(
    not E13_PATH.exists(), reason="e13.etheme not available on this machine"
)


@pytest.fixture(scope="module")
def e13_root():
    with extract(E13_PATH) as raw:
        yield raw.asset_root


@needs_e13
def test_e13_font_default_resolves_ttf(e13_root):
    fonts = parse_fonts(e13_root)
    spec = fonts["font-default"]
    assert spec.size == 9
    assert spec.ttf_path is not None and spec.ttf_path.is_file()
    assert spec.ttf_path.name == "ariali.ttf"
    # Pillow reads the real family name from the face; ariali is Arial Italic.
    assert spec.family == "Arial"


@needs_e13
def test_e13_xlfd_entry_has_no_ttf(e13_root):
    fonts = parse_fonts(e13_root)
    spec = fonts["font-coords"]
    assert spec.ttf_path is None
    assert spec.family == "lucida"
    # "-*-lucida-bold-r-normal-*-*-100-*-*-p-*-iso8859-1": pixel field is a
    # wildcard, point field 100 → size 10.
    assert spec.size == 10


def test_parse_fonts_missing_files(tmp_path):
    assert parse_fonts(tmp_path) == {}


def test_parse_fonts_rejects_path_escape(tmp_path):
    (tmp_path / "fonts.theme.cfg").write_text(
        '__FONTS __BGN\n  font-evil "../../etc/passwd/9"\n__END\n'
    )
    spec = parse_fonts(tmp_path)["font-evil"]
    assert spec.ttf_path is None  # T-05-01: escapes asset_root → dropped


@needs_e13
def test_e13_text1_captures_raw_justification_and_font(e13_root):
    from themey.analyze.build_theme import build_theme

    theme = build_theme(
        e13_root, parse_tree(e13_root), name="e13", display_name="e13", scale=2
    )
    text1 = theme.tclasses["TEXT1"]
    # E16 keeps ONE justification per tclass, last declaration wins:
    # TEXT1 declares 25 (normal) then 0 (active) → 0.
    assert text1.justification_q10 == 0
    assert text1.font_normal == "*font-default"
    assert text1.font_active == "*font-default"
    assert text1.font_alias == "font-default"
    # Theme.fonts is wired and the alias is resolvable end to end.
    assert theme.fonts["font-default"].ttf_path is not None


def test_theme_fonts_defaulted():
    """Hand-built Themes in older tests never pass fonts= — must still work."""
    import inspect

    from themey.ir import Theme

    assert inspect.signature(Theme).parameters["fonts"].default is not inspect.Parameter.empty
