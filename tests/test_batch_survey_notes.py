"""scripts/batch_survey.py note normalization must not swallow the token
glued to a file path (a macro name, a paren, a quote) — that rendered the
overlay note as "wallpaper: FILE') is a desktop overlay ..." across 46
themes in the 2026-09-01 survey."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "batch_survey.py"


@pytest.fixture(scope="module")
def note_pattern():
    spec = importlib.util.spec_from_file_location("batch_survey", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("batch_survey", mod)
    spec.loader.exec_module(mod)
    return mod.note_pattern


def test_quoted_path_keeps_its_quotes(note_pattern) -> None:
    assert note_pattern("wallpaper: 'artwork/bg.png' (fit): aligned") == (
        "wallpaper: 'FILE' (fit): aligned"
    )


def test_macro_wrapped_path_keeps_macro_and_parens(note_pattern) -> None:
    assert note_pattern("x: ADD_OVERLAY_IMAGE_CENTERED('a/logo.png') overlay") == (
        "x: ICLASS('FILE') overlay"
    )


def test_bare_path_still_normalized(note_pattern) -> None:
    assert note_pattern("wallpaper: artwork/logo.png (__FORGROUND_LAYER) is") == (
        "wallpaper: FILE (__FORGROUND_LAYER) is"
    )
