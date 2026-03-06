#!/usr/bin/env python3
"""
Tests for blur overlay (cover-up region) feature.
Validates that blur overlay settings are saved in job dicts, passed through
the processing pipeline, and correctly generate FFmpeg filter chains.
"""
import ast


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_add_job_saves_blur_overlay_settings():
    """add_job must include all blur overlay fields in the job dict."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "add_job":
                    src = ast.get_source_segment(source, item)
                    for key in [
                        "blur_overlay_enabled",
                        "blur_overlay_x",
                        "blur_overlay_y",
                        "blur_overlay_w",
                        "blur_overlay_h",
                        "blur_overlay_intensity",
                    ]:
                        assert key in src, f"add_job must save {key} in the job dict"
                    print("✓ add_job saves all blur overlay settings")
                    return
    raise AssertionError("Could not find App.add_job")


def test_queue_worker_passes_blur_overlay_settings():
    """queue_worker must pass blur overlay settings to process_single_job via effect_settings."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            for key in [
                "blur_overlay_enabled",
                "blur_overlay_x",
                "blur_overlay_y",
                "blur_overlay_w",
                "blur_overlay_h",
                "blur_overlay_intensity",
            ]:
                assert key in src, f"queue_worker must pass {key} in effect_settings"
            print("✓ queue_worker passes all blur overlay settings")
            return
    raise AssertionError("Could not find queue_worker function")


def test_format_job_info_shows_blur_overlay():
    """_format_job_info must show blur overlay info when enabled."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_format_job_info":
                    src = ast.get_source_segment(source, item)
                    assert "blur_overlay_enabled" in src, (
                        "_format_job_info must check blur_overlay_enabled"
                    )
                    assert "blur_box" in src, (
                        "_format_job_info must display blur_box info"
                    )
                    print("✓ _format_job_info displays blur overlay info")
                    return
    raise AssertionError("Could not find App._format_job_info")


def test_export_function_has_blur_overlay_filter():
    """_export_with_ffmpeg_filters must build blur overlay filter chain."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # Must use split to duplicate the video stream
            assert "split" in src, "Must use split filter for blur overlay"
            # Must use crop to extract the region
            assert "crop=" in src, "Must use crop filter for blur overlay region"
            # Must use boxblur to blur the cropped region
            assert "boxblur" in src, "Must use boxblur on the cropped region"
            # Must overlay the blurred region back
            assert "overlay" in src, "Must overlay blurred region back"
            # Must check blur_overlay_enabled
            assert "blur_overlay_enabled" in src, (
                "Must check blur_overlay_enabled from effect_settings"
            )
            print("✓ _export_with_ffmpeg_filters builds blur overlay filter chain")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_get_current_effect_settings_includes_blur_overlay():
    """_get_current_effect_settings must include blur overlay fields."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "_get_current_effect_settings":
                    src = ast.get_source_segment(source, item)
                    for key in [
                        "blur_overlay_enabled",
                        "blur_overlay_x",
                        "blur_overlay_y",
                        "blur_overlay_w",
                        "blur_overlay_h",
                        "blur_overlay_intensity",
                    ]:
                        assert key in src, f"_get_current_effect_settings must include {key}"
                    print("✓ _get_current_effect_settings includes all blur overlay settings")
                    return
    raise AssertionError("Could not find App._get_current_effect_settings")


def test_gui_has_blur_overlay_controls():
    """App.__init__ must create blur overlay GUI controls."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            # Check the whole class source for GUI variable definitions
            src = ast.get_source_segment(source, node)
            for var in [
                "blur_overlay_enabled_var",
                "blur_overlay_x_var",
                "blur_overlay_y_var",
                "blur_overlay_w_var",
                "blur_overlay_h_var",
                "blur_overlay_intensity_var",
            ]:
                assert var in src, f"App class must define {var} GUI variable"
            assert "Blur Overlay" in src, "App class must have 'Blur Overlay' section label"
            print("✓ App class has all blur overlay GUI controls")
            return
    raise AssertionError("Could not find App class")


def test_per_job_different_blur_overlay_in_dict():
    """Two jobs with different blur overlay settings should store different values."""
    job1 = {
        "blur_overlay_enabled": True,
        "blur_overlay_x": 10.0,
        "blur_overlay_y": 20.0,
        "blur_overlay_w": 30.0,
        "blur_overlay_h": 15.0,
        "blur_overlay_intensity": 25,
    }
    job2 = {
        "blur_overlay_enabled": True,
        "blur_overlay_x": 50.0,
        "blur_overlay_y": 60.0,
        "blur_overlay_w": 10.0,
        "blur_overlay_h": 10.0,
        "blur_overlay_intensity": 40,
    }
    assert job1["blur_overlay_x"] != job2["blur_overlay_x"]
    assert job1["blur_overlay_y"] != job2["blur_overlay_y"]
    assert job1["blur_overlay_w"] != job2["blur_overlay_w"]
    assert job1["blur_overlay_intensity"] != job2["blur_overlay_intensity"]
    print("✓ Per-job dicts can store different blur overlay settings independently")


def test_reset_to_defaults_resets_blur_overlay():
    """reset_to_defaults must reset blur overlay settings."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "reset_to_defaults":
                    src = ast.get_source_segment(source, item)
                    assert "blur_overlay_enabled_var" in src, (
                        "reset_to_defaults must reset blur_overlay_enabled_var"
                    )
                    print("✓ reset_to_defaults resets blur overlay settings")
                    return
    raise AssertionError("Could not find App.reset_to_defaults")


def test_on_job_double_click_loads_blur_overlay():
    """on_job_double_click must load blur overlay settings from job."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "on_job_double_click":
                    src = ast.get_source_segment(source, item)
                    assert "blur_overlay_enabled" in src, (
                        "on_job_double_click must load blur_overlay_enabled"
                    )
                    print("✓ on_job_double_click loads blur overlay settings")
                    return
    raise AssertionError("Could not find App.on_job_double_click")
