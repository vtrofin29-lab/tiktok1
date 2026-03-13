"""Tests for OpenAI TTS (Text-to-Speech) integration.

Validates that:
1. _openai_tts_generate function exists and uses correct API endpoint
2. generate_tts_audio tries OpenAI TTS before other engines
3. Verify success message mentions TTS capability
4. Proper error handling for 429 and other errors
"""
import os
import re


def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── OpenAI TTS Function Exists ─────────────────────────────────────

def test_openai_tts_function_defined():
    """_openai_tts_generate function should be defined."""
    source = _read_source()
    assert re.search(r'def _openai_tts_generate\(', source), \
        "_openai_tts_generate function should be defined"

def test_openai_tts_uses_correct_api_endpoint():
    """Should use OpenAI's /v1/audio/speech endpoint."""
    source = _read_source()
    assert 'api.openai.com/v1/audio/speech' in source, \
        "Should use OpenAI's /v1/audio/speech endpoint"

def test_openai_tts_uses_tts_model():
    """Should use the tts-1 model."""
    source = _read_source()
    assert "'tts-1'" in source or '"tts-1"' in source, \
        "Should use the tts-1 model"

def test_openai_tts_has_voice_selection():
    """Should select voice based on language."""
    source = _read_source()
    # Find the _openai_tts_generate function and check for voice_map
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert 'voice_map' in func_body, \
        "Should have a voice_map for language-based voice selection"

def test_openai_tts_uses_global_api_key():
    """Should use the global OPENAI_API_KEY (same as translation)."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert 'OPENAI_API_KEY' in func_body, \
        "Should use the global OPENAI_API_KEY"


# ─── OpenAI TTS Error Handling ──────────────────────────────────────

def test_openai_tts_handles_429():
    """Should handle 429 rate limit errors gracefully."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert '429' in func_body, \
        "Should handle 429 rate limit errors"

def test_openai_tts_returns_none_on_failure():
    """Should return None when API call fails."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert func_body.count('return None') >= 3, \
        "Should return None in multiple error paths"

def test_openai_tts_writes_mp3_file():
    """Should write response content to an MP3 file."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert "response.content" in func_body, \
        "Should write response.content to file (binary audio data)"
    assert "'mp3'" in func_body or "mp3" in func_body, \
        "Should generate MP3 format"


# ─── generate_tts_audio Integration ─────────────────────────────────

def test_generate_tts_audio_tries_openai_first():
    """generate_tts_audio should try OpenAI TTS before GenAI Pro and gTTS."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    
    idx_openai = func_body.index('_openai_tts_generate(')
    idx_genaipro = func_body.index('generate_tts_with_genaipro(')
    assert idx_openai < idx_genaipro, \
        "OpenAI TTS should be tried before GenAI Pro"

def test_generate_tts_audio_checks_openai_key():
    """generate_tts_audio should check for OPENAI_API_KEY before calling OpenAI TTS."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'OPENAI_API_KEY' in func_body, \
        "Should check for OPENAI_API_KEY"

def test_generate_tts_audio_falls_back_on_failure():
    """generate_tts_audio should fall back to next engine if OpenAI TTS fails."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'OpenAI TTS failed' in func_body, \
        "Should log when falling back from OpenAI TTS"

def test_generate_tts_audio_logs_openai_usage():
    """Should log that OpenAI TTS is being used."""
    source = _read_source()
    func_match = re.search(r'def generate_tts_audio\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find generate_tts_audio function"
    func_body = func_match.group(0)
    assert 'OpenAI TTS' in func_body or 'OpenAI' in func_body, \
        "Should log when using OpenAI TTS"


# ─── Verify Message Mentions TTS ────────────────────────────────────

def test_verify_success_mentions_tts():
    """Verify success message should mention that TTS/voice is also available."""
    source = _read_source()
    assert 'Voice generation (TTS) will also use OpenAI' in source, \
        "Verify log should mention TTS capability"

def test_verify_success_messagebox_mentions_tts():
    """Verify success messagebox should mention TTS."""
    source = _read_source()
    assert 'Voice generation (TTS) will use OpenAI TTS' in source, \
        "Verify messagebox should mention TTS"


# ─── OpenAI TTS Voice Options ──────────────────────────────────────

def test_openai_tts_supports_multiple_voices():
    """Should support multiple OpenAI voices for different languages."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    # OpenAI voices: alloy, echo, fable, onyx, nova, shimmer
    voice_count = sum(1 for v in ['alloy', 'nova', 'shimmer', 'onyx'] if v in func_body)
    assert voice_count >= 3, \
        f"Should support at least 3 different OpenAI voices (found {voice_count})"

def test_openai_tts_has_timeout():
    """Should have a reasonable timeout for TTS API calls."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert 'timeout=' in func_body, \
        "Should set a timeout for the API call"

def test_openai_tts_checks_requests_available():
    """Should check REQUESTS_AVAILABLE before attempting API call."""
    source = _read_source()
    func_match = re.search(r'def _openai_tts_generate\(.*?\n(?=def |\Z)', source, re.DOTALL)
    assert func_match, "Should find _openai_tts_generate function"
    func_body = func_match.group(0)
    assert 'REQUESTS_AVAILABLE' in func_body, \
        "Should check REQUESTS_AVAILABLE"
