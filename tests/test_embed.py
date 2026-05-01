"""Tests for src/themey/images/embed.py."""
import base64
import io

from PIL import Image

from themey.images.embed import embed_png_b64, image_to_b64_uri

DATA_URI_PREFIX = "data:image/png;base64,"


def _make_png_bytes(width: int = 8, height: int = 8) -> bytes:
    """Create a small PNG image and return its bytes."""
    img = Image.new("RGBA", (width, height), (42, 84, 126, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_embed_png_b64_prefix():
    result = embed_png_b64(b"x")
    assert result.startswith(DATA_URI_PREFIX)


def test_embed_png_b64_no_newlines():
    png_bytes = _make_png_bytes()
    result = embed_png_b64(png_bytes)
    assert "\n" not in result, "data URI must not contain newlines"
    assert "\r" not in result, "data URI must not contain carriage returns"


def test_embed_png_b64_roundtrip():
    png_bytes = _make_png_bytes(8, 8)
    uri = embed_png_b64(png_bytes)
    # Strip prefix and decode
    b64_part = uri[len(DATA_URI_PREFIX):]
    decoded = base64.b64decode(b64_part)
    img = Image.open(io.BytesIO(decoded))
    assert img.size == (8, 8)


def test_image_to_b64_uri_calls_embed():
    img = Image.new("RGBA", (4, 4), (10, 20, 30, 255))
    result = image_to_b64_uri(img)
    assert result.startswith(DATA_URI_PREFIX)
    # Decode and verify dimensions
    b64_part = result[len(DATA_URI_PREFIX):]
    decoded = base64.b64decode(b64_part)
    loaded = Image.open(io.BytesIO(decoded))
    assert loaded.size == (4, 4)


def test_embed_empty_bytes_still_valid_uri():
    result = embed_png_b64(b"")
    assert result == DATA_URI_PREFIX, (
        f"empty bytes should produce URI with empty payload; got {result!r}"
    )
