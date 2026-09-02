#!/usr/bin/env python3
"""Refresh the locally installed ``themey_*`` reference packages.

The packages under ``~/.local/share/{kwin/decorations,plasma/desktoptheme,
plasma/look-and-feel}`` (plus ``~/.icons`` and ``$XDG_DATA_HOME/icons`` for
the cursor/icon namespaces) were each installed by a `themey <archive>` run
at whatever themey version was current that day, so as references for eyeballing
a generator change they drift stale. This script finds the ``.etheme``
archive each installed package came from (via ``slug.plugin_id`` on the
archive stem — the same identity ``themey apply`` resolves), then re-runs
``pipeline.convert`` in-process with the current defaults: no ``apply``, no
preview auto-open, installing over the existing package exactly as
``themey <archive>`` would from the CLI.

Nothing is deleted: an installed package with no matching archive under the
corpus is only listed, never removed. Not a themey CLI command — a
maintainer script beside ``batch_survey.py``, run once at the end of a
polish pass after every work package that touches a generator has merged.

Usage:
    uv run python scripts/reconvert_installed.py [--corpus DIR]
        [--dry-run] [--only PKG_ID ...]

    --dry-run    list the archive each installed package matches (or
                 doesn't) and convert nothing.
    --only       restrict to these package ids (``themey_<slug>``, the
                 bare ``<slug>`` also accepted) — for testing one theme at
                 a time instead of the whole installed set.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = Path.home() / "Desktop" / "ethemes" / "e16"

# A themey_<slug> directory in the cursor (~/.icons) or icon
# ($XDG_DATA_HOME/icons) namespaces carries one of these suffixes; both
# fold back to the same conversion's canonical id, not a separate one.
_NAMESPACE_SUFFIXES = ("-cursors", "-icons")

# report.write's Approximated-section layout (report.py): these note
# prefixes are surfaced as top-level "- prefix: ..." bullets ahead of the
# per-state collapse bucket, whose own notes are nested "  - ..." bullets
# under a fixed summary line and truncated at 20 with a "... (N more)"
# trailer. previous_note_count() reverses that layout to recover
# len(theme.notes) from a report.txt already on disk.
_LAYOUT_PREFIXES = (
    "aurorae_rc:", "bundle:", "colors:", "composite:", "cursors:",
    "fonts:", "icons:", "plasmastyle:", "qmldeco:", "tooltips:", "wallpaper:",
)
_MORE_RE = re.compile(r"^\s*\.\.\.\s*\((\d+) more\)\s*$")


def canonical_package_ids(*roots: Path) -> set[str]:
    """``themey_*`` directory names under *roots*, namespace suffixes
    stripped back to the shared conversion id (see module docstring)."""
    ids: set[str] = set()
    for root in roots:
        if not root.is_dir():
            continue
        for entry in root.iterdir():
            if not entry.is_dir() or not entry.name.startswith("themey_"):
                continue
            name = entry.name
            for suffix in _NAMESPACE_SUFFIXES:
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            ids.add(name)
    return ids


def match_archives(
    pkg_ids: set[str], corpus: Path
) -> tuple[dict[str, Path], set[str]]:
    """Map each id in *pkg_ids* to the ``.etheme`` archive under *corpus*
    whose ``slug.plugin_id(stem)`` produces it.

    Returns ``(matches, unmatched)``. When two archive stems collide on the
    same plugin id (hyphens and underscores mangle to the same string) the
    first one in sorted order wins — the same ambiguity ``themey apply``
    already lives with, not something this script needs to adjudicate.
    """
    from themey.slug import plugin_id

    by_id: dict[str, Path] = {}
    for etheme in sorted(corpus.glob("*.etheme")):
        by_id.setdefault(plugin_id(etheme.stem), etheme)
    matches = {pid: by_id[pid] for pid in pkg_ids if pid in by_id}
    unmatched = {pid for pid in pkg_ids if pid not in by_id}
    return matches, unmatched


def previous_note_count(theme_name: str) -> int | str:
    """Reconstruct the previous conversion's ``len(theme.notes)`` from its
    installed ``report.txt`` (``paths.themey_reports() /
    f"{theme_name}.report.txt"`` — see ``pipeline.py``). Returns ``"?"``
    when the file is missing or doesn't parse as report.write's layout."""
    from themey import paths

    report_path = paths.themey_reports() / f"{theme_name}.report.txt"
    if not report_path.is_file():
        return "?"
    text = report_path.read_text(encoding="utf-8")
    if "## Approximated" not in text or "## Skipped" not in text:
        return "?"
    section = text.split("## Approximated", 1)[1].split("## Skipped", 1)[0]
    count = 0
    for line in section.splitlines():
        more = _MORE_RE.match(line)
        if more:
            count += int(more.group(1))
        elif line.startswith("  - "):
            count += 1
        elif line.startswith("- ") and line[2:].startswith(_LAYOUT_PREFIXES):
            count += 1
    return count


def _normalize_pkg_id(s: str) -> str:
    return s if s.startswith("themey_") else f"themey_{s}"


def _print_table(rows: list[dict[str, Any]]) -> None:
    headers = ("package", "status", "notes before", "notes after", "delta")
    cols = [
        [str(r[k]) for r in rows]
        for k in ("pkg_id", "status", "before", "after", "delta")
    ]
    widths = [
        max(len(h), *(len(c) for c in col)) if col else len(h)
        for h, col in zip(headers, cols, strict=True)
    ]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*("-" * w for w in widths)))
    for i in range(len(rows)):
        print(fmt.format(*(col[i] for col in cols)))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="list matched/unmatched packages and convert nothing",
    )
    ap.add_argument(
        "--only", nargs="*", default=None, metavar="PKG_ID",
        help="restrict to these package ids (themey_<slug> or bare <slug>)",
    )
    args = ap.parse_args(argv)

    sys.path.insert(0, str(REPO / "src"))
    from themey import paths
    from themey.pipeline import convert as pipeline_convert
    from themey.slug import slugify

    installed = canonical_package_ids(
        paths.kwin_decorations(), paths.desktop_themes(), paths.look_and_feel()
    )
    if args.only:
        wanted = {_normalize_pkg_id(s) for s in args.only}
        unknown = wanted - installed
        if unknown:
            print(
                f"--only names not installed: {sorted(unknown)}", file=sys.stderr
            )
            return 2
        installed = installed & wanted

    if not installed:
        print(
            f"no themey_* packages found under {paths.kwin_decorations().parent}"
        )
        return 0

    matches, unmatched = match_archives(installed, args.corpus)
    print(
        f"{len(installed)} installed themey_* package(s); "
        f"{len(matches)} matched an archive under {args.corpus}, "
        f"{len(unmatched)} unmatched"
    )
    if unmatched:
        print("unmatched (left installed, not deleted): " + ", ".join(sorted(unmatched)))

    if args.dry_run:
        for pkg_id in sorted(matches):
            print(f"  {pkg_id} -> {matches[pkg_id].name}")
        return 0

    rows: list[dict[str, Any]] = []
    failed = 0
    for pkg_id in sorted(matches):
        etheme = matches[pkg_id]
        theme_name = slugify(etheme.stem)
        before = previous_note_count(theme_name)
        try:
            result = pipeline_convert(etheme)
        except Exception as exc:  # one bad archive must not sink the run
            failed += 1
            rows.append({
                "pkg_id": pkg_id, "status": "FAILED", "before": before,
                "after": "?", "delta": f"{type(exc).__name__}: {exc}",
            })
            print(f"  {pkg_id}: FAILED ({type(exc).__name__}: {exc})", file=sys.stderr)
            continue
        after = result.notes_count
        delta = after - before if isinstance(before, int) else "?"
        rows.append({
            "pkg_id": pkg_id, "status": "ok", "before": before, "after": after,
            "delta": delta,
        })
        print(f"  {pkg_id}: ok (notes {before} -> {after})")

    print()
    _print_table(rows)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
