"""generate/icons.py — the per-app XDG icon theme from windowmatches rules.

A fake applications dir stands in for /usr/share/applications; the
``.desktop`` reader is hand-rolled (localized keys, ``%`` in Exec).
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from themey.generate import icons
from themey.ir import BorderSpec, IconMatchSpec, Palette, Theme
from themey.slug import icon_theme_dir


def _theme(tmp_path: Path, matches: tuple[IconMatchSpec, ...]) -> Theme:
    return Theme(
        name="Tiny", display_name="Tiny", author=None, scale=2,
        asset_root=tmp_path,
        border=BorderSpec(
            name="DEFAULT", border_size_left=4, border_size_right=4,
            border_size_top=18, border_size_bottom=4, parts=(),
        ),
        iclasses={}, tclasses={}, button_codes={}, left_buttons="",
        right_buttons="",
        palette=Palette(
            titlebar_active=(64, 64, 64), titlebar_inactive=(128, 128, 128),
            text_active=(255, 255, 255), text_inactive=(192, 192, 192),
        ),
        icon_matches=matches,
    )


def _art(tmp_path: Path, name: str = "app.png", size=(4, 4)) -> Path:
    p = tmp_path / "art" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (200, 40, 40, 255)).save(p)
    return p


def _desktop(apps: Path, stem: str, **keys: str) -> Path:
    apps.mkdir(parents=True, exist_ok=True)
    lines = ["[Desktop Entry]", "Type=Application"]
    lines += [f"{k}={v}" for k, v in keys.items()]
    lines += ["Name[de]=Lokalisiert", "[Desktop Action new-window]", "Icon=window-new"]
    p = apps / f"{stem}.desktop"
    p.write_text("\n".join(lines) + "\n")
    return p


@pytest.fixture
def apps(tmp_path: Path, monkeypatch) -> Path:
    d = tmp_path / "applications"
    monkeypatch.setattr(icons, "applications_dirs", lambda: [d])
    _desktop(d, "debian-xterm", Name="XTerm", Icon="xterm-color_48x48",
             Exec="xterm", StartupWMClass="XTerm")
    _desktop(d, "org.kde.konsole", Name="Konsole", Icon="utilities-terminal",
             Exec="konsole %u", StartupWMClass="konsole")
    _desktop(d, "emacs", Name="Emacs (GUI)", Icon="emacs.png", Exec="/usr/bin/emacs %F")
    _desktop(d, "abs", Name="Abs", Icon="/opt/abs/icon.png", Exec="abs",
             StartupWMClass="Abs")
    _desktop(d, "noicon", Name="NoIcon", Exec="noicon", StartupWMClass="NoIcon")
    return d


def test_read_desktop_entry_ignores_localized_and_action_groups(apps: Path) -> None:
    e = icons.read_desktop_entry(apps / "org.kde.konsole.desktop")
    assert e is not None
    assert e.name == "Konsole" and e.icon == "utilities-terminal"
    assert e.exec_argv0 == "konsole" and e.wm_class == "konsole"
    assert icons.read_desktop_entry(apps / "noicon.desktop") is None


def test_matching_kinds(apps: Path) -> None:
    entries = icons.scan_desktop_entries()
    art = Path("/x.png")
    by_class = icons.match_rule(IconMatchSpec("class", "XTerm", art), entries)
    assert [e.stem for e in by_class] == ["debian-xterm"]
    # No StartupWMClass: the stem stands in.
    by_stem = icons.match_rule(IconMatchSpec("class", "emacs", art), entries)
    assert [e.stem for e in by_stem] == ["emacs"]
    by_name = icons.match_rule(IconMatchSpec("name", "kons*", art), entries)
    assert [e.stem for e in by_name] == ["org.kde.konsole"]
    by_title = icons.match_rule(IconMatchSpec("title", "Emacs*", art), entries)
    assert [e.stem for e in by_title] == ["emacs"]
    # fnmatchcase: E16 passed flags 0 — case matters.
    assert icons.match_rule(IconMatchSpec("class", "xterm", art), entries) == []


def test_write_theme_layout_and_index(tmp_path: Path, apps: Path, snapshot) -> None:
    art = _art(tmp_path)
    theme = _theme(tmp_path, (IconMatchSpec("class", "XTerm", art),))
    out = tmp_path / icon_theme_dir("Tiny")
    result = icons.write_theme(theme, out)
    assert result is not None
    assert result.name == "themey_Tiny-icons" == out.name
    assert result.icons == ("xterm-color_48x48",)
    png = out / "48x48" / "apps" / "xterm-color_48x48.png"
    assert png.is_file()
    with Image.open(png) as im:
        assert im.size == (48, 48)
        # 4×4 art NEAREST-fitted: solid red across the whole canvas.
        assert im.getpixel((0, 0)) == (200, 40, 40, 255)
        assert im.getpixel((47, 47)) == (200, 40, 40, 255)
    assert (out / "index.theme").read_text() == snapshot
    assert any("debian-xterm.desktop (xterm-color_48x48) wears app.png" in n
               for n in theme.notes)


def test_fit_icon_keeps_aspect_and_centres(tmp_path: Path) -> None:
    art = _art(tmp_path, "wide.png", size=(8, 2))
    im = icons.fit_icon(art)
    assert im.size == (48, 48)
    assert im.getpixel((24, 24)) == (200, 40, 40, 255)
    assert im.getpixel((24, 0)) == (0, 0, 0, 0)  # letterboxed


def test_first_rule_wins_and_absolute_icon_skipped(tmp_path: Path, apps: Path) -> None:
    first = _art(tmp_path, "first.png")
    second = _art(tmp_path, "second.png")
    theme = _theme(tmp_path, (
        IconMatchSpec("class", "XTerm", first),
        IconMatchSpec("name", "xterm", second),
        IconMatchSpec("class", "Abs", first),
    ))
    out = tmp_path / icon_theme_dir("Tiny")
    result = icons.write_theme(theme, out)
    assert result is not None and result.icons == ("xterm-color_48x48",)
    assert any("wears first.png" in n for n in theme.notes)
    assert not any("wears second.png" in n for n in theme.notes)
    assert any("absolute Icon= path" in n for n in theme.notes)


def test_title_rule_notes_approximation(tmp_path: Path, apps: Path) -> None:
    art = _art(tmp_path)
    theme = _theme(tmp_path, (IconMatchSpec("title", "Emacs*", art),))
    result = icons.write_theme(theme, tmp_path / icon_theme_dir("Tiny"))
    assert result is not None and result.icons == ("emacs",)  # .png stripped
    assert any("approximate" in n for n in theme.notes)


def test_no_rules_or_no_match_writes_nothing(tmp_path: Path, apps: Path) -> None:
    out = tmp_path / icon_theme_dir("Tiny")
    theme = _theme(tmp_path, ())
    assert icons.write_theme(theme, out) is None
    assert not out.exists()
    assert any("no usable __USE_ICON" in n for n in theme.notes)
    art = _art(tmp_path)
    theme2 = _theme(tmp_path, (IconMatchSpec("class", "Netscape", art),))
    assert icons.write_theme(theme2, out) is None
    assert not out.exists()
    assert any("matches no installed application" in n for n in theme2.notes)
    assert any("no icon theme written" in n for n in theme2.notes)


def test_write_theme_rejects_wrong_dir_name(tmp_path: Path) -> None:
    theme = _theme(tmp_path, (IconMatchSpec("class", "X", tmp_path / "x.png"),))
    with pytest.raises(icons.IconThemeError, match="basename"):
        icons.write_theme(theme, tmp_path / "wrong")


def test_applications_dirs_follow_xdg_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.setenv("XDG_DATA_DIRS", "/opt/share:/usr/share")
    assert icons.applications_dirs() == [
        tmp_path / "xdg" / "applications",
        Path("/opt/share/applications"),
        Path("/usr/share/applications"),
    ]
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.delenv("XDG_DATA_DIRS")
    dirs = icons.applications_dirs()
    assert dirs[0] == tmp_path / ".local" / "share" / "applications"
    assert Path("/usr/share/applications") in dirs


def test_replace_keeps_frozen_spec() -> None:
    spec = IconMatchSpec("class", "X", Path("/x.png"))
    assert replace(spec, pattern="Y").pattern == "Y"
