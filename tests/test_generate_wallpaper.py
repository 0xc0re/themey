"""Tests for themey.generate.wallpaper — the Plasma wallpaper package writer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from themey import external
from themey.generate.wallpaper import (
    MAX_IMAGE_PIXELS,
    WallpaperError,
    WallpaperPackage,
    pick_default,
    write_package,
)
from themey.ir import (
    BorderSpec,
    ButtonPart,
    IClassSpec,
    Palette,
    Theme,
    WallpaperSpec,
)
from themey.slug import wallpaper_id


def _make_theme(name: str = "TestTheme", display_name: str = "Test Theme") -> Theme:
    border = BorderSpec(
        name="DEFAULT",
        border_size_left=4,
        border_size_right=4,
        border_size_top=24,
        border_size_bottom=4,
        parts=(
            ButtonPart(
                iclass_name="CLOSE",
                aclass=None,
                tl_x_pct=0,
                tl_x_abs=0,
                tl_y_pct=0,
                tl_y_abs=0,
                br_x_pct=0,
                br_x_abs=24,
                br_y_pct=0,
                br_y_abs=24,
            ),
        ),
    )
    return Theme(
        name=name,
        display_name=display_name,
        author="tester",
        scale=2,
        asset_root=Path("/tmp/test"),
        border=border,
        iclasses={
            "TITLE_BAR_HORIZONTAL": IClassSpec(
                name="TITLE_BAR_HORIZONTAL",
                edge_scaling=(1, 2, 3, 4),
                normal=None,
                normal_active=None,
                hilited=None,
                hilited_active=None,
                clicked=None,
                clicked_active=None,
                normal_sticky=None,
                normal_active_sticky=None,
            )
        },
        tclasses={},
        button_codes={"CLOSE": "X"},
        left_buttons="X",
        right_buttons="",
        palette=Palette(
            titlebar_active=(40, 40, 40),
            titlebar_inactive=(60, 60, 60),
            text_active=(255, 255, 255),
            text_inactive=(180, 180, 180),
        ),
    )


def _png(path: Path, size: tuple[int, int] = (16, 12)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (10, 20, 30, 255)).save(path, format="PNG")
    return path


def _gif(path: Path, size: tuple[int, int] = (8, 6)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("P", size).save(path, format="GIF")
    return path


def test_write_package_png_passthrough(tmp_path: Path) -> None:
    src = _png(tmp_path / "src" / "bg.png", (32, 24))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    pkg = write_package(theme, spec, pkg_dir)

    assert pkg.width == 32
    assert pkg.height == 24
    assert pkg.fill_mode == "stretch"
    assert pkg.id == wallpaper_id(theme.name, "bg")
    image_path = pkg_dir / "contents" / "images" / "32x24.png"
    assert image_path.is_file()
    with Image.open(image_path) as im:
        assert im.size == (32, 24)


def test_write_package_metadata_json_shape(tmp_path: Path) -> None:
    src = _png(tmp_path / "src" / "bg.png")
    theme = _make_theme(name="Aliens", display_name="Aliens")
    spec = WallpaperSpec(path=src, fill_mode="tile")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    write_package(theme, spec, pkg_dir)

    meta = json.loads((pkg_dir / "metadata.json").read_text())
    assert set(meta.keys()) == {"KPlugin", "X-Themey-FillMode"}
    assert meta["X-Themey-FillMode"] == "tile"
    assert meta["KPlugin"]["Id"] == wallpaper_id("Aliens", "bg")
    assert "Aliens" in meta["KPlugin"]["Name"]
    assert "bg" in meta["KPlugin"]["Name"]
    assert "(themey)" in meta["KPlugin"]["Name"]


def test_write_package_gif_converts_to_png_first_frame(tmp_path: Path) -> None:
    src = _gif(tmp_path / "src" / "anim.gif", (10, 5))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "anim")
    pkg = write_package(theme, spec, pkg_dir)

    assert pkg.width == 10
    assert pkg.height == 5
    image_path = pkg_dir / "contents" / "images" / "10x5.png"
    assert image_path.is_file()
    with Image.open(image_path) as im:
        assert im.format == "PNG"


def test_write_package_bomb_guard(tmp_path: Path) -> None:
    src = tmp_path / "src" / "huge.png"
    src.parent.mkdir(parents=True, exist_ok=True)

    class _FakeImg:
        width = 20_000
        height = 20_000
        format = "PNG"

        def __enter__(self) -> _FakeImg:
            return self

        def __exit__(self, *exc: object) -> None:
            return None

    import themey.generate.wallpaper as wallpaper_mod

    orig_open = wallpaper_mod.Image.open
    wallpaper_mod.Image.open = lambda *_a, **_k: _FakeImg()  # type: ignore[assignment]
    try:
        assert 20_000 * 20_000 > MAX_IMAGE_PIXELS
        theme = _make_theme()
        spec = WallpaperSpec(path=src, fill_mode="stretch")
        with pytest.raises(WallpaperError, match="pixel guard"):
            write_package(theme, spec, tmp_path / "pkg")
    finally:
        wallpaper_mod.Image.open = orig_open


def test_write_package_missing_file_raises(tmp_path: Path) -> None:
    theme = _make_theme()
    spec = WallpaperSpec(path=tmp_path / "nope.png", fill_mode="stretch")
    with pytest.raises(WallpaperError):
        write_package(theme, spec, tmp_path / "pkg")


def test_write_package_cleans_up_pkg_dir_on_mid_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure AFTER images_dir exists (not just the pre-open bomb guard)
    must still leave no partial package directory behind."""
    src = _png(tmp_path / "src" / "bg.png", (10, 10))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg_dir = tmp_path / "pkg"

    import themey.generate.wallpaper as wallpaper_mod

    def _boom(*_a: object, **_k: object) -> None:
        raise OSError("disk full (synthetic)")

    monkeypatch.setattr(wallpaper_mod.shutil, "copyfile", _boom)

    with pytest.raises(WallpaperError, match="disk full"):
        write_package(theme, spec, pkg_dir)
    assert not pkg_dir.exists()


