"""Tests for the hand-rolled .desktop file writer.

Per plan: desktop_writer must NOT use configparser — localized keys like
``Name[de]=Foo`` confuse configparser's section regex.
"""
from __future__ import annotations

from pathlib import Path


def test_write_desktop_basic(tmp_path: Path) -> None:
    from themey.generate.desktop_writer import write_desktop

    out = tmp_path / "test.desktop"
    write_desktop(out, {"Desktop Entry": {"Name": "Foo", "Type": "Service"}})
    content = out.read_text()
    assert "[Desktop Entry]" in content
    assert "Name=Foo" in content
    assert "Type=Service" in content


def test_write_desktop_localization_keys_preserved(tmp_path: Path) -> None:
    """Localization key `Name[de]=Foo` must appear verbatim — not mangled by configparser."""
    from themey.generate.desktop_writer import write_desktop

    out = tmp_path / "test.desktop"
    write_desktop(out, {"Desktop Entry": {"Name": "Hello", "Name[de]": "Hallo"}})
    content = out.read_text()
    assert "Name[de]=Hallo" in content
    # Make sure [de] was NOT interpreted as a section header
    lines = content.splitlines()
    assert "[de]" not in lines  # configparser would mangle this


def test_write_desktop_multiple_sections_separated_by_blank_line(tmp_path: Path) -> None:
    from themey.generate.desktop_writer import write_desktop

    out = tmp_path / "test.desktop"
    write_desktop(
        out,
        {
            "Desktop Entry": {"Name": "Foo"},
            "Plugin Info": {"Version": "1.0"},
        },
    )
    content = out.read_text()
    # Both sections present
    assert "[Desktop Entry]" in content
    assert "[Plugin Info]" in content
    # A blank line separates the two sections
    assert "\n\n" in content


def test_write_desktop_preserves_key_case(tmp_path: Path) -> None:
    """Keys must keep their original case (X-KDE-PluginInfo-Name, LeftButtons, etc.)."""
    from themey.generate.desktop_writer import write_desktop

    out = tmp_path / "test.desktop"
    write_desktop(
        out,
        {"Desktop Entry": {"X-KDE-PluginInfo-Name": "Aliens", "LeftButtons": "XAI"}},
    )
    content = out.read_text()
    assert "X-KDE-PluginInfo-Name=Aliens" in content
    assert "LeftButtons=XAI" in content
    # Ensure lowercase mangling did NOT happen
    assert "x-kde-plugininfo-name=" not in content
    assert "leftbuttons=" not in content
