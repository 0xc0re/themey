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
    from themey.slug import slugify

    import re

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
