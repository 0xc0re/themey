"""Frozen IR — the only contract crossing the analyze/generate seam.

All types in this module are frozen dataclasses. Code on the analyze side
populates them; code on the generate side reads them. The only mutable
accumulator is ``Theme.notes`` (a ``list[str]``), which exists specifically
so analysis-stage code can append fidelity notes that ``report.py`` and
``preview.py`` later read.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Palette:
    """Sampled dominant colors from the theme imagery."""

    titlebar_active: tuple[int, int, int]  # RGB 0-255
    titlebar_inactive: tuple[int, int, int]
    text_active: tuple[int, int, int]
    text_inactive: tuple[int, int, int]


@dataclass(frozen=True)
class IClassSpec:
    """E16 image class — one border-region image with up to 8 state variants."""

    name: str  # e.g. "TITLE_BAR_HORIZONTAL"
    edge_scaling: tuple[int, int, int, int]  # (left, right, top, bottom) from __EDGE_SCALING
    normal: Path | None  # path under asset_root, may be None
    normal_active: Path | None
    hilited: Path | None
    hilited_active: Path | None
    clicked: Path | None
    clicked_active: Path | None
    normal_sticky: Path | None
    normal_active_sticky: Path | None


@dataclass(frozen=True)
class TClassSpec:
    """E16 text class — titlebar text style per state."""

    name: str  # e.g. "TEXT1"
    fg_normal: tuple[int, int, int] | None  # __FORGROUND_COLOR after __NORMAL
    fg_active: tuple[int, int, int] | None  # __FORGROUND_COLOR after __NORMAL_ACTIVE


@dataclass(frozen=True)
class ButtonPart:
    """One button within a border — position encoded in E16's hybrid pct+abs coordinate."""

    iclass_name: str
    aclass: str | None  # null sentinel when E16 source omits __ACLASS
    tl_x_pct: int  # Q10 fixed-point: 1024 == 100%
    tl_x_abs: int  # signed; may be negative
    tl_y_pct: int
    tl_y_abs: int
    br_x_pct: int
    br_x_abs: int
    br_y_pct: int
    br_y_abs: int


@dataclass(frozen=True)
class BorderSpec:
    """One E16 border definition (DEFAULT, BORDERLESS, DIALOG, …)."""

    name: str  # "DEFAULT" only in Phase 1; others SKIPPED
    border_size_left: int
    border_size_right: int
    border_size_top: int
    border_size_bottom: int
    parts: tuple[ButtonPart, ...]


@dataclass(frozen=True)
class Theme:
    """Complete analyzed representation of one E16 theme.

    Frozen except for ``notes``, which is intentionally mutable so that
    analysis-stage code can accumulate fidelity warnings without violating
    the frozen contract on all other fields.
    """

    name: str  # slug from filename, e.g. "Aliens"
    display_name: str  # human label, may equal name
    author: str | None
    scale: int  # 1, 2, or 3
    asset_root: Path  # extracted tmpdir; valid only during convert()
    border: BorderSpec
    iclasses: dict[str, IClassSpec]  # by IClass name
    tclasses: dict[str, TClassSpec]
    button_codes: dict[str, str]  # part.iclass_name -> "X"|"A"|"I"|"L"|"S"
    left_buttons: str  # final Aurorae LeftButtons string, e.g. "XAI"
    right_buttons: str
    palette: Palette
    notes: list[str] = field(default_factory=list)  # ONLY mutable accumulator
    skipped_borders: tuple[str, ...] = ()
