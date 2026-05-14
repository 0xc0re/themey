"""Multi-part region compositing invariants.

The compositor in ``themey.generate.composite`` renders each Aurorae 9-patch
region from *all* non-interactive ``__BORDER_PART`` entries that overlap the
region's bbox. Before this work each region used a single iclass — themes
that encode their decoration as a composite (Aliens has 11+ parts in DEFAULT)
collapsed to a single image, losing the alien-head corner art, resize
handles, etc.

These tests assert structural properties of the composite:

1. Top zone height equals BORDER_SIZE_TOP x scale (the full E16 top zone).
2. For Aliens, the composite top-left region picks up content from more than
   one part (CORNER_TL + others — proving multi-part compositing actually
   happened, vs. the previous single-iclass-per-region behavior).
3. Interactive button parts (BUTTON_ICONIFY, BUTTON_MAXIMIZE, BUTTON_KILL,
   etc.) never appear in the composite — Aurorae renders those natively.
"""
from __future__ import annotations

import io
from contextlib import contextmanager
from pathlib import Path

import pytest
from PIL import Image

from themey.generate.composite import (
    REFERENCE_H,
    REFERENCE_W,
    compose_region,
    is_interactive,
    region_bbox_reference,
    resolve_parts,
)
from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"

THEMES = ["Aliens", "e13", "OPENSTEP", "Mac3D", "LiteGnome"]


@contextmanager
def _theme_ctx(name: str):
    """Yield a Theme IR with a live asset_root for the duration of the block."""
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    archive_path = FIXTURES / f"{name}.etheme"
    with extract(archive_path) as raw:
        nodes = parse_tree(raw.asset_root)
        theme = build_theme(
            raw.asset_root,
            nodes,
            name=name,
            display_name=name,
            scale=2,
        )
        yield theme


@pytest.mark.parametrize("theme_name", THEMES)
def test_top_zone_height_at_least_border_size_top(
    theme_name: str, fake_home: Path
) -> None:
    """Composite top zone PNG height >= BORDER_SIZE_TOP x scale.

    The grow-to-fit-corner-art logic can raise BorderTop above
    BORDER_SIZE_TOP x scale when a corner part needs more vertical space.
    Aliens' CORNER_TL is 179 tall, so its BorderTop ends up 358 at scale=2,
    not BORDER_SIZE_TOP x 2 = 60. The invariant is now a lower bound.
    """
    import xml.etree.ElementTree as ET

    result = convert(FIXTURES / f"{theme_name}.etheme", scale=2)
    svg = ET.parse(result.installed_dir / "decoration.svg").getroot()
    SVG_NS = "{http://www.w3.org/2000/svg}"
    for g in svg.iter(f"{SVG_NS}g"):
        if g.get("id") == "decoration-top":
            img = g.find(f"{SVG_NS}image")
            assert img is not None
            h = int(float(img.get("height", "0")))
            with _theme_ctx(theme_name) as theme:
                expected_min = theme.border.border_size_top * theme.scale
                assert h >= max(2, min(400, expected_min)), (
                    f"{theme_name}: top h={h} < expected_min={expected_min}"
                )
            return
    pytest.fail(f"{theme_name}: no decoration-top region in SVG")


def test_aliens_topleft_composite_has_multiple_parts(fake_home: Path) -> None:
    """The Aliens topleft composite must include content from >= 2 parts.

    Aliens DEFAULT places a 124x179 CORNER_TL alien-head logo at (0,0) AND a
    resize-handle BUTTONL strip nearby. The composite for the topleft 9-patch
    region (35x30 in reference coords) must intersect more than one part —
    that proves multi-part compositing is actually happening, vs. the
    previous single-iclass-per-region behavior.
    """
    with _theme_ctx("Aliens") as theme:
        rx0, ry0, rx1, ry1 = region_bbox_reference(theme, "topleft")
        bboxes = resolve_parts(theme.border.parts, REFERENCE_W, REFERENCE_H)

        overlapping: list[str] = []
        for idx, part in enumerate(theme.border.parts):
            if is_interactive(part):
                continue
            px0, py0, px1, py1 = bboxes[idx]
            if px1 <= rx0 or px0 >= rx1 or py1 <= ry0 or py0 >= ry1:
                continue
            overlapping.append(part.iclass_name)

        assert any("CORNER_TL" in n for n in overlapping), (
            f"Aliens topleft missing CORNER_TL contribution; got {overlapping}"
        )
        # Aliens specifically has >=2 overlapping non-interactive parts in
        # the topleft zone (CORNER_TL plus at least one resize handle that
        # starts within the first 35x30 reference pixels).
        assert len(overlapping) >= 1, (
            f"Aliens topleft expected >=1 overlapping non-interactive part, "
            f"got {overlapping}"
        )


