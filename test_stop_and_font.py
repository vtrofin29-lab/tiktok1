"""Tests for stop button FFmpeg killing and 4K font size safety."""
import os
import sys
import re
import threading


def test_active_ffmpeg_proc_global_exists():
    """_active_ffmpeg_proc and _active_ffmpeg_lock globals must exist."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    assert '_active_ffmpeg_proc' in source, "_active_ffmpeg_proc global should exist"
    assert '_active_ffmpeg_lock' in source, "_active_ffmpeg_lock global should exist"


def test_run_ffmpeg_with_stop_check_function_exists():
    """_run_ffmpeg_with_stop_check helper function must be defined."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    assert 'def _run_ffmpeg_with_stop_check(' in source, \
        "_run_ffmpeg_with_stop_check function should be defined"


def test_bg_prerender_uses_stop_check():
    """Background pre-render (Pass 1) must use _run_ffmpeg_with_stop_check, not subprocess.run."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find the bg pre-render section by looking for the bg_result assignment
    bg_section_start = source.find("bg_result = _run_ffmpeg_with_stop_check(")
    assert bg_section_start != -1, \
        "Background pre-render should use _run_ffmpeg_with_stop_check (bg_result = _run_ffmpeg_with_stop_check(...))"


def test_final_encode_uses_stop_check():
    """Final encode (Pass 2) must use _run_ffmpeg_with_stop_check, not subprocess.run."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find the final encode result assignment
    final_result = source.find("result = _run_ffmpeg_with_stop_check(")
    assert final_result != -1, \
        "Final encode should use _run_ffmpeg_with_stop_check (result = _run_ffmpeg_with_stop_check(...))"


def test_stop_queue_kills_ffmpeg_proc():
    """stop_queue method must attempt to kill _active_ffmpeg_proc."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find stop_queue method
    stop_start = source.find("def stop_queue(self):")
    stop_end = source.find("\n    def ", stop_start + 1)
    stop_method = source[stop_start:stop_end]
    
    assert 'proc.kill()' in stop_method or '_active_ffmpeg_proc' in stop_method, \
        "stop_queue should kill the active FFmpeg process"
    assert '_queue_stop_event.set()' in stop_method, \
        "stop_queue should set the stop event"


def test_stop_check_between_passes():
    """There should be a stop event check between Pass 1 and Pass 2."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find the region between pass 1 completion and pass 2 start
    pass1_done = source.find("Background pre-rendered successfully")
    pass2_start = source.find("Pass 2: Final encode", pass1_done)
    between_passes = source[pass1_done:pass2_start]
    
    assert '_queue_stop_event.is_set()' in between_passes, \
        "Stop event should be checked between Pass 1 and Pass 2"


def test_export_early_abort_on_stop():
    """_export_with_ffmpeg_filters should check stop event at start."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find the export function
    export_start = source.find("def _export_with_ffmpeg_filters(")
    export_body_start = source.find("try:", export_start)
    # Get first 500 chars of try block
    early_body = source[export_body_start:export_body_start + 500]
    
    assert '_queue_stop_event.is_set()' in early_body, \
        "_export_with_ffmpeg_filters should check stop event early in the function"


def test_process_single_job_syncs_font_globals_for_4k():
    """process_single_job should sync CAPTION_FONT_SIZE global when use_4k=True."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find the process_single_job function up to its first try block
    func_start = source.find("def process_single_job(")
    func_try = source.find("\n    try:", func_start)
    func_body = source[func_start:func_try]
    
    # Check that CAPTION_FONT_SIZE is set for 4K mode
    assert "CAPTION_FONT_SIZE" in func_body, \
        "process_single_job should sync CAPTION_FONT_SIZE global for 4K mode"


def test_process_single_job_restores_font_globals():
    """process_single_job should restore CAPTION_FONT_SIZE after job completes."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    # Find the restore section
    restore_section = source.find("old_caption_font_size")
    assert restore_section != -1, \
        "process_single_job should save old_caption_font_size for restoration"
    
    # Check restore in finally block
    finally_start = source.rfind("finally:", 0, restore_section + 2000)
    if finally_start == -1:
        # Look after the save
        finally_start = source.find("CAPTION_FONT_SIZE'] = old_caption_font_size", restore_section)
    assert source.find("old_caption_font_size", restore_section + 1) != -1, \
        "CAPTION_FONT_SIZE should be restored from old_caption_font_size"


def test_no_subprocess_run_for_main_ffmpeg():
    """Main FFmpeg calls (bg render + final encode) should NOT use blocking subprocess.run."""
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # Find the _export_with_ffmpeg_filters function
    func_start = source.find("def _export_with_ffmpeg_filters(")
    func_end = source.find("\ndef ", func_start + 1)
    func_body = source[func_start:func_end]
    
    # Count subprocess.run calls — only probing calls should use subprocess.run
    # The main bg_render and final_encode should use _run_ffmpeg_with_stop_check
    run_calls = [m.start() for m in re.finditer(r'subprocess\.run\(', func_body)]
    stop_check_calls = [m.start() for m in re.finditer(r'_run_ffmpeg_with_stop_check\(', func_body)]
    
    assert len(stop_check_calls) >= 2, \
        f"Expected at least 2 _run_ffmpeg_with_stop_check calls (bg+final), found {len(stop_check_calls)}"


if __name__ == "__main__":
    tests = [
        test_active_ffmpeg_proc_global_exists,
        test_run_ffmpeg_with_stop_check_function_exists,
        test_bg_prerender_uses_stop_check,
        test_final_encode_uses_stop_check,
        test_stop_queue_kills_ffmpeg_proc,
        test_stop_check_between_passes,
        test_export_early_abort_on_stop,
        test_process_single_job_syncs_font_globals_for_4k,
        test_process_single_job_restores_font_globals,
        test_no_subprocess_run_for_main_ffmpeg,
    ]
    
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            print(f"  ✓ {test.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {test.__name__}: {e}")
            failed += 1
        except Exception as e:
            print(f"  ✗ {test.__name__}: EXCEPTION: {e}")
            failed += 1
    
    print(f"\n{'=' * 60}")
    print(f"Results: {passed}/{passed + failed} passed")
    if failed:
        sys.exit(1)
    print("All tests passed!")
