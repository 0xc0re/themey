"""``themey.__version__`` is the single source of truth for the CLI's
``--version``, and nothing else in the build reads it — hatchling takes the
number from ``[project] version`` in pyproject.toml. The two can therefore
drift silently; these tests pin them together and pin the flag's output to
the same string.
"""
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import themey
from themey.cli import app

PYPROJECT = Path(__file__).parent.parent / "pyproject.toml"


def _pyproject_version() -> str:
    with PYPROJECT.open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_dunder_version_matches_pyproject():
    assert themey.__version__ == _pyproject_version(), (
        "themey.__version__ and pyproject.toml [project] version disagree; "
        "bump both together"
    )


def test_cli_version_flag_prints_version():
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == themey.__version__


def test_cli_version_flag_is_not_rewritten_to_convert():
    """``_DefaultConvertGroup`` prepends ``convert`` to unrecognized argv;
    ``--version`` must be exempt or Click reports "No such option"."""
    result = CliRunner().invoke(app, ["--version"])
    assert "No such option" not in result.output
    assert "convert" not in result.output
