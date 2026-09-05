"""themey CLI entry point.

Default (convert) form:
    themey <theme.etheme> [--scale N] [--output DIR] [--open]

Subcommands:
    themey convert <theme.etheme> ...      same as the default form
    themey render  <theme.etheme|name> ... headless KWin screenshot (see render.py)
    themey apply   <name> ...              point the live KWin at an installed theme
    themey dock    [--remove]              build just the dock panel, no theme needed

Flags (convert):
    --scale=N     in [0.5, 3]; fractional (e.g. 1.5 or 0.5) is
                  QML-backend-only; default 2
    --output DIR  write the theme tree + report + preview under DIR instead
                  of installing to ~/.local/share (nothing outside DIR is touched)
    --upscale M   part-art scaler: nearest (default), quality (in-tree hqx)
                  or waifu2x (external CNN; falls back to hqx when the
                  binary or its models are missing). Both QML-only
    --shade-button ACTION
                  QML-backend-only remap for E16's dead shade button
                  (Plasma 6 removed window shading): maximize (default),
                  keepAbove, keepBelow, menu, hide, or none
    --iconbox-frames off|on
                  Plasma Style task frames on the icon task manager: off
                  (default, E16's own frameless iconbox) or on (the
                  iconbox button art as per-icon plates)
    --widget-style windows|fusion|breeze
                  Qt application style for the bundle to select
                  (default: leave the user's application style alone)
    --apply       hand the freshly installed theme straight to
                  `themey apply` (the E16 furniture flags below apply)
    --no-restart-shell
                  only with --apply; see the apply flag of the same name
    --open        launch the HTML preview in a browser when the conversion
                  finishes (default: just print its path; --no-open still
                  parses and is the default)
    -v / -vv      increase verbosity (DEBUG, default INFO)
    -q            quiet (WARNING+ only)

Flags (apply, E16 furniture — convert takes the same set with --apply).
Every panel is opt-in and every selector is a tri-state: the positive
flag builds it, --no-<panel> removes one an earlier apply created, and an
absent flag leaves that panel alone:
    --pager / --no-pager
    --iconbox / --no-iconbox
    --dragbar / --no-dragbar
    --dock / --no-dock
    --furniture-strut
                  let the pager/iconbox panels reserve screen space
                  (default: Windows Go Below)
    --pager-cell PX / --iconbox-size PX / --dock-size PX
                  override E16's own 48 px cell / iconbox sizes, and the
                  dock's scale-derived thickness

Flags (apply, other):
    --widget-style windows|fusion|breeze
                  override the bundle's own X-Themey-WidgetStyle stamp
                  for this run

Group flags:
    --version     print themey.__version__ and exit 0

Batch form (themey --all <dir>) is unbuilt and intentionally not exposed.
"""
from __future__ import annotations

import logging
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer
import typer.core

from . import __version__, apply, external, log
from .pipeline import convert


class WidgetStyle(StrEnum):
    """``--widget-style`` choices, on both ``convert`` and ``apply``.

    The members mirror :data:`themey.generate.lookandfeel.WIDGET_STYLES`
    (which owns the token -> Qt style-name mapping); this enum exists so
    Typer renders and validates the choice list. Absent = the user's
    application style is left alone.
    """

    windows = "windows"
    fusion = "fusion"
    breeze = "breeze"


#: Help for the furniture flags, shared by ``convert --apply`` and
#: ``apply`` so both spell the same tri-state the same way: the positive
#: form builds the panel, ``--no-*`` removes one a previous apply
#: created, and an absent flag leaves it alone
#: (:meth:`themey.apply.FurnitureOptions.wanted`).
_PAGER_HELP = (
    "Create E16's pager panel; --no-pager removes one a previous apply "
    "created (and puts your desktop grid back); absent = leave it alone"
)
_ICONBOX_HELP = (
    "Create E16's iconbox panel; --no-iconbox removes one a previous apply "
    "created; absent = leave it alone"
)
_DRAGBAR_HELP = (
    "Create E16's top dragbar; --no-dragbar removes one a previous apply "
    "created (and unparks your own top panels); absent = leave it alone"
)
_DOCK_HELP = (
    "Create the macOS-style dock panel (see also `themey dock`); --no-dock "
    "removes one a previous apply created; absent = leave it alone"
)
_DOCK_SIZE_HELP = (
    "Dock panel thickness in px; default = 32 px at the theme's conversion "
    "scale, floored at 48"
)

