"""Tests for TTS (Text-to-Speech) — OpenAI NOT used for voice generation.

Validates that:
1. OpenAI is used ONLY for translation, NOT for TTS voice generation
2. generate_tts_audio uses GenAI Pro only (no gTTS fallback)
3. Verify success message does NOT promise OpenAI TTS
4. _openai_tts_generate function still exists (dormant, not called by TTS pipeline)
"""
import os
import re


def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── OpenAI NOT Used for TTS ────────────────────────────────────────

def test_generate_tts_audio_does_not_call_openai():
    """generate_tts_audio should NOT call _openai_tts_generate."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert '_openai_tts_generate(' not in func_body, \
        "generate_tts_audio should NOT call _openai_tts_generate — OpenAI is for translation only"

def test_generate_tts_audio_does_not_check_openai_key():
    """generate_tts_audio should NOT check OPENAI_API_KEY."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'OPENAI_API_KEY' not in func_body, \
        "generate_tts_audio should NOT reference OPENAI_API_KEY — OpenAI is for translation only"

def test_generate_tts_audio_uses_genaipro():
    """generate_tts_audio should try GenAI Pro."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'generate_tts_with_genaipro(' in func_body, \
        "generate_tts_audio should use GenAI Pro for TTS"

def test_generate_tts_audio_does_not_use_gtts():
    """generate_tts_audio should NOT fall back to gTTS — uses GenAI Pro only."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "generate_tts_audio should NOT use gTTS — voice generation uses GenAI Pro only"

def test_generate_tts_audio_docstring_mentions_no_openai():
    """generate_tts_audio docstring should clarify OpenAI is NOT used for TTS."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'NOT for voice generation' in func_body or 'not for TTS' in func_body.lower() or \
           'ONLY for translation' in func_body, \
        "Docstring should clarify OpenAI is NOT used for voice generation"


# ─── Verify Message Does NOT Promise OpenAI TTS ─────────────────────

def test_verify_success_does_not_mention_openai_tts():
    """Verify success message should NOT promise OpenAI TTS voice generation."""
    source = _read_source()
    assert 'Voice generation (TTS) will also use OpenAI' not in source, \
        "Verify log should NOT mention OpenAI TTS capability"

def test_verify_messagebox_does_not_promise_openai_tts():
    """Verify success messagebox should NOT promise OpenAI TTS."""
    source = _read_source()
    assert 'Voice generation (TTS) will use OpenAI TTS' not in source, \
        "Verify messagebox should NOT mention OpenAI TTS"

def test_verify_messagebox_mentions_translation_only():
    """Verify success messagebox should mention translations only."""
    source = _read_source()
    assert 'Translations will use GPT-4o-mini' in source, \
        "Verify messagebox should still mention translation"


# ─── replace_voice_with_tts Does NOT Check OpenAI ───────────────────

def test_replace_voice_does_not_check_openai_key():
    """replace_voice_with_tts should NOT check for OPENAI_API_KEY."""
    source = _read_source()
    func_match = re.search(r'def replace_voice_with_tts\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find replace_voice_with_tts function"
    func_body = func_match.group(0)
    assert 'OPENAI_API_KEY' not in func_body, \
        "replace_voice_with_tts should NOT reference OPENAI_API_KEY"


# ─── OpenAI Translation Still Works ─────────────────────────────────

def test_openai_translation_function_exists():
    """_openai_translate_segments function should still exist for translation."""
    source = _read_source()
    assert re.search(r'def _openai_translate_segments\(', source), \
        "_openai_translate_segments should be defined (OpenAI used for translation)"

def test_translate_segments_tries_openai_first():
    """translate_segments should try OpenAI for translation."""
    source = _read_source()
    func_match = re.search(r'def translate_segments\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find translate_segments function"
    func_body = func_match.group(0)
    assert '_openai_translate_segments(' in func_body, \
        "translate_segments should use OpenAI for translation"


# ─── _openai_tts_generate Still Exists (dormant) ────────────────────

def test_openai_tts_function_still_exists():
    """_openai_tts_generate function should still exist (dormant, unused by pipeline)."""
    source = _read_source()
    assert re.search(r'def _openai_tts_generate\(', source), \
        "_openai_tts_generate function should still be defined"


# ─── Voice Pipeline Does NOT Use gTTS ────────────────────────────────

def test_submit_voice_does_not_use_gtts():
    """_submit_voice_for_job should NOT fall back to gTTS."""
    source = _read_source()
    func_match = re.search(r'def _submit_voice_for_job\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find _submit_voice_for_job function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "_submit_voice_for_job should NOT use gTTS — voice generation uses GenAI Pro only"

def test_complete_voice_does_not_use_gtts():
    """_complete_voice_for_job should NOT fall back to gTTS."""
    source = _read_source()
    func_match = re.search(r'def _complete_voice_for_job\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find _complete_voice_for_job function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "_complete_voice_for_job should NOT use gTTS — voice generation uses GenAI Pro only"

def test_verify_messagebox_does_not_mention_gtts():
    """Verify success messagebox should NOT mention gTTS."""
    source = _read_source()
    assert 'GenAI Pro / gTTS' not in source, \
        "Verify messagebox should NOT mention gTTS — voice generation uses GenAI Pro only"

def test_voice_toggle_checks_genaipro_not_gtts():
    """on_ai_voice_toggle should check GenAI Pro key, not gTTS availability."""
    source = _read_source()
    func_match = re.search(r'def on_ai_voice_toggle\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find on_ai_voice_toggle function"
    func_body = func_match.group(0)
    assert 'gTTS' not in func_body and 'gtts' not in func_body, \
        "on_ai_voice_toggle should NOT reference gTTS"
    assert '_get_genaipro_api_key' in func_body, \
        "on_ai_voice_toggle should check GenAI Pro API key"
