#!/usr/bin/env python3
"""Full-corpus survey: convert + render every .etheme, emit a triage gallery.

For each theme in the corpus directory this runs the full pipeline into a
throwaway output dir (collecting fidelity notes and crashes), renders it with
the headless-KWin harness (``themey render`` — the visual truth), and writes
a static HTML gallery pairing each render with its ps.ucw.cz gallery
reference thumbnail, its layout-decision notes and its error bucket. The
deliverable is a ranked list of the corpus's remaining failure shapes.

Resumable: a theme is skipped when its render PNG (or its error marker from
a previous run) already exists under the output dir. Delete
``renders/<name>.png`` / ``errors/<name>.txt`` to redo one.

Usage:
    uv run python scripts/survey_corpus.py [--corpus DIR] [--out DIR]
        [--limit N] [--only NAME ...] [--no-render]

Output (default ~/.local/share/themey/survey/):
    renders/<name>.png   headless-KWin screenshot
    reports/<name>.txt   report.txt copy
    errors/<name>.txt    traceback for crashed themes
    survey.json          machine-readable results
    index.html           the triage gallery
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
import tempfile
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

from themey.pipeline import convert  # noqa: E402
from themey.render import RenderError, available, render  # noqa: E402
from themey.slug import slugify  # noqa: E402

GALLERY = "https://ps.ucw.cz/e16/e16-themes-gallery"


@dataclass
class Result:
    name: str
    stem: str
    status: str = "ok"  # ok | convert-error | render-error | skipped-prior-error
    error: str = ""
    error_class: str = ""
    layout_notes: list[str] = field(default_factory=list)
    note_count: int = 0
    render: str = ""  # relative PNG path when rendered


def survey_one(etheme: Path, out: Path, do_render: bool) -> Result:
    name = slugify(etheme.stem)
    res = Result(name=name, stem=etheme.stem)
    with tempfile.TemporaryDirectory(prefix=f"survey-{name}-") as tmp:
        try:
            conv = convert(etheme, scale=2, output_dir=Path(tmp))
        except Exception as exc:
            res.status = "convert-error"
            res.error = f"{type(exc).__name__}: {exc}"
            res.error_class = type(exc).__name__
            (out / "errors" / f"{name}.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
            return res
        if conv.report_path.is_file():
            report = conv.report_path.read_text(encoding="utf-8")
            shutil.copy(conv.report_path, out / "reports" / f"{name}.txt")
            res.layout_notes = [
                line.lstrip("- ").strip()
                for line in report.splitlines()
                if line.startswith(("- composite:", "- aurorae_rc:"))
            ]
            res.note_count = sum(
                1 for line in report.splitlines() if line.lstrip().startswith("- ")
            )
    if do_render:
        png = out / "renders" / f"{name}.png"
        try:
            render(str(etheme), out=png)
            res.render = f"renders/{name}.png"
        except (RenderError, Exception) as exc:  # noqa: BLE001 — bucket everything
            res.status = "render-error"
            res.error = f"{type(exc).__name__}: {exc}"
            res.error_class = type(exc).__name__
            (out / "errors" / f"{name}.txt").write_text(
                traceback.format_exc(), encoding="utf-8"
            )
    return res


def write_gallery(out: Path, results: list[Result]) -> Path:
    buckets: dict[str, int] = {}
    for r in results:
        if r.status != "ok":
            key = f"{r.status}:{r.error_class or '?'}"
            buckets[key] = buckets.get(key, 0) + 1
    ranked_buckets = sorted(buckets.items(), key=lambda kv: -kv[1])
    ok = [r for r in results if r.status == "ok"]
    errs = [r for r in results if r.status != "ok"]
    noisiest = sorted(ok, key=lambda r: -len(r.layout_notes))[:20]

    rows: list[str] = []
    for r in errs + sorted(ok, key=lambda r: (-len(r.layout_notes), r.name)):
        ref = f"{GALLERY}/tn/{html.escape(r.stem)}.png.jpg"
        render_cell = (
            f'<img src="{html.escape(r.render)}" loading="lazy">'
            if r.render
            else f'<div class="err">{html.escape(r.error or r.status)}</div>'
        )
        notes = "".join(
            f"<li>{html.escape(n)}</li>" for n in r.layout_notes
        ) or "<li>none</li>"
        rows.append(
            f'<div class="card" id="{html.escape(r.name)}">'
            f"<h3>{html.escape(r.stem)} "
            f'<span class="meta">{r.note_count} notes · {r.status}</span></h3>'
            f'<div class="pair">{render_cell}'
            f'<a href="{GALLERY}/" target="_blank">'
            f'<img src="{ref}" loading="lazy" title="E16 reference"></a></div>'
            f'<details><summary>layout notes ({len(r.layout_notes)})</summary>'
            f"<ul>{notes}</ul></details></div>"
        )

    bucket_html = "".join(
        f"<li><b>{html.escape(k)}</b> — {v}</li>" for k, v in ranked_buckets
    ) or "<li>none 🎉</li>"
    noisy_html = "".join(
        f'<li><a href="#{html.escape(r.name)}">{html.escape(r.stem)}</a> '
        f"({len(r.layout_notes)} layout notes)</li>"
        for r in noisiest
    )
    page = f"""<!doctype html><meta charset="utf-8">