#: Lone flags that belong to the group itself, not to the implicit
#: ``convert``. Without this exemption ``_DefaultConvertGroup`` would rewrite
#: ``themey --version`` into ``themey convert --version``, which has no such
#: option.
_GROUP_ONLY_FLAGS = ("--help", "-h", "--version")


class _DefaultConvertGroup(typer.core.TyperGroup):
    """Click group that routes ``themey foo.etheme`` to ``themey convert``.

    If none of the argv tokens name a registered subcommand, ``convert`` is
    prepended so the historical single-argument form keeps working — except
    for the group's own lone flags (:data:`_GROUP_ONLY_FLAGS`).
    """

    # ``ctx`` is annotated with ``typer.Context``, not ``click.Context``:
    # typer >=0.26 vendors its own click as ``typer._click``, so
    # ``TyperGroup.parse_args`` expects the vendored ``Context`` and a real
    # ``click.Context`` no longer type-checks. ``typer.Context`` subclasses
    # whichever one the installed typer uses, so it is correct on both sides
    # of that split — and it avoids importing the private ``typer._click``.
    def parse_args(self, ctx: typer.Context, args: list[str]) -> list[str]:
        if args and not any(a in self.commands for a in args):
            if not (len(args) == 1 and args[0] in _GROUP_ONLY_FLAGS):
                args = ["convert", *args]
        return super().parse_args(ctx, args)


app = typer.Typer(
    cls=_DefaultConvertGroup,
    no_args_is_help=True,
    add_completion=False,
    help=(
        "Convert Enlightenment DR16 .etheme archives into Plasma 6 Aurorae "
        "decorations. `themey FILE.etheme` is shorthand for `themey convert FILE.etheme` "
        "(--scale, --output, --open live there)."
    ),
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the themey version and exit",
        ),
    ] = False,
) -> None:
    """Group-level options. Eager ``--version`` exits before any subcommand
    runs; see ``_GROUP_ONLY_FLAGS`` for why it also has to bypass the
    implicit-``convert`` rewrite."""


