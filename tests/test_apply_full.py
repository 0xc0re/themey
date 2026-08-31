"""``themey apply`` full Look-and-Feel apply + ``themey apply --revert``.

``apply_full`` is the CLI default: verify the Look-and-Feel bundle and QML
decoration are both installed, snapshot the pre-themey baselines (once),
``plasma-apply-lookandfeel``, re-assert the deco keys explicitly, fix up a
tiled default wallpaper, then reconfigure. ``revert`` reads those baselines
back and restores them. All kwriteconfig6/kreadconfig6/plasma-apply-*/qdbus
calls are mocked — see ``test_apply.py`` for the deco-only path this one
delegates to.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from themey import apply as apply_mod
from themey import paths
from themey.generate.desktop_writer import write_desktop
from themey.slug import plugin_id


class FakeKConfig:
    """Records every subprocess call; serves kreadconfig values back."""

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

    def index_of(self, *needle: str) -> int:
        """Index of the first recorded call whose argv contains, as a
        substring of some token, every string in *needle*."""
        for i, c in enumerate(self.calls):
            if all(any(n in tok for tok in c) for n in needle):
                return i
        raise AssertionError(f"no call contains {needle!r} in {self.calls!r}")


@pytest.fixture
def fake_kconfig(monkeypatch, fake_home: Path) -> FakeKConfig:
    fk = FakeKConfig()
    monkeypatch.setattr(apply_mod.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(apply_mod.subprocess, "run", fk.run)
    return fk


def _install_fake_deco(name: str = "e13") -> Path:
    pkg = paths.kwin_decorations() / plugin_id(name)
    (pkg / "contents" / "ui").mkdir(parents=True)
    (pkg / "metadata.json").write_text("{}")
    return pkg


def _install_fake_lnf(name: str = "e13", *, wallpaper_id: str | None = None) -> Path:
    lnf = paths.look_and_feel() / plugin_id(name)
    (lnf / "contents").mkdir(parents=True)
    (lnf / "metadata.json").write_text("{}")
    sections: dict[str, dict[str, str]] = {}
    if wallpaper_id is not None:
        sections["Wallpaper"] = {"Image": wallpaper_id}
    sections["kwinrc][org.kde.kdecoration2"] = {
        "library": "org.kde.kwin.aurorae",
        "theme": plugin_id(name),
    }
    write_desktop(lnf / "contents" / "defaults", sections)
    return lnf


def _install_fake_wallpaper(wp_id: str, *, fill_mode: str) -> Path:
    wp = paths.wallpapers() / wp_id
    images = wp / "contents" / "images"
    images.mkdir(parents=True)
    (images / "800x600.png").write_bytes(b"\x89PNG")
    (wp / "metadata.json").write_text(
        json.dumps({"KPlugin": {"Id": wp_id}, "X-Themey-FillMode": fill_mode})
    )
    return wp


# --- E2: full apply ----------------------------------------------------


def test_apply_full_requires_lnf_and_deco_installed(fake_kconfig: FakeKConfig) -> None:
    with pytest.raises(apply_mod.ApplyError, match="themey convert"):
        apply_mod.apply_full("e13")


def test_apply_full_requires_deco_when_only_lnf_installed(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_lnf("e13")
    with pytest.raises(apply_mod.ApplyError, match="themey convert"):
        apply_mod.apply_full("e13")


def test_apply_full_requires_lnf_when_only_deco_installed(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    with pytest.raises(apply_mod.ApplyError, match="themey convert"):
        apply_mod.apply_full("e13")


def test_apply_full_call_order_record_then_lookandfeel_then_kwinrc(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["LookAndFeelPackage"] = "com.github.vinceliuice.MacVentura-Dark"
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")

    record_lnf_idx = fake_kconfig.index_of("kdeglobals", apply_mod._PREV_LNF_KEY)
    record_deco_idx = fake_kconfig.index_of("kwinrc", apply_mod._PREV_DECO_KEY)
    lookandfeel_idx = fake_kconfig.index_of("-a", "themey_e13")
    theme_write_idx = fake_kconfig.index_of("--key", "theme", "themey_e13")

    assert record_lnf_idx < lookandfeel_idx
    assert record_deco_idx < lookandfeel_idx
    assert lookandfeel_idx < theme_write_idx


def test_apply_full_never_passes_reset_layout(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    assert all("--resetLayout" not in c for c in fake_kconfig.calls)


def test_apply_full_writes_qml_deco(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["library"] == "org.kde.kwin.aurorae"
    assert fake_kconfig.store["theme"] == "themey_e13"
    assert "BorderSize" not in fake_kconfig.store


def test_apply_full_tiled_wallpaper_triggers_fill_fixup(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    wp = _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13")
    call = fake_kconfig.index_of("plasma-apply-wallpaperimage")
    cmd = fake_kconfig.calls[call]
    assert "-f" in cmd
    assert cmd[cmd.index("-f") + 1] == "tile"
    assert str(wp / "contents" / "images" / "800x600.png") in cmd


def test_apply_full_scaled_wallpaper_no_fixup(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="scaled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13")
    assert not any("plasma-apply-wallpaperimage" in c[0] for c in fake_kconfig.calls)


def test_apply_full_no_wallpaper_section_no_fixup(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13", wallpaper_id=None)
    apply_mod.apply_full("e13")
    assert not any("plasma-apply-wallpaperimage" in c[0] for c in fake_kconfig.calls)


def test_apply_full_missing_lookandfeel_tool_raises(
    fake_kconfig: FakeKConfig, monkeypatch
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")

    def which(n: str) -> str | None:
        return None if n == "plasma-apply-lookandfeel" else f"/usr/bin/{n}"

    monkeypatch.setattr(apply_mod.shutil, "which", which)
    with pytest.raises(apply_mod.ApplyError):
        apply_mod.apply_full("e13")


def test_apply_full_marker_written_once(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["LookAndFeelPackage"] = "org.kde.breeze.desktop"
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    assert fake_kconfig.store[apply_mod._PREV_LNF_KEY] == "org.kde.breeze.desktop"
    # Simulate what a real plasma-apply-lookandfeel would have done.
    fake_kconfig.store["LookAndFeelPackage"] = "themey_e13"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store[apply_mod._PREV_LNF_KEY] == "org.kde.breeze.desktop"
    assert fake_kconfig.store[apply_mod._PREV_DECO_KEY] == "@unset|@unset|@unset"


# --- E3: revert ----------------------------------------------------------


def test_revert_nothing_to_revert(fake_kconfig: FakeKConfig) -> None:
    assert apply_mod.revert() is False
    assert not any(
        "plasma-apply-lookandfeel" in c[0] or "qdbus" in Path(c[0]).name
        for c in fake_kconfig.calls
    )


def test_revert_restores_lnf_and_deco_and_clears_markers(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store[apply_mod._PREV_LNF_KEY] = (
        "com.github.vinceliuice.MacVentura-Dark"
    )
    fake_kconfig.store[apply_mod._PREV_DECO_KEY] = "org.kde.breeze|Breeze|Normal"
    reverted = apply_mod.revert()
    assert reverted is True
    lnf_call = fake_kconfig.index_of(
        "-a", "com.github.vinceliuice.MacVentura-Dark"
    )
    assert "plasma-apply-lookandfeel" in fake_kconfig.calls[lnf_call][0]
    assert fake_kconfig.store["library"] == "org.kde.breeze"
    assert fake_kconfig.store["theme"] == "Breeze"
    assert fake_kconfig.store["BorderSize"] == "Normal"
    assert apply_mod._PREV_LNF_KEY not in fake_kconfig.store
    assert apply_mod._PREV_DECO_KEY not in fake_kconfig.store


def test_revert_deletes_keys_on_unset_sentinel(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store[apply_mod._PREV_LNF_KEY] = "@unset"
    fake_kconfig.store[apply_mod._PREV_DECO_KEY] = "@unset|@unset|@unset"
    fake_kconfig.store["library"] = "org.kde.kwin.aurorae"
    fake_kconfig.store["theme"] = "themey_e13"
    fake_kconfig.store["BorderSize"] = "Normal"
    apply_mod.revert()
    assert "library" not in fake_kconfig.store
    assert "theme" not in fake_kconfig.store
    assert "BorderSize" not in fake_kconfig.store
    # @unset LnF baseline: no plasma-apply-lookandfeel call.
    assert not any("plasma-apply-lookandfeel" in c[0] for c in fake_kconfig.calls)


def test_revert_restores_button_layout_too(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store[apply_mod._PREV_LNF_KEY] = "@unset"
    fake_kconfig.store[apply_mod._PREV_DECO_KEY] = "org.kde.breeze|Breeze|Normal"
    fake_kconfig.store[apply_mod._PREV_BUTTONS_KEY] = "MS|IAX"
    apply_mod.revert()
    assert fake_kconfig.store["ButtonsOnLeft"] == "MS"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"
    assert apply_mod._PREV_BUTTONS_KEY not in fake_kconfig.store