<title>themey corpus survey</title>
<style>
body {{ font: 14px system-ui; margin: 2rem; background: #16181d; color: #d7dae0; }}
h1, h2 {{ font-weight: 600; }}
a {{ color: #7ab4ff; }}
.card {{ background: #1e222a; border-radius: 8px; padding: 1rem; margin: 1rem 0; }}
.card h3 {{ margin: 0 0 .5rem; }}
.meta {{ color: #8b93a3; font-weight: 400; font-size: .85em; }}
.pair {{ display: flex; gap: 1rem; align-items: flex-start; flex-wrap: wrap; }}
.pair img {{ max-width: 460px; border-radius: 4px; background: #fff2; }}
.err {{ color: #ff8f8f; max-width: 460px; white-space: pre-wrap; }}
details {{ margin-top: .5rem; color: #aab2c0; }}
</style>
<h1>themey corpus survey</h1>
<p>{len(results)} themes · {len(ok)} converted+rendered · {len(errs)} failed</p>
<h2>Failure shapes (ranked)</h2><ul>{bucket_html}</ul>
<h2>Most-approximated themes</h2><ol>{noisy_html}</ol>
<h2>Gallery</h2>
{"".join(rows)}
"""
    path = out / "index.html"
    path.write_text(page, encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--corpus", type=Path,
        default=Path.home() / "Desktop" / "ethemes" / "e16",
    )
    ap.add_argument(
        "--out", type=Path,
        default=Path.home() / ".local" / "share" / "themey" / "survey",
    )
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--only", nargs="*", default=None)
    ap.add_argument("--no-render", action="store_true")
    args = ap.parse_args()

    do_render = not args.no_render
    if do_render and not available():
        print("render harness tools missing; falling back to --no-render")
        do_render = False

    out: Path = args.out
    for sub in ("renders", "reports", "errors"):
        (out / sub).mkdir(parents=True, exist_ok=True)

    themes = sorted(args.corpus.glob("*.etheme"))
    if args.only:
        themes = [t for t in themes if t.stem in set(args.only)]
    if args.limit:
        themes = themes[: args.limit]

    results: list[Result] = []
    for i, etheme in enumerate(themes, 1):
        name = slugify(etheme.stem)
        png = out / "renders" / f"{name}.png"
        err = out / "errors" / f"{name}.txt"
        if do_render and png.exists():
            r = Result(name=name, stem=etheme.stem, render=f"renders/{name}.png")
            report = out / "reports" / f"{name}.txt"
            if report.is_file():
                text = report.read_text(encoding="utf-8")
                r.layout_notes = [
                    line.lstrip("- ").strip()
                    for line in text.splitlines()
                    if line.startswith(("- composite:", "- aurorae_rc:"))
                ]
                r.note_count = sum(
                    1 for line in text.splitlines()
                    if line.lstrip().startswith("- ")
                )
            results.append(r)
            print(f"[{i}/{len(themes)}] {etheme.stem}: cached")
            continue
        if err.exists():
            results.append(
                Result(
                    name=name, stem=etheme.stem,
                    status="skipped-prior-error",
                    error=err.read_text(encoding="utf-8").strip().splitlines()[-1],
                )
            )
            print(f"[{i}/{len(themes)}] {etheme.stem}: prior error, skipped")
            continue
        r = survey_one(etheme, out, do_render)
        results.append(r)
        print(f"[{i}/{len(themes)}] {etheme.stem}: {r.status}"
              + (f" ({r.error})" if r.error else ""))

    (out / "survey.json").write_text(
        json.dumps([asdict(r) for r in results], indent=1), encoding="utf-8"
    )
    page = write_gallery(out, results)
    print(f"\nSurvey gallery: {page}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
