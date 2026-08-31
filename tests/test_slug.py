"""Tests for themey.slug.slugify — filesystem-safe theme-name sanitizer."""
from __future__ import annotations

import pytest


def test_slug_clean_name_unchanged() -> None:
    from themey.slug import slugify

    assert slugify("Aliens") == "Aliens"


def test_slug_path_traversal_neutralized() -> None:
    from themey.slug import slugify

    result = slugify("../etc.etheme")
    assert ".." not in result
    assert "/" not in result
    import re

    assert re.match(r"^[A-Za-z0-9_-]+$", result)


def test_slug_strips_leading_dots() -> None:
    from themey.slug import slugify

    result = slugify(".hidden")
    assert not result.startswith(".")


def test_slug_strips_trailing_extension() -> None:
    from themey.slug import slugify

    assert slugify("Aliens.etheme") == "Aliens"


def test_slug_replaces_spaces() -> None:
    import re

    from themey.slug import slugify

    result = slugify("My Cool Theme")
    assert re.match(r"^[A-Za-z0-9_-]+$", result)


def test_slug_collapses_runs() -> None:
    from themey.slug import slugify

    result = slugify("a---b")
    assert "---" not in result
    assert result == "a-b"


def test_slug_empty_input_raises() -> None:
    from themey.slug import slugify

    with pytest.raises(ValueError, match="empty"):
        slugify("")


def test_slug_only_dots_raises() -> None:
    from themey.slug import slugify

    with pytest.raises(ValueError):
        slugify("...")


def test_slug_only_special_raises() -> None:
    from themey.slug import slugify

    with pytest.raises(ValueError):
        slugify("!!!@@@")


def test_cursor_theme_dir() -> None:
    from themey.slug import cursor_theme_dir

    assert cursor_theme_dir("Aliens") == "themey_Aliens-cursors"


def test_cursor_theme_dir_sanitizes_and_keeps_hyphens() -> None:
    """Unlike plugin_id, hyphens survive — the string is only ever a
    directory name and a kcminputrc cursorTheme= value, never an
    identifier."""
    from themey.slug import cursor_theme_dir

    assert cursor_theme_dir("Lite Gnome/../x") == "themey_x-cursors"
    assert cursor_theme_dir("e13-dark") == "themey_e13-dark-cursors"


def test_cursor_theme_dir_is_distinct_from_plugin_id() -> None:
    from themey.slug import cursor_theme_dir, plugin_id

    assert cursor_theme_dir("Aliens") != plugin_id("Aliens")
