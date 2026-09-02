"""Shared pytest fixtures.

fake_home: monkeypatches HOME + XDG_DATA_HOME + XDG_CACHE_HOME to a tmp
directory so install / preview / report paths route into the test's tmp
tree. XDG_CACHE_HOME is not cosmetic: ``install.clear_style_cache``
(install.py:50) reads it at call time and *globs and deletes*
``plasma_theme_*.kcache`` under it, so without this fixture a developer
who has XDG_CACHE_HOME set has every convert test deleting from their
real cache.
Never use pyfakefs — Pillow and tarfile need real files.
"""
from __future__ import annotations

from pathlib import Path

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-visual-hashes",
        action="store_true",
        default=False,
        help="Overwrite committed perceptual-hash snapshots from current renders.",
    )


@pytest.fixture
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Monkeypatch HOME + XDG_DATA_HOME + XDG_CACHE_HOME to tmp_path.

    Returns the home dir. Creates ``tmp_path/.local/share`` and
    ``tmp_path/.cache`` so XDG default resolution works even with both
    variables unset. The cache redirect keeps
    ``install.clear_style_cache``'s ``plasma_theme_*.kcache`` glob-unlink
    inside the tmp tree instead of the developer's own cache.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    (tmp_path / ".local" / "share").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".cache").mkdir(parents=True, exist_ok=True)
    return tmp_path


GANYMEDE_SLIDEOUTS = """\
__ACLASS __BGN
  __NAME ACTION_GANYMEDE_KILL
  __TYPE __TYPE_NORMAL
  __EVENT __MOUSE_RELEASE
  __BUTTON 1
  __ACTION __A_KILL
  __NEXT_ACTION
  __BUTTON 3
  __ACTION __A_ICONIFY
__END
"""

GANYMEDE_BORDERS = """\
__BORDER __BGN
  __NAME DEFAULT
  __BORDER_SIZE_LEFT 5
  __BORDER_SIZE_RIGHT 5
  __BORDER_SIZE_TOP 23
  __BORDER_SIZE_BOTTOM 5
  __BORDER_PART __BGN
    __ICLASS BORDER_TOPLEFT
    __ACLASS ACTION_GANYMEDE_KILL
    __TOPLEFT_X_PERCENTAGE 0
    __TOPLEFT_X_ABSOLUTE 0
    __TOPLEFT_Y_PERCENTAGE 0
    __TOPLEFT_Y_ABSOLUTE 0
    __BOTTOMRIGHT_X_PERCENTAGE 0
    __BOTTOMRIGHT_X_ABSOLUTE 22
    __BOTTOMRIGHT_Y_PERCENTAGE 0
    __BOTTOMRIGHT_Y_ABSOLUTE 23
  __END
  __BORDER_PART __BGN
    __ICLASS BORDER_TITLE
    __ACLASS ACTION_MOVE
    __FLAGS __FLAG_TITLE
    __TOPLEFT_X_PERCENTAGE 0
    __TOPLEFT_X_ABSOLUTE 22
    __TOPLEFT_Y_PERCENTAGE 0
    __TOPLEFT_Y_ABSOLUTE 0
    __BOTTOMRIGHT_X_PERCENTAGE 1024
    __BOTTOMRIGHT_X_ABSOLUTE -1
    __BOTTOMRIGHT_Y_PERCENTAGE 0
    __BOTTOMRIGHT_Y_ABSOLUTE 23
  __END
__END
"""


@pytest.fixture
def ganymede_tree(tmp_path: Path) -> Path:
    """A theme tree in Ganymede's shape: a border part bound to a
    theme-private __ACLASS defined in slideouts.cfg, the way E16's
    ThemeConfigLoad reads them (config.c:580, slideouts before borders)."""
    (tmp_path / "borders.cfg").write_text(GANYMEDE_BORDERS)
    (tmp_path / "slideouts.cfg").write_text(GANYMEDE_SLIDEOUTS)
    return tmp_path
