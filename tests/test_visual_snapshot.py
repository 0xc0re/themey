"""Visual regression: perceptual-hash decoration.svg renders.

For each fixture theme, this test:
  1. Converts the .etheme via the real pipeline.
  2. Rasterizes decoration.svg with ``rsvg-convert`` at 600x400 (simulating
     a real-world rendered window).
  3. Computes a perceptual hash (imagehash.phash) of the rendered PNG.
  4. Compares against a committed reference hash; fails if the Hamming
     distance exceeds ``THRESHOLD``.

Perceptual hashes are tolerant of librsvg/font version drift — small color
or anti-aliasing differences move ~1-3 bits, large structural changes
(the "thin sliver" regression we just fixed) move >>10 bits.

Hash file format: ``tests/snapshots/visual/<theme>.phash`` — one hex string.

Regenerate with::

    pytest tests/test_visual_snapshot.py --update-visual-hashes

(see ``--update-visual-hashes`` conftest hook).

Skipped if ``rsvg-convert`` isn't on PATH.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import imagehash
import pytest
from PIL import Image

from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOTS = Path(__file__).parent / "snapshots" / "visual"

THEMES = ["Aliens", "e13", "OPENSTEP", "Mac3D", "LiteGnome"]

# Maximum Hamming distance between phashes that still counts as "same scene".
# phash is 64 bits; ≤8 bits = ≈87% similar = same structure, color/AA drift only.
THRESHOLD = 8


def pytest_addoption_for_test(parser):  # pragma: no cover
    """Hook to register --update-visual-hashes (registered in conftest)."""


def _have_rsvg() -> bool:
    return shutil.which("rsvg-convert") is not None


def _render_svg(svg: Path, out: Path, width: int = 600, height: int = 400) -> None:
    subprocess.run(
        ["rsvg-convert", "-w", str(width), "-h", str(height), "-o", str(out), str(svg)],
        check=True,
        capture_output=True,
    )


def _phash_of(png: Path) -> imagehash.ImageHash:
    with Image.open(png) as im:
        return imagehash.phash(im)


def _ref_path(theme_name: str) -> Path:
    return SNAPSHOTS / f"{theme_name}.phash"


@pytest.mark.skipif(not _have_rsvg(), reason="rsvg-convert not available")
@pytest.mark.parametrize("theme_name", THEMES)
def test_decoration_svg_visual_phash(
    theme_name: str, tmp_path: Path, fake_home: Path, request: pytest.FixtureRequest
) -> None:
    """Decoration SVG must render within Hamming distance THRESHOLD of reference."""
    result = convert(FIXTURES / f"{theme_name}.etheme", scale=2)
    svg = result.installed_dir / "decoration.svg"
    png = tmp_path / f"{theme_name}.png"
    _render_svg(svg, png)
    actual = _phash_of(png)

    ref_file = _ref_path(theme_name)
    update = request.config.getoption("--update-visual-hashes", default=False)

    if update or not ref_file.is_file():
        ref_file.parent.mkdir(parents=True, exist_ok=True)
        ref_file.write_text(str(actual) + "\n", encoding="utf-8")
        # On first creation, also save the PNG next to the hash for human review.
        snap_png = SNAPSHOTS / f"{theme_name}.png"
        snap_png.write_bytes(png.read_bytes())
        if not update:
            pytest.skip(f"created reference hash for {theme_name}; rerun to verify")
        return

    expected = imagehash.hex_to_hash(ref_file.read_text().strip())
    distance = actual - expected
    assert distance <= THRESHOLD, (
        f"{theme_name}: perceptual hash drift {distance} > {THRESHOLD}\n"
        f"  expected: {expected}\n"
        f"  actual:   {actual}\n"
        f"  rendered: {png}\n"
        f"  reference snapshot: {SNAPSHOTS / f'{theme_name}.png'}\n"
        f"  Regenerate with: pytest --update-visual-hashes"
    )


@pytest.mark.skipif(not _have_rsvg(), reason="rsvg-convert not available")
@pytest.mark.parametrize("theme_name", THEMES)
def test_decoration_svg_not_mostly_transparent(
    theme_name: str, tmp_path: Path, fake_home: Path
) -> None:
    """Smoke test: rendered decoration has visible artwork (catches the old bug).

    The pre-fix code produced 64x64 canvases with strips squashed to 4-6 pixels,
    rendered as mostly-transparent or single-color blobs. Any rendered frame
    should have at least 5% of pixels with non-trivial alpha.
    """
    result = convert(FIXTURES / f"{theme_name}.etheme", scale=2)
    svg = result.installed_dir / "decoration.svg"
    png = tmp_path / f"{theme_name}.png"
    _render_svg(svg, png)
    with Image.open(png) as im:
        rgba = im.convert("RGBA")
        opaque_px = sum(1 for px in rgba.getdata() if px[3] > 32)
        total = rgba.size[0] * rgba.size[1]
        ratio = opaque_px / total
    # A real window frame is opaque around the perimeter only; expect 10-50%.
    assert ratio > 0.05, (
        f"{theme_name}: only {ratio:.1%} opaque pixels — frame likely empty"
    )
