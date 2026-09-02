"""CLI wiring for ``themey apply`` — routing to apply()/apply_full()/revert().

The full apply()/apply_full()/revert() behavior is exercised in
test_apply.py and test_apply_full.py; these tests only check that the CLI
passes flags through to the right function and prints the right message,
via monkeypatched targets so no real kwriteconfig/plasma-apply-* tools are
needed.
"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from themey import apply as apply_mod
from themey import cli as cli_mod
from themey.cli import app


def test_apply_default_routes_to_apply_full(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13"])
    assert result.exit_code == 0, result.output
    assert calls == [
        ("e13", {
            "legacy_plugin": False, "border_size": None,
            "keep_buttons": False, "restart_shell": True,
            "furniture": apply_mod.FurnitureOptions(),
        })
    ]
    assert "revert: themey apply --revert" in result.output


def test_apply_deco_only_routes_to_apply(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(apply_mod, "apply", lambda name, **kw: calls.append((name, kw)))
    result = CliRunner().invoke(app, ["apply", "e13", "--deco-only"])
    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0][0] == "e13"
    assert "revert: themey apply --revert" in result.output


def test_apply_revert_routes_to_revert_and_name_optional(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(apply_mod, "revert", lambda: calls.append("called") or True)
    result = CliRunner().invoke(app, ["apply", "--revert"])
    assert result.exit_code == 0, result.output
    assert calls == ["called"]


def test_apply_revert_with_name_also_works(monkeypatch) -> None:
    """--revert plus a (now-irrelevant) name argument is still accepted."""
    calls: list[str] = []
    monkeypatch.setattr(apply_mod, "revert", lambda: calls.append("called") or True)
    result = CliRunner().invoke(app, ["apply", "e13", "--revert"])
    assert result.exit_code == 0, result.output
    assert calls == ["called"]


def test_apply_revert_nothing_to_revert_message(monkeypatch) -> None:
    monkeypatch.setattr(apply_mod, "revert", lambda: False)
    result = CliRunner().invoke(app, ["apply", "--revert"])
    assert result.exit_code == 0, result.output
    assert "nothing to revert" in result.output.lower()


def test_apply_without_name_or_revert_errors(monkeypatch) -> None:
    result = CliRunner().invoke(app, ["apply"])
    assert result.exit_code != 0


def test_apply_svg_backend_without_deco_only_rejected(monkeypatch, caplog) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--backend=svg"])
    assert result.exit_code != 0
    assert calls == []
    assert "--deco-only" in caplog.text


def test_apply_svg_backend_with_deco_only_still_routes_to_apply(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(apply_mod, "apply", lambda name, **kw: calls.append((name, kw)))
    result = CliRunner().invoke(app, ["apply", "e13", "--deco-only", "--backend=svg"])
    assert result.exit_code == 0, result.output
    assert calls == [
        ("e13", {
            "legacy_plugin": False, "border_size": None,
            "keep_buttons": False, "backend": "svg",
        })
    ]


def test_apply_full_apply_error_exits_nonzero(monkeypatch) -> None:
    def boom(name, **kw):
        raise apply_mod.ApplyError("not installed")

    monkeypatch.setattr(apply_mod, "apply_full", boom)
    result = CliRunner().invoke(app, ["apply", "e13"])
    assert result.exit_code != 0


def test_apply_revert_error_exits_nonzero(monkeypatch) -> None:
    def boom():
        raise apply_mod.ApplyError("no kreadconfig6")

    monkeypatch.setattr(apply_mod, "revert", boom)
    result = CliRunner().invoke(app, ["apply", "--revert"])
    assert result.exit_code != 0


def test_apply_no_restart_shell_flag_passes_through(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--no-restart-shell"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["restart_shell"] is False


def test_apply_furniture_flags_build_options(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(
        app,
        [
            "apply", "e13", "--no-pager", "--no-dragbar", "--furniture-strut",
            "--pager-cell", "64", "--iconbox-size", "32",
        ],
    )
    assert result.exit_code == 0, result.output
    assert calls[0][1]["furniture"] == apply_mod.FurnitureOptions(
        pager=False, iconbox=True, dragbar=False, strut=True,
        pager_cell_px=64, iconbox_px=32,
    )


def test_apply_no_iconbox_flag(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--no-iconbox"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["furniture"].iconbox is False


@pytest.mark.parametrize(
    "flag", ["--pager-cell", "--iconbox-size"]
)
@pytest.mark.parametrize("value", ["0", "-8"])
def test_apply_rejects_nonpositive_furniture_sizes(
    monkeypatch, flag: str, value: str,
) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", flag, value])
    assert result.exit_code != 0
    assert calls == []


def test_furniture_options_helper_is_reusable() -> None:
    """WP4's ``convert --apply`` builds its options through the same
    helper, so it takes the six flag values and nothing else."""
    opts = cli_mod._furniture_options(
        no_pager=False, no_iconbox=True, no_dragbar=False,
        furniture_strut=False, pager_cell=48, iconbox_size=48,
    )
    assert opts == apply_mod.FurnitureOptions(iconbox=False)
