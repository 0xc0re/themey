"""Visual review loop — mock or live screenshot for a themey-installed theme.

Two modes:

* **Mock (default)**: render a QML-faithful approximation via
  ``scripts/render_review.py`` and write ``/tmp/themey_review/<theme>.png``.
  No KDE plumbing involved — fast, deterministic, no side effects.

* **Live (--live)**: swap the active KWin window decoration to ``<theme>``,
  capture a screenshot of a real KWin-rendered window, then revert to Breeze.
  Wrapped in ``try/finally`` so an interrupted run still restores the user's
  baseline decoration.

Usage:
    uv run python scripts/visual_review.py <theme> [W H]            # mock
    uv run python scripts/visual_review.py <theme> --live [W H]     # live

Live mode needs (in PATH):
    * ``kwriteconfig6`` (apply ``kwinrc`` ``theme`` key)
    * ``qdbus6 org.kde.KWin /KWin reconfigure``
    * one of ``spectacle -b -n``, ``grim``, or ``scrot`` for capture

Output:
    /tmp/themey_review/<theme>.png         (mock mode)
    /tmp/themey_review/<theme>.live.png    (live mode)
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path


def _which(*names: str) -> str | None:
    for n in names:
        p = shutil.which(n)
        if p:
            return p
    return None


def _apply_aurorae_theme(theme_name: str) -> None:
    """Apply <theme_name> as the active KWin Aurorae decoration."""
    kw = _which("kwriteconfig6", "kwriteconfig5")
    if kw is None:
        raise SystemExit("kwriteconfig6 not found on PATH")
    subprocess.run(
        [
            kw, "--file", "kwinrc",
            "--group", "org.kde.kdecoration2",
            "--key", "library", "org.kde.kwin.aurorae",
        ],
        check=True,
    )
    subprocess.run(
        [
            kw, "--file", "kwinrc",
            "--group", "org.kde.kdecoration2",
            "--key", "theme", f"__aurorae__svg__{theme_name}",
        ],
        check=True,
    )
    qdbus = _which("qdbus6", "qdbus-qt6", "qdbus")
    if qdbus is None:
        raise SystemExit("qdbus6 not found on PATH")
    subprocess.run([qdbus, "org.kde.KWin", "/KWin", "reconfigure"], check=True)


def _capture_screenshot(out: Path) -> bool:
    """Capture the active window to ``out``. Returns True on success."""
    out.parent.mkdir(parents=True, exist_ok=True)
    spectacle = _which("spectacle")
    if spectacle:
        # -b: no notification; -n: no GUI; -a: active window
        r = subprocess.run(
            [spectacle, "-b", "-n", "-a", "-o", str(out)],
            capture_output=True,
        )
        if r.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            return True
    grim = _which("grim")
    if grim:
        r = subprocess.run([grim, str(out)], capture_output=True)
        if r.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            return True
    scrot = _which("scrot")
    if scrot:
        r = subprocess.run([scrot, "-u", str(out)], capture_output=True)
        if r.returncode == 0 and out.is_file() and out.stat().st_size > 0:
            return True
    return False


def _live_review(theme_name: str) -> Path:
    out = Path("/tmp/themey_review") / f"{theme_name}.live.png"
    print(f"Applying {theme_name} ...", file=sys.stderr)
    try:
        _apply_aurorae_theme(theme_name)
        # KWin needs a beat to reconfigure and repaint.
        time.sleep(1.5)
        print(f"Capturing screenshot ...", file=sys.stderr)
        if not _capture_screenshot(out):
            raise SystemExit(
                "screenshot tools (spectacle/grim/scrot) all failed — install one"
            )
    finally:
        print("Reverting to Breeze ...", file=sys.stderr)
        kw = _which("kwriteconfig6", "kwriteconfig5")
        if kw is not None:
            subprocess.run(
                [
                    kw, "--file", "kwinrc",
                    "--group", "org.kde.kdecoration2",
                    "--key", "library", "org.kde.breeze",
                ],
                check=False,
            )
            subprocess.run(
                [
                    kw, "--file", "kwinrc",
                    "--group", "org.kde.kdecoration2",
                    "--key", "theme", "Breeze",
                ],
                check=False,
            )
            qdbus = _which("qdbus6", "qdbus-qt6", "qdbus")
            if qdbus is not None:
                subprocess.run(
                    [qdbus, "org.kde.KWin", "/KWin", "reconfigure"],
                    check=False,
                )
    return out


def _mock_review(theme_name: str, w: int, h: int) -> Path:
    """Delegate to render_review.render; no external tools required."""
    sys.path.insert(0, str(Path(__file__).parent))
    import render_review  # type: ignore[import-not-found]

    return render_review.render(theme_name, w, h)


def main() -> None:
    argv = sys.argv[1:]
    live = False
    if "--live" in argv:
        live = True
        argv.remove("--live")
    if not argv:
        print(__doc__)
        raise SystemExit(2)

    name = argv[0]
    w = int(argv[1]) if len(argv) > 1 else 1000
    h = int(argv[2]) if len(argv) > 2 else 700

    out = _live_review(name) if live else _mock_review(name, w, h)
    print(out)


if __name__ == "__main__":
    main()
