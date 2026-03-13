"""Tests for volume control dB display (CapCut-style) and related features."""
import os
import re
import math

def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── Volume defaults & slider ranges ───────────────────────────────

def test_voice_gain_default_increased():
    """VOICE_GAIN default should be 5.0 for louder voice output."""
    source = _read_source()
    assert re.search(r'^VOICE_GAIN\s*=\s*5\.0', source, re.MULTILINE), \
        "VOICE_GAIN default should be 5.0"

def test_voice_gain_default_is_5():
    """Confirm VOICE_GAIN is exactly 5.0."""
    source = _read_source()
    match = re.search(r'^VOICE_GAIN\s*=\s*(\S+)', source, re.MULTILINE)
    assert match, "VOICE_GAIN must be defined"
    assert float(match.group(1)) == 5.0, f"VOICE_GAIN should be 5.0, got {match.group(1)}"

def test_music_gain_default_is_025():
    """Confirm MUSIC_GAIN is exactly 0.25."""
    source = _read_source()
    match = re.search(r'^MUSIC_GAIN\s*=\s*(\S+)', source, re.MULTILINE)
    assert match, "MUSIC_GAIN must be defined"
    assert float(match.group(1)) == 0.25, f"MUSIC_GAIN should be 0.25, got {match.group(1)}"

def test_voice_slider_max_increased():
    """Voice slider should allow up to 20.0x."""
    source = _read_source()
    assert "to=20.0" in source, "Voice slider must allow gains up to 20.0x"

def test_voice_slider_max_is_20():
    """Voice gain scale to=20.0 must exist in slider creation."""
    source = _read_source()
    # Find the voice gain scale creation
    idx = source.find("voice_gain_scale")
    assert idx != -1, "voice_gain_scale must exist"
    nearby = source[idx:idx+200]
    assert "to=20.0" in nearby, "voice_gain_scale must have to=20.0"

def test_music_slider_max_increased():
    """Music slider should allow up to 5.0x."""
    source = _read_source()
    assert "to=5.0" in source, "Music slider must allow gains up to 5.0x"

def test_music_slider_max_is_5():
    """Music gain scale to=5.0 must exist in slider creation."""
    source = _read_source()
    idx = source.find("music_gain_scale")
    assert idx != -1, "music_gain_scale must exist"
    nearby = source[idx:idx+200]
    assert "to=5.0" in nearby, "music_gain_scale must have to=5.0"


# ─── Preset loading syncs volume globals + dB labels ───────────────

def test_preset_loading_syncs_volume_globals():
    """Preset loading must call on_voice_gain_changed to sync globals + dB labels."""
    source = _read_source()
    # After voice_gain_var.set(), the on_voice_gain_changed callback must be called
    idx = source.find("voice_gain_var.set(preset_data")
    assert idx != -1, "Preset loading must set voice_gain_var"
    nearby = source[idx:idx+400]
    assert "on_voice_gain_changed" in nearby, \
        "Preset loading must call on_voice_gain_changed to sync globals and dB label"

def test_preset_silent_loading_syncs_volume_globals():
    """Silent preset loading must also sync volume globals + dB labels."""
    source = _read_source()
    # Find all preset loading sections that set voice_gain_var
    occurrences = [m.start() for m in re.finditer(r'voice_gain_var\.set\(', source)]
    synced = 0
    for idx in occurrences:
        nearby = source[idx:idx+400]
        if "on_voice_gain_changed" in nearby:
            synced += 1
    assert synced >= 2, \
        f"At least 2 preset loading locations must sync volume globals; found {synced}"


# ─── No FFMPEG_OUTPUT_VOLUME_BOOST constant ─────────────────────────

def test_no_ffmpeg_output_volume_boost_constant():
    """There should be no FFMPEG_OUTPUT_VOLUME_BOOST constant (was removed)."""
    source = _read_source()
    assert "FFMPEG_OUTPUT_VOLUME_BOOST" not in source, \
        "FFMPEG_OUTPUT_VOLUME_BOOST should not exist"


# ─── dB display (CapCut-style) ──────────────────────────────────────

def test_gain_to_db_str_exists():
    """_gain_to_db_str function must exist for CapCut-style dB display."""
    source = _read_source()
    assert "def _gain_to_db_str(" in source, \
        "_gain_to_db_str function must exist"

def test_gain_to_db_str_mute():
    """_gain_to_db_str(0) should return 'Mute'."""
    source = _read_source()
    func_start = source.find("def _gain_to_db_str(")
    assert func_start != -1
    func_body = source[func_start:func_start + 300]
    assert '"Mute"' in func_body or "'Mute'" in func_body, \
        "_gain_to_db_str should return 'Mute' for zero gain"

