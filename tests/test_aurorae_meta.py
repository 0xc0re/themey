"""Tests for aurorae_meta.py — metadata.desktop + metadata.json writers."""
from __future__ import annotations

import json
from pathlib import Path


def _make_minimal_theme(name: str = "Aliens"):
    from themey.ir import BorderSpec, Palette, Theme

    return Theme(
        name=name,
        display_name=name,
        author="testauthor",
        scale=2,
        asset_root=Path("/tmp/x"),
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4,
            border_size_right=4,
            border_size_top=18,
            border_size_bottom=4,
            parts=(),
        ),
        iclasses={},
        tclasses={},
        button_codes={},
        left_buttons="XAI",
        right_buttons="",
        palette=Palette(
            titlebar_active=(64, 64, 64),
            titlebar_inactive=(128, 128, 128),
            text_active=(255, 255, 255),
            text_inactive=(192, 192, 192),
        ),
    )


def test_metadata_desktop_kde_plugin_info_name_matches_folder(tmp_path: Path) -> None:
    from themey.generate.aurorae_meta import write_metadata_desktop

    theme = _make_minimal_theme(name="Aliens")
    out = write_metadata_desktop(theme, tmp_path)
    assert out.is_file()
    content = out.read_text()
    assert "X-KDE-PluginInfo-Name=Aliens" in content


def test_metadata_desktop_has_required_keys(tmp_path: Path) -> None:
    from themey.generate.aurorae_meta import write_metadata_desktop

    theme = _make_minimal_theme()
    out = write_metadata_desktop(theme, tmp_path)
    content = out.read_text()
    for key in (
        "Name=",
        "X-KDE-PluginInfo-Author=",
        "X-KDE-PluginInfo-Name=",
        "X-KDE-PluginInfo-Version=",
    ):
        assert key in content, f"Missing required key: {key}"


def test_metadata_json_kpackage_structure(tmp_path: Path) -> None:
    from themey.generate.aurorae_meta import write_metadata_json

    theme = _make_minimal_theme()
    out = write_metadata_json(theme, tmp_path)
    assert out.is_file()
    data = json.loads(out.read_text())
    assert data["KPackageStructure"] == "KWin/Aurorae"
    assert data["KPlugin"]["ServiceTypes"] == ["KWin/Aurorae"]


def test_metadata_json_kplugin_id_matches_folder(tmp_path: Path) -> None:
    from themey.generate.aurorae_meta import write_metadata_json

    theme = _make_minimal_theme(name="Aliens")
    out = write_metadata_json(theme, tmp_path)
    data = json.loads(out.read_text())
    assert data["KPlugin"]["Id"] == "Aliens"


def test_metadata_json_authors_field(tmp_path: Path) -> None:
    from themey.generate.aurorae_meta import write_metadata_json

    theme = _make_minimal_theme()
    out = write_metadata_json(theme, tmp_path)
    data = json.loads(out.read_text())
    authors = data["KPlugin"]["Authors"]
    assert isinstance(authors, list)
    assert len(authors) >= 1
    assert "Name" in authors[0]
