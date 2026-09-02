#!/usr/bin/env python3
"""Corpus-wide audit of the Kickoff highlight: MENU_SEL's tile decision and
the Selection / View colours the Plasma Style derives from it.

``generate/plasmastyle.build_viewitem`` decides per theme whether a
rectangular MENU_SEL strip's middle is REPEATED (grain the art would lose
under a stretch) or STRETCHED (a gradient that bands or seams when
repeated). One theme's screenshot cannot calibrate that: this walks every
``.etheme`` in the corpus, prints the three band measurements per state,
and flags every theme whose decision differs between the pre-2026-09-01
classifier (raw within-row spread vs row drift) and the current one
(residual grain vs drift on BOTH axes). It also reports the Selection
background before/after it moved from the hover art to the pressed art,
and the View background before/after it started following the popup
surface.

Nothing is installed and nothing is written outside ``--out``: each
archive is extracted to a temp dir, parsed and built into an ``ir.Theme``,
and the measurements are read straight off the art.

Usage:
    uv run python scripts/audit_viewitem.py --out DIR [--corpus DIR]
        [--only NAME ...] [--limit N] [--no-sheet]

Output (under --out):
    viewitem.json     per-theme records
    viewitem.md       the tile table, the flip list and the colour table
    contact.png       hover + selected art strips, one row per theme,
                      flips marked — the eyeball check for the flip list
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from themey.analyze.build_theme import build_theme  # noqa: E402
from themey.analyze.colors import (  # noqa: E402
    MIN_CONTRAST,
    contrast_ratio,
    extract_dominant,
    view_from_window,
)
from themey.etheme.archive import extract  # noqa: E402
from themey.etheme.parse import parse_tree  # noqa: E402
from themey.generate import plasmastyle as ps  # noqa: E402
from themey.ir import Theme  # noqa: E402

DEFAULT_CORPUS = Path.home() / "Desktop" / "ethemes" / "e16"

#: Contact-sheet geometry (px). Kept small on purpose — the whole sheet
#: must stay under a megabyte to be worth opening.
STRIP = (88, 13)
LABEL_W = 104
COLUMNS = 4
ROW_H = 17


# --------------------------------------------------------------------- #
# The pre-2026-09-01 classifier, frozen for comparison
# --------------------------------------------------------------------- #

def _textured_old(img: Image.Image, caps: tuple[int, int, int, int]) -> bool:
    """``_middle_is_textured`` as it stood before the residual rewrite:
    grain = the RAW within-row spread, drift = the row-mean spread only.
    A horizontal gradient reads as pure grain here — the ShinyMetal bug."""
    left, right, top, bottom = caps
    lum = img.convert("L")
    w, h = lum.size
    bw, bh = w - left - right, h - top - bottom
    if bw < 2 or bh < 2:
        return False
    data = lum.crop((left, top, w - right, h - bottom)).tobytes()
    row_means: list[float] = []
    grains: list[float] = []
    for y in range(bh):
        vals = list(data[y * bw:(y + 1) * bw])
        row_means.append(statistics.fmean(vals))
        grains.append(statistics.pstdev(vals))
    grain = statistics.fmean(grains)
    drift = statistics.pstdev(row_means)
    # Frozen thresholds too — this copy must not drift with the live ones.
    return grain >= 8.0 and drift <= 8.0 and grain > 1.5 * drift


# --------------------------------------------------------------------- #
# Per-theme measurement
# --------------------------------------------------------------------- #

def _trimmed_art(
    spec: Any, state: str
) -> tuple[Image.Image, tuple[int, int, int, int]] | None:
    """The post-trim RGBA art and edge for *state*, as ``_emit_set`` sees it."""
    found = ps._state_attr(spec, state)
    if found is None:
        return None
    state_attr, path = found
    try:
        with Image.open(path) as im:
            trimmed = ps._opaque_trim(im.convert("RGBA"), spec.edge_for(state_attr))
    except (OSError, ValueError):
        return None
    if trimmed is None:
        return None
    img, edge, _ = trimmed
    return img, edge


def _state_record(spec: Any, state: str) -> dict[str, Any] | None:
    """Band measurements + old/new tile decision for one MENU_SEL state."""
    art = _trimmed_art(spec, state)
    if art is None:
        return None
    img, edge = art
    caps, branch = ps._viewitem_caps(
        edge, img.width, img.height, rounded=ps._is_rounded(img)
    )
    stats = ps._band_stats(img, caps)
    old = branch == "bevel" and _textured_old(img, caps)
    new = branch == "bevel" and ps._middle_is_textured(img, caps)
    return {
        "state": state,
        "size": [img.width, img.height],
        "branch": branch,
        "grain": round(stats[0], 2) if stats else None,
        "drift_v": round(stats[1], 2) if stats else None,
        "drift_h": round(stats[2], 2) if stats else None,
        "old_tiled": old,
        "new_tiled": new,
        "flipped": old != new,
    }


def _colour_record(theme: Theme) -> dict[str, Any]:
    """Selection + View backgrounds before and after WP1's colour moves."""
    out: dict[str, Any] = {}
    sel = theme.iclasses.get("MENU_SEL")
    hover = ps._state_image(sel, "hover")
    pressed = ps._state_image(sel, "selected")
    if hover is not None:
        out["sel_old"] = extract_dominant(hover)
    if pressed is not None:
        out["sel_new"] = extract_dominant(pressed)
    # The label colours as SHIPPED, i.e. after the WCAG guard: old sampled
    # the hover art and guarded against it alone, new samples the pressed
    # art and guards against both plates (Kickoff keeps the hover prefix
    # painted underneath).
    fallback = theme.scheme.selection.foreground_normal if theme.scheme else (0, 0, 0)
    if out.get("sel_old") is not None:
        fg_old, _ = ps._fg_for(
            ps._menu_hover_fg(theme), fallback, (out["sel_old"],)
        )
        out["fg_old"] = fg_old
        out["contrast_old"] = round(contrast_ratio(fg_old, out["sel_old"]), 2)
    if out.get("sel_new") is not None:
        guards = tuple(
            c for c in (out.get("sel_new"), out.get("sel_old")) if c is not None
        )
        candidate = ps._menu_pressed_fg(theme)
        fg_new, _ = ps._fg_for(candidate, fallback, guards)
        if not all(contrast_ratio(fg_new, b) >= MIN_CONTRAST for b in guards):
            fg_new, _ = ps._fg_for(candidate, fallback, (out["sel_new"],))
        out["fg_new"] = fg_new
        out["contrast_new"] = round(contrast_ratio(fg_new, out["sel_new"]), 2)

    scheme = theme.scheme
    if scheme is not None:
        out["view_old"] = scheme.view.background_normal
        out["accent_fallback"] = scheme.accent_fallback
        dialog = ps._dialog_source(theme)
        path = ps._state_image(dialog, "normal") if dialog is not None else None
        window_bg = extract_dominant(path) if path is not None else None
        if window_bg is not None:
            out["window_new"] = window_bg
            out["view_new"] = view_from_window(
                window_bg, scheme.view.decoration_focus,
                scheme.view.foreground_normal,
            ).background_normal
    return out


