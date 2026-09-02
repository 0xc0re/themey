"""Theme-name sanitizer for output paths.

Reduces to [A-Za-z0-9_-]+; rejects names that resolve to empty or all-dots.

Theme names come from archive filenames; cfg-content ``__NAME`` blocks must
NEVER reach output paths.
"""
from __future__ import annotations

import re

_SAFE_RE = re.compile(r"[^A-Za-z0-9_-]+")
_COLLAPSE_HYPHENS_RE = re.compile(r"-{2,}")
_ETHEME_SUFFIX_RE = re.compile(r"\.etheme$", re.IGNORECASE)


def slugify(name: str) -> str:
    """Reduce to [A-Za-z0-9_-]+; reject names that resolve to empty or '.'/'..'.

    Removes leading dots (no ``.hidden_evil``). Strips ``.etheme`` suffix.
    Replaces all other non-allowed chars with hyphens. Collapses runs of
    hyphens. Result MUST be safe to use in any filesystem path.
    """
    if not isinstance(name, str):
        raise TypeError(f"theme name must be str, got {type(name)}")
    # Strip .etheme suffix if present
    n = _ETHEME_SUFFIX_RE.sub("", name)
    # Strip path components — basename only (handles ../etc and ..\etc)
    n = n.split("/")[-1].split("\\")[-1]
    # Strip leading dots so we never get .hidden_evil
    n = n.lstrip(".")
    # Replace any non-allowed run with single hyphen
    n = _SAFE_RE.sub("-", n)
    # Collapse runs of hyphens
    n = _COLLAPSE_HYPHENS_RE.sub("-", n)
    # Trim hyphens at edges
    n = n.strip("-")
    if not n or set(n) == {"-"}:
        raise ValueError(f"theme name reduces to empty after sanitization: {name!r}")
    return n


def plugin_id(name: str) -> str:
    """KPlugin Id for the QML decoration package: ``themey_<slug>``.

    Hyphens become underscores — the id doubles as the package directory
    name under ``kwin/decorations/`` and as the kwinrc ``theme=`` value,
    and a single-token identifier avoids any KPackage id quoting concerns.
    """
    return "themey_" + slugify(name).replace("-", "_")


def wallpaper_id(name: str, stem: str) -> str:
    """KPlugin Id for one wallpaper package: ``themey_<slug>_<stem-slug>``.

    Unlike :func:`plugin_id`, hyphens are left as-is — wallpaper package
    ids are never used as QML/JS identifiers, only as directory names and
    ``KPlugin.Id`` values, so there's no reason to mangle them further.
    """
    return f"themey_{slugify(name)}_{slugify(stem)}"


def icon_theme_dir(name: str) -> str:
    """Directory name for the per-app icon theme: ``themey_<slug>-icons``.

    Like :func:`cursor_theme_dir`, an XDG icon theme has no KPlugin id —
    the directory name under ``icons/`` IS the kdeglobals ``[Icons]
    Theme=`` value. The ``-icons`` suffix keeps it apart from the cursor
    theme, which lives in a different root (``~/.icons``).
    """
    return f"themey_{slugify(name)}-icons"


def cursor_theme_dir(name: str) -> str:
    """Directory name for the XCursor theme: ``themey_<slug>-cursors``.

    XCursor themes have no KPlugin id — the directory name under
    ``icons/`` *is* the theme name that ``kcminputrc``'s ``cursorTheme=``
    refers to, so this string is the whole contract. The ``-cursors``
    suffix keeps it distinct from the decoration package, which shares the
    ``themey_<slug>`` prefix in a different namespace.
    """
    return f"themey_{slugify(name)}-cursors"
