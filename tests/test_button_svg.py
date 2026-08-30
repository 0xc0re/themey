"""Tests for button_svg.py — per-button SVGs with hover/pressed states."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image

SVG_NS = "http://www.w3.org/2000/svg"


def _make_tiny_png(tmp_path: Path, name: str = "btn.png") -> Path:
    p = tmp_path / name
    img = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    img.save(str(p), format="PNG")
    return p


def _make_theme(tmp_path: Path, button_codes: dict[str, str], left_buttons: str = "", right_buttons: str = ""):
    from themey.ir import BorderSpec, IClassSpec, Palette, Theme

    png = _make_tiny_png(tmp_path)
    iclasses = {}
    for iclass_name in button_codes:
        iclasses[iclass_name] = IClassSpec(
            name=iclass_name,
            edge_scaling=(2, 2, 2, 2),
            normal=png,
            normal_active=png,
            hilited=png,
            hilited_active=None,
            clicked=png,
            clicked_active=None,
            normal_sticky=None,
            normal_active_sticky=None,
        )

    return Theme(
        name="TestButtons",
        display_name="TestButtons",
        author=None,
        scale=1,
        asset_root=tmp_path,
        border=BorderSpec(
            name="DEFAULT",
            border_size_left=4,
            border_size_right=4,
            border_size_top=18,
            border_size_bottom=4,
            parts=(),
        ),
        iclasses=iclasses,
        tclasses={},
        button_codes=button_codes,
        left_buttons=left_buttons,
        right_buttons=right_buttons,
        palette=Palette(
            titlebar_active=(64, 64, 64),
            titlebar_inactive=(128, 128, 128),
            text_active=(255, 255, 255),
            text_inactive=(192, 192, 192),
        ),
    )


def _collect_ids(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    return {e.get("id") for e in root.iter() if e.get("id")}


def test_button_svg_close_written_when_X_in_codes(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(
        tmp_path, {"BUTTON_CLOSE": "X"}, left_buttons="X"
    )
    written = write_button_svgs(theme, tmp_path / "out")
    (tmp_path / "out").mkdir(exist_ok=True)
    written = write_button_svgs(theme, tmp_path / "out")
    assert (tmp_path / "out" / "close.svg").is_file()


def test_button_svg_maximize_and_restore_when_A_in_codes(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(
        tmp_path, {"BUTTON_MAXIMIZE": "A"}, left_buttons="A"
    )
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    write_button_svgs(theme, out)
    assert (out / "maximize.svg").is_file()
    assert (out / "restore.svg").is_file()


def test_button_svg_minimize_when_I(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(
        tmp_path, {"BUTTON_ICONIFY": "I"}, left_buttons="I"
    )
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    write_button_svgs(theme, out)
    assert (out / "minimize.svg").is_file()


def test_button_svg_alldesktops_when_S(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(
        tmp_path, {"BUTTON_STICK": "S"}, left_buttons="S"
    )
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    write_button_svgs(theme, out)
    assert (out / "alldesktops.svg").is_file()


def test_button_svg_shade_when_L(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(
        tmp_path, {"BUTTON_SHADE": "L"}, left_buttons="L"
    )
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    write_button_svgs(theme, out)
    assert (out / "shade.svg").is_file()


def test_button_svg_skipped_when_no_code(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(tmp_path, {}, left_buttons="", right_buttons="")
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    written = write_button_svgs(theme, out)
    # menu.svg is unconditional (kwinrc's default ButtonsOnLeft is "M");
    # nothing else should be written when the theme has no button codes.
    assert [p.name for p in written] == ["menu.svg"], written


def test_button_svg_uses_framesvg_prefixes(tmp_path: Path) -> None:
    """KSvg/FrameSvg requires 9-patch IDs like ``active-center``, ``hover-center``,
    ``pressed-center``. Aurorae's ``AuroraeButton.qml`` instantiates a
    ``KSvg.FrameSvg{ imagePath }`` per state and calls
    ``hasElementPrefix("active"|"hover"|"pressed"|...)`` — if the prefix
    isn't found, the per-state group has ``imagePath: ""`` and the button is
    hidden. We previously emitted bare IDs (close, close-hover, close-pressed)
    so every button rendered invisibly in real KWin.
    """
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(tmp_path, {"BUTTON_CLOSE": "X"}, left_buttons="X")
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    write_button_svgs(theme, out)
    ids = _collect_ids(out / "close.svg")
    assert "active-center" in ids, f"missing active-center prefix; ids={ids}"
    assert "hover-center" in ids, f"missing hover-center prefix; ids={ids}"
    assert "pressed-center" in ids, f"missing pressed-center prefix; ids={ids}"
    # Bare IDs (close, close-hover, close-pressed) match no FrameSvg prefix.
    assert "close" not in ids, f"bare id 'close' must not appear; ids={ids}"
    assert "close-hover" not in ids, f"legacy id 'close-hover' must not appear"
    assert "close-pressed" not in ids, f"legacy id 'close-pressed' must not appear"


def test_button_svg_each_has_hover_and_pressed_subelements(tmp_path: Path) -> None:
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(
        tmp_path, {"BUTTON_CLOSE": "X"}, left_buttons="X"
    )
    out = tmp_path / "out"
    out.mkdir(exist_ok=True)
    write_button_svgs(theme, out)
    ids = _collect_ids(out / "close.svg")
    # FrameSvg 9-patch prefixes for each state.
    assert "hover-center" in ids, f"missing hover-center; ids={ids}"
    assert "pressed-center" in ids, f"missing pressed-center; ids={ids}"


def test_button_svg_menu_written_for_M(tmp_path: Path) -> None:
    """Code M has no E16 iclass; a placeholder menu.svg must still exist so
    kwinrc ButtonsOnLeft=M renders something."""
    from themey.generate.button_svg import write_button_svgs

    theme = _make_theme(tmp_path, {}, left_buttons="M", right_buttons="")
    written = write_button_svgs(theme, tmp_path / "out")
    assert (tmp_path / "out" / "menu.svg") in written
    content = (tmp_path / "out" / "menu.svg").read_text()
    assert 'id="active-center"' in content
