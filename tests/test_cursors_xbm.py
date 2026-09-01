"""XBM polarity spike (Phase C / C2) — the guard against inverted cursors.

Every E16 cursor is a pair of X11 bitmaps: the image chooses between the
theme's foreground and background colors, the sibling ``<file>.xbm.mask``
chooses what is drawn at all. Get either polarity backwards and every
cursor in every theme comes out inverted or solid-black, which is easy to
miss in a screenshot and impossible to miss on a live desktop.

The color polarity is NOT plain ``XCreatePixmapCursor``: E16 deliberately
swaps ``__FG_COLOR``/``__BG_COLOR`` for every theme cursor because "the
pmap (not mask) bits in all theme cursors are inverted" (e16-1.0.31
``src/eimage.c:770-791``, the XRender path every real build takes, and
``src/cursors.c:71-74`` for the non-XRender one). The rule is
mechanical: for Aliens-style art (SET bits = body, the corpus majority)
the body renders in ``__BG_COLOR``, the classic black arrow with a white
outline; for e13/Yellow-style art (SET bits = outline) the body takes
``__FG_COLOR``. Either way it is what E16 showed. So this file pins the
cases against synthetic bitmaps it writes itself (no fixture
dependency), per ``eimage.c:783-789``:

    mask bit SET      -> pixel is visible
    mask bit CLEAR    -> pixel is transparent (image bit irrelevant)
    image bit SET     -> BACKGROUND color   (E16's fg/bg swap)
    image bit CLEAR   -> FOREGROUND color   (E16's fg/bg swap)
    no mask file      -> set bits in BACKGROUND color over transparent
                         (E16 itself paints nothing at all here —
                         ``bits_m`` is 0 for every pixel — so this is
                         themey's choice, kept consistent with the swap)

It also pins the reader against the two things Pillow's XbmImagePlugin
cannot do with the real fixture files: a leading ``/* Made with GIMP */``
comment (its header regex is anchored at ``#define``) and a hotspot whose
symbol name contains an underscore (``resize_h_x_hot``, which its
``[^_]*_x_hot`` sub-pattern cannot match).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.generate.cursors import CursorError, rasterize, read_xbm

FG = (255, 0, 0)
BG = (0, 0, 255)


def _write_xbm(
    path: Path,
    name: str,
    width: int,
    height: int,
    rows: list[int],
    *,
    hot: tuple[int, int] | None = None,
    preamble: str = "",
    decl: str = "static char",
) -> Path:
    """Write an XBM whose rows are one byte each (width <= 8)."""
    lines = [preamble] if preamble else []
    lines.append(f"#define {name}_width {width}")
    lines.append(f"#define {name}_height {height}")
    if hot is not None:
        lines.append(f"#define {name}_x_hot {hot[0]}")
        lines.append(f"#define {name}_y_hot {hot[1]}")
    body = ", ".join(f"0x{b:02x}" for b in rows)
    lines.append(f"{decl} {name}_bits[] = {{")
    lines.append(f"   {body} }};")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


@pytest.fixture
def pair(tmp_path: Path) -> tuple[Path, Path]:
    """An 8x8 image + mask exercising all three polarity cases on row 0.

    image row 0 = 0x01 -> only x=0 set
    mask  row 0 = 0x03 -> x=0 and x=1 set
    """
    img = _write_xbm(tmp_path / "p.xbm", "p", 8, 8, [0x01] + [0x00] * 7, hot=(2, 3))
    mask = _write_xbm(tmp_path / "p.xbm.mask", "p", 8, 8, [0x03] + [0x00] * 7)
    return img, mask


# --------------------------------------------------------------------- #
# Polarity — the whole point of this file
# --------------------------------------------------------------------- #


def test_mask_set_and_image_set_is_background(pair):
    """eimage.c:785-786 — ``else if (bits_i & bit) pixel = bg; /* fg/bg
    swapped */``. Plain X11 polarity would say foreground here."""
    img, mask = pair
    out = rasterize(read_xbm(img), read_xbm(mask), FG, BG)
    assert out.getpixel((0, 0)) == (*BG, 255)


def test_mask_set_and_image_clear_is_foreground(pair):
    """eimage.c:787-788 — a masked pixel whose image bit is clear is the
    pointer's body and takes ``__FG_COLOR`` (the swapped ``fg``)."""
    img, mask = pair
    out = rasterize(read_xbm(img), read_xbm(mask), FG, BG)
    assert out.getpixel((1, 0)) == (*FG, 255)


def test_mask_clear_is_transparent_regardless_of_image(pair):
    img, mask = pair
    out = rasterize(read_xbm(img), read_xbm(mask), FG, BG)
    # x=2 is clear in both; x=0 of row 1 is set in neither. Both invisible.
    assert out.getpixel((2, 0))[3] == 0
    assert out.getpixel((0, 1))[3] == 0


