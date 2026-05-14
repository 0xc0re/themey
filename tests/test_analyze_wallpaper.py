"""Tests for desktops.cfg wallpaper-path extraction."""
from __future__ import annotations

from pathlib import Path

from themey.analyze.wallpaper import extract_wallpapers


def _write_cfg(asset_root: Path, text: str) -> None:
    (asset_root / "desktops.cfg").write_text(text, encoding="utf-8")


def _touch(asset_root: Path, *rel_parts: str) -> Path:
    p = asset_root.joinpath(*rel_parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")
    return p


def test_extract_wallpapers_finds_add_background_scaled(tmp_path: Path) -> None:
    p = _touch(tmp_path, "artwork", "backgrounds", "a.jpg")
    _write_cfg(
        tmp_path,
        """
        BEGIN_BACKGROUND("Foo")
          ADD_BACKGROUND_SCALED("artwork/backgrounds/a.jpg")
        END_BACKGROUND
        """,
    )
    wps = extract_wallpapers(tmp_path)
    assert wps == (p,)


def test_extract_wallpapers_finds_bg_file(tmp_path: Path) -> None:
    p = _touch(tmp_path, "wp.png")
    _write_cfg(tmp_path, 'BG_FILE("wp.png")\n')
    wps = extract_wallpapers(tmp_path)
    assert wps == (p,)


def test_extract_wallpapers_deduplicates(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.jpg")
    _write_cfg(
        tmp_path,
        'ADD_BACKGROUND_SCALED("bg.jpg")\n'
        'ADD_BACKGROUND_SCALED("bg.jpg")\n'
        'ADD_BACKGROUND_SCALED("bg.jpg")\n',
    )
    wps = extract_wallpapers(tmp_path)
    assert len(wps) == 1
    assert wps[0] == p


def test_extract_wallpapers_skips_missing_files(tmp_path: Path) -> None:
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("not-on-disk.jpg")\n')
    wps = extract_wallpapers(tmp_path)
    assert wps == ()


def test_extract_wallpapers_rejects_path_traversal(tmp_path: Path) -> None:
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("../../etc/hostname")\n')
    wps = extract_wallpapers(tmp_path)
    assert wps == ()


def test_extract_wallpapers_returns_empty_when_cfg_missing(tmp_path: Path) -> None:
    wps = extract_wallpapers(tmp_path)
    assert wps == ()


def test_aliens_wallpapers_found_count(tmp_path: Path) -> None:
    """Aliens' desktops.cfg references at least one wallpaper image."""
    from themey.etheme.archive import extract

    fixture = Path(__file__).parent / "fixtures" / "Aliens.etheme"
    if not fixture.exists():
        import pytest
        pytest.skip("Aliens.etheme fixture not available")
    with extract(fixture) as raw:
        wps = extract_wallpapers(raw.asset_root)
    assert len(wps) >= 1, (
        f"Aliens ships multiple wallpapers; extract found {len(wps)}"
    )
