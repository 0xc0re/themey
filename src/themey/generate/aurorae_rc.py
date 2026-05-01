"""Aurorae <name>rc INI writer.

``RawConfigParser`` preserves ``%`` characters in values (some KDE color values
use ``%`` in font names via ``BasicInterpolation``). The subclass form
``optionxform = staticmethod(str)`` preserves KDE's case-sensitive keys
(``LeftButtons``, ``BackgroundNormal``, etc.) without tripping pyright basic's
"cannot assign method to instance" error that the bare ``cp.optionxform = str``
form raises.

Layout numerical mapping:

    BorderLeft  = border_size_left * scale
    PaddingLeft = border_size_left * scale * 2  (FrameSvg shadow padding)
    TitleHeight = max(15, border_size_top - 4 * scale)

These are Open Question A2 from 01-RESEARCH.md — visual-gate-tunable. The
formula block is isolated in ``_layout_values`` so Plan 09's visual gate can
adjust a single function without touching callers.
"""
from __future__ import annotations

import configparser
from pathlib import Path

from themey.ir import Theme


def _format_color_rgba(rgb: tuple[int, int, int]) -> str:
    """Format RGB tuple as ``R,G,B,255`` (full alpha, 4-tuple)."""
    return f"{rgb[0]},{rgb[1]},{rgb[2]},255"


def _layout_values(theme: Theme) -> dict[str, str]:
    """Compute the [Layout] section from Theme border sizes and scale.

    All values are scaled uniformly by ``theme.scale``. The formula matches
    the Edna reference layout with scale=1 as the baseline.

    Tunable formula block (Open Question A2 — adjust here for visual gate):
    """
    s = theme.scale
    bl = theme.border.border_size_left * s
    br = theme.border.border_size_right * s
    bt = theme.border.border_size_top * s
    bb = theme.border.border_size_bottom * s
    return {
        "BorderLeft": str(bl),
        "BorderRight": str(br),
        "BorderBottom": str(bb),
        "BorderTop": str(bt),
        "TitleEdgeTop": str(2 * s),
        "TitleEdgeBottom": str(2 * s),
        "TitleEdgeLeft": str(4 * s),
        "TitleEdgeRight": str(4 * s),
        "TitleBorderLeft": str(2 * s),
        "TitleBorderRight": str(2 * s),
        "TitleHeight": str(max(15, bt - 4 * s)),
        "ButtonWidth": str(12 * s),
        "ButtonHeight": str(12 * s),
        "ButtonSpacing": str(4 * s),
        "ButtonMarginTop": str(2 * s),
        "ButtonMarginLeft": str(3 * s),
        "ExplicitButtonSpacer": "0",
        "PaddingTop": str(bt * 2),
        "PaddingBottom": str(bb * 2),
        "PaddingLeft": str(bl * 2),
        "PaddingRight": str(br * 2),
    }


class _CaseSensitiveRawConfigParser(configparser.RawConfigParser):
    """RawConfigParser subclass that preserves key case verbatim.

    KDE reads keys like ``LeftButtons`` and ``BackgroundNormal`` case-
    sensitively. The default ``optionxform = str.lower`` silently mangles them.

    Pyright basic flags the bare ``cp.optionxform = str`` form as
    "cannot assign method to instance"; the class-level ``staticmethod``
    form is the canonical fix from the configparser docs.
    """

    optionxform = staticmethod(str)  # type: ignore[assignment]


def write_aurorae_rc(theme: Theme, out_dir: Path) -> Path:
    """Write ``<theme.name>rc`` INI file into ``out_dir``.

    Follows the ``Ednarc`` format exactly: ``[General]`` + ``[Layout]`` sections,
    ``space_around_delimiters=False`` so KDE's parser sees ``Key=Value``.

    Args:
        theme: Frozen Theme IR.
        out_dir: Directory to write into. Created if absent.

    Returns:
        Path to the written ``<name>rc`` file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cp = _CaseSensitiveRawConfigParser()

    cp["General"] = {
        "ActiveTextColor": _format_color_rgba(theme.palette.text_active),
        "InactiveTextColor": _format_color_rgba(theme.palette.text_inactive),
        "TitleAlignment": "Center",
        "TitleVerticalAlignment": "Center",
        "UseTextShadow": "true",
        "ActiveTextShadowColor": "0,0,0,255",
        "InactiveTextShadowColor": "0,0,0,255",
        "TextShadowOffsetX": "0",
        "TextShadowOffsetY": "1",
        "LeftButtons": theme.left_buttons,
        "RightButtons": theme.right_buttons,
        "Shadow": "true",
        "Animation": "1",
    }
    cp["Layout"] = _layout_values(theme)

    out_path = out_dir / f"{theme.name}rc"
    with open(out_path, "w", encoding="utf-8") as f:
        cp.write(f, space_around_delimiters=False)
    return out_path
