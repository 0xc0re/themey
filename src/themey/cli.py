"""themey CLI entry point.

Single-theme form (Phase 1; CLI-01):
    themey <theme.etheme>

Flags:
    --scale=N   1, 2 (default), or 3
    -v / -vv    increase verbosity (DEBUG, default INFO)
    -q          quiet (WARNING+ only)

Batch form (themey --all <dir>) is Phase 4 and intentionally not exposed
here. The roadmap maps CLI-01 entirely to Phase 1 because the single-theme
form ships first.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from . import external, log
from .pipeline import convert

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
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
        result = convert(theme, scale=scale)
    except Exception as exc:
        logging.getLogger(__name__).error("conversion failed: %s", exc)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Installed: {result.installed_dir}")
    typer.echo(f"Preview:   {result.preview_path}")
    typer.echo(f"Report:    {result.report_path}")
    typer.echo(
        f"Apply via System Settings - Window Decorations - {result.theme_name}"
    )

    # Auto-open preview unless headless / SSH
    opened = external.open_preview_unless_headless(result.preview_path)
    if not opened:
        typer.echo(f"(Open the preview manually: file://{result.preview_path})")


if __name__ == "__main__":
    app()