@app.command("convert")
def convert_cmd(
    theme: Annotated[
        Path,
        typer.Argument(
            exists=True,
            dir_okay=False,
            readable=True,
            help="Path to a .etheme archive",
        ),
    ],
    scale: Annotated[
        float,
        typer.Option(
            "--scale",
            min=0.5,
            max=3,
            help=(
                "Border/image upscale factor in [0.5, 3]; fractional values "
                "(e.g. 1.5 or 0.5) are QML-backend-only (default 2)"
            ),
        ),
    ] = 2,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            file_okay=False,
            help="Write theme tree + report + preview under DIR; skip the install",
        ),
    ] = None,
    open_preview: Annotated[
        bool,
        typer.Option(
            "--open/--no-open",
            help="Open the HTML preview in a browser when the conversion "
            "finishes (default: just print its path)",
        ),
    ] = False,
    upscale: Annotated[
        str,
        typer.Option(
            "--upscale",
            help=(
                "Part-art scaler: 'nearest' (default, pixel-art sharp), "
                "'quality' (in-tree hqx smoothing) or 'waifu2x' "
                "(waifu2x-ncnn-vulkan; falls back to hqx with a report "
                "note when the binary or its models are absent). Both "
                "smoothing modes are QML-backend-only"
            ),
        ),
    ] = "nearest",
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            help=(
                "Decoration backend: 'qml' (E16-faithful QML package, "
                "default), 'svg' (Aurorae SVG theme), or 'both'"
            ),
        ),
    ] = "qml",
    shade_button: Annotated[
        str,
        typer.Option(
            "--shade-button",
            help=(
                "QML-backend-only remap for E16's shade button (Plasma 6 "
                "removed window shading): 'maximize' (default), "
                "'keepAbove', 'keepBelow', 'menu', 'hide', or 'none' "
                "(today's inert disabled button)"
            ),
        ),
    ] = "maximize",
    iconbox_frames: Annotated[
        str,
        typer.Option(
            "--iconbox-frames",
            help=(
                "Plasma Style task frames on the icon task manager: 'off' "
                "(default: E16's own frameless iconbox — container.c "
                "draw_icon_base = 0) or 'on' (the iconbox button art as "
                "per-icon plates)"
            ),
        ),
    ] = "off",
    widget_style: Annotated[
        WidgetStyle | None,
        typer.Option(
            "--widget-style",
            help=(
                "Qt application style for the Global Theme bundle to "
                "select (kdeglobals widgetStyle); default: leave the "
                "user's application style alone"
            ),
        ),
    ] = None,
    apply_flag: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Apply the theme to the live desktop as soon as it is "
            "installed (the same work as a following `themey apply NAME`); "
            "not available with --output or --backend svg/both",
        ),
    ] = False,
    no_restart_shell: Annotated[
        bool,
        typer.Option(
            "--no-restart-shell",
            help="Skip the automatic plasmashell restart that makes a tiled "
            "wallpaper repaint immediately (the config still lands; the "
            "repaint then waits for the next login). Only with --apply",
        ),
    ] = False,
    pager: Annotated[
        bool | None,
        typer.Option(
            "--pager/--no-pager",
            help=_PAGER_HELP,
        ),
    ] = None,
    iconbox: Annotated[
        bool | None,
        typer.Option(
            "--iconbox/--no-iconbox",
            help=_ICONBOX_HELP,
        ),
    ] = None,
    dragbar: Annotated[
        bool | None,
        typer.Option(
            "--dragbar/--no-dragbar",
            help=_DRAGBAR_HELP,
        ),
    ] = None,
    dock: Annotated[
        bool | None,
        typer.Option(
            "--dock/--no-dock",
            help=_DOCK_HELP,
        ),
    ] = None,
    furniture_strut: Annotated[
        bool,
        typer.Option(
            "--furniture-strut",
            help="Let the pager/iconbox panels reserve screen space; default is "
            "Windows Go Below, so maximized windows keep the whole screen",
        ),
    ] = False,
    pager_cell: Annotated[
        int,
        typer.Option(
            "--pager-cell",
            help="Pager cell height in px (E16's own default 48); the panel is "
            "one aspect-true cell thick",
        ),
    ] = apply.DEFAULT_FURNITURE.pager_cell_px,
    iconbox_size: Annotated[
        int,
        typer.Option(
            "--iconbox-size",
            help="Iconbox panel thickness in px = the task icon size "
            "(E16's own default 48)",
        ),
    ] = apply.DEFAULT_FURNITURE.iconbox_px,
    dock_size: Annotated[
        int | None,
        typer.Option("--dock-size", help=_DOCK_SIZE_HELP),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "-v",
            "--verbose",
            count=True,
            help="Increase verbosity (use -v for DEBUG)",
        ),
    ] = 0,
    quiet: Annotated[
        bool,
        typer.Option(
            "-q",
            "--quiet",
            help="Suppress info messages (WARNING+ only)",
        ),
    ] = False,
) -> None:
    """Convert one .etheme to a Plasma 6 KWin window decoration."""
    log.setup_logging(verbose=verbose, quiet=quiet)
    # Every --apply usage error is raised BEFORE the conversion: a bad
    # flag combination must not cost a full convert + install first.
    style_token = widget_style.value if widget_style else None
    furniture = apply.DEFAULT_FURNITURE
    if apply_flag:
        if output is not None:
            raise typer.BadParameter(
                "--apply needs an installed theme, but --output writes the "
                "tree under DIR and installs nothing; drop one of the two"
            )
        if backend != "qml":
            raise typer.BadParameter(
                f"--apply is QML-only (got --backend {backend}); the full "
                "Look-and-Feel apply has no SVG path — convert without "
                "--apply, then `themey apply NAME --deco-only --backend svg`"
            )
        furniture = _furniture_options(
            pager=pager,
            iconbox=iconbox,
            dragbar=dragbar,
            dock=dock,
            furniture_strut=furniture_strut,
            pager_cell=pager_cell,
            iconbox_size=iconbox_size,
            dock_size=dock_size,
        )
    try:
        result = convert(
            theme, scale=scale, output_dir=output, backend=backend,
            upscale=upscale, shade_button=shade_button,
            iconbox_frames=iconbox_frames,
            widget_style=style_token,
        )
    except Exception as exc:
        logging.getLogger(__name__).error("conversion failed: %s", exc)
        raise typer.Exit(code=1) from exc

    if result.installed:
        typer.echo(f"Installed: {result.installed_dir}")
    else:
        typer.echo(f"Wrote:     {result.installed_dir}")
    if result.qml_installed_dir is not None and result.qml_installed_dir != result.installed_dir:
        verb = "Installed" if result.installed else "Wrote"
        typer.echo(f"{verb} (QML): {result.qml_installed_dir}")
    if result.color_scheme_path is not None:
        verb = "Installed" if result.installed else "Wrote"
        typer.echo(f"{verb} (colors): {result.color_scheme_path}")
    if result.cursor_theme_dir is not None:
        verb = "Installed" if result.installed else "Wrote"
        typer.echo(f"{verb} (cursors): {result.cursor_theme_dir}")
    if result.desktop_theme_dir is not None:
        verb = "Installed" if result.installed else "Wrote"
        typer.echo(f"{verb} (plasma style): {result.desktop_theme_dir}")
    if result.lnf_dir is not None:
        verb = "Installed" if result.installed else "Wrote"
        typer.echo(f"{verb} (bundle): {result.lnf_dir}")
    typer.echo(f"Preview:   {result.preview_path}")
    typer.echo(f"Report:    {result.report_path}")
    if result.installed:
        qml_built = result.qml_installed_dir is not None
        # With --apply (which implies the QML backend) the apply runs
        # below, after this whole block, and prints its own line — none of
        # the "here is how to apply it" advice belongs on that path.
        if not qml_built:
            typer.echo(
                f"Apply via System Settings - Window Decorations - {result.theme_name}, "
                f"or: themey apply {result.theme_name} --deco-only --backend svg"
            )
        elif not apply_flag:
            typer.echo(
                f"Apply via System Settings - Window Decorations - {result.theme_name}, "
                f"or: themey apply {result.theme_name}"
            )
        if result.color_scheme_path is not None:
            typer.echo(
                f"Colors:    pick '{result.theme_name} (themey)' under "
                "System Settings - Colors"
            )
        if result.cursor_theme_dir is not None:
            typer.echo(
                f"Cursors:   pick '{result.theme_name} (themey)' under "
                "System Settings - Cursors"
            )
        if result.lnf_id is not None:
            if apply_flag:
                typer.echo(f"Global theme: {result.lnf_id}")
            elif qml_built:
                typer.echo(
                    f"Global theme: {result.lnf_id} — apply: themey apply "
                    f"{result.theme_name}"
                )
            else:
                typer.echo(
                    f"Global theme: {result.lnf_id} — apply via System "
                    "Settings - Appearance - Global Theme, or decoration-"
                    f"only: themey apply {result.theme_name} --deco-only "
                    "--backend svg"
                )

    if apply_flag:
        # One command, converted and loaded. The theme is installed
        # either way; only the apply can fail from here on.
        try:
            apply.apply_full(
                result.theme_name,
                restart_shell=not no_restart_shell,
                furniture=furniture,
                widget_style=style_token,
            )
        except apply.ApplyError as exc:
            logging.getLogger(__name__).error("apply failed: %s", exc)
            raise typer.Exit(code=1) from exc
        typer.echo("Applied.")

    if not open_preview:
        return
    # Auto-open preview unless headless / SSH
    opened = external.open_preview_unless_headless(result.preview_path)
    if not opened:
        typer.echo(f"(Open the preview manually: file://{result.preview_path})")


