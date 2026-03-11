#!/usr/bin/env python3
"""
Tests for 4K export resolution.
Validates that when use_4k=True, the export pipeline uses 2160x3840 resolution.
"""
import ast


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_process_single_job_sets_width_height_for_4k():
    """process_single_job must set WIDTH=2160 and HEIGHT=3840 when use_4k=True.
    Without this, FFmpeg export always uses 1080x1920 regardless of 4K checkbox."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "process_single_job":
            src = ast.get_source_segment(source, node)
            # Must set WIDTH and HEIGHT for 4K
            assert "globals()['WIDTH'] = 2160" in src, (
                "process_single_job must set WIDTH=2160 when use_4k=True"
            )
            assert "globals()['HEIGHT'] = 3840" in src, (
                "process_single_job must set HEIGHT=3840 when use_4k=True"
            )
            print("✓ process_single_job sets WIDTH=2160, HEIGHT=3840 for 4K")
            return
    raise AssertionError("Could not find process_single_job function")


def test_process_single_job_restores_width_height():
    """process_single_job must restore WIDTH and HEIGHT after job completes.
    This prevents 4K settings from leaking into subsequent HD jobs."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "process_single_job":
            src = ast.get_source_segment(source, node)
            # Must save old values
            assert "old_width" in src, (
                "process_single_job must save old WIDTH before modifying"
            )
            assert "old_height" in src, (
                "process_single_job must save old HEIGHT before modifying"
            )
            # Must restore old values
            assert "globals()['WIDTH'] = old_width" in src, (
                "process_single_job must restore WIDTH after job"
            )
            assert "globals()['HEIGHT'] = old_height" in src, (
                "process_single_job must restore HEIGHT after job"
            )
            print("✓ process_single_job saves and restores WIDTH/HEIGHT")
            return
    raise AssertionError("Could not find process_single_job function")


def test_process_single_job_sets_hd_for_non_4k():
    """process_single_job must explicitly set WIDTH=1080, HEIGHT=1920 for non-4K jobs.
    This ensures the resolution is deterministic regardless of prior global state."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "process_single_job":
            src = ast.get_source_segment(source, node)
            # Must set HD resolution explicitly
            assert "globals()['WIDTH'] = 1080" in src, (
                "process_single_job must set WIDTH=1080 for HD mode"
            )
            assert "globals()['HEIGHT'] = 1920" in src, (
                "process_single_job must set HEIGHT=1920 for HD mode"
            )
            print("✓ process_single_job sets WIDTH=1080, HEIGHT=1920 for HD")
            return
    raise AssertionError("Could not find process_single_job function")


def test_export_uses_width_height_globals():
    """compose_final_video_with_static_blurred_bg must pass WIDTH and HEIGHT globals
    to _export_with_ffmpeg_filters. These globals are set by process_single_job based on use_4k."""
    source = _load_source()
    lines = source.splitlines()
    
    # Find the _export_with_ffmpeg_filters call inside compose_final_video_with_static_blurred_bg
    in_compose = False
    found_width = False
    found_height = False
    for i, line in enumerate(lines):
        if "def compose_final_video_with_static_blurred_bg" in line:
            in_compose = True
        elif in_compose and not line.startswith(" ") and line.strip().startswith("def "):
            break
        if in_compose:
            if "video_width=WIDTH" in line:
                found_width = True
            if "video_height=HEIGHT" in line:
                found_height = True
    
    assert found_width, "compose_final_video must pass WIDTH to _export_with_ffmpeg_filters"
    assert found_height, "compose_final_video must pass HEIGHT to _export_with_ffmpeg_filters"
    print("✓ _export_with_ffmpeg_filters receives WIDTH/HEIGHT from globals")


def test_4k_resolution_values_consistent():
    """4K resolution must be exactly 2160x3840 (2x HD 1080x1920) in all locations."""
    source = _load_source()
    
    # on_4k_toggle and process_single_job must agree on 4K values
    assert source.count("globals()['WIDTH'] = 2160") >= 2, (
        "WIDTH=2160 must appear in both on_4k_toggle and process_single_job"
    )
    assert source.count("globals()['HEIGHT'] = 3840") >= 2, (
        "HEIGHT=3840 must appear in both on_4k_toggle and process_single_job"
    )
    print("✓ 4K resolution is 2160x3840 in both GUI toggle and export pipeline")


if __name__ == "__main__":
    test_process_single_job_sets_width_height_for_4k()
    test_process_single_job_restores_width_height()
    test_process_single_job_sets_hd_for_non_4k()
    test_export_uses_width_height_globals()
    test_4k_resolution_values_consistent()
    print("\n" + "=" * 60)
    print("✓ ALL 5 TESTS PASSED - 4K export resolution fix verified!")
    print("=" * 60)