def audit_theme(path: Path) -> dict[str, Any]:
    """One archive → its record (or an ``error`` key)."""
    record: dict[str, Any] = {"name": path.stem}
    try:
        with extract(path) as raw:
            theme = build_theme(
                raw.asset_root, parse_tree(raw.asset_root),
                name=path.stem, display_name=path.stem,
            )
            spec = theme.iclasses.get("MENU_SEL")
            if spec is None:
                record["states"] = []
                record["colours"] = {}
                return record
            record["states"] = [
                r for r in (_state_record(spec, s) for s in ("hover", "selected"))
                if r is not None
            ]
            record["colours"] = _colour_record(theme)
            record["strips"] = {
                s: _strip(spec, s) for s in ("hover", "selected")
            }
    except Exception as exc:  # an audit never stops on one theme
        record["error"] = f"{type(exc).__name__}: {exc}"
    return record


def _strip(spec: Any, state: str) -> list[list[int]] | None:
    """The art squeezed to ``STRIP``, as rows of RGB ints, for the sheet."""
    art = _trimmed_art(spec, state)
    if art is None:
        return None
    img = art[0].convert("RGB").resize(STRIP, Image.Resampling.NEAREST)
    row_bytes = STRIP[0] * 3
    data = img.tobytes()
    return [
        list(data[y * row_bytes:(y + 1) * row_bytes]) for y in range(STRIP[1])
    ]


# --------------------------------------------------------------------- #
# Reports
# --------------------------------------------------------------------- #

