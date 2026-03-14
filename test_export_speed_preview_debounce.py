"""Tests for export speed improvements and preview debounce fixes.

Tests cover:
1. MoviePy export uses os.cpu_count() threads (not hardcoded 4)
2. Font size slider uses debounce (after/after_cancel pattern)
3. Caption Y offset slider uses debounce (after/after_cancel pattern)
4. Spinbox caption Y offset shares debounce with slider
5. update_idletasks() is NOT called in slider handlers (prevents UI freeze)
6. Debounce methods exist and are separate from handlers
"""

import re


def _get_full_source():
    """Read the full source of tiktok_full_gui.py."""
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def _get_method_source(method_name):
    """Extract a method's source by regex (handles indented methods inside classes).
    
    Returns the source from 'def method_name' until the next method at the same indent level.
    """
    source = _get_full_source()
    # Find method def (indented, as class method)
    pattern = re.compile(
        rf'^( +)def {re.escape(method_name)}\(.*?\):\n(.*?)(?=^\1def |\Z)',
        re.MULTILINE | re.DOTALL
    )
    match = pattern.search(source)
    if match:
        return match.group(0)
    raise RuntimeError(f"Could not find method {method_name}")


def _get_function_source(func_name):
    """Extract a top-level function or large function source by finding its body."""
    source = _get_full_source()
    # Find the function by searching for 'def func_name(' and capturing until next top-level def
    pattern = re.compile(
        rf'^def {re.escape(func_name)}\(.*?\):\n(.*?)(?=^def |\Z)',
        re.MULTILINE | re.DOTALL
    )
    match = pattern.search(source)
    if match:
        return match.group(0)
    raise RuntimeError(f"Could not find function {func_name}")


# ── Export Thread Tests ──────────────────────────────────────────

def test_moviepy_threads_use_cpu_count():
    """MoviePy export must use os.cpu_count() threads, not hardcoded 4."""
    src = _get_function_source("compose_final_video_with_static_blurred_bg")
    assert "os.cpu_count()" in src, \
        "compose_final_video_with_static_blurred_bg must use os.cpu_count() for MoviePy threads"
    assert "threads_setting = 4" not in src, \
        "compose_final_video_with_static_blurred_bg must not use hardcoded threads_setting = 4"


def test_moviepy_threads_fallback_to_4():
    """os.cpu_count() fallback must be 4 when cpu_count returns None."""
    src = _get_function_source("compose_final_video_with_static_blurred_bg")
    assert "or 4" in src, \
        "compose_final_video_with_static_blurred_bg must have 'or 4' fallback for os.cpu_count()"


# ── Font Size Debounce Tests ────────────────────────────────────

def test_font_size_handler_does_not_call_update_idletasks():
    """Font size handler must NOT call update_idletasks() (causes UI freeze)."""
    src = _get_method_source("on_caption_font_size_changed")
    assert "update_idletasks" not in src, \
        "on_caption_font_size_changed must not call update_idletasks() (blocks UI)"


def test_font_size_handler_uses_after_cancel():
    """Font size handler must use after_cancel for debounce."""
    src = _get_method_source("on_caption_font_size_changed")
    assert "after_cancel" in src, \
        "on_caption_font_size_changed must use after_cancel for debounce"


def test_font_size_handler_uses_after():
    """Font size handler must schedule deferred update with self.after()."""
    src = _get_method_source("on_caption_font_size_changed")
    assert "self.after(" in src, \
        "on_caption_font_size_changed must use self.after() for debounce scheduling"


def test_font_size_deferred_method_exists():
    """Deferred font size preview update method must exist."""
    src = _get_full_source()
    assert "def _do_font_size_preview_update(self)" in src, \
        "TikTokApp must have _do_font_size_preview_update method"


def test_font_size_handler_still_updates_label_immediately():
    """Font size handler must still update the px label immediately (lightweight)."""
    src = _get_method_source("on_caption_font_size_changed")
    assert "caption_font_size_label" in src, \
        "on_caption_font_size_changed must still update font size label immediately"


def test_font_size_handler_still_sets_global():
    """Font size handler must still set CAPTION_FONT_SIZE global immediately."""
    src = _get_method_source("on_caption_font_size_changed")
    assert "CAPTION_FONT_SIZE" in src, \
        "on_caption_font_size_changed must still set CAPTION_FONT_SIZE global"


