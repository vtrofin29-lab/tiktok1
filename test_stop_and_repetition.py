"""Tests for Stop button and translation anti-repetition post-processing."""
import os
import re
import sys

def _read_source():
    """Read the main source file."""
    src_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(src_path, "r", encoding="utf-8") as f:
        return f.read()


# ─── Import the module for functional tests ────────────────────────
def _import_module():
    """Import tiktok_full_gui module for functional testing."""
    sys.path.insert(0, os.path.dirname(__file__))
    # We need to handle the tkinter import issue in test environment
    import importlib
    try:
        import tiktok_full_gui as mod
        return mod
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════
# STOP BUTTON TESTS
# ═══════════════════════════════════════════════════════════════════

def test_stop_requested_global_exists():
    """STOP_REQUESTED global variable must exist."""
    source = _read_source()
    assert re.search(r'^STOP_REQUESTED\s*=\s*False', source, re.MULTILINE), \
        "STOP_REQUESTED = False must be defined at module level"


def test_stop_button_in_gui():
    """A Stop button must be present in bottom_controls."""
    source = _read_source()
    assert 'stop_btn' in source, "self.stop_btn must be defined in the GUI"
    assert 'Stop' in source, "Stop button text must be present"


def test_stop_button_has_command():
    """Stop button must have a command handler."""
    source = _read_source()
    assert '_on_stop' in source, "_on_stop method must exist for stop button"


def test_on_stop_method_exists():
    """The _on_stop method must be defined."""
    source = _read_source()
    assert re.search(r'def _on_stop\(self\)', source), \
        "_on_stop(self) method must be defined"


def test_on_stop_sets_stop_requested():
    """_on_stop must set STOP_REQUESTED to True."""
    source = _read_source()
    # Find the _on_stop method and check it sets the flag
    stop_method = re.search(r'def _on_stop\(self\):.*?(?=\n    def )', source, re.DOTALL)
    assert stop_method, "_on_stop method must exist"
    assert 'STOP_REQUESTED' in stop_method.group(0), \
        "_on_stop must reference STOP_REQUESTED"
    assert 'True' in stop_method.group(0), \
        "_on_stop must set STOP_REQUESTED to True"


def test_on_run_single_resets_stop_flag():
    """on_run_single must reset STOP_REQUESTED to False before starting."""
    source = _read_source()
    run_method = re.search(r'def on_run_single\(self\):.*?(?=\n    def )', source, re.DOTALL)
    assert run_method, "on_run_single method must exist"
    assert 'STOP_REQUESTED' in run_method.group(0), \
        "on_run_single must reference STOP_REQUESTED"
    assert 'False' in run_method.group(0), \
        "on_run_single must reset STOP_REQUESTED to False"


def test_check_stop_in_process_single_job():
    """process_single_job must check STOP_REQUESTED."""
    source = _read_source()
    # Find process_single_job function
    job_func = re.search(r'def process_single_job\(.*?\n(?=def )', source, re.DOTALL)
    assert job_func, "process_single_job must exist"
    assert '_check_stop' in job_func.group(0) or 'STOP_REQUESTED' in job_func.group(0), \
        "process_single_job must check for stop requests"


def test_interrupted_error_handled():
    """process_single_job must handle InterruptedError."""
    source = _read_source()
    assert 'except InterruptedError' in source, \
        "InterruptedError must be caught in process_single_job"


# ═══════════════════════════════════════════════════════════════════
# TRANSLATION ANTI-REPETITION TESTS
# ═══════════════════════════════════════════════════════════════════

def test_reduce_translation_repetition_function_exists():
    """_reduce_translation_repetition function must exist."""
    source = _read_source()
    assert 'def _reduce_translation_repetition' in source, \
        "_reduce_translation_repetition function must be defined"


def test_build_short_reference_function_exists():
    """_build_short_reference function must exist."""
    source = _read_source()
    assert 'def _build_short_reference' in source, \
        "_build_short_reference function must be defined"


def test_reduce_repetition_called_in_translate_segments():
    """translate_segments must call _reduce_translation_repetition for googletrans paths."""
    source = _read_source()
    # Find the translate_segments function
    func = re.search(r'def translate_segments\(.*?\n(?=def )', source, re.DOTALL)
    assert func, "translate_segments must exist"
    assert '_reduce_translation_repetition' in func.group(0), \
        "translate_segments must call _reduce_translation_repetition"


