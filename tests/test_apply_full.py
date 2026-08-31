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
    """Records every subprocess call; serves kreadconfig values back.

    ``fail_on`` lets a test make a specific external tool (by basename,
    e.g. ``"plasma-apply-lookandfeel"``) fail with a non-zero exit and
    given stderr, to exercise the typed-``ApplyError`` wrapping around
    those subprocess calls.
    """

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.calls: list[list[str]] = []
        self.fail_on: dict[str, str] = {}

    def run(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        prog = Path(cmd[0]).name
        if prog in self.fail_on:
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr=self.fail_on[prog]
            )
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


# --- fix round 1: Breeze on the default path -----------------------------


def test_apply_full_breeze_routes_to_breeze_special_case(
    fake_kconfig: FakeKConfig,
) -> None:
    """themey apply Breeze (no --deco-only) must behave exactly like
    apply()'s Breeze special case: no LnF/deco install check, no baseline
    recording, no plasma-apply-lookandfeel call — just the legacy revert."""
    fake_kconfig.store["ButtonsOnLeft"] = "M"
    fake_kconfig.store["ButtonsOnRight"] = "IAX"
    apply_mod.apply_full("Breeze")
    assert fake_kconfig.store["library"] == "org.kde.breeze"
    assert fake_kconfig.store["theme"] == "Breeze"
    assert not any("plasma-apply-lookandfeel" in c[0] for c in fake_kconfig.calls)
    assert apply_mod._PREV_LNF_KEY not in fake_kconfig.store
    assert apply_mod._PREV_DECO_KEY not in fake_kconfig.store