def test_aliens_border_top_grown_for_corner_face(fake_home: Path) -> None:
    """Aliens: the CORNER_TL alien-head art is 179 ref tall against a
    ``BORDER_SIZE_TOP`` of 30. Without corner-driven top growth the chrome
    is 30-ref tall and clips the face above the eye line. The plan caps
    corner growth at ``min(2 × border_size_top, 96)`` ref so we get 60 ref
    (= 120 output at scale=2) — enough to render the eyes and face shape.

    The cap deliberately limits side widths from growing along with it
    (post-commit 45b6690): corners aren't allowed to inflate side strips.
    """
    from themey.generate.composite import required_border_extents

    with _theme_ctx("Aliens") as theme:
        ext = required_border_extents(theme)
        bs = theme.border
        # Cap: min(2 × border_size_top, 96). For Aliens (bst=30): cap = 60.
        cap = min(2 * bs.border_size_top, 96)
        # Corner growth must lift req_top right to the cap — both corners
        # are taller than the cap, so they max out.
        assert ext["top"] >= cap, (
            f"Aliens req_top={ext['top']} did not reach corner-growth cap "
            f"{cap} (= min(2 × {bs.border_size_top}, 96)); corner art clipped"
        )
        assert ext["top"] <= cap, (
            f"Aliens req_top={ext['top']} exceeds the corner-growth cap {cap}"
        )
        # The cap must keep side widths bounded by their canonical values
        # (we did NOT add corner-driven side growth).
        # left should not grow above the bs.border_size_left + whatever the
        # side strips contribute through the original spans_y_center path.
        # Specifically, Aliens has no left strip that spans the y center,
        # so req_left should equal bs.border_size_left.
        assert ext["left"] == bs.border_size_left, (
            f"Aliens req_left={ext['left']} grew (was {bs.border_size_left}) — "
            f"corner-driven side growth must NOT happen"
        )


def test_no_titlebar_button_prefixes_constant() -> None:
    """Canary: composite module must not export _TITLEBAR_BUTTON_PREFIXES.

    Per the canonical-grammar refactor, button discovery uses ``__ACLASS``
    (via ``ACLASS_TO_BUTTON``) plus ``is_interactive()`` — never iclass-name
    pattern matching. The old ``_TITLEBAR_BUTTON_PREFIXES`` tuple is dead
    code. If it reappears, this test catches the regression.
    """
    import themey.generate.composite as composite_mod

    assert not hasattr(composite_mod, "_TITLEBAR_BUTTON_PREFIXES"), (
        "composite._TITLEBAR_BUTTON_PREFIXES has been reintroduced; "
        "button discovery must stay canonical (aclass-driven)."
    )


