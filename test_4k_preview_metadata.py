"""Tests for 4K preview caption accuracy and CapCut metadata in FFmpeg commands."""
import os
import sys
import re
import unittest


SOURCE_FILE = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")


def _read_source():
    with open(SOURCE_FILE, 'r', encoding='utf-8') as f:
        return f.read()


# ---------- _calc_caption_y_for_preview tests ----------

def test_calc_caption_y_no_8_percent_margin():
    """_calc_caption_y_for_preview must NOT use 8% bottom margin anymore."""
    source = _read_source()
    func_start = source.find("def _calc_caption_y_for_preview(")
    assert func_start != -1, "_calc_caption_y_for_preview must exist"
    func_end = source.find("\n    def ", func_start + 10)
    func_body = source[func_start:func_end]
    # Should NOT contain the old 8% margin pattern
    assert "h * 0.08)" not in func_body, \
        "_calc_caption_y_for_preview should not use 8% canvas margin"
    assert "max(30," not in func_body, \
        "_calc_caption_y_for_preview should not use max(30,...) margin"


def test_calc_caption_y_uses_font_correction():
    """_calc_caption_y_for_preview should use font-based y_correction to match export."""
    source = _read_source()
    func_start = source.find("def _calc_caption_y_for_preview(")
    func_end = source.find("\n    def ", func_start + 10)
    func_body = source[func_start:func_end]
    # Should reference CAPTION_FONT_SIZE for the correction
    assert "CAPTION_FONT_SIZE" in func_body, \
        "_calc_caption_y_for_preview should use CAPTION_FONT_SIZE for y_correction"
    # Should have a small correction factor (0.08) matching the FFmpeg drawtext formula
    assert "0.08" in func_body, \
        "_calc_caption_y_for_preview should use 0.08 correction factor matching FFmpeg"


def test_calc_caption_y_uses_preview_ratio():
    """_calc_caption_y_for_preview must still use preview_ratio = h / HEIGHT."""
    source = _read_source()
    func_start = source.find("def _calc_caption_y_for_preview(")
    func_end = source.find("\n    def ", func_start + 10)
    func_body = source[func_start:func_end]
    assert "preview_ratio" in func_body
    assert "h / HEIGHT" in func_body


# ---------- CapCut metadata helper tests ----------

def test_build_capcut_meta_exists():
    """_build_capcut_meta helper function must exist."""
    source = _read_source()
    assert 'def _build_capcut_meta(' in source, \
        "_build_capcut_meta helper function must be defined"


def test_build_capcut_meta_uses_isom_brand():
    """_build_capcut_meta must use isom brand (matching real CapCut)."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert "'isom'" in func_body or '"isom"' in func_body, \
        "_build_capcut_meta should set brand to isom (real CapCut brand)"
    assert 'map_metadata' in func_body, \
        "_build_capcut_meta should strip source metadata with -map_metadata -1"
    assert 'handler_name=VideoHandler' in func_body, \
        "_build_capcut_meta should set video handler name"


def test_build_capcut_meta_has_creation_time():
    """_build_capcut_meta must set creation_time for authentic timestamps."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'creation_time' in func_body, \
        "_build_capcut_meta should set creation_time metadata"


def test_capcut_color_flags_exist():
    """_CAPCUT_COLOR_FLAGS must define BT.709 color space (matching real CapCut)."""
    source = _read_source()
    assert '_CAPCUT_COLOR_FLAGS' in source, \
        "_CAPCUT_COLOR_FLAGS constant must be defined"
    flags_start = source.find('_CAPCUT_COLOR_FLAGS')
    flags_section = source[flags_start:flags_start + 300]
    assert 'bt709' in flags_section, \
        "_CAPCUT_COLOR_FLAGS should include bt709 color primaries"
    assert 'color_range' in flags_section, \
        "_CAPCUT_COLOR_FLAGS should include color_range"


