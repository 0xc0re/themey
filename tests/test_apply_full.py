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
from themey import install as install_mod
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
        #: stdout served for the plasmashell panel-length READ script
        #: ("" = no panels reported).
        self.panel_read_reply: str = ""
        #: stdout served for the iconbox CREATE script (the new panel's id;
        #: "" = plasmashell printed nothing, the failure signal).
        self.iconbox_create_reply: str = "301"
        #: stdout served for the pager-panel CREATE script.
        self.pager_create_reply: str = "302"
        #: stdout served for the furniture existence-check scripts.
        self.iconbox_exists_reply: str = "missing"
        #: stdout served for the iconbox REMOVAL script ("" = the script
        #: threw and printed nothing — qdbus still exits 0).
        self.iconbox_remove_reply: str = "removed"

    def run(self, cmd, **kwargs):
        self.calls.append(list(cmd))
        prog = Path(cmd[0]).name
        if prog in self.fail_on:
            return subprocess.CompletedProcess(
                cmd, 1, stdout="", stderr=self.fail_on[prog]
            )
        if any("evaluateScript" in tok for tok in cmd) and "out.push" in cmd[-1]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=self.panel_read_reply + "\n"
            )
        if any("evaluateScript" in tok for tok in cmd) and "new Panel" in cmd[-1]:
            reply = (
                self.iconbox_create_reply
                if "icontasks" in cmd[-1]
                else self.pager_create_reply
            )
            return subprocess.CompletedProcess(cmd, 0, stdout=reply + "\n")
        if any("evaluateScript" in tok for tok in cmd) and "'exists'" in cmd[-1]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=self.iconbox_exists_reply + "\n"
            )
        if any("evaluateScript" in tok for tok in cmd) and "'removed'" in cmd[-1]:
            return subprocess.CompletedProcess(
                cmd, 0, stdout=self.iconbox_remove_reply + "\n"
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
    monkeypatch.setattr(apply_mod, "_AURORAE_FLUSH_WAIT_S", 0.0, raising=False)
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


def test_apply_full_bounces_deco_through_breeze_before_write(
    fake_kconfig: FakeKConfig,
) -> None:
    """Same Aurorae component-cache flush as the deco-only path: a re-run
    of ``convert`` + ``apply`` on the already-active theme must not leave
    KWin rendering the stale cached QML (see test_apply.py)."""
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    theme_writes = [
        c[-1]
        for c in fake_kconfig.calls
        if Path(c[0]).name.startswith("kwriteconfig")
        and "--key" in c
        and "--delete" not in c
        and c[c.index("--key") + 1] == "theme"
    ]
    assert theme_writes == ["Breeze", "themey_e13"]
    breeze_idx = fake_kconfig.index_of("kwriteconfig", "Breeze")
    reconfigures = [
        i for i, c in enumerate(fake_kconfig.calls) if "reconfigure" in c
    ]
    assert any(i > breeze_idx for i in reconfigures)


def test_apply_full_tiled_wallpaper_triggers_fill_fixup(
    fake_kconfig: FakeKConfig,
) -> None:
    """Tiled fix-up = image apply (NO -f: the tool has no tile token on
    Plasma 6.6, verified live) + a plasmashell script writing FillMode=3."""
    _install_fake_deco("e13")
    wp = _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13")
    call = fake_kconfig.index_of("plasma-apply-wallpaperimage")
    cmd = fake_kconfig.calls[call]
    assert "-f" not in cmd
    assert str(wp / "contents" / "images" / "800x600.png") in cmd
    script_call = fake_kconfig.index_of("writeConfig('FillMode', 3)")
    script = fake_kconfig.calls[script_call][-1]
    assert "org.kde.plasmashell" in fake_kconfig.calls[script_call]
    assert "reloadConfig()" in script  # required for the live repaint
    assert script_call > call  # image first, then the fill-mode script


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


def _install_fake_style(name: str = "e13") -> Path:
    style = paths.desktop_themes() / plugin_id(name)
    style.mkdir(parents=True, exist_ok=True)
    (style / "metadata.json").write_text("{}")
    return style


def _make_kcache(home: Path, pkg_id: str) -> Path:
    cache = home / ".cache"
    cache.mkdir(exist_ok=True)
    kcache = cache / f"plasma_theme_{pkg_id}_v1.0.kcache"
    kcache.write_bytes(b"stale")
    return kcache


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


# --- explicit Plasma Style apply (plasmarc [Theme] name is an explicit
# --- user-layer value on the reference machine — name=Otto — so the LnF
# --- apply cannot be trusted to displace it; same shadowing as colors) --


def test_apply_full_applies_style_and_records_marker(
    fake_kconfig: FakeKConfig, monkeypatch, fake_home: Path,
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    _install_fake_style("e13")
    fake_kconfig.store["name"] = "Otto"  # plasmarc [Theme] name
    kcache = _make_kcache(fake_home, "themey_e13")

    apply_mod.apply_full("e13")

    assert fake_kconfig.store["PrevPlasmaTheme"] == "Otto"
    i_colors_or_lnf = fake_kconfig.index_of("plasma-apply-lookandfeel")
    i_style = fake_kconfig.index_of("plasma-apply-desktoptheme")
    i_deco = fake_kconfig.index_of("--key", "theme", "themey_e13")
    assert fake_kconfig.calls[i_style][-1] == "themey_e13"
    assert i_colors_or_lnf < i_style < i_deco
    # The Version-keyed cache never invalidates on re-convert — apply
    # must have deleted it before the style apply.
    assert not kcache.exists()


def test_apply_full_no_style_installed_skips_style_apply(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    assert "PrevPlasmaTheme" not in fake_kconfig.store
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("plasma-apply-desktoptheme")


def test_apply_full_style_after_colors_before_deco(
    fake_kconfig: FakeKConfig, monkeypatch,
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    _install_full("e13")
    _install_fake_style("e13")
    apply_mod.apply_full("e13")
    i_record = fake_kconfig.index_of("kdeglobals", "PrevPlasmaTheme")
    i_lnf = fake_kconfig.index_of("plasma-apply-lookandfeel")
    i_colors = fake_kconfig.index_of("plasma-apply-colorscheme")
    i_style = fake_kconfig.index_of("plasma-apply-desktoptheme")
    i_deco = fake_kconfig.index_of("--key", "theme", "themey_e13")
    assert i_record < i_lnf < i_colors < i_style < i_deco


def test_apply_full_style_marker_written_once(
    fake_kconfig: FakeKConfig, monkeypatch,
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    _install_fake_style("e13")
    fake_kconfig.store["name"] = "Otto"
    apply_mod.apply_full("e13")
    fake_kconfig.store["name"] = "themey_e13"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevPlasmaTheme"] == "Otto"


def test_apply_full_style_unset_sentinel(
    fake_kconfig: FakeKConfig, monkeypatch,
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    _install_fake_style("e13")
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevPlasmaTheme"] == "@unset"


def test_apply_full_style_failure_raises_apply_error(
    fake_kconfig: FakeKConfig, monkeypatch,
) -> None:
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    _install_fake_style("e13")
    fake_kconfig.fail_on["plasma-apply-desktoptheme"] = "no such theme"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-desktoptheme"):
        apply_mod.apply_full("e13")


def test_clear_style_cache_respects_xdg_cache_home(
    monkeypatch, tmp_path: Path,
) -> None:
    cache_dir = tmp_path / "xdg-cache"
    cache_dir.mkdir()
    stale = cache_dir / "plasma_theme_themey_e13.kcache"
    stale.write_bytes(b"stale")
    other = cache_dir / "plasma_theme_Otto.kcache"
    other.write_bytes(b"keep")
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache_dir))
    install_mod.clear_style_cache("themey_e13")
    assert not stale.exists()
    assert other.exists()  # other themes' caches are left alone


def test_revert_restores_prev_plasmatheme_and_clears_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevPlasmaTheme"] = "Otto"
    assert apply_mod.revert() is True
    i = fake_kconfig.index_of("plasma-apply-desktoptheme")
    assert fake_kconfig.calls[i][-1] == "Otto"
    assert "PrevPlasmaTheme" not in fake_kconfig.store


def test_revert_plasmatheme_unset_deletes_user_key(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevPlasmaTheme"] = "@unset"
    fake_kconfig.store["name"] = "themey_e13"  # plasmarc [Theme] name
    assert apply_mod.revert() is True
    assert "name" not in fake_kconfig.store
    assert "PrevPlasmaTheme" not in fake_kconfig.store
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("plasma-apply-desktoptheme")


def test_revert_plasmatheme_failure_keeps_marker_restores_rest(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevPlasmaTheme"] = "Otto"
    fake_kconfig.store["ThemeyPrevDeco"] = "org.kde.breeze|Breeze|@unset"
    fake_kconfig.fail_on["plasma-apply-desktoptheme"] = "theme gone"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-desktoptheme"):
        apply_mod.revert()
    assert fake_kconfig.store["PrevPlasmaTheme"] == "Otto"
    assert fake_kconfig.store["theme"] == "Breeze"
    assert "ThemeyPrevDeco" not in fake_kconfig.store


def test_apply_full_sets_panels_fit_and_records_modes(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.panel_read_reply = "1058=fill|1060=custom"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevPanelLengthModes"] == "1058=fill|1060=custom"
    i = fake_kconfig.index_of("p.lengthMode = 'fit'")
    assert "org.kde.plasmashell" in fake_kconfig.calls[i]


def test_apply_full_panels_fit_before_wallpaper_fixup(
    fake_kconfig: FakeKConfig,
) -> None:
    """A failing wallpaper fix-up must not cost the panel feel: the fit
    script runs first, and the wallpaper error still raises after."""
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    fake_kconfig.panel_read_reply = "1195=fill"
    fake_kconfig.fail_on["plasma-apply-wallpaperimage"] = "boom"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-wallpaperimage"):
        apply_mod.apply_full("e13")
    i_fit = fake_kconfig.index_of("p.lengthMode = 'fit'")
    i_wp = fake_kconfig.index_of("plasma-apply-wallpaperimage")
    assert i_fit < i_wp
    assert fake_kconfig.store["PrevPanelLengthModes"] == "1195=fill"


def test_apply_full_panel_marker_written_once(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.panel_read_reply = "1058=fill"
    apply_mod.apply_full("e13")
    fake_kconfig.panel_read_reply = "1058=fit"  # already themey'd
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevPanelLengthModes"] == "1058=fill"


def test_apply_full_no_panels_no_marker_no_fit_script(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")  # panel_read_reply defaults to ""
    assert "PrevPanelLengthModes" not in fake_kconfig.store
    # The fit-ALL loop specifically — the iconbox creation script sets its
    # own panel's lengthMode and is allowed to run without other panels.
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("for (const p of panels()) { p.lengthMode = 'fit'; }")


def test_revert_restores_panel_modes_and_clears_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevPanelLengthModes"] = "1058=fill|1060=custom"
    assert apply_mod.revert() is True
    i = fake_kconfig.index_of("p.id == 1058")
    script = fake_kconfig.calls[i][-1]
    assert "p.lengthMode = 'fill'" in script
    assert "p.id == 1060" in script and "'custom'" in script
    assert "PrevPanelLengthModes" not in fake_kconfig.store


def test_revert_panel_restore_failure_keeps_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevPanelLengthModes"] = "1058=fill"
    fake_kconfig.fail_on["qdbus6"] = "plasmashell gone"
    with pytest.raises(apply_mod.ApplyError, match="panel"):
        apply_mod.revert()
    assert fake_kconfig.store["PrevPanelLengthModes"] == "1058=fill"


def test_apply_full_creates_pager_panel_and_records_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    """E16 furniture, piece one: a thick content-sized pager panel hugging
    the TOP-left ('left' alignment == top on a vertical panel) — where E16
    kept its pager window, with cells big enough to read the theme art."""
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    i = fake_kconfig.index_of("new Panel", "org.kde.plasma.pager")
    script = fake_kconfig.calls[i][-1]
    assert "org.kde.plasmashell" in fake_kconfig.calls[i]
    assert "p.location = 'left'" in script
    assert "p.alignment = 'left'" in script
    assert "p.lengthMode = 'fit'" in script
    assert "p.height = 130" in script
    # A scripted `new Panel` starts with min=max=full-screen and
    # lengthMode='fit' does NOT clear them (verified live 2026-08-31:
    # the panel drew as a full-height column around 33px of content).
    assert "p.minimumLength = 0" in script
    assert "p.addWidget('org.kde.plasma.pager')" in script
    # Dual-head virtual desktops are ultrawide; per-screen cells keep
    # desktop aspect readable.
    assert "w.writeConfig('showOnlyCurrentScreen', true)" in script
    assert "icontasks" not in script
    assert "print(p.id)" in script
    assert fake_kconfig.store["PagerPanel"] == "302"


def test_apply_full_creates_iconbox_panel_and_records_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    """E16 furniture, piece two: a slim content-sized panel hugging the
    BOTTOM-left ('right' alignment == bottom on a vertical panel) holding
    an icons-only task manager showing only minimized windows — the
    iconbox."""
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    i = fake_kconfig.index_of("new Panel", "icontasks")
    script = fake_kconfig.calls[i][-1]
    assert "org.kde.plasmashell" in fake_kconfig.calls[i]
    assert "p.location = 'left'" in script
    assert "p.alignment = 'right'" in script
    assert "p.lengthMode = 'fit'" in script
    assert "p.height = 60" in script
    assert "p.minimumLength = 0" in script
    assert "p.addWidget('org.kde.plasma.icontasks')" in script
    assert "org.kde.plasma.pager" not in script
    assert "w.writeConfig('showOnlyMinimized', true)" in script
    assert "w.writeConfig('launchers', '')" in script
    assert "print(p.id)" in script
    assert fake_kconfig.store["IconboxPanel"] == "301"


def test_apply_full_iconbox_after_fit_before_wallpaper_and_out_of_baseline(
    fake_kconfig: FakeKConfig,
) -> None:
    """Created AFTER the fit snapshot (so the new panel never pollutes the
    PrevPanelLengthModes baseline) and BEFORE the failure-prone wallpaper
    fix-up."""
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    fake_kconfig.panel_read_reply = "1058=fill"
    apply_mod.apply_full("e13")
    i_fit = fake_kconfig.index_of("p.lengthMode = 'fit'")
    i_create = fake_kconfig.index_of("new Panel")
    i_wp = fake_kconfig.index_of("plasma-apply-wallpaperimage")
    assert i_fit < i_create < i_wp
    assert fake_kconfig.store["PrevPanelLengthModes"] == "1058=fill"
    assert "301" not in fake_kconfig.store["PrevPanelLengthModes"]
    assert "302" not in fake_kconfig.store["PrevPanelLengthModes"]


def test_apply_full_second_apply_reuses_live_iconbox(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")
    fake_kconfig.iconbox_exists_reply = "exists"
    apply_mod.apply_full("e13")
    creates = [c for c in fake_kconfig.calls if "new Panel" in c[-1]]
    assert len(creates) == 2  # one per furniture panel, first apply only
    assert fake_kconfig.store["IconboxPanel"] == "301"
    assert fake_kconfig.store["PagerPanel"] == "302"


def test_apply_full_recreates_iconbox_when_panel_gone(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.store["IconboxPanel"] = "290"
    fake_kconfig.store["PagerPanel"] = "291"
    fake_kconfig.iconbox_exists_reply = "missing"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["IconboxPanel"] == "301"
    assert fake_kconfig.store["PagerPanel"] == "302"


def test_apply_full_iconbox_create_without_id_raises_no_stale_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    """qdbus exits 0 even when the script throws — the printed id is the
    real success signal."""
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.iconbox_create_reply = ""
    with pytest.raises(apply_mod.ApplyError, match="iconbox"):
        apply_mod.apply_full("e13")
    assert "IconboxPanel" not in fake_kconfig.store
    # The pager panel is created first and keeps its marker — the retry
    # skips it instead of doubling it.
    assert fake_kconfig.store["PagerPanel"] == "302"


def test_apply_full_iconbox_survives_wallpaper_failure(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    fake_kconfig.fail_on["plasma-apply-wallpaperimage"] = "boom"
    with pytest.raises(apply_mod.ApplyError, match="plasma-apply-wallpaperimage"):
        apply_mod.apply_full("e13")
    fake_kconfig.index_of("new Panel")
    assert fake_kconfig.store["IconboxPanel"] == "301"
    assert fake_kconfig.store["PagerPanel"] == "302"


def test_apply_breeze_never_creates_iconbox(fake_kconfig: FakeKConfig) -> None:
    apply_mod.apply_full("Breeze")
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("new Panel")


def test_revert_removes_iconbox_and_clears_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["IconboxPanel"] = "301"
    assert apply_mod.revert() is True
    i = fake_kconfig.index_of("panelById(301)")
    script = fake_kconfig.calls[i][-1]
    assert "remove()" in script
    assert "IconboxPanel" not in fake_kconfig.store


def test_revert_removes_both_furniture_panels(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["IconboxPanel"] = "301"
    fake_kconfig.store["PagerPanel"] = "302"
    assert apply_mod.revert() is True
    fake_kconfig.index_of("panelById(301)")
    fake_kconfig.index_of("panelById(302)")
    assert "IconboxPanel" not in fake_kconfig.store
    assert "PagerPanel" not in fake_kconfig.store


def test_revert_with_only_iconbox_marker_is_a_revert(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["IconboxPanel"] = "301"
    assert apply_mod.revert() is True


def test_revert_iconbox_removal_failure_keeps_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["IconboxPanel"] = "301"
    fake_kconfig.fail_on["qdbus6"] = "plasmashell gone"
    with pytest.raises(apply_mod.ApplyError, match="iconbox"):
        apply_mod.revert()
    assert fake_kconfig.store["IconboxPanel"] == "301"


def test_revert_iconbox_script_error_keeps_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    """qdbus exits 0 even when the removal script throws — the printed
    sentinel is the real success signal, and without it the marker (the
    only handle on the created panel) must survive for a retry."""
    fake_kconfig.store["IconboxPanel"] = "301"
    fake_kconfig.iconbox_remove_reply = ""
    with pytest.raises(apply_mod.ApplyError, match="iconbox"):
        apply_mod.revert()
    assert fake_kconfig.store["IconboxPanel"] == "301"


def test_revert_iconbox_absent_panel_still_clears_marker(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["IconboxPanel"] = "301"
    fake_kconfig.iconbox_remove_reply = "absent"
    assert apply_mod.revert() is True
    assert "IconboxPanel" not in fake_kconfig.store


def test_iconbox_non_ascii_digit_marker_never_interpolated(
    fake_kconfig: FakeKConfig,
) -> None:
    """str.isdigit() alone accepts superscript digits — those must be
    treated like any other tampered marker, not interpolated."""
    weird = "³01"  # "³01": isdigit() is True, not a valid panel id
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.store["IconboxPanel"] = weird
    apply_mod.apply_full("e13")
    assert all(weird not in tok for c in fake_kconfig.calls for tok in c)
    assert fake_kconfig.store["IconboxPanel"] == "301"

    fake_kconfig.store["IconboxPanel"] = weird
    assert apply_mod.revert() is True
    assert all(
        weird not in c[-1]
        for c in fake_kconfig.calls
        if any("evaluateScript" in tok for tok in c)
    )
    assert "IconboxPanel" not in fake_kconfig.store


def test_apply_full_restart_skipped_when_systemctl_missing(
    fake_kconfig: FakeKConfig, monkeypatch, caplog,
) -> None:
    """No systemd is a graceful skip with a hint, never a failed apply."""
    monkeypatch.setattr(
        apply_mod.shutil, "which",
        lambda n: None if n == "systemctl" else f"/usr/bin/{n}",
    )
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13")  # must not raise
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("systemctl")
    assert "restart plasmashell manually" in caplog.text


def test_revert_removes_iconbox_before_panel_mode_restore(
    fake_kconfig: FakeKConfig,
) -> None:
    """The mode-restore script must iterate only surviving panels."""
    fake_kconfig.store["IconboxPanel"] = "301"
    fake_kconfig.store["PrevPanelLengthModes"] = "1058=fill"
    assert apply_mod.revert() is True
    i_remove = fake_kconfig.index_of("panelById(301)")
    i_restore = fake_kconfig.index_of("p.id == 1058")
    assert i_remove < i_restore


def test_iconbox_non_digit_marker_never_interpolated(
    fake_kconfig: FakeKConfig,
) -> None:
    """kdeglobals is user-editable — a tampered marker must never reach a
    plasmashell script (apply recreates; revert just drops the marker)."""
    evil = "0); panelById(1).remove(); print("
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.store["IconboxPanel"] = evil
    apply_mod.apply_full("e13")
    assert all(evil not in tok for c in fake_kconfig.calls for tok in c)
    assert fake_kconfig.store["IconboxPanel"] == "301"

    fake_kconfig.store["IconboxPanel"] = evil
    assert apply_mod.revert() is True
    assert all(
        evil not in c[-1]
        for c in fake_kconfig.calls
        if any("evaluateScript" in tok for tok in c)
    )
    assert "IconboxPanel" not in fake_kconfig.store


def test_apply_full_sets_vertical_desktop_grid(
    fake_kconfig: FakeKConfig,
) -> None:
    """One pager column: kwinrc [Desktops] Rows = Number, prior Rows
    recorded once, and the LIVE rows set over D-Bus — KWin reads the
    config key only at startup (verified live 2026-08-31: kwriteconfig +
    reconfigure left the layout unchanged)."""
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.store["Number"] = "2"
    fake_kconfig.store["Rows"] = "1"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["Rows"] == "2"
    assert fake_kconfig.store["PrevDesktopRows"] == "1"
    i = fake_kconfig.index_of("VirtualDesktopManager", "rows")
    cmd = fake_kconfig.calls[i]
    assert "org.freedesktop.DBus.Properties.Set" in cmd
    assert cmd[-1] == "2"


def test_apply_full_desktop_rows_marker_written_once(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    fake_kconfig.store["Number"] = "2"
    apply_mod.apply_full("e13")
    assert fake_kconfig.store["PrevDesktopRows"] == "@unset"
    fake_kconfig.iconbox_exists_reply = "exists"
    apply_mod.apply_full("e13")  # Rows now "2" — must not become baseline
    assert fake_kconfig.store["PrevDesktopRows"] == "@unset"


def test_apply_full_no_desktop_count_skips_grid(
    fake_kconfig: FakeKConfig,
) -> None:
    _install_fake_deco("e13")
    _install_fake_lnf("e13")
    apply_mod.apply_full("e13")  # no [Desktops] Number readable
    assert "Rows" not in fake_kconfig.store
    assert "PrevDesktopRows" not in fake_kconfig.store


def test_revert_restores_desktop_rows(fake_kconfig: FakeKConfig) -> None:
    fake_kconfig.store["PrevDesktopRows"] = "1"
    fake_kconfig.store["Rows"] = "2"
    assert apply_mod.revert() is True
    assert fake_kconfig.store["Rows"] == "1"
    assert "PrevDesktopRows" not in fake_kconfig.store
    i = fake_kconfig.index_of("VirtualDesktopManager", "rows")
    assert fake_kconfig.calls[i][-1] == "1"


def test_revert_unset_desktop_rows_deletes_key(
    fake_kconfig: FakeKConfig,
) -> None:
    fake_kconfig.store["PrevDesktopRows"] = "@unset"
    fake_kconfig.store["Rows"] = "2"
    assert apply_mod.revert() is True
    assert "Rows" not in fake_kconfig.store
    assert "PrevDesktopRows" not in fake_kconfig.store
    i = fake_kconfig.index_of("VirtualDesktopManager", "rows")
    assert fake_kconfig.calls[i][-1] == "1"  # KWin default


def test_revert_retry_with_only_plasma_marker_succeeds(
    fake_kconfig: FakeKConfig,
) -> None:
    """After a failed style restore leaves only PrevPlasmaTheme behind,
    a later revert retries just that half — not "nothing to revert"."""
    fake_kconfig.store["PrevPlasmaTheme"] = "Otto"
    assert apply_mod.revert() is True
    i = fake_kconfig.index_of("plasma-apply-desktoptheme")
    assert fake_kconfig.calls[i][-1] == "Otto"
    assert "PrevPlasmaTheme" not in fake_kconfig.store
    assert "library" not in fake_kconfig.store


def test_apply_full_tiled_wallpaper_restarts_plasmashell_last(
    fake_kconfig: FakeKConfig,
) -> None:
    """plasmashell 6.6.6 never repaints fill-mode from scripting (verified
    live) — a tiled wallpaper needs a shell restart, dead last so it cannot
    race any evaluateScript call."""
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13")
    i_restart = fake_kconfig.index_of("systemctl")
    cmd = fake_kconfig.calls[i_restart]
    assert cmd[1:] == ["--user", "restart", "plasma-plasmashell"]
    i_reconf = fake_kconfig.index_of("org.kde.KWin", "reconfigure")
    assert i_reconf < i_restart
    assert i_restart == len(fake_kconfig.calls) - 1


def test_apply_full_scaled_wallpaper_no_restart(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="scaled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13")
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("systemctl")


def test_apply_full_no_restart_shell_opt_out(fake_kconfig: FakeKConfig) -> None:
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    apply_mod.apply_full("e13", restart_shell=False)
    with pytest.raises(AssertionError):
        fake_kconfig.index_of("systemctl")


def test_apply_full_restart_failure_only_warns(
    fake_kconfig: FakeKConfig, caplog,
) -> None:
    """The theme is fully applied by restart time — a failed restart is a
    warning (repaint waits for the next login), never a failed apply."""
    _install_fake_deco("e13")
    _install_fake_wallpaper("themey_e13_tanbg", fill_mode="tiled")
    _install_fake_lnf("e13", wallpaper_id="themey_e13_tanbg")
    fake_kconfig.fail_on["systemctl"] = "unit not loaded"
    apply_mod.apply_full("e13")  # must not raise
    assert "restart" in caplog.text.lower()