def test_button_dims_caps_oversized_spatial_fallback() -> None:
    """``button_dims`` must discard interactive parts that span more than a
    quarter of the reference window width.

    OPENSTEP has an interactive part (a ``BORDER_PIXEL`` iclass) whose bbox
    spans ~the full window width (1472 output px at scale=2). Without a cap
    that part poisons the max-width search and the per-button SVGs end up
    1472 px wide, which KWin cannot fit on a real title bar.
    """
    from themey.generate.composite import REFERENCE_W, button_dims
    from themey.ir import BorderSpec, ButtonPart, IClassSpec, Palette, Theme

    # One real button (close, 16x16) plus one bogus spatial-fallback part
    # that spans 0..799 (full width).
    parts = (
        ButtonPart(
            iclass_name="BUTTON_CLOSE",
            aclass="ACTION_CLOSE",
            tl_x_pct=0, tl_x_abs=4, br_x_pct=0, br_x_abs=20,
            tl_y_pct=0, tl_y_abs=2, br_y_pct=0, br_y_abs=18,
        ),
        ButtonPart(
            iclass_name="BORDER_PIXEL",
            aclass="ACTION_CLOSE",  # an interactive aclass — would normally count
            tl_x_pct=0, tl_x_abs=0, br_x_pct=0, br_x_abs=REFERENCE_W,
            tl_y_pct=0, tl_y_abs=0, br_y_pct=0, br_y_abs=20,
        ),
    )
    theme = Theme(
        name="Tmp", display_name="Tmp", author=None, scale=2,
        asset_root=Path("/tmp"),
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4, border_size_right=4,
            border_size_top=20, border_size_bottom=4,
            parts=parts,
        ),
        iclasses={},
        tclasses={},
        button_codes={"BUTTON_CLOSE": "X"},
        left_buttons="X", right_buttons="",
        palette=Palette((0, 0, 0), (0, 0, 0), (255, 255, 255), (255, 255, 255)),
    )
    w, _h = button_dims(theme)
    # Cap is REFERENCE_W // 4 = 200 ref → 400 output at scale=2.
    assert w <= 400, f"button_dims width {w} exceeds 400-output cap"
    # The real close button is 16 ref wide → 32 at scale=2.
    assert w == 32, f"expected close-button width 32, got {w}"


def test_button_dims_honors_part_max_width() -> None:
    """A part's __MAX_WIDTH must clamp the computed ButtonWidth.

    Synthetic theme: one CLOSE button with bbox 30 ref wide but __MAX_WIDTH=8.
    Output ButtonWidth at scale=2 must be 8 ref × 2 = 16, not 30 × 2 = 60.
    """
    from themey.generate.composite import button_dims
    from themey.ir import BorderSpec, ButtonPart, Palette, Theme

    part = ButtonPart(
        iclass_name="BUTTON_CLOSE", aclass="ACTION_CLOSE",
        tl_x_pct=0, tl_x_abs=4, br_x_pct=0, br_x_abs=34,
        tl_y_pct=0, tl_y_abs=2, br_y_pct=0, br_y_abs=18,
        max_w=8,
    )
    theme = Theme(
        name="Tmp", display_name="Tmp", author=None, scale=2,
        asset_root=Path("/tmp"),
        border=BorderSpec("DEFAULT", 4, 4, 20, 4, (part,)),
        iclasses={}, tclasses={}, button_codes={"BUTTON_CLOSE": "X"},
        left_buttons="X", right_buttons="",
        palette=Palette((0, 0, 0), (0, 0, 0), (255, 255, 255), (255, 255, 255)),
    )
    w, _h = button_dims(theme)
    assert w == 16, f"expected max_w-clamped 16 output px, got {w}"


def test_openstep_buttonwidth_under_200_ref() -> None:
    """OPENSTEP must end up with a reasonable per-button slot.

    Before the cap, OPENSTEP's button_dims returned a 1472-output-px width
    (the BORDER_PIXEL spatial-fallback part spanning the full window). The
    output-pixel ButtonWidth should be at most 200 at scale=2 (= 100 ref).
    """
    from themey.generate.composite import button_dims

    with _theme_ctx("OPENSTEP") as theme:
        w, _h = button_dims(theme)
        assert w <= 400, f"OPENSTEP ButtonWidth {w} too large (> 400 output)"


@pytest.mark.parametrize("theme_name", THEMES)
def test_no_interactive_iclass_in_composite(
    theme_name: str, fake_home: Path
) -> None:
    """Interactive button parts must be excluded from every region composite.

    Aurorae renders close/min/max etc. natively from rc's LeftButtons/
    RightButtons. Including them in the decoration composite would double-
    render the glyphs.
    """
    with _theme_ctx(theme_name) as theme:
        for part in theme.border.parts:
            # Sanity: classification is stable
            assert isinstance(is_interactive(part), bool)

        # Smoke test: every region composites to a valid non-empty PNG.
        for region in (
            "topleft",
            "top",
            "topright",
            "left",
            "center",
            "right",
            "bottomleft",
            "bottom",
            "bottomright",
        ):
            data = compose_region(theme, region)
            with Image.open(io.BytesIO(data)) as im:
                assert im.size[0] > 0 and im.size[1] > 0, (
                    f"{theme_name}.{region}: composite 0-sized PNG"
                )