def test_write_package_cleans_up_pkg_dir_on_metadata_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure writing metadata.json (after the image itself succeeded)
    must also roll back the whole package dir, not just the image."""
    src = _png(tmp_path / "src" / "bg.png", (10, 10))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg_dir = tmp_path / "pkg"

    import themey.generate.wallpaper as wallpaper_mod

    orig_write_text = wallpaper_mod.Path.write_text

    def _boom(self: Path, *a: object, **k: object) -> int:
        if self.name == "metadata.json":
            raise OSError("disk full (synthetic)")
        return orig_write_text(self, *a, **k)  # type: ignore[return-value]

    monkeypatch.setattr(wallpaper_mod.Path, "write_text", _boom)

    with pytest.raises(WallpaperError, match="disk full"):
        write_package(theme, spec, pkg_dir)
    assert not pkg_dir.exists()


def test_write_package_solid_only(tmp_path: Path) -> None:
    """A SET_SOLID-only spec becomes a small flat 128x128 PNG package."""
    theme = _make_theme(name="OPENSTEP", display_name="OPENSTEP")
    spec = WallpaperSpec(
        path=None, fill_mode="stretch", solid_rgb=(200, 200, 200),
        name="OPENSTEP_Background",
    )
    pkg_dir = tmp_path / wallpaper_id(theme.name, spec.stem)
    pkg = write_package(theme, spec, pkg_dir)

    assert pkg.solid is True
    assert pkg.width == pkg.height == 128
    assert pkg.fill_mode == "stretch"
    image_path = pkg_dir / "contents" / "images" / "128x128.png"
    assert image_path.is_file()
    with Image.open(image_path) as im:
        assert im.convert("RGB").getpixel((64, 64)) == (200, 200, 200)
    meta = json.loads((pkg_dir / "metadata.json").read_text())
    assert meta["KPlugin"]["Id"] == wallpaper_id("OPENSTEP", "OPENSTEP_Background")


def test_write_package_flattens_alpha_over_solid(tmp_path: Path) -> None:
    """An RGBA source with a solid underneath is composited over the solid —
    e13's tanbg.png tiles over SET_SOLID("0 0 0") in E16."""
    src = tmp_path / "src" / "tanbg.png"
    src.parent.mkdir(parents=True)
    im = Image.new("RGBA", (8, 8), (10, 20, 30, 255))
    im.putpixel((0, 0), (0, 0, 0, 0))  # fully transparent corner
    im.save(src, format="PNG")

    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="tile", solid_rgb=(0, 0, 0))
    pkg_dir = tmp_path / wallpaper_id(theme.name, "tanbg")
    pkg = write_package(theme, spec, pkg_dir)

    assert pkg.solid is False
    image_path = pkg_dir / "contents" / "images" / "8x8.png"
    with Image.open(image_path) as out:
        rgb = out.convert("RGB")
        assert rgb.getpixel((0, 0)) == (0, 0, 0)  # solid shows through
        assert rgb.getpixel((4, 4)) == (10, 20, 30)  # opaque art untouched
    assert any("flattened" in n for n in theme.notes), theme.notes


