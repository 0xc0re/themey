"""Visual regression for the QML decoration backend — nested-KWin phash.

Unlike the SVG phash tests (which rasterize decoration.svg with
rsvg-convert), the QML backend's only faithful renderer is KWin itself, so
these snapshots come from the real render harness. That makes them slow
(~10s each) and machine-bound; they skip whenever the harness tools are
missing. Hash files: ``tests/snapshots/visual/<theme>-qml.phash``.

Regenerate with::

    pytest tests/test_qmldeco_visual.py --update-visual-hashes
"""
from __future__ import annotations

from pathlib import Path

import imagehash
import pytest
from PIL import Image

from themey import render

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOTS = Path(__file__).parent / "snapshots" / "visual"

THEMES = ["e13", "Aliens"]
THRESHOLD = 8

pytestmark = pytest.mark.skipif(
    not render.available(), reason=f"missing: {render.missing_tools()}"
)


@pytest.mark.parametrize("theme_name", THEMES)
def test_qml_render_visual_phash(
    theme_name: str, tmp_path: Path, request: pytest.FixtureRequest
) -> None:
    png = render.render(
        str(FIXTURES / f"{theme_name}.etheme"),
        out=tmp_path / f"{theme_name}-qml.png",
        plugin="qml",
        scale=2,
    )
    with Image.open(png) as im:
        actual = imagehash.phash(im)

    ref_file = SNAPSHOTS / f"{theme_name}-qml.phash"
    update = request.config.getoption("--update-visual-hashes", default=False)
    if update or not ref_file.is_file():
        ref_file.parent.mkdir(parents=True, exist_ok=True)
        ref_file.write_text(str(actual) + "\n", encoding="utf-8")
        (SNAPSHOTS / f"{theme_name}-qml.png").write_bytes(png.read_bytes())
        if not update:
            pytest.skip(f"created reference hash for {theme_name}-qml; rerun to verify")
        return

    expected = imagehash.hex_to_hash(ref_file.read_text().strip())
    distance = actual - expected
    assert distance <= THRESHOLD, (
        f"{theme_name}-qml: perceptual hash drift {distance} > {THRESHOLD}\n"
        f"  rendered: {png}\n"
        f"  reference snapshot: {SNAPSHOTS / f'{theme_name}-qml.png'}\n"
        f"  Regenerate with: pytest tests/test_qmldeco_visual.py --update-visual-hashes"
    )
