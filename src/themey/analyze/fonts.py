"""``__FONTS`` blocks (fonts.theme.cfg / fonts.cfg) → FontSpec dict.

The main cfg lexer only tokenizes uppercase identifiers, so font aliases
(``font-default``) and TTF specs (``ariali/9``) would be silently dropped by
the normal parse path. This module therefore does a tolerant standalone text
scan of the fonts files instead of going through etheme/parse.py.

Contract: every returned FontSpec.ttf_path resolves inside asset_root
(T-05-01 idiom, same as iclasses.py) or is None. ``fonts.theme.cfg`` is
E16's preferred per-theme file; ``fonts.cfg`` is only read as a fallback
when the former is absent — matching E16's ThemeConfigFontsLoad order.

Entry value grammar (E16 text.c TextstateCreate):
- ``"name/size"``  → TTF loaded from <theme>/ttfonts/name.ttf. Also seen
  with an explicit .ttf suffix in a few corpus themes.
- ``"-foundry-family-…"`` (XLFD) → server-side font; no shippable file.
  Family is field 2; size is the pixel-size field, falling back to
  point-size/10 when pixel-size is a wildcard.

Family aliasing (``XLFD_FAMILY_ALIASES``): the corpus names X11 core
families a Plasma system does not carry. fontconfig itself aliases
helvetica/times/courier (→ Nimbus Sans/Roman/Mono PS, or Liberation), so
those pass through untouched; ``lucida`` (1360 corpus alias lines — B&H
Lucida, the humanist sans behind every second E16 title), ``fixed`` and
``lucidatypewriter`` (monospace bitmaps) and ``clean`` (a small bitmap
sans) have no fontconfig alias and fell to the default sans (Noto Sans).
They map to the DejaVu faces (Bitstream Vera, the same foundry lineage as
Lucida) or the generic family; Qt falls back to the default family when
DejaVu is absent. The authored name is kept in ``FontSpec.source_family``
and ``build_theme`` writes one ``fonts:`` note per distinct mapping.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from themey.ir import FontSpec

log = logging.getLogger(__name__)

FONTS_FILES: tuple[str, ...] = ("fonts.theme.cfg", "fonts.cfg")

# alias "value" — alias is any run of non-space, non-quote chars; tolerant of
# the lowercase/hyphen names the main lexer cannot represent.
_RE_ENTRY = re.compile(r'^\s*([A-Za-z0-9_.\-]+)\s+"([^"]*)"')
_RE_TTF_SPEC = re.compile(r"^([^/]+)/(\d+)$")

DEFAULT_SIZE = 10  # E16's fallback when a spec carries no usable size


def _ttf_family(path: Path) -> str | None:
    """Best-effort real family name from the TTF via Pillow."""
    try:
        from PIL import ImageFont

        return ImageFont.truetype(str(path)).getname()[0]
    except Exception:  # any font parse failure → fall back
        return None


def _resolve_ttf(name: str, asset_root: Path) -> Path | None:
    """Resolve a TTF basename against the theme tree, staying inside it."""
    root_resolved = str(asset_root.resolve())
    basenames = [name] if name.lower().endswith(".ttf") else [name + ".ttf", name]
    for base in basenames:
        for candidate in (asset_root / "ttfonts" / base, asset_root / base):
            target = candidate.resolve()
            if not (
                str(target) == root_resolved
                or str(target).startswith(root_resolved + "/")
            ):
                continue  # T-05-01: path escapes asset_root
            if target.is_file():
                return target
    return None


_BOLD_WEIGHTS = frozenset({"bold", "demibold", "semibold", "black", "heavy", "strong"})

#: X11 core family (lowercase) → fontconfig family. See the module
#: docstring; families fontconfig already aliases are deliberately absent.
XLFD_FAMILY_ALIASES: dict[str, str] = {
    "lucida": "DejaVu Sans",
    "lucidatypewriter": "DejaVu Sans Mono",
    "fixed": "DejaVu Sans Mono",
    "clean": "sans-serif",
}


def alias_family(family: str | None) -> tuple[str | None, str | None]:
    """``(family to use, authored family or None)`` per ``XLFD_FAMILY_ALIASES``
    (case-insensitive, whitespace-trimmed)."""
    if family is None:
        return None, None
    mapped = XLFD_FAMILY_ALIASES.get(family.strip().lower())
    if mapped is None or mapped == family:
        return family, None
    return mapped, family


def _parse_xlfd(alias: str, value: str) -> FontSpec:
    fields = value.split("-")
    # ['-family-…'] splits to ['', foundry, family, weight, slant, setwidth,
    #  addstyle, pixel, point, …]
    family = fields[2] if len(fields) > 2 and fields[2] not in ("", "*") else None
    weight = fields[3].lower() if len(fields) > 3 else ""
    slant = fields[4].lower() if len(fields) > 4 else ""
    size = DEFAULT_SIZE
    points = False
    if len(fields) > 7 and fields[7].isdigit():
        size = int(fields[7])
    elif len(fields) > 8 and fields[8].isdigit():
        size = max(1, int(fields[8]) // 10)
        points = True
    family, source_family = alias_family(family)
    return FontSpec(
        alias=alias, ttf_path=None, family=family, size=size, points=points,
        bold=weight in _BOLD_WEIGHTS, italic=slant in ("i", "o"),
        source_family=source_family,
    )


_RE_XFT = re.compile(r"^xft:\s*([^:\-]+?)(?:-(\d+))?((?::[A-Za-z]+)*)\s*$", re.I)


def _parse_xft(alias: str, value: str) -> FontSpec | None:
    """``xft:family-size:style:...`` (XftFontOpenName pattern; 3 corpus
    themes): size in points, ``:bold``/``:italic``/``:oblique`` flags."""
    m = _RE_XFT.match(value)
    if m is None:
        return None
    family, source_family = alias_family(m.group(1).strip())
    size = int(m.group(2)) if m.group(2) else DEFAULT_SIZE
    flags = {f.lower() for f in m.group(3).split(":") if f}
    return FontSpec(
        alias=alias, ttf_path=None, family=family, size=size, points=True,
        bold="bold" in flags, italic=bool(flags & {"italic", "oblique"}),
        source_family=source_family,
    )


def parse_fonts(asset_root: Path) -> dict[str, FontSpec]:
    """Parse the theme's font aliases. Returns {} when no fonts file exists."""
    for filename in FONTS_FILES:
        path = asset_root / filename
        if path.is_file():
            return _parse_file(path, asset_root)
    return {}


