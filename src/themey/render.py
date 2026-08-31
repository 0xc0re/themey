"""Headless render harness — screenshot a theme inside a nested KWin.

``scripts/render_review.py`` is a mock approximation of Aurorae; this module
is the truth. It launches a private ``kwin_wayland --virtual`` session with
its own ``XDG_CONFIG_HOME`` / ``XDG_DATA_HOME`` / ``XDG_RUNTIME_DIR`` and a
private D-Bus session (so it never touches the live desktop or clashes with
the host's ``org.kde.KWin`` name), opens a Qt client window inside it, and
grabs the virtual framebuffer with ``spectacle -b -n``.

Mechanism:
  1. Copy the theme tree into ``$XDG_DATA_HOME/aurorae/themes/<name>/``.
  2. Write ``kwinrc`` selecting the Aurorae plugin (``legacy`` = the v1 QML
     plugin ``org.kde.kwin.aurorae``; ``v2`` = ``org.kde.kwin.aurorae.v2``,
     Plasma's default). Both clamp ``BorderLeft/Right/Bottom`` to the
     ``BorderSize`` bracket; ``--border-size`` selects it.
  3. ``dbus-run-session -- kwin_wayland --virtual --exit-with-session <script>``
     where the script starts ``kdialog`` and runs spectacle.
  4. Return the PNG path.

``--maximized`` is implemented via a ``kwinrulesrc`` force rule matched on
the kdialog window class, so no scripting/D-Bus round-trip is needed.
"""
from __future__ import annotations

import logging
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

from . import paths
from .kwin import (  # noqa: F401  (re-exported for callers/tests)
    BORDER_SIZE_BRACKETS,
    BORDER_SIZES,
    PLUGINS,
    recommended_border_size,
)
from .pipeline import convert

log = logging.getLogger(__name__)

REQUIRED_TOOLS: tuple[str, ...] = ("kwin_wayland", "dbus-run-session", "spectacle", "kdialog")

SCREEN_W = 900
SCREEN_H = 600
CLIENT_W = 520
CLIENT_H = 300
SETTLE_SECONDS = 3.0
TIMEOUT_SECONDS = 60


class RenderError(Exception):
    """The nested-KWin render could not be performed."""


def missing_tools() -> list[str]:
    """Names of required executables that are not on PATH."""
    return [t for t in REQUIRED_TOOLS if shutil.which(t) is None]


def available() -> bool:
    return not missing_tools()


def resolve_theme_dir(
    theme: str,
    *,
    scale: float,
    work: Path,
    qml: bool = False,
    upscale: str = "nearest",
) -> tuple[str, Path]:
    """Return ``(name, theme_dir)`` for a ``.etheme`` path or an installed name.

    With ``qml=True`` the name is the KPackage plugin id and the dir is the
    QML decoration package (converted with the qml backend, or found under
    ``kwin/decorations/``).
    """
    from .slug import plugin_id

    p = Path(theme)
    if p.suffix == ".etheme" or p.is_file():
        if not p.is_file():
            raise RenderError(f"no such file: {p}")
        result = convert(
            p, scale=scale, output_dir=work / "convert",
            backend="qml" if qml else "svg", upscale=upscale,
        )
        if qml:
            assert result.qml_plugin_id is not None
            assert result.qml_installed_dir is not None
            return result.qml_plugin_id, result.qml_installed_dir
        return result.theme_name, result.installed_dir
    if qml:
        pkg_id = theme if theme.startswith("themey_") else plugin_id(theme)
        pkg = paths.kwin_decorations() / pkg_id
        if (pkg / "metadata.json").is_file():
            return pkg_id, pkg
        raise RenderError(
            f"{theme!r} is neither a .etheme file nor an installed QML "
            f"decoration under {paths.kwin_decorations()}"
        )
    installed = paths.aurorae_themes() / theme
    if installed.is_dir():
        return theme, installed
    raise RenderError(
        f"{theme!r} is neither a .etheme file nor an installed theme "
        f"under {paths.aurorae_themes()}"
    )


