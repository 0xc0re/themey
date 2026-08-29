"""themey CLI entry point.

Default (convert) form:
    themey <theme.etheme> [--scale N] [--output DIR] [--no-open]

Subcommands:
    themey convert <theme.etheme> ...      same as the default form
    themey render  <theme.etheme|name> ... headless KWin screenshot (see render.py)
    themey apply   <name> ...              point the live KWin at an installed theme

Flags (convert):
    --scale=N     1, 2 (default), or 3
    --output DIR  write the theme tree + report + preview under DIR instead
                  of installing to ~/.local/share (nothing outside DIR is touched)
    --no-open     do not launch the HTML preview in a browser
    -v / -vv      increase verbosity (DEBUG, default INFO)
    -q            quiet (WARNING+ only)

Batch form (themey --all <dir>) is Phase 4 and intentionally not exposed.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import click
import typer
import typer.core

from . import external, log
from .pipeline import convert


class _DefaultConvertGroup(typer.core.TyperGroup):
    """Click group that routes ``themey foo.etheme`` to ``themey convert``.

    If none of the argv tokens name a registered subcommand, ``convert`` is
    prepended so the historical single-argument form keeps working.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if args and not any(a in self.commands for a in args):
            if not (len(args) == 1 and args[0] in ("--help", "-h")):
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
        int,
        typer.Option(
            "--scale",
            min=1,
            max=3,
            help="Border/image upscale factor (1/2/3; default 2)",
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
    """Convert one .etheme to a Plasma 6 Aurorae window decoration."""
    log.setup_logging(verbose=verbose, quiet=quiet)
    try:
        result = convert(theme, scale=scale, output_dir=output)
    except Exception as exc:
        logging.getLogger(__name__).error("conversion failed: %s", exc)
        raise typer.Exit(code=1) from exc

    if result.installed:
        typer.echo(f"Installed: {result.installed_dir}")
    else:
        typer.echo(f"Wrote:     {result.installed_dir}")
    typer.echo(f"Preview:   {result.preview_path}")
    typer.echo(f"Report:    {result.report_path}")
    if result.installed:
        typer.echo(
            f"Apply via System Settings - Window Decorations - {result.theme_name}, "
            f"or: themey apply {result.theme_name} --legacy-plugin"
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
        typer.Option("--plugin", help="Aurorae plugin: 'legacy' (org.kde.kwin.aurorae) or 'v2'"),
    ] = "legacy",
    border_size: Annotated[
        str,
        typer.Option("--border-size", help="KWin BorderSize (Tiny..Oversized); v2 clamps to it"),
    ] = "Normal",
    maximized: Annotated[
        bool,
        typer.Option("--maximized", help="Render the client window maximized"),
    ] = False,
    scale: Annotated[int, typer.Option("--scale", min=1, max=3)] = 2,
    verbose: Annotated[int, typer.Option("-v", "--verbose", count=True)] = 0,
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
        )
    except render.RenderError as exc:
        logging.getLogger(__name__).error("render failed: %s", exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Rendered: {png}")


@app.command("apply")
def apply_cmd(
    name: Annotated[str, typer.Argument(help="Installed theme name (see themey convert)")],
    legacy_plugin: Annotated[
        bool,
        typer.Option(
            "--legacy-plugin",
            help="Use org.kde.kwin.aurorae (honours theme border sizes) instead of aurorae.v2",
        ),
    ] = False,
    border_size: Annotated[
        str | None,
        typer.Option("--border-size", help="Set KWin BorderSize (Tiny..Oversized)"),
    ] = None,
) -> None:
    """Point the live KWin session at an installed theme (writes kwinrc, reconfigures)."""
    from . import apply

    try:
        apply.apply(name, legacy_plugin=legacy_plugin, border_size=border_size)
    except apply.ApplyError as exc:
        logging.getLogger(__name__).error("apply failed: %s", exc)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Applied {name} (revert: themey apply Breeze or System Settings)")


if __name__ == "__main__":
    app()
