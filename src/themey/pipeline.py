"""Single-theme conversion pipeline.

Composes the four stages: ingest → analyze → generate → install + report
+ preview. The asset_root from archive.extract is valid ONLY inside the
``with extract(...)`` block, so all generate-stage work happens inside it.

Lifecycle invariant:
    ``raw.asset_root`` is valid only while the ``with extract(...)`` block
    is open. EVERYTHING that derives geometry runs INSIDE that block —
    ``build_theme``, ``write_aurorae``, and also ``report.write`` and
    ``preview.render``: since the measured-geometry work,
    ``strip_thicknesses``/``required_border_extents`` open the iclass
    images (opaque-span trims), so a report/preview generated after the
    block would silently compute geometry that disagrees with the
    installed SVG (``composite._zone_art_span`` warns when it detects a
    vanished image). Do NOT move any of these calls outside the ``with
    extract(...)`` block.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from . import external, install, paths
from .analyze.build_theme import build_theme
from .etheme.archive import extract
from .etheme.parse import parse_tree
from .generate import lookandfeel, plasmoids, qmldeco
from .generate.aurorae import write as write_aurorae
from .generate.colors import scheme_stem, write_colors
from .generate.cursors import CursorTheme
from .generate.cursors import write_theme as write_cursor_theme
from .generate.icons import IconThemeError
from .generate.icons import write_theme as write_icon_theme
from .generate.plasmastyle import ICONBOX_FRAME_MODES, PlasmaStyleError
from .generate.plasmastyle import write as write_plasma_style
from .generate.wallpaper import WallpaperError, WallpaperPackage
from .generate.wallpaper import pick_default as pick_default_wallpaper
from .generate.wallpaper import write_package as write_wallpaper_package
from .images.upscale import UPSCALE_MODES
from .ir import WallpaperSpec
from .preview import render as render_preview
from .report import write as write_report
from .slug import cursor_theme_dir, icon_theme_dir, plugin_id, slugify, wallpaper_id

log = logging.getLogger(__name__)

BACKENDS = ("svg", "qml", "both")


@dataclass(frozen=True)
class ConvertResult:
    """Result of a successful pipeline.convert() call."""

    theme_name: str
    installed_dir: Path
    preview_path: Path
    report_path: Path
    notes_count: int
    notes: tuple[str, ...] = ()
    """The full ``theme.notes`` list at the end of the convert — every
    fidelity note, unlike ``report.txt`` which truncates the unprefixed
    per-state bucket at 20 (``report.py``). ``scripts/batch_survey.py``
    reads this to histogram note patterns across the corpus."""
    installed: bool = True
    """False when ``output_dir`` was given: ``installed_dir`` is then the
    theme tree under that directory and nothing was written to XDG paths."""
    qml_installed_dir: Path | None = None
    """QML decoration package dir (backend 'qml'/'both'); None for 'svg'."""
    qml_plugin_id: str | None = None
    """KPlugin Id / kwinrc theme= value for the QML package."""
    color_scheme_path: Path | None = None
    """Installed ``themey_<slug>.colors`` (or the copy under ``output_dir``)."""
    wallpaper_dirs: tuple[Path, ...] = ()
    """One installed wallpaper package dir per convertible background image
    (or the copies under ``output_dir``). Images that fail to convert are
    skipped with a ``wallpaper:`` note rather than failing the convert."""
    icon_theme_dir: Path | None = None
    """Installed ``themey_<slug>-icons`` XDG icon theme (or the copy under
    ``output_dir``) from the theme's ``windowmatches.cfg`` ``__USE_ICON``
    rules; None when no rule matched an installed application (an
    ``icons:`` note says so)."""
    plasmoid_dirs: tuple[Path, ...] = ()
    """themey's own applet packages (``org.themey.pager``,
    ``org.themey.deskbutton`` — ``generate/plasmoids``), theme-agnostic and
    rewritten on every convert; under ``output_dir/plasmoids/`` in
    non-installing mode."""
    cursor_theme_dir: Path | None = None
    """Installed ``themey_<slug>-cursors`` XCursor theme (or the copy under
    ``output_dir``). None when the theme declares no ``__CURSOR`` blocks,
    xcursorgen is not on PATH, or no pointer could be converted — each
    leaves a ``cursors:`` note instead of failing the convert."""
    desktop_theme_dir: Path | None = None
    """Installed Plasma Style (desktop theme) package dir (or the copy
    under ``output_dir``). None when the style failed to build — a
    ``plasmastyle:`` note says why, and the convert still succeeds."""
    desktop_theme_id: str | None = None
    """Package dir name / ``plasmarc [Theme] name=`` value for the Plasma
    Style — the same ``themey_<slug>`` string as ``qml_plugin_id``, in yet
    another namespace (``plasma/desktoptheme/``)."""
    lnf_dir: Path | None = None
    """Installed Plasma Global Theme (Look-and-Feel) bundle dir (or the copy
    under ``output_dir``). Assembled LAST, from the artifact ids that
    actually deployed in this conversion — see ``generate/lookandfeel.py``.
    Always set on a successful convert (some deco backend always runs)."""
    lnf_id: str | None = None
    """``KPlugin.Id`` of the bundle above — same string as ``qml_plugin_id``
    (a different namespace), so ``themey apply <name>`` resolves either."""


def _default_wallpaper_image(pkg: WallpaperPackage | None) -> Path | None:
    """The installed image file for *pkg* (``pick_default``'s pick), or None.

    Feeds ``lookandfeel.write``'s optional preview.png source; only ever
    called on a package that already exists on disk at this point in the
    pipeline (staged or installed), so an empty ``images/`` glob would mean
    a ``write_wallpaper_package`` contract violation, not a normal case.
    """
    if pkg is None:
        return None
    images = sorted((pkg.dir / "contents" / "images").glob("*"))
    return images[0] if images else None


def convert(
    etheme_path: Path,
    *,
    scale: float = 2,
    output_dir: Path | None = None,
    backend: str = "qml",
    upscale: str = "nearest",
    shade_button: str = "maximize",
    iconbox_frames: str = "off",
    widget_style: str | None = None,
) -> ConvertResult:
    """Convert one .etheme to an installed KWin decoration + preview + report.

    Args:
        etheme_path: Path to a ``.etheme`` archive (gzipped tar).
        scale: Border/image upscale factor in [0.5, 3]; quantized to two
            decimals, int-valued floats normalized to int. Fractional
            values (every sub-1 value included) are accepted only with
            ``backend="qml"``. The 0.5 floor is deliberate: below it,
            1-px pixel-art features vanish entirely.
        output_dir: When given, skip the XDG install entirely and write the
            output tree(s) under ``output_dir`` plus ``<name>.report.txt``
            and ``<name>.html`` next to them. Nothing under
            ``~/.local/share`` is touched.
        backend: ``"qml"`` (default — the E16-faithful QML decoration
            package), ``"svg"`` (the legacy Aurorae SVG theme, kept as
            an escape hatch), or ``"both"``.
        upscale: Part-art scaler for the QML package: ``"nearest"``
            (default), ``"quality"`` (the in-tree hqx port) or
            ``"waifu2x"`` (the external waifu2x-ncnn-vulkan CNN). Both
            smoothing modes are QML-backend-only. ``"waifu2x"`` degrades
            to ``"quality"`` with an ``upscale:`` note when the binary or
            its model weights are missing, so it never fails a convert;
            the substitution is decided once, right after ``build_theme``,
            and the effective mode is what both the generator and the
            report see.
        shade_button: QML-backend-only remap for E16's shade button
            (KWin removed window shading in Plasma 6): one of
            ``qmldeco.SHADE_BUTTON_MODES`` — ``"maximize"`` (default),
            ``"keepAbove"``, ``"keepBelow"``, ``"menu"``, ``"hide"``, or
            ``"none"`` (today's inert disabled button). The SVG backend
            never consumes this flag, so any value is accepted regardless
            of ``backend``.
        iconbox_frames: Plasma Style task frames for the icon task
            manager: ``"off"`` (default — E16's own frameless iconbox,
            ``container.c`` ``draw_icon_base = 0``) or ``"on"`` (the
            iconbox button art as per-icon plates);
            ``plasmastyle.ICONBOX_FRAME_MODES``.
        widget_style: Qt application style for the Global Theme bundle to
            select — a ``lookandfeel.WIDGET_STYLES`` token
            (``"windows"``/``"fusion"``/``"breeze"``) — or None (default)
            to leave the user's application style alone. It names no
            themey artifact: it rides in the bundle's ``[kdeglobals][KDE]
            widgetStyle`` group and in the ``X-Themey-WidgetStyle`` stamp
            ``apply`` writes the user-layer key from.

    Returns:
        A :class:`ConvertResult`. ``installed_dir`` is the SVG theme dir
        when the SVG backend ran, else the QML package dir;
        ``qml_installed_dir``/``qml_plugin_id`` are set whenever the QML
        backend ran. ``color_scheme_path`` is the ``.colors`` file, which
        both backends share. ``wallpaper_dirs`` holds one entry per
        installed wallpaper package, and ``cursor_theme_dir`` the XCursor
        pointer theme (None when there was nothing to install).

    Raises:
        ValueError: If ``scale``, ``backend``, ``upscale``, ``shade_button``,
            ``iconbox_frames`` or ``widget_style`` is invalid.
        UnsafeArchiveError: If the archive fails safe-extract validation.
        InstallError: If the atomic install rename fails.
    """
    scale = round(float(scale), 2)
    if not 0.5 <= scale <= 3:
        raise ValueError(f"scale must be in [0.5, 3] (got {scale})")
    if scale == int(scale):
        scale = int(scale)
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {BACKENDS} (got {backend!r})")
    want_svg = backend in ("svg", "both")
    want_qml = backend in ("qml", "both")
    if want_svg and not isinstance(scale, int):
        raise ValueError(
            f"backend {backend!r} requires an integer scale (got {scale}); "
            "fractional --scale is QML-backend-only"
        )
    if upscale not in UPSCALE_MODES:
        raise ValueError(
            f"upscale must be one of {UPSCALE_MODES} (got {upscale!r})"
        )
    if want_svg and upscale != "nearest":
        raise ValueError(
            f"backend {backend!r} requires upscale 'nearest' "
            f"(got {upscale!r}); --upscale {upscale} is QML-backend-only"
        )
    if shade_button not in qmldeco.SHADE_BUTTON_MODES:
        raise ValueError(
            f"shade_button must be one of {qmldeco.SHADE_BUTTON_MODES} "
            f"(got {shade_button!r})"
        )
    if iconbox_frames not in ICONBOX_FRAME_MODES:
        raise ValueError(
            f"iconbox_frames must be one of {ICONBOX_FRAME_MODES} "
            f"(got {iconbox_frames!r})"
        )
    if widget_style is not None and widget_style not in lookandfeel.WIDGET_STYLES:
        raise ValueError(
            f"widget_style must be one of {sorted(lookandfeel.WIDGET_STYLES)} "
            f"(got {widget_style!r})"
        )

    # Theme name comes from the archive filename, never from cfg content.
    theme_name = slugify(etheme_path.stem)
    log.info("converting %s as %s (scale=%s)", etheme_path, theme_name, scale)

    with extract(etheme_path) as raw:
        log.debug("extracted to %s", raw.asset_root)
        ast_nodes = parse_tree(raw.asset_root)
        log.debug("parsed %d top-level AST nodes", len(ast_nodes))
        # ONE decision point for the whole run: waifu2x is the one mode
        # that can be unavailable at run time, so resolve it HERE — before
        # the Theme exists — and hand the EFFECTIVE mode to every
        # consumer, the Theme itself included (ir.Theme.upscale reaches
        # plasmastyle's builders and wallpaper.write_package). The scaler,
        # the shipped art and the report line can then never disagree. The
        # decision needs no Theme; only the note does, and `notes` is the
        # one mutable field, so it is appended immediately after.
        effective_upscale = upscale
        fallback_reason: str | None = None
        if upscale == "waifu2x":
            fallback_reason = external.waifu2x_unavailable_reason()
            if fallback_reason is not None:
                effective_upscale = "quality"
                log.warning(
                    "waifu2x unavailable, falling back to hqx: %s", fallback_reason
                )

        theme = build_theme(
            raw.asset_root,
            ast_nodes,
            name=theme_name,
            display_name=theme_name,
            scale=scale,
            upscale=effective_upscale,
        )
        if fallback_reason is not None:
            theme.notes.append(
                f"upscale: {fallback_reason} — part art upscaled with hqx instead"
            )

        log.info(
            "theme: parts=%d iclasses=%d notes=%d skipped=%d",
            len(theme.border.parts),
            len(theme.iclasses),
            len(theme.notes),
            len(theme.skipped_borders),
        )

        pkg_id = plugin_id(theme_name)
        colors_name = f"{scheme_stem(theme)}.colors"
        installed: Path | None = None
        qml_installed: Path | None = None
        colors_path: Path | None = None
        cursor_dir_name = cursor_theme_dir(theme_name)
        cursor_dir: Path | None = None
        cursor_theme: CursorTheme | None = None
        icons_dir_name = icon_theme_dir(theme_name)
        icons_dir: Path | None = None
        style_dir: Path | None = None
        style_id: str | None = None
        lnf_dir: Path | None = None
        plasmoid_dirs: list[Path] = []
        wallpaper_dirs: list[Path] = []
        # One WallpaperPackage per installed wallpaper_dirs entry (same
        # order), with `.dir` rebased to the FINAL installed/output
        # location — pick_default_wallpaper needs the real package to rank
        # by area, and lookandfeel's bundle needs its final image path.
        wallpaper_packages: list[WallpaperPackage] = []
        # Subset of theme.wallpaper_specs that actually made it to disk —
        # threaded into write_report so its status line can't overstate
        # what's installed when write_wallpaper_package fails partway
        # through (see report.write's wallpaper_specs docstring).
        installed_wallpaper_specs: list[WallpaperSpec] = []

        if output_dir is not None:
            # Non-installing mode: write straight into output_dir.
            output_dir.mkdir(parents=True, exist_ok=True)
            if want_svg:
                installed = output_dir / theme_name
                if installed.exists():
                    shutil.rmtree(installed)
                write_aurorae(theme, installed)
                log.info("wrote SVG theme tree to %s", installed)
            if want_qml:
                qml_installed = output_dir / pkg_id
                if qml_installed.exists():
                    shutil.rmtree(qml_installed)
                qmldeco.write(
                    theme, qml_installed, upscale=effective_upscale,
                    shade_button=shade_button,
                )
                log.info("wrote QML decoration package to %s", qml_installed)
            colors_path = write_colors(theme, output_dir / colors_name)
            log.info("wrote color scheme to %s", colors_path)
            for spec in theme.wallpaper_specs:
                wp_id = wallpaper_id(theme_name, spec.stem)
                wp_out = output_dir / wp_id
                if wp_out.exists():
                    shutil.rmtree(wp_out)
                try:
                    pkg = write_wallpaper_package(theme, spec, wp_out)
                except WallpaperError as exc:
                    theme.notes.append(
                        f"wallpaper: skipped {spec.stem}: {exc}"
                    )
                    continue
                wallpaper_dirs.append(wp_out)
                wallpaper_packages.append(pkg)  # pkg.dir == wp_out already
                installed_wallpaper_specs.append(spec)
                log.info("wrote wallpaper package to %s", wp_out)
            cursor_out = output_dir / cursor_dir_name
            if cursor_out.exists():
                shutil.rmtree(cursor_out)
            cursor_theme = write_cursor_theme(theme, cursor_out)
            if cursor_theme is not None:
                cursor_dir = cursor_out
                log.info("wrote cursor theme to %s", cursor_dir)
            icons_out = output_dir / icons_dir_name
            if icons_out.exists():
                shutil.rmtree(icons_out)
            try:
                icon_theme = write_icon_theme(theme, icons_out)
            except IconThemeError as exc:
                theme.notes.append(f"icons: skipped: {exc}")
                icon_theme = None
            if icon_theme is not None:
                icons_dir = icon_theme.dir
                log.info("wrote icon theme to %s", icons_dir)
            # The Plasma Style also lives under its own "desktoptheme/"
            # subdir — its dir name is again pkg_id (see the look-and-feel
            # comment below) and would collide with `qml_installed` flat.
            style_out = output_dir / "desktoptheme" / pkg_id
            if style_out.exists():
                shutil.rmtree(style_out)
            try:
                style = write_plasma_style(theme, style_out, iconbox_frames=iconbox_frames)
            except PlasmaStyleError as exc:
                theme.notes.append(f"plasmastyle: skipped: {exc}")
            else:
                style_dir = style.dir
                style_id = style.id
                log.info("wrote Plasma Style to %s", style_dir)
            # themey's applets: theme-agnostic, so the same bytes every
            # time; their own "plasmoids/" subdir keeps the survey's
            # home-check tree shape identical to the install layout.
            plasmoids_out = output_dir / "plasmoids"
            for pkg_id_applet in plasmoids.PLASMOID_IDS:
                if (plasmoids_out / pkg_id_applet).exists():
                    shutil.rmtree(plasmoids_out / pkg_id_applet)
            for applet in plasmoids.write_all(plasmoids_out):
                plasmoid_dirs.append(applet.dir)
                log.info("wrote applet package to %s", applet.dir)

            # LAST: assemble the Global Theme bundle from the ids that
            # actually deployed above, never from theme analysis — a
            # wallpaper that failed to convert must not be referenced.
            # It lives under a "look-and-feel/" subdir, not output_dir
            # directly: its Id is deliberately the same string as pkg_id
            # (the QML package's own dirname), which would otherwise
            # collide with `qml_installed` in this flat --output tree.
            default_wp = pick_default_wallpaper(wallpaper_packages)
            deco_library, deco_theme = lookandfeel.deco_defaults(
                theme_name, want_qml=want_qml, pkg_id=pkg_id
            )
            lnf_out = output_dir / "look-and-feel" / pkg_id
            if lnf_out.exists():
                shutil.rmtree(lnf_out)
            bundle = lookandfeel.write(
                theme,
                lnf_out,
                color_scheme_stem=colors_path.stem if colors_path else None,
                cursor_theme_name=cursor_theme.name if cursor_theme else None,
                default_wallpaper_id=default_wp.id if default_wp else None,
                default_wallpaper_image=_default_wallpaper_image(default_wp),
                deco_library=deco_library,
                deco_theme=deco_theme,
                desktop_theme_name=style_id,
                icon_theme_name=icons_dir.name if icons_dir is not None else None,
                widget_style=widget_style,
            )
            lnf_dir = bundle.dir
            log.info("wrote Look-and-Feel bundle to %s", lnf_dir)
            previews = output_dir
        else:
            # Stage outputs under XDG_DATA_HOME so os.replace can rename
            # atomically into their final positions on the same filesystem.
            staging_root = paths.themey_previews().parent / "staging"
            staging_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=f"{theme_name}-",
                dir=str(staging_root),
            ) as stage_str:
                stage = Path(stage_str)
                if want_svg:
                    stage_theme_dir = stage / theme_name
                    write_aurorae(theme, stage_theme_dir)
                    log.debug("wrote Aurorae output to %s", stage_theme_dir)
                    # Atomic install: renames stage_theme_dir into final
                    # position; it no longer exists in the stage afterwards.
                    installed = install.deploy(theme_name, stage_theme_dir)
                    log.info("installed SVG theme to %s", installed)
                if want_qml:
                    stage_pkg_dir = stage / pkg_id
                    qmldeco.write(
                        theme, stage_pkg_dir, upscale=effective_upscale,
                        shade_button=shade_button,
                    )
                    log.debug("wrote QML package to %s", stage_pkg_dir)
                    qml_installed = install.deploy(
                        pkg_id, stage_pkg_dir,
                        target_root=paths.kwin_decorations(),
                    )
                    log.info("installed QML decoration to %s", qml_installed)
                stage_colors = stage / colors_name
                write_colors(theme, stage_colors)
                colors_path = install.deploy_file(
                    colors_name, stage_colors, target_root=paths.color_schemes()
                )
                log.info("installed color scheme to %s", colors_path)
                for spec in theme.wallpaper_specs:
                    wp_id = wallpaper_id(theme_name, spec.stem)
                    stage_wp_dir = stage / wp_id
                    try:
                        pkg = write_wallpaper_package(theme, spec, stage_wp_dir)
                    except WallpaperError as exc:
                        theme.notes.append(
                            f"wallpaper: skipped {spec.stem}: {exc}"
                        )
                        continue
                    installed_wp = install.deploy(
                        wp_id, stage_wp_dir, target_root=paths.wallpapers()
                    )
                    wallpaper_dirs.append(installed_wp)
                    # Rebase pkg.dir from the (now gone) stage path to the
                    # final installed one — the bundle's preview.png source
                    # must resolve after this pipeline call returns.
                    wallpaper_packages.append(
                        WallpaperPackage(
                            id=pkg.id,
                            dir=installed_wp,
                            width=pkg.width,
                            height=pkg.height,
                            fill_mode=pkg.fill_mode,
                            solid=pkg.solid,
                        )
                    )
                    installed_wallpaper_specs.append(spec)
                    log.info("installed wallpaper package to %s", installed_wp)
                stage_cursor_dir = stage / cursor_dir_name
                cursor_theme = write_cursor_theme(theme, stage_cursor_dir)
                if cursor_theme is not None:
                    cursor_dir = install.deploy(
                        cursor_dir_name, stage_cursor_dir,
                        target_root=paths.cursor_themes(),
                    )
                    log.info("installed cursor theme to %s", cursor_dir)
                stage_icons_dir = stage / icons_dir_name
                try:
                    icon_theme = write_icon_theme(theme, stage_icons_dir)
                except IconThemeError as exc:
                    theme.notes.append(f"icons: skipped: {exc}")
                    icon_theme = None
                if icon_theme is not None:
                    icons_dir = install.deploy(
                        icons_dir_name, stage_icons_dir,
                        target_root=paths.icon_themes(),
                    )
                    log.info("installed icon theme to %s", icons_dir)
                # Staged under "desktoptheme/" for the same pkg_id
                # collision reason as "look-and-feel/" below.
                stage_style_dir = stage / "desktoptheme" / pkg_id
                try:
                    style = write_plasma_style(
                        theme, stage_style_dir, iconbox_frames=iconbox_frames
                    )
                except PlasmaStyleError as exc:
                    theme.notes.append(f"plasmastyle: skipped: {exc}")
                else:
                    style_dir = install.deploy(
                        pkg_id, stage_style_dir,
                        target_root=paths.desktop_themes(),
                    )
                    # The kcache is keyed by the package Version, which a
                    # re-convert never bumps — clear it here too so a
                    # re-convert WITHOUT a re-apply refreshes the panel art
                    # (apply clears it again before repainting).
                    install.clear_style_cache(pkg_id)
                    style_id = style.id
                    log.info("installed Plasma Style to %s", style_dir)
                # themey's own applets, right after the style they read
                # their art from; overwritten atomically on every convert
                # (theme-agnostic, so a re-convert of ANY theme refreshes
                # the runtime for the panels apply created).
                for applet in plasmoids.write_all(stage / "plasmoids"):
                    installed_applet = install.deploy(
                        applet.id, applet.dir, target_root=paths.plasmoids()
                    )
                    plasmoid_dirs.append(installed_applet)
                    log.info("installed applet package to %s", installed_applet)

                # LAST: assemble + install the Global Theme bundle from the
                # ids that actually deployed above (see the output_dir
                # branch's comment for why "look-and-feel/" namespaces the
                # staging path — same pkg_id collision, this time against
                # stage_pkg_dir).
                default_wp = pick_default_wallpaper(wallpaper_packages)
                deco_library, deco_theme = lookandfeel.deco_defaults(
                    theme_name, want_qml=want_qml, pkg_id=pkg_id
                )
                stage_lnf_dir = stage / "look-and-feel" / pkg_id
                lookandfeel.write(
                    theme,
                    stage_lnf_dir,
                    color_scheme_stem=colors_path.stem if colors_path else None,
                    cursor_theme_name=cursor_theme.name if cursor_theme else None,
                    default_wallpaper_id=default_wp.id if default_wp else None,
                    default_wallpaper_image=_default_wallpaper_image(default_wp),
                    deco_library=deco_library,
                    deco_theme=deco_theme,
                    desktop_theme_name=style_id,
                    icon_theme_name=icons_dir.name if icons_dir is not None else None,
                    widget_style=widget_style,
                )
                lnf_dir = install.deploy(
                    pkg_id, stage_lnf_dir, target_root=paths.look_and_feel()
                )
                log.info("installed Look-and-Feel bundle to %s", lnf_dir)
            previews = paths.themey_previews()

        # Report and preview MUST run inside the extract block: they call
        # strip_thicknesses, which measures iclass images (opaque-span
        # trims). See lifecycle invariant in module docstring.
        previews.mkdir(parents=True, exist_ok=True)
        report_path = write_report(
            theme,
            previews / f"{theme_name}.report.txt",
            backend=backend,
            upscale=effective_upscale,
            wallpaper_specs=tuple(installed_wallpaper_specs),
            cursor_theme=cursor_theme,
            lnf_id=pkg_id,
            lnf_dir=lnf_dir,
            desktop_theme_id=style_id,
        )
        preview_path = render_preview(theme, previews / f"{theme_name}.html")

    primary = installed if installed is not None else qml_installed
    assert primary is not None  # at least one backend always runs
    return ConvertResult(
        theme_name=theme_name,
        installed_dir=primary,
        preview_path=preview_path,
        report_path=report_path,
        notes_count=len(theme.notes),
        notes=tuple(theme.notes),
        installed=output_dir is None,
        qml_installed_dir=qml_installed,
        qml_plugin_id=pkg_id if want_qml else None,
        color_scheme_path=colors_path,
        wallpaper_dirs=tuple(wallpaper_dirs),
        plasmoid_dirs=tuple(plasmoid_dirs),
        cursor_theme_dir=cursor_dir,
        icon_theme_dir=icons_dir,
        desktop_theme_dir=style_dir,
        desktop_theme_id=style_id,
        lnf_dir=lnf_dir,
        lnf_id=pkg_id,
    )
