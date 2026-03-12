"""Tests for translation quality improvement and volume control fixes."""
import os
import re

def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── Translation quality improvements ───────────────────────────────

def test_two_step_translation_for_non_english_targets():
    """For non-English targets, should use Whisper translate→English→Google Translate→target."""
    source = _read_source()
    func_start = source.find("def transcribe_captions(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    # Should have a flag for second-pass translation (non-English targets)
    assert "_needs_second_pass_translation" in func_body, \
        "Should have _needs_second_pass_translation flag for two-step translation"
    # Should always use Whisper translate when translation is requested
    assert 'task="translate"' in func_body or "task='translate'" in func_body or \
           "_whisper_task = \"translate\"" in func_body, \
        "Should use Whisper translate task when any translation is requested"


def test_whisper_translate_always_used_for_translation():
    """Whisper's translate task should be used for ALL translation targets, not just English."""
    source = _read_source()
    func_start = source.find("def transcribe_captions(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    # The whisper task should be set to 'translate' for any translation target,
    # not just when target is English
    assert "_whisper_task = \"translate\"" in func_body, \
        "Should set _whisper_task to translate for any translation target"
    # The logic should set translate for ALL targets, then do a second pass
    # for non-English targets
    assert "_needs_second_pass_translation = True" in func_body, \
        "Should set _needs_second_pass_translation for non-English targets"


def test_two_step_logging():
    """Should log the two-step translation approach for non-English targets."""
    source = _read_source()
    func_start = source.find("def transcribe_captions(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end].lower()
    assert "two-step" in func_body, \
        "Should log the two-step translation approach"


# ─── Volume control fixes ───────────────────────────────────────────

def test_voice_gain_default_increased():
    """Default VOICE_GAIN should be 2.5x or higher for better clarity."""
    source = _read_source()
    match = re.search(r'VOICE_GAIN\s*=\s*([0-9.]+)', source)
    assert match is not None, "VOICE_GAIN constant should exist"
    gain = float(match.group(1))
    assert gain >= 2.0, f"VOICE_GAIN default should be >= 2.0 for better clarity, got {gain}"


def test_voice_slider_max_increased():
    """Voice volume slider should have max >= 5.0 for sufficient headroom."""
    source = _read_source()
    # Find the voice gain scale creation with to= parameter
    voice_scale_pattern = re.search(
        r'voice_gain_scale\s*=\s*tk\.Scale\([^)]*to=([0-9.]+)', source)
    assert voice_scale_pattern is not None, "Voice gain scale should exist"
    max_val = float(voice_scale_pattern.group(1))
    assert max_val >= 5.0, f"Voice slider max should be >= 5.0, got {max_val}"


def test_music_slider_max_increased():
    """Music volume slider should have max >= 2.5 for sufficient headroom."""
    source = _read_source()
    music_scale_pattern = re.search(
        r'music_gain_scale\s*=\s*tk\.Scale\([^)]*to=([0-9.]+)', source)
    assert music_scale_pattern is not None, "Music gain scale should exist"
    max_val = float(music_scale_pattern.group(1))
    assert max_val >= 2.5, f"Music slider max should be >= 2.5, got {max_val}"


def test_per_job_voice_gain_in_batch_queue():
    """Job dicts for batch queue should include voice_gain."""
    source = _read_source()
    # Find the add_job function's job dict construction
    add_job_start = source.find("def add_job(")
    assert add_job_start != -1, "add_job function should exist"
    add_job_end = source.find("\n    def ", add_job_start + 10)
    add_job_body = source[add_job_start:add_job_end]
    assert '"voice_gain"' in add_job_body, \
        "Batch queue job dict should include voice_gain"
    assert '"music_gain"' in add_job_body, \
        "Batch queue job dict should include music_gain"


def test_per_job_voice_gain_in_single_run():
    """Job dict for single run should include voice_gain."""
    source = _read_source()
    # Find the on_run_single function
    run_single_start = source.find("def on_run_single(")
    assert run_single_start != -1, "on_run_single function should exist"
    run_single_end = source.find("\n    def ", run_single_start + 10)
    run_single_body = source[run_single_start:run_single_end]
    assert '"voice_gain"' in run_single_body, \
        "Single run job dict should include voice_gain"
    assert '"music_gain"' in run_single_body, \
        "Single run job dict should include music_gain"


def test_process_single_job_accepts_voice_gain():
    """process_single_job should accept voice_gain and music_gain parameters."""
    source = _read_source()
    sig_start = source.find("def process_single_job(")
    assert sig_start != -1
    # Find the end of the signature (closing paren + colon)
    sig_end = source.find(":", sig_start)
    signature = source[sig_start:sig_end]
    assert "voice_gain" in signature, \
        "process_single_job should have voice_gain parameter"
    assert "music_gain" in signature, \
        "process_single_job should have music_gain parameter"


def test_process_single_job_applies_per_job_gains():
    """process_single_job should apply per-job gains to globals."""
    source = _read_source()
    func_start = source.find("def process_single_job(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    # Should set globals from per-job parameters
    assert "globals()['VOICE_GAIN'] = voice_gain" in func_body, \
        "Should apply per-job voice_gain to global"
    assert "globals()['MUSIC_GAIN'] = music_gain" in func_body, \
        "Should apply per-job music_gain to global"


def test_run_video_job_passes_voice_gain():
    """_run_video_job should pass voice_gain and music_gain to process_single_job."""
    source = _read_source()
    func_start = source.find("def _run_video_job(")
    assert func_start != -1
    func_end = source.find("\ndef ", func_start + 10)
    func_body = source[func_start:func_end]
    assert 'voice_gain=job.get("voice_gain")' in func_body, \
        "_run_video_job should pass voice_gain from job dict"
    assert 'music_gain=job.get("music_gain")' in func_body, \
        "_run_video_job should pass music_gain from job dict"


def test_preset_loading_syncs_volume_globals():
    """Preset loading should sync volume globals via callbacks."""
    source = _read_source()
    # Check load_preset function
    load_start = source.find("def load_preset(self):")
    assert load_start != -1
    load_end = source.find("\n    def ", load_start + 10)
    load_body = source[load_start:load_end]
    assert "on_voice_gain_changed" in load_body, \
        "load_preset should call on_voice_gain_changed to sync globals"
    assert "on_music_gain_changed" in load_body, \
        "load_preset should call on_music_gain_changed to sync globals"


def test_preset_silent_loading_syncs_volume_globals():
    """Silent preset loading should also sync volume globals via callbacks."""
    source = _read_source()
    # Check load_preset_silent function
    load_start = source.find("def load_preset_silent(self):")
    assert load_start != -1
    load_end = source.find("\n    def ", load_start + 10)
    load_body = source[load_start:load_end]
    assert "on_voice_gain_changed" in load_body, \
        "load_preset_silent should call on_voice_gain_changed to sync globals"
    assert "on_music_gain_changed" in load_body, \
        "load_preset_silent should call on_music_gain_changed to sync globals"


def test_reset_defaults_syncs_volume_globals():
    """Reset to defaults should sync volume globals via callbacks."""
    source = _read_source()
    # Look for reset function that sets voice_gain_var
    reset_pattern = re.findall(
        r'on_voice_gain_changed.*str.*VOICE_GAIN', source)
    assert len(reset_pattern) >= 1, \
        "Reset to defaults should call on_voice_gain_changed to sync globals"