def _parse_file(path: Path, asset_root: Path) -> dict[str, FontSpec]:
    out: dict[str, FontSpec] = {}
    in_fonts = False
    for line in path.read_text(encoding="utf-8", errors="replace").split("\n"):
        stripped = line.strip()
        if "__FONTS" in stripped:
            in_fonts = True
            continue
        if stripped.startswith("__END"):
            in_fonts = False
            continue
        if not in_fonts:
            continue
        m = _RE_ENTRY.match(line)
        if m is None:
            continue
        alias, value = m.group(1), m.group(2)
        if value.startswith("-"):
            out[alias] = _parse_xlfd(alias, value)
            continue
        if value.lower().startswith("xft:"):
            xft = _parse_xft(alias, value)
            if xft is not None:
                out[alias] = xft
                continue
        tm = _RE_TTF_SPEC.match(value)
        if tm is not None:
            name, size = tm.group(1), int(tm.group(2))
        else:
            name, size = value, DEFAULT_SIZE
        ttf = _resolve_ttf(name, asset_root)
        if ttf is None:
            log.debug("fonts: %s -> %r has no resolvable TTF", alias, value)
        family = _ttf_family(ttf) if ttf is not None else None
        out[alias] = FontSpec(
            alias=alias,
            ttf_path=ttf,
            family=family or Path(name).stem,
            size=size,
            points=True,  # Imlib2: FT_Set_Char_Size at 96 dpi
        )
    return out
