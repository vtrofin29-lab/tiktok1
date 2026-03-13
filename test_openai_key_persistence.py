"""Tests for OpenAI API key persistence and translation prompt features."""
import os
import re
import json
import tempfile


def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── OpenAI Key Save Button ─────────────────────────────────────────

def test_save_button_exists_in_openai_key_gui():
    """GUI should have a Save button next to Set for OpenAI key."""
    source = _read_source()
    assert '_save_openai_key' in source, \
        "Should have _save_openai_key method"

def test_save_openai_key_method_defined():
    """_save_openai_key method should be defined."""
    source = _read_source()
    assert re.search(r'def _save_openai_key\(self\)', source), \
        "_save_openai_key method should be defined"

def test_save_button_in_openai_frame():
    """Save button should be packed in openai_frame."""
    source = _read_source()
    assert re.search(r'text="Save".*command=self\._save_openai_key', source), \
        "Save button should call _save_openai_key"


# ─── OpenAI Config File ─────────────────────────────────────────────

def test_openai_config_json_save():
    """_save_openai_key should write to openai_config.json."""
    source = _read_source()
    assert 'openai_config.json' in source, \
        "Should reference openai_config.json config file"

def test_openai_config_json_load():
    """GUI should load OpenAI key from openai_config.json on startup."""
    source = _read_source()
    # Should load from config file during GUI init
    load_pattern = re.search(
        r'openai_config_path.*openai_config\.json.*openai_api_key',
        source, re.DOTALL
    )
    assert load_pattern, \
        "Should load openai_api_key from openai_config.json at startup"

def test_openai_key_json_format():
    """Config should use 'openai_api_key' as the JSON key."""
    source = _read_source()
    assert '"openai_api_key"' in source, \
        "Should use 'openai_api_key' as JSON key in config file"


# ─── OpenAI Key in Presets ───────────────────────────────────────────

def test_openai_key_saved_in_preset():
    """Preset save should include openai_api_key."""
    source = _read_source()
    assert re.search(r'"openai_api_key".*openai_key_var', source), \
        "Preset save should include openai_api_key from openai_key_var"

def test_openai_key_loaded_from_preset():
    """Preset load should restore openai_api_key."""
    source = _read_source()
    matches = re.findall(r'preset_data\.get\("openai_api_key"', source)
    assert len(matches) >= 2, \
        "Both preset load functions should load openai_api_key"


# ─── GitIgnore ───────────────────────────────────────────────────────

def test_openai_config_in_gitignore():
    """openai_config.json should be in .gitignore to prevent key leaks."""
    gitignore_path = os.path.join(os.path.dirname(__file__), ".gitignore")
    with open(gitignore_path, "r") as f:
        content = f.read()
    assert 'openai_config.json' in content, \
        "openai_config.json should be in .gitignore"


# ─── Translation Custom Prompt ───────────────────────────────────────

def test_translation_custom_prompt_global():
    """TRANSLATION_CUSTOM_PROMPT global should exist."""
    source = _read_source()
    assert re.search(r'^TRANSLATION_CUSTOM_PROMPT\s*=', source, re.MULTILINE), \
        "TRANSLATION_CUSTOM_PROMPT global must be defined"

def test_language_placeholder_in_prompt():
    """Custom prompt should support {language} placeholder."""
    source = _read_source()
    assert "replace('{language}'" in source or 'replace("{language}"' in source, \
        "Should replace {language} placeholder in custom prompt"

def test_prompt_hint_shown():
    """GUI should show hint about {language} placeholder."""
    source = _read_source()
    assert '{language}' in source, \
        "Should display {language} placeholder hint in GUI"

def test_prompt_saved_in_preset():
    """Translation prompt should be saved in presets."""
    source = _read_source()
    assert '"translation_custom_prompt"' in source, \
        "translation_custom_prompt should be saved in presets"


# ─── Integration: Key is applied on load ──────────────────────────────

def test_loaded_key_applied_to_global():
    """When key is loaded from file, it should set OPENAI_API_KEY global."""
    source = _read_source()
    # Check that loading from config file sets the global
    assert re.search(
        r"globals\(\)\['OPENAI_API_KEY'\]\s*=\s*saved_openai_key",
        source
    ), "Loading from openai_config.json should set OPENAI_API_KEY global"


# ─── Verify Button ───────────────────────────────────────────────────

def test_verify_button_exists():
    """GUI should have a Verify button for testing the OpenAI key."""
    source = _read_source()
    assert re.search(r'text="Verify".*command=self\._verify_openai_key', source), \
        "Verify button should call _verify_openai_key"

