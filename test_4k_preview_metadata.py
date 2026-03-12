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
        f"No code lines should reference mp42 brand (found: {meta_lines[:3]})"


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


if __name__ == "__main__":
    # Run with pytest or unittest
    import pytest
    pytest.main([__file__, "-v"])