def test_font_size_deferred_calls_tiktok_preview():
    """Deferred font size update must call on_tiktok_preview_refresh (like position does)."""
    src = _get_method_source("_do_font_size_preview_update")
    assert "on_tiktok_preview_refresh" in src, \
        "_do_font_size_preview_update must call on_tiktok_preview_refresh to update TikTok preview"


def test_font_size_handler_does_not_call_tiktok_preview_directly():
    """Font size handler must NOT call on_tiktok_preview_refresh directly (deferred via debounce)."""
    src = _get_method_source("on_caption_font_size_changed")
    assert "on_tiktok_preview_refresh" not in src, \
        "on_caption_font_size_changed must not call on_tiktok_preview_refresh directly (deferred)"


# ── Caption Position Debounce Tests ─────────────────────────────

def test_caption_position_handler_does_not_call_update_idletasks():
    """Caption position handler must NOT call update_idletasks() (causes UI freeze)."""
    src = _get_method_source("on_caption_position_changed")
    assert "update_idletasks" not in src, \
        "on_caption_position_changed must not call update_idletasks()"


def test_caption_position_handler_uses_debounce():
    """Caption position handler must use after_cancel + after for debounce."""
    src = _get_method_source("on_caption_position_changed")
    assert "after_cancel" in src, \
        "on_caption_position_changed must use after_cancel for debounce"
    assert "self.after(" in src, \
        "on_caption_position_changed must use self.after() for debounce scheduling"


def test_caption_position_deferred_method_exists():
    """Deferred caption position preview update method must exist."""
    src = _get_full_source()
    assert "def _do_caption_position_update(self)" in src, \
        "TikTokApp must have _do_caption_position_update method"


def test_caption_position_handler_does_not_call_tiktok_preview_directly():
    """Caption position handler must NOT call on_tiktok_preview_refresh directly (slow)."""
    src = _get_method_source("on_caption_position_changed")
    assert "on_tiktok_preview_refresh" not in src, \
        "on_caption_position_changed must not call on_tiktok_preview_refresh directly (deferred)"


def test_caption_position_deferred_calls_tiktok_preview():
    """Deferred position update must call on_tiktok_preview_refresh."""
    src = _get_method_source("_do_caption_position_update")
    assert "on_tiktok_preview_refresh" in src, \
        "_do_caption_position_update must call on_tiktok_preview_refresh"


# ── Spinbox Debounce Tests ──────────────────────────────────────

def test_spinbox_handler_does_not_call_update_idletasks():
    """Spinbox handler must NOT call update_idletasks() (causes UI freeze)."""
    src = _get_method_source("_on_caption_y_spinbox_changed")
    assert "update_idletasks" not in src, \
        "_on_caption_y_spinbox_changed must not call update_idletasks()"


def test_spinbox_handler_uses_debounce():
    """Spinbox handler must use debounce pattern (shared with slider)."""
    src = _get_method_source("_on_caption_y_spinbox_changed")
    assert "after_cancel" in src, \
        "_on_caption_y_spinbox_changed must use after_cancel for debounce"
    assert "self.after(" in src, \
        "_on_caption_y_spinbox_changed must use self.after() for scheduling"


def test_spinbox_shares_debounce_with_slider():
    """Spinbox and slider must share the same debounce ID (_caption_pos_debounce_id)."""
    src_spinbox = _get_method_source("_on_caption_y_spinbox_changed")
    src_slider = _get_method_source("on_caption_position_changed")
    assert "_caption_pos_debounce_id" in src_spinbox, \
        "Spinbox must use _caption_pos_debounce_id (shared with slider)"
    assert "_caption_pos_debounce_id" in src_slider, \
        "Slider must use _caption_pos_debounce_id (shared with spinbox)"


def test_spinbox_does_not_call_tiktok_preview_directly():
    """Spinbox handler must NOT call on_tiktok_preview_refresh directly."""
    src = _get_method_source("_on_caption_y_spinbox_changed")
    assert "on_tiktok_preview_refresh" not in src, \
        "_on_caption_y_spinbox_changed must not call on_tiktok_preview_refresh directly"

