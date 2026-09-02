"""``themey convert --apply`` and ``--widget-style`` (WP4).

``convert --apply`` runs one command end to end: convert, install, then
hand the freshly installed bundle to :func:`themey.apply.apply_full`. The
apply itself is exercised in test_apply_full.py; here the concern is the
wiring — the guard combos that must be refused BEFORE a conversion starts,
the exact kwargs the convert path forwards, and the ``X-Themey-WidgetStyle``
stamp ``--widget-style`` leaves in the installed bundle.

Every test monkeypatches ``apply.apply_full``: nothing here may touch the
live desktop.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from themey import apply as apply_mod
from themey.cli import app

FIXTURES = Path(__file__).parent / "fixtures"
ALIENS = str(FIXTURES / "Aliens.etheme")


@pytest.fixture
def recorded_apply(monkeypatch) -> list[tuple]:
    """Records every ``apply_full`` call instead of running one."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    return calls


# --- guards (refused before the conversion runs) --------------------------


def test_convert_apply_rejects_output_dir(recorded_apply, tmp_path, fake_home) -> None:
    """``--output`` writes a tree instead of installing, so there is
    nothing installed for apply to point the desktop at."""
    result = CliRunner().invoke(
        app, [ALIENS, "--apply", "--output", str(tmp_path / "o"), "--no-open"]
    )
    assert result.exit_code != 0
    assert recorded_apply == []
    assert "--output" in result.output
    assert not (tmp_path / "o").exists()


@pytest.mark.parametrize("backend", ["svg", "both"])
def test_convert_apply_rejects_non_qml_backend(
    recorded_apply, fake_home, backend: str,
) -> None:
    """The full bundle apply is QML-only (see ``apply_cmd``'s own guard)."""
    result = CliRunner().invoke(
        app, [ALIENS, "--apply", "--backend", backend, "--no-open"]
    )
    assert result.exit_code != 0
    assert recorded_apply == []
    assert "--backend" in result.output


def test_convert_apply_rejects_nonpositive_furniture_size(
    recorded_apply, fake_home,
) -> None:
    """A usage error must not cost a whole conversion first."""
    result = CliRunner().invoke(
        app, [ALIENS, "--apply", "--pager-cell", "0", "--no-open"]
    )
    assert result.exit_code != 0
    assert recorded_apply == []
    assert not (fake_home / ".local/share/kwin/decorations/themey_Aliens").exists()


# --- pass-through ---------------------------------------------------------


def test_convert_apply_calls_apply_full_with_defaults(
    recorded_apply, fake_home,
) -> None:
    result = CliRunner().invoke(app, [ALIENS, "--apply", "--no-open"])
    assert result.exit_code == 0, result.output
    assert recorded_apply == [
        ("Aliens", {
            "restart_shell": True,
            "furniture": apply_mod.FurnitureOptions(),
            "widget_style": None,
        })
    ]
    assert "Applied." in result.output
    assert "themey apply Aliens" not in result.output


def test_convert_apply_forwards_furniture_and_restart_flags(
    recorded_apply, fake_home,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            ALIENS, "--apply", "--no-open", "--no-restart-shell", "--no-pager",
            "--no-iconbox", "--no-dragbar", "--furniture-strut",
            "--pager-cell", "64", "--iconbox-size", "32",
            "--widget-style", "fusion",
        ],
    )
    assert result.exit_code == 0, result.output
    name, kwargs = recorded_apply[0]
    assert name == "Aliens"
    assert kwargs["restart_shell"] is False
    assert kwargs["widget_style"] == "fusion"
    assert kwargs["furniture"] == apply_mod.FurnitureOptions(
        pager=False, iconbox=False, dragbar=False, strut=True,
        pager_cell_px=64, iconbox_px=32,
    )


def test_convert_without_apply_never_applies_and_keeps_the_hint(
    recorded_apply, fake_home,
) -> None:
    result = CliRunner().invoke(app, [ALIENS, "--no-open"])
    assert result.exit_code == 0, result.output
    assert recorded_apply == []
    assert "themey apply Aliens" in result.output
    assert "Applied." not in result.output


def test_convert_apply_failure_exits_nonzero(monkeypatch, fake_home) -> None:
    """The theme is installed either way; only the apply failed."""
    def boom(name, **kw):
        raise apply_mod.ApplyError("not fully installed")

    monkeypatch.setattr(apply_mod, "apply_full", boom)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(app, [ALIENS, "--apply", "--no-open"])
    assert result.exit_code != 0
    assert (fake_home / ".local/share/kwin/decorations/themey_Aliens").is_dir()


# --- --widget-style stamps the bundle -------------------------------------


def test_convert_widget_style_stamps_bundle_and_defaults(
    fake_home, monkeypatch,
) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(
        app, [ALIENS, "--widget-style", "windows", "--no-open"]
    )
    assert result.exit_code == 0, result.output
    lnf = fake_home / ".local/share/plasma/look-and-feel/themey_Aliens"
    meta = json.loads((lnf / "metadata.json").read_text())
    assert meta["X-Themey-WidgetStyle"] == "Windows"
    defaults = (lnf / "contents" / "defaults").read_text()
    assert "[kdeglobals][KDE]\nwidgetStyle=Windows\n" in defaults


def test_convert_without_widget_style_leaves_the_bundle_unstamped(
    fake_home, monkeypatch,
) -> None:
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    result = CliRunner().invoke(app, [ALIENS, "--no-open"])
    assert result.exit_code == 0, result.output
    lnf = fake_home / ".local/share/plasma/look-and-feel/themey_Aliens"
    meta = json.loads((lnf / "metadata.json").read_text())
    assert "X-Themey-WidgetStyle" not in meta
    assert "widgetStyle" not in (lnf / "contents" / "defaults").read_text()


def test_convert_widget_style_invalid_rejected(fake_home) -> None:
    result = CliRunner().invoke(app, [ALIENS, "--widget-style", "kvantum"])
    assert result.exit_code != 0


def test_convert_widget_style_reaches_output_tree(
    fake_home, tmp_path, monkeypatch,
) -> None:
    """The ``--output`` tree carries the same stamp (no install involved)."""
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    out = tmp_path / "o"
    result = CliRunner().invoke(
        app, [ALIENS, "--widget-style", "breeze", "--output", str(out), "--no-open"]
    )
    assert result.exit_code == 0, result.output
    lnf = out / "look-and-feel" / "themey_Aliens"
    meta = json.loads((lnf / "metadata.json").read_text())
    assert meta["X-Themey-WidgetStyle"] == "Breeze"