def test_write_package_opaque_with_solid_copied_through(tmp_path: Path) -> None:
    """An opaque (no-alpha) source is byte-copied even when the block also
    declared a SET_SOLID — nothing to flatten."""
    src = tmp_path / "src" / "bg.png"
    src.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), (10, 20, 30)).save(src, format="PNG")

    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch", solid_rgb=(1, 2, 3))
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    write_package(theme, spec, pkg_dir)

    dest = pkg_dir / "contents" / "images" / "16x12.png"
    assert dest.read_bytes() == src.read_bytes()


def test_write_package_alpha_without_solid_copied_through(tmp_path: Path) -> None:
    """RGBA with NO solid underneath keeps today's byte-copy behavior."""
    src = _png(tmp_path / "src" / "bg.png", (16, 12))  # RGBA helper
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    write_package(theme, spec, pkg_dir)
    dest = pkg_dir / "contents" / "images" / "16x12.png"
    assert dest.read_bytes() == src.read_bytes()


def test_pick_default_largest_area() -> None:
    small = WallpaperPackage(id="a", dir=Path("a"), width=10, height=10, fill_mode="stretch")
    big = WallpaperPackage(id="b", dir=Path("b"), width=100, height=50, fill_mode="tile")
    medium = WallpaperPackage(id="c", dir=Path("c"), width=40, height=40, fill_mode="stretch")
    assert pick_default([small, big, medium]) is big


def test_pick_default_empty_is_none() -> None:
    assert pick_default([]) is None


def test_pick_default_solid_never_outranks_art() -> None:
    """A solid package loses to real art regardless of area; it wins only
    when it's the only package (OPENSTEP's case)."""
    solid = WallpaperPackage(
        id="s", dir=Path("s"), width=128, height=128, fill_mode="stretch", solid=True
    )
    art = WallpaperPackage(
        id="a", dir=Path("a"), width=64, height=48, fill_mode="tile"
    )
    assert pick_default([solid, art]) is art
    assert pick_default([solid]) is solid


def test_aliens_fixture_four_packages_one_gif_converted(tmp_path: Path) -> None:
    from themey.analyze.wallpaper import extract_wallpaper_specs
    from themey.etheme.archive import extract

    fixture = Path(__file__).parent / "fixtures" / "Aliens.etheme"
    theme = _make_theme(name="Aliens", display_name="Aliens")
    with extract(fixture) as raw:
        specs = extract_wallpaper_specs(raw.asset_root)
        assert len(specs) == 4
        packages = []
        for spec in specs:
            pkg_dir = tmp_path / wallpaper_id(theme.name, spec.path.stem)
            packages.append(write_package(theme, spec, pkg_dir))

    assert len(packages) == 4
    ids = {p.id for p in packages}
    assert len(ids) == 4  # all distinct
    gif_pkg = next(p for p in packages if p.id == wallpaper_id("Aliens", "giger045"))
    gif_images = list((gif_pkg.dir / "contents" / "images").glob("*"))
    assert len(gif_images) == 1
    assert gif_images[0].suffix == ".png"


# --------------------------------------------------------------------- #
# Fill-mode vocabulary + SET_SOLID letterbox color in the metadata
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("mode", ["stretch", "tile", "tile-h", "tile-v", "pad", "fit"])
def test_write_package_metadata_carries_every_fill_mode(tmp_path: Path, mode: str) -> None:
    src = _png(tmp_path / "src" / "bg.png")
    theme = _make_theme()
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    pkg = write_package(theme, WallpaperSpec(path=src, fill_mode=mode), pkg_dir)
    meta = json.loads((pkg_dir / "metadata.json").read_text())
    assert meta["X-Themey-FillMode"] == mode
    assert pkg.fill_mode == mode


def test_write_package_metadata_solid_color_for_letterbox(tmp_path: Path) -> None:
    """A block's SET_SOLID is the letterbox color of a fit/pad wallpaper —
    written as KConfig's QColor spelling so apply can hand it straight to
    the Image wallpaper's Color key."""
    src = tmp_path / "src" / "logo.png"
    src.parent.mkdir(parents=True)
    Image.new("RGB", (16, 12), (10, 20, 30)).save(src, format="PNG")
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="pad", solid_rgb=(100, 70, 40))
    pkg_dir = tmp_path / wallpaper_id(theme.name, "logo")
    write_package(theme, spec, pkg_dir)
    meta = json.loads((pkg_dir / "metadata.json").read_text())
    assert set(meta.keys()) == {"KPlugin", "X-Themey-FillMode", "X-Themey-SolidColor"}
    assert meta["X-Themey-SolidColor"] == "100,70,40"


