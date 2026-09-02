"""Plasma Global Theme (Look-and-Feel) bundle writer — the one-click install.

Format (byte-verified against an installed Look-and-Feel package):

    <lnf>/metadata.json                  KPackageStructure "Plasma/LookAndFeel",
                                          KPlugin.Id == the directory basename,
                                          X-Themey-Scale == theme.scale,
                                          X-Themey-WidgetStyle == the chosen Qt
                                          application style (only with
                                          ``--widget-style``)
    <lnf>/contents/defaults               double-bracket INI sections, one
                                          group per artifact this conversion
                                          actually deployed:
        [kdeglobals][General]  ColorScheme=<.colors stem>
        [kdeglobals][Icons]    Theme=<icon theme dir name> (only when the
                                          windowmatches icon theme shipped)
        [kdeglobals][KDE]      widgetStyle=<Qt style name> (only with
                                          ``--widget-style``; the key KDE's
                                          own Look-and-Feel bundles use)
        [kcminputrc][Mouse]    cursorTheme=<XCursor theme dir name>
        [Wallpaper]            Image=<wallpaper package Id, never a path>
        [kwinrc][org.kde.kdecoration2]  library= + theme=
        [plasmarc][Theme]      name=<Plasma Style package dir name> (last,
                                          matching the real third-party
                                          bundles on the reference machine)
    <lnf>/contents/previews/preview.png  optional, downscaled from the
                                          default wallpaper image

Every key is conditional on its artifact existing — a theme with no
wallpapers, no cursor art, or an unwritable preview source must not emit a
key that points at nothing (``plasma-apply-lookandfeel`` applies the whole
``defaults`` file with no partial-apply flag, so a dangling reference is not
a soft failure, it silently breaks whatever it names). Only the
``[kwinrc][org.kde.kdecoration2]`` group is unconditional: some deco backend
always installs.

The double bracket in ``"kdeglobals][General"`` is not a typo — it is one
section NAME containing a literal ``]``, the same trick ``generate/colors.py``
uses for ``[Colors:Header][Inactive]``. ``desktop_writer.write_desktop``
writes section strings verbatim, which is why it is used here rather than
``configparser``.

The bundle ``KPlugin.Id`` is ``slug.plugin_id(theme.name)`` — the SAME
string as the deco KPackage's own Id, in a different namespace
(``plasma/look-and-feel/`` vs ``kwin/decorations/``); see the naming
contract in CLAUDE.md. Callers therefore MUST NOT write the two packages to
sibling paths sharing a parent (a flat ``--output`` tree, for instance) —
``pipeline.py`` gives the bundle its own ``look-and-feel/`` subdirectory to
avoid exactly that collision.

Zero symlinks: unlike the XCursor theme (which legitimately uses them for
legacy name aliases), nothing here is ever a symlink — every artifact this
module references is named by its installed Id/path string, not by a link.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from themey.generate.desktop_writer import write_desktop
from themey.ir import Theme
from themey.kwin import PLUGINS
from themey.slug import plugin_id

log = logging.getLogger(__name__)

#: Longer side of the generated contents/previews/preview.png, in px.
#: "Keep it simple" per the brief — this is a thumbnail, not art.
PREVIEW_MAX_DIM = 512

#: ``--widget-style`` token -> the Qt application-style name, spelled the
#: way KDE's own Look-and-Feel bundles spell it in ``[kdeglobals][KDE]
#: widgetStyle``. The two built-in Qt styles plus Breeze are the ones
#: present on a stock Plasma install (Kvantum is a separate package and
#: needs its own theme, which themey does not generate); E16's flat
#: 3D-bevelled widgets read closest under ``Windows``. This map is the
#: single vocabulary: ``cli.WidgetStyle`` mirrors its keys and
#: ``apply.apply_full`` resolves through it.
WIDGET_STYLES: dict[str, str] = {
    "windows": "Windows",
    "fusion": "Fusion",
    "breeze": "Breeze",
}


def _qt_widget_style(widget_style: str | None) -> str | None:
    """Resolve a ``--widget-style`` token to its Qt style name.

    None (the default) means "leave the application style alone" — no
    stamp, no ``defaults`` key, and nothing for ``apply`` to write.
    """
    if widget_style is None:
        return None
    try:
        return WIDGET_STYLES[widget_style]
    except KeyError:
        raise ValueError(
            f"widget_style must be one of {sorted(WIDGET_STYLES)} "
            f"(got {widget_style!r})"
        ) from None


@dataclass(frozen=True)
class LookAndFeelBundle:
    """One written Look-and-Feel package — what the pipeline installs."""

    id: str
    dir: Path


def deco_defaults(theme_name: str, *, want_qml: bool, pkg_id: str) -> tuple[str, str]:
    """kwinrc ``[org.kde.kdecoration2]`` ``library``/``theme`` for this conversion.

    Mirrors exactly what ``apply.py`` writes for the same backend choice, so
    applying the bundle and running ``themey apply`` agree: the QML backend
    (``want_qml``) loads via the v1 plugin with the raw package Id as
    ``theme=``; the SVG-only case loads via the v2 plugin with Aurorae's
    ``__aurorae__svg__<name>`` theme string.
    """
    if want_qml:
        return PLUGINS["legacy"], pkg_id
    return PLUGINS["v2"], f"__aurorae__svg__{theme_name}"


def build_defaults_sections(
    *,
    color_scheme_stem: str | None,
    cursor_theme_name: str | None,
    default_wallpaper_id: str | None,
    deco_library: str,
    deco_theme: str,
    desktop_theme_name: str | None = None,
    icon_theme_name: str | None = None,
    widget_style: str | None = None,
) -> dict[str, dict[str, str]]:
    """Assemble the ``contents/defaults`` section map.

    Each conditional group is included only when its artifact argument is
    not None; the deco group is unconditional (some backend always
    installs). Order matches the byte-verified format census, with the
    Plasma Style group last as in real third-party bundles and the
    ``--widget-style`` group beside the other ``kdeglobals`` ones.

    Raises:
        ValueError: If ``widget_style`` is not a :data:`WIDGET_STYLES` key.
    """
    qt_style = _qt_widget_style(widget_style)
    sections: dict[str, dict[str, str]] = {}
    if color_scheme_stem is not None:
        sections["kdeglobals][General"] = {"ColorScheme": color_scheme_stem}
    if icon_theme_name is not None:
        sections["kdeglobals][Icons"] = {"Theme": icon_theme_name}
    if qt_style is not None:
        sections["kdeglobals][KDE"] = {"widgetStyle": qt_style}
    if cursor_theme_name is not None:
        sections["kcminputrc][Mouse"] = {"cursorTheme": cursor_theme_name}
    if default_wallpaper_id is not None:
        sections["Wallpaper"] = {"Image": default_wallpaper_id}
    sections["kwinrc][org.kde.kdecoration2"] = {
        "library": deco_library,
        "theme": deco_theme,
    }
    if desktop_theme_name is not None:
        sections["plasmarc][Theme"] = {"name": desktop_theme_name}
    return sections


def write_metadata_json(
    theme: Theme, lnf_dir: Path, *, widget_style: str | None = None,
) -> Path:
    """Write ``metadata.json``; ``lnf_dir``'s basename MUST be its own Id.

    Raises:
        ValueError: If ``widget_style`` is not a :data:`WIDGET_STYLES` key.
    """
    qt_style = _qt_widget_style(widget_style)
    meta = {
        "KPackageStructure": "Plasma/LookAndFeel",
        # themey's own stamp: the conversion scale, read back by
        # ``apply.py`` (``_read_theme_scale``) to size the E16 dragbar
        # panel it creates at ``scale_px(16)`` — the bundle is the one
        # artifact apply already opens, so the scale rides along here
        # rather than in a new file. Absent (pre-stamp bundles) → 2.
        "X-Themey-Scale": theme.scale,
        "KPlugin": {
            "Id": plugin_id(theme.name),
            "Name": f"{theme.display_name} (themey)",
            "Description": (
                f"E16 theme '{theme.display_name}' converted by themey — "
                "decoration, colors, wallpaper and cursors as one Plasma "
                "Global Theme"
            ),
            "Authors": [{"Name": theme.author or "unknown"}],
            "License": "GPL",
            "Version": "1.0",
        },
    }
    if qt_style is not None:
        # themey's second stamp: the Qt application style this conversion
        # chose, read back by ``apply.py`` (``_read_widget_style``), which
        # must write the kdeglobals key in the USER layer itself — the
        # bundle's own [kdeglobals][KDE] group lands in kdedefaults and an
        # explicit user-layer widgetStyle would shadow it. Absent when
        # --widget-style was not given: the style is then left alone.
        meta["X-Themey-WidgetStyle"] = qt_style
    lnf_dir.mkdir(parents=True, exist_ok=True)
    out = lnf_dir / "metadata.json"
    out.write_text(json.dumps(meta, indent=4, sort_keys=True) + "\n")
    return out


def write_preview(image_path: Path, out_path: Path, *, max_dim: int = PREVIEW_MAX_DIM) -> Path:
    """Downscale *image_path* into ``contents/previews/preview.png``.

    LANCZOS is the wallpaper carve-out from CLAUDE.md's NEAREST-by-default
    rule — this is photographic art, not a pixel-art border. Raises
    OSError/ValueError on an unreadable source; the caller treats that as
    non-fatal (see :func:`write`'s docstring).
    """
    with Image.open(image_path) as im:
        frame = im.convert("RGB")
        frame.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frame.save(out_path, format="PNG")
    return out_path


def write(
    theme: Theme,
    out_dir: Path,
    *,
    color_scheme_stem: str | None,
    cursor_theme_name: str | None,
    default_wallpaper_id: str | None,
    default_wallpaper_image: Path | None,
    deco_library: str,
    deco_theme: str,
    desktop_theme_name: str | None = None,
    icon_theme_name: str | None = None,
    widget_style: str | None = None,
) -> LookAndFeelBundle:
    """Write the Look-and-Feel bundle for *theme* under *out_dir*.

    ``out_dir``'s basename MUST be ``slug.plugin_id(theme.name)`` — Plasma
    matches Look-and-Feel packages by ``KPlugin.Id``, same contract as every
    other themey package. The keyword artifact args (color scheme, cursor
    theme, wallpaper, desktop theme) are each the id/name/path that
    ARTIFACT was actually installed as in THIS conversion — pass None for
    anything that wasn't (a theme with no wallpapers, no convertible
    cursor art, a failed Plasma Style, ...) so ``build_defaults_sections``
    omits the matching key rather than pointing at nothing.

    ``default_wallpaper_image`` is the source image (post-conversion, e.g. a
    wallpaper package's installed ``contents/images/<W>x<H>.<ext>``) used to
    generate the optional ``contents/previews/preview.png``; pass None to
    skip the preview entirely (no default wallpaper, or the caller chooses
    not to bother). A preview source that fails to open/convert is
    non-fatal: it appends a ``bundle:`` note to ``theme.notes`` and the
    bundle ships without ``contents/previews/``.

    ``widget_style`` is a :data:`WIDGET_STYLES` token (``themey convert
    --widget-style``) or None to leave the Qt application style alone. It
    is the one argument here that names no themey-installed artifact — it
    selects a style Plasma already ships — so it lands in BOTH files: the
    ``[kdeglobals][KDE]`` defaults group and the ``X-Themey-WidgetStyle``
    stamp ``apply`` reads.

    Raises:
        ValueError: If ``widget_style`` is not a :data:`WIDGET_STYLES` key.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    write_metadata_json(theme, out_dir, widget_style=widget_style)
    sections = build_defaults_sections(
        color_scheme_stem=color_scheme_stem,
        cursor_theme_name=cursor_theme_name,
        default_wallpaper_id=default_wallpaper_id,
        deco_library=deco_library,
        deco_theme=deco_theme,
        desktop_theme_name=desktop_theme_name,
        icon_theme_name=icon_theme_name,
        widget_style=widget_style,
    )
    contents_dir = out_dir / "contents"
    contents_dir.mkdir(parents=True, exist_ok=True)
    write_desktop(contents_dir / "defaults", sections)

    if default_wallpaper_image is not None:
        try:
            write_preview(
                default_wallpaper_image, contents_dir / "previews" / "preview.png"
            )
        except (OSError, ValueError) as exc:
            theme.notes.append(f"bundle: preview.png skipped: {exc}")

    log.info(
        "Look-and-Feel bundle %s: colors=%s cursors=%s wallpaper=%s",
        out_dir.name,
        color_scheme_stem is not None,
        cursor_theme_name is not None,
        default_wallpaper_id is not None,
    )
    return LookAndFeelBundle(id=plugin_id(theme.name), dir=out_dir)