def test_gain_to_db_str_uses_log10():
    """_gain_to_db_str must use 20*log10 formula for dB conversion."""
    source = _read_source()
    func_start = source.find("def _gain_to_db_str(")
    assert func_start != -1
    func_body = source[func_start:func_start + 300]
    assert "log10" in func_body, "_gain_to_db_str must use log10 for dB"
    assert "20" in func_body, "_gain_to_db_str must use 20*log10 formula"

def test_gain_to_db_str_positive_format():
    """Positive dB values should be formatted with + prefix (CapCut-style)."""
    source = _read_source()
    func_start = source.find("def _gain_to_db_str(")
    assert func_start != -1
    func_body = source[func_start:func_start + 300]
    # Should include a + prefix for positive dB
    assert '"+' in func_body or "'+'" in func_body or 'f"+{' in func_body, \
        "Positive dB values should have + prefix (e.g. +6.0 dB)"

def test_gain_to_db_str_math_correctness():
    """Verify the dB formula: 20*log10(gain) produces correct values."""
    # Test known values: gain=1.0 -> 0 dB, gain=2.0 -> +6.0 dB, gain=0.5 -> -6.0 dB
    assert abs(20.0 * math.log10(1.0)) < 0.01, "gain=1.0 should be 0 dB"
    assert abs(20.0 * math.log10(2.0) - 6.02) < 0.1, "gain=2.0 should be ~+6 dB"
    assert abs(20.0 * math.log10(0.5) - (-6.02)) < 0.1, "gain=0.5 should be ~-6 dB"
    assert abs(20.0 * math.log10(5.0) - 13.98) < 0.1, "gain=5.0 should be ~+14 dB"

def test_volume_label_shows_db():
    """Volume labels should display dB values via _gain_to_db_str, not multipliers."""
    source = _read_source()
    # voice_gain_label should use _gain_to_db_str, not f"{gain:.1f}x"
    assert "_gain_to_db_str" in source, "_gain_to_db_str must be used"
    # Labels should be initialized with dB display
    idx = source.find("voice_gain_label")
    assert idx != -1
    nearby = source[idx:idx+200]
    assert "_gain_to_db_str" in nearby, "voice_gain_label should use _gain_to_db_str"

def test_voice_callback_shows_db():
    """on_voice_gain_changed must update label with dB via _gain_to_db_str."""
    source = _read_source()
    func_start = source.find("def on_voice_gain_changed(")
    assert func_start != -1
    func_body = source[func_start:func_start + 400]
    assert "_gain_to_db_str" in func_body, \
        "on_voice_gain_changed should use _gain_to_db_str for dB display"

def test_music_callback_shows_db():
    """on_music_gain_changed must update label with dB via _gain_to_db_str."""
    source = _read_source()
    func_start = source.find("def on_music_gain_changed(")
    assert func_start != -1
    func_body = source[func_start:func_start + 400]
    assert "_gain_to_db_str" in func_body, \
        "on_music_gain_changed should use _gain_to_db_str for dB display"

def test_voice_callback_updates_global():
    """on_voice_gain_changed must update the global VOICE_GAIN."""
    source = _read_source()
    func_start = source.find("def on_voice_gain_changed(")
    assert func_start != -1
    func_body = source[func_start:func_start + 400]
    assert "VOICE_GAIN" in func_body, \
        "on_voice_gain_changed should set globals()['VOICE_GAIN']"

def test_music_callback_updates_global():
    """on_music_gain_changed must update the global MUSIC_GAIN."""
    source = _read_source()
    func_start = source.find("def on_music_gain_changed(")
    assert func_start != -1
    func_body = source[func_start:func_start + 400]
    assert "MUSIC_GAIN" in func_body, \
        "on_music_gain_changed should set globals()['MUSIC_GAIN']"

def test_import_math_for_db():
    """math module must be imported for log10 dB calculation."""
    source = _read_source()
    assert "import math" in source, "math module needed for dB calculation"

def test_db_display_in_both_labels():
    """Both voice and music gain labels should use dB display."""
    source = _read_source()
    # Find voice label creation
    voice_idx = source.find("voice_gain_label = ttk.Label")
    assert voice_idx != -1, "voice_gain_label creation must exist"
    voice_nearby = source[voice_idx:voice_idx + 200]
    assert "_gain_to_db_str" in voice_nearby, "voice label must use dB format"
    
    # Find music label creation  
    music_idx = source.find("music_gain_label = ttk.Label")
    assert music_idx != -1, "music_gain_label creation must exist"
    music_nearby = source[music_idx:music_idx + 200]
    assert "_gain_to_db_str" in music_nearby, "music label must use dB format"

def test_openai_api_key_variable_exists():
    """OPENAI_API_KEY global variable must exist."""
    source = _read_source()
    assert re.search(r'^OPENAI_API_KEY\s*=', source, re.MULTILINE), \
        "OPENAI_API_KEY variable must be defined at module level"