def _contact_sheet(records: list[dict[str, Any]], out: Path) -> int:
    """One row per theme: name, hover strip, selected strip; flips marked
    with a ``>`` and a red rule. Returns the file size in bytes."""
    rows = [r for r in records if r.get("strips")]
    per_col = (len(rows) + COLUMNS - 1) // COLUMNS or 1
    cell_w = LABEL_W + STRIP[0] * 2 + 12
    sheet = Image.new(
        "RGB", (cell_w * COLUMNS, ROW_H * per_col + 4), (24, 24, 24)
    )
    draw = ImageDraw.Draw(sheet)
    for i, rec in enumerate(rows):
        col, row = divmod(i, per_col)
        x0, y0 = col * cell_w, row * ROW_H + 2
        flipped = any(s["flipped"] for s in rec["states"])
        draw.text(
            (x0 + 2, y0 + 2), ("> " if flipped else "  ") + rec["name"][:15],
            fill=(255, 120, 120) if flipped else (200, 200, 200),
        )
        for j, state in enumerate(("hover", "selected")):
            data = rec["strips"].get(state)
            if data is None:
                continue
            flat = bytes(v for line in data for v in line)
            strip = Image.frombytes("RGB", STRIP, flat)
            sheet.paste(strip, (x0 + LABEL_W + j * (STRIP[0] + 4), y0 + 1))
    sheet.convert("P", palette=Image.Palette.ADAPTIVE, colors=256).save(
        out, optimize=True
    )
    return out.stat().st_size


def _markdown(records: list[dict[str, Any]]) -> str:
    lines = ["# viewitem audit", ""]
    errors = [r for r in records if r.get("error")]
    flips = [
        r for r in records
        if any(s["flipped"] for s in r.get("states", []))
    ]
    tiled_old = sum(
        1 for r in records if any(s["old_tiled"] for s in r.get("states", []))
    )
    tiled_new = sum(
        1 for r in records if any(s["new_tiled"] for s in r.get("states", []))
    )
    lines += [
        f"- themes audited: {len(records)} ({len(errors)} errored)",
        f"- with a tiled MENU_SEL state: {tiled_old} before, {tiled_new} after",
        f"- decisions flipped: {len(flips)}",
        "",
        "## Flipped",
        "",
        "| theme | state | size | grain | drift_v | drift_h | old | new |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in flips:
        for s in r["states"]:
            if not s["flipped"]:
                continue
            lines.append(
                f"| {r['name']} | {s['state']} | {s['size'][0]}x{s['size'][1]} "
                f"| {s['grain']} | {s['drift_v']} | {s['drift_h']} "
                f"| {'tile' if s['old_tiled'] else 'stretch'} "
                f"| {'tile' if s['new_tiled'] else 'stretch'} |"
            )
    lines += [
        "",
        "## All measurements",
        "",
        "| theme | state | branch | size | grain | drift_v | drift_h | tile |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in records:
        for s in r.get("states", []):
            lines.append(
                f"| {r['name']} | {s['state']} | {s['branch']} "
                f"| {s['size'][0]}x{s['size'][1]} | {s['grain']} "
                f"| {s['drift_v']} | {s['drift_h']} "
                f"| {'tile' if s['new_tiled'] else 'stretch'} |"
            )
    lines += [
        "",
        "## Colours",
        "",
        "| theme | Selection old | new | shipped contrast old / new | "
        "View old | new | accent fallback |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in records:
        c = r.get("colours") or {}
        if not c:
            continue
        lines.append(
            f"| {r['name']} | {c.get('sel_old')} | {c.get('sel_new')} "
            f"| {c.get('contrast_old')} / {c.get('contrast_new')} "
            f"| {c.get('view_old')} | {c.get('view_new')} "
            f"| {c.get('accent_fallback')} |"
        )
    if errors:
        lines += ["", "## Errors", ""]
        lines += [f"- {r['name']}: {r['error']}" for r in errors]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-sheet", action="store_true")
    args = ap.parse_args()

    archives = sorted(args.corpus.glob("*.etheme"))
    if args.only:
        wanted = {n.lower() for n in args.only}
        archives = [p for p in archives if p.stem.lower() in wanted]
    if args.limit:
        archives = archives[: args.limit]
    if not archives:
        print(f"no .etheme archives under {args.corpus}", file=sys.stderr)
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for i, path in enumerate(archives, 1):
        rec = audit_theme(path)
        records.append(rec)
        flag = "!" if any(s["flipped"] for s in rec.get("states", [])) else " "
        print(f"[{i}/{len(archives)}] {flag} {rec['name']}"
              f"{' — ' + rec['error'] if rec.get('error') else ''}")

    sheet_note = ""
    if not args.no_sheet:
        size = _contact_sheet(records, args.out / "contact.png")
        sheet_note = f", contact.png {size / 1024:.0f} KB"

    (args.out / "viewitem.md").write_text(_markdown(records), encoding="utf-8")
    (args.out / "viewitem.json").write_text(
        json.dumps(
            [{k: v for k, v in r.items() if k != "strips"} for r in records],
            indent=1,
        ),
        encoding="utf-8",
    )
    flips = [r["name"] for r in records
             if any(s["flipped"] for s in r.get("states", []))]
    print(f"\n{len(records)} themes, {len(flips)} flipped{sheet_note}")
    if flips:
        print("flipped: " + ", ".join(flips))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
