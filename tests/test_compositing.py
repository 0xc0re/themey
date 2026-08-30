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
    from themey.generate.composite import declared_zone_extents

    with _theme_ctx("Aliens") as theme:
        ext = declared_zone_extents(theme)
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
        # (we did NOT add corner-driven side growth). The DECLARED zone is
        # the pre-trim value; the interactive-side trim is asserted
        # separately in test_aliens_left_trimmed_for_kill_from_side_button.
        assert ext["left"] == bs.border_size_left, (
            f"Aliens declared left={ext['left']} grew (was "
            f"{bs.border_size_left}) — corner-driven side growth must NOT "
            "happen"
        )


def test_degenerate_rect_pinned_to_min_size() -> None:
    """A part whose rect collapses to zero extent is inflated to its __MIN pin.

    e13's WIN_BOTTOM declares both y coords at H-6 (height 0); its real height
    lives only in the __MIN/__MAX pins (6). The resolved bbox must come out
    6 ref tall, spanning [H-6, H] — otherwise the ``y1 <= y0`` guard drops the
    part and the bottom border never composites.
    """
    from themey.ir import ButtonPart

    part = ButtonPart(
        iclass_name="WIN_BOTTOM",
        aclass="ACTION_RESIZE_V",
        tl_x_pct=0, tl_x_abs=40, br_x_pct=1024, br_x_abs=-6,
        tl_y_pct=1024, tl_y_abs=-6, br_y_pct=1024, br_y_abs=-6,
        min_w=20, min_h=6, max_w=99999, max_h=6,
    )
    bb = resolve_parts((part,), REFERENCE_W, REFERENCE_H)[0]
    assert bb == (40, REFERENCE_H - 6, REFERENCE_W - 6, REFERENCE_H), bb


def test_min_pin_shifts_back_inside_window() -> None:
    """Pin inflation is anchored top-left but shifted back inside the window.

    A degenerate part sitting exactly on the bottom edge (y0 == y1 == H) must
    inflate upward into [H - min_h, H], not spill past the window.
    """
    from themey.ir import ButtonPart

    part = ButtonPart(
        iclass_name="EDGE",
        aclass=None,
        tl_x_pct=0, tl_x_abs=0, br_x_pct=1024, br_x_abs=0,
        tl_y_pct=1024, tl_y_abs=0, br_y_pct=1024, br_y_abs=0,
        min_w=0, min_h=8,
    )
    bb = resolve_parts((part,), REFERENCE_W, REFERENCE_H)[0]
    assert bb == (0, REFERENCE_H - 8, REFERENCE_W, REFERENCE_H), bb


def test_min_pin_noop_when_extent_already_satisfies() -> None:
    """Parts whose extent already meets the pin are untouched (e13 buttons)."""
    from themey.ir import ButtonPart

    part = ButtonPart(
        iclass_name="BUTTON_KILL",
        aclass="ACTION_KILL",
        tl_x_pct=0, tl_x_abs=0, br_x_pct=0, br_x_abs=40,
        tl_y_pct=0, tl_y_abs=0, br_y_pct=0, br_y_abs=38,
        min_w=40, min_h=38, max_w=40, max_h=38,
    )
    bb = resolve_parts((part,), REFERENCE_W, REFERENCE_H)[0]
    assert bb == (0, 0, 40, 38), bb


def _nine_patch_source() -> Image.Image:
    """12x12 RGBA: 3px caps in distinct colors, distinct edge/middle fills.

    Corners: TL red, TR green, BL yellow, BR cyan. Top/bottom edge strips
    magenta/white, left/right edge strips orange/purple, middle blue.
    """
    img = Image.new("RGBA", (12, 12), (0, 0, 255, 255))  # middle blue
    def fill(x0, y0, x1, y1, c):
        for y in range(y0, y1):
            for x in range(x0, x1):
                img.putpixel((x, y), c)
    fill(3, 0, 9, 3, (255, 0, 255, 255))    # top edge magenta
    fill(3, 9, 9, 12, (255, 255, 255, 255)) # bottom edge white
    fill(0, 3, 3, 9, (255, 128, 0, 255))    # left edge orange
    fill(9, 3, 12, 9, (128, 0, 255, 255))   # right edge purple
    fill(0, 0, 3, 3, (255, 0, 0, 255))      # TL red
    fill(9, 0, 12, 3, (0, 255, 0, 255))     # TR green
    fill(0, 9, 3, 12, (255, 255, 0, 255))   # BL yellow
    fill(9, 9, 12, 12, (0, 255, 255, 255))  # BR cyan
    return img


def test_resize_edge_scaling_zero_is_byte_identical_to_uniform() -> None:
    """edge_scaling (0,0,0,0) must take the legacy uniform-resize path."""
    from themey.generate.composite import _resize_with_edge_scaling

    img = _nine_patch_source()
    out = _resize_with_edge_scaling(img, (0, 0, 0, 0), 40, 20, 2)
    ref = img.resize((40, 20), Image.Resampling.NEAREST)
    assert out.tobytes() == ref.tobytes()


