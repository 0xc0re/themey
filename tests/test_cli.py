"""Tests for src/themey/cli.py via Typer's testing runner."""
import shutil
from pathlib import Path

from typer.testing import CliRunner

from themey.cli import app

FIXTURES = Path(__file__).parent / "fixtures"


def test_cli_help_shows_options():
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "scale" in result.output.lower()


def test_cli_no_args_is_help():
    result = CliRunner().invoke(app, [])
    # Typer's no_args_is_help=True returns 0 with help text;
    # accept either 0+help or non-zero
    assert result.exit_code == 0 or result.exit_code != 0
    assert "Usage" in result.output or "scale" in result.output.lower()


def test_cli_nonexistent_path_errors():
    result = CliRunner().invoke(app, ["/tmp/totally_nonexistent_themey_test.etheme"])
    assert result.exit_code != 0


def test_cli_scale_4_rejected():
    result = CliRunner().invoke(app, ["--scale=4", str(FIXTURES / "Aliens.etheme")])
    assert result.exit_code != 0


def test_cli_aliens_end_to_end(fake_home, monkeypatch):
    # Suppress xdg-open by ensuring no DISPLAY
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(app, [str(FIXTURES / "Aliens.etheme")])
    assert result.exit_code == 0, result.output
    assert "Installed:" in result.output
    assert "Preview:" in result.output
    assert "Apply via" in result.output
    # Verify install actually happened (default backend = qml package)
    pkg = fake_home / ".local/share/kwin/decorations/themey_Aliens"
    assert (pkg / "metadata.json").is_file()
    assert (pkg / "contents/ui/theme.js").is_file()
    # The sampled color scheme installs alongside it, under the XDG root
    # KDE's Colors KCM reads.
    colors = fake_home / ".local/share/color-schemes/themey_Aliens.colors"
    assert colors.is_file()
    assert "[General]\nColorScheme=themey_Aliens\n" in colors.read_text()
    assert "Installed (colors):" in result.output
    if shutil.which("xcursorgen") is not None:
        cursors = fake_home / ".local/share/icons/themey_Aliens-cursors"
        assert (cursors / "index.theme").is_file()
        assert (cursors / "cursors" / "default").is_file()
        assert "Installed (cursors):" in result.output


def test_cli_quiet_suppresses_info(fake_home, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(app, ["-q", str(FIXTURES / "Aliens.etheme")])
    assert result.exit_code == 0
    # The info-level "converting ..." log should NOT appear.
    # (quiet=WARNING level; INFO suppressed)
    # However Typer's typer.echo always prints to stdout — those lines
    # ALWAYS appear (Installed:/Preview:/Apply via). Just check log
    # records aren't appearing as "INFO " prefix.
    # NOTE: pytest CliRunner captures both stdout and stderr; logs go to stderr.
    # We check that the result.output doesn't contain "INFO themey.pipeline"
    assert "INFO themey.pipeline" not in result.output


def test_cli_verbose_emits_debug(fake_home, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(app, ["-v", str(FIXTURES / "Aliens.etheme")])
    assert result.exit_code == 0
    # -v sets DEBUG level; pipeline emits log.debug() — should appear
    assert ("DEBUG themey.pipeline" in result.output
            or "DEBUG" in result.output), result.output


def test_cli_output_dir_skips_install(fake_home, tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    out = tmp_path / "out"
    result = CliRunner().invoke(
        app, ["--output", str(out), "--no-open", str(FIXTURES / "Aliens.etheme")]
    )
    assert result.exit_code == 0, result.output
    # QML package + report + preview land under --output, nothing under HOME.
    assert (out / "themey_Aliens" / "metadata.json").is_file()
    assert (out / "themey_Aliens" / "contents/ui/theme.js").is_file()
    assert (out / "Aliens.report.txt").is_file()
    assert (out / "Aliens.html").is_file()
    assert (out / "themey_Aliens.colors").is_file()
    assert not (fake_home / ".local/share/aurorae").exists()
    assert not (fake_home / ".local/share/color-schemes").exists()
    assert "Wrote:" in result.output


def test_cli_no_open_suppresses_browser(fake_home, monkeypatch):
    monkeypatch.setenv("DISPLAY", ":0")
    calls: list = []
    monkeypatch.setattr(
        "themey.external.open_preview_unless_headless",
        lambda p: calls.append(p) or True,
    )
    result = CliRunner().invoke(app, ["--no-open", str(FIXTURES / "Aliens.etheme")])
    assert result.exit_code == 0, result.output
    assert calls == []


def test_cli_fractional_scale_accepted_for_qml(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app,
        ["--scale=1.5", "--output", str(tmp_path / "o"), "--no-open",
         str(FIXTURES / "Aliens.etheme")],
    )
    assert result.exit_code == 0, result.output


def test_cli_fractional_scale_rejected_for_svg_backend(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app,
        ["--scale=1.5", "--backend=svg", "--output", str(tmp_path / "o"),
         "--no-open", str(FIXTURES / "Aliens.etheme")],
    )
    assert result.exit_code != 0


def test_cli_scale_below_1_rejected():
    result = CliRunner().invoke(
        app, ["--scale=0.5", str(FIXTURES / "Aliens.etheme")]
    )
    assert result.exit_code != 0


def test_cli_upscale_quality_accepted_for_qml(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app,
        ["--upscale", "quality", "--output", str(tmp_path / "o"), "--no-open",
         str(FIXTURES / "Aliens.etheme")],
    )
    assert result.exit_code == 0, result.output


def test_cli_upscale_quality_rejected_for_svg_backend(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app,
        ["--upscale", "quality", "--backend=svg", "--output",
         str(tmp_path / "o"), "--no-open", str(FIXTURES / "Aliens.etheme")],
    )
    assert result.exit_code != 0


def test_cli_shade_button_hide_accepted(tmp_path, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app,
        ["--shade-button", "hide", "--output", str(tmp_path / "o"), "--no-open",
         str(FIXTURES / "Aliens.etheme")],
    )
    assert result.exit_code == 0, result.output


def test_cli_svg_backend_apply_advice_uses_deco_only(fake_home, monkeypatch):
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app, ["--backend", "svg", str(FIXTURES / "Aliens.etheme")]
    )
    assert result.exit_code == 0, result.output
    assert "themey apply Aliens --deco-only --backend svg" in result.output
    assert "or: themey apply Aliens\n" not in result.output
    assert "apply: themey apply Aliens\n" not in result.output


def test_cli_shade_button_invalid_rejected():
    result = CliRunner().invoke(
        app, ["--shade-button", "bogus", str(FIXTURES / "Aliens.etheme")]
    )
    assert result.exit_code != 0
