#!/usr/bin/env python3
"""Build the README's `--upscale` before/after figures.

One figure per theme: the SAME crop of the SAME window, rendered twice by
``themey render --plugin qml`` — once with the default ``--upscale nearest``
and once with ``--upscale waifu2x`` — laid side by side on the flat slate
background the other ``docs/images`` renders use.

The crop is a decoration corner, not the whole window: the client area is
byte-identical between the two runs and only the frame art moves. It is
magnified with NEAREST so the figure shows the real pixels — a browser
scaling a native-size crop up would smooth the ``nearest`` panel too and
hide the very difference the figure exists to show.

Both panels take the same crop rect, which is safe by construction: the
scaler cannot move geometry (``upscale_part`` targets the same ``scale_px``
dims in either mode), so the two renders differ only in pixels.

Usage:
    uv run python scripts/make_upscale_figures.py               # all themes
    uv run python scripts/make_upscale_figures.py Aliens e13    # a subset
    uv run python scripts/make_upscale_figures.py --corpus DIR --out DIR

Output:
    docs/images/<theme-lower>-upscale-compare.png
    plus the raw renders cached under --cache (reused on a re-run)
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
CORPUS = Path.home() / "Desktop" / "ethemes" / "e16"
OUT = REPO / "docs" / "images"
CACHE = Path("/tmp/themey-upscale-figures")

# The slate the existing docs/images renders are composited onto.
FLAT_BG = (88, 96, 110)
GAP_PX = 16
ZOOM = 3

# The four themes whose art gains most, plus Obsidian — the counter-example:
# already-smooth gradient chrome the CNN has nothing to reconstruct from.
THEMES = ["Graphiti", "e13", "OldE", "Aliens", "Obsidian"]

# Crop window over the decoration, in RENDER px, as an offset from the
# top-left of the window's bounding box plus a size. The default lands on the
# top-left corner art; a theme whose interesting art sits elsewhere overrides
# it here.
DEFAULT_CROP = (0, 0, 210, 145)
CROPS: dict[str, tuple[int, int, int, int]] = {}


def render(theme: str, mode: str, corpus: Path, cache: Path) -> Path:
    """Render ``theme`` at ``--upscale mode``, reusing a cached PNG."""
    png = cache / f"{theme}-{mode}.png"
    if png.exists() and png.stat().st_size > 0:
        return png
    archive = corpus / f"{theme}.etheme"
    if not archive.exists():
        raise SystemExit(f"no such archive: {archive}")
    cache.mkdir(parents=True, exist_ok=True)
    print(f"rendering {theme} --upscale {mode} ...", flush=True)
    subprocess.run(
        [
            "uv", "run", "themey", "render", str(archive),
            "--plugin", "qml", "--upscale", mode, "-o", str(png),
        ],
        cwd=REPO,
        check=True,
        stdout=subprocess.DEVNULL,
    )
    return png


def crop_rect(
    a: Image.Image, b: Image.Image, theme: str
) -> tuple[int, int, int, int]:
    """The shared crop box: the theme's window corner, clamped to the frame."""
    box_a, box_b = a.getbbox(), b.getbbox()
    if box_a is None or box_b is None:
        raise SystemExit(f"{theme}: a render is fully transparent")
    left = min(box_a[0], box_b[0])
    top = min(box_a[1], box_b[1])
    dx, dy, w, h = CROPS.get(theme, DEFAULT_CROP)
    x0 = max(0, left + dx)
    y0 = max(0, top + dy)
    return (x0, y0, min(a.width, x0 + w), min(a.height, y0 + h))


def panel(img: Image.Image, box: tuple[int, int, int, int]) -> Image.Image:
    """Crop, flatten onto the slate, and magnify with NEAREST."""
    cut = img.crop(box)
    flat = Image.new("RGBA", cut.size, (*FLAT_BG, 255))
    flat.alpha_composite(cut)
    size = (cut.width * ZOOM, cut.height * ZOOM)
    return flat.convert("RGB").resize(size, Image.Resampling.NEAREST)


def figure(theme: str, corpus: Path, cache: Path, out: Path) -> Path:
    near = Image.open(render(theme, "nearest", corpus, cache)).convert("RGBA")
    waif = Image.open(render(theme, "waifu2x", corpus, cache)).convert("RGBA")
    box = crop_rect(near, waif, theme)
    left, right = panel(near, box), panel(waif, box)
    sheet = Image.new(
        "RGB", (left.width + GAP_PX + right.width, left.height), FLAT_BG
    )
    sheet.paste(left, (0, 0))
    sheet.paste(right, (left.width + GAP_PX, 0))
    out.mkdir(parents=True, exist_ok=True)
    png = out / f"{theme.lower()}-upscale-compare.png"
    sheet.save(png, optimize=True)
    print(f"wrote {png} ({png.stat().st_size // 1024} KB)")
    return png


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("themes", nargs="*", default=None)
    ap.add_argument("--corpus", type=Path, default=CORPUS)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--cache", type=Path, default=CACHE)
    args = ap.parse_args(argv)
    for theme in args.themes or THEMES:
        figure(theme, args.corpus, args.cache, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
