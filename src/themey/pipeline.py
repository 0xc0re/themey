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

from . import install, paths
from .analyze.build_theme import build_theme
from .etheme.archive import extract
from .etheme.parse import parse_tree
from .generate.aurorae import write as write_aurorae
from .preview import render as render_preview
from .report import write as write_report
from .slug import slugify

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConvertResult:
    """Result of a successful pipeline.convert() call."""

    theme_name: str
    installed_dir: Path
    preview_path: Path
    report_path: Path
    notes_count: int
    installed: bool = True
    """False when ``output_dir`` was given: ``installed_dir`` is then the
    theme tree under that directory and nothing was written to XDG paths."""


def convert(
    etheme_path: Path, *, scale: int = 2, output_dir: Path | None = None
) -> ConvertResult:
    """Convert one .etheme to an installed Aurorae theme + preview + report.

    Args:
        etheme_path: Path to a ``.etheme`` archive (gzipped tar).
        scale: Border/image upscale factor. Must be 1, 2, or 3.
        output_dir: When given, skip the XDG install entirely and write the
            theme tree to ``output_dir/<name>/`` plus ``<name>.report.txt``
            and ``<name>.html`` next to it. Nothing under ``~/.local/share``
            is touched.

    Returns:
        A :class:`ConvertResult` with paths to the installed theme, preview,
        and report.

    Raises:
        ValueError: If ``scale`` is not 1, 2, or 3.
        UnsafeArchiveError: If the archive fails safe-extract validation.
        InstallError: If the atomic install rename fails.
    """
    if scale not in (1, 2, 3):
        raise ValueError(f"scale must be 1, 2, or 3 (got {scale})")

    # Theme name comes from the archive filename, never from cfg content.
    theme_name = slugify(etheme_path.stem)
    log.info("converting %s as %s (scale=%d)", etheme_path, theme_name, scale)

    with extract(etheme_path) as raw:
        log.debug("extracted to %s", raw.asset_root)
        ast_nodes = parse_tree(raw.asset_root)
        log.debug("parsed %d top-level AST nodes", len(ast_nodes))
        theme = build_theme(
            raw.asset_root,
            ast_nodes,
            name=theme_name,
            display_name=theme_name,
            scale=scale,
        )
        log.info(
            "theme: parts=%d iclasses=%d notes=%d skipped=%d",
            len(theme.border.parts),
            len(theme.iclasses),
            len(theme.notes),
            len(theme.skipped_borders),
        )

        if output_dir is not None:
            # Non-installing mode: write straight into output_dir/<name>/.
            output_dir.mkdir(parents=True, exist_ok=True)
            installed = output_dir / theme_name
            if installed.exists():
                shutil.rmtree(installed)
            write_aurorae(theme, installed)
            log.info("wrote theme tree to %s", installed)
            previews = output_dir
        else:
            # Stage outputs under XDG_DATA_HOME so os.replace can rename
            # atomically into ~/.local/share/aurorae/themes/<name>/ on the
            # same filesystem.
            staging_root = paths.themey_previews().parent / "staging"
            staging_root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix=f"{theme_name}-",
                dir=str(staging_root),
            ) as stage_str:
                stage = Path(stage_str)
                # Generators write into stage/<theme_name>/
                stage_theme_dir = stage / theme_name
                write_aurorae(theme, stage_theme_dir)
                log.debug("wrote Aurorae output to %s", stage_theme_dir)
                # Atomic install: renames stage_theme_dir into final
                # position. After this call, stage_theme_dir no longer
                # exists inside the TemporaryDirectory.
                installed = install.deploy(theme_name, stage_theme_dir)
                log.info("installed to %s", installed)
            previews = paths.themey_previews()

        # Report and preview MUST run inside the extract block: they call
        # strip_thicknesses, which measures iclass images (opaque-span
        # trims). See lifecycle invariant in module docstring.
        previews.mkdir(parents=True, exist_ok=True)
        report_path = write_report(theme, previews / f"{theme_name}.report.txt")
        preview_path = render_preview(theme, previews / f"{theme_name}.html")

    return ConvertResult(
        theme_name=theme_name,
        installed_dir=installed,
        preview_path=preview_path,
        report_path=report_path,
        notes_count=len(theme.notes),
        installed=output_dir is None,
    )
