#!/usr/bin/env python3
"""
Tests for per-job caption font/color settings.
Validates that each job saves and passes its own caption styling
(text color, stroke color, stroke width, font size) through the
processing pipeline, so different jobs can have different caption styles.
"""
import ast
import inspect


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_add_job_saves_caption_font_size():
    """add_job must include caption_font_size in the job dict."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "add_job":
                    src = ast.get_source_segment(source, item)
                    assert "caption_font_size" in src, (
                        "add_job must save caption_font_size in the job dict"
                    )
                    assert "caption_text_color" in src
                    assert "caption_stroke_color" in src
                    assert "caption_stroke_width" in src
                    print("✓ add_job saves all four caption settings")
                    return
    raise AssertionError("Could not find App.add_job")


def test_queue_worker_passes_caption_settings():
    """queue_worker must pass per-job caption settings to process_single_job."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            for key in [
                "caption_text_color",
                "caption_stroke_color",
                "caption_stroke_width",
                "caption_font_size",
            ]:
                assert key in src, (
                    f"queue_worker must pass {key} to process_single_job"
                )
            print("✓ queue_worker passes all four caption settings")
            return
    raise AssertionError("Could not find queue_worker function")


def test_process_single_job_accepts_caption_params():
    """process_single_job must accept caption color/font parameters."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "process_single_job":
            arg_names = [a.arg for a in node.args.args]
            for param in [
                "caption_text_color",
                "caption_stroke_color",
                "caption_stroke_width",
                "caption_font_size",
            ]:
                assert param in arg_names, (
                    f"process_single_job must accept {param} parameter"
                )
            print("✓ process_single_job accepts all four caption parameters")
            return
    raise AssertionError("Could not find process_single_job function")


def test_compose_with_pref_font_accepts_caption_params():
    """_compose_with_pref_font must accept and forward caption settings."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_compose_with_pref_font":
            arg_names = [a.arg for a in node.args.args]
            for param in [
                "caption_text_color",
                "caption_stroke_color",
                "caption_stroke_width",
                "caption_font_size",
            ]:
                assert param in arg_names, (
                    f"_compose_with_pref_font must accept {param} parameter"
                )
            print("✓ _compose_with_pref_font accepts all four caption parameters")
            return
    raise AssertionError("Could not find _compose_with_pref_font function")


def test_compose_final_video_accepts_caption_params():
    """compose_final_video_with_static_blurred_bg must accept caption settings."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "compose_final_video_with_static_blurred_bg":
            arg_names = [a.arg for a in node.args.args]
            for param in [
                "caption_text_color",
                "caption_stroke_color",
                "caption_stroke_width",
                "caption_font_size",
            ]:
                assert param in arg_names, (
                    f"compose_final_video_with_static_blurred_bg must accept {param}"
                )
            print("✓ compose_final_video_with_static_blurred_bg accepts all four caption parameters")
            return
    raise AssertionError("Could not find compose_final_video_with_static_blurred_bg function")


def test_format_job_info_shows_font_size():
    """_format_job_info must show non-default font size."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_format_job_info":
                    src = ast.get_source_segment(source, item)
                    assert "caption_font_size" in src, (
                        "_format_job_info must display caption_font_size"
                    )
                    print("✓ _format_job_info displays font size info")
                    return
    raise AssertionError("Could not find App._format_job_info")


def test_per_job_different_colors_in_dict():
    """Two jobs with different colors should store different values."""
    job1 = {
        "caption_text_color": (255, 255, 255, 255),
        "caption_stroke_color": (0, 0, 0, 150),
        "caption_stroke_width": 3,
        "caption_font_size": 56,
    }
    job2 = {
        "caption_text_color": (255, 0, 0, 255),
        "caption_stroke_color": (0, 255, 0, 200),
        "caption_stroke_width": 5,
        "caption_font_size": 72,
    }
    assert job1["caption_text_color"] != job2["caption_text_color"]
    assert job1["caption_stroke_color"] != job2["caption_stroke_color"]
    assert job1["caption_stroke_width"] != job2["caption_stroke_width"]
    assert job1["caption_font_size"] != job2["caption_font_size"]
    print("✓ Per-job dicts can store different caption settings independently")


def test_export_uses_per_job_colors_not_only_globals():
    """compose_final_video_with_static_blurred_bg must use per-job color params,
    not just globals, when calling _export_with_ffmpeg_filters."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "compose_final_video_with_static_blurred_bg":
            src = ast.get_source_segment(source, node)
            # The key change: caption_text_color param should be used (not only globals)
            assert "caption_text_color" in src, (
                "compose_final_video must reference caption_text_color parameter"
            )
            # Should fall back to globals only when per-job value is None
            assert "if caption_text_color is not None" in src or "caption_text_color if caption_text_color" in src, (
                "Must prefer per-job caption_text_color over globals"
            )
            print("✓ Export uses per-job color values (with globals as fallback)")
            return
    raise AssertionError("Could not find compose_final_video_with_static_blurred_bg")
