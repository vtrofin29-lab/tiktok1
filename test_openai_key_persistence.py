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
