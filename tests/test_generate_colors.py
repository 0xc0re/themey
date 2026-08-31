"""Tests for themey.generate.colors — the KColorScheme .colors emitter.

The format census here is byte-verified against an installed Breeze scheme
(/usr/share/color-schemes/BreezeLight.colors): exactly 13 groups, 12
identical keys in every ``Colors:*`` group, exactly 6 in ``[WM]``, values
``R,G,B`` with no spaces, and the literal nested section
``[Colors:Header][Inactive]``.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
SNAPSHOT_THEMES = ("Aliens", "e13")

EXPECTED_GROUPS = [
    "ColorEffects:Disabled",
    "ColorEffects:Inactive",
    "Colors:Button",
    "Colors:Complementary",
    "Colors:Header",
    "Colors:Header][Inactive",
    "Colors:Selection",
    "Colors:Tooltip",
    "Colors:View",
    "Colors:Window",
    "General",
    "KDE",
    "WM",
]

COLORS_GROUP_KEYS = [
    "BackgroundAlternate",
    "BackgroundNormal",
    "DecorationFocus",
    "DecorationHover",
    "ForegroundActive",
    "ForegroundInactive",
    "ForegroundLink",
    "ForegroundNegative",
    "ForegroundNeutral",
    "ForegroundNormal",
    "ForegroundPositive",
    "ForegroundVisited",
]

WM_KEYS = [
    "activeBackground",
    "activeBlend",
    "activeForeground",
    "inactiveBackground",
    "inactiveBlend",
    "inactiveForeground",
]

_SECTION_RE = re.compile(r"^\[(.+)\]$")


def _parse(text: str) -> dict[str, dict[str, str]]:
    """Read the emitted file the way the census describes it.

    Deliberately not configparser: ``[Colors:Header][Inactive]`` is one
    section name with a literal bracket in it, which configparser's regex
    would mangle.
    """
    out: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if not line.strip():
            continue
        m = _SECTION_RE.match(line)
        if m:
            current = {}
            out[m.group(1)] = current
            continue
        assert current is not None, f"key line before any section: {line!r}"
        key, _, value = line.partition("=")
        current[key] = value
    return out


def _theme(name: str):
    from themey.analyze.build_theme import build_theme
    from themey.etheme.archive import extract
    from themey.etheme.parse import parse_tree

    with extract(FIXTURES / f"{name}.etheme") as raw:
        return build_theme(
            raw.asset_root,
            parse_tree(raw.asset_root),
            name=name,
            display_name=name,
            scale=2,
        )


def _synthetic_theme():
    """A hand-built Theme whose scheme is the neutral fallback."""
    from themey.analyze.colors import default_scheme, palette_from_scheme
    from themey.ir import BorderSpec, Theme

    scheme = default_scheme()
    return Theme(
        name="Synthetic",
        display_name="Synthetic",
        author=None,
        scale=2,
        asset_root=Path("/nonexistent"),
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
        left_buttons="",
        right_buttons="",
        palette=palette_from_scheme(scheme),
        scheme=scheme,
    )


# --------------------------------------------------------------------- #
# Structural census
# --------------------------------------------------------------------- #


def test_group_census(tmp_path: Path) -> None:
    from themey.generate.colors import write_colors

    out = write_colors(_synthetic_theme(), tmp_path / "s.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    assert list(parsed) == EXPECTED_GROUPS
    assert len(parsed) == 13


def test_every_colors_group_has_the_same_twelve_keys(tmp_path: Path) -> None:
    from themey.generate.colors import write_colors

    out = write_colors(_synthetic_theme(), tmp_path / "s.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    groups = [g for g in parsed if g.startswith("Colors:")]
    assert len(groups) == 8
    for group in groups:
        assert sorted(parsed[group]) == COLORS_GROUP_KEYS, group


def test_wm_group_has_exactly_six_keys(tmp_path: Path) -> None:
    from themey.generate.colors import write_colors

    out = write_colors(_synthetic_theme(), tmp_path / "s.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    assert sorted(parsed["WM"]) == WM_KEYS


def test_color_values_are_rgb_without_spaces(tmp_path: Path) -> None:
    from themey.generate.colors import write_colors

    out = write_colors(_synthetic_theme(), tmp_path / "s.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    for group in [g for g in parsed if g.startswith("Colors:")] + ["WM"]:
        for key, value in parsed[group].items():
            assert re.fullmatch(r"\d{1,3},\d{1,3},\d{1,3}", value), f"{group}/{key}={value}"


def test_general_section_names_the_scheme_stem(tmp_path: Path) -> None:
    from themey.generate.colors import write_colors

    theme = _synthetic_theme()
    out = write_colors(theme, tmp_path / "themey_Synthetic.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    # KDE matches the scheme by its [General] ColorScheme value, which must
    # equal the file stem or System Settings shows a duplicate entry.
    assert parsed["General"]["ColorScheme"] == "themey_Synthetic"
    assert out.stem == parsed["General"]["ColorScheme"]
    assert "(themey)" in parsed["General"]["Name"]
    assert "Synthetic" in parsed["General"]["Name"]


def test_semantic_colors_are_breeze_stock(tmp_path: Path) -> None:
    """Link/Visited/Negative/Neutral/Positive must not take the theme's cast."""
    from themey.generate.colors import BREEZE_SEMANTIC, write_colors

    out = write_colors(_theme("Aliens"), tmp_path / "a.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    for key, value in BREEZE_SEMANTIC.items():
        assert parsed["Colors:Window"][key] == "{},{},{}".format(*value)


def test_scheme_reflects_the_sampled_theme(tmp_path: Path) -> None:
    from themey.generate.colors import write_colors

    theme = _theme("Aliens")
    out = write_colors(theme, tmp_path / "a.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    assert theme.scheme is not None
    assert parsed["WM"]["activeBackground"] == "{},{},{}".format(
        *theme.scheme.wm_active_background
    )
    assert parsed["Colors:Window"]["BackgroundNormal"] == "{},{},{}".format(
        *theme.scheme.window.background_normal
    )
    # activeBlend mirrors activeBackground, as Breeze's own schemes do.
    assert parsed["WM"]["activeBlend"] == parsed["WM"]["activeBackground"]


def test_theme_without_a_scheme_falls_back(tmp_path: Path) -> None:
    """A hand-built Theme (scheme=None) still emits a complete valid file."""
    import dataclasses

    from themey.generate.colors import write_colors

    theme = dataclasses.replace(_synthetic_theme(), scheme=None)
    out = write_colors(theme, tmp_path / "n.colors")
    parsed = _parse(out.read_text(encoding="utf-8"))
    assert list(parsed) == EXPECTED_GROUPS


# --------------------------------------------------------------------- #
# Snapshots
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("name", SNAPSHOT_THEMES)
def test_colors_snapshot(name: str, tmp_path: Path, snapshot) -> None:
    from themey.generate.colors import write_colors

    out = write_colors(_theme(name), tmp_path / f"{name}.colors")
    assert out.read_text(encoding="utf-8") == snapshot


def test_synthetic_colors_snapshot(tmp_path: Path, snapshot) -> None:
    from themey.generate.colors import write_colors

    out = write_colors(_synthetic_theme(), tmp_path / "Synthetic.colors")
    assert out.read_text(encoding="utf-8") == snapshot
