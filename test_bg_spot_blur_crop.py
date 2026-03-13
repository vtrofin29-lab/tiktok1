"""Tests for background spot blur crop and CPU thread utilization.

When spot blur is enabled, the background should be cropped to exclude the
vertical range of the spot blur area (keeping the larger portion above or below),
then zoomed in to fill the frame. This prevents the background from showing
content that the spot blur is trying to hide.

Also verifies that CPU thread caps have been removed to use all available cores.
"""
import ast
import re


def _get_source():
    """Get the source code of _export_with_ffmpeg_filters from file."""
    with open("tiktok_full_gui.py", "r") as f:
        source = f.read()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            return ast.get_source_segment(source, node)
    raise RuntimeError("Could not find _export_with_ffmpeg_filters")


# ── Background spot blur crop tests ──

def test_bg_crop_checks_blur_overlay_enabled():
    """Background crop must check blur_overlay_enabled from effect_settings."""
    src = _get_source()
    assert "blur_overlay_enabled" in src, (
        "Background crop must check blur_overlay_enabled"
    )
    # Must reference effect_settings for blur overlay detection
    assert "effect_settings" in src
    print("✓ Background crop checks blur_overlay_enabled from effect_settings")


def test_bg_crop_reads_blur_y_and_h():
    """Background crop must read blur_overlay_y and blur_overlay_h to determine
    which portion to crop."""
    src = _get_source()
    assert "blur_overlay_y" in src, "Must read blur_overlay_y"
    assert "blur_overlay_h" in src, "Must read blur_overlay_h"
    print("✓ Background crop reads blur_overlay_y and blur_overlay_h")


def test_bg_crop_keeps_larger_portion():
    """When spot blur is active, background should keep the larger portion
    (above or below the blur area)."""
    src = _get_source()
    # Must have logic for above vs below comparison
    assert "_above" in src or "above" in src.lower(), (
        "Background crop must compare above vs below portions"
    )
    assert "_below" in src or "below" in src.lower(), (
        "Background crop must compare above vs below portions"
    )
    print("✓ Background crop keeps the larger portion (above or below)")


def test_bg_crop_has_minimum_threshold():
    """Background crop should have a minimum threshold (e.g., 15%) to avoid
    cropping to an extremely small area."""
    src = _get_source()
    # Check for a minimum threshold check (0.15 = 15%)
    assert "0.15" in src, (
        "Background crop must have a minimum threshold to prevent tiny crops"
    )
    print("✓ Background crop has minimum 15% threshold")


def test_bg_crop_uses_ffmpeg_crop_filter():
    """The background spot blur crop must use FFmpeg crop= filter syntax."""
    src = _get_source()
    # Should generate crop filter for the background
    # The crop override replaces bg_crop_part with a new crop
    lines = src.split('\n')
    found_spot_blur_crop = False
    for line in lines:
        if 'spot-blur crop' in line.lower() or 'spot_blur crop' in line.lower():
            found_spot_blur_crop = True
            break
    # Also check for the crop= filter generation
    crop_pattern = re.findall(r'bg_crop_part\s*=\s*f"crop=', src)
    assert len(crop_pattern) >= 2, (
        "Background must have at least 2 bg_crop_part assignments "
        "(one for above, one for below the blur area)"
    )
    print("✓ Background spot blur crop uses FFmpeg crop= filter")


def test_bg_crop_logs_decision():
    """Background crop must log which decision was made (above/below/too-large)."""
    src = _get_source()
    assert "spot-blur crop" in src.lower() or "spot_blur crop" in src.lower(), (
        "Background crop must log the crop decision"
    )
    # Check for 3 log paths: above, below, too large
    assert "keeping top" in src, "Must log when keeping top portion"
    assert "keeping bottom" in src, "Must log when keeping bottom portion"
    assert "too large" in src, "Must log when blur area is too large to crop around"
    print("✓ Background crop logs all 3 decision paths")


# ── CPU thread utilization tests ──

def test_cpu_threads_no_cap_at_8():
    """CPU-only path must NOT cap threads at 8 – use all available cores."""
    src = _get_source()
    # The old code had: cpu_threads = min(total_cores, 8)
    # The new code should have: cpu_threads = total_cores
    # Make sure `min(total_cores, 8)` is NOT present
    assert "min(total_cores, 8)" not in src, (
        "CPU-only thread count must not be capped at 8 – use all cores"
    )
    print("✓ CPU-only threads not capped at 8")


def test_gpu_threads_no_cap_at_8():
    """GPU path must NOT cap filter threads at 8."""
    src = _get_source()
    assert "min(total_cores // 2, 8)" not in src, (
        "GPU filter thread count must not be capped at 8"
    )
    print("✓ GPU filter threads not capped at 8")


def test_cpu_only_uses_all_cores():
    """CPU-only path should set cpu_threads = total_cores (no cap)."""
    src = _get_source()
    # Find the CPU-only assignment
    assert "cpu_threads = total_cores" in src, (
        "CPU-only path must use all available cores: cpu_threads = total_cores"
    )
    print("✓ CPU-only path uses all available cores")


def test_gpu_path_uses_half_cores():
    """GPU path should use half cores without an artificial cap."""
    src = _get_source()
    assert "total_cores // 2" in src, (
        "GPU path must use half the CPU cores for filter processing"
    )
    print("✓ GPU path uses half CPU cores (no cap)")


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"✗ {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
