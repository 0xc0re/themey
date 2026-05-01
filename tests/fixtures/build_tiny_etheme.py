"""Build a tiny hand-crafted .etheme for deterministic parser tests.

Run via: uv run python tests/fixtures/build_tiny_etheme.py

The archive contains:
  borders.cfg           — top-level file that #includes borders/default.cfg
  borders/default.cfg   — one __BORDER DEFAULT block with 2 __BORDER_PART children
  imageclasses.cfg      — two __ICLASS blocks (BUTTON_CLOSE, TITLE_BAR_HORIZONTAL)
  textclasses.cfg       — one __TCLASS with __FORGROUND_COLOR (preserved misspelling)
  btn_close.png         — minimal 8×8 transparent PNG
  title.png             — minimal 8×8 transparent PNG
"""
from __future__ import annotations

import io
import tarfile
from pathlib import Path

OUT = Path(__file__).parent / "tiny.etheme"

BORDERS_CFG = b'# tiny theme\n#include "borders/default.cfg"\n'

BORDERS_DEFAULT_CFG = b"""\
__BORDER DEFAULT
__BGN
__BORDER_SIZE_LEFT 4
__BORDER_SIZE_RIGHT 4
__BORDER_SIZE_TOP 18
__BORDER_SIZE_BOTTOM 4
__BORDER_PART
__BGN
    __ICLASS BUTTON_CLOSE
    __ACLASS ACTION_CLOSE
    __TOPLEFT_X_PERCENTAGE 1024
    __TOPLEFT_X_ABSOLUTE -16
    __TOPLEFT_Y_PERCENTAGE 0
    __TOPLEFT_Y_ABSOLUTE 2
    __BOTTOMRIGHT_X_PERCENTAGE 1024
    __BOTTOMRIGHT_X_ABSOLUTE -2
    __BOTTOMRIGHT_Y_PERCENTAGE 0
    __BOTTOMRIGHT_Y_ABSOLUTE 16
__END
__BORDER_PART
__BGN
    __ICLASS TITLE_BAR_HORIZONTAL
    __ACLASS ACTION_MOVE
    __TOPLEFT_X_PERCENTAGE 0
    __TOPLEFT_X_ABSOLUTE 4
    __TOPLEFT_Y_PERCENTAGE 0
    __TOPLEFT_Y_ABSOLUTE 2
    __BOTTOMRIGHT_X_PERCENTAGE 1024
    __BOTTOMRIGHT_X_ABSOLUTE -18
    __BOTTOMRIGHT_Y_PERCENTAGE 0
    __BOTTOMRIGHT_Y_ABSOLUTE 16
__END
__END
"""

IMAGECLASSES_CFG = b"""\
__ICLASS BUTTON_CLOSE
__BGN
__EDGE_SCALING 0 0 0 0
__NORMAL btn_close.png
__NORMAL_ACTIVE btn_close.png
__END
__ICLASS TITLE_BAR_HORIZONTAL
__BGN
__EDGE_SCALING 4 4 0 0
__NORMAL title.png
__NORMAL_ACTIVE title.png
__END
"""

TEXTCLASSES_CFG = b"""\
__TCLASS TEXT1
__BGN
__NORMAL
__FORGROUND_COLOR 200 200 200
__NORMAL_ACTIVE
__FORGROUND_COLOR 255 255 200
__END
"""

# Minimal valid 8×8 transparent PNG (IHDR + IDAT + IEND)
# Generated from a known-good hex sequence for a 1×1 transparent PNG
# and extended to 8×8 so Pillow can open it without complaints.
# Source: https://www.nayuki.io/page/tiny-png-output
PNG_8x8 = bytes.fromhex(
    "89504e470d0a1a0a"          # PNG signature
    "0000000d49484452"          # IHDR chunk length + type
    "000000080000000808060000"  # 8×8, 8-bit RGBA
    "00c40fbe8b"                # IHDR CRC
    "0000000a4944415478da6300010000000500010d0a2db4"  # IDAT (minimal empty)
    "0000000049454e44ae426082"  # IEND
)


def _add(tar: tarfile.TarFile, name: str, content: bytes) -> None:
    info = tarfile.TarInfo(name=name)
    info.size = len(content)
    tar.addfile(info, io.BytesIO(content))


def main() -> None:
    with tarfile.open(OUT, "w:gz") as tar:
        _add(tar, "borders.cfg", BORDERS_CFG)
        _add(tar, "borders/default.cfg", BORDERS_DEFAULT_CFG)
        _add(tar, "imageclasses.cfg", IMAGECLASSES_CFG)
        _add(tar, "textclasses.cfg", TEXTCLASSES_CFG)
        _add(tar, "btn_close.png", PNG_8x8)
        _add(tar, "title.png", PNG_8x8)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
