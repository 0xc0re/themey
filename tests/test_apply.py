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
from themey.slug import plugin_id


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
    monkeypatch.setattr(apply_mod, "_AURORAE_FLUSH_WAIT_S", 0.0, raising=False)
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
    apply_mod.apply("e13", backend="svg")
    assert fake_kconfig.store["ButtonsOnLeft"] == "XILS"
    assert fake_kconfig.store["ButtonsOnRight"] == ""
    # Previous (unset) layout recorded for revert.
    assert fake_kconfig.store["ThemeyPrevButtons"] == "@unset|@unset"


def test_apply_keep_buttons_flag_skips(fake_kconfig: FakeKConfig) -> None:
    _install_fake_theme("e13")
    apply_mod.apply("e13", keep_buttons=True, backend="svg")
    assert "ButtonsOnLeft" not in fake_kconfig.store
    assert "ThemeyPrevButtons" not in fake_kconfig.store


def test_apply_records_existing_layout_once(fake_kconfig: FakeKConfig) -> None:
    """A user's custom layout is captured before the first overwrite, and a
    second themey theme must NOT clobber the recorded original."""
    fake_kconfig.store["ButtonsOnLeft"] = "MS"
    fake_kconfig.store["ButtonsOnRight"] = "IAX"
    _install_fake_theme("e13")
    _install_fake_theme("other", left="X", right="I")
    apply_mod.apply("e13", backend="svg")
    assert fake_kconfig.store["ThemeyPrevButtons"] == "MS|IAX"
    apply_mod.apply("other", backend="svg")
    assert fake_kconfig.store["ThemeyPrevButtons"] == "MS|IAX"  # unchanged
    assert fake_kconfig.store["ButtonsOnLeft"] == "X"


