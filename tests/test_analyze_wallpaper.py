"""Tests for desktops.cfg wallpaper-path extraction."""
from __future__ import annotations

from pathlib import Path

from themey.analyze.wallpaper import extract_wallpaper_specs, extract_wallpapers
from themey.ir import WallpaperSpec


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


# --------------------------------------------------------------------- #
# extract_wallpaper_specs — fill-mode capture (B1)
# --------------------------------------------------------------------- #


def test_extract_wallpaper_specs_tiled_fill_mode(tmp_path: Path) -> None:
    p = _touch(tmp_path, "tile.png")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_TILED("tile.png")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="tiled"),)


def test_extract_wallpaper_specs_tiled_variant_fill_mode(tmp_path: Path) -> None:
    """ADD_BACKGROUND_TILED_SCALED_VERTICALLY etc. still count as tiled."""
    p = _touch(tmp_path, "tile.jpeg")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_TILED_SCALED_VERTICALLY("tile.jpeg")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="tiled"),)


def test_extract_wallpaper_specs_scaled_fill_mode(tmp_path: Path) -> None:
    p = _touch(tmp_path, "a.jpg")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("a.jpg")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="scaled"),)


def test_extract_wallpaper_specs_bg_file_fill_mode(tmp_path: Path) -> None:
    p = _touch(tmp_path, "wp.png")
    _write_cfg(tmp_path, 'BG_FILE("wp.png")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="scaled"),)


def test_extract_wallpaper_specs_traversal_rejected(tmp_path: Path) -> None:
    _write_cfg(tmp_path, 'ADD_BACKGROUND_TILED("../../etc/hostname")\n')
    assert extract_wallpaper_specs(tmp_path) == ()


def test_extract_wallpapers_wrapper_matches_specs(tmp_path: Path) -> None:
    p = _touch(tmp_path, "a.jpg")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("a.jpg")\n')
    assert extract_wallpapers(tmp_path) == (p,)


# --------------------------------------------------------------------- #
# Fixture ground truth (2026-08-30, verified against tests/fixtures/*.etheme)
# --------------------------------------------------------------------- #


def _extract_fixture(name: str) -> tuple[WallpaperSpec, ...]:
    from themey.etheme.archive import extract

    fixture = Path(__file__).parent / "fixtures" / f"{name}.etheme"
    with extract(fixture) as raw:
        return extract_wallpaper_specs(raw.asset_root)


def test_e13_fixture_one_tiled_tanbg() -> None:
    specs = _extract_fixture("e13")
    assert len(specs) == 1
    assert specs[0].path.name == "tanbg.png"
    assert specs[0].fill_mode == "tiled"


def test_aliens_fixture_four_scaled() -> None:
    specs = _extract_fixture("Aliens")
    assert len(specs) == 4
    assert all(s.fill_mode == "scaled" for s in specs)


def test_openstep_fixture_no_wallpapers() -> None:
    assert _extract_fixture("OPENSTEP") == ()


def test_tiny_fixture_no_wallpapers() -> None:
    assert _extract_fixture("tiny") == ()
