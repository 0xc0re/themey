"""scripts/audit_viewitem.py must keep its contact sheet under the size the
plan allows (1 MB): a sheet too big to open is not an audit artifact.

The corpus sheet comes out around 95 KB, so the cap only ever bites on a
much larger corpus — which is exactly why it needs a test rather than a
comment. ``_contact_sheet`` takes the cap as an argument so these can
exercise the shrink loop cheaply.
"""
from __future__ import annotations

import importlib.util
import random
import sys
from pathlib import Path

import pytest
from PIL import Image

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_viewitem.py"


@pytest.fixture(scope="module")
def audit():
    spec = importlib.util.spec_from_file_location("audit_viewitem", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("audit_viewitem", mod)
    spec.loader.exec_module(mod)
    return mod


def _records(audit, count: int) -> list[dict]:
    """*count* themes of incompressible noise — the worst case for a PNG."""
    rnd = random.Random(5)
    w, h = audit.STRIP
    out = []
    for i in range(count):
        strips = {
            state: [
                [rnd.randrange(256) for _ in range(w * 3)] for _ in range(h)
            ]
            for state in ("hover", "selected")
        }
        out.append({
            "name": f"Theme{i}",
            "states": [{"state": "hover", "flipped": i % 3 == 0}],
            "strips": strips,
        })
    return out


def test_contact_sheet_full_size_when_it_fits(audit, tmp_path) -> None:
    out = tmp_path / "contact.png"
    size = audit._contact_sheet(_records(audit, 8), out)
    assert size == out.stat().st_size <= audit.MAX_SHEET_BYTES
    # Untouched geometry: label column + two strips + padding, per column.
    assert Image.open(out).width == (
        audit.LABEL_W + audit.STRIP[0] * 2 + 12
    ) * audit.COLUMNS


def test_contact_sheet_shrinks_until_it_fits(audit, tmp_path) -> None:
    out = tmp_path / "contact.png"
    records = _records(audit, 40)
    full = audit._contact_sheet(records, tmp_path / "full.png")
    cap = full // 3
    size = audit._contact_sheet(records, out, max_bytes=cap)
    assert size <= cap
    assert Image.open(out).width < Image.open(tmp_path / "full.png").width


def test_contact_sheet_refuses_when_even_the_smallest_is_too_big(
    audit, tmp_path
) -> None:
    with pytest.raises(audit.SheetTooLargeError, match="contact sheet"):
        audit._contact_sheet(_records(audit, 40), tmp_path / "c.png", max_bytes=200)
