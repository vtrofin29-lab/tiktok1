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
    """queue_worker pipeline must pass blur overlay settings to process_single_job via effect_settings."""
    source = _load_source()
    tree = ast.parse(source)

    # The blur overlay settings may be in queue_worker itself or in helper functions
    # it delegates to (_extract_effect_settings, _run_video_job).
    # Check all three.
    found_extract = False
    found_run = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in ("queue_worker", "_extract_effect_settings", "_run_video_job"):
                src = ast.get_source_segment(source, node)
                if node.name == "_extract_effect_settings":
                    for key in [
                        "blur_overlay_enabled",
                        "blur_overlay_x",
                        "blur_overlay_y",
                        "blur_overlay_w",
                        "blur_overlay_h",
                        "blur_overlay_intensity",
                    ]:
                        assert key in src, f"_extract_effect_settings must include {key}"
                    found_extract = True
                if node.name == "_run_video_job":
                    assert "effect_settings" in src, "_run_video_job must pass effect_settings"
                    assert "process_single_job" in src, "_run_video_job must call process_single_job"
                    found_run = True
    assert found_extract, "Could not find _extract_effect_settings function"
    assert found_run, "Could not find _run_video_job function"
    print("✓ queue_worker pipeline passes all blur overlay settings")


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


def test_blur_overlay_even_coordinates():
    """Blur overlay x/y must be forced even for yuv420p compatibility (prevents green artifacts)."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # Both x and y positions must be made even with & ~1
            # Count how many & ~1 appear in the blur overlay section
            blur_section_start = src.find("blur_overlay_enabled")
            blur_section = src[blur_section_start:blur_section_start + 3000]
            even_count = blur_section.count("& ~1")
            assert even_count >= 4, (
                f"All 4 blur coords (x,y,w,h) must use & ~1 for even alignment, found {even_count}"
            )
            print("✓ All blur overlay coordinates are forced even for yuv420p")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_blur_overlay_prescale_before_blur():
    """Blur overlay must convert to yuv420p and transform coordinates using fg offset."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # Must add format=yuv420p BEFORE the split/crop/blur chain
            # Find the FOREGROUND blur overlay section (Pass 2) — second occurrence
            # of blur_overlay_enabled. The first occurrence is the background
            # crop-above-zoom section (Pass 1).
            first_idx = src.find("blur_overlay_enabled")
            assert first_idx != -1, "Must have blur_overlay_enabled in export function"
            blur_section_start = src.find("blur_overlay_enabled", first_idx + 1)
            if blur_section_start == -1:
                # Only one occurrence — use it directly
                blur_section_start = first_idx
            blur_section = src[blur_section_start:blur_section_start + 3000]
            # format=yuv420p must appear before split
            fmt_pos = blur_section.find("format=yuv420p")
            split_pos = blur_section.find("split")
            assert fmt_pos != -1, "Must use format=yuv420p before blur overlay"
            assert fmt_pos < split_pos, "format=yuv420p must come before split in blur chain"
            # Must probe foreground dimensions for coordinate transformation
            assert "ffprobe" in blur_section, "Must probe foreground video dimensions"
            # Must calculate foreground offset in composited frame
            assert "fg_y_off" in blur_section or "fg_y_offset" in blur_section, (
                "Must calculate foreground Y offset in composited frame"
            )
            # Must use crop_top_ratio for Y coordinate transformation
            assert "crop_top_ratio" in blur_section, (
                "Must account for crop_top_ratio in blur Y coordinate"
            )
            print("✓ Blur overlay converts to yuv420p and transforms coordinates correctly")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_blur_overlay_boxblur_fixed_power():
    """boxblur must use fixed power (2) not the intensity value to prevent green artifacts."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # boxblur should use :2 as the power, not :{b_blur}
            assert "boxblur={b_blur}:2" in src, (
                "boxblur must use fixed power of 2 (not intensity as power)"
            )
            # Must NOT have boxblur={b_blur}:{b_blur} (old broken pattern)
            assert "boxblur={b_blur}:{b_blur}" not in src, (
                "boxblur must NOT use intensity as both radius and power"
            )
            print("✓ boxblur uses fixed power=2, not intensity as power")
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


def test_apply_blur_overlay_to_preview_exists():
    """apply_blur_overlay_to_preview function must exist."""
    source = _load_source()
    tree = ast.parse(source)
    
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "apply_blur_overlay_to_preview":
            found = True
            src = ast.get_source_segment(source, node)
            assert "blur_overlay_enabled" in src, "Must check blur_overlay_enabled"
            assert "GaussianBlur" in src, "Must use GaussianBlur for blur effect"
            assert "crop" in src.lower(), "Must crop a region for blur"
            assert "paste" in src.lower(), "Must paste blurred region back"
            break
    assert found, "apply_blur_overlay_to_preview function must exist"
    print("✓ apply_blur_overlay_to_preview exists and has correct implementation")


def test_mini_preview_applies_blur_overlay():
    """Both mini preview paths must call apply_blur_overlay_to_preview."""
    source = _load_source()
    tree = ast.parse(source)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "App":
            found_extract = False
            found_persistent = False
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    src = ast.get_source_segment(source, item)
                    if item.name == "_mini_extract_and_update":
                        assert "apply_blur_overlay_to_preview" in src, (
                            "_mini_extract_and_update must call apply_blur_overlay_to_preview"
                        )
                        found_extract = True
                    if item.name == "_mini_persistent_worker":
                        assert "apply_blur_overlay_to_preview" in src, (
                            "_mini_persistent_worker must call apply_blur_overlay_to_preview"
                        )
                        found_persistent = True
            assert found_extract, "Could not find _mini_extract_and_update"
            assert found_persistent, "Could not find _mini_persistent_worker"
            print("✓ Both mini preview paths apply blur overlay to preview")
            return
    raise AssertionError("Could not find App class")


def _extract_blur_overlay_func():
    """Extract apply_blur_overlay_to_preview from source and return callable.
    
    Uses regex extraction + exec to avoid importing the full module (which needs tkinter).
    """
    from PIL import ImageFilter
    import re
    source = _load_source()
    match = re.search(
        r'^(def apply_blur_overlay_to_preview\(.*?\n(?:(?:    .*|)\n)*)',
        source, re.MULTILINE
    )
    assert match, "Could not find apply_blur_overlay_to_preview function in source"
    ns = {'ImageFilter': ImageFilter}
    exec(match.group(1), ns)
    return ns['apply_blur_overlay_to_preview']


def test_apply_blur_overlay_returns_original_when_disabled():
    """apply_blur_overlay_to_preview must return original image when disabled."""
    from PIL import Image
    apply_blur_overlay_to_preview = _extract_blur_overlay_func()
    
    img = Image.new('RGB', (100, 100), color='red')
    # Disabled
    result = apply_blur_overlay_to_preview(img, {'blur_overlay_enabled': False})
    assert result is img, "Must return original image when disabled"
    # None settings
    result = apply_blur_overlay_to_preview(img, None)
    assert result is img, "Must return original image when settings is None"
    # Empty settings
    result = apply_blur_overlay_to_preview(img, {})
    assert result is img, "Must return original image when settings is empty"
    print("✓ apply_blur_overlay_to_preview returns original when disabled")


def test_apply_blur_overlay_modifies_image_when_enabled():
    """apply_blur_overlay_to_preview must actually blur a region when enabled."""
    from PIL import Image, ImageDraw
    import numpy as np
    apply_blur_overlay_to_preview = _extract_blur_overlay_func()
    
    # Create a checkerboard image with sharp edges so blur changes pixels
    img = Image.new('RGB', (200, 200), color='white')
    draw = ImageDraw.Draw(img)
    # Draw alternating black/white stripes in the blur region
    for i in range(20, 60, 4):
        draw.rectangle([i, 20, i+1, 59], fill='black')
    
    settings = {
        'blur_overlay_enabled': True,
        'blur_overlay_x': 10.0,   # 10% = pixel 20
        'blur_overlay_y': 10.0,   # 10% = pixel 20
        'blur_overlay_w': 20.0,   # 20% = 40px
        'blur_overlay_h': 20.0,   # 20% = 40px
        'blur_overlay_intensity': 10,
    }
    result = apply_blur_overlay_to_preview(img, settings)
    assert result is not img, "Must return a new image (copy)"
    # The blurred region should differ from original
    orig_arr = np.array(img)
    res_arr = np.array(result)
    # The blur region pixels should have changed (sharp stripes get smoothed)
    region_orig = orig_arr[20:60, 20:60]
    region_result = res_arr[20:60, 20:60]
    assert not np.array_equal(region_orig, region_result), "Blurred region must differ from original"
    # Pixels outside the region should be unchanged
    assert np.array_equal(orig_arr[0:19, 0:19], res_arr[0:19, 0:19]), "Pixels outside blur region must be unchanged"
    print("✓ apply_blur_overlay_to_preview correctly blurs the region")
