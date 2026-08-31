"""Tests for themey.analyze.colors — dominant-color sampling + scheme build."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from themey.ir import BorderSpec, ButtonPart, IClassSpec, TClassSpec


def _png(path: Path, size: tuple[int, int], pixels) -> Path:
    """Write an RGBA PNG whose pixels come from ``pixels(x, y)``."""
    im = Image.new("RGBA", size)
    im.putdata([pixels(x, y) for y in range(size[1]) for x in range(size[0])])
    im.save(path)
    return path


def _solid(path: Path, rgba: tuple[int, int, int, int], size=(16, 16)) -> Path:
    return _png(path, size, lambda x, y: rgba)


def _iclass(name: str, normal: Path | None, normal_active: Path | None = None):
    return IClassSpec(
        name=name,
        edge_scaling=(0, 0, 0, 0),
        normal=normal,
        normal_active=normal_active,
        hilited=None,
        hilited_active=None,
        clicked=None,
        clicked_active=None,
        normal_sticky=None,
        normal_active_sticky=None,
    )


def _part(iclass: str, *, title: bool = False, box=(0, 0, 1024, 0, 0, 0, 1024, 0)):
    tlxp, tlxa, brxp, brxa, tlyp, tlya, bryp, brya = box
    return ButtonPart(
        iclass_name=iclass,
        aclass=None,
        tl_x_pct=tlxp,
        tl_x_abs=tlxa,
        tl_y_pct=tlyp,
        tl_y_abs=tlya,
        br_x_pct=brxp,
        br_x_abs=brxa,
        br_y_pct=bryp,
        br_y_abs=brya,
        flags=("__FLAG_TITLE",) if title else (),
    )


def _border(parts) -> BorderSpec:
    return BorderSpec(
        name="DEFAULT",
        border_size_left=4,
        border_size_right=4,
        border_size_top=18,
        border_size_bottom=4,
        parts=tuple(parts),
    )


# --------------------------------------------------------------------- #
# extract_dominant
# --------------------------------------------------------------------- #


def test_extract_dominant_solid_color(tmp_path: Path) -> None:
    from themey.analyze.colors import extract_dominant

    p = _solid(tmp_path / "red.png", (220, 30, 40, 255))
    rgb = extract_dominant(p)
    assert rgb is not None
    assert rgb[0] > 180 and rgb[1] < 80 and rgb[2] < 90


def test_extract_dominant_ignores_transparency_bias(tmp_path: Path) -> None:
    """A half-transparent image must sample as its ART, not as black or mat.

    Transparent RGBA pixels commonly carry (0,0,0,0); converting straight to
    RGB turns half the image into pure black and black wins the count —
    and compositing them over the grey mat instead just makes the MAT win
    (Aliens' 66%-opaque n_menub.png and e13's whole scheme sampled
    (128,128,128) before per-pixel masking). Fully transparent pixels must
    not enter the count at all.
    """
    from themey.analyze.colors import extract_dominant

    p = _png(
        tmp_path / "half.png",
        (16, 16),
        lambda x, y: (0, 0, 0, 0) if y < 8 else (220, 30, 40, 255),
    )
    rgb = extract_dominant(p)
    assert rgb is not None
    assert rgb[0] > 180 and rgb[1] < 80 and rgb[2] < 90, (
        f"expected the red art to win outright, got {rgb}"
    )


def test_extract_clusters_excludes_transparent_pixels(tmp_path: Path) -> None:
    """Pixels at or below the alpha floor never become countable clusters."""
    from themey.analyze.colors import _ALPHA_FLOOR, extract_clusters

    p = _png(
        tmp_path / "mostly-clear.png",
        (16, 16),
        # 75% fully transparent, 25% blue — the old mat compositing made
        # grey the biggest cluster by 3:1.
        lambda x, y: (0, 0, 0, 0) if y < 12 else (20, 90, 200, 255),
    )
    clusters = extract_clusters(p)
    assert clusters
    assert sum(count for count, _ in clusters) == 16 * 4
    assert all(rgb != (128, 128, 128) for _, rgb in clusters)
    assert _ALPHA_FLOOR < 255  # masked, not "only fully opaque"


def test_extract_dominant_semitransparent_still_composites_over_mat(
    tmp_path: Path,
) -> None:
    """Pixels ABOVE the floor but below 255 keep the mat blend — partial
    edges should sample as their seen-on-screen color, not full-strength."""
    from themey.analyze.colors import extract_dominant

    p = _solid(tmp_path / "ghost-red.png", (220, 30, 40, 128))
    rgb = extract_dominant(p)
    assert rgb is not None
    # ~50/50 blend of (220,30,40) and the (128,128,128) mat.
    assert 150 < rgb[0] < 200 and 60 < rgb[1] < 100 and 60 < rgb[2] < 105, (
        f"expected a mat-blended red, got {rgb}"
    )


def test_extract_dominant_prefers_saturated_over_neutral(tmp_path: Path) -> None:
    """A saturated minority beats a slightly larger neutral blob."""
    from themey.analyze.colors import extract_dominant

    p = _png(
        tmp_path / "mix.png",
        (16, 16),
        lambda x, y: (128, 128, 128, 255) if y < 9 else (20, 90, 200, 255),
    )
    rgb = extract_dominant(p)
    assert rgb is not None
    assert rgb[2] > rgb[0], f"expected the blue cluster to win, got {rgb}"


def test_extract_dominant_missing_file(tmp_path: Path) -> None:
    from themey.analyze.colors import extract_dominant

    assert extract_dominant(tmp_path / "nope.png") is None


def test_extract_dominant_fully_transparent(tmp_path: Path) -> None:
    """A fully transparent image carries no color — None, not the grey mat."""
    from themey.analyze.colors import extract_dominant

    p = _solid(tmp_path / "clear.png", (0, 0, 0, 0))
    assert extract_dominant(p) is None


def test_extract_dominant_rejects_decompression_bomb(tmp_path: Path, monkeypatch) -> None:
    from themey.analyze import colors

    monkeypatch.setattr(colors, "MAX_IMAGE_PIXELS", 4)
    p = _solid(tmp_path / "big.png", (220, 30, 40, 255))
    assert colors.extract_dominant(p) is None


# --------------------------------------------------------------------- #
# contrast helper
# --------------------------------------------------------------------- #


def test_contrast_ratio_extremes() -> None:
    from themey.analyze.colors import contrast_ratio

    assert contrast_ratio((0, 0, 0), (255, 255, 255)) == 21.0
    assert contrast_ratio((120, 120, 120), (120, 120, 120)) == 1.0


# --------------------------------------------------------------------- #
# build_scheme
# --------------------------------------------------------------------- #


def test_build_scheme_no_art_falls_back_with_note() -> None:
    from themey.analyze.colors import build_scheme, default_scheme

    notes: list[str] = []
    scheme = build_scheme(_border([]), {}, {}, notes)
    assert scheme == default_scheme()
    assert any(n.startswith("colors:") and "fallback" in n for n in notes)


def test_build_scheme_samples_title_art_for_wm(tmp_path: Path) -> None:
    from themey.analyze.colors import build_scheme

    active = _solid(tmp_path / "title_a.png", (30, 60, 140, 255))
    inactive = _solid(tmp_path / "title_i.png", (90, 90, 90, 255))
    iclasses = {"TITLEBAR": _iclass("TITLEBAR", inactive, active)}
    notes: list[str] = []
    scheme = build_scheme(
        _border([_part("TITLEBAR", title=True)]), iclasses, {}, notes
    )
    assert scheme.wm_active_background[2] > scheme.wm_active_background[0]
    assert max(scheme.wm_inactive_background) - min(scheme.wm_inactive_background) < 20
    assert any("TITLEBAR" in n for n in notes if n.startswith("colors:"))


def test_build_scheme_guards_foreground_contrast(tmp_path: Path) -> None:
    """White TEXT1 on near-white title art must be corrected, not emitted."""
    from themey.analyze.colors import MIN_CONTRAST, build_scheme, contrast_ratio

    art = _solid(tmp_path / "pale.png", (248, 248, 246, 255))
    iclasses = {"TITLEBAR": _iclass("TITLEBAR", art, art)}
    tclasses = {
        "TEXT1": TClassSpec(
            name="TEXT1", fg_normal=(255, 255, 255), fg_active=(255, 255, 255)
        )
    }
    notes: list[str] = []
    scheme = build_scheme(
        _border([_part("TITLEBAR", title=True)]), iclasses, tclasses, notes
    )
    assert (
        contrast_ratio(scheme.wm_active_foreground, scheme.wm_active_background)
        >= MIN_CONTRAST
    )


def test_build_scheme_prefers_text1_when_legible(tmp_path: Path) -> None:
    from themey.analyze.colors import build_scheme

    art = _solid(tmp_path / "dark.png", (20, 20, 24, 255))
    iclasses = {"TITLEBAR": _iclass("TITLEBAR", art, art)}
    tclasses = {
        "TEXT1": TClassSpec(
            name="TEXT1", fg_normal=(200, 200, 90), fg_active=(250, 220, 60)
        )
    }
    scheme = build_scheme(
        _border([_part("TITLEBAR", title=True)]), iclasses, tclasses, []
    )
    assert scheme.wm_active_foreground == (250, 220, 60)
    assert scheme.wm_inactive_foreground == (200, 200, 90)


def test_build_scheme_every_group_is_legible(tmp_path: Path) -> None:
    """Contract: every group's ForegroundNormal clears MIN_CONTRAST."""
    from themey.analyze.colors import MIN_CONTRAST, build_scheme, contrast_ratio

    title = _solid(tmp_path / "t.png", (40, 40, 60, 255))
    side = _solid(tmp_path / "s.png", (200, 190, 120, 255))
    iclasses = {
        "TITLEBAR": _iclass("TITLEBAR", title, title),
        "BORDER_LEFT": _iclass("BORDER_LEFT", side),
    }
    parts = [
        _part("TITLEBAR", title=True),
        _part("BORDER_LEFT", box=(0, 0, 0, 8, 0, 0, 1024, 0)),
    ]
    scheme = build_scheme(_border(parts), iclasses, {}, [])
    for name in (
        "view",
        "window",
        "button",
        "selection",
        "tooltip",
        "complementary",
        "header",
        "header_inactive",
    ):
        group = getattr(scheme, name)
        ratio = contrast_ratio(group.foreground_normal, group.background_normal)
        assert ratio >= MIN_CONTRAST, f"{name}: contrast {ratio:.2f}"


