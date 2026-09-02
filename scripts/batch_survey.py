#!/usr/bin/env python3
"""Corpus-wide convert survey: every .etheme through ``pipeline.convert``,
in-process, never installed — the instrument for "look for issues".

Each theme is converted in its own worker process (per-theme timeout, a
crash in one theme cannot take the survey down) with ``output_dir`` set,
which is the pipeline's non-installing mode: nothing under ``~/.local``,
``~/.config``, ``~/.cache`` or ``~/.icons`` is touched. Belt-and-braces,
``HOME`` and the ``XDG_*`` roots are re-pointed at the output dir before
themey is imported, and the real home is scanned for files newer than a
run marker afterwards (``--no-home-check`` skips that).

Per theme it captures: exception class + traceback tail (or timeout), wall
time, the FULL ``theme.notes`` (``report.txt`` truncates the unprefixed
per-state bucket at 20), and structural stats read back from the written
packages: viewitem cap sizes and visibility, which iclass fed the panel /
viewitem / tasks / dialog / tooltip / button, theme.js outliers (zero
borders, title height 0 or > 80, zero-size or missing part images, parts
without art), wallpaper and cursor package presence.

Usage:
    uv run python scripts/batch_survey.py --out DIR [--corpus DIR]
        [--jobs N] [--timeout SEC] [--scale S] [--only NAME ...]
        [--limit N] [--discard] [--compare PREV/summary.json]

Output (under --out):
    themes/<name>/        the convert output tree (unless --discard)
    summary.json          per-theme records + aggregate counts
    summary.md            failure classes, outlier tables, top-40 note
                          patterns, slowest 10 — the human deliverable
"""
from __future__ import annotations

import argparse
import base64
import collections
import io
import json
import multiprocessing as mp
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = Path.home() / "Desktop" / "ethemes" / "e16"
REAL_HOME = Path.home()

#: A Kickoff row is ~30 px; a viewitem cap past this (ref px) is an
#: outlier the Plasma Style must clamp (plan finding B).
VIEWITEM_MAX_REF_CAP = 12
TITLE_HEIGHT_MAX = 80
TRACEBACK_TAIL_LINES = 12
TOP_NOTE_PATTERNS = 40

# Dirs under the real home that a themey install would write to. Scanned
# for files newer than the run marker to prove the survey never installed.
HOME_WATCH = (
    ".local/share/kwin", ".local/share/aurorae", ".local/share/plasma",
    ".local/share/color-schemes", ".local/share/wallpapers",
    ".local/share/themey", ".local/share/icons", ".icons", ".config/kwinrc",
    ".config/kdeglobals",
    ".config/plasmarc", ".config/kcminputrc", ".cache/plasma_theme",
    ".cache/plasma-svgelements",
)

SVG_NS = "{http://www.w3.org/2000/svg}"
XLINK_HREF = "{http://www.w3.org/1999/xlink}href"


# --------------------------------------------------------------------- #
# Worker
# --------------------------------------------------------------------- #

def _isolate_env(out: Path) -> None:
    fake_home = out / "home"
    fake_home.mkdir(parents=True, exist_ok=True)
    os.environ["HOME"] = str(fake_home)
    os.environ["XDG_DATA_HOME"] = str(fake_home / ".local" / "share")
    os.environ["XDG_CONFIG_HOME"] = str(fake_home / ".config")
    os.environ["XDG_CACHE_HOME"] = str(fake_home / ".cache")