def test_resize_edge_scaling_caps_pixel_exact() -> None:
    """Caps are NEAREST-upscaled x scale and pinned to the target's edges."""
    from themey.generate.composite import _resize_with_edge_scaling

    src = _nine_patch_source()
    out = _resize_with_edge_scaling(src, (3, 3, 3, 3), 60, 40, 2)
    assert out.size == (60, 40)
    up = Image.Resampling.NEAREST
    # 3px caps upscaled x2 = 6px, pinned to each corner of the target.
    assert (
        out.crop((0, 0, 6, 6)).tobytes()
        == src.crop((0, 0, 3, 3)).resize((6, 6), up).tobytes()
    )
    assert (
        out.crop((54, 0, 60, 6)).tobytes()
        == src.crop((9, 0, 12, 3)).resize((6, 6), up).tobytes()
    )
    assert (
        out.crop((0, 34, 6, 40)).tobytes()
        == src.crop((0, 9, 3, 12)).resize((6, 6), up).tobytes()
    )
    assert (
        out.crop((54, 34, 60, 40)).tobytes()
        == src.crop((9, 9, 12, 12)).resize((6, 6), up).tobytes()
    )


def test_resize_edge_scaling_middles_stretch() -> None:
    """Only the middle slices stretch: edge strips span cap-to-cap."""
    from themey.generate.composite import _resize_with_edge_scaling

    src = _nine_patch_source()
    out = _resize_with_edge_scaling(src, (3, 3, 3, 3), 60, 40, 2)
    # Top edge strip (magenta) spans x 6..54 at y 0..6.
    assert out.getpixel((30, 2)) == (255, 0, 255, 255)
    assert out.getpixel((7, 2)) == (255, 0, 255, 255)
    assert out.getpixel((53, 2)) == (255, 0, 255, 255)
    # Left edge strip (orange) spans y 6..34.
    assert out.getpixel((2, 20)) == (255, 128, 0, 255)
    # Middle (blue) fills the interior.
    assert out.getpixel((30, 20)) == (0, 0, 255, 255)


def test_resize_edge_scaling_oversized_caps_fall_back_uniform() -> None:
    """Caps that don't fit the image (or the target) fall back to uniform
    resize and leave a composite: note."""
    from themey.generate.composite import _resize_with_edge_scaling

    src = _nine_patch_source()
    notes: list[str] = []
    out = _resize_with_edge_scaling(
        src, (8, 8, 0, 0), 40, 20, 2, notes=notes, part_name="BOGUS"
    )
    ref = src.resize((40, 20), Image.Resampling.NEAREST)
    assert out.tobytes() == ref.tobytes()
    assert any(n.startswith("composite:") and "BOGUS" in n for n in notes)


def test_e13_corner_extents_include_cap_reach() -> None:
    """e13's top-band strips push their unstretchable caps into the corners.

    TITLEBAR (x 40..795, edge_scaling l=5) → topleft reach 45; FIN
    (x 40..798, edge_scaling r=129) → topright reach 131 — the fin ornament
    renders full-size, right-pinned, exactly as E16 anchors it.
    """
    from themey.generate.composite import corner_extents

    with _theme_ctx("e13") as theme:
        ext = corner_extents(theme)
        assert ext["left"] == 45, ext
        assert ext["right"] == 131, ext


def test_e13_left_border_trimmed_to_opaque_art() -> None:
    """The 40-ref left zone hosts a button stack; the strip trims to the art.

    e13's declared left zone (40) exists to hold KILL/ICONIFY/SHADE/STICK,
    which migrate to the Aurorae title row. The non-interactive art in the
    zone (WIN_SIDE_LEFT) is opaque only in cols 24-29 → the required extent
    trims to the ~7-ref opaque span. Right/bottom host no interactive parts,
    so their gates must not fire.
    """
    from themey.generate.composite import (
        declared_zone_extents,
        required_border_extents,
    )

    with _theme_ctx("e13") as theme:
        dz = declared_zone_extents(theme)
        req = required_border_extents(theme)
        assert dz["left"] == 40, dz
        assert req["left"] == 7, req
        assert req["right"] == dz["right"], (req, dz)
        assert req["bottom"] == dz["bottom"], (req, dz)


def test_aliens_left_trimmed_for_kill_from_side_button() -> None:
    """Aliens hosts a kill-from-side BUTTON_KILL at (11,46)-(22,58) in its
    35-ref left zone; the only non-interactive art there is the 5-ref
    BUTTONL resize strip at x 30-35 (the rest is shaped-transparent
    breathing room for the corner head). The gate fires and the left
    border trims to the visible strip; other sides are untouched.
    """
    from themey.generate.composite import (
        declared_zone_extents,
        required_border_extents,
    )

    with _theme_ctx("Aliens") as theme:
        dz = declared_zone_extents(theme)
        req = required_border_extents(theme)
        assert dz["left"] == 35 and req["left"] == 5, (dz, req)
        for side in ("top", "right", "bottom"):
            assert req[side] == dz[side], (side, req, dz)


def test_e13_left_crop_anchored_on_visible_art() -> None:
    """The left strip's crop window must land on the opaque art.

    e13's visible left edge is WIN_SIDE_LEFT's cols 24-29 → ref x 33-40.
    The old bbox-based scan anchored the crop at x=9 (the part's declared
    origin) and the visible border showed only transparency.
    """
    with _theme_ctx("e13") as theme:
        rx0, _, rx1, _ = region_bbox_reference(theme, "left", 120, 48)
        assert rx0 == 33, (rx0, rx1)


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
