"""Tests for themey.generate.lookandfeel — the Plasma Global Theme bundle writer.

Format census (byte-verified against an installed Look-and-Feel
package): metadata.json is Plasma/LookAndFeel with
KPlugin.Id == dirname; contents/defaults carries double-bracket sections,
each conditional on its artifact actually existing, in the order
kdeglobals/kcminputrc/Wallpaper/kwinrc.
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from themey.generate.lookandfeel import (
    WIDGET_STYLES,
    LookAndFeelBundle,
    build_defaults_sections,
    deco_defaults,
    write,
    write_metadata_json,
    write_preview,
)
from themey.ir import BorderSpec, IClassSpec, Palette, Theme
from themey.kwin import PLUGINS
from themey.slug import plugin_id


def _make_theme(name: str = "Aliens", display_name: str = "Aliens") -> Theme:
    border = BorderSpec(
        name="DEFAULT",
        border_size_left=4,
        border_size_right=4,
        border_size_top=24,
        border_size_bottom=4,
        parts=(),
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
        button_codes={},
        left_buttons="X",
        right_buttons="",
        palette=Palette(
            titlebar_active=(40, 40, 40),
            titlebar_inactive=(60, 60, 60),
            text_active=(255, 255, 255),
            text_inactive=(180, 180, 180),
        ),
    )


def _png(path: Path, size: tuple[int, int] = (32, 24)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (10, 20, 30)).save(path, format="PNG")
    return path


# --------------------------------------------------------------------- #
# deco_defaults
# --------------------------------------------------------------------- #


def test_deco_defaults_qml_uses_legacy_plugin_and_pkg_id() -> None:
    assert deco_defaults("Aliens", want_qml=True, pkg_id="themey_Aliens") == (
        PLUGINS["legacy"],
        "themey_Aliens",
    )


def test_deco_defaults_svg_only_uses_v2_and_aurorae_svg_theme_string() -> None:
    assert deco_defaults("Aliens", want_qml=False, pkg_id="themey_Aliens") == (
        PLUGINS["v2"],
        "__aurorae__svg__Aliens",
    )


# --------------------------------------------------------------------- #
# build_defaults_sections
# --------------------------------------------------------------------- #


def test_defaults_sections_all_artifacts_present() -> None:
    sections = build_defaults_sections(
        color_scheme_stem="themey_Aliens",
        cursor_theme_name="themey_Aliens-cursors",
        default_wallpaper_id="themey_Aliens_giger045",
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
    )
    assert list(sections) == [
        "kdeglobals][General",
        "kcminputrc][Mouse",
        "Wallpaper",
        "kwinrc][org.kde.kdecoration2",
    ]
    assert sections["kdeglobals][General"] == {"ColorScheme": "themey_Aliens"}
    assert sections["kcminputrc][Mouse"] == {"cursorTheme": "themey_Aliens-cursors"}
    assert sections["Wallpaper"] == {"Image": "themey_Aliens_giger045"}
    assert sections["kwinrc][org.kde.kdecoration2"] == {
        "library": PLUGINS["legacy"],
        "theme": "themey_Aliens",
    }


def test_defaults_sections_omit_missing_artifacts() -> None:
    """No wallpaper, no cursor theme -> those keys/groups vanish entirely.

    plasma-apply-lookandfeel has no partial-apply flag, so a key pointing
    at a package that was never installed would break, not degrade.
    """
    sections = build_defaults_sections(
        color_scheme_stem="themey_Synthetic",
        cursor_theme_name=None,
        default_wallpaper_id=None,
        deco_library=PLUGINS["v2"],
        deco_theme="__aurorae__svg__Synthetic",
    )
    assert "kcminputrc][Mouse" not in sections
    assert "Wallpaper" not in sections
    assert list(sections) == ["kdeglobals][General", "kwinrc][org.kde.kdecoration2"]


def test_defaults_sections_desktop_theme_group_last_when_set() -> None:
    """[plasmarc][Theme] name= goes LAST, matching the real third-party
    bundles byte-verified on the reference machine."""
    sections = build_defaults_sections(
        color_scheme_stem="themey_Aliens",
        cursor_theme_name=None,
        default_wallpaper_id=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
        desktop_theme_name="themey_Aliens",
    )
    assert list(sections) == [
        "kdeglobals][General",
        "kwinrc][org.kde.kdecoration2",
        "plasmarc][Theme",
    ]
    assert sections["plasmarc][Theme"] == {"name": "themey_Aliens"}


def test_defaults_sections_no_desktop_theme_group_when_none() -> None:
    sections = build_defaults_sections(
        color_scheme_stem=None,
        cursor_theme_name=None,
        default_wallpaper_id=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_X",
        desktop_theme_name=None,
    )
    assert "plasmarc][Theme" not in sections


def test_defaults_sections_deco_group_always_present() -> None:
    """The kwinrc group is unconditional: some deco backend always installs."""
    sections = build_defaults_sections(
        color_scheme_stem=None,
        cursor_theme_name=None,
        default_wallpaper_id=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_X",
    )
    assert list(sections) == ["kwinrc][org.kde.kdecoration2"]


# --------------------------------------------------------------------- #
# write_metadata_json
# --------------------------------------------------------------------- #


def test_metadata_json_shape(tmp_path: Path) -> None:
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write_metadata_json(theme, out_dir)
    meta = json.loads((out_dir / "metadata.json").read_text())
    assert meta["KPackageStructure"] == "Plasma/LookAndFeel"
    assert meta["KPlugin"]["Id"] == plugin_id(theme.name) == out_dir.name
    assert "(themey)" in meta["KPlugin"]["Name"]
    assert "Aliens" in meta["KPlugin"]["Name"]


# --------------------------------------------------------------------- #
# write_preview
# --------------------------------------------------------------------- #


def test_write_preview_downscales(tmp_path: Path) -> None:
    src = _png(tmp_path / "src.png", (2000, 1000))
    out = write_preview(src, tmp_path / "preview.png", max_dim=512)
    with Image.open(out) as im:
        assert max(im.size) <= 512
        assert im.size[0] / im.size[1] == pytest.approx(2.0, rel=0.05)


def test_write_preview_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises((OSError, ValueError)):
        write_preview(tmp_path / "nope.png", tmp_path / "preview.png")


# --------------------------------------------------------------------- #
# write() — full bundle assembly
# --------------------------------------------------------------------- #


def test_write_full_bundle_all_artifacts(tmp_path: Path) -> None:
    theme = _make_theme()
    wp_image = _png(tmp_path / "wp" / "32x24.png")
    out_dir = tmp_path / plugin_id(theme.name)

    bundle = write(
        theme,
        out_dir,
        color_scheme_stem="themey_Aliens",
        cursor_theme_name="themey_Aliens-cursors",
        default_wallpaper_id="themey_Aliens_bg",
        default_wallpaper_image=wp_image,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
    )

    assert isinstance(bundle, LookAndFeelBundle)
    assert bundle.id == plugin_id(theme.name)
    assert bundle.dir == out_dir
    assert (out_dir / "metadata.json").is_file()
    assert (out_dir / "contents" / "defaults").is_file()
    assert (out_dir / "contents" / "previews" / "preview.png").is_file()

    text = (out_dir / "contents" / "defaults").read_text()
    assert "[kdeglobals][General]" in text
    assert "ColorScheme=themey_Aliens" in text
    assert "[kcminputrc][Mouse]" in text
    assert "cursorTheme=themey_Aliens-cursors" in text
    assert "[Wallpaper]" in text
    assert "Image=themey_Aliens_bg" in text
    assert "[kwinrc][org.kde.kdecoration2]" in text
    assert f"theme={PLUGINS['legacy']}" not in text  # sanity: not swapped
    assert "theme=themey_Aliens" in text


def test_write_bundle_no_wallpaper_no_cursor_no_preview(tmp_path: Path) -> None:
    theme = _make_theme(name="Synthetic", display_name="Synthetic")
    out_dir = tmp_path / plugin_id(theme.name)

    write(
        theme,
        out_dir,
        color_scheme_stem="themey_Synthetic",
        cursor_theme_name=None,
        default_wallpaper_id=None,
        default_wallpaper_image=None,
        deco_library=PLUGINS["v2"],
        deco_theme="__aurorae__svg__Synthetic",
    )

    assert not (out_dir / "contents" / "previews").exists()
    text = (out_dir / "contents" / "defaults").read_text()
    assert "[kcminputrc][Mouse]" not in text
    assert "[Wallpaper]" not in text
    assert "[kdeglobals][General]" in text
    assert "[kwinrc][org.kde.kdecoration2]" in text


def test_write_bundle_preview_failure_is_non_fatal_and_notes(tmp_path: Path) -> None:
    theme = _make_theme(name="Broken", display_name="Broken")
    out_dir = tmp_path / plugin_id(theme.name)
    bad_image = tmp_path / "not-an-image.png"
    bad_image.write_text("not a png")

    bundle = write(
        theme,
        out_dir,
        color_scheme_stem="themey_Broken",
        cursor_theme_name=None,
        default_wallpaper_id="themey_Broken_bg",
        default_wallpaper_image=bad_image,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Broken",
    )

    assert bundle.dir == out_dir
    assert not (out_dir / "contents" / "previews").exists()
    assert (out_dir / "contents" / "defaults").is_file()
    assert any(n.startswith("bundle: preview.png skipped") for n in theme.notes)


def test_write_bundle_zero_symlinks(tmp_path: Path) -> None:
    theme = _make_theme()
    wp_image = _png(tmp_path / "wp2" / "32x24.png")
    out_dir = tmp_path / plugin_id(theme.name)
    write(
        theme,
        out_dir,
        color_scheme_stem="themey_Aliens",
        cursor_theme_name="themey_Aliens-cursors",
        default_wallpaper_id="themey_Aliens_bg",
        default_wallpaper_image=wp_image,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
    )
    assert not any(p.is_symlink() for p in out_dir.rglob("*"))


# --------------------------------------------------------------------- #
# Snapshots (D2)
# --------------------------------------------------------------------- #


def test_defaults_snapshot_all_artifacts(tmp_path: Path, snapshot) -> None:
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write(
        theme,
        out_dir,
        color_scheme_stem="themey_Aliens",
        cursor_theme_name="themey_Aliens-cursors",
        default_wallpaper_id="themey_Aliens_giger045",
        default_wallpaper_image=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
    )
    assert (out_dir / "contents" / "defaults").read_text() == snapshot


def test_lookandfeel_metadata_carries_scale(tmp_path: Path) -> None:
    """``X-Themey-Scale`` rides in the bundle metadata so ``apply`` can
    size the dragbar panel it creates (``scale_px(16)``) without a new
    artifact — the bundle is the file apply already opens."""
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write_metadata_json(theme, out_dir)
    meta = json.loads((out_dir / "metadata.json").read_text())
    assert meta["X-Themey-Scale"] == theme.scale
    theme15 = replace(theme, scale=1.5)
    write_metadata_json(theme15, out_dir)
    meta = json.loads((out_dir / "metadata.json").read_text())
    assert meta["X-Themey-Scale"] == 1.5


def test_metadata_snapshot_all_artifacts(tmp_path: Path, snapshot) -> None:
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write_metadata_json(theme, out_dir)
    assert (out_dir / "metadata.json").read_text() == snapshot


def test_defaults_snapshot_no_wallpaper_no_cursor(tmp_path: Path, snapshot) -> None:
    theme = _make_theme(name="Synthetic", display_name="Synthetic")
    out_dir = tmp_path / plugin_id(theme.name)
    write(
        theme,
        out_dir,
        color_scheme_stem="themey_Synthetic",
        cursor_theme_name=None,
        default_wallpaper_id=None,
        default_wallpaper_image=None,
        deco_library=PLUGINS["v2"],
        deco_theme="__aurorae__svg__Synthetic",
    )
    assert (out_dir / "contents" / "defaults").read_text() == snapshot


def test_metadata_snapshot_no_wallpaper_no_cursor(tmp_path: Path, snapshot) -> None:
    theme = _make_theme(name="Synthetic", display_name="Synthetic")
    out_dir = tmp_path / plugin_id(theme.name)
    write_metadata_json(theme, out_dir)
    assert (out_dir / "metadata.json").read_text() == snapshot


# --------------------------------------------------------------------- #
# --widget-style (WP4)
# --------------------------------------------------------------------- #


def test_widget_styles_map_tokens_to_qt_style_names() -> None:
    """The CLI's lowercase tokens spell the Qt style names KDE's own
    Look-and-Feel bundles put in ``[kdeglobals][KDE] widgetStyle``."""
    assert WIDGET_STYLES == {
        "windows": "Windows",
        "fusion": "Fusion",
        "breeze": "Breeze",
    }


def test_defaults_sections_widget_style_group() -> None:
    """``[kdeglobals][KDE] widgetStyle`` rides with the other kdeglobals
    groups, before kcminputrc."""
    sections = build_defaults_sections(
        color_scheme_stem="themey_Aliens",
        cursor_theme_name="themey_Aliens-cursors",
        default_wallpaper_id=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
        widget_style="windows",
    )
    assert list(sections) == [
        "kdeglobals][General",
        "kdeglobals][KDE",
        "kcminputrc][Mouse",
        "kwinrc][org.kde.kdecoration2",
    ]
    assert sections["kdeglobals][KDE"] == {"widgetStyle": "Windows"}


def test_defaults_sections_no_widget_style_group_by_default() -> None:
    """Default None = the application style is left alone, so no key at
    all (plasma-apply-lookandfeel applies the whole file)."""
    sections = build_defaults_sections(
        color_scheme_stem="themey_Aliens",
        cursor_theme_name=None,
        default_wallpaper_id=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
    )
    assert "kdeglobals][KDE" not in sections


def test_defaults_sections_widget_style_unknown_token_raises() -> None:
    with pytest.raises(ValueError, match="widget_style"):
        build_defaults_sections(
            color_scheme_stem=None,
            cursor_theme_name=None,
            default_wallpaper_id=None,
            deco_library=PLUGINS["legacy"],
            deco_theme="themey_X",
            widget_style="kvantum",
        )


def test_metadata_carries_widget_style_stamp(tmp_path: Path) -> None:
    """``X-Themey-WidgetStyle`` is the Qt style name apply reads back."""
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write_metadata_json(theme, out_dir, widget_style="fusion")
    meta = json.loads((out_dir / "metadata.json").read_text())
    assert meta["X-Themey-WidgetStyle"] == "Fusion"


def test_metadata_has_no_widget_style_stamp_by_default(tmp_path: Path) -> None:
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write_metadata_json(theme, out_dir)
    meta = json.loads((out_dir / "metadata.json").read_text())
    assert "X-Themey-WidgetStyle" not in meta


def test_write_bundle_threads_widget_style_into_both_files(tmp_path: Path) -> None:
    theme = _make_theme()
    out_dir = tmp_path / plugin_id(theme.name)
    write(
        theme,
        out_dir,
        color_scheme_stem=None,
        cursor_theme_name=None,
        default_wallpaper_id=None,
        default_wallpaper_image=None,
        deco_library=PLUGINS["legacy"],
        deco_theme="themey_Aliens",
        widget_style="breeze",
    )
    meta = json.loads((out_dir / "metadata.json").read_text())
    assert meta["X-Themey-WidgetStyle"] == "Breeze"
    defaults = (out_dir / "contents" / "defaults").read_text()
    assert "[kdeglobals][KDE]\nwidgetStyle=Breeze\n" in defaults