def write_kwinrc(
    cfg_dir: Path,
    *,
    name: str,
    plugin: str,
    border_size: str,
    buttons: tuple[str, str] | None = None,
) -> Path:
    """Nested-session kwinrc. ``buttons`` is the theme's (L, R) binning from
    the installed rc's [Themey] section — the same layout ``themey apply``
    sets on the real desktop, so the harness screenshot shows what the user
    will get. Falls back to M / IAX when the theme has no opinion.

    ``plugin="qml"``: the v1 Aurorae library with the RAW package id as
    ``theme=`` (no ``__aurorae__svg__`` prefix), and neither ButtonsOn*
    nor BorderSize — the QML theme draws its own buttons and borders.
    """
    cfg_dir.mkdir(parents=True, exist_ok=True)
    kwinrc = cfg_dir / "kwinrc"
    if plugin == "qml":
        kwinrc.write_text(
            "[org.kde.kdecoration2]\n"
            f"library={PLUGINS['legacy']}\n"
            f"theme={name}\n"
            "\n[Compositing]\n"
            "Enabled=true\n",
            encoding="utf-8",
        )
        return kwinrc
    if plugin not in PLUGINS:
        raise RenderError(
            f"unknown plugin {plugin!r}; expected 'qml' or one of {sorted(PLUGINS)}"
        )
    if border_size not in BORDER_SIZES:
        raise RenderError(
            f"unknown border size {border_size!r}; expected one of {BORDER_SIZES}"
        )
    left, right = buttons if buttons is not None else ("M", "IAX")
    kwinrc.write_text(
        "[org.kde.kdecoration2]\n"
        f"library={PLUGINS[plugin]}\n"
        f"theme=__aurorae__svg__{name}\n"
        f"BorderSize={border_size}\n"
        "BorderSizeAuto=false\n"
        f"ButtonsOnLeft={left}\n"
        f"ButtonsOnRight={right}\n"
        "\n[Compositing]\n"
        "Enabled=true\n",
        encoding="utf-8",
    )
    return kwinrc


def write_kwinrulesrc(cfg_dir: Path, *, maximized: bool) -> Path | None:
    if not maximized:
        return None
    rules = cfg_dir / "kwinrulesrc"
    rules.write_text(
        "[General]\ncount=1\nrules=themey-maximized\n\n"
        "[themey-maximized]\n"
        "Description=themey render: maximize client\n"
        "wmclass=kdialog\nwmclassmatch=2\nwmclasscomplete=false\n"
        "maximizehoriz=true\nmaximizehorizrule=3\n"
        "maximizevert=true\nmaximizevertrule=3\n",
        encoding="utf-8",
    )
    return rules


def _session_script(work: Path, out: Path, log_path: Path) -> Path:
    script = work / "session.sh"
    script.write_text(
        "#!/bin/bash\n"
        f"exec >{_q(log_path)} 2>&1\n"
        'echo "WAYLAND_DISPLAY=$WAYLAND_DISPLAY"\n'
        "export QT_QPA_PLATFORM=wayland\n"
        "kdialog --title 'themey render' --textbox "
        f"{_q(work / 'body.txt')} {CLIENT_W} {CLIENT_H} &\n"
        f"sleep {SETTLE_SECONDS}\n"
        f"spectacle -b -n -o {_q(out)}\n"
        'echo "spectacle rc=$?"\n'
        "sleep 0.5\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    (work / "body.txt").write_text(
        "themey render harness\n\nThe quick brown fox jumps over the lazy dog.\n"
        * 6,
        encoding="utf-8",
    )
    return script


def _q(p: Path) -> str:
    return "'" + str(p).replace("'", "'\\''") + "'"


_QML_ERROR_MARKERS = ("qml", "qqmlapplicationengine")
_QML_ERROR_WORDS = ("error", "typeerror", "referenceerror", "syntax", "not found",
                    "failed", "binding loop")