def test_apply_breeze_restores_previous_layout(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["ButtonsOnLeft"] = "MS"
    fake_kconfig.store["ButtonsOnRight"] = "IAX"
    _install_fake_theme("e13")
    apply_mod.apply("e13", backend="svg")
    apply_mod.apply("Breeze")
    assert fake_kconfig.store["ButtonsOnLeft"] == "MS"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"
    assert "ThemeyPrevButtons" not in fake_kconfig.store


def test_apply_breeze_deletes_buttons_when_originally_unset(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_theme("e13")
    apply_mod.apply("e13", backend="svg")
    apply_mod.apply("Breeze")
    assert "ButtonsOnLeft" not in fake_kconfig.store
    assert "ButtonsOnRight" not in fake_kconfig.store


def test_apply_theme_without_binning_leaves_buttons_alone(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_theme("plain", left=None)
    apply_mod.apply("plain", backend="svg")
    assert "ButtonsOnLeft" not in fake_kconfig.store
    assert "ThemeyPrevButtons" not in fake_kconfig.store


# --- Aurorae QML component-cache flush ---------------------------------------


def _install_fake_qml_deco(name: str = "Obsidian") -> Path:
    pkg = paths.kwin_decorations() / plugin_id(name)
    pkg.mkdir(parents=True)
    (pkg / "metadata.json").write_text("{}")
    return pkg


def _theme_writes(fk: FakeKConfig) -> list[str]:
    """Values written to the kwinrc ``theme`` key, in call order."""
    out = []
    for c in fk.calls:
        prog = Path(c[0]).name
        if prog.startswith("kwriteconfig") and "--key" in c and "--delete" not in c:
            if c[c.index("--key") + 1] == "theme":
                out.append(c[-1])
    return out


def test_apply_qml_bounces_through_breeze_first(fake_kconfig: FakeKConfig) -> None:
    """KWin's Aurorae v1 plugin caches the compiled QML component per theme
    name for the compositor's lifetime (``Helper::m_components``); the
    engine is reset only when every Aurorae decoration is destroyed. A QML
    apply must flip the live deco to Breeze + reconfigure before pointing
    kwinrc back at the (possibly re-converted) package, or KWin keeps
    rendering the stale copy."""
    _install_fake_qml_deco("Obsidian")
    apply_mod.apply("Obsidian", backend="qml")
    assert _theme_writes(fake_kconfig) == ["Breeze", plugin_id("Obsidian")]
    # A reconfigure must land between the Breeze flip and the target write,
    # so KWin actually drops its Aurorae decorations in between.
    breeze_idx = next(
        i for i, c in enumerate(fake_kconfig.calls)
        if Path(c[0]).name.startswith("kwriteconfig") and c[-1] == "Breeze"
    )
    target_idx = next(
        i for i, c in enumerate(fake_kconfig.calls)
        if Path(c[0]).name.startswith("kwriteconfig") and c[-1] == plugin_id("Obsidian")
    )
    reconfigures = [
        i for i, c in enumerate(fake_kconfig.calls) if "reconfigure" in c
    ]
    assert any(breeze_idx < i < target_idx for i in reconfigures)
    # ...and one final reconfigure after the target write.
    assert any(i > target_idx for i in reconfigures)


def test_apply_breeze_does_not_bounce(fake_kconfig: FakeKConfig) -> None:
    apply_mod.apply("Breeze")
    assert _theme_writes(fake_kconfig) == ["Breeze"]
    assert sum("reconfigure" in c for c in fake_kconfig.calls) == 1


def test_apply_svg_does_not_bounce(fake_kconfig: FakeKConfig) -> None:
    """The flush is a QML-backend contract: SVG themes share one cached
    aurorae.qml whose per-theme art goes through Plasma's own SVG cache."""
    _install_fake_theme("e13")
    apply_mod.apply("e13", backend="svg")
    assert _theme_writes(fake_kconfig) == ["__aurorae__svg__e13"]


# --- E1: baseline recorders -------------------------------------------------


def test_record_prev_lookandfeel_snapshots_current_package(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["LookAndFeelPackage"] = "com.github.vinceliuice.MacVentura-Dark"
    kw, kr = "/usr/bin/kwriteconfig6", "/usr/bin/kreadconfig6"
    apply_mod._record_prev_lookandfeel(kw, kr)
    assert (
        fake_kconfig.store[apply_mod._PREV_LNF_KEY]
        == "com.github.vinceliuice.MacVentura-Dark"
    )
    call = next(
        c for c in fake_kconfig.calls if apply_mod._PREV_LNF_KEY in c
    )
    assert "kdeglobals" in call
    assert "Themey" in call


def test_record_prev_lookandfeel_unset_sentinel(fake_kconfig: FakeKConfig) -> None:
    kw, kr = "/usr/bin/kwriteconfig6", "/usr/bin/kreadconfig6"
    apply_mod._record_prev_lookandfeel(kw, kr)
    assert fake_kconfig.store[apply_mod._PREV_LNF_KEY] == "@unset"


def test_record_prev_lookandfeel_written_once(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["LookAndFeelPackage"] = "org.kde.breeze.desktop"
    kw, kr = "/usr/bin/kwriteconfig6", "/usr/bin/kreadconfig6"
    apply_mod._record_prev_lookandfeel(kw, kr)
    fake_kconfig.store["LookAndFeelPackage"] = "themey_e13"  # simulated apply
    apply_mod._record_prev_lookandfeel(kw, kr)
    assert fake_kconfig.store[apply_mod._PREV_LNF_KEY] == "org.kde.breeze.desktop"


def test_record_prev_deco_snapshots_current_triple(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["library"] = "org.kde.breeze"
    fake_kconfig.store["theme"] = "Breeze"
    fake_kconfig.store["BorderSize"] = "Normal"
    kw, kr = "/usr/bin/kwriteconfig6", "/usr/bin/kreadconfig6"
    apply_mod._record_prev_deco(kw, kr)
    assert fake_kconfig.store[apply_mod._PREV_DECO_KEY] == "org.kde.breeze|Breeze|Normal"


def test_record_prev_deco_unset_sentinel(fake_kconfig: FakeKConfig) -> None:
    kw, kr = "/usr/bin/kwriteconfig6", "/usr/bin/kreadconfig6"
    apply_mod._record_prev_deco(kw, kr)
    assert fake_kconfig.store[apply_mod._PREV_DECO_KEY] == "@unset|@unset|@unset"


def test_record_prev_deco_written_once(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["library"] = "org.kde.breeze"
    fake_kconfig.store["theme"] = "Breeze"
    kw, kr = "/usr/bin/kwriteconfig6", "/usr/bin/kreadconfig6"
    apply_mod._record_prev_deco(kw, kr)
    fake_kconfig.store["library"] = "org.kde.kwin.aurorae"  # simulated apply
    apply_mod._record_prev_deco(kw, kr)
    assert fake_kconfig.store[apply_mod._PREV_DECO_KEY] == "org.kde.breeze|Breeze|@unset"


def test_run_checked_uses_sanitized_env(monkeypatch) -> None:
    """Every external write funnels through _run_checked, which must hand
    the tools `paths.subprocess_env()` (snap XDG_DATA_HOME dropped)."""
    import subprocess

    from themey import apply as apply_mod

    seen: dict = {}

    def fake_run(argv, **kwargs):
        seen["env"] = kwargs.get("env")
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(apply_mod.subprocess, "run", fake_run)
    monkeypatch.setenv("XDG_DATA_HOME", "/home/u/snap/code/259/.local/share")
    apply_mod._run_checked(["true"], "probe")
    assert seen["env"] is not None
    assert "XDG_DATA_HOME" not in seen["env"]
