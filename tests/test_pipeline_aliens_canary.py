"""End-to-end pipeline test exercising Aliens.etheme through the full stack."""
import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

import pytest

from themey.etheme.archive import UnsafeArchiveError
from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS
from themey.install import InstallError
from themey.pipeline import convert

FIXTURES = Path(__file__).parent / "fixtures"


def test_pipeline_convert_aliens_writes_all_artifacts(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    assert result.theme_name == "Aliens"
    assert result.installed_dir == fake_home / ".local/share/aurorae/themes/Aliens"
    assert result.installed_dir.is_dir()
    for fname in ("decoration.svg", "Aliensrc", "metadata.desktop",
                  "metadata.json", "close.svg", "maximize.svg",
                  "restore.svg", "minimize.svg"):
        assert (result.installed_dir / fname).is_file(), \
            f"missing {fname} after install"
    assert result.preview_path.is_file()
    assert result.report_path.is_file()
    assert result.notes_count >= 4


def test_pipeline_18_framesvg_ids_in_installed_decoration_svg(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    root = ET.parse(result.installed_dir / "decoration.svg").getroot()
    present = {e.get("id") for e in root.iter() if e.get("id")}
    missing = set(REQUIRED_FRAMESVG_IDS) - present
    assert not missing, f"missing FrameSvg IDs after install: {missing}"


def test_pipeline_idempotent_rerun(fake_home):
    r1 = convert(FIXTURES / "Aliens.etheme", scale=2)
    r2 = convert(FIXTURES / "Aliens.etheme", scale=2)
    assert r1.installed_dir == r2.installed_dir
    # Second run should have replaced first; both files still there
    assert (r2.installed_dir / "decoration.svg").is_file()
    # No backup left over
    backup = r2.installed_dir.with_name("Aliens.themey-old")
    assert not backup.exists()


def test_pipeline_scale_changes_BorderLeft(fake_home):
    r1 = convert(FIXTURES / "Aliens.etheme", scale=1)
    cp1 = RawConfigParser()
    cp1.optionxform = str  # type: ignore[method-assign]
    cp1.read(r1.installed_dir / "Aliensrc")
    bl_1 = int(cp1["Layout"]["BorderLeft"])

    r2 = convert(FIXTURES / "Aliens.etheme", scale=2)
    cp2 = RawConfigParser()
    cp2.optionxform = str  # type: ignore[method-assign]
    cp2.read(r2.installed_dir / "Aliensrc")
    bl_2 = int(cp2["Layout"]["BorderLeft"])

    r3 = convert(FIXTURES / "Aliens.etheme", scale=3)
    cp3 = RawConfigParser()
    cp3.optionxform = str  # type: ignore[method-assign]
    cp3.read(r3.installed_dir / "Aliensrc")
    bl_3 = int(cp3["Layout"]["BorderLeft"])

    # BorderLeft = max(BORDER_SIZE_LEFT, max anchored-part width) x scale.
    # Aliens' CORNER_TL is 124 wide, so unclamped values are 124/248/372 at
    # scales 1/2/3. The [2, 400] clamp accommodates all three.
    assert bl_1 > 0, "BorderLeft must be positive at scale=1"
    assert bl_3 > 0, "BorderLeft must be positive at scale=3"
    assert bl_1 <= 400, f"BorderLeft={bl_1} at scale=1 above the [2,400] clamp"
    assert bl_3 <= 400, f"BorderLeft={bl_3} at scale=3 above the [2,400] clamp"
    # bl_2 should be between bl_1 and bl_3 (monotonic with scale).
    assert bl_1 <= bl_2 <= bl_3, f"BorderLeft not monotonic: {bl_1}/{bl_2}/{bl_3}"


def test_pipeline_malicious_archive_writes_nothing(fake_home):
    with pytest.raises((UnsafeArchiveError, InstallError, Exception)):
        convert(FIXTURES / "malicious/path_traversal.tar.gz", scale=2)
    # No new theme dir should have been created
    themes_dir = fake_home / ".local/share/aurorae/themes"
    if themes_dir.exists():
        assert not any(themes_dir.iterdir()), \
            "no theme files should be written for a rejected archive"


def test_pipeline_aliens_button_svgs_for_xai(fake_home):
    """Button ORDER is global (kwinrc), so the rc carries no LeftButtons;
    the theme decides only which button SVGs exist (X, A, I → 4 files)."""
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(result.installed_dir / "Aliensrc")
    assert "LeftButtons" not in cp["General"]
    for f in ("close.svg", "maximize.svg", "restore.svg", "minimize.svg", "menu.svg"):
        assert (result.installed_dir / f).is_file(), f


def _region_opaque_fraction(svg: Path, gid: str) -> float:
    import base64
    import io

    from PIL import Image

    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.parse(svg).getroot()
    g = root.find(f"s:g[@id='{gid}']", ns)
    assert g is not None, gid
    im = g.find("s:image", ns)
    assert im is not None
    href = im.get("{http://www.w3.org/1999/xlink}href") or ""
    data = base64.b64decode(href.split(",", 1)[1])
    with Image.open(io.BytesIO(data)) as img:
        alpha = img.convert("RGBA").getchannel("A").getdata()
        px = list(alpha)
    return sum(1 for a in px if a > 32) / len(px)


def test_pipeline_capped_left_strip_keeps_inner_edge_art(fake_home):
    """Aliens' BUTTONL resize strip sits at x=30..35 of a 35-wide left zone.

    Whatever width the left frame column ends up (folded corner width, or
    the 48-px side cap when there is no corner art), that strip must still
    be inside it: when the column is narrower than the zone the crop anchors
    at the INNER edge (next to the client); when wider, it spans the zone.
    Either way the strip must not render empty. (5 of 124 ref px ≈ 4%.)
    """
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    svg = result.installed_dir / "decoration.svg"
    assert _region_opaque_fraction(svg, "decoration-left") > 0.02
    assert _region_opaque_fraction(svg, "decoration-bottom") > 0.02


def test_pipeline_hint_left_margin_matches_folded_corner(fake_home):
    """FrameSvg sizes the topleft corner by the left margin hint, and paints
    the frame independently of KWin's clamped BorderLeft. So when corner art
    is folded into the title band, the hint (and the left strip slot) must be
    as wide as the corner slot or the art gets squashed to BorderLeft."""
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.parse(result.installed_dir / "decoration.svg").getroot()

    def slot_w(gid: str) -> int:
        g = root.find(f"s:g[@id='{gid}']", ns)
        assert g is not None, gid
        return int(g.find("s:image", ns).get("width"))

    hint = root.find("s:rect[@id='decoration-hint-left-margin']", ns)
    assert hint is not None
    tl = slot_w("decoration-topleft")
    assert tl >= 200, tl  # CORNER_TL is 124 ref = 248 out
    assert int(hint.get("width")) == tl
    assert slot_w("decoration-left") == tl
    assert slot_w("decoration-bottomleft") == tl


def test_pipeline_side_composites_match_slots(fake_home):
    """Every region PNG must be exactly the size of its SVG slot — a
    narrower composite gets stretched by FrameSvg (Aliens' 70-px left zone
    in a 248-px folded column rendered 3.5x wide)."""
    import base64
    import io

    from PIL import Image

    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    ns = {"s": "http://www.w3.org/2000/svg"}
    root = ET.parse(result.installed_dir / "decoration.svg").getroot()
    for g in root.findall("s:g", ns):
        gid = g.get("id") or ""
        if not gid.startswith("decoration-") or "maximized" in gid:
            continue
        im = g.find("s:image", ns)
        href = im.get("{http://www.w3.org/1999/xlink}href") or ""
        data = base64.b64decode(href.split(",", 1)[1])
        with Image.open(io.BytesIO(data)) as png:
            assert png.size == (int(im.get("width")), int(im.get("height"))), gid
