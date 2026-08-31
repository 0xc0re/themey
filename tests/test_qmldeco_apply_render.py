"""Phase 4 — apply + render wiring for the QML decoration backend.

QML applies write library=org.kde.kwin.aurorae + the raw package id as
theme=, and MUST NOT touch ButtonsOnLeft/Right or BorderSize (the theme
draws its own buttons and sets unclamped borders). The render harness's
qml mode uses the same kwinrc shape and stages the package into the
private session's kwin/decorations/.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from themey import apply as apply_mod
from themey import paths
from themey.render import RenderError, _qml_error_lines, write_kwinrc


class FakeKConfig:
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
            return subprocess.CompletedProcess(
                cmd, 0, stdout=self.store.get(key, "") + "\n"
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="")


@pytest.fixture
def fake_kconfig(monkeypatch, fake_home: Path) -> FakeKConfig:
    fk = FakeKConfig()
    monkeypatch.setattr(apply_mod.shutil, "which", lambda n: f"/usr/bin/{n}")
    monkeypatch.setattr(apply_mod.subprocess, "run", fk.run)
    return fk


def _install_fake_qml_package(name: str = "e13") -> Path:
    from themey.slug import plugin_id

    pkg = paths.kwin_decorations() / plugin_id(name)
    (pkg / "contents" / "ui").mkdir(parents=True)
    (pkg / "metadata.json").write_text("{}")
    return pkg


def test_apply_qml_sets_legacy_library_and_raw_theme(fake_kconfig: FakeKConfig):
    _install_fake_qml_package("e13")
    apply_mod.apply("e13", backend="qml")
    assert fake_kconfig.store["library"] == "org.kde.kwin.aurorae"
    assert fake_kconfig.store["theme"] == "themey_e13"


def test_apply_qml_touches_neither_buttons_nor_border_size(
    fake_kconfig: FakeKConfig,
):
    fake_kconfig.store["ButtonsOnLeft"] = "M"
    fake_kconfig.store["ButtonsOnRight"] = "IAX"
    _install_fake_qml_package("e13")
    apply_mod.apply("e13", backend="qml")
    assert "BorderSize" not in fake_kconfig.store
    assert fake_kconfig.store["ButtonsOnLeft"] == "M"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"
    assert apply_mod._PREV_BUTTONS_KEY not in fake_kconfig.store


def test_apply_qml_accepts_plugin_id_directly(fake_kconfig: FakeKConfig):
    _install_fake_qml_package("e13")
    apply_mod.apply("themey_e13", backend="qml")
    assert fake_kconfig.store["theme"] == "themey_e13"


def test_apply_qml_missing_package_raises(fake_kconfig: FakeKConfig):
    with pytest.raises(apply_mod.ApplyError, match="not installed"):
        apply_mod.apply("nosuch", backend="qml")


def test_apply_breeze_still_restores_after_qml(fake_kconfig: FakeKConfig):
    """The snapshot/restore machinery survives untouched for the revert path."""
    _install_fake_qml_package("e13")
    fake_kconfig.store[apply_mod._PREV_BUTTONS_KEY] = "MS|IAX"
    apply_mod.apply("Breeze")
    assert fake_kconfig.store["library"] == "org.kde.breeze"
    assert fake_kconfig.store["ButtonsOnLeft"] == "MS"
    assert fake_kconfig.store["ButtonsOnRight"] == "IAX"


def test_write_kwinrc_qml_mode(tmp_path):
    kwinrc = write_kwinrc(
        tmp_path, name="themey_e13", plugin="qml", border_size="Normal"
    )
    text = kwinrc.read_text()
    assert "library=org.kde.kwin.aurorae\n" in text
    assert "theme=themey_e13\n" in text
    assert "__aurorae__svg__" not in text
    assert "BorderSize" not in text
    assert "ButtonsOn" not in text


def test_write_kwinrc_svg_mode_unchanged(tmp_path):
    text = write_kwinrc(
        tmp_path, name="e13", plugin="legacy", border_size="Normal",
        buttons=("XILS", ""),
    ).read_text()
    assert "theme=__aurorae__svg__e13\n" in text
    assert "BorderSize=Normal\n" in text


def test_resolve_theme_dir_qml_installed(fake_home):
    from themey.render import resolve_theme_dir

    pkg = _install_fake_qml_package("e13")
    name, theme_dir = resolve_theme_dir(
        "e13", scale=2, work=Path("/nonexistent"), qml=True
    )
    assert (name, theme_dir) == ("themey_e13", pkg)


def test_resolve_theme_dir_qml_missing(fake_home):
    from themey.render import resolve_theme_dir

    with pytest.raises(RenderError, match="QML decoration"):
        resolve_theme_dir("ghost", scale=2, work=Path("/nonexistent"), qml=True)


def test_qml_error_lines_filter():
    text = (
        "kwin_core: something normal\n"
        "file:///x/main.qml:12:5: TypeError: Cannot read property 'x' of null\n"
        "qml: harmless console.log\n"
        "file:///x/ThemeyPart.qml:26:5: QML ThemeyPart: "
        "Binding loop detected for property \"geo\"\n"
    )
    lines = _qml_error_lines(text)
    assert len(lines) == 2
    assert "TypeError" in lines[0]
    assert "Binding loop" in lines[1]