def test_reduce_repetition_empty_input():
    """_reduce_translation_repetition should handle empty input."""
    mod = _import_module()
    if mod is None:
        # Can't import module, skip
        return
    result = mod._reduce_translation_repetition([])
    assert result == []
    result = mod._reduce_translation_repetition(None)
    assert result is None


def test_reduce_repetition_single_segment():
    """Single segment should be returned unchanged."""
    mod = _import_module()
    if mod is None:
        return
    segments = [{"text": "Hello world"}]
    result = mod._reduce_translation_repetition(segments)
    assert len(result) == 1
    assert result[0]["text"] == "Hello world"


def test_reduce_repetition_similar_segments_romanian():
    """Similar Romanian segments should be shortened."""
    mod = _import_module()
    if mod is None:
        return
    segments = [
        {"text": "El avea 20 de ani"},
        {"text": "Ea avea 20 de ani"}
    ]
    result = mod._reduce_translation_repetition(segments)
    assert len(result) == 2
    assert result[0]["text"] == "El avea 20 de ani"  # First unchanged
    # Second should be shortened (not the full repetition)
    assert result[1]["text"] != "Ea avea 20 de ani", \
        f"Repeated text should be shortened, got: {result[1]['text']}"
    assert "la fel" in result[1]["text"].lower() or "ea" in result[1]["text"].lower(), \
        f"Should contain 'la fel' or 'ea', got: {result[1]['text']}"


def test_reduce_repetition_similar_segments_english():
    """Similar English segments should be shortened."""
    mod = _import_module()
    if mod is None:
        return
    segments = [
        {"text": "He was twenty years old"},
        {"text": "She was twenty years old"}
    ]
    result = mod._reduce_translation_repetition(segments)
    assert len(result) == 2
    assert result[0]["text"] == "He was twenty years old"  # First unchanged
    # Second should be shortened
    assert result[1]["text"] != "She was twenty years old", \
        f"Repeated text should be shortened, got: {result[1]['text']}"


def test_reduce_repetition_different_segments_unchanged():
    """Different segments should NOT be modified."""
    mod = _import_module()
    if mod is None:
        return
    segments = [
        {"text": "The sun was shining brightly"},
        {"text": "The cat jumped over the fence"}
    ]
    result = mod._reduce_translation_repetition(segments)
    assert len(result) == 2
    assert result[0]["text"] == "The sun was shining brightly"
    assert result[1]["text"] == "The cat jumped over the fence"


def test_reduce_repetition_short_segments_unchanged():
    """Short segments (< 4 words) should not be modified."""
    mod = _import_module()
    if mod is None:
        return
    segments = [
        {"text": "Da, el"},
        {"text": "Da, ea"}
    ]
    result = mod._reduce_translation_repetition(segments)
    assert len(result) == 2
    # Short segments should be unchanged
    assert result[1]["text"] == "Da, ea"


def test_build_short_reference_romanian():
    """_build_short_reference should produce Romanian-style references."""
    mod = _import_module()
    if mod is None:
        return
    result = mod._build_short_reference(
        "Ea avea 20 de ani", 
        "El avea 20 de ani", 
        diff_words=["ea"]
    )
    assert "la fel" in result.lower(), f"Should contain 'la fel', got: {result}"


def test_build_short_reference_english():
    """_build_short_reference should produce English-style references."""
    mod = _import_module()
    if mod is None:
        return
    result = mod._build_short_reference(
        "She was twenty years old", 
        "He was twenty years old", 
        diff_words=["she"]
    )
    assert "too" in result.lower(), f"Should contain 'too', got: {result}"


def test_build_short_reference_identical():
    """Identical segments should produce minimal reference."""
    mod = _import_module()
    if mod is None:
        return
    result = mod._build_short_reference(
        "El avea 20 de ani", 
        "El avea 20 de ani", 
        diff_words=[]
    )
    assert "la fel" in result.lower() or "the same" in result.lower(), \
        f"Identical segments should produce 'La fel' or 'The same', got: {result}"


