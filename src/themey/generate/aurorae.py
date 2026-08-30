"""Top-level Aurorae generator orchestrator.

Calls the four sub-generators in order:
  1. ``decoration.svg``         — 9-patch FrameSvg with 36 IDs (Pitfall 5)
  2. ``<name>rc``               — INI [General] + [Layout]
  3. ``metadata.desktop`` / ``metadata.json``  — both, per RESEARCH A8
  4. per-button SVGs            — close, maximize, restore, minimize, etc.

This is the single-import contract for Plan 09 (CLI pipeline)::

    from themey.generate.aurorae import write as write_aurorae
"""
from __future__ import annotations

from pathlib import Path

from themey.ir import Theme

from .aurorae_meta import write_metadata_desktop, write_metadata_json
from .aurorae_rc import write_aurorae_rc
from .button_svg import write_button_svgs
from .decoration_svg import write_decoration_svg

_SIDES = (
    "topleft", "top", "topright",
    "left", "center", "right",
    "bottomleft", "bottom", "bottomright",
)

# 36 FrameSvg IDs verbatim — Pitfall 5.
# Aurorae's FrameSvg renderer matches by literal id with ``decoration-`` prefix.
# 9 x {active, inactive, maximized, maximized-inactive}. Without the
# maximized groups Aurorae renders a blank title bar on maximized windows.
REQUIRED_FRAMESVG_IDS: tuple[str, ...] = tuple(
    f"{prefix}-{side}"
    for prefix in (
        "decoration",
        "decoration-inactive",
        "decoration-maximized",
        "decoration-maximized-inactive",
    )
    for side in _SIDES
)


def write(theme: Theme, out_dir: Path) -> list[Path]:
    """Write the full Aurorae theme tree under ``out_dir``.

    Files written:
      - ``decoration.svg``               (FrameSvg with 36 IDs + hint rects)
      - ``<theme.name>rc``               (INI: [General] + [Layout])
      - ``metadata.desktop``             (Aurorae plugin metadata)
      - ``metadata.json``                (KF6-friendly metadata)
      - ``close.svg`` / ``maximize.svg`` / ``restore.svg`` / ``minimize.svg`` (always if X/A/I)
      - ``shade.svg`` / ``alldesktops.svg`` / ``keepabove.svg`` / ``keepbelow.svg`` (when L/S/F/B)
      - ``menu.svg``                     (always — kwinrc ButtonsOnLeft usually has M)

    Args:
        theme: Frozen Theme IR.
        out_dir: Destination directory. Created if absent.

    Returns:
        List of all files actually created.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    files: list[Path] = []
    files.append(write_decoration_svg(theme, out_dir))
    files.append(write_aurorae_rc(theme, out_dir))
    files.append(write_metadata_desktop(theme, out_dir))
    files.append(write_metadata_json(theme, out_dir))
    files.extend(write_button_svgs(theme, out_dir))
    return files
