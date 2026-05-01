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
