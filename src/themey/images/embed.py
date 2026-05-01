"""Embed PNG bytes as SVG-compatible base64 data URI.

AURORAE-03 / Pitfall 6: every <image> element in decoration.svg must use
`data:image/png;base64,...` — relative paths fail to resolve after the SVG
is installed to a different directory.
"""
from __future__ import annotations

import base64
import io

from PIL import Image

DATA_URI_PREFIX = "data:image/png;base64,"


def embed_png_b64(png_bytes: bytes) -> str:
    """Wrap PNG bytes in a base64 data URI with no newlines.

    Args:
        png_bytes: Raw PNG file bytes (or any bytes — caller's responsibility
            to supply valid PNG when embedding in SVG).

    Returns:
        A ``data:image/png;base64,<b64>`` string suitable for use as an SVG
        ``<image>`` ``href`` attribute. Contains no whitespace or newlines.
    """
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return DATA_URI_PREFIX + b64


def image_to_b64_uri(img: Image.Image) -> str:
    """Save a Pillow Image as PNG bytes, then embed as data URI.

    Args:
        img: Any Pillow Image. Will be serialized as PNG.

    Returns:
        A ``data:image/png;base64,...`` data URI string.
    """
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return embed_png_b64(buf.getvalue())
