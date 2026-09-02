"""E16 ``windowmatches.cfg`` ``__USE_ICON`` rules → a per-app XDG icon theme.

Output layout (the freedesktop icon-theme spec, verified against the
third-party themes under ``~/.local/share/icons`` on the reference
machine):

    <themey_<slug>-icons>/index.theme             [Icon Theme] Name= +
                                                   Inherits=breeze,hicolor +
                                                   Directories=48x48/apps
    <themey_<slug>-icons>/48x48/apps/<Icon>.png   one PNG per matched app

Contract: the theme's own art replaces the icon of every application whose
``.desktop`` entry an E16 rule matches; everything else falls through
``Inherits`` to Breeze. ``Inherits`` is STATIC — the user's current icon
theme is restored on revert (``apply.py`` ``PrevIconTheme``), and
``--output-dir``/survey runs have no user to read it from.

Matching (E16 ``regex.c:29-35``: plain ``fnmatch``, flags 0 →
``fnmatch.fnmatchcase``): a ``class`` rule matches ``StartupWMClass=``
when present, else the desktop file's stem; a ``name`` rule matches the
``Exec=`` argv0 basename, else the stem; a ``title`` rule matches
``Name=`` (approximate — E16 saw the live window title; noted). First
rule wins per icon name. ``.desktop`` files are read with a hand-rolled
parser: localized keys (``Name[de]=``) look like section headers to
configparser and ``%`` in ``Exec=`` trips its interpolation. Entries with
an absolute-path ``Icon=`` are skipped (an icon theme cannot shadow a
path), as are entries without ``Icon=``.

Yield is low by design — 11/223 corpus themes carry ``__USE_ICON``
rules, five of them working ones, and each rule needs a matching
``.desktop`` file on the box (Sensible's ``XTerm`` → ``debian-xterm``) —
chris opted in with that known (2026-09-01). Art is fitted into 48×48
with NEAREST (E16's iconbox default ``iconsize = 48``; pixel art stays
pixel art).
"""
from __future__ import annotations

import fnmatch
import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from themey.ir import IconMatchSpec, Theme
from themey.slug import icon_theme_dir

log = logging.getLogger(__name__)

INHERITS = "breeze,hicolor"
ICON_SIZE = 48
_ICON_SUFFIXES = (".png", ".svg", ".svgz", ".xpm")


class IconThemeError(Exception):
    """The icon theme could not be written."""


@dataclass(frozen=True)
class IconTheme:
    """One written icon theme: its directory name IS the kdeglobals
    ``[Icons] Theme=`` value."""

    name: str
    dir: Path
    icons: tuple[str, ...]


@dataclass(frozen=True)
class DesktopEntry:
    path: Path
    name: str
    icon: str
    exec_argv0: str
    wm_class: str

    @property
    def stem(self) -> str:
        return self.path.stem


def applications_dirs() -> list[Path]:
    """Where ``.desktop`` files live, user layer first, then
    ``$XDG_DATA_DIRS`` (default ``/usr/local/share:/usr/share``); read at
    call time so tests can monkeypatch the environment (the ``paths.py``
    rule)."""
    home = Path(os.environ.get("HOME", "/"))
    data_home = os.environ.get("XDG_DATA_HOME") or str(home / ".local" / "share")
    dirs = [Path(data_home) / "applications"]
    data_dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    for d in data_dirs.split(":"):
        if d:
            dirs.append(Path(d) / "applications")
    return dirs


