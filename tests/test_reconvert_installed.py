"""scripts/reconvert_installed.py: slug discovery + archive matching + the
previous-report note-count recovery, plus one real end-to-end run against a
fixture archive inside ``fake_home`` (WP5, "Refresh the locally installed
references"). No installed-package deletion is exercised here — the script
never deletes anything, only lists what it can't match.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "reconvert_installed.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="module")
def mod():
    spec = importlib.util.spec_from_file_location("reconvert_installed", _SCRIPT)
    assert spec is not None and spec.loader is not None
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("reconvert_installed", m)
    spec.loader.exec_module(m)
    return m


# --------------------------------------------------------------------- #
# canonical_package_ids
# --------------------------------------------------------------------- #

def test_canonical_package_ids_collects_plain_dirs(mod, tmp_path) -> None:
    root = tmp_path / "decorations"
    (root / "themey_Aliens").mkdir(parents=True)
    (root / "themey_e13").mkdir(parents=True)
    (root / "not-themey").mkdir(parents=True)
    assert mod.canonical_package_ids(root) == {"themey_Aliens", "themey_e13"}


def test_canonical_package_ids_strips_cursor_and_icon_suffixes(mod, tmp_path) -> None:
    icons_root = tmp_path / "icons"
    icons_root.mkdir()
    (icons_root / "themey_Aliens-cursors").mkdir()
    (icons_root / "themey_Aliens-icons").mkdir()
    # Both namespace dirs fold back to the same canonical conversion id —
    # they are not separate conversions.
    assert mod.canonical_package_ids(icons_root) == {"themey_Aliens"}


def test_canonical_package_ids_unions_multiple_roots(mod, tmp_path) -> None:
    deco = tmp_path / "deco"
    style = tmp_path / "style"
    deco.mkdir()
    style.mkdir()
    (deco / "themey_Aliens").mkdir()
    (style / "themey_e13").mkdir()
    assert mod.canonical_package_ids(deco, style) == {"themey_Aliens", "themey_e13"}


def test_canonical_package_ids_ignores_missing_root(mod, tmp_path) -> None:
    assert mod.canonical_package_ids(tmp_path / "does-not-exist") == set()


def test_canonical_package_ids_ignores_files(mod, tmp_path) -> None:
    root = tmp_path / "decorations"
    root.mkdir()
    (root / "themey_NotADir").write_text("x")
    assert mod.canonical_package_ids(root) == set()


# --------------------------------------------------------------------- #
# match_archives
# --------------------------------------------------------------------- #

def test_match_archives_matches_via_plugin_id(mod, tmp_path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "Aliens.etheme").write_bytes(b"")
    (corpus / "e13.etheme").write_bytes(b"")
    matches, unmatched = mod.match_archives({"themey_Aliens", "themey_Nope"}, corpus)
    assert matches == {"themey_Aliens": corpus / "Aliens.etheme"}
    assert unmatched == {"themey_Nope"}


def test_match_archives_handles_hyphenated_stems(mod, tmp_path) -> None:
    # slug.plugin_id mangles hyphens to underscores in the id.
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "Foo-Bar.etheme").write_bytes(b"")
    matches, unmatched = mod.match_archives({"themey_Foo_Bar"}, corpus)
    assert matches == {"themey_Foo_Bar": corpus / "Foo-Bar.etheme"}
    assert unmatched == set()


def test_match_archives_empty_corpus(mod, tmp_path) -> None:
    corpus = tmp_path / "empty-corpus"
    corpus.mkdir()
    matches, unmatched = mod.match_archives({"themey_Aliens"}, corpus)
    assert matches == {}
    assert unmatched == {"themey_Aliens"}


# --------------------------------------------------------------------- #
# previous_note_count — reconstructing len(theme.notes) from report.txt
# --------------------------------------------------------------------- #

_SAMPLE_REPORT = """# themey conversion report: Sample

## Preserved
- something preserved

## Approximated
- QML backend: boilerplate line, not a note
- plasmastyle: panel background from iclass PANEL art
- wallpaper: 'bg.png' (fit): aligned
- E16's 8-state image model collapsed to Aurorae's 2-state model:
  - KILL normal->active dropped hilited
  - MOVE normal->active dropped hilited
  ... (5 more)
- Pixel-art borders upscaled 2x with NEAREST.

## Skipped
- No additional border types found.
"""


def test_previous_note_count_reconstructs_full_count(mod, fake_home) -> None:
    from themey import paths

    previews = paths.themey_reports()
    previews.mkdir(parents=True, exist_ok=True)
    (previews / "sample.report.txt").write_text(_SAMPLE_REPORT, encoding="utf-8")
    # 2 layout-prefixed notes + 2 shown state notes + 5 "more" = 9
    assert mod.previous_note_count("sample") == 9


def test_previous_note_count_missing_file_is_unknown(mod, fake_home) -> None:
    assert mod.previous_note_count("never-converted") == "?"


def test_previous_note_count_unparseable_file_is_unknown(mod, fake_home) -> None:
    from themey import paths

    previews = paths.themey_reports()
    previews.mkdir(parents=True, exist_ok=True)
    (previews / "garbled.report.txt").write_text("not a real report", encoding="utf-8")
    assert mod.previous_note_count("garbled") == "?"


# --------------------------------------------------------------------- #
# End-to-end: dry-run and a real conversion against a fixture archive,
# entirely inside fake_home.
# --------------------------------------------------------------------- #

def test_main_dry_run_lists_matches_without_converting(mod, fake_home, capsys) -> None:
    from themey import paths
    from themey.pipeline import convert

    convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")
    installed_before = sorted(p.name for p in paths.kwin_decorations().iterdir())

    rc = mod.main(["--corpus", str(FIXTURES), "--dry-run"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "themey_tiny" in out
    # Nothing was reinstalled by the dry run.
    assert sorted(p.name for p in paths.kwin_decorations().iterdir()) == installed_before


def test_main_only_converts_named_package(mod, fake_home, capsys) -> None:
    from themey.pipeline import convert

    convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")

    rc = mod.main(["--corpus", str(FIXTURES), "--only", "themey_tiny"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "themey_tiny" in out
    assert "ok" in out


def test_main_no_installed_packages_is_a_friendly_noop(mod, fake_home, capsys) -> None:
    rc = mod.main(["--corpus", str(FIXTURES)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "no themey_* packages" in out


def test_main_only_rejects_unknown_package(mod, fake_home, capsys) -> None:
    from themey.pipeline import convert

    convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")

    rc = mod.main(["--corpus", str(FIXTURES), "--only", "themey_nope"])

    assert rc == 2
    err = capsys.readouterr().err
    assert "themey_nope" in err


def test_main_lists_unmatched_without_deleting(mod, fake_home, tmp_path, capsys) -> None:
    from themey import paths
    from themey.pipeline import convert

    convert(FIXTURES / "tiny.etheme", scale=2, backend="qml")
    empty_corpus = tmp_path / "no-archives-here"
    empty_corpus.mkdir()

    rc = mod.main(["--corpus", str(empty_corpus), "--dry-run"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "themey_tiny" in out
    assert "0 matched" in out
    # A package with no matching archive is only reported, never removed.
    assert (paths.kwin_decorations() / "themey_tiny").is_dir()