@app.command("render")
def render_cmd(
    theme: Annotated[
        str,
        typer.Argument(help="Path to a .etheme archive, or the name of an installed theme"),
    ],
    out: Annotated[
        Path | None,
        typer.Option("-o", "--out", dir_okay=False, help="Output PNG path"),
    ] = None,
    target: Annotated[
        str,
        typer.Option(
            "--target",
            help=(
                "'deco' (default: window decoration via a kdialog client), "
                "'style' (the Plasma Style's FrameSvg sets — panel/popup/"
                "tooltip/tasks/pager — via a plasmoidviewer probe applet) or "
                "'pager' (themey's own E16 pager applet in the same harness)"
            ),
        ),
    ] = "deco",
    plugin: Annotated[
        str,
        typer.Option(
            "--plugin",
            help=(
                "'legacy' (org.kde.kwin.aurorae SVG), 'v2', or 'qml' "
                "(the QML decoration package backend)"
            ),
        ),
    ] = "legacy",
    border_size: Annotated[
        str,
        typer.Option(
            "--border-size",
            help="KWin BorderSize (Tiny..Oversized); both plugins clamp sides to it",
        ),
    ] = "Normal",
    maximized: Annotated[
        bool,
        typer.Option("--maximized", help="Render the client window maximized"),
    ] = False,
    scale: Annotated[
        float,
        typer.Option(
            "--scale",
            min=0.5,
            max=3,
            help="Border/image upscale factor in [0.5, 3]; fractional needs --plugin qml",
        ),
    ] = 2,
    upscale: Annotated[
        str,
        typer.Option(
            "--upscale",
            help="'nearest' (default), 'quality' (hqx) or 'waifu2x'",
        ),
    ] = "nearest",
    verbose: Annotated[
        int,
        typer.Option(
            "-v",
            "--verbose",
            count=True,
            help="Increase verbosity (use -v for DEBUG)",
        ),
    ] = 0,
) -> None:
    """Screenshot the theme inside a headless nested KWin (truth, not a mock)."""
    from . import render

    log.setup_logging(verbose=verbose, quiet=False)
    try:
        if target == "style":
            png = render.render_style(
                theme, out=out, scale=scale, upscale=upscale
            )
        elif target == "pager":
            png = render.render_pager(
                theme, out=out, scale=scale, upscale=upscale
            )
        elif target == "deco":
            png = render.render(
                theme,
                out=out,
                plugin=plugin,
                border_size=border_size,
                maximized=maximized,
                scale=scale,
                upscale=upscale,
            )
        else:
            raise render.RenderError(
                f"unknown --target {target!r}; expected 'deco', 'style' or 'pager'"
            )
    except render.RenderError as exc:
        logging.getLogger(__name__).error("render failed: %s", exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Rendered: {png}")


def _furniture_options(
    *,
    pager: bool | None,
    iconbox: bool | None,
    dragbar: bool | None,
    dock: bool | None,
    furniture_strut: bool,
    pager_cell: int,
    iconbox_size: int,
    dock_size: int | None,
) -> apply.FurnitureOptions:
    """Build the :class:`apply.FurnitureOptions` for one command's flags.

    Shared by ``themey apply`` and ``themey convert --apply`` so both
    spell the E16 furniture the same way. The four selectors pass straight
    through as the tri-states Typer parsed them into: True for the
    positive flag, False for ``--no-*``, None when neither was given. The
    sizes are validated here as a usage error rather than surfacing
    ``apply``'s typed :class:`~themey.apply.ApplyError` as a failed apply;
    ``--dock-size`` only when it was actually passed.
    """
    sizes: tuple[tuple[str, int | None], ...] = (
        ("--pager-cell", pager_cell),
        ("--iconbox-size", iconbox_size),
        ("--dock-size", dock_size),
    )
    for flag, value in sizes:
        if value is not None and value <= 0:
            raise typer.BadParameter(f"{flag} must be a positive number of pixels")
    return apply.FurnitureOptions(
        pager=pager,
        iconbox=iconbox,
        dragbar=dragbar,
        dock=dock,
        strut=furniture_strut,
        pager_cell_px=pager_cell,
        iconbox_px=iconbox_size,
        dock_px=dock_size,
    )


@app.command("apply")
def apply_cmd(
    name: Annotated[
        str | None,
        typer.Argument(
            help="Installed theme name (see themey convert); omit only with --revert"
        ),
    ] = None,
    legacy_plugin: Annotated[
        bool,
        typer.Option(
            "--legacy-plugin",
            help="Use the v1 QML plugin org.kde.kwin.aurorae instead of Plasma's default .v2",
        ),
    ] = False,
    border_size: Annotated[
        str | None,
        typer.Option(
            "--border-size",
            help="KWin BorderSize (Tiny..Oversized); default = bracket that fits the theme",
        ),
    ] = None,
    keep_buttons: Annotated[
        bool,
        typer.Option(
            "--keep-buttons",
            help="Don't touch the global titlebar button layout (kwinrc ButtonsOnLeft/Right)",
        ),
    ] = False,
    backend: Annotated[
        str,
        typer.Option(
            "--backend",
            help="'qml' (QML decoration package, default) or 'svg' (Aurorae SVG theme) "
            "— only meaningful with --deco-only",
        ),
    ] = "qml",
    deco_only: Annotated[
        bool,
        typer.Option(
            "--deco-only",
            help="Apply only the window decoration (today's kwinrc-only behavior) "
            "instead of the full Look-and-Feel bundle",
        ),
    ] = False,
    revert: Annotated[
        bool,
        typer.Option(
            "--revert",
            help="Restore the global theme + decoration that were active before "
            "the last full `themey apply` (NAME is not needed)",
        ),
    ] = False,
    no_restart_shell: Annotated[
        bool,
        typer.Option(
            "--no-restart-shell",
            help="Skip the automatic plasmashell restart that makes a tiled "
            "wallpaper repaint immediately (the config still lands; the "
            "repaint then waits for the next login). Full apply only — "
            "ignored with --deco-only/--revert",
        ),
    ] = False,
    pager: Annotated[
        bool | None,
        typer.Option("--pager/--no-pager", help=_PAGER_HELP),
    ] = None,
    iconbox: Annotated[
        bool | None,
        typer.Option("--iconbox/--no-iconbox", help=_ICONBOX_HELP),
    ] = None,
    dragbar: Annotated[
        bool | None,
        typer.Option("--dragbar/--no-dragbar", help=_DRAGBAR_HELP),
    ] = None,
    dock: Annotated[
        bool | None,
        typer.Option("--dock/--no-dock", help=_DOCK_HELP),
    ] = None,
    furniture_strut: Annotated[
        bool,
        typer.Option(
            "--furniture-strut",
            help="Let the pager/iconbox panels reserve screen space; default is "
            "Windows Go Below, so maximized windows keep the whole screen",
        ),
    ] = False,
    pager_cell: Annotated[
        int,
        typer.Option(
            "--pager-cell",
            help="Pager cell height in px (E16's own default 48); the panel is "
            "one aspect-true cell thick",
        ),
    ] = apply.DEFAULT_FURNITURE.pager_cell_px,
    iconbox_size: Annotated[
        int,
        typer.Option(
            "--iconbox-size",
            help="Iconbox panel thickness in px = the task icon size "
            "(E16's own default 48)",
        ),
    ] = apply.DEFAULT_FURNITURE.iconbox_px,
    dock_size: Annotated[
        int | None,
        typer.Option("--dock-size", help=_DOCK_SIZE_HELP),
    ] = None,
    widget_style: Annotated[
        WidgetStyle | None,
        typer.Option(
            "--widget-style",
            help="Qt application style to select (kdeglobals widgetStyle), "
            "overriding the bundle's own --widget-style stamp for this "
            "run; default: use the stamp, or leave the style alone when "
            "the bundle carries none. Full apply only",
        ),
    ] = None,
) -> None:
    """Point the live KWin session at an installed theme's full Look-and-Feel
    bundle (or, with --deco-only, just its decoration), and reconfigure."""
    if revert:
        try:
            reverted = apply.revert()
        except apply.ApplyError as exc:
            logging.getLogger(__name__).error("revert failed: %s", exc)
            raise typer.Exit(code=1) from exc
        if reverted:
            typer.echo("Reverted to the previous global theme and decoration.")
        else:
            typer.echo("Nothing to revert (no prior `themey apply` on this machine).")
        return

    if name is None:
        typer.echo("Error: NAME is required unless --revert is given.", err=True)
        raise typer.Exit(code=1)

    try:
        if backend == "svg" and not deco_only:
            raise apply.ApplyError(
                "--backend svg only applies via --deco-only (the full "
                "Look-and-Feel bundle apply is QML-only); run `themey apply "
                f"{name} --deco-only --backend svg`, or apply the svg bundle's "
                "colors/wallpaper/cursors via System Settings -> Appearance "
                "-> Global Theme"
            )
        if deco_only:
            apply.apply(
                name,
                legacy_plugin=legacy_plugin,
                border_size=border_size,
                keep_buttons=keep_buttons,
                backend=backend,
            )
        else:
            apply.apply_full(
                name,
                legacy_plugin=legacy_plugin,
                border_size=border_size,
                keep_buttons=keep_buttons,
                restart_shell=not no_restart_shell,
                furniture=_furniture_options(
                    pager=pager,
                    iconbox=iconbox,
                    dragbar=dragbar,
                    dock=dock,
                    furniture_strut=furniture_strut,
                    pager_cell=pager_cell,
                    iconbox_size=iconbox_size,
                    dock_size=dock_size,
                ),
                widget_style=widget_style.value if widget_style else None,
            )
    except apply.ApplyError as exc:
        logging.getLogger(__name__).error("apply failed: %s", exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Applied {name} (revert: themey apply --revert)")


@app.command("dock")
def dock_cmd(
    remove: Annotated[
        bool,
        typer.Option(
            "--remove",
            help="Remove the dock panel this command created and clear its "
            "marker, instead of building one",
        ),
    ] = False,
    dock_size: Annotated[
        int | None,
        typer.Option("--dock-size", help=_DOCK_SIZE_HELP),
    ] = None,
    verbose: Annotated[
        int,
        typer.Option(
            "-v", "--verbose", count=True,
            help="Increase verbosity (use -v for DEBUG)",
        ),
    ] = 0,
    quiet: Annotated[
        bool,
        typer.Option(
            "-q", "--quiet", help="Suppress info messages (WARNING+ only)",
        ),
    ] = False,
) -> None:
    """Build (or, with --remove, remove) just themey's dock panel.

    The dock needs no converted theme — it takes its art from whatever
    Plasma Style is active — so it is its own command rather than another
    `themey apply` flag. It touches nothing but that one panel: no global
    theme, no decoration, and none of the other furniture panels.
    `themey apply --revert` removes it along with everything else.
    """
    log.setup_logging(verbose=verbose, quiet=quiet)
    if dock_size is not None and dock_size <= 0:
        raise typer.BadParameter("--dock-size must be a positive number of pixels")
    try:
        acted = apply.apply_dock(size_px=dock_size, remove=remove)
    except apply.ApplyError as exc:
        logging.getLogger(__name__).error("dock failed: %s", exc)
        raise typer.Exit(code=1) from exc
    if not remove:
        typer.echo("Dock panel ready (remove: themey dock --remove)")
    elif acted:
        typer.echo("Dock panel removed.")
    else:
        typer.echo("No themey dock panel to remove.")


if __name__ == "__main__":
    app()