def read_desktop_entry(path: Path) -> DesktopEntry | None:
    """The ``[Desktop Entry]`` group's unlocalized ``Name``/``Icon``/
    ``Exec``/``StartupWMClass``, or None for an unreadable file or one
    without ``Icon=``."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    in_group = False
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            in_group = line == "[Desktop Entry]"
            continue
        if not in_group or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if "[" in key:
            continue  # localized key
        values.setdefault(key, value.strip())
    icon = values.get("Icon", "")
    if not icon:
        return None
    exec_line = values.get("Exec", "")
    argv0 = exec_line.split()[0] if exec_line.split() else ""
    return DesktopEntry(
        path=path,
        name=values.get("Name", ""),
        icon=icon,
        exec_argv0=Path(argv0).name if argv0 else "",
        wm_class=values.get("StartupWMClass", ""),
    )


def scan_desktop_entries(dirs: list[Path] | None = None) -> list[DesktopEntry]:
    """Every readable ``.desktop`` entry with an ``Icon=``, user dirs
    first; a file seen in an earlier dir shadows the same basename later
    (the XDG override rule)."""
    seen: set[str] = set()
    out: list[DesktopEntry] = []
    for d in dirs if dirs is not None else applications_dirs():
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*.desktop")):
            rel = str(path.relative_to(d))
            if rel in seen:
                continue
            seen.add(rel)
            entry = read_desktop_entry(path)
            if entry is not None:
                out.append(entry)
    return out


def _candidates(spec: IconMatchSpec, entry: DesktopEntry) -> tuple[str, ...]:
    if spec.kind == "class":
        return (entry.wm_class,) if entry.wm_class else (entry.stem,)
    if spec.kind == "name":
        return (entry.exec_argv0,) if entry.exec_argv0 else (entry.stem,)
    return (entry.name,)


def match_rule(spec: IconMatchSpec, entries: list[DesktopEntry]) -> list[DesktopEntry]:
    """The entries *spec* matches (``fnmatchcase`` — E16 passed flags 0)."""
    return [
        e for e in entries
        if any(c and fnmatch.fnmatchcase(c, spec.pattern) for c in _candidates(spec, e))
    ]


def _icon_name(icon: str) -> str | None:
    """The theme-lookup name for an ``Icon=`` value: None for an absolute
    path (an icon theme cannot shadow it), the value minus a
    ``.png``/``.svg`` suffix otherwise."""
    if icon.startswith("/") or "/" in icon:
        return None
    for suffix in _ICON_SUFFIXES:
        if icon.endswith(suffix):
            return icon[: -len(suffix)]
    return icon


def fit_icon(source: Path, size: int = ICON_SIZE) -> Image.Image:
    """*source* fitted into a transparent ``size``×``size`` canvas with
    NEAREST (pixel art stays pixel art), aspect kept, centred."""
    with Image.open(source) as im:
        rgba = im.convert("RGBA")
    w, h = rgba.size
    if w == 0 or h == 0:
        raise IconThemeError(f"{source.name} is empty")
    factor = min(size / w, size / h)
    new_w = max(1, round(w * factor))
    new_h = max(1, round(h * factor))
    fitted = rgba.resize((new_w, new_h), Image.Resampling.NEAREST)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    canvas.paste(fitted, ((size - new_w) // 2, (size - new_h) // 2))
    return canvas


def write_theme(
    theme: Theme, out_dir: Path, *, entries: list[DesktopEntry] | None = None
) -> IconTheme | None:
    """Write the icon theme for *theme* under *out_dir*.

    ``out_dir``'s basename MUST be ``slug.icon_theme_dir(theme.name)`` —
    the directory name is the ``[Icons] Theme=`` value. Returns None
    (leaving no directory behind) when the theme has no usable
    ``__USE_ICON`` rules or none of them matches an installed
    application; every outcome appends an ``icons:`` note.
    """
    expected = icon_theme_dir(theme.name)
    if out_dir.name != expected:
        raise IconThemeError(
            f"out_dir basename must be {expected!r} (got {out_dir.name!r})"
        )
    if not theme.icon_matches:
        theme.notes.append(
            "icons: no usable __USE_ICON window matches; the icon theme is "
            "left alone"
        )
        return None
    if entries is None:
        entries = scan_desktop_entries()
    chosen: dict[str, tuple[IconMatchSpec, DesktopEntry]] = {}
    for spec in theme.icon_matches:
        hits = match_rule(spec, entries)
        if not hits:
            theme.notes.append(
                f"icons: {spec.kind} rule {spec.pattern!r} → {spec.image.name} "
                "matches no installed application (.desktop file); skipped"
            )
            continue
        for entry in hits:
            icon = _icon_name(entry.icon)
            if icon is None:
                theme.notes.append(
                    f"icons: {entry.path.name} uses an absolute Icon= path; "
                    "an icon theme cannot replace it"
                )
                continue
            if icon in chosen:
                continue  # first rule wins
            chosen[icon] = (spec, entry)
        if spec.kind == "title":
            theme.notes.append(
                f"icons: title rule {spec.pattern!r} matched on the launcher "
                "Name= (E16 matched the live window title — approximate)"
            )
    if not chosen:
        theme.notes.append(
            f"icons: {len(theme.icon_matches)} __USE_ICON rule(s) matched no "
            "installed application; no icon theme written"
        )
        return None

    apps = out_dir / f"{ICON_SIZE}x{ICON_SIZE}" / "apps"
    try:
        apps.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for icon, (spec, entry) in sorted(chosen.items()):
            try:
                fit_icon(spec.image).save(apps / f"{icon}.png", format="PNG")
            except (OSError, ValueError, IconThemeError) as exc:
                theme.notes.append(
                    f"icons: {spec.image.name} could not be converted ({exc}); "
                    f"{entry.path.name} keeps its stock icon"
                )
                continue
            written.append(icon)
            theme.notes.append(
                f"icons: {entry.path.name} ({icon}) wears {spec.image.name} "
                f"({spec.kind} rule {spec.pattern!r})"
            )
        if not written:
            shutil.rmtree(out_dir, ignore_errors=True)
            return None
        (out_dir / "index.theme").write_text(
            "[Icon Theme]\n"
            f"Name={theme.display_name} (themey)\n"
            f"Comment=E16 theme '{theme.display_name}' application icons "
            "from windowmatches.cfg, converted by themey\n"
            f"Inherits={INHERITS}\n"
            f"Directories={ICON_SIZE}x{ICON_SIZE}/apps\n"
            "\n"
            f"[{ICON_SIZE}x{ICON_SIZE}/apps]\n"
            f"Size={ICON_SIZE}\n"
            "Context=Applications\n"
            "Type=Fixed\n",
            encoding="utf-8",
        )
    except OSError as exc:
        shutil.rmtree(out_dir, ignore_errors=True)
        raise IconThemeError(f"could not write icon theme {expected}: {exc}") from exc
    log.info("icon theme %s: %d icon(s) (%s)", expected, len(written), ", ".join(written))
    return IconTheme(name=expected, dir=out_dir, icons=tuple(written))
