"""Tests for --upscale reaching the Plasma Style package.

Until 2026-09-02 the flag improved the window decoration and NOTHING
else: all three ``upscale_part`` call sites in ``generate/plasmastyle.py``
took the default "nearest", so a themed desktop showed smoothed window
frames beside a staircased panel and Kickoff.

The invariant worth guarding is not the pixels — it is that swapping the
scaler moves NO geometry. Every classifier (``_opaque_trim``,
``_is_rounded``, ``_band_stats``, ``_transparent_fraction``) runs on
SOURCE art, and caps come from ``_scaled_caps(edge, w, h, scale)`` —
source dims times scale, never from the pixels. So the emitted SVG's
element geometry must be byte-identical between modes while the embedded
rasters differ.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from themey import external
from themey.analyze.build_theme import build_theme
from themey.etheme.archive import extract
from themey.etheme.parse import parse_tree
from themey.generate import plasmastyle
from themey.slug import plugin_id

FIXTURES = Path(__file__).parent / "fixtures"

needs_waifu2x = pytest.mark.skipif(
    not external.waifu2x_available(),
    reason="waifu2x-ncnn-vulkan or its model weights not installed",
)

# The base64 payload of an <image> href — the raster, as opposed to the
# geometry attributes that surround it.
_B64 = re.compile(r'xlink:href="data:image/png;base64,[^"]+"')


def _style(tmp_path: Path, name: str, upscale: str, scale: float = 2):
    """Write the Plasma Style for *name* at *upscale*; return the pkg dir."""
    out = tmp_path / upscale / plugin_id(name)
    with extract(FIXTURES / f"{name}.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name=name, display_name=name, scale=scale, upscale=upscale,
        )
        plasmastyle.write(theme, out)
    return out


def _svgs(pkg: Path) -> dict[str, str]:
    return {
        str(p.relative_to(pkg)): p.read_text()
        for p in sorted(pkg.rglob("*.svg"))
    }


def _geometry_only(svg: str) -> str:
    """The SVG with every embedded raster blanked out."""
    return _B64.sub('xlink:href="RASTER"', svg)


def test_theme_carries_the_upscale_mode():
    """It rides on Theme beside `scale`, which is how plasmastyle already
    gets its render setting — _BUILDERS is a fixed Callable[[Theme], ...],
    so an explicit parameter would mean ~35 call sites."""
    with extract(FIXTURES / "Aliens.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens", upscale="quality",
        )
        assert theme.upscale == "quality"


def test_theme_upscale_defaults_to_nearest():
    with extract(FIXTURES / "Aliens.etheme") as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root),
            name="Aliens", display_name="Aliens",
        )
        assert theme.upscale == "nearest"


def test_quality_mode_changes_the_plasma_style_rasters(tmp_path: Path):
    """The whole point: the flag must reach the panel and the menu, not
    just the window frame."""
    near = _svgs(_style(tmp_path, "Aliens", "nearest"))
    qual = _svgs(_style(tmp_path, "Aliens", "quality"))
    assert set(near) == set(qual)
    changed = [rel for rel in near if near[rel] != qual[rel]]
    assert changed, "no Plasma Style SVG changed — the flag never arrived"


def test_quality_mode_moves_no_geometry(tmp_path: Path):
    """Caps, margin hints and every element rect come from source dims x
    scale, so only the rasters may differ."""
    near = _svgs(_style(tmp_path, "Aliens", "nearest"))
    qual = _svgs(_style(tmp_path, "Aliens", "quality"))
    for rel in near:
        assert _geometry_only(near[rel]) == _geometry_only(qual[rel]), (
            f"{rel}: the scaler moved geometry, which it must never do"
        )


@needs_waifu2x
def test_waifu2x_mode_changes_rasters_but_not_geometry(tmp_path: Path):
    near = _svgs(_style(tmp_path, "Aliens", "nearest"))
    w2x = _svgs(_style(tmp_path, "Aliens", "waifu2x"))
    assert set(near) == set(w2x)
    assert [rel for rel in near if near[rel] != w2x[rel]]
    for rel in near:
        assert _geometry_only(near[rel]) == _geometry_only(w2x[rel]), (
            f"{rel}: the scaler moved geometry, which it must never do"
        )


def test_viewitem_source_scale_override_still_applies(tmp_path: Path):
    """The viewitem builder drops to scale 1.0 when the caps would not fit
    a Plasma row. That decision is made on SOURCE art, so it must fire
    identically whatever the scaler is — verified through the geometry
    equality above, but pinned here on the file that carries the rule."""
    near = _svgs(_style(tmp_path, "Aliens", "nearest"))
    qual = _svgs(_style(tmp_path, "Aliens", "quality"))
    rel = plasmastyle.VIEWITEM_SVG
    assert rel in near
    assert _geometry_only(near[rel]) == _geometry_only(qual[rel])
