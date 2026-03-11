#!/usr/bin/env python3
"""
Tests for TikTok preview error handling.
Validates that on_tiktok_preview_refresh handles corrupt/unreadable video files
gracefully with try/finally instead of crashing with an unhandled OSError.
"""


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_preview_has_try_finally_for_video_clip():
    """on_tiktok_preview_refresh must use try/finally to close VideoFileClip.
    Without this, corrupt videos cause OSError and leak file handles."""
    source = _load_source()
    lines = source.splitlines()

    in_preview_fn = False
    found_video_clip_init = False
    found_finally = False
    found_close = False
    for i, line in enumerate(lines):
        if "def on_tiktok_preview_refresh" in line:
            in_preview_fn = True
        elif in_preview_fn and not line.startswith(" ") and line.strip().startswith("def "):
            break
        if in_preview_fn:
            if "video_clip = None" in line:
                found_video_clip_init = True
            if "finally:" in line:
                found_finally = True
            if "video_clip.close()" in line:
                found_close = True

    assert found_video_clip_init, "on_tiktok_preview_refresh must initialize video_clip = None before try"
    assert found_finally, "on_tiktok_preview_refresh must have finally block to close clip"
    assert found_close, "on_tiktok_preview_refresh must call video_clip.close() in finally"
    print("✓ on_tiktok_preview_refresh uses try/finally for safe clip cleanup")


def test_preview_catches_oserror():
    """on_tiktok_preview_refresh must catch OSError from VideoFileClip.
    This is the specific error thrown when MoviePy can't read the first frame."""
    source = _load_source()
    lines = source.splitlines()

    in_preview_fn = False
    found_oserror_catch = False
    for i, line in enumerate(lines):
        if "def on_tiktok_preview_refresh" in line:
            in_preview_fn = True
        elif in_preview_fn and not line.startswith(" ") and line.strip().startswith("def "):
            break
        if in_preview_fn and "OSError" in line and "except" in line:
            found_oserror_catch = True

    assert found_oserror_catch, (
        "on_tiktok_preview_refresh must catch OSError (MoviePy's error for unreadable videos)"
    )
    print("✓ on_tiktok_preview_refresh catches OSError for corrupt videos")


def test_preview_returns_early_on_error():
    """on_tiktok_preview_refresh must return early when video can't be read.
    This prevents downstream errors from accessing undefined 'frame' variable."""
    source = _load_source()
    lines = source.splitlines()

    in_preview_fn = False
    found_except_return = False
    in_except_block = False
    for i, line in enumerate(lines):
        if "def on_tiktok_preview_refresh" in line:
            in_preview_fn = True
        elif in_preview_fn and not line.startswith(" ") and line.strip().startswith("def "):
            break
        if in_preview_fn:
            stripped = line.strip()
            if "except" in stripped and "OSError" in stripped:
                in_except_block = True
            if in_except_block and stripped == "return":
                found_except_return = True
                break

    assert found_except_return, (
        "on_tiktok_preview_refresh must return early after catching video read error"
    )
    print("✓ on_tiktok_preview_refresh returns early on video read error")


def test_preview_logs_user_friendly_message():
    """on_tiktok_preview_refresh must log a user-friendly message when video is unreadable."""
    source = _load_source()
    lines = source.splitlines()

    in_preview_fn = False
    found_log_message = False
    for i, line in enumerate(lines):
        if "def on_tiktok_preview_refresh" in line:
            in_preview_fn = True
        elif in_preview_fn and not line.startswith(" ") and line.strip().startswith("def "):
            break
        if in_preview_fn and "Cannot read video" in line:
            found_log_message = True

    assert found_log_message, (
        "on_tiktok_preview_refresh must show user-friendly 'Cannot read video' message"
    )
    print("✓ on_tiktok_preview_refresh logs user-friendly error message")


def test_extract_and_scale_frame_uses_try_finally():
    """extract_and_scale_frame must use try/finally to close clip even when get_frame fails.
    Without this, a corrupt video leaks a file handle."""
    source = _load_source()
    lines = source.splitlines()

    in_fn = False
    found_try = False
    found_finally = False
    found_close = False
    for i, line in enumerate(lines):
        if "def extract_and_scale_frame" in line:
            in_fn = True
        elif in_fn and not line.startswith(" ") and line.strip().startswith("def "):
            break
        if in_fn:
            if "try:" in line.strip():
                found_try = True
            if "finally:" in line.strip():
                found_finally = True
            if "clip.close()" in line:
                found_close = True

    assert found_try, "extract_and_scale_frame must have try block around get_frame"
    assert found_finally, "extract_and_scale_frame must have finally block to close clip"
    assert found_close, "extract_and_scale_frame must call clip.close() in finally"
    print("✓ extract_and_scale_frame uses try/finally for safe clip cleanup")


def test_browse_video_uses_ffprobe_fallback():
    """browse_video must fall back to ffprobe for duration when VideoFileClip fails.
    Without this, a corrupt video causes a second VideoFileClip crash."""
    source = _load_source()
    lines = source.splitlines()

    in_fn = False
    found_ffprobe = False
    found_no_double_vfc = True
    in_except_block = False
    for i, line in enumerate(lines):
        if "def browse_video" in line:
            in_fn = True
        elif in_fn and line.strip().startswith("def ") and not line.startswith(" " * 4 + " "):
            break
        if in_fn:
            stripped = line.strip()
            if "except" in stripped:
                in_except_block = True
            if in_except_block and "ffprobe" in line:
                found_ffprobe = True
            # Check there's no second VideoFileClip in the except handler
            if in_except_block and "VideoFileClip(path)" in line and "self._preview_clip" not in line:
                found_no_double_vfc = False

    assert found_ffprobe, (
        "browse_video must use ffprobe as fallback when VideoFileClip fails"
    )
    assert found_no_double_vfc, (
        "browse_video must NOT retry VideoFileClip in the except handler (use ffprobe instead)"
    )
    print("✓ browse_video uses ffprobe fallback for corrupt videos")


if __name__ == "__main__":
    test_preview_has_try_finally_for_video_clip()
    test_preview_catches_oserror()
    test_preview_returns_early_on_error()
    test_preview_logs_user_friendly_message()
    test_extract_and_scale_frame_uses_try_finally()
    test_browse_video_uses_ffprobe_fallback()
    print("\n" + "=" * 60)
    print("✓ ALL 6 TESTS PASSED - Preview error handling verified!")
    print("=" * 60)