def _qml_error_lines(text: str) -> list[str]:
    """Lines that look like QML load/eval failures (for RenderError detail)."""
    out: list[str] = []
    for line in text.splitlines():
        low = line.lower()
        if any(m in low for m in _QML_ERROR_MARKERS) and any(
            w in low for w in _QML_ERROR_WORDS
        ):
            out.append(line.strip())
    return out


def render(
    theme: str,
    *,
    out: Path | None = None,
    plugin: str = "legacy",
    border_size: str = "Normal",
    maximized: bool = False,
    scale: float = 2,
    upscale: str = "nearest",
    keep_work: bool = False,
) -> Path:
    """Render *theme* in a nested headless KWin and return the PNG path.

    Raises:
        RenderError: when a required tool is missing, the theme cannot be
            resolved, or the session produced no screenshot.
    """
    missing = missing_tools()
    if missing:
        raise RenderError(f"missing tools on PATH: {', '.join(missing)}")

    work = Path(tempfile.mkdtemp(prefix="themey-render-"))
    try:
        qml = plugin == "qml"
        name, theme_dir = resolve_theme_dir(
            theme, scale=scale, work=work, qml=qml, upscale=upscale
        )
        cfg = work / "config"
        data = work / "data"
        runtime = work / "runtime"
        runtime.mkdir(mode=0o700)
        if qml:
            shutil.copytree(theme_dir, data / "kwin" / "decorations" / name)
            buttons = None
        else:
            shutil.copytree(theme_dir, data / "aurorae" / "themes" / name)
            from themey.apply import buttons_for_installed

            buttons = buttons_for_installed(theme_dir, name)

        write_kwinrc(
            cfg,
            name=name,
            plugin=plugin,
            border_size=border_size,
            buttons=buttons,
        )
        write_kwinrulesrc(cfg, maximized=maximized)

        if out is None:
            suffix = f"-{plugin}-{border_size}" + ("-max" if maximized else "")
            out = paths.themey_previews() / f"{name}{suffix}.png"
        out = out.resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()

        session_log = work / "session.log"
        script = _session_script(work, out, session_log)

        env = dict(os.environ)
        env.update(
            XDG_CONFIG_HOME=str(cfg),
            XDG_DATA_HOME=str(data),
            XDG_RUNTIME_DIR=str(runtime),
            XDG_CACHE_HOME=str(work / "cache"),
        )
        for var in ("WAYLAND_DISPLAY", "DISPLAY", "DBUS_SESSION_BUS_ADDRESS"):
            env.pop(var, None)
        cmd = [
            "dbus-run-session", "--", "kwin_wayland", "--virtual", "--no-lockscreen",
            "--width", str(SCREEN_W), "--height", str(SCREEN_H),
            "--exit-with-session", str(script),
        ]
        log.info("render: %s (plugin=%s border=%s max=%s)", name, plugin, border_size, maximized)
        log.debug("render: %s", " ".join(cmd))
        try:
            proc = subprocess.run(
                cmd, env=env, cwd=work, capture_output=True, text=True,
                timeout=TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError(f"nested kwin_wayland timed out after {TIMEOUT_SECONDS}s") from exc
        qml_errors = _qml_error_lines(proc.stderr) + (
            _qml_error_lines(session_log.read_text(errors="replace"))
            if session_log.exists() else []
        )
        if not out.is_file() or out.stat().st_size == 0:
            tail = session_log.read_text(errors="replace")[-2000:] if session_log.exists() else ""
            qml_part = (
                "\nQML errors:\n" + "\n".join(qml_errors[:20]) if qml_errors else ""
            )
            raise RenderError(
                f"no screenshot produced (kwin rc={proc.returncode})."
                f"{qml_part}\n"
                f"session log:\n{tail}\nkwin stderr:\n{proc.stderr[-2000:]}"
            )
        if qml_errors:
            log.warning(
                "render: session reported %d QML error line(s); the "
                "decoration may be partially drawn:\n%s",
                len(qml_errors), "\n".join(qml_errors[:10]),
            )
        return out
    finally:
        if keep_work:
            log.info("render: work dir kept at %s", work)
        else:
            shutil.rmtree(work, ignore_errors=True)
