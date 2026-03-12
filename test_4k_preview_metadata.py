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


# ---------- CapCut metadata tests ----------

def test_make_ffmpeg_params_has_capcut_metadata():
    """_make_ffmpeg_params_for_codec must include CapCut metadata."""
    source = _read_source()
    func_start = source.find("def _make_ffmpeg_params_for_codec(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'map_metadata' in func_body, \
        "_make_ffmpeg_params_for_codec should strip source metadata"
    assert 'encoder=CapCut' in func_body, \
        "_make_ffmpeg_params_for_codec should set encoder to CapCut"
    assert 'CapCut Video Handler' in func_body, \
        "_make_ffmpeg_params_for_codec should set video handler to CapCut"
    assert 'CapCut Sound Handler' in func_body, \
        "_make_ffmpeg_params_for_codec should set audio handler to CapCut"


def test_reencode_has_capcut_metadata():
    """reencode_with_libx264 must include CapCut metadata in the FFmpeg command."""
    source = _read_source()
    func_start = source.find("def reencode_with_libx264(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'map_metadata' in func_body, \
        "reencode_with_libx264 should strip source metadata"
    assert 'encoder=CapCut' in func_body, \
        "reencode_with_libx264 should set encoder to CapCut"
    assert 'CapCut Video Handler' in func_body, \
        "reencode_with_libx264 should set video handler to CapCut"


def test_final_encode_has_capcut_metadata():
    """The final FFmpeg export command must include CapCut metadata."""
    source = _read_source()
    # Find the final encode section (around the FINAL-ENCODE label)
    final_section = source.find('label="FINAL-ENCODE"')
    assert final_section != -1, "FINAL-ENCODE label must exist"
    # Search backward for the cmd construction (within ~2000 chars)
    search_start = max(0, final_section - 2000)
    cmd_section = source[search_start:final_section]
    assert 'map_metadata' in cmd_section, \
        "Final export command should strip source metadata"
    assert 'encoder=CapCut' in cmd_section, \
        "Final export command should set encoder to CapCut"
    assert 'CapCut Video Handler' in cmd_section, \
        "Final export command should set video handler to CapCut"
    assert 'CapCut Sound Handler' in cmd_section, \
        "Final export command should set audio handler to CapCut"


def test_metadata_strips_source_before_adding():
    """'-map_metadata -1' must appear before custom metadata tags."""
    source = _read_source()
    func_start = source.find("def _make_ffmpeg_params_for_codec(")
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    map_pos = func_body.find("map_metadata")
    encoder_pos = func_body.find("encoder=CapCut")
    assert map_pos < encoder_pos, \
        "-map_metadata should appear before encoder=CapCut"


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