def test_metadata_strips_source_before_adding():
    """_build_capcut_meta must strip metadata (-map_metadata -1) before adding custom tags."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    map_pos = func_body.find("map_metadata")
    handler_pos = func_body.find("handler_name=VideoHandler")
    assert map_pos < handler_pos, \
        "-map_metadata should appear before handler_name metadata"


def test_build_capcut_meta_has_hw():
    """_build_capcut_meta must set Hw=1 (CapCut hardware tag)."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'Hw=1' in func_body, \
        "_build_capcut_meta should set Hw=1 metadata"


def test_build_capcut_meta_has_bitrate():
    """_build_capcut_meta must set Bitrate=28000000."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'Bitrate=28000000' in func_body, \
        "_build_capcut_meta should set Bitrate=28000000 metadata"


def test_build_capcut_meta_has_te_is_reencode():
    """_build_capcut_meta must set 'Te Is Reencode=1'."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'Te Is Reencode=1' in func_body, \
        "_build_capcut_meta should set 'Te Is Reencode=1' metadata"


def test_build_capcut_meta_has_mp4_data_incomplete():
    """_build_capcut_meta must set 'Mp 4 Data Incomplete=false'."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'Mp 4 Data Incomplete=false' in func_body, \
        "_build_capcut_meta should set 'Mp 4 Data Incomplete=false' metadata"


def test_build_capcut_meta_has_artwork():
    """_build_capcut_meta must include Artwork JSON metadata."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'Artwork=' in func_body, \
        "_build_capcut_meta should set Artwork metadata"
    assert '_build_capcut_artwork' in func_body, \
        "_build_capcut_meta should call _build_capcut_artwork()"