def _parse_theme_js(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    start = text.index("{")
    end = text.rindex("}")
    return json.loads(text[start:end + 1])


def _theme_js_stats(pkg_dir: Path | None) -> dict[str, Any]:
    """Outliers read from the QML package's theme.js + shipped PNGs."""
    stats: dict[str, Any] = {"present": False}
    if pkg_dir is None:
        return stats
    js = pkg_dir / "contents" / "ui" / "theme.js"
    if not js.is_file():
        return stats
    from PIL import Image

    data = _parse_theme_js(js)
    borders = data.get("borders", {})
    parts = data.get("parts", [])
    stats["present"] = True
    stats["borders"] = borders
    stats["zero_borders"] = all(int(v) <= 0 for v in borders.values()) if borders else True
    stats["title_height"] = int(borders.get("top", 0))
    stats["parts"] = len(parts)
    stats["parts_without_images"] = sorted(
        p.get("id", "?") for p in parts if not p.get("images")
    )
    stats["buttons"] = sorted(
        str(p["button"]) for p in parts if p.get("button")
    )
    zero_size: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()
    for p in parts:
        for rel in (p.get("images") or {}).values():
            if rel in seen:
                continue
            seen.add(rel)
            img_path = (js.parent / rel).resolve()
            if not img_path.is_file():
                missing.append(rel)
                continue
            try:
                with Image.open(img_path) as im:
                    if im.width == 0 or im.height == 0:
                        zero_size.append(rel)
            except OSError:
                zero_size.append(rel)
    stats["zero_size_images"] = zero_size
    stats["missing_images"] = missing
    return stats


def _decode_image(el: ET.Element):
    from PIL import Image

    href = el.get(XLINK_HREF) or el.get("href") or ""
    if not href.startswith("data:image/png;base64,"):
        return None
    raw = base64.b64decode(href.split(",", 1)[1])
    return Image.open(io.BytesIO(raw)).convert("RGBA")


def _viewitem_stats(style_dir: Path | None, scale: float) -> dict[str, Any]:
    """Cap sizes per prefix (output px and ref px) + visibility."""
    stats: dict[str, Any] = {"present": False}
    if style_dir is None:
        return stats
    svg = style_dir / "widgets" / "viewitem.svg"
    if not svg.is_file():
        return stats
    stats["present"] = True
    root = ET.parse(svg).getroot()
    dims: dict[str, tuple[int, int]] = {}
    any_visible = False
    for g in root.iter(f"{SVG_NS}g"):
        gid = g.get("id", "")
        img_el = g.find(f"{SVG_NS}image")
        if img_el is None:
            continue
        dims[gid] = (int(float(img_el.get("width", "0"))), int(float(img_el.get("height", "0"))))
        if not any_visible:
            im = _decode_image(img_el)
            if im is not None:
                _, amax = im.getchannel("A").getextrema()
                if amax >= 128:
                    any_visible = True
    caps_px: dict[str, list[int]] = {}
    prefixes = sorted({gid.rsplit("-", 1)[0] + "-" for gid in dims if "-" in gid})
    for prefix in prefixes:
        left = dims.get(prefix + "left", dims.get(prefix + "topleft", (0, 0)))[0]
        right = dims.get(prefix + "right", dims.get(prefix + "topright", (0, 0)))[0]
        top = dims.get(prefix + "top", dims.get(prefix + "topleft", (0, 0)))[1]
        bottom = dims.get(prefix + "bottom", dims.get(prefix + "bottomleft", (0, 0)))[1]
        caps_px[prefix] = [left, right, top, bottom]
    stats["caps_px"] = caps_px
    stats["caps_ref"] = {
        k: [round(v / scale, 1) for v in vals] for k, vals in caps_px.items()
    }
    stats["max_cap_ref"] = max(
        (v for vals in stats["caps_ref"].values() for v in vals), default=0
    )
    stats["asymmetric"] = any(
        vals[0] != vals[1] for vals in caps_px.values()
    )
    stats["invisible"] = not any_visible
    return stats


_SOURCE_RE = re.compile(
    r"^plasmastyle: (?P<what>panel background|menu/list selection|task frames|"
    r"popup/dialog background|popup/dialog frame composed|tooltip background|"
    r"widget buttons|pager cells|pager window rects|dragbar desk buttons) "
    r"from (?:iclass |menu frame pieces )(?P<src>[A-Za-z0-9_+, ]+?)"
    r"(?: art| around|;|\s*\(|$)"
)
_SOURCE_KEY = {
    "panel background": "panel",
    "menu/list selection": "viewitem",
    "task frames": "tasks",
    "popup/dialog background": "dialog",
    "popup/dialog frame composed": "dialog",
    "tooltip background": "tooltip",
    "widget buttons": "button",
    "pager cells": "pager",
    "pager window rects": "pager_win",
    "dragbar desk buttons": "dragbar",
}


def _sources_from_notes(notes: list[str]) -> dict[str, str | None]:
    sources: dict[str, str | None] = dict.fromkeys(set(_SOURCE_KEY.values()))
    for note in notes:
        m = _SOURCE_RE.match(note)
        if m:
            sources[_SOURCE_KEY[m.group("what")]] = m.group("src").strip()
    return sources


def _panel_mode(notes: list[str]) -> str:
    for note in notes:
        if note.startswith("plasmastyle: panel background is a translucent tint"):
            return "tint"
        if note.startswith("plasmastyle: panel background from iclass"):
            return "art"
    return "none"


def _panel_rejections(notes: list[str]) -> list[str]:
    return [
        n for n in notes
        if n.startswith("plasmastyle: ") and "rejected for the panel background" in n
    ]


def survey_one(etheme: str, out_dir: str, scale: float, discard: bool) -> dict[str, Any]:
    """Convert one theme and read its stats back. Runs in a worker process."""
    out = Path(out_dir)
    _isolate_env(out)
    sys.path.insert(0, str(REPO / "src"))
    import logging

    logging.disable(logging.CRITICAL)
    from themey.pipeline import convert
    from themey.slug import slugify

    path = Path(etheme)
    name = slugify(path.stem)
    rec: dict[str, Any] = {"name": name, "stem": path.stem, "file": path.name}
    if discard:
        tmp = tempfile.mkdtemp(prefix=f"survey-{name}-", dir=str(out))
        theme_out = Path(tmp)
    else:
        theme_out = out / "themes" / name
        if theme_out.exists():
            shutil.rmtree(theme_out)
    t0 = time.perf_counter()
    try:
        result = convert(path, scale=scale, output_dir=theme_out)
    except BaseException as exc:  # a survey records everything
        rec["status"] = "error"
        rec["error_type"] = type(exc).__name__
        rec["error"] = str(exc).splitlines()[0][:300] if str(exc) else ""
        tb = traceback.format_exc().splitlines()
        rec["traceback_tail"] = tb[-TRACEBACK_TAIL_LINES:]
        rec["seconds"] = round(time.perf_counter() - t0, 2)
        if discard:
            shutil.rmtree(theme_out, ignore_errors=True)
        return rec
    rec["seconds"] = round(time.perf_counter() - t0, 2)
    rec["status"] = "ok"
    notes = list(result.notes)
    rec["notes"] = notes
    rec["note_count"] = len(notes)
    stats: dict[str, Any] = {}
    stats["wallpapers"] = len(result.wallpaper_dirs)
    stats["cursors"] = result.cursor_theme_dir is not None
    stats["icon_theme"] = result.icon_theme_dir is not None
    stats["icon_rules"] = sum(
        1 for n in notes if n.startswith("icons: ") and " wears " in n
    )
    stats["style"] = result.desktop_theme_dir is not None
    if result.desktop_theme_dir is not None:
        stats["style_files"] = sorted(
            str(p.relative_to(result.desktop_theme_dir))
            for p in result.desktop_theme_dir.rglob("*.svg")
            if "solid" not in p.parts and "opaque" not in p.parts
        )
    else:
        stats["style_files"] = []
    stats["theme_js"] = _theme_js_stats(result.qml_installed_dir)
    stats["sources"] = _sources_from_notes(notes)
    stats["panel_mode"] = _panel_mode(notes)
    stats["panel_rejections"] = _panel_rejections(notes)
    # _surface_scale drops chrome-dominated art to 1x — read the note so
    # ref px stay honest for those themes.
    vi_src = stats["sources"].get("viewitem") or "MENU_SEL"
    vi_scale = 1.0 if any(
        n.startswith(f"plasmastyle: {vi_src} caps (") and "dominate the surface" in n
        for n in notes
    ) else float(scale)
    try:
        stats["viewitem"] = _viewitem_stats(result.desktop_theme_dir, vi_scale)
    except Exception as exc:
        stats["viewitem"] = {"present": True, "error": f"{type(exc).__name__}: {exc}"}
    rec["stats"] = stats
    if discard:
        shutil.rmtree(theme_out, ignore_errors=True)
    return rec


def _worker_main(etheme: str, out_dir: str, scale: float, discard: bool, queue) -> None:
    try:
        rec = survey_one(etheme, out_dir, scale, discard)
    except BaseException as exc:
        rec = {
            "name": Path(etheme).stem, "stem": Path(etheme).stem,
            "file": Path(etheme).name, "status": "error",
            "error_type": type(exc).__name__, "error": str(exc)[:300],
            "traceback_tail": traceback.format_exc().splitlines()[-TRACEBACK_TAIL_LINES:],
            "seconds": 0.0,
        }
    queue.put(rec)


# --------------------------------------------------------------------- #
# Scheduler
# --------------------------------------------------------------------- #

def run_all(
    themes: list[Path], out: Path, *, jobs: int, timeout: float, scale: float,
    discard: bool,
) -> list[dict[str, Any]]:
    ctx = mp.get_context("fork")
    queue = ctx.Queue()
    pending = list(themes)
    running: dict[str, tuple[Any, float, Path]] = {}
    results: dict[str, dict[str, Any]] = {}
    done = 0
    total = len(themes)
    while pending or running:
        while pending and len(running) < jobs:
            path = pending.pop(0)
            proc = ctx.Process(
                target=_worker_main,
                args=(str(path), str(out), scale, discard, queue),
                daemon=True,
            )
            proc.start()
            running[path.stem] = (proc, time.monotonic(), path)
        try:
            while True:
                rec = queue.get(timeout=0.2)
                results[rec["stem"]] = rec
        except Exception:  # queue.Empty (mp re-exports it via queue module)
            pass
        now = time.monotonic()
        for stem, (proc, started, path) in list(running.items()):
            if stem in results:
                proc.join(1)
                del running[stem]
                done += 1
                status = results[stem]["status"]
                secs = results[stem]["seconds"]
                print(f"[{done}/{total}] {stem}: {status} ({secs}s)", flush=True)
            elif not proc.is_alive() and stem not in results:
                # Died without reporting (segfault, OOM kill).
                proc.join(1)
                results[stem] = {
                    "name": stem, "stem": stem, "file": path.name,
                    "status": "error", "error_type": "WorkerDied",
                    "error": f"worker exited with code {proc.exitcode}",
                    "traceback_tail": [], "seconds": round(now - started, 2),
                }
                del running[stem]
                done += 1
                print(f"[{done}/{total}] {stem}: worker died (exit {proc.exitcode})", flush=True)
            elif now - started > timeout:
                proc.terminate()
                proc.join(2)
                if proc.is_alive():
                    proc.kill()
                results[stem] = {
                    "name": stem, "stem": stem, "file": path.name,
                    "status": "timeout", "error_type": "Timeout",
                    "error": f"exceeded {timeout:g}s", "traceback_tail": [],
                    "seconds": round(now - started, 2),
                }
                del running[stem]
                done += 1
                print(f"[{done}/{total}] {stem}: TIMEOUT", flush=True)
    return [results[p.stem] for p in themes]


# --------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------- #

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")
# A path token stops at quotes/parens so a macro('path') wrapper or a
# repr'd 'path' keeps its punctuation (the old \S+ swallowed them and
# rendered overlay notes as "FILE')").
_FILE_RE = re.compile(
    r"[^\s'\"()]+\.(?:png|jpe?g|bmp|gif|ttf|otf|xbm|xpm|pcf|fnt)\b", re.I
)
_ICLASS_RE = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_RGB_RE = re.compile(r"rgb\([^)]*\)")


def note_pattern(note: str) -> str:
    s = _RGB_RE.sub("rgb(...)", note)
    s = _FILE_RE.sub("FILE", s)
    s = _ICLASS_RE.sub("ICLASS", s)
    s = _NUM_RE.sub("N", s)
    return s[:160]


def error_class(rec: dict[str, Any]) -> str:
    msg = rec.get("error", "")
    return f"{rec.get('error_type', '?')}: {note_pattern(msg)[:100]}"


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    ok = [r for r in records if r["status"] == "ok"]
    agg: dict[str, Any] = {
        "total": len(records),
        "ok": len(ok),
        "error": sum(1 for r in records if r["status"] == "error"),
        "timeout": sum(1 for r in records if r["status"] == "timeout"),
        "seconds_total": round(sum(r.get("seconds", 0) for r in records), 1),
    }
    failures: dict[str, list[str]] = collections.defaultdict(list)
    for r in records:
        if r["status"] != "ok":
            failures[error_class(r)].append(r["name"])
    agg["failure_classes"] = dict(
        sorted(failures.items(), key=lambda kv: -len(kv[1]))
    )

    patterns: dict[str, set[str]] = collections.defaultdict(set)
    for r in ok:
        for note in r["notes"]:
            patterns[note_pattern(note)].add(r["name"])
    agg["note_patterns"] = [
        {"pattern": p, "themes": len(names), "example": sorted(names)[0]}
        for p, names in sorted(patterns.items(), key=lambda kv: -len(kv[1]))
    ]

    def names(pred) -> list[str]:
        return sorted(r["name"] for r in ok if pred(r["stats"]))

    vi = lambda s: s.get("viewitem", {})  # noqa: E731
    tj = lambda s: s.get("theme_js", {})  # noqa: E731
    agg["outliers"] = {
        "viewitem_absent": names(lambda s: not vi(s).get("present")),
        "viewitem_invisible": names(lambda s: vi(s).get("present") and vi(s).get("invisible")),
        "viewitem_cap_over_max": [
            {"name": r["name"], "caps_ref": vi(r["stats"]).get("caps_ref", {}).get("hover-"),
             "source": r["stats"]["sources"].get("viewitem")}
            for r in ok
            if vi(r["stats"]).get("max_cap_ref", 0) > VIEWITEM_MAX_REF_CAP
        ],
        "viewitem_asymmetric": names(lambda s: vi(s).get("asymmetric", False)),
        "panel_art": names(lambda s: s.get("panel_mode") == "art"),
        "panel_tint": names(lambda s: s.get("panel_mode") == "tint"),
        "panel_rejections": {
            r["name"]: r["stats"]["panel_rejections"]
            for r in ok if r["stats"].get("panel_rejections")
        },
        "no_style": names(lambda s: not s.get("style")),
        "no_wallpapers": names(lambda s: s.get("wallpapers", 0) == 0),
        "no_cursors": names(lambda s: not s.get("cursors")),
        "icon_theme": names(lambda s: s.get("icon_theme")),
        "deco_zero_borders": names(lambda s: tj(s).get("present") and tj(s).get("zero_borders")),
        "deco_title_height_odd": [
            {"name": r["name"], "title_height": tj(r["stats"]).get("title_height")}
            for r in ok
            if tj(r["stats"]).get("present")
            and (tj(r["stats"]).get("title_height", 0) <= 0
                 or tj(r["stats"]).get("title_height", 0) > TITLE_HEIGHT_MAX)
        ],
        "deco_zero_parts": names(lambda s: tj(s).get("present") and tj(s).get("parts", 0) == 0),
        "deco_parts_without_images": {
            r["name"]: tj(r["stats"])["parts_without_images"]
            for r in ok if tj(r["stats"]).get("parts_without_images")
        },
        "deco_zero_size_images": {
            r["name"]: tj(r["stats"])["zero_size_images"]
            for r in ok if tj(r["stats"]).get("zero_size_images")
        },
        "deco_missing_images": {
            r["name"]: tj(r["stats"])["missing_images"]
            for r in ok if tj(r["stats"]).get("missing_images")
        },
        "no_qml_package": names(lambda s: not tj(s).get("present")),
    }
    agg["sources"] = {
        key: collections.Counter(
            str(r["stats"]["sources"].get(key)) for r in ok
        ).most_common()
        for key in (
            "panel", "viewitem", "tasks", "dialog", "tooltip", "button",
            "pager", "pager_win", "dragbar",
        )
    }
    agg["style_files"] = collections.Counter(
        f for r in ok for f in r["stats"].get("style_files", [])
    ).most_common()
    agg["slowest"] = [
        {"name": r["name"], "seconds": r.get("seconds", 0)}
        for r in sorted(records, key=lambda r: -r.get("seconds", 0))[:10]
    ]
    return agg


def _md_list(items, limit: int = 12) -> str:
    items = list(items)
    if not items:
        return "_none_"
    shown = ", ".join(f"`{i}`" for i in items[:limit])
    if len(items) > limit:
        shown += f" … (+{len(items) - limit})"
    return shown


def write_summary_md(agg: dict[str, Any], out: Path, compare: dict[str, Any] | None) -> None:
    L: list[str] = []
    L.append("# Batch survey summary\n")
    L.append(
        f"Themes: {agg['total']} — ok {agg['ok']}, error {agg['error']}, "
        f"timeout {agg['timeout']}; {agg['seconds_total']} s of convert time.\n"
    )
    if compare is not None:
        L.append("## Delta vs previous run\n")
        L.append("| metric | previous | now |")
        L.append("|---|---:|---:|")
        for key in ("ok", "error", "timeout"):
            L.append(f"| {key} | {compare.get(key, '?')} | {agg[key]} |")
        prev_out = compare.get("outliers", {})
        for key, val in agg["outliers"].items():
            L.append(f"| {key} | {len(prev_out.get(key, []))} | {len(val)} |")
        L.append("")

    L.append("## Failure classes\n")
    if not agg["failure_classes"]:
        L.append("_no crashes or timeouts_\n")
    for cls, names in agg["failure_classes"].items():
        L.append(f"- **{len(names)}× `{cls}`** — {_md_list(names, 8)}")
    L.append("")

    o = agg["outliers"]
    L.append("## Outliers\n")
    L.append("| check | count | themes |")
    L.append("|---|---:|---|")
    for key in (
        "viewitem_absent", "viewitem_invisible", "viewitem_asymmetric",
        "panel_art", "panel_tint", "no_style", "no_wallpapers", "no_cursors",
        "icon_theme", "deco_zero_borders", "deco_zero_parts", "no_qml_package",
    ):
        L.append(f"| {key} | {len(o[key])} | {_md_list(o[key])} |")
    for key in (
        "deco_parts_without_images", "deco_zero_size_images", "deco_missing_images",
        "panel_rejections",
    ):
        L.append(f"| {key} | {len(o[key])} | {_md_list(o[key])} |")
    L.append("")

    n_over = len(o["viewitem_cap_over_max"])
    L.append(f"### viewitem caps over {VIEWITEM_MAX_REF_CAP} ref px ({n_over})\n")
    if o["viewitem_cap_over_max"]:
        L.append("| theme | hover caps (L R T B, ref px) | source |")
        L.append("|---|---|---|")
        for row in sorted(o["viewitem_cap_over_max"], key=lambda r: -max(r["caps_ref"] or [0])):
            L.append(f"| {row['name']} | {row['caps_ref']} | {row['source']} |")
    L.append("")

    n_odd = len(o["deco_title_height_odd"])
    L.append(f"### deco title height ≤ 0 or > {TITLE_HEIGHT_MAX} ({n_odd})\n")
    for row in o["deco_title_height_odd"]:
        L.append(f"- {row['name']}: {row['title_height']}")
    L.append("")

    L.append("## Plasma Style sources\n")
    for key, counts in agg["sources"].items():
        L.append(f"- **{key}**: " + ", ".join(f"{src} ×{n}" for src, n in counts[:8]))
    L.append("")
    L.append("## Shipped style files\n")
    L.append(", ".join(f"`{f}` ×{n}" for f, n in agg["style_files"]))
    L.append("")

    L.append(f"## Top {TOP_NOTE_PATTERNS} note patterns\n")
    L.append("| themes | pattern | e.g. |")
    L.append("|---:|---|---|")
    for row in agg["note_patterns"][:TOP_NOTE_PATTERNS]:
        pat = row["pattern"].replace("|", "\\|")
        L.append(f"| {row['themes']} | {pat} | {row['example']} |")
    L.append("")

    L.append("## Slowest 10\n")
    for row in agg["slowest"]:
        L.append(f"- {row['name']}: {row['seconds']} s")
    L.append("")
    (out / "summary.md").write_text("\n".join(L), encoding="utf-8")


def home_check(marker: Path) -> list[str]:
    hits: list[str] = []
    for rel in HOME_WATCH:
        p = REAL_HOME / rel
        if not p.exists():
            continue
        cmd = ["find", str(p), "-newer", str(marker)]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            continue
        hits.extend(line for line in res.stdout.splitlines() if line.strip())
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--scale", type=float, default=2)
    ap.add_argument("--only", nargs="*", default=None, help="theme stems to run")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument(
        "--discard", action="store_true",
        help="delete each theme's output after reading its stats",
    )
    ap.add_argument(
        "--compare", type=Path, default=None,
        help="previous summary.json to diff against",
    )
    ap.add_argument("--no-home-check", action="store_true")
    args = ap.parse_args(argv)

    themes = sorted(args.corpus.glob("*.etheme"))
    if args.only:
        wanted = set(args.only)
        themes = [t for t in themes if t.stem in wanted]
    if args.limit:
        themes = themes[: args.limit]
    if not themes:
        print(f"no .etheme files under {args.corpus}", file=sys.stderr)
        return 2
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    marker = out / ".run-marker"
    marker.touch()
    time.sleep(1.1)  # find -newer is second-granular on some filesystems

    print(f"surveying {len(themes)} themes with {args.jobs} workers → {out}", flush=True)
    t0 = time.monotonic()
    records = run_all(
        themes, out, jobs=args.jobs, timeout=args.timeout,
        scale=args.scale, discard=args.discard,
    )
    wall = round(time.monotonic() - t0, 1)
    agg = aggregate(records)
    agg["wall_seconds"] = wall
    compare = None
    if args.compare and args.compare.is_file():
        compare = json.loads(args.compare.read_text(encoding="utf-8")).get("aggregate")
    (out / "summary.json").write_text(
        json.dumps({"aggregate": agg, "themes": records}, indent=1, sort_keys=True),
        encoding="utf-8",
    )
    write_summary_md(agg, out, compare)

    if not args.no_home_check:
        hits = home_check(marker)
        if hits:
            print("WARNING: files under the real home changed during the survey:", file=sys.stderr)
            for h in hits[:20]:
                print("  " + h, file=sys.stderr)
        else:
            print("home check: nothing under the real home was written", flush=True)

    print(
        f"done in {wall}s: ok {agg['ok']}, error {agg['error']}, "
        f"timeout {agg['timeout']} → {out / 'summary.md'}",
        flush=True,
    )
    return 0 if agg["error"] == 0 and agg["timeout"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
