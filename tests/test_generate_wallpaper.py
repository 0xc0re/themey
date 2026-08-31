"""Tests for themey.generate.wallpaper — the Plasma wallpaper package writer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

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
    spec = WallpaperSpec(path=src, fill_mode="scaled")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    pkg = write_package(theme, spec, pkg_dir)

    assert pkg.width == 32
    assert pkg.height == 24
    assert pkg.fill_mode == "scaled"
    assert pkg.id == wallpaper_id(theme.name, "bg")
    image_path = pkg_dir / "contents" / "images" / "32x24.png"
    assert image_path.is_file()
    with Image.open(image_path) as im:
        assert im.size == (32, 24)


def test_write_package_metadata_json_shape(tmp_path: Path) -> None:
    src = _png(tmp_path / "src" / "bg.png")
    theme = _make_theme(name="Aliens", display_name="Aliens")
    spec = WallpaperSpec(path=src, fill_mode="tiled")
    pkg_dir = tmp_path / wallpaper_id(theme.name, "bg")
    write_package(theme, spec, pkg_dir)

    meta = json.loads((pkg_dir / "metadata.json").read_text())
    assert set(meta.keys()) == {"KPlugin", "X-Themey-FillMode"}
    assert meta["X-Themey-FillMode"] == "tiled"
    assert meta["KPlugin"]["Id"] == wallpaper_id("Aliens", "bg")
    assert "Aliens" in meta["KPlugin"]["Name"]
    assert "bg" in meta["KPlugin"]["Name"]
    assert "(themey)" in meta["KPlugin"]["Name"]


def test_write_package_gif_converts_to_png_first_frame(tmp_path: Path) -> None:
    src = _gif(tmp_path / "src" / "anim.gif", (10, 5))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="scaled")
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
        spec = WallpaperSpec(path=src, fill_mode="scaled")
        with pytest.raises(WallpaperError, match="pixel guard"):
            write_package(theme, spec, tmp_path / "pkg")
    finally:
        wallpaper_mod.Image.open = orig_open


def test_write_package_missing_file_raises(tmp_path: Path) -> None:
    theme = _make_theme()
    spec = WallpaperSpec(path=tmp_path / "nope.png", fill_mode="scaled")
    with pytest.raises(WallpaperError):
        write_package(theme, spec, tmp_path / "pkg")


def test_write_package_cleans_up_pkg_dir_on_mid_write_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failure AFTER images_dir exists (not just the pre-open bomb guard)
    must still leave no partial package directory behind."""
    src = _png(tmp_path / "src" / "bg.png", (10, 10))
    theme = _make_theme()
    spec = WallpaperSpec(path=src, fill_mode="scaled")
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
    spec = WallpaperSpec(path=src, fill_mode="scaled")
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


def test_pick_default_largest_area() -> None:
    small = WallpaperPackage(id="a", dir=Path("a"), width=10, height=10, fill_mode="scaled")
    big = WallpaperPackage(id="b", dir=Path("b"), width=100, height=50, fill_mode="tiled")
    medium = WallpaperPackage(id="c", dir=Path("c"), width=40, height=40, fill_mode="scaled")
    assert pick_default([small, big, medium]) is big


def test_pick_default_empty_is_none() -> None:
    assert pick_default([]) is None


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