def test_mask_clear_wins_over_a_set_image_bit(tmp_path: Path):
    """The dangerous inversion: an image bit with no mask bit must NOT show."""
    img = _write_xbm(tmp_path / "q.xbm", "q", 8, 8, [0xFF] * 8)
    mask = _write_xbm(tmp_path / "q.xbm.mask", "q", 8, 8, [0x00] * 8)
    out = rasterize(read_xbm(img), read_xbm(mask), FG, BG)
    assert out.getbbox() is None  # fully transparent


def test_absent_mask_is_background_over_transparent(pair):
    """No ``.mask`` file: set bits keep the swapped color (``bg``), clear
    bits stay transparent. E16's XRender path would draw nothing at all
    (eimage.c:783-784, ``bits_m`` is 0 without a mask) and the non-XRender
    path a solid rectangle, so there is no fidelity target — the swap is
    just kept consistent with the masked case."""
    img, _ = pair
    out = rasterize(read_xbm(img), None, FG, BG)
    assert out.getpixel((0, 0)) == (*BG, 255)
    assert out.getpixel((1, 0))[3] == 0  # clear bit is transparent, NOT fg


# --------------------------------------------------------------------- #
# Bit and byte order
# --------------------------------------------------------------------- #


def test_bits_are_least_significant_first_within_a_byte(tmp_path: Path):
    img = _write_xbm(tmp_path / "b.xbm", "b", 8, 1, [0x80])
    out = rasterize(read_xbm(img), None, FG, BG)
    assert out.getpixel((7, 0)) == (*BG, 255)  # set bit -> bg (E16 swap)
    assert out.getpixel((0, 0))[3] == 0


def test_rows_are_padded_to_whole_bytes(tmp_path: Path):
    """A 9px row occupies 2 bytes; the second row starts at byte 2."""
    path = tmp_path / "w.xbm"
    path.write_text(
        "#define w_width 9\n#define w_height 2\n"
        "static char w_bits[] = {\n   0x00, 0x01, 0x01, 0x00 };\n",
        encoding="utf-8",
    )
    out = rasterize(read_xbm(path), None, FG, BG)
    assert out.size == (9, 2)
    assert out.getpixel((8, 0)) == (*BG, 255)  # bit 0 of the second byte
    assert out.getpixel((0, 1)) == (*BG, 255)  # first bit of row 1
    assert out.getpixel((0, 0))[3] == 0


# --------------------------------------------------------------------- #
# Header forms Pillow's XbmImagePlugin rejects (measured on the fixtures)
# --------------------------------------------------------------------- #


def test_reads_hotspot(pair):
    img, _ = pair
    xbm = read_xbm(img)
    assert (xbm.hot_x, xbm.hot_y) == (2, 3)


def test_hotspot_is_none_when_absent(pair):
    _, mask = pair
    xbm = read_xbm(mask)
    assert xbm.hot_x is None and xbm.hot_y is None


def test_reads_file_with_leading_comment(tmp_path: Path):
    """Mac3D's GIMP-authored cursors start with a C comment."""
    path = _write_xbm(
        tmp_path / "c.xbm", "c", 8, 1, [0x01], preamble="/* Made with GIMP */"
    )
    assert read_xbm(path).width == 8
    assert rasterize(read_xbm(path), None, FG, BG).getpixel((0, 0)) == (*BG, 255)


def test_reads_hotspot_from_underscored_symbol_name(tmp_path: Path):
    """``resize_h_x_hot`` — the real fixture form."""
    path = _write_xbm(tmp_path / "r.xbm", "resize_h", 8, 1, [0x01], hot=(7, 7))
    xbm = read_xbm(path)
    assert (xbm.hot_x, xbm.hot_y) == (7, 7)


def test_reads_unsigned_char_declaration(tmp_path: Path):
    path = _write_xbm(
        tmp_path / "u.xbm", "u", 8, 1, [0x01], decl="static unsigned char"
    )
    assert read_xbm(path).width == 8


# --------------------------------------------------------------------- #
# Malformed input
# --------------------------------------------------------------------- #


def test_missing_dimensions_raises(tmp_path: Path):
    path = tmp_path / "bad.xbm"
    path.write_text("static char bad_bits[] = {\n   0x01 };\n", encoding="utf-8")
    with pytest.raises(CursorError):
        read_xbm(path)


def test_truncated_bit_data_raises(tmp_path: Path):
    path = tmp_path / "short.xbm"
    path.write_text(
        "#define s_width 8\n#define s_height 4\n"
        "static char s_bits[] = {\n   0x01, 0x02 };\n",
        encoding="utf-8",
    )
    with pytest.raises(CursorError, match="expected 4 bytes"):
        read_xbm(path)


def test_mask_of_different_size_raises(tmp_path: Path):
    img = _write_xbm(tmp_path / "m.xbm", "m", 8, 8, [0x01] * 8)
    mask = _write_xbm(tmp_path / "m.xbm.mask", "m", 8, 4, [0x01] * 4)
    with pytest.raises(CursorError, match="mask"):
        rasterize(read_xbm(img), read_xbm(mask), FG, BG)
