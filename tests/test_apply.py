"""themey apply — kwinrc writes, including the theme's button layout.

E16 themes place buttons themselves (e13 stacks all four at the top-left);
KWin's button order is global kwinrc state that no theme file can carry, so
``apply`` must write ``ButtonsOnLeft/Right`` from the binning persisted in
the installed rc's ``[Themey]`` section. The user's previous layout is
recorded in a ``ThemeyPrevButtons`` marker and restored by ``apply Breeze``.
All kwriteconfig6/kreadconfig6/qdbus calls are mocked.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from themey import apply as apply_mod
from themey import paths


class FakeKConfig:
    """Records kwriteconfig calls; serves kreadconfig values."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.calls: list[list[str]] = []

    def run(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        prog = Path(cmd[0]).name
        if prog.startswith("kwriteconfig"):
            key = cmd[cmd.index("--key") + 1]
            if "--delete" in cmd:
                self.store.pop(key, None)
            else:
                self.store[key] = cmd[-1]
            return subprocess.CompletedProcess(cmd, 0)
        if prog.startswith("kreadconfig"):
            key = cmd[cmd.index("--key") + 1]
            out = self.store.get(key, "")
            return subprocess.CompletedProcess(cmd, 0, stdout=out + "\n")
        return subprocess.CompletedProcess(cmd, 0, stdout="")


@pytest.fixture
def fake_kconfig(monkeypatch, fake_home: Path) -> FakeKConfig:
    fk = FakeKConfig()
    monkeypatch.setattr(apply_mod.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(apply_mod.subprocess, "run", fk.run)
    return fk


def _install_fake_theme(
    name: str, left: str | None = "XILS", right: str | None = ""
) -> Path:
    theme_dir = paths.aurorae_themes() / name
    theme_dir.mkdir(parents=True)
    lines = [
        "[Layout]",
        "BorderLeft=14",
        "BorderRight=12",
        "BorderBottom=20",
    ]
    if left is not None:
        lines += ["", "[Themey]", f"LeftButtons={left}", f"RightButtons={right}"]
    (theme_dir / f"{name}rc").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return theme_dir


def test_apply_sets_buttons_from_installed_rc(fake_kconfig: FakeKConfig) -> None:
    _install_fake_theme("e13")
    apply_mod.apply("e13")
    assert fake_kconfig.store["ButtonsOnLeft"] == "XILS"
    assert fake_kconfig.store["ButtonsOnRight"] == ""
    # Previous (unset) layout recorded for revert.
    assert fake_kconfig.store["ThemeyPrevButtons"] == "@unset|@unset"


def test_apply_keep_buttons_flag_skips(fake_kconfig: FakeKConfig) -> None:
    _install_fake_theme("e13")
    apply_mod.apply("e13", keep_buttons=True)
    assert "ButtonsOnLeft" not in fake_kconfig.store
    assert "ThemeyPrevButtons" not in fake_kconfig.store


def test_apply_records_existing_layout_once(fake_kconfig: FakeKConfig) -> None:
    """A user's custom layout is captured before the first overwrite, and a
    second themey theme must NOT clobber the recorded original."""
    fake_kconfig.store["ButtonsOnLeft"] = "MS"
    fake_kconfig.store["ButtonsOnRight"] = "IAX"
    _install_fake_theme("e13")
    _install_fake_theme("other", left="X", right="I")
    apply_mod.apply("e13")
    assert fake_kconfig.store["ThemeyPrevButtons"] == "MS|IAX"
    apply_mod.apply("other")
    assert fake_kconfig.store["ThemeyPrevButtons"] == "MS|IAX"  # unchanged
    assert fake_kconfig.store["ButtonsOnLeft"] == "X"


def test_apply_breeze_restores_previous_layout(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["ButtonsOnLeft"] = "MS"
    fake_kconfig.store["ButtonsOnRight"] = "IAX"
    _install_fake_theme("e13")
    apply_mod.apply("e13")
    apply_mod.apply("Breeze")
    assert fake_kconfig.store["ButtonsOnLeft"] == "MS"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"
    assert "ThemeyPrevButtons" not in fake_kconfig.store


def test_apply_breeze_deletes_buttons_when_originally_unset(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_theme("e13")
    apply_mod.apply("e13")
    apply_mod.apply("Breeze")
    assert "ButtonsOnLeft" not in fake_kconfig.store
    assert "ButtonsOnRight" not in fake_kconfig.store


def test_apply_theme_without_binning_leaves_buttons_alone(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_theme("plain", left=None)
    apply_mod.apply("plain")
    assert "ButtonsOnLeft" not in fake_kconfig.store
    assert "ThemeyPrevButtons" not in fake_kconfig.store
