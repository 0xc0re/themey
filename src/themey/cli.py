"""themey CLI entry point.

Default (convert) form:
    themey <theme.etheme> [--scale N] [--output DIR] [--no-open]

Subcommands:
    themey convert <theme.etheme> ...      same as the default form
    themey render  <theme.etheme|name> ... headless KWin screenshot (see render.py)
    themey apply   <name> ...              point the live KWin at an installed theme

Flags (convert):
    --scale=N     in [1, 3]; fractional (e.g. 1.5) is QML-backend-only; default 2
    --output DIR  write the theme tree + report + preview under DIR instead
                  of installing to ~/.local/share (nothing outside DIR is touched)
    --upscale M   part-art scaler: nearest (default) or quality (QML-only hqx)
    --shade-button ACTION
                  QML-backend-only remap for E16's dead shade button
                  (Plasma 6 removed window shading): maximize (default),
                  keepAbove, keepBelow, menu, hide, or none
    --no-open     do not launch the HTML preview in a browser
    -v / -vv      increase verbosity (DEBUG, default INFO)
    -q            quiet (WARNING+ only)

Group flags:
    --version     print themey.__version__ and exit 0

Batch form (themey --all <dir>) is unbuilt and intentionally not exposed.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer
import typer.core

from . import __version__, external, log
from .pipeline import convert

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
        "(--scale, --output, --no-open live there)."
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
            min=1,
            max=3,
            help=(
                "Border/image upscale factor in [1, 3]; fractional values "
                "(e.g. 1.5) are QML-backend-only (default 2)"
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
    no_open: Annotated[
        bool,
        typer.Option("--no-open", help="Do not open the HTML preview in a browser"),
    ] = False,
    upscale: Annotated[
        str,
        typer.Option(
            "--upscale",
            help=(
                "Part-art scaler: 'nearest' (default, pixel-art sharp) or "
                "'quality' (hqx smoothing; QML-backend-only)"
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
    try:
        result = convert(
            theme, scale=scale, output_dir=output, backend=backend,
            upscale=upscale, shade_button=shade_button,
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
        if qml_built:
            typer.echo(
                f"Apply via System Settings - Window Decorations - {result.theme_name}, "
                f"or: themey apply {result.theme_name}"
            )
        else:
            typer.echo(
                f"Apply via System Settings - Window Decorations - {result.theme_name}, "
                f"or: themey apply {result.theme_name} --deco-only --backend svg"
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
            if qml_built:
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

    if no_open:
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
            min=1,
            max=3,
            help="Border/image upscale factor in [1, 3]; fractional needs --plugin qml",
        ),
    ] = 2,
    upscale: Annotated[
        str,
        typer.Option("--upscale", help="'nearest' (default) or 'quality' (hqx)"),
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
        png = render.render(
            theme,
            out=out,
            plugin=plugin,
            border_size=border_size,
            maximized=maximized,
            scale=scale,
            upscale=upscale,
        )
    except render.RenderError as exc:
        logging.getLogger(__name__).error("render failed: %s", exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Rendered: {png}")


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
) -> None:
    """Point the live KWin session at an installed theme's full Look-and-Feel
    bundle (or, with --deco-only, just its decoration), and reconfigure."""
    from . import apply

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
            )
    except apply.ApplyError as exc:
        logging.getLogger(__name__).error("apply failed: %s", exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Applied {name} (revert: themey apply --revert)")


if __name__ == "__main__":
    app()
