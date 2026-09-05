"""``themey dock`` — the standalone dock panel (``apply.apply_dock``).

The dock is the one furniture panel that is useful without a themey global
theme, so this path deliberately does far less than ``apply_full``: no
Look-and-Feel/decoration verification, no ``plasma-apply-*`` tool, no KWin
reconfigure, no plasmashell restart, and no fit-all/un-float loop over the
user's own panels. It creates (or re-asserts, or removes) exactly one
panel and writes exactly that panel's ``panelVisibility``.

``FakeKConfig`` and the fake-package helpers are reused from
``test_apply_full`` rather than duplicated — it is the recorder for every
kwriteconfig6/kreadconfig6/plasmashell-scripting call ``apply.py`` makes,
and this module asserts on the same recorded scripts and config store.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.test_apply_full import (
    FakeKConfig,
    _install_fake_lnf,
    _install_fake_plasmoids,
)
from themey import apply as apply_mod
from themey import paths
from themey.generate import plasmoids


@pytest.fixture
def fake_kconfig(monkeypatch, fake_home: Path) -> FakeKConfig:
    """Same recorder ``test_apply_full`` uses, with themey's applet
    packages installed (``apply_dock``'s pre-check)."""
    fk = FakeKConfig()
    monkeypatch.setattr(apply_mod.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(apply_mod.subprocess, "run", fk.run)
    _install_fake_plasmoids()
    return fk


def _scripts(fk: FakeKConfig) -> list[str]:
    """The plasmashell script bodies of every recorded evaluateScript."""
    return [
        c[-1] for c in fk.calls if any("evaluateScript" in tok for tok in c)
    ]


# --- creating the dock ----------------------------------------------------


def test_apply_dock_creates_the_panel_without_any_theme_installed(
    fake_kconfig: FakeKConfig,
) -> None:
    """The dock stands on its own: no Look-and-Feel bundle, no decoration
    package, nothing but the applet."""
    assert apply_mod.apply_dock() is True
    script = fake_kconfig.calls[
        fake_kconfig.index_of("new Panel", "org.themey.dock")
    ][-1]
    assert "p.location = 'bottom'" in script
    assert "p.alignment = 'center'" in script
    assert "p.height = 64" in script  # the default scale 2
    assert "p.lengthMode = 'fit'" in script
    assert "p.minimumLength = 0" in script
    assert "p.floating = true" in script
    assert "p.hiding = 'dodgewindows'" in script
    assert fake_kconfig.store["DockPanel"] == "304"
    assert (
        fake_kconfig.store["plasmashellrc/PlasmaViews/Panel 304/panelVisibility"]
        == "2"
    )


def test_apply_dock_touches_no_other_marker_and_removes_nothing(
    fake_kconfig: FakeKConfig,
) -> None:
    """``themey dock`` is not a furniture apply: the pager/iconbox/dragbar
    markers are neither read as dead nor acted on."""
    fake_kconfig.store["PagerPanel"] = "302"
    fake_kconfig.store["IconboxPanel"] = "301"
    fake_kconfig.store["DragbarPanel"] = "303"
    apply_mod.apply_dock()
    for key in ("PagerPanel", "IconboxPanel", "DragbarPanel"):
        assert fake_kconfig.store[key] == {
            "PagerPanel": "302", "IconboxPanel": "301", "DragbarPanel": "303",
        }[key]
    scripts = _scripts(fake_kconfig)
    assert all("p.remove()" not in s for s in scripts)
    assert all("panelById(301)" not in s for s in scripts)
    assert all("panelById(302)" not in s for s in scripts)
    assert all("panelById(303)" not in s for s in scripts)
    assert sum("new Panel" in s for s in scripts) == 1


def test_apply_dock_reasserts_a_live_panel(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["DockPanel"] = "304"
    fake_kconfig.dock_exists_reply = "exists"
    assert apply_mod.apply_dock() is True
    reassert = fake_kconfig.calls[
        fake_kconfig.index_of("panelById(304)", "p.height")
    ][-1]
    assert "p.height = 64" in reassert
    assert "p.floating = true" in reassert
    assert "p.hiding = 'dodgewindows'" in reassert
    assert all("new Panel" not in s for s in _scripts(fake_kconfig))
    assert fake_kconfig.store["DockPanel"] == "304"


def test_apply_dock_takes_the_scale_from_the_active_themey_bundle(
    fake_kconfig: FakeKConfig,
) -> None:
    lnf = _install_fake_lnf("e13")
    (lnf / "metadata.json").write_text(json.dumps({"X-Themey-Scale": 3}))
    fake_kconfig.store["LookAndFeelPackage"] = "themey_e13"
    apply_mod.apply_dock()
    script = fake_kconfig.calls[
        fake_kconfig.index_of("new Panel", "org.themey.dock")
    ][-1]
    assert "p.height = 96" in script  # scale_px(32, 3)


def test_apply_dock_default_scale_without_a_themey_global_theme(
    fake_kconfig: FakeKConfig,
) -> None:
    """A non-themey global theme carries no conversion scale, so the dock
    falls back to the pipeline's own default of 2."""
    fake_kconfig.store["LookAndFeelPackage"] = "org.kde.breeze.desktop"
    apply_mod.apply_dock()
    script = fake_kconfig.calls[
        fake_kconfig.index_of("new Panel", "org.themey.dock")
    ][-1]
    assert "p.height = 64" in script


def test_apply_dock_size_override(fake_kconfig: FakeKConfig) -> None:
    apply_mod.apply_dock(size_px=72)
    script = fake_kconfig.calls[
        fake_kconfig.index_of("new Panel", "org.themey.dock")
    ][-1]
    assert "p.height = 72" in script


@pytest.mark.parametrize("value", [0, -8])
def test_apply_dock_rejects_a_nonpositive_size(
    fake_kconfig: FakeKConfig, value: int,
) -> None:
    with pytest.raises(apply_mod.ApplyError, match="dock_px"):
        apply_mod.apply_dock(size_px=value)
    assert all("new Panel" not in s for s in _scripts(fake_kconfig))


def test_apply_dock_requires_the_applet_package(
    fake_kconfig: FakeKConfig,
) -> None:
    import shutil as _shutil

    _shutil.rmtree(paths.plasmoids() / plasmoids.DOCK_ID)
    with pytest.raises(apply_mod.ApplyError, match="themey convert"):
        apply_mod.apply_dock()
    assert _scripts(fake_kconfig) == []
    assert "DockPanel" not in fake_kconfig.store


# --- removing the dock ----------------------------------------------------


def test_apply_dock_remove_removes_the_recorded_panel(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["DockPanel"] = "304"
    assert apply_mod.apply_dock(remove=True) is True
    fake_kconfig.index_of("panelById(304)", "p.remove()")
    assert "DockPanel" not in fake_kconfig.store


def test_apply_dock_remove_without_a_marker_is_a_no_op(
    fake_kconfig: FakeKConfig,
) -> None:
    assert apply_mod.apply_dock(remove=True) is False
    assert all("p.remove()" not in s for s in _scripts(fake_kconfig))


def test_apply_dock_remove_failure_raises_and_keeps_the_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    """The marker is the only handle on the panel, so a removal that did
    not confirm keeps it for a later retry."""
    fake_kconfig.store["DockPanel"] = "304"
    fake_kconfig.iconbox_remove_reply = ""
    with pytest.raises(apply_mod.ApplyError, match="dock panel"):
        apply_mod.apply_dock(remove=True)
    assert fake_kconfig.store["DockPanel"] == "304"


def test_apply_dock_remove_needs_no_applet_package(
    fake_kconfig: FakeKConfig,
) -> None:
    """Removing a panel does not host anything, so an uninstalled applet
    must not block the way out."""
    import shutil as _shutil

    _shutil.rmtree(paths.plasmoids() / plasmoids.DOCK_ID)
    fake_kconfig.store["DockPanel"] = "304"
    assert apply_mod.apply_dock(remove=True) is True
    assert "DockPanel" not in fake_kconfig.store


# --- what apply_dock must NOT do ------------------------------------------


@pytest.mark.parametrize("remove", [False, True])
def test_apply_dock_runs_no_desktop_wide_step(
    fake_kconfig: FakeKConfig, remove: bool,
) -> None:
    """No global theme tool, no shell restart, no KWin reconfigure, and
    none of ``apply_full``'s panel-wide steps."""
    fake_kconfig.store["DockPanel"] = "304"
    apply_mod.apply_dock(remove=remove)
    programs = [Path(c[0]).name for c in fake_kconfig.calls]
    assert not any(p.startswith("plasma-apply-") for p in programs)
    assert "systemctl" not in programs
    scripts = _scripts(fake_kconfig)
    assert all("screenGeometry" not in s for s in scripts)
    assert all("for (const p of panels())" not in s for s in scripts)
    assert all("reconfigure" not in tok for c in fake_kconfig.calls for tok in c)
    # ... and no baseline of the user's own panels is recorded either.
    for key in ("PrevPanelLengthModes", "PrevPanelFloating", "PrevTopPanels"):
        assert key not in fake_kconfig.store
