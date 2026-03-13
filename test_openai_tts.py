"""Tests for TTS (Text-to-Speech) — 3-tier fallback: GenAI Pro → OpenAI TTS → gTTS.

Validates that:
1. generate_tts_audio uses a 3-tier fallback: GenAI Pro → OpenAI TTS → gTTS
2. replace_voice_with_tts checks all TTS engines (not just GenAI Pro)
3. on_ai_voice_toggle accepts any available TTS engine
4. _openai_tts_generate function exists and is called by generate_tts_audio
5. Translation prompt rules are in Romanian and allow adding text for story coherence
"""
import os
import re


def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── 3-Tier TTS Fallback ────────────────────────────────────────────

def test_generate_tts_audio_calls_openai_tts():
    """generate_tts_audio should call _openai_tts_generate as Tier 2 fallback."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert '_openai_tts_generate(' in func_body, \
        "generate_tts_audio should call _openai_tts_generate as Tier 2"

def test_generate_tts_audio_uses_genaipro():
    """generate_tts_audio should try GenAI Pro as Tier 1."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'generate_tts_with_genaipro(' in func_body, \
        "generate_tts_audio should use GenAI Pro as Tier 1"

def test_generate_tts_audio_uses_gtts_fallback():
    """generate_tts_audio should use gTTS as Tier 3 fallback."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'gTTS(' in func_body, \
        "generate_tts_audio should use gTTS as Tier 3 fallback"

def test_generate_tts_audio_tier_order():
    """generate_tts_audio should try GenAI Pro first, then OpenAI, then gTTS."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    pos_genaipro = func_body.find('generate_tts_with_genaipro(')
    pos_openai = func_body.find('_openai_tts_generate(')
    pos_gtts = func_body.find('gTTS(')
    assert pos_genaipro >= 0, "Should find generate_tts_with_genaipro call"
    assert pos_openai >= 0, "Should find _openai_tts_generate call"
    assert pos_gtts >= 0, "Should find gTTS call"
    assert pos_genaipro < pos_openai < pos_gtts, \
        "Order should be: GenAI Pro → OpenAI TTS → gTTS"


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


# ─── replace_voice_with_tts Checks Multiple Engines ─────────────────

def test_replace_voice_checks_multiple_engines():
    """replace_voice_with_tts should check for multiple TTS engines."""
    source = _read_source()
    func_match = re.search(r'def replace_voice_with_tts\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find replace_voice_with_tts function"
    func_body = func_match.group(0)
    assert 'OPENAI_API_KEY' in func_body or 'has_openai' in func_body, \
        "replace_voice_with_tts should check OpenAI availability"


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


# ─── _openai_tts_generate Exists and Is Active ──────────────────────

def test_openai_tts_function_exists():
    """_openai_tts_generate function should exist."""
    source = _read_source()
    assert re.search(r'def _openai_tts_generate\(', source), \
        "_openai_tts_generate function should be defined"


# ─── Voice Pipeline Uses GenAI Pro (not gTTS directly) ──────────────

def test_submit_voice_does_not_use_gtts():
    """_submit_voice_for_job should NOT fall back to gTTS directly."""
    source = _read_source()
    func_match = re.search(r'def _submit_voice_for_job\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find _submit_voice_for_job function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "_submit_voice_for_job should NOT use gTTS directly — gTTS is in generate_tts_audio fallback chain"

def test_complete_voice_does_not_use_gtts():
    """_complete_voice_for_job should NOT fall back to gTTS directly."""
    source = _read_source()
    func_match = re.search(r'def _complete_voice_for_job\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find _complete_voice_for_job function"
    func_body = func_match.group(0)
    assert 'gTTS(' not in func_body, \
        "_complete_voice_for_job should NOT use gTTS directly — gTTS is in generate_tts_audio fallback chain"


# ─── on_ai_voice_toggle Checks All Engines ───────────────────────────

def test_voice_toggle_checks_multiple_engines():
    """on_ai_voice_toggle should check for any available TTS engine."""
    source = _read_source()
    func_match = re.search(r'def on_ai_voice_toggle\(.*?\n(?=    def |\nclass |\Z)', source, re.DOTALL)
    assert func_match, "Should find on_ai_voice_toggle function"
    func_body = func_match.group(0)
    assert '_get_genaipro_api_key' in func_body, \
        "on_ai_voice_toggle should check GenAI Pro API key"
    assert 'OPENAI_API_KEY' in func_body or 'has_openai' in func_body, \
        "on_ai_voice_toggle should also check for OpenAI key"


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
