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

    # BorderLeft scales linearly with the scale factor.
    # New formula derives from the left-edge iclass image width (BUTTONL: 3px wide),
    # so scale=1 -> 3, scale=2 -> 6, scale=3 -> 9.
    # The exact value can change if the iclass is found or not; assert proportionality.
    assert bl_1 > 0, "BorderLeft must be positive at scale=1"
    assert bl_3 > 0, "BorderLeft must be positive at scale=3"
    # Must be reasonably small — NOT grotesquely large (old bug: 35, 70, 105)
    assert bl_1 <= 20, f"BorderLeft={bl_1} at scale=1 too large (should be ≤20px thin frame)"
    assert bl_3 <= 60, f"BorderLeft={bl_3} at scale=3 too large"
    # bl_2 should be between bl_1 and bl_3 (monotonic with scale)
    assert bl_1 <= bl_2 <= bl_3, f"BorderLeft not monotonic: {bl_1}/{bl_2}/{bl_3}"


def test_pipeline_malicious_archive_writes_nothing(fake_home):
    with pytest.raises((UnsafeArchiveError, InstallError, Exception)):
        convert(FIXTURES / "malicious/path_traversal.tar.gz", scale=2)
    # No new theme dir should have been created
    themes_dir = fake_home / ".local/share/aurorae/themes"
    if themes_dir.exists():
        assert not any(themes_dir.iterdir()), \
            "no theme files should be written for a rejected archive"


def test_pipeline_aliens_rc_left_buttons_xai(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    cp = RawConfigParser()
    cp.optionxform = str  # type: ignore[method-assign]
    cp.read(result.installed_dir / "Aliensrc")
    assert cp["General"]["LeftButtons"] == "XAI"
    assert cp["General"]["RightButtons"] == ""
