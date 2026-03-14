"""Tests for TTS (Text-to-Speech) — GenAI Pro exclusively.

Validates that:
1. generate_tts_audio uses GenAI Pro only (no OpenAI TTS or gTTS fallback)
2. replace_voice_with_tts checks GenAI Pro key only
3. on_ai_voice_toggle checks GenAI Pro key only
4. _openai_tts_generate function exists but is NOT called by generate_tts_audio
5. Translation prompt rules are in Romanian and allow adding text for story coherence
"""
import os
import re


def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── GenAI Pro Only TTS ─────────────────────────────────────────────

def test_generate_tts_audio_does_not_call_openai_tts():
    """generate_tts_audio should NOT call _openai_tts_generate."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert '_openai_tts_generate(' not in func_body, \
        "generate_tts_audio should NOT call _openai_tts_generate — GenAI Pro only"

def test_generate_tts_audio_uses_genaipro():
    """generate_tts_audio should use GenAI Pro."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'generate_tts_with_genaipro(' in func_body, \
        "generate_tts_audio should use GenAI Pro"

def test_generate_tts_audio_no_gtts_fallback():
    """generate_tts_audio should NOT use gTTS as fallback."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "generate_tts_audio should NOT use gTTS — GenAI Pro only"


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


# ─── replace_voice_with_tts Checks GenAI Pro Only ───────────────────

def test_replace_voice_checks_genaipro_only():
    """replace_voice_with_tts should check GenAI Pro key only."""
    source = _read_source()
    func_match = re.search(r'def replace_voice_with_tts\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find replace_voice_with_tts function"
    func_body = func_match.group(0)
    assert '_get_genaipro_api_key' in func_body, \
        "replace_voice_with_tts should check GenAI Pro key"
    assert 'has_openai' not in func_body, \
        "replace_voice_with_tts should NOT check OpenAI for TTS"


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


# ─── _openai_tts_generate Exists But Is Not Used ─────────────────────

def test_openai_tts_function_exists():
    """_openai_tts_generate function should exist (dormant)."""
    source = _read_source()
    assert re.search(r'def _openai_tts_generate\(', source), \
        "_openai_tts_generate function should be defined (dormant)"


# ─── Voice Pipeline Uses GenAI Pro (not gTTS directly) ──────────────

def test_submit_voice_does_not_use_gtts():
    """_submit_voice_for_job should NOT fall back to gTTS directly."""
    source = _read_source()
    func_match = re.search(r'def _submit_voice_for_job\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find _submit_voice_for_job function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "_submit_voice_for_job should NOT use gTTS directly"

def test_complete_voice_does_not_use_gtts():
    """_complete_voice_for_job should NOT fall back to gTTS directly."""
    source = _read_source()
    func_match = re.search(r'def _complete_voice_for_job\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find _complete_voice_for_job function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "_complete_voice_for_job should NOT use gTTS directly"


# ─── on_ai_voice_toggle Checks GenAI Pro Only ────────────────────────

def test_voice_toggle_checks_genaipro_only():
    """on_ai_voice_toggle should check GenAI Pro key only."""
    source = _read_source()
    func_match = re.search(r'def on_ai_voice_toggle\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find on_ai_voice_toggle function"
    func_body = func_match.group(0)
    assert '_get_genaipro_api_key' in func_body, \
        "on_ai_voice_toggle should check GenAI Pro API key"
    assert 'has_openai' not in func_body and 'OPENAI_API_KEY' not in func_body, \
        "on_ai_voice_toggle should NOT check OpenAI for TTS"


# ─── Translation Prompt in Romanian ─────────────────────────────────

def test_translation_prompt_in_romanian():
    """Translation system prompt rules should be in Romanian."""
    source = _read_source()
    assert 'REGULI FORMAT' in source or 'REGULI IMPORTANTE' in source, \
        "Translation rules should be in Romanian"

def test_translation_allows_adding_text():
    """Translation rules should allow OpenAI to add text for story coherence."""
    source = _read_source()
    assert 'povestea' in source or 'logică' in source or 'sens' in source, \
        "Rules should mention allowing text for story coherence (povestea/logică/sens)"

def test_translation_no_word_for_word():
    """Translation rules should NOT force word-for-word translation."""
    source = _read_source()
    assert 'cuvânt cu cuvânt' in source, \
        "Rules should mention NOT translating word-for-word (cuvânt cu cuvânt)"
