"""Validate that every bundled font file is a real TTF/OTF > 30 KB with a valid signature."""
from pathlib import Path

from app import config as app_config
from app.captions import track
from maxclipper.resilience.exceptions import FONT_MISSING


# Valid OpenType font signatures (first 4 bytes)
VALID_SIGNATURES = {b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true"}


def is_valid_font_file(path: Path) -> bool:
    """Check that a font file has a valid signature and is larger than 30 KB."""
    try:
        data = path.read_bytes()
        if len(data) <= 30 * 1024:  # > 30 KB
            return False
        if data[:4] not in VALID_SIGNATURES:
            return False
        return True
    except Exception:
        return False


def test_all_bundled_fonts_valid():
    """Every .ttf/.otf in app/assets/fonts must start with a valid font signature
    and be larger than 30 KB."""
    fonts_dir = Path(app_config.FONTS_DIR).resolve()
    ttf_files = sorted(fonts_dir.glob("*.ttf")) + sorted(fonts_dir.glob("*.otf"))
    assert ttf_files, f"No .ttf/.otf files found in {fonts_dir}"
    for f in ttf_files:
        assert is_valid_font_file(f), (
            f"{f.name} is not a valid font signature or too small "
            f"(< 30 KB or bad magic {f.read_bytes()[:4]!r})"
        )


def test_style_fonts_resolve_to_valid_files():
    """Every STYLES entry's font_name must resolve to a valid font file
    in app/assets/fonts (not outside the bundle)."""
    fonts_dir = Path(app_config.FONTS_DIR).resolve()
    valid_fonts = {f.name for f in fonts_dir.glob("*.ttf")}
    valid_fonts.update(f.name for f in fonts_dir.glob("*.otf"))

    for style_name, style in track._STYLES.items():
        font_path = track._resolve_font(style["font_name"])
        assert font_path is not None, f"Font for style '{style_name}' could not be resolved"
        assert font_path.exists(), f"Resolved font path does not exist: {font_path}"
        # The resolved font must be inside the bundled fonts directory
        assert font_path.parent == fonts_dir, (
            f"Font {style_name} resolved to {font_path.name} outside assets/fonts "
            f"({font_path.parent})"
        )
        # The resolved font must also be a valid font file
        assert is_valid_font_file(font_path), (
            f"Font {style_name} resolved to invalid file {font_path}"
        )
