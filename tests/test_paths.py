"""Tests for the XDG-aware paths module (themey.paths)."""
from __future__ import annotations


def test_aurorae_themes_default(monkeypatch):
    """With HOME=/tmp/abc and XDG_DATA_HOME unset, aurorae_themes() returns the XDG default path."""
    monkeypatch.setenv("HOME", "/tmp/abc")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    from themey.paths import aurorae_themes

    result = aurorae_themes()
    assert str(result) == "/tmp/abc/.local/share/aurorae/themes"


def test_aurorae_themes_xdg_override(monkeypatch):
    """With XDG_DATA_HOME set, aurorae_themes() uses it instead of ~/.local/share."""
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")

    from themey.paths import aurorae_themes

    result = aurorae_themes()
    assert str(result) == "/tmp/xdg/aurorae/themes"


def test_snap_xdg_data_home_ignored(monkeypatch):
    """A snap-sandbox XDG_DATA_HOME (VS Code terminal) is ignored: KWin only
    reads the real ~/.local/share, so installing there would be invisible."""
    monkeypatch.setenv("HOME", "/tmp/abc")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/abc/snap/code/259/.local/share")

    from themey.paths import aurorae_themes

    result = aurorae_themes()
    assert str(result) == "/tmp/abc/.local/share/aurorae/themes"


def test_snap_xdg_data_home_warns(monkeypatch, caplog):
    """Ignoring a snap XDG_DATA_HOME is logged so the redirect is not silent."""
    monkeypatch.setenv("HOME", "/tmp/abc")
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/abc/snap/code/259/.local/share")

    from themey.paths import aurorae_themes

    with caplog.at_level("WARNING", logger="themey.paths"):
        aurorae_themes()
    assert any("snap" in rec.message for rec in caplog.records)


def test_fake_home_routes_paths(fake_home, tmp_path):
    from themey.paths import aurorae_themes

    # fake_home == tmp_path; aurorae_themes() should be under it
    result = aurorae_themes()
    assert str(result).startswith(str(tmp_path))
    assert result.parts[-2:] == ("aurorae", "themes")


def test_global_theme_dirs_default(monkeypatch):
    """The four Global-Theme install roots resolve under the XDG default."""
    monkeypatch.setenv("HOME", "/tmp/abc")
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    from themey import paths

    base = "/tmp/abc/.local/share"
    assert str(paths.color_schemes()) == f"{base}/color-schemes"
    assert str(paths.wallpapers()) == f"{base}/wallpapers"
    assert str(paths.icon_themes()) == f"{base}/icons"
    assert str(paths.look_and_feel()) == f"{base}/plasma/look-and-feel"


def test_global_theme_dirs_xdg_override(monkeypatch):
    """XDG_DATA_HOME redirects every Global-Theme root."""
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")

    from themey import paths

    assert str(paths.color_schemes()) == "/tmp/xdg/color-schemes"
    assert str(paths.wallpapers()) == "/tmp/xdg/wallpapers"
    assert str(paths.icon_themes()) == "/tmp/xdg/icons"
    assert str(paths.look_and_feel()) == "/tmp/xdg/plasma/look-and-feel"