def test_build_scheme_backgrounds_take_the_side_art_cast(tmp_path: Path) -> None:
    """Window/View/Button share the side-art hue and differ in luminance."""
    from themey.analyze.colors import build_scheme

    title = _solid(tmp_path / "t2.png", (40, 40, 60, 255))
    side = _solid(tmp_path / "s2.png", (30, 110, 40, 255))
    iclasses = {
        "TITLEBAR": _iclass("TITLEBAR", title, title),
        "BORDER_LEFT": _iclass("BORDER_LEFT", side),
    }
    parts = [
        _part("TITLEBAR", title=True),
        _part("BORDER_LEFT", box=(0, 0, 0, 8, 0, 0, 1024, 0)),
    ]
    notes: list[str] = []
    scheme = build_scheme(_border(parts), iclasses, {}, notes)
    for group in (scheme.window, scheme.view, scheme.button):
        r, g, b = group.background_normal
        assert g > r and g > b, f"green cast lost: {group.background_normal}"
    ladder = {
        scheme.view.background_normal,
        scheme.window.background_normal,
        scheme.header.background_normal,
    }
    assert len(ladder) == 3, f"luminance ladder collapsed: {ladder}"
    assert any("BORDER_LEFT" in n for n in notes if n.startswith("colors:"))


def test_build_scheme_ladder_survives_black_art(tmp_path: Path) -> None:
    """An all-black border (OPENSTEP's BORDER_PIXEL) must still separate groups.

    A linear-luminance ladder clamps View/Window/Button onto the floor here;
    the perceptual-lightness ladder keeps them distinct and still dark.
    """
    from themey.analyze.colors import build_scheme

    black = _solid(tmp_path / "black.png", (0, 0, 0, 255))
    iclasses = {
        "TITLEBAR": _iclass("TITLEBAR", black, black),
        "BORDER_PIXEL": _iclass("BORDER_PIXEL", black),
    }
    parts = [
        _part("TITLEBAR", title=True),
        _part("BORDER_PIXEL", box=(0, 0, 0, 4, 0, 0, 1024, 0)),
    ]
    scheme = build_scheme(_border(parts), iclasses, {}, [])
    rungs = [
        scheme.view.background_normal,
        scheme.window.background_normal,
        scheme.button.background_normal,
        scheme.header.background_normal,
    ]
    assert len(set(rungs)) == len(rungs), f"ladder collapsed: {rungs}"
    # Still reads as a black theme, not washed out to mid-grey.
    assert max(scheme.header.background_normal) < 90


def test_palette_from_scheme_mirrors_wm_colors(tmp_path: Path) -> None:
    from themey.analyze.colors import build_scheme, palette_from_scheme

    art = _solid(tmp_path / "p.png", (20, 20, 24, 255))
    iclasses = {"TITLEBAR": _iclass("TITLEBAR", art, art)}
    scheme = build_scheme(_border([_part("TITLEBAR", title=True)]), iclasses, {}, [])
    palette = palette_from_scheme(scheme)
    assert palette.titlebar_active == scheme.wm_active_background
    assert palette.titlebar_inactive == scheme.wm_inactive_background
    assert palette.text_active == scheme.wm_active_foreground
    assert palette.text_inactive == scheme.wm_inactive_foreground