def test_write_package_metadata_no_solid_key_without_solid(tmp_path: Path) -> None:
    src = _png(tmp_path / "src" / "bg.png")
    theme = _make_theme()
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    write_package(theme, WallpaperSpec(path=src, fill_mode="fit"), pkg_dir)
    meta = json.loads((pkg_dir / "metadata.json").read_text())
    assert "X-Themey-SolidColor" not in meta


# --------------------------------------------------------------------- #
# waifu2x upscaling (--upscale waifu2x only)
# --------------------------------------------------------------------- #

needs_waifu2x = pytest.mark.skipif(
    not external.waifu2x_available(),
    reason="waifu2x-ncnn-vulkan or its model weights not installed",
)


def _jpeg(path: Path, size: tuple[int, int]) -> Path:
    """A JPEG with real structure — a flat fill compresses to nothing and
    tells us nothing about re-encode size."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size)
    px = img.load()
    assert px is not None
    for y in range(size[1]):
        for x in range(size[0]):
            px[x, y] = ((x * 7) % 256, (y * 5) % 256, ((x + y) * 3) % 256)
    img.save(path, format="JPEG", quality=85)
    return path


def test_default_mode_leaves_wallpapers_untouched(tmp_path: Path) -> None:
    """nearest/quality must not touch wallpapers: hqx on a photo is wrong,
    and this is the behaviour every existing package depends on."""
    src = _jpeg(tmp_path / "src" / "bg.jpg", (64, 48))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    pkg = write_package(theme, spec, pkg_dir)
    assert pkg.width == 64 and pkg.height == 48
    # byte-for-byte passthrough is the documented contract at default
    shipped = pkg.dir / "contents" / "images" / "64x48.jpg"
    assert shipped.read_bytes() == src.read_bytes()


def test_upscale_only_applies_below_the_threshold(tmp_path: Path) -> None:
    """A source that already covers a 1080p width ships as-is — 2x-ing a
    1920-wide image only bloats the package."""
    from themey.generate.wallpaper import WALLPAPER_UPSCALE_MAX_WIDTH

    big = WALLPAPER_UPSCALE_MAX_WIDTH
    src = _jpeg(tmp_path / "src" / "wide.jpg", (big, 100))
    theme = _make_theme()
    object.__setattr__(theme, "upscale", "waifu2x")
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg = write_package(theme, spec, tmp_path / wallpaper_id(theme.name, "wide"))
    assert (pkg.width, pkg.height) == (big, 100)


@needs_waifu2x
def test_waifu2x_doubles_a_small_wallpaper(tmp_path: Path) -> None:
    src = _jpeg(tmp_path / "src" / "small.jpg", (64, 48))
    theme = _make_theme()
    object.__setattr__(theme, "upscale", "waifu2x")
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg = write_package(theme, spec, tmp_path / wallpaper_id(theme.name, "small"))
    assert (pkg.width, pkg.height) == (128, 96)
    assert (pkg.dir / "contents" / "images" / "128x96.jpg").is_file()


def test_waifu2x_failure_ships_the_original_with_a_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A scaler failure must never fail the conversion — same spirit as
    the hqx fallback in pipeline.convert."""
    monkeypatch.setattr(
        "themey.generate.wallpaper.waifu2x",
        lambda img, factor: (_ for _ in ()).throw(external.Waifu2xError("boom")),
    )
    src = _jpeg(tmp_path / "src" / "small.jpg", (64, 48))
    theme = _make_theme()
    object.__setattr__(theme, "upscale", "waifu2x")
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg = write_package(theme, spec, tmp_path / wallpaper_id(theme.name, "small"))
    assert (pkg.width, pkg.height) == (64, 48)
    assert any(n.startswith("wallpaper:") and "boom" in n for n in theme.notes)


def test_upscale_never_breaches_the_decompression_guard(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The guard is checked against the POST-upscale size: a source that
    passes at 1x can be 4x the pixels afterwards."""
    monkeypatch.setattr(
        "themey.generate.wallpaper.MAX_IMAGE_PIXELS", 64 * 48 * 2
    )
    src = _jpeg(tmp_path / "src" / "small.jpg", (64, 48))
    theme = _make_theme()
    object.__setattr__(theme, "upscale", "waifu2x")
    spec = WallpaperSpec(path=src, fill_mode="stretch")
    pkg = write_package(theme, spec, tmp_path / wallpaper_id(theme.name, "small"))
    assert (pkg.width, pkg.height) == (64, 48)