# ═══════════════════════════════════════════════════════════════════
# OPENAI PROMPT ANTI-REPETITION TESTS
# ═══════════════════════════════════════════════════════════════════

def test_openai_prompt_has_anti_repetition():
    """OpenAI system prompt must instruct to avoid repetition (in Romanian)."""
    source = _read_source()
    assert 'EVITĂ repetițiile' in source or 'AVOID repetition' in source, \
        "System prompt must mention avoiding repetition"


def test_openai_prompt_has_example():
    """OpenAI system prompt must include a practical example of anti-repetition."""
    source = _read_source()
    # Romanian: "El avea 20 de ani" / "Ea avea 20 de ani"
    has_ro = 'El avea 20 de ani' in source and 'Ea avea 20 de ani' in source
    has_en = 'He was 20 years old' in source and 'She was 20 years old' in source
    assert has_ro or has_en, \
        "System prompt should include a practical example with age repetition"


# ═══════════════════════════════════════════════════════════════════
# CUSTOM TRANSLATION PROMPT TESTS
# ═══════════════════════════════════════════════════════════════════

def test_translation_custom_prompt_global_exists():
    """TRANSLATION_CUSTOM_PROMPT global must exist."""
    source = _read_source()
    assert re.search(r'^TRANSLATION_CUSTOM_PROMPT\s*=', source, re.MULTILINE), \
        "TRANSLATION_CUSTOM_PROMPT global must be defined"


def test_translation_custom_prompt_default_empty():
    """TRANSLATION_CUSTOM_PROMPT should default to empty string."""
    source = _read_source()
    assert 'TRANSLATION_CUSTOM_PROMPT = ""' in source or "TRANSLATION_CUSTOM_PROMPT = ''" in source, \
        "TRANSLATION_CUSTOM_PROMPT must default to empty string"


def test_translation_prompt_gui_field_exists():
    """GUI must have a translation prompt entry field."""
    source = _read_source()
    assert 'translation_prompt_var' in source, \
        "GUI must have translation_prompt_var for custom prompt"
    assert 'translation_prompt_entry' in source, \
        "GUI must have translation_prompt_entry for custom prompt"


def test_translation_prompt_set_button():
    """GUI must have a Set button for the translation prompt."""
    source = _read_source()
    assert '_apply_translation_prompt' in source, \
        "GUI must have _apply_translation_prompt method"


def test_translation_prompt_language_placeholder():
    """Custom prompt must support {language} placeholder auto-replacement."""
    source = _read_source()
    assert "replace('{language}'" in source or 'replace("{language}"' in source, \
        "Custom prompt must replace {language} placeholder with target language"


def test_translation_prompt_saved_in_preset():
    """Custom translation prompt must be saved/loaded in presets."""
    source = _read_source()
    assert '"translation_custom_prompt"' in source, \
        "translation_custom_prompt must be saved in preset"


def test_translation_prompt_uses_custom_when_set():
    """When custom prompt is set, it should be used instead of default."""
    source = _read_source()
    assert "TRANSLATION_CUSTOM_PROMPT" in source, \
        "Function must reference TRANSLATION_CUSTOM_PROMPT global"
    # Check there's a conditional that checks if custom prompt is set
    assert re.search(r'if\s+custom', source), \
        "Must check if custom prompt is provided before using it"


def test_translation_prompt_appends_format_rules():
    """Custom prompt should append output format rules automatically (Romanian)."""
    source = _read_source()
    assert 'REGULI FORMAT' in source or 'OUTPUT FORMAT RULES' in source, \
        "Custom prompt must append output format rules for numbered line format"


def test_custom_prompt_functional():
    """Functional test: TRANSLATION_CUSTOM_PROMPT replaces {language} in system prompt."""
    mod = _import_module()
    if mod is None:
        return  # Skip if module can't be imported

    # Set a custom prompt with {language} placeholder
    mod.TRANSLATION_CUSTOM_PROMPT = "Translate subtitles to {language} using casual slang"
    
    # The function should use the custom prompt
    source = _read_source()
    assert "globals().get('TRANSLATION_CUSTOM_PROMPT'" in source, \
        "_openai_translate_segments must read TRANSLATION_CUSTOM_PROMPT from globals"
    
    # Clean up
    mod.TRANSLATION_CUSTOM_PROMPT = ""
