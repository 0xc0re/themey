"""Stdlib logging facade. Configure once via setup_logging().

Verbosity: -q -> WARNING, default -> INFO, -v/-vv -> DEBUG.
"""
from __future__ import annotations

import logging


def setup_logging(verbose: int = 0, quiet: bool = False) -> None:
    if quiet:
        level = logging.WARNING
    elif verbose >= 1:
        level = logging.DEBUG
    else:
        level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )
