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
from themey.generate.lookandfeel import WIDGET_STYLES


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
            "widget_style": None,
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
    """Each furniture flag is tri-state: ``--no-*`` is False, the positive
    flag is True, and an absent flag stays None (leave that panel alone)."""
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
        pager=False, iconbox=None, dragbar=False, strut=True,
        pager_cell_px=64, iconbox_px=32,
    )


def test_apply_positive_furniture_flags_opt_in(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(
        app, ["apply", "e13", "--pager", "--iconbox", "--dragbar", "--dock"]
    )
    assert result.exit_code == 0, result.output
    assert calls[0][1]["furniture"] == apply_mod.FurnitureOptions(
        pager=True, iconbox=True, dragbar=True, dock=True,
    )


def test_apply_without_furniture_flags_leaves_every_panel_alone(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13"])
    assert result.exit_code == 0, result.output
    furniture = calls[0][1]["furniture"]
    assert (furniture.pager, furniture.iconbox, furniture.dragbar, furniture.dock) == (
        None, None, None, None,
    )


def test_apply_no_iconbox_flag(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--no-iconbox"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["furniture"].iconbox is False


def test_apply_no_dock_flag(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--no-dock"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["furniture"].dock is False


def test_apply_dock_size_passes_through(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--dock-size", "64"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["furniture"].dock_px == 64


@pytest.mark.parametrize(
    "flag", ["--pager-cell", "--iconbox-size", "--dock-size"]
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
    """``convert --apply`` builds its options through the same helper, so
    it takes the furniture flag values and nothing else."""
    opts = cli_mod._furniture_options(
        pager=None, iconbox=False, dragbar=True, dock=None,
        furniture_strut=False, pager_cell=48, iconbox_size=48, dock_size=None,
    )
    assert opts == apply_mod.FurnitureOptions(iconbox=False, dragbar=True)


def test_apply_widget_style_passes_through(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--widget-style", "windows"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["widget_style"] == "windows"


def test_apply_widget_style_defaults_to_none(monkeypatch) -> None:
    """No flag = whatever the bundle was stamped with (apply reads it)."""
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13"])
    assert result.exit_code == 0, result.output
    assert calls[0][1]["widget_style"] is None


def test_apply_widget_style_invalid_rejected(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(
        apply_mod, "apply_full", lambda name, **kw: calls.append((name, kw))
    )
    result = CliRunner().invoke(app, ["apply", "e13", "--widget-style", "kvantum"])
    assert result.exit_code != 0
    assert calls == []


def test_widget_style_enum_matches_the_generator_map() -> None:
    """The CLI's choices and lookandfeel's token->Qt-name map are one
    vocabulary — a new style is added in exactly one place."""
    assert {m.value for m in cli_mod.WidgetStyle} == set(WIDGET_STYLES)


# --- themey dock ----------------------------------------------------------


def test_dock_cmd_routes_to_apply_dock(monkeypatch) -> None:
    """``themey dock`` is its own subcommand, so the implicit-``convert``
    rewrite leaves it alone."""
    calls: list[dict] = []
    monkeypatch.setattr(
        apply_mod, "apply_dock", lambda **kw: calls.append(kw) or True
    )
    result = CliRunner().invoke(app, ["dock"])
    assert result.exit_code == 0, result.output
    assert calls == [{"size_px": None, "remove": False}]
    assert "themey dock --remove" in result.output


def test_dock_cmd_remove_flag(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        apply_mod, "apply_dock", lambda **kw: calls.append(kw) or True
    )
    result = CliRunner().invoke(app, ["dock", "--remove"])
    assert result.exit_code == 0, result.output
    assert calls == [{"size_px": None, "remove": True}]
    assert "Dock panel removed." in result.output


def test_dock_cmd_remove_with_nothing_to_remove(monkeypatch) -> None:
    monkeypatch.setattr(apply_mod, "apply_dock", lambda **kw: False)
    result = CliRunner().invoke(app, ["dock", "--remove"])
    assert result.exit_code == 0, result.output
    assert "No themey dock panel to remove." in result.output


def test_dock_cmd_size_passes_through(monkeypatch) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        apply_mod, "apply_dock", lambda **kw: calls.append(kw) or True
    )
    result = CliRunner().invoke(app, ["dock", "--dock-size", "72"])
    assert result.exit_code == 0, result.output
    assert calls == [{"size_px": 72, "remove": False}]


@pytest.mark.parametrize("value", ["0", "-8"])
def test_dock_cmd_rejects_nonpositive_size(monkeypatch, value: str) -> None:
    calls: list[dict] = []
    monkeypatch.setattr(
        apply_mod, "apply_dock", lambda **kw: calls.append(kw) or True
    )
    result = CliRunner().invoke(app, ["dock", "--dock-size", value])
    assert result.exit_code != 0
    assert calls == []


def test_dock_cmd_apply_error_exits_nonzero(monkeypatch) -> None:
    """A typed ApplyError is a failed command, not a traceback — and the
    success line is never printed."""
    def boom(**kw):
        raise apply_mod.ApplyError("no plasmashell")

    monkeypatch.setattr(apply_mod, "apply_dock", boom)
    result = CliRunner().invoke(app, ["dock"])
    assert result.exit_code == 1
    assert "Dock panel" not in result.output
