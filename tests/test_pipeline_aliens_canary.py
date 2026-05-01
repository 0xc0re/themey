"""End-to-end pipeline test exercising Aliens.etheme through the full stack."""
import xml.etree.ElementTree as ET
from configparser import RawConfigParser
from pathlib import Path

import pytest

from themey.etheme.archive import UnsafeArchiveError
from themey.generate.aurorae import REQUIRED_FRAMESVG_IDS
from themey.install import InstallError
from themey.pipeline import ConvertResult, convert

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
    cp = RawConfigParser(); cp.optionxform = str  # type: ignore[method-assign]
    cp.read(r1.installed_dir / "Aliensrc")
    bl_1 = int(cp["Layout"]["BorderLeft"])

    r3 = convert(FIXTURES / "Aliens.etheme", scale=3)
    cp = RawConfigParser(); cp.optionxform = str  # type: ignore[method-assign]
    cp.read(r3.installed_dir / "Aliensrc")
    bl_3 = int(cp["Layout"]["BorderLeft"])

    # Scale=1 should produce 35; scale=3 should produce 105 (linear in scale)
    assert bl_1 == 35
    assert bl_3 == 105


def test_pipeline_malicious_archive_writes_nothing(fake_home):
    before = list((fake_home / ".local/share").rglob("*"))
    with pytest.raises((UnsafeArchiveError, InstallError, Exception)) as ei:
        convert(FIXTURES / "malicious/path_traversal.tar.gz", scale=2)
    after = list((fake_home / ".local/share").rglob("*"))
    # No new theme dir should have been created
    themes_dir = fake_home / ".local/share/aurorae/themes"
    if themes_dir.exists():
        assert not any(themes_dir.iterdir()), \
            "no theme files should be written for a rejected archive"


def test_pipeline_aliens_rc_left_buttons_xai(fake_home):
    result = convert(FIXTURES / "Aliens.etheme", scale=2)
    cp = RawConfigParser(); cp.optionxform = str  # type: ignore[method-assign]
    cp.read(result.installed_dir / "Aliensrc")
    assert cp["General"]["LeftButtons"] == "XAI"
    assert cp["General"]["RightButtons"] == ""