def test_build_capcut_artwork_exists():
    """_build_capcut_artwork helper function must exist and return valid JSON."""
    source = _read_source()
    assert 'def _build_capcut_artwork(' in source, \
        "_build_capcut_artwork helper function must be defined"
    func_start = source.find("def _build_capcut_artwork(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'source_platform' in func_body, \
        "_build_capcut_artwork should include source_platform"
    assert 'vicut' in func_body, \
        "_build_capcut_artwork should include vicut product"
    assert 'videoParams' in func_body, \
        "_build_capcut_artwork should include videoParams"


# ---------- Metadata usage in FFmpeg commands ----------

def test_make_ffmpeg_params_uses_capcut_meta():
    """_make_ffmpeg_params_for_codec must use _build_capcut_meta and _CAPCUT_COLOR_FLAGS."""
    source = _read_source()
    func_start = source.find("def _make_ffmpeg_params_for_codec(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert '_build_capcut_meta' in func_body, \
        "_make_ffmpeg_params_for_codec should call _build_capcut_meta()"
    assert '_CAPCUT_COLOR_FLAGS' in func_body, \
        "_make_ffmpeg_params_for_codec should include _CAPCUT_COLOR_FLAGS"


def test_reencode_uses_capcut_meta():
    """reencode_with_libx264 must use _build_capcut_meta and _CAPCUT_COLOR_FLAGS."""
    source = _read_source()
    func_start = source.find("def reencode_with_libx264(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert '_build_capcut_meta' in func_body, \
        "reencode_with_libx264 should call _build_capcut_meta()"
    assert '_CAPCUT_COLOR_FLAGS' in func_body, \
        "reencode_with_libx264 should include _CAPCUT_COLOR_FLAGS"


def test_final_encode_uses_capcut_meta():
    """The final FFmpeg export command must use _build_capcut_meta and _CAPCUT_COLOR_FLAGS."""
    source = _read_source()
    final_section = source.find('label="FINAL-ENCODE"')
    assert final_section != -1, "FINAL-ENCODE label must exist"
    search_start = max(0, final_section - 2000)
    cmd_section = source[search_start:final_section]
    assert '_build_capcut_meta' in cmd_section, \
        "Final export command should call _build_capcut_meta()"
    assert '_CAPCUT_COLOR_FLAGS' in cmd_section, \
        "Final export command should include _CAPCUT_COLOR_FLAGS"


def test_prerender_uses_capcut_meta():
    """pre_render_foreground_ffmpeg must use _build_capcut_meta and _CAPCUT_COLOR_FLAGS."""
    source = _read_source()
    func_start = source.find("def pre_render_foreground_ffmpeg(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert '_build_capcut_meta' in func_body, \
        "pre_render_foreground_ffmpeg should call _build_capcut_meta()"
    assert '_CAPCUT_COLOR_FLAGS' in func_body, \
        "pre_render_foreground_ffmpeg should include _CAPCUT_COLOR_FLAGS"


def test_no_mp42_brand_remaining():
    """No FFmpeg command should use the old mp42 brand anymore (real CapCut uses isom)."""
    source = _read_source()
    # mp42 should not appear in any metadata context
    # (it may appear in comments, which is fine)
    meta_lines = [line for line in source.split('\n')
                  if 'mp42' in line and not line.strip().startswith('#')]
    assert len(meta_lines) == 0, \
        f"No code lines should reference mp42 brand (found {len(meta_lines)} occurrences: {meta_lines})"


# ---------- Caption indicator info label tests ----------

def test_caption_indicator_shows_resolution_mode():
    """_draw_caption_indicator_on_preview info label should show HD/4K mode."""
    source = _read_source()
    func_start = source.find("def _draw_caption_indicator_on_preview(")
    assert func_start != -1
    func_end = source.find("\n    def ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'IS_4K_MODE' in func_body, \
        "Caption indicator should check IS_4K_MODE for resolution label"
    assert '"4K"' in func_body or "'4K'" in func_body, \
        "Caption indicator should display '4K' when in 4K mode"
    assert '"HD"' in func_body or "'HD'" in func_body, \
        "Caption indicator should display 'HD' when in HD mode"


def test_build_capcut_meta_has_minor_version():
    """_build_capcut_meta must set minor_version=512 (matching real CapCut ftyp)."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'minor_version=512' in func_body, \
        "_build_capcut_meta should set minor_version=512 metadata"


def test_build_capcut_meta_has_compatible_brands():
    """_build_capcut_meta must set compatible_brands=isomiso2avc1mp41."""
    source = _read_source()
    func_start = source.find("def _build_capcut_meta(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'compatible_brands=isomiso2avc1mp41' in func_body, \
        "_build_capcut_meta should set compatible_brands=isomiso2avc1mp41"


def test_stop_check_proc_wait_has_timeout_protection():
    """_run_ffmpeg_with_stop_check must catch TimeoutExpired from proc.wait() after kill."""
    source = _read_source()
    func_start = source.find("def _run_ffmpeg_with_stop_check(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    # After proc.kill(), proc.wait(timeout=10) should be wrapped in try/except
    kill_pos = func_body.find("proc.kill()")
    assert kill_pos != -1
    # Find the section after first proc.kill() for stop path
    stop_section = func_body[kill_pos:kill_pos + 200]
    assert "except subprocess.TimeoutExpired" in stop_section, \
        "proc.wait() after proc.kill() must be protected by try/except TimeoutExpired"


def test_movflags_use_metadata_tags():
    """All movflags must include use_metadata_tags so FFmpeg writes custom
    metadata (Artwork, Hw, Bitrate, etc.) to the MP4 container."""
    source = _read_source()
    # Find all movflags occurrences
    movflags_pattern = re.compile(r'"-movflags",\s*"([^"]+)"')
    matches = movflags_pattern.findall(source)
    assert len(matches) >= 5, f"Expected at least 5 movflags, found {len(matches)}"
    for flag_value in matches:
        assert "use_metadata_tags" in flag_value, \
            f"movflags '{flag_value}' must include use_metadata_tags for custom MP4 metadata"
        assert "faststart" in flag_value, \
            f"movflags '{flag_value}' must include faststart for web streaming"


if __name__ == "__main__":
    # Run with pytest or unittest
    import pytest
    pytest.main([__file__, "-v"])

