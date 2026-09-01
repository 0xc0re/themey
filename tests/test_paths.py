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
    assert str(paths.cursor_themes()) == "/tmp/abc/.icons"
    assert str(paths.desktop_themes()) == f"{base}/plasma/desktoptheme"
    assert str(paths.look_and_feel()) == f"{base}/plasma/look-and-feel"


def test_global_theme_dirs_xdg_override(monkeypatch):
    """XDG_DATA_HOME redirects every Global-Theme root."""
    monkeypatch.setenv("XDG_DATA_HOME", "/tmp/xdg")

    from themey import paths

    assert str(paths.color_schemes()) == "/tmp/xdg/color-schemes"
    assert str(paths.wallpapers()) == "/tmp/xdg/wallpapers"
    # cursor themes deliberately do NOT follow XDG_DATA_HOME:
    # libXcursor's stock search path is ~/.icons + /usr/share/icons, and
    # Kubuntu's build (and Plasma's cursor KCM on it) never scans
    # $XDG_DATA_HOME/icons — verified live 2026-08-31.
    assert str(paths.cursor_themes()).endswith("/.icons")
    assert str(paths.desktop_themes()) == "/tmp/xdg/plasma/desktoptheme"
    assert str(paths.look_and_feel()) == "/tmp/xdg/plasma/look-and-feel"


def test_subprocess_env_drops_snap_xdg_data_home(monkeypatch) -> None:
    """The Plasma tools search KPackages through KDE's XDG lookup, so a
    snap-sandbox XDG_DATA_HOME (VS Code's terminal) must not reach them —
    live 2026-09-01: `plasma-apply-lookandfeel -a themey_Yellow` said
    "Unable to find the theme" while themey had installed it under
    ~/.local/share (the same fallback `_xdg_data_home` applies)."""
    from themey import paths

    monkeypatch.setenv("XDG_DATA_HOME", "/home/u/snap/code/259/.local/share")
    monkeypatch.setenv("THEMEY_TEST_MARKER", "1")
    env = paths.subprocess_env()
    assert "XDG_DATA_HOME" not in env
    assert env["THEMEY_TEST_MARKER"] == "1"


def test_subprocess_env_keeps_real_xdg_data_home(monkeypatch, tmp_path) -> None:
    from themey import paths

    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert paths.subprocess_env()["XDG_DATA_HOME"] == str(tmp_path)
