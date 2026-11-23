"""Pytest for caption font rendering using bundled OFL fonts.

Verifies that every style font can be resolved from the bundle
and that a missing font raises CaptionError(FONT_MISSING) with a fix_action.
"""
from pathlib import Path

import pytest

# conftest.py already inserts the project root on sys.path, so `app` and
# `maxclipper` import normally as installed packages.
from app import config as app_config
from app.captions import track
from maxclipper.resilience.exceptions import CaptionError, FONT_MISSING


def test_fonts_dir_is_project_root_assets():
    """FONTS_DIR must be <project_root>/assets/fonts with real .ttf files."""
    fonts_dir = Path(app_config.FONTS_DIR).resolve()
    assert fonts_dir.name == "fonts"
    assert fonts_dir.parent.name == "assets"
    assert fonts_dir.exists(), f"Bundled fonts dir missing: {fonts_dir}"
    ttfs = sorted(fonts_dir.glob("*.ttf"))
    assert ttfs, f"No .ttf files in {fonts_dir}"
    # Every bundled font must be a real TrueType file (not an HTML stub).
    for f in ttfs:
        head = f.read_bytes()[:4]
        assert head in (b"\x00\x01\x00\x00", b"true", b"OTTO", b"ttcf"), (
            f"{f.name} is not a real font (magic={head!r})"
        )


def test_all_styles_resolve_to_bundled_fonts():
    """Every STYLES entry's font_name resolves to a file inside assets/fonts."""
    fonts_dir = Path(app_config.FONTS_DIR).resolve()
    for style_name, style in track._STYLES.items():
        font_path = track._resolve_font(style["font_name"])
        assert font_path is not None, f"Font for style '{style_name}' could not be resolved"
        assert font_path.exists(), f"Resolved font path does not exist: {font_path}"
        assert font_path.parent == fonts_dir, (
            f"Font {style_name} resolved to {font_path.name} outside assets/fonts "
            f"({font_path.parent})"
        )


def test_missing_font_raises_caption_error():
    """Unknown fonts raise CaptionError(FONT_MISSING) with a fix_action."""
    with pytest.raises(CaptionError) as excinfo:
        track._resolve_font("DefinitelyNotARealFont9999")
    err = excinfo.value
    assert err.error_code == FONT_MISSING
    assert getattr(err, "fix_action", None) is not None