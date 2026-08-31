"""QML backend geometry — the Python resolver against e13 ground truth.

The resolver (generate/qmldeco/resolver.py) mirrors runtime/resolver.js;
these tests pin the e13 values KWin must reproduce (from E16 borders.c
BorderWinpartCalc semantics, verified against the live E16 rendering):
KILL 40x38 @ (0,0); the ICONIFY/SHADE/STICK stack at x=9; FIN a
full-width 16px strip at y=30; TITLEBAR a compact text-sized plaque
(textwidth + 25) flush left at x=40.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from themey.generate.qmldeco.resolver import part_geometry, scale_px

E13_PATH = Path(__file__).parent / "fixtures" / "e13.etheme"

needs_e13 = pytest.mark.skipif(
    not E13_PATH.exists(), reason="e13.etheme not available on this machine"
)


@pytest.fixture(scope="module")
def e13_data():
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree
    from themey.generate.qmldeco.theme_js import build_theme_data

    with extract(E13_PATH) as raw:
        theme = build_theme(
            raw.asset_root, parse_tree(raw.asset_root), name="e13",
            display_name="e13", scale=2,
        )
        data, _manifest, _fonts = build_theme_data(theme)
    return data


def _index(data: dict, part_id: str) -> int:
    for i, p in enumerate(data["parts"]):
        if p["id"] == part_id:
            return i
    raise AssertionError(f"part {part_id} not in model")


# Frame: 520x300 client at scale 2 + e13 borders (80/12 sides, 92/12 t/b).
FRAME_W = 520 * 2 + 80 + 12
FRAME_H = 300 * 2 + 92 + 12


def _tw(_i: int) -> int:
    return 106  # measured caption width in output px (from the spike render)


@needs_e13
@pytest.mark.parametrize(
    ("part_id", "expected"),
    [
        # Ground truth in output px (ref x scale 2).
        ("BUTTON_KILL", (0, 0, 80, 76)),        # 40x38 @ (0,0)
        ("BUTTON_ICONIFY", (18, 80, 62, 86)),   # 31x43 @ (9,40)
        ("BUTTON_SHADE", (18, 166, 62, 42)),    # 31x21 @ (9,83)
        ("BUTTON_STICK", (18, 208, 62, 76)),    # 31x38 @ (9,104)
    ],
)
def test_e13_button_stack_geometry(e13_data, part_id, expected):
    got = part_geometry(e13_data, _index(e13_data, part_id), FRAME_W, FRAME_H, _tw)
    assert got == expected


@needs_e13
def test_e13_fin_full_width_strip(e13_data):
    x, y, w, h = part_geometry(e13_data, _index(e13_data, "FIN"), FRAME_W, FRAME_H, _tw)
    assert (x, y, h) == (80, 60, 32)  # x=40 ref, y=30 ref, 16 ref tall
    # br abs -2 with the INCLUSIVE anchor → ends 1 ref px short of the edge
    assert x + w == FRAME_W - 1 * 2


@needs_e13
def test_e13_titlebar_is_text_sized_and_flush_left(e13_data):
    x, y, w, h = part_geometry(
        e13_data, _index(e13_data, "TITLEBAR"), FRAME_W, FRAME_H, _tw
    )
    assert (x, y, h) == (80, 0, 92)  # flush left at x=40 ref, full 46-ref band
    # w = (ceil(106/2) + pad 5 + 20) ref x 2 = 156 — text-sized, NOT the span
    assert w == 156
    assert w < FRAME_W // 2, "plaque must be compact, not stretched"


@needs_e13
def test_e13_titlebar_tracks_caption_width(e13_data):
    i = _index(e13_data, "TITLEBAR")
    w_short = part_geometry(e13_data, i, FRAME_W, FRAME_H, lambda _: 40)[2]
    w_long = part_geometry(e13_data, i, FRAME_W, FRAME_H, lambda _: 400)[2]
    assert w_long - w_short == 360  # grows 1:1 with the text (ref-rounded x2)


@needs_e13
def test_e13_title_clamps_to_span_and_min(e13_data):
    i = _index(e13_data, "TITLEBAR")
    # Absurdly long caption: clamps to the declared span (x stays put).
    x, _y, w, _h = part_geometry(e13_data, i, FRAME_W, FRAME_H, lambda _: 10_000)
    assert x == 80
    # br abs -5, inclusive anchor → span ends 4 ref px short of the edge
    assert x + w == FRAME_W - 4 * 2
    # Empty caption: MIN_WIDTH 25 ref holds.
    w_empty = part_geometry(e13_data, i, FRAME_W, FRAME_H, lambda _: 0)[2]
    assert w_empty == 25 * 2


@needs_e13
def test_e13_maximized_band_detection(e13_data):
    """Only parts fitting inside the 46-ref title band survive maximize."""
    hidden = {p["id"] for p in e13_data["parts"] if p["hideWhenMaximized"]}
    assert "BUTTON_KILL" not in hidden  # corner button lives in the band
    assert "TITLEBAR" not in hidden
    assert "FIN" not in hidden
    assert {"BUTTON_ICONIFY", "BUTTON_SHADE", "BUTTON_STICK",
            "WIN_SIDE_LEFT", "WIN_SIDE_RIGHT", "WIN_BOTTOM"} <= hidden


def _mk_part(**over) -> dict:
    base = {
        "id": "P", "tlXP": 0, "tlXA": 0, "tlYP": 0, "tlYA": 0,
        "brXP": 0, "brXA": 9, "brYP": 0, "brYA": 9,
        "tlOrigin": -1, "brOrigin": -1,
        "minW": 0, "maxW": 0, "minH": 0, "maxH": 0,
        "isTitle": False, "vertical": False,
        "padLeft": 0, "padRight": 0, "padTop": 0, "padBottom": 0,
        "justification": 512,
    }
    base.update(over)
    return base


def test_max_clamp_recenters():
    """E16 re-centers a part inside its declared span when exceeding max."""
    data = {"scale": 1, "parts": [_mk_part(brXA=19, brYA=19, maxW=10, maxH=10)]}
    # raw w = 19 - 0 + 1 = 20; max 10 → x += (20-10)>>1 = 5
    assert part_geometry(data, 0, 100, 100, lambda _: 0) == (5, 5, 10, 10)


def test_origin_chaining_adds_origin_position():
    data = {
        "scale": 1,
        "parts": [
            _mk_part(tlXA=10, tlYA=20, brXA=29, brYA=39),  # box (10,20,20,20)
            _mk_part(
                tlOrigin=0, brOrigin=0,
                tlXP=1024, tlXA=0, tlYP=0, tlYA=0,
                brXP=1024, brXA=4, brYP=0, brYA=4,
            ),
        ],
    }
    # tl = origin.x + (100% of origin.w) + 0 = 10+20 = 30; y = 20
    assert part_geometry(data, 1, 200, 200, lambda _: 0) == (30, 20, 5, 5)


def test_vertical_title_sizes_height_to_text():
    data = {
        "scale": 1,
        "parts": [
            _mk_part(
                brXA=19, brYA=199, isTitle=True, vertical=True,
                maxW=20, maxH=0, padTop=3, padBottom=4, justification=0,
            )
        ],
    }
    _x, y, _w, h = part_geometry(data, 0, 300, 300, lambda _: 50)
    assert (y, h) == (0, 57)  # text 50 + pads 7, justified to the top


def test_scale_px_half_rounds_up():
    """scale_px is floor(v*s + 0.5) — half-up in BOTH resolvers, killing
    the Python round() (banker's) vs Math.round() (half-up) divergence."""
    assert scale_px(5, 1.5) == 8
    assert scale_px(9, 1.5) == 14
    assert scale_px(3, 1.5) == 5  # 4.5 rounds up, unlike banker's round()


def test_scale_px_matches_plain_multiplication_at_integer_scales():
    for v in range(-5, 50):
        for s in (1, 2, 3):
            assert scale_px(v, s) == v * s


# Same ref frame as the scale-2 pins (566x352 ref), at scale 1.5.
FRAME_W_15 = 849
FRAME_H_15 = 528


@needs_e13
@pytest.mark.parametrize(
    ("part_id", "expected"),
    [
        # Edge-based rounding of the pinned ref geometry:
        # x_out = scale_px(x), w_out = scale_px(x+w) - x_out.
        ("BUTTON_KILL", (0, 0, 60, 57)),      # 40x38 @ (0,0)
        ("BUTTON_ICONIFY", (14, 60, 46, 65)),  # 31x43 @ (9,40)
        ("BUTTON_SHADE", (14, 125, 46, 31)),   # 31x21 @ (9,83)
        ("BUTTON_STICK", (14, 156, 46, 57)),   # 31x38 @ (9,104)
    ],
)
def test_e13_button_stack_geometry_at_fractional_scale(e13_data, part_id, expected):
    data = dict(e13_data, scale=1.5)
    got = part_geometry(data, _index(data, part_id), FRAME_W_15, FRAME_H_15, _tw)
    assert got == expected


def test_adjacent_parts_share_edges_at_fractional_scale():
    """Parts adjacent in ref space stay seamless in output space — the
    edge-based multiply rounds shared edges identically for both parts."""
    data = {
        "scale": 1.5,
        "parts": [
            _mk_part(brXA=9, brYA=9),                # ref x 0..9
            _mk_part(tlXA=10, brXA=19, brYA=9),      # ref x 10..19
        ],
    }
    ax, _ay, aw, _ah = part_geometry(data, 0, 100, 100, lambda _: 0)
    bx, _by, bw, _bh = part_geometry(data, 1, 100, 100, lambda _: 0)
    assert ax + aw == bx
    assert (ax, aw, bw) == (0, 15, 15)


# ------------------------------------------------------------------ #
# titleBandItem union — Python replica of main.qml's height binding
# (QML can't execute under pytest). The installed title item is the
# union bounding box of the full-width top band and every visible
# button part's rect; KWin's sectionUnderMouse() gives that rect the
# arrow cursor and titlebar drag semantics.
# ------------------------------------------------------------------ #


def _title_union_height(data, frame_w, frame_h, tw, *, maximized=False):
    bottom = data["borders"]["top"]
    for i, p in enumerate(data["parts"]):
        if p["button"] is None:
            continue
        if maximized and p["hideWhenMaximized"]:
            continue
        _x, y, _w, h = part_geometry(data, i, frame_w, frame_h, tw)
        bottom = max(bottom, y + h)
    return bottom


@needs_e13
def test_e13_title_union_covers_button_stack(e13_data):
    # Band 92; button bottoms KILL 76 / ICONIFY 166 / SHADE 208 /
    # STICK 284 → the lowest button wins.
    assert _title_union_height(e13_data, FRAME_W, FRAME_H, _tw) == 284


@needs_e13
def test_e13_title_union_ignores_chrome_parts(e13_data):
    # WIN_BOTTOM reaches the frame bottom — if chrome (button is None)
    # parts entered the union, the whole frame would become titleBar
    # and no resize section would survive.
    i = _index(e13_data, "WIN_BOTTOM")
    _x, y, _w, h = part_geometry(e13_data, i, FRAME_W, FRAME_H, _tw)
    assert y + h > 284
    assert _title_union_height(e13_data, FRAME_W, FRAME_H, _tw) == 284


@needs_e13
def test_e13_title_union_collapses_when_maximized(e13_data):
    # Below-band buttons are hideWhenMaximized; KILL (bottom 76) fits
    # inside the 92px band, so the union collapses to borders.top
    # exactly (== maximizedBorders.top).
    assert (
        _title_union_height(e13_data, FRAME_W, FRAME_H, _tw, maximized=True)
        == 92
    )


@needs_e13
def test_e13_title_union_at_fractional_scale(e13_data):
    # e13_data was emitted at scale 2 (borders pre-scaled); rebuild the
    # display-only band for 1.5: scale_px(46, 1.5) = 69.
    data = dict(
        e13_data, scale=1.5,
        borders=dict(e13_data["borders"], top=69),
    )
    # STICK bottom 213 vs band 69 → union 213.
    assert _title_union_height(data, FRAME_W_15, FRAME_H_15, _tw) == 213


def test_scale_multiplies_after_ref_math():
    """Ref-space math xscale — output-space math would shift this part."""
    data1 = {"scale": 1, "parts": [_mk_part(brXA=40, brYA=38, maxW=40, maxH=38)]}
    data2 = {"scale": 2, "parts": [_mk_part(brXA=40, brYA=38, maxW=40, maxH=38)]}
    g1 = part_geometry(data1, 0, 566, 352, lambda _: 0)
    g2 = part_geometry(data2, 0, 1132, 704, lambda _: 0)
    assert g2 == tuple(v * 2 for v in g1)
    assert g2[:2] == (0, 0)  # the e13 KILL regression: was (1,1)