def test_apply_full_breeze_restores_buttons_like_apply(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store[apply_mod._PREV_BUTTONS_KEY] = "MS|IAX"
    apply_mod.apply_full("Breeze")
    assert fake_kconfig.store["ButtonsOnLeft"] == "MS"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"
    assert apply_mod._PREV_BUTTONS_KEY not in fake_kconfig.store


# --- fix round 1: typed errors on plasma-apply-* subprocess failures -----


def test_apply_full_lookandfeel_failure_raises_apply_error(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.fail_on["plasma-apply-lookandfeel"] = "no such package themey_e13"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-lookandfeel"):
        apply_mod.apply_full("e13")


def test_apply_full_wallpaper_failure_raises_apply_error(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    fake_kconfig.fail_on["plasma-apply-wallpaperimage"] = "bad fill mode"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-wallpaperimage"):
        apply_mod.apply_full("e13")


def test_revert_lookandfeel_failure_still_restores_deco_and_buttons(
    fake_kconfig: FakeKConfig,
) -> None:
    """A real-world revert failure: the recorded baseline theme is no
    longer installed. plasma-apply-lookandfeel fails, but the deco triple
    and the button layout must still be restored — the recovery command
    must not abandon the rest of the recovery."""
    fake_kconfig.store[apply_mod._PREV_LNF_KEY] = (
        "com.github.vinceliuice.MacVentura-Dark"
    )
    fake_kconfig.store[apply_mod._PREV_DECO_KEY] = "org.kde.breeze|Breeze|Normal"
    fake_kconfig.store[apply_mod._PREV_BUTTONS_KEY] = "MS|IAX"
    fake_kconfig.fail_on["plasma-apply-lookandfeel"] = "package not found"

    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-lookandfeel"):
        apply_mod.revert()

    assert fake_kconfig.store["library"] == "org.kde.breeze"
    assert fake_kconfig.store["theme"] == "Breeze"
    assert fake_kconfig.store["BorderSize"] == "Normal"
    assert fake_kconfig.store["ButtonsOnLeft"] == "MS"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"
    assert apply_mod._PREV_BUTTONS_KEY not in fake_kconfig.store
    # The deco half succeeded, so its marker is cleared...
    assert apply_mod._PREV_DECO_KEY not in fake_kconfig.store
    # ...but the LnF half failed, so its marker is the only remaining
    # record of the baseline global theme and must survive for a retry.
    assert fake_kconfig.store[apply_mod._PREV_LNF_KEY] == (
        "com.github.vinceliuice.MacVentura-Dark"
    )
    # Reconfigure still ran despite the LnF failure.
    assert any(Path(c[0]).name.startswith("qdbus") for c in fake_kconfig.calls)


def test_revert_retry_with_only_lnf_marker_succeeds(fake_kconfig: FakeKConfig) -> None:
    """After a failed revert leaves only the LnF marker behind (previous
    test), a later `themey apply --revert` must retry just the LnF restore,
    succeed, delete that marker, and NOT report "nothing to revert" —
    even though ThemeyPrevDeco/ThemeyPrevButtons are already gone."""
    fake_kconfig.store[apply_mod._PREV_LNF_KEY] = (
        "com.github.vinceliuice.MacVentura-Dark"
    )
    # No ThemeyPrevDeco, no ThemeyPrevButtons — already restored earlier.

    reverted = apply_mod.revert()

    assert reverted is True
    lnf_call = fake_kconfig.index_of(
        "-a", "com.github.vinceliuice.MacVentura-Dark"
    )
    assert "plasma-apply-lookandfeel" in fake_kconfig.calls[lnf_call][0]
    assert apply_mod._PREV_LNF_KEY not in fake_kconfig.store
    # No deco keys touched — nothing was recorded to restore this time.
    assert "library" not in fake_kconfig.store
    assert "theme" not in fake_kconfig.store
    assert any(Path(c[0]).name.startswith("qdbus") for c in fake_kconfig.calls)


# --- explicit color-scheme apply (plasma-apply-lookandfeel does NOT apply
# --- colors past an explicit user-layer [General] ColorScheme — verified
# --- live 2026-08-31 on Plasma 6.6.6) ----------------------------------


def _install_fake_colors(name: str = "e13") -> Path:
    scheme = paths.color_schemes() / f"{plugin_id(name)}.colors"
    scheme.parent.mkdir(parents=True, exist_ok=True)
    scheme.write_text("[General]\nColorScheme=" + plugin_id(name) + "\n")
    return scheme


def _install_full(name: str = "e13") -> None:
    _install_fake_deco(name)
    _install_fake_lnf(name)
    _install_fake_colors(name)


def test_apply_full_records_prev_colorscheme_and_applies_scheme(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_full("e13")
    fake_kconfig.store["ColorScheme"] = "MacVenturaDark"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevColorScheme"] == "MacVenturaDark"
    i_lnf = fake_kconfig.index_of("plasma-apply-lookandfeel")
    i_colors = fake_kconfig.index_of("plasma-apply-colorscheme")
    assert i_colors > i_lnf
    assert fake_kconfig.calls[i_colors][-1] == "themey_e13"


def test_apply_full_no_colorscheme_installed_skips_scheme_apply(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    assert "PrevColorScheme" not in fake_kconfig.store
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("plasma-apply-colorscheme")


def test_apply_full_prev_colorscheme_unset_sentinel(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_full("e13")
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevColorScheme"] == "@unset"


def test_apply_full_colorscheme_marker_written_once(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_full("e13")
    fake_kconfig.store["ColorScheme"] = "MacVenturaDark"
    apply_mod.apply_full("e13")
    fake_kconfig.store["ColorScheme"] = "themey_e13"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevColorScheme"] == "MacVenturaDark"


def test_apply_full_colorscheme_failure_raises_apply_error(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_full("e13")
    fake_kconfig.fail_on["plasma-apply-colorscheme"] = "no such scheme"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-colorscheme"):
        apply_mod.apply_full("e13")


def test_revert_restores_prev_colorscheme_and_clears_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevColorScheme"] = "MacVenturaDark"
    assert apply_mod.revert() is True
    i = fake_kconfig.index_of("plasma-apply-colorscheme")
    assert fake_kconfig.calls[i][-1] == "MacVenturaDark"
    assert "PrevColorScheme" not in fake_kconfig.store


def test_revert_colorscheme_unset_deletes_user_key(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevColorScheme"] = "@unset"
    fake_kconfig.store["ColorScheme"] = "themey_e13"
    assert apply_mod.revert() is True
    assert "ColorScheme" not in fake_kconfig.store
    assert "PrevColorScheme" not in fake_kconfig.store
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("plasma-apply-colorscheme")


def test_revert_colorscheme_failure_keeps_marker_restores_rest(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevColorScheme"] = "MacVenturaDark"
    fake_kconfig.store["ThemeyPrevDeco"] = "org.kde.breeze|Breeze|@unset"
    fake_kconfig.fail_on["plasma-apply-colorscheme"] = "scheme gone"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-colorscheme"):
        apply_mod.revert()
    assert fake_kconfig.store["PrevColorScheme"] == "MacVenturaDark"
    assert fake_kconfig.store["theme"] == "Breeze"
    assert "ThemeyPrevDeco" not in fake_kconfig.store
