"""Top-level Aurorae generator orchestrator.

Calls the four sub-generators in order:
  1. ``decoration.svg``         — 9-patch FrameSvg with 18 IDs (Pitfall 5)
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

# 18 FrameSvg IDs verbatim — Pitfall 5.
# Aurorae's FrameSvg renderer matches by literal id with ``decoration-`` prefix.
# 9 active + 9 inactive = 18. Maximized variants omitted (Edna works without them).
REQUIRED_FRAMESVG_IDS: tuple[str, ...] = (
    "decoration-topleft",
    "decoration-top",
    "decoration-topright",
    "decoration-left",
    "decoration-center",
    "decoration-right",
    "decoration-bottomleft",
    "decoration-bottom",
    "decoration-bottomright",
    "decoration-inactive-topleft",
    "decoration-inactive-top",
    "decoration-inactive-topright",
    "decoration-inactive-left",
    "decoration-inactive-center",
    "decoration-inactive-right",
    "decoration-inactive-bottomleft",
    "decoration-inactive-bottom",
    "decoration-inactive-bottomright",
)


def write(theme: Theme, out_dir: Path) -> list[Path]:
    """Write the full Aurorae theme tree under ``out_dir``.

    Files written:
      - ``decoration.svg``               (FrameSvg with 18 IDs + hint margins)
      - ``<theme.name>rc``               (INI: [General] + [Layout])
      - ``metadata.desktop``             (Aurorae plugin metadata)
      - ``metadata.json``                (KF6-friendly metadata)
      - ``close.svg`` / ``maximize.svg`` / ``restore.svg`` / ``minimize.svg`` (always if X/A/I)
      - ``shade.svg`` / ``alldesktops.svg`` / ``keepabove.svg`` / ``keepbelow.svg`` (when L/S/F/B)

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
