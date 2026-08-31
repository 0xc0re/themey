"""KColorScheme ``.colors`` writer.

The contract this module satisfies is the file census, byte-verified
against an installed Breeze scheme (``/usr/share/color-schemes/
BreezeLight.colors``) — KDE's Colors KCM is unforgiving about a partial
file, so we emit the full shape every time:

* exactly **13 groups**: 2 ``ColorEffects:*``, 8 ``Colors:*``, plus
  ``General``, ``KDE`` and ``WM``;
* the same **12 keys in every** ``Colors:*`` group — a group missing a key
  silently inherits it from whatever scheme was previously active;
* exactly **6 keys** in ``[WM]``;
* values are ``R,G,B`` with **no spaces**;
* ``[General] ColorScheme`` must equal the installed file's stem, or
  System Settings lists the scheme twice and applies neither reliably.

One group header is literally ``[Colors:Header][Inactive]``. That is a
single section name containing a bracket, not two sections — which is why
this writer uses ``desktop_writer.write_desktop`` (section strings written
verbatim) rather than ``configparser``, whose section regex would mangle
it.

Two families of color come from outside the theme:

* ``ForegroundLink``/``Visited``/``Negative``/``Neutral``/``Positive`` and
  both ``ColorEffects`` groups are **Breeze stock, verbatim**. They are
  semantic — "this is an error", "this link is unvisited" — so tinting
  them to a 2009 window border would make them lie. Sampled colors stop at
  backgrounds, foregrounds, and the accent (see ``analyze/colors.py``).
* ``[KDE] contrast=4`` is Breeze's value and KDE's default.
"""
from __future__ import annotations

from pathlib import Path

from themey.analyze.colors import default_scheme
from themey.generate.desktop_writer import write_desktop
from themey.ir import ColorGroup, ColorScheme, Theme
from themey.slug import plugin_id

RGB = tuple[int, int, int]

# Semantic foregrounds, copied verbatim from the [Colors:Window] group of
# /usr/share/color-schemes/BreezeLight.colors (Plasma 6.6.6).
BREEZE_SEMANTIC: dict[str, RGB] = {
    "ForegroundLink": (41, 128, 185),
    "ForegroundNegative": (218, 68, 83),
    "ForegroundNeutral": (246, 116, 0),
    "ForegroundPositive": (39, 174, 96),
    "ForegroundVisited": (155, 89, 182),
}

# Both ColorEffects groups verbatim from the same file. These are numeric
# effect parameters rather than colors, so there is nothing to sample.
BREEZE_COLOR_EFFECTS: dict[str, dict[str, str]] = {
    "ColorEffects:Disabled": {
        "Color": "56,56,56",
        "ColorAmount": "0",
        "ColorEffect": "0",
        "ContrastAmount": "0.65",
        "ContrastEffect": "1",
        "IntensityAmount": "0.1",
        "IntensityEffect": "2",
    },
    "ColorEffects:Inactive": {
        "ChangeSelectionColor": "true",
        "Color": "112,111,110",
        "ColorAmount": "0.025",
        "ColorEffect": "2",
        "ContrastAmount": "0.1",
        "ContrastEffect": "2",
        "Enable": "false",
        "IntensityAmount": "0",
        "IntensityEffect": "0",
    },
}

# KDE's default contrast setting, as Breeze ships it.
KDE_CONTRAST: str = "4"

# Section name for the nested Header-Inactive group. write_desktop writes
# section strings verbatim, so the closing bracket of "[Colors:Header]" and
# the opening of "[Inactive]" live inside the name itself.
HEADER_INACTIVE_SECTION: str = "Colors:Header][Inactive"


def scheme_stem(theme: Theme) -> str:
    """``themey_<slug>`` — the ``.colors`` stem and ``ColorScheme`` value.

    Same string as the QML decoration package's KPlugin Id, in a different
    namespace; see the naming contract in CLAUDE.md.
    """
    return plugin_id(theme.name)


def _rgb(value: RGB) -> str:
    return f"{value[0]},{value[1]},{value[2]}"


def _group_entries(group: ColorGroup) -> dict[str, str]:
    """The 12 keys of one ``[Colors:*]`` group, in Breeze's key order."""
    entries = {
        "BackgroundAlternate": _rgb(group.background_alternate),
        "BackgroundNormal": _rgb(group.background_normal),
        "DecorationFocus": _rgb(group.decoration_focus),
        "DecorationHover": _rgb(group.decoration_hover),
        "ForegroundActive": _rgb(group.foreground_active),
        "ForegroundInactive": _rgb(group.foreground_inactive),
    }
    entries.update({k: _rgb(v) for k, v in BREEZE_SEMANTIC.items()})
    entries["ForegroundNormal"] = _rgb(group.foreground_normal)
    return dict(sorted(entries.items()))


def build_sections(
    scheme: ColorScheme, *, stem: str, display_name: str
) -> dict[str, dict[str, str]]:
    """Assemble the full 13-group section map, in Breeze's group order."""
    sections: dict[str, dict[str, str]] = dict(BREEZE_COLOR_EFFECTS)
    sections["Colors:Button"] = _group_entries(scheme.button)
    sections["Colors:Complementary"] = _group_entries(scheme.complementary)
    sections["Colors:Header"] = _group_entries(scheme.header)
    sections[HEADER_INACTIVE_SECTION] = _group_entries(scheme.header_inactive)
    sections["Colors:Selection"] = _group_entries(scheme.selection)
    sections["Colors:Tooltip"] = _group_entries(scheme.tooltip)
    sections["Colors:View"] = _group_entries(scheme.view)
    sections["Colors:Window"] = _group_entries(scheme.window)
    sections["General"] = {
        "ColorScheme": stem,
        "Name": f"{display_name} (themey)",
        "shadeSortColumn": "true",
    }
    sections["KDE"] = {"contrast": KDE_CONTRAST}
    # activeBlend/inactiveBlend mirror their backgrounds, as every stock
    # Breeze scheme does — the blend is a legacy gradient endpoint and a
    # different value paints a gradient E16 never had.
    sections["WM"] = {
        "activeBackground": _rgb(scheme.wm_active_background),
        "activeBlend": _rgb(scheme.wm_active_background),
        "activeForeground": _rgb(scheme.wm_active_foreground),
        "inactiveBackground": _rgb(scheme.wm_inactive_background),
        "inactiveBlend": _rgb(scheme.wm_inactive_background),
        "inactiveForeground": _rgb(scheme.wm_inactive_foreground),
    }
    return sections


def write_colors(theme: Theme, out_path: Path) -> Path:
    """Write *theme*'s color scheme to *out_path*; returns *out_path*.

    ``out_path``'s stem must be :func:`scheme_stem` — KDE matches the
    scheme by ``[General] ColorScheme``, which this writer sets from that
    helper rather than from the filename.
    """
    scheme = theme.scheme if theme.scheme is not None else default_scheme()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_desktop(
        out_path,
        build_sections(
            scheme, stem=scheme_stem(theme), display_name=theme.display_name
        ),
    )
    return out_path