def test_verify_openai_key_method_defined():
    """_verify_openai_key method should be defined."""
    source = _read_source()
    assert re.search(r'def _verify_openai_key\(self\)', source), \
        "_verify_openai_key method should be defined"

def test_verify_uses_gpt4o_mini():
    """Verify should test with gpt-4o-mini model."""
    source = _read_source()
    # Find the verify method
    idx = source.find('def _verify_openai_key')
    assert idx != -1
    method_body = source[idx:idx+2000]
    assert 'gpt-4o-mini' in method_body, \
        "Verify should use gpt-4o-mini model"

def test_verify_checks_401_status():
    """Verify should handle 401 (invalid key) response."""
    source = _read_source()
    idx = source.find('def _verify_openai_key')
    assert idx != -1
    method_body = source[idx:idx+3000]
    assert '401' in method_body, \
        "Verify should check for 401 unauthorized status"

def test_verify_shows_platform_url():
    """Verify success should mention platform.openai.com/usage."""
    source = _read_source()
    idx = source.find('def _verify_openai_key')
    assert idx != -1
    method_body = source[idx:idx+3000]
    assert 'platform.openai.com/usage' in method_body, \
        "Verify should show platform.openai.com/usage link"


# ─── API ≠ ChatGPT Logging ──────────────────────────────────────────

def test_startup_log_mentions_platform():
    """Startup config load should log platform.openai.com/usage URL."""
    source = _read_source()
    # Look near the config loading section
    assert 'platform.openai.com/usage' in source, \
        "Should mention platform.openai.com/usage in logging"

def test_startup_log_clarifies_not_chatgpt():
    """Startup should clarify that API calls don't appear on chat.openai.com."""
    source = _read_source()
    assert 'chat.openai.com' in source, \
        "Should clarify API calls don't show on chat.openai.com"

def test_translate_logs_which_engine():
    """translate_segments should log whether OpenAI or googletrans is used."""
    source = _read_source()
    assert 'No OpenAI API key set' in source, \
        "Should log when no API key is set (falling back to googletrans)"


# ─── Retry Logic for 429 ────────────────────────────────────────────

def test_openai_translate_has_retry_loop():
    """_openai_translate_segments should retry on 429 rate-limit errors."""
    source = _read_source()
    assert 'max_retries' in source, \
        "Should have max_retries for 429 retry logic"

def test_openai_translate_retries_on_429():
    """_openai_translate_segments should detect 429 status and retry."""
    source = _read_source()
    assert 'status_code == 429' in source, \
        "Should check for 429 status code in _openai_translate_segments"

def test_openai_translate_retry_backoff():
    """_openai_translate_segments should use exponential backoff on retries."""
    source = _read_source()
    assert '2 ** attempt' in source, \
        "Should use exponential backoff (2 ** attempt)"

def test_openai_translate_retry_billing_tip():
    """Should show billing URL tip when rate limited."""
    source = _read_source()
    assert 'platform.openai.com/settings/organization/billing' in source, \
        "Should mention billing URL for adding credit"


# ─── Custom Prompt Logging ──────────────────────────────────────────

def test_openai_translate_logs_custom_prompt():
    """Should log when custom prompt is being used."""
    source = _read_source()
    assert 'Using CUSTOM prompt' in source, \
        "Should log when using a custom translation prompt"

def test_openai_translate_logs_default_prompt():
    """Should log when default prompt is being used."""
    source = _read_source()
    assert 'Using default subtitle translator prompt' in source, \
        "Should log when using the default prompt"


# ─── Improved 429 Verify Message ────────────────────────────────────

def test_verify_429_mentions_billing_credit():
    """429 verify message should tell user to add billing credit."""
    source = _read_source()
    # Find the 429 handling in _verify_openai_key
    assert 'Billing Credit Required' in source or 'billing credit' in source.lower(), \
        "429 message should mention billing credit"

def test_verify_429_mentions_free_tier():
    """429 verify message should explain that free-tier keys have no quota."""
    source = _read_source()
    assert 'free-tier' in source.lower() or 'Free-tier' in source or 'free tier' in source.lower(), \
        "429 message should explain free-tier keys have no quota"

def test_verify_429_has_billing_url():
    """429 verify message should link to billing page."""
    source = _read_source()
    assert 'platform.openai.com/settings/organization/billing' in source, \
        "429 message should link to billing settings page"


# ─── Functional Retry Test ──────────────────────────────────────────

def test_openai_translate_retry_returns_none_after_all_retries():
    """After all retries exhausted, should return None."""
    source = _read_source()
    assert 'All retries failed' in source, \
        "Should log message when all retries are exhausted"
