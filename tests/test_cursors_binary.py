"""Structural assertions on the emitted XCursor binaries (Phase C / C4).

Binary output is not byte-snapshotted (per the testing policy in
CLAUDE.md); instead this file parses the files it produced and checks the
properties KWin actually depends on. The XCursor container is a 16-byte
header, a table of contents, and one image chunk per nominal size:

    header   "Xcur" | header size (16) | version | ntoc
    toc[i]   type (0xfffd0002 = image) | subtype (nominal size) | offset
    chunk    header size (36) | type | subtype | version
             | width | height | xhot | yhot | delay | ARGB pixels

Every field below was read back off a file xcursorgen wrote from this
emitter, not taken from documentation.
"""
from __future__ import annotations

import shutil
import struct
from dataclasses import dataclass
from pathlib import Path

import pytest

from themey.analyze.build_theme import build_theme
from themey.etheme.archive import extract
from themey.etheme.parse import parse_tree
from themey.generate.cursors import write_theme
from themey.slug import cursor_theme_dir

FIXTURES = Path(__file__).parent / "fixtures"

XCURSOR_MAGIC = b"Xcur"
CHUNK_TYPE_IMAGE = 0xFFFD0002

pytestmark = pytest.mark.skipif(
    shutil.which("xcursorgen") is None, reason="xcursorgen not installed"
)


@dataclass(frozen=True)
class XcursorImage:
    nominal: int
    width: int
    height: int
    hot_x: int
    hot_y: int
    pixels: tuple[int, ...]
    """Packed ARGB, one uint32 per pixel, row-major (0x00000000 = clear)."""


def parse_xcursor(path: Path) -> list[XcursorImage]:
    """Parse an XCursor file into its image chunks. Asserts as it goes."""
    data = path.read_bytes()
    magic, header_size, _version, ntoc = struct.unpack_from("<4sIII", data, 0)
    assert magic == XCURSOR_MAGIC, f"{path.name}: not an XCursor file"
    assert header_size == 16
    assert ntoc > 0

    images: list[XcursorImage] = []
    for i in range(ntoc):
        chunk_type, subtype, offset = struct.unpack_from("<III", data, 16 + 12 * i)
        assert chunk_type == CHUNK_TYPE_IMAGE, f"{path.name}: unexpected chunk type"
        assert 0 < offset < len(data), f"{path.name}: toc offset out of file"
        (
            chunk_header,
            inner_type,
            inner_subtype,
            _chunk_version,
            width,
            height,
            hot_x,
            hot_y,
            _delay,
        ) = struct.unpack_from("<IIIIIIIII", data, offset)
        assert chunk_header == 36
        assert inner_type == chunk_type
        assert inner_subtype == subtype, "toc subtype must match the chunk's"
        # The pixel payload must actually be present, not truncated.
        assert offset + 36 + width * height * 4 <= len(data)
        pixels = struct.unpack_from(f"<{width * height}I", data, offset + 36)
        images.append(
            XcursorImage(subtype, width, height, hot_x, hot_y, pixels)
        )
    return images


def _emit(fixture: str, tmp_path: Path):
    """Convert one fixture's cursors into *tmp_path*; returns (result, dir)."""
    out = tmp_path / cursor_theme_dir(fixture)
    with extract(FIXTURES / f"{fixture}.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name=fixture, display_name=fixture, scale=2,
        )
        result = write_theme(theme, out)
    assert result is not None
    return result, out, theme


# --------------------------------------------------------------------- #
# Aliens canary — the six shapes E16 and X11 agree on
# --------------------------------------------------------------------- #


def test_aliens_emits_six_modern_shapes(tmp_path: Path):
    result, _, _ = _emit("Aliens", tmp_path)
    assert set(result.shapes) == {
        "default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"
    }


def test_aliens_every_binary_has_three_nominal_sizes(tmp_path: Path):
    _, out, _ = _emit("Aliens", tmp_path)
    for shape in ("default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"):
        images = parse_xcursor(out / "cursors" / shape)
        assert [i.nominal for i in images] == [16, 32, 48], shape


def test_aliens_image_dimensions_are_the_nearest_upscales(tmp_path: Path):
    """16px sources at x1/x2/x3 — no resampling to a fixed nominal grid."""
    _, out, _ = _emit("Aliens", tmp_path)
    images = parse_xcursor(out / "cursors" / "default")
    assert [(i.width, i.height) for i in images] == [(16, 16), (32, 32), (48, 48)]


def test_aliens_hotspots_stay_inside_the_image(tmp_path: Path):
    _, out, _ = _emit("Aliens", tmp_path)
    for shape in ("default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"):
        for image in parse_xcursor(out / "cursors" / shape):
            assert 0 <= image.hot_x < image.width, shape
            assert 0 <= image.hot_y < image.height, shape


def test_aliens_hotspot_comes_from_the_xbm_and_scales(tmp_path: Path):
    """cursor.xbm declares x_hot 1 / y_hot 1 and the cfg declares none."""
    _, out, _ = _emit("Aliens", tmp_path)
    images = parse_xcursor(out / "cursors" / "default")
    assert [(i.hot_x, i.hot_y) for i in images] == [(1, 1), (2, 2), (3, 3)]


