"""waifu2x-ncnn-vulkan as an image-level upscaler.

:func:`waifu2x` is deliberately the same shape as :func:`images.hqx.hqx`
— ``(Image, factor) -> Image`` — so ``upscale_part`` can dispatch to
either without special-casing. The difference is that this one shells out
(``external.run_waifu2x``), which means a temp directory: the tool reads
and writes files, not pipes.

**Alpha is waifu2x's own, not the source's 1-bit mask.** E16 stores a
hard silhouette, so forcing that mask back over the output is the
obvious-looking move; it is the wrong one here on three counts. The
existing quality path already lets hqx blend alpha
(``tests/test_hqx.py``), the QML backend's ``BorderImage`` composites
RGBA correctly, and ``images/opaque.py``'s coverage vote — the one place
a soft edge would actually mislead — is SVG-backend-only, which this
mode never reaches (``pipeline.convert`` rejects any non-nearest mode
for the svg backend). A hard cut would re-staircase exactly the edges
the CNN was run to reconstruct. Measured on e13 at scale 2: a shaped
button ships 273 partially-transparent pixels out of 5332 against hqx's
42 and nearest's 0, and the nested-KWin render shows clean frame edges,
not a halo. If edges ever do look wrong, restoring ``src alpha ->
NEAREST -> target`` after ``upscale_part``'s downsample is a two-line
change.

The subprocess costs ~2.8 s of Vulkan init per call on an RTX 3070, so
``generate/qmldeco/package.export_images`` memoizes per SOURCE FILE
before it gets here (e13: 76 manifest entries, ~26 distinct files).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from PIL import Image

from .. import external


def waifu2x(img: Image.Image, factor: int) -> Image.Image:
    """Return *img* upscaled by *factor* through waifu2x-ncnn-vulkan.

    Always returns a new RGBA image, loaded fully into memory before the
    temp directory goes away.

    Args:
        img: Source Pillow Image.
        factor: One of waifu2x's supported powers of two (2, 4, 8, ...);
            ``upscale.py`` picks it via ``_waifu2x_factor``.

    Raises:
        external.Waifu2xError: If the binary or its model weights are
            absent, or the run produced nothing usable.
    """
    with tempfile.TemporaryDirectory(prefix="themey-waifu2x-") as tmp:
        tmp_dir = Path(tmp)
        src_path = tmp_dir / "src.png"
        out_path = tmp_dir / "out.png"
        img.convert("RGBA").save(src_path)
        external.run_waifu2x(src_path, out_path, factor)
        with Image.open(out_path) as result:
            return result.convert("RGBA")
