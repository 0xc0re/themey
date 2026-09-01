"""Tests for desktops.cfg wallpaper-path extraction."""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.analyze.wallpaper import (
    extract_wallpaper_specs,
    extract_wallpapers,
    fill_mode_for_layer,
)
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
    assert specs == (WallpaperSpec(path=p, fill_mode="tile"),)


def test_extract_wallpaper_specs_tiled_scaled_vertically_is_tile_h(tmp_path: Path) -> None:
    """ADD_BACKGROUND_TILED_SCALED_VERTICALLY = stretched to screen height,
    tiled across — NOT a plain tile (42 corpus themes use it for gradient
    strips that must not repeat vertically)."""
    p = _touch(tmp_path, "tile.jpeg")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_TILED_SCALED_VERTICALLY("tile.jpeg")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="tile-h"),)


def test_extract_wallpaper_specs_scaled_fill_mode(tmp_path: Path) -> None:
    p = _touch(tmp_path, "a.jpg")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("a.jpg")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="stretch"),)


def test_extract_wallpaper_specs_bg_file_fill_mode(tmp_path: Path) -> None:
    p = _touch(tmp_path, "wp.png")
    _write_cfg(tmp_path, 'BG_FILE("wp.png")\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="stretch"),)


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
    assert specs[0].path is not None
    assert specs[0].path.name == "tanbg.png"
    assert specs[0].fill_mode == "tile"
    # tanbg.png is tiled over SET_SOLID("0 0 0") — the solid must ride along
    # so the generator can flatten the RGBA tile over it.
    assert specs[0].solid_rgb == (0, 0, 0)


def test_aliens_fixture_four_scaled() -> None:
    specs = _extract_fixture("Aliens")
    assert len(specs) == 4
    assert all(s.fill_mode == "stretch" for s in specs)
    # Each block's SET_SOLID rides along with its image spec.
    by_stem = {s.stem: s for s in specs}
    assert by_stem["Alien97"].solid_rgb == (100, 70, 40)
    assert by_stem["giger045"].solid_rgb == (200, 200, 200)


def test_aliens_fixture_commented_overlay_not_noted() -> None:
    """Aliens' only ADD_OVERLAY_IMAGE_* lives inside a /* */ comment — no
    overlay note may fire for it."""
    from themey.etheme.archive import extract

    fixture = Path(__file__).parent / "fixtures" / "Aliens.etheme"
    notes: list[str] = []
    with extract(fixture) as raw:
        extract_wallpaper_specs(raw.asset_root, notes)
    assert not any("overlay" in n.lower() for n in notes), notes


def test_litegnome_fixture_one_tiled() -> None:
    specs = _extract_fixture("LiteGnome")
    assert len(specs) == 1
    assert specs[0].path.name == "tileable.png"
    assert specs[0].fill_mode == "tile"


def test_mac3d_fixture_four_tiled() -> None:
    specs = _extract_fixture("Mac3D")
    assert len(specs) == 4
    assert all(s.fill_mode == "tile" for s in specs)
    assert {s.path.stem for s in specs} == {"steel", "marble", "paper", "black"}


def test_openstep_fixture_solid_only_spec() -> None:
    """OPENSTEP declares only SET_SOLID("200 200 200") — one solid-only spec
    (previously dropped entirely, leaving the conversion with no wallpaper)."""
    specs = _extract_fixture("OPENSTEP")
    assert len(specs) == 1
    s = specs[0]
    assert s.path is None
    assert s.solid_rgb == (200, 200, 200)
    assert s.name == "OPENSTEP_Background"
    assert s.stem == "OPENSTEP_Background"
    assert s.fill_mode == "stretch"


def test_tiny_fixture_no_wallpapers() -> None:
    assert _extract_fixture("tiny") == ()


# --------------------------------------------------------------------- #
# wallpaper: fidelity notes — __FORGROUND_LAYER exclusion, missing files
# --------------------------------------------------------------------- #


def test_forground_layer_excluded_but_noted(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    _touch(tmp_path, "overlay.png")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("Foo")\n'
        '  ADD_BACKGROUND_TILED("bg.png")\n'
        '  __FORGROUND_LAYER "overlay.png" 1 512 512 0 0\n'
        "END_BACKGROUND\n",
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs == (WallpaperSpec(path=p, fill_mode="tile", name="Foo"),)
    assert any(
        n.startswith("wallpaper:") and "overlay.png" in n and "__FORGROUND_LAYER" in n
        for n in notes
    ), notes


def test_litegnome_fixture_forground_layer_noted() -> None:
    from themey.etheme.archive import extract

    fixture = Path(__file__).parent / "fixtures" / "LiteGnome.etheme"
    notes: list[str] = []
    with extract(fixture) as raw:
        extract_wallpaper_specs(raw.asset_root, notes)
    assert any(n.startswith("wallpaper:") and "__FORGROUND_LAYER" in n for n in notes), notes


def test_missing_file_dropped_but_noted(tmp_path: Path) -> None:
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("not-on-disk.jpg")\n')
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs == ()
    assert any(
        n.startswith("wallpaper:") and "not-on-disk.jpg" in n for n in notes
    ), notes


def test_traversal_rejected_silently_no_note(tmp_path: Path) -> None:
    """T-05-01: traversal rejection stays silent — no fidelity note."""
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("../../etc/hostname")\n')
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs == ()
    assert notes == []


def test_notes_default_none_does_not_raise(tmp_path: Path) -> None:
    """Callers that don't pass notes (e.g. the old call sites) still work."""
    _write_cfg(tmp_path, 'ADD_BACKGROUND_SCALED("missing.jpg")\n')
    assert extract_wallpaper_specs(tmp_path) == ()


# --------------------------------------------------------------------- #
# SET_SOLID: solid-only blocks, solid attached to image specs, comments
# --------------------------------------------------------------------- #


def test_solid_only_block_emits_solid_spec_with_note(tmp_path: Path) -> None:
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("Gray")\n'
        '  SET_SOLID("200 200 200")\n'
        '  ON_DESKTOP("0")\n'
        "END_BACKGROUND\n",
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert len(specs) == 1
    assert specs[0].path is None
    assert specs[0].solid_rgb == (200, 200, 200)
    assert specs[0].name == "Gray"
    assert any(n.startswith("wallpaper:") and "SET_SOLID" in n for n in notes), notes


def test_solid_attached_to_image_spec(tmp_path: Path) -> None:
    p = _touch(tmp_path, "tile.png")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("T")\n'
        '  SET_SOLID("0 0 0")\n'
        '  ADD_BACKGROUND_TILED("tile.png")\n'
        "END_BACKGROUND\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (
        WallpaperSpec(path=p, fill_mode="tile", solid_rgb=(0, 0, 0), name="T"),
    )


def test_per_block_solid_does_not_bleed(tmp_path: Path) -> None:
    a = _touch(tmp_path, "a.png")
    b = _touch(tmp_path, "b.png")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("A")\n'
        '  SET_SOLID("1 2 3")\n'
        '  ADD_BACKGROUND_TILED("a.png")\n'
        "END_BACKGROUND\n"
        'BEGIN_BACKGROUND("B")\n'
        '  ADD_BACKGROUND_SCALED("b.png")\n'
        "END_BACKGROUND\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs[0].path == a
    assert specs[0].solid_rgb == (1, 2, 3)
    assert specs[1].path == b
    assert specs[1].solid_rgb is None


def test_commented_out_background_macro_ignored(tmp_path: Path) -> None:
    """/* */ comments are stripped BEFORE macro scanning."""
    _touch(tmp_path, "x.png")
    _write_cfg(tmp_path, '/* ADD_BACKGROUND_SCALED("x.png") */\n')
    assert extract_wallpaper_specs(tmp_path) == ()


# --------------------------------------------------------------------- #
# ADD_OVERLAY_IMAGE_* — note-only (no live overlays in the corpus)
# --------------------------------------------------------------------- #


def test_live_overlay_noted_background_kept(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    _touch(tmp_path, "logo.png")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("O")\n'
        '  ADD_BACKGROUND_SCALED("bg.png")\n'
        '  ADD_OVERLAY_IMAGE_CENTERED("logo.png")\n'
        "END_BACKGROUND\n",
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert len(specs) == 1
    assert specs[0].path == p
    assert any(
        n.startswith("wallpaper:") and "logo.png" in n and "overlay" in n.lower()
        for n in notes
    ), notes


def test_commented_overlay_verbatim_aliens_snippet_silent(tmp_path: Path) -> None:
    """The exact commented-out line Aliens ships must not fire a note."""
    _touch(tmp_path, "artwork/backgrounds/Alien97.jpg")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("Aliens_Alien97")\n'
        '  SET_SOLID("100 70 40")\n'
        '  ADD_BACKGROUND_SCALED("artwork/backgrounds/Alien97.jpg")\n'
        '/* ADD_OVERLAY_IMAGE_CENTERED("artwork/Elogo.png") */\n'
        '  ON_DESKTOP("0")\n'
        "END_BACKGROUND\n",
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert len(specs) == 1
    assert not any("overlay" in n.lower() for n in notes), notes


# --------------------------------------------------------------------- #
# Fill-mode vocabulary: the 6-int __BACKGROUND_LAYER tuple decides
# (E16 backgrounds.c _BgPartFindImageSize + _BackgroundRealize)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "layer, mode",
    [
        # config/definitions:943-1009 macro table, in order
        ((1, 1, 0, 0, 0, 0), "tile"),  # TILED
        ((0, 0, 0, 0, 1024, 1024), "stretch"),  # SCALED
        ((1, 0, 0, 0, 0, 1024), "tile-h"),  # TILED_SCALED_VERTICALLY
        ((1, 0, 0, 0, 1024, 0), "tile-v"),  # TILED_SCALED_HORIZONTALLY
        ((0, 1, 512, 512, 0, 0), "pad"),  # CENTERED
        ((1, 1, 512, 512, 0, 0), "tile"),  # TILED_CENTER
        ((0, 1, 512, 512, 1024, 1024), "fit"),  # SCALED_RETAIN_ASPECT
        ((1, 1, 512, 512, 1024, 1024), "tile-h"),  # TILED_SCALED_RETAIN_ASPECT
        ((0, 1, 1024, 512, 0, 1024), "fit"),  # ..._ALIGN_RIGHT
        ((0, 1, 0, 512, 0, 1024), "fit"),  # ..._ALIGN_LEFT
        ((0, 1, 512, 0, 1024, 0), "fit"),  # ..._ALIGN_TOP
        ((0, 1, 512, 1024, 1024, 0), "fit"),  # ..._ALIGN_BOTTOM
        # raw corpus forms (Rebound / Fossils_of_the_Machines)
        ((1, 0, 0, 0, 1024, 1024), "stretch"),  # one screen-sized tile
        ((1, 0, 0, 0, 0, 0), "tile"),
    ],
)
def test_fill_mode_for_layer_table(layer: tuple[int, ...], mode: str) -> None:
    assert fill_mode_for_layer(*layer)[0] == mode


def test_fill_mode_for_layer_centered_macros_carry_no_note() -> None:
    """The plain macros map cleanly — no approximation note."""
    for layer in [
        (1, 1, 0, 0, 0, 0),
        (0, 0, 0, 0, 1024, 1024),
        (1, 0, 0, 0, 0, 1024),
        (1, 0, 0, 0, 1024, 0),
        (0, 1, 512, 512, 0, 0),
        (0, 1, 512, 512, 1024, 1024),
    ]:
        assert fill_mode_for_layer(*layer)[1] == (), layer


def test_fill_mode_for_layer_align_variants_note_lost_alignment() -> None:
    for layer in [
        (0, 1, 1024, 512, 0, 1024),
        (0, 1, 0, 512, 0, 1024),
        (0, 1, 512, 0, 1024, 0),
        (0, 1, 512, 1024, 1024, 0),
    ]:
        mode, reasons = fill_mode_for_layer(*layer)
        assert mode == "fit"
        assert any("align" in r.lower() for r in reasons), (layer, reasons)


def test_fill_mode_for_layer_tiled_retain_aspect_notes_aspect() -> None:
    mode, reasons = fill_mode_for_layer(1, 1, 512, 512, 1024, 1024)
    assert mode == "tile-h"
    assert any("aspect" in r.lower() for r in reasons), reasons


def test_fill_mode_for_layer_partial_percent_noted() -> None:
    """A 50 % scale has no Plasma analog — nearest mode plus a note."""
    mode, reasons = fill_mode_for_layer(0, 0, 512, 512, 512, 512)
    assert mode == "stretch"
    assert reasons


@pytest.mark.parametrize(
    "macro, mode",
    [
        ("ADD_BACKGROUND_TILED", "tile"),
        ("ADD_BACKGROUND_SCALED", "stretch"),
        ("ADD_BACKGROUND_TILED_SCALED_VERTICALLY", "tile-h"),
        ("ADD_BACKGROUND_TILED_SCALED_HORIZONTALLY", "tile-v"),
        ("ADD_BACKGROUND_CENTERED", "pad"),
        ("ADD_BACKGROUND_TILED_CENTER", "tile"),
        ("ADD_BACKGROUND_SCALED_RETAIN_ASPECT", "fit"),
        ("ADD_BACKGROUND_TILED_SCALED_RETAIN_ASPECT", "tile-h"),
        ("ADD_BACKGROUND_SCALED_RETAIN_ASPECT_ALIGN_RIGHT", "fit"),
        ("ADD_BACKGROUND_SCALED_RETAIN_ASPECT_ALIGN_LEFT", "fit"),
        ("ADD_BACKGROUND_SCALED_RETAIN_ASPECT_ALIGN_TOP", "fit"),
        ("ADD_BACKGROUND_SCALED_RETAIN_ASPECT_ALIGN_BOTTOM", "fit"),
    ],
)
def test_every_background_macro_maps(tmp_path: Path, macro: str, mode: str) -> None:
    p = _touch(tmp_path, "bg.png")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("M")\n'
        f'  {macro}("bg.png")\n'
        "END_BACKGROUND\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode=mode, name="M"),)


def test_align_macro_notes_lost_alignment(tmp_path: Path) -> None:
    _touch(tmp_path, "bg.png")
    _write_cfg(
        tmp_path,
        'ADD_BACKGROUND_SCALED_RETAIN_ASPECT_ALIGN_RIGHT("bg.png")\n',
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs[0].fill_mode == "fit"
    assert any(
        n.startswith("wallpaper:") and "bg.png" in n and "align" in n.lower()
        for n in notes
    ), notes


def test_unknown_background_macro_kept_as_stretch_with_note(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    _write_cfg(tmp_path, 'ADD_BACKGROUND_WIBBLE("bg.png")\n')
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs == (WallpaperSpec(path=p, fill_mode="stretch"),)
    assert any(n.startswith("wallpaper:") and "WIBBLE" in n for n in notes), notes


# --------------------------------------------------------------------- #
# Raw (macro-less) grammar — Rebound and Fossils_of_the_Machines write
# __DESKTOP __BGN / __NAME / __SOLID_COLOR / __BACKGROUND_LAYER / __END
# by hand; previously unparsed, so both lost every wallpaper.
# --------------------------------------------------------------------- #


def test_raw_background_layer_line(tmp_path: Path) -> None:
    p = _touch(tmp_path, "strip.png")
    _write_cfg(tmp_path, '__BACKGROUND_LAYER "strip.png" 1 0 0 0 0 1024\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="tile-h"),)


def test_raw_background_layer_unquoted_path(tmp_path: Path) -> None:
    p = _touch(tmp_path, "strip.png")
    _write_cfg(tmp_path, "__BACKGROUND_LAYER strip.png 0 0 0 0 1024 1024\n")
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="stretch"),)


def test_raw_desktop_block_rebound_shape(tmp_path: Path) -> None:
    """Verbatim Rebound shape: block name and __SOLID_COLOR ride along."""
    p = _touch(tmp_path, "artwork", "background", "cyrusV20.jpg")
    _write_cfg(
        tmp_path,
        "#include <definitions>\n"
        "__E_CFG_VERSION 1\n"
        "__DESKTOP __BGN\n"
        "  __NAME Rebound_V20\n"
        "  __SOLID_COLOR 100 70 40\n"
        '  __BACKGROUND_LAYER "artwork/background/cyrusV20.jpg" 1 0 0 0 1024 1024\n'
        "  __USE_ON_DESKTOP 0\n"
        "__END\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (
        WallpaperSpec(
            path=p, fill_mode="stretch", solid_rgb=(100, 70, 40), name="Rebound_V20"
        ),
    )


def test_raw_desktop_block_trailing_whitespace_fossils_shape(tmp_path: Path) -> None:
    """Fossils_of_the_Machines has a trailing space after the last int."""
    p = _touch(tmp_path, "artwork", "backgrounds", "fotm-logo.jpg")
    _write_cfg(
        tmp_path,
        "__DESKTOP __BGN\n"
        "  __NAME FOTM_LOGO\n"
        "  __SOLID_COLOR 0 0 0\n"
        '  __BACKGROUND_LAYER "artwork/backgrounds/fotm-logo.jpg" 1 0 0 0 1024 1024 \n'
        "  __USE_ON_DESKTOP 4\n"
        "__END\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (
        WallpaperSpec(path=p, fill_mode="stretch", solid_rgb=(0, 0, 0), name="FOTM_LOGO"),
    )


def test_raw_solid_only_block(tmp_path: Path) -> None:
    _write_cfg(
        tmp_path,
        "__DESKTOP __BGN\n"
        "  __NAME Flat\n"
        "  __SOLID_COLOR 10 20 30\n"
        "__END\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (
        WallpaperSpec(path=None, fill_mode="stretch", solid_rgb=(10, 20, 30), name="Flat"),
    )


def test_raw_and_macro_blocks_mix(tmp_path: Path) -> None:
    a = _touch(tmp_path, "a.png")
    b = _touch(tmp_path, "b.png")
    _write_cfg(
        tmp_path,
        'BEGIN_BACKGROUND("A")\n'
        '  SET_SOLID("1 2 3")\n'
        '  ADD_BACKGROUND_CENTERED("a.png")\n'
        "END_BACKGROUND\n"
        "__DESKTOP __BGN\n"
        "  __NAME B\n"
        '  __BACKGROUND_LAYER "b.png" 1 1 0 0 0 0\n'
        "__END\n",
    )
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (
        WallpaperSpec(path=a, fill_mode="pad", solid_rgb=(1, 2, 3), name="A"),
        WallpaperSpec(path=b, fill_mode="tile", name="B"),
    )


def test_raw_forground_layer_in_raw_block_noted_not_shipped(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    _touch(tmp_path, "fg.png")
    _write_cfg(
        tmp_path,
        "__DESKTOP __BGN\n"
        "  __NAME X\n"
        '  __BACKGROUND_LAYER "bg.png" 0 0 0 0 1024 1024\n'
        '  __FORGROUND_LAYER "fg.png" 1 512 512 0 0\n'
        "__END\n",
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs == (WallpaperSpec(path=p, fill_mode="stretch", name="X"),)
    assert any("__FORGROUND_LAYER" in n and "fg.png" in n for n in notes), notes


# --------------------------------------------------------------------- #
# #include following — desktops.cfg may pull background blocks from
# another cfg in the archive; <definitions> (the system macro file) and
# any shipped copy of it must contribute nothing.
# --------------------------------------------------------------------- #


def test_quoted_include_followed(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    (tmp_path / "backgrounds.cfg").write_text(
        'BEGIN_BACKGROUND("Inc")\n'
        '  ADD_BACKGROUND_TILED("bg.png")\n'
        "END_BACKGROUND\n",
        encoding="utf-8",
    )
    _write_cfg(tmp_path, '#include <definitions>\n#include "backgrounds.cfg"\n')
    specs = extract_wallpaper_specs(tmp_path)
    assert specs == (WallpaperSpec(path=p, fill_mode="tile", name="Inc"),)


def test_angle_include_of_archive_file_followed(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "bg.cfg").write_text(
        'ADD_BACKGROUND_SCALED("bg.png")\n', encoding="utf-8"
    )
    _write_cfg(tmp_path, "#include <sub/bg.cfg>\n")
    assert extract_wallpaper_specs(tmp_path) == (
        WallpaperSpec(path=p, fill_mode="stretch"),
    )


def test_include_cycle_terminates(tmp_path: Path) -> None:
    p = _touch(tmp_path, "bg.png")
    (tmp_path / "a.cfg").write_text(
        '#include "desktops.cfg"\nADD_BACKGROUND_TILED("bg.png")\n', encoding="utf-8"
    )
    _write_cfg(tmp_path, '#include "a.cfg"\n')
    assert extract_wallpaper_specs(tmp_path) == (
        WallpaperSpec(path=p, fill_mode="tile"),
    )


def test_include_traversal_ignored(tmp_path: Path) -> None:
    _write_cfg(tmp_path, '#include "../../etc/passwd"\n')
    assert extract_wallpaper_specs(tmp_path) == ()


def test_shipped_definitions_contributes_nothing(tmp_path: Path) -> None:
    """BlueIce ships its own definitions copy; the #define bodies carry
    bare __BACKGROUND_LAYER lines that must not become specs or notes."""
    p = _touch(tmp_path, "bg.png")
    (tmp_path / "definitions").write_text(
        "#define ADD_BACKGROUND_TILED(file)\\\n"
        "  __BACKGROUND_LAYER file 1 1 0 0 0 0\n"
        "#define ADD_BACKGROUND_SCALED(file)\\\n"
        "  __BACKGROUND_LAYER file 0 0 0 0 1024 1024\n",
        encoding="utf-8",
    )
    _write_cfg(
        tmp_path,
        "#include <definitions>\n"
        'ADD_BACKGROUND_TILED("bg.png")\n',
    )
    notes: list[str] = []
    specs = extract_wallpaper_specs(tmp_path, notes)
    assert specs == (WallpaperSpec(path=p, fill_mode="tile"),)
    assert notes == []