def test_aliens_default_pixels_are_fg_bg_and_transparent(tmp_path: Path):
    """The polarity chain, end to end, on real fixture art.

    test_cursors_xbm.py pins the rasterizer against synthetic bitmaps, but
    if E16's sibling ``.xbm.mask`` convention ran opposite to
    XCreatePixmapCursor, every one of those tests would still pass while
    every shipped pointer came out a solid bg_rgb rectangle. So: read the
    ARGB payload back out of the file xcursorgen wrote and require all
    three states to be present. Aliens' DEFAULT block declares
    __FG_COLOR 255 255 255 and __BG_COLOR 0 0 0, so a correct arrow is
    white fill, black outline, transparent surround — and nothing else.
    """
    _, out, _ = _emit("Aliens", tmp_path)
    x1 = parse_xcursor(out / "cursors" / "default")[0]
    assert (x1.width, x1.height) == (16, 16)
    clear, fg, bg = 0x00000000, 0xFFFFFFFF, 0xFF000000
    assert clear in x1.pixels, "no transparent pixel — the mask was dropped"
    assert fg in x1.pixels, "no foreground pixel — image polarity is inverted"
    assert bg in x1.pixels, "no background pixel — the outline is missing"
    assert set(x1.pixels) == {clear, fg, bg}

    # Presence alone does not pin WHICH color goes where — a fg/bg swap
    # leaves the same three values in the image. So check two pixels,
    # derived by hand from cursor.xbm/.mask rather than from our own
    # output. Row 0 is image 0xf8,0xff over mask 0x07,0x00; row 1 is
    # 0xe6,0xff over 0x1f,0x00. Bits are LSB-first, so at (0,0) the mask
    # bit is set and the image bit is clear -> background, and at (1,1)
    # both are set -> foreground.
    assert x1.pixels[0] == bg, "(0,0) should be the outline, not the fill"
    assert x1.pixels[1 * x1.width + 1] == fg, "(1,1) should be the fill"


def test_aliens_skips_e16_only_shapes(tmp_path: Path):
    _, out, theme = _emit("Aliens", tmp_path)
    for skipped in ("iconify", "kill", "max", "stick"):
        assert not (out / "cursors" / skipped).exists()
    note = next(n for n in theme.notes if "no X11 equivalent" in n)
    assert "4 E16-only pointer(s)" in note


def test_aliens_legacy_aliases_resolve_to_real_binaries(tmp_path: Path):
    _, out, _ = _emit("Aliens", tmp_path)
    cursors = out / "cursors"
    for alias in ("left_ptr", "move", "sb_h_double_arrow", "bottom_right_corner"):
        link = cursors / alias
        assert link.is_symlink()
        assert not link.readlink().is_absolute()
        assert parse_xcursor(link)  # resolves and parses through the link


# --------------------------------------------------------------------- #
# Mac3D canary — _CUR suffixes and non-16px sources
# --------------------------------------------------------------------- #


def test_mac3d_cur_suffixed_names_normalize(tmp_path: Path):
    result, out, _ = _emit("Mac3D", tmp_path)
    assert set(result.shapes) == {
        "default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"
    }
    # MOVE_CUR -> fleur, RESIZE_UL_CUR -> size_fdiag, RESIZE_UR_CUR -> size_bdiag
    for shape in ("fleur", "size_fdiag", "size_bdiag"):
        assert (out / "cursors" / shape).is_file()


def test_mac3d_25px_source_keeps_its_own_nominal_sizes(tmp_path: Path):
    """move.xbm is 25x25, so fleur is 25/50/75 while default stays 16/32/48."""
    _, out, _ = _emit("Mac3D", tmp_path)
    assert [i.nominal for i in parse_xcursor(out / "cursors" / "fleur")] == [25, 50, 75]
    assert [i.nominal for i in parse_xcursor(out / "cursors" / "default")] == [16, 32, 48]


def test_mac3d_hotspots_stay_inside_the_image(tmp_path: Path):
    result, out, _ = _emit("Mac3D", tmp_path)
    for shape in result.shapes:
        for image in parse_xcursor(out / "cursors" / shape):
            assert 0 <= image.hot_x < image.width, shape
            assert 0 <= image.hot_y < image.height, shape


# --------------------------------------------------------------------- #
# The remaining fixtures, as a sweep
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("LiteGnome", {"default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"}),
        ("e13", {"default", "fleur", "size_hor", "size_ver", "size_fdiag", "size_bdiag"}),
        ("OPENSTEP", {"default", "fleur", "size_fdiag", "size_bdiag"}),
    ],
)
def test_fixture_shape_sets(fixture: str, expected: set[str], tmp_path: Path):
    result, out, _ = _emit(fixture, tmp_path)
    assert set(result.shapes) == expected
    for shape in result.shapes:
        assert parse_xcursor(out / "cursors" / shape)
