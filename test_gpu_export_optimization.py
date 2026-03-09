#!/usr/bin/env python3
"""
Tests for GPU export optimization.
Validates that FFmpeg export uses GPU correctly:
- No -hwaccel cuda for CPU filter paths (avoids GPU→CPU transfer overhead)
- filter_threads for CPU filter parallelism
- PyTorch cu130 URL suggested for RTX 5070+ in error messages
"""
import ast


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_pass2_no_hwaccel_for_cpu_overlay():
    """Pass 2 must NOT use -hwaccel cuda when filter chain is CPU-based (captions/overlay).
    GPU decoding with CPU filters forces costly GPU→CPU transfer per frame."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # The hwaccel cuda for Pass 2 must be conditioned on use_gpu_overlay
            assert "use_gpu_overlay" in src, (
                "_export_with_ffmpeg_filters must reference use_gpu_overlay"
            )
            # Must NOT blindly add -hwaccel cuda when use_gpu is True
            # Check that hwaccel cuda is gated on use_gpu_overlay, not just use_gpu
            assert "use_gpu and USE_HARDWARE_DECODING and use_gpu_overlay" in src, (
                "Pass 2 -hwaccel cuda must be conditioned on use_gpu_overlay (not just use_gpu)"
            )
            print("✓ Pass 2 only uses -hwaccel cuda with GPU overlay")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_pass1_hwaccel_gated_on_gpu_filters():
    """Pass 1 must only use -hwaccel cuda when GPU filters (scale_cuda) are active."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # Must check gpu_filters before adding hwaccel
            assert "gpu_filters and not needs_stream_loop" in src, (
                "Pass 1 -hwaccel cuda must be gated on gpu_filters"
            )
            print("✓ Pass 1 gates -hwaccel cuda on gpu_filters")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_filter_threads_for_cpu_path():
    """CPU filter paths must use -filter_threads for parallel processing."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            assert "filter_threads" in src, (
                "_export_with_ffmpeg_filters must use filter_threads for CPU paths"
            )
            assert "filter_complex_threads" in src, (
                "_export_with_ffmpeg_filters must use filter_complex_threads for CPU paths"
            )
            print("✓ CPU filter paths use -filter_threads")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_pytorch_cu130_in_whisper_error_messages():
    """Whisper error messages must suggest cu130 nightly for RTX 5070+."""
    source = _load_source()
    # Check that cu130 URL appears in the whisper error guidance
    assert "whl/nightly/cu130" in source, (
        "PyTorch cu130 nightly URL must be in whisper error messages"
    )
    # Must NOT only suggest old cu118 without also suggesting cu130
    # Find the whisper section error messages
    idx_cu130 = source.find("whl/nightly/cu130")
    assert idx_cu130 > 0, "Must reference cu130 nightly URL"
    print("✓ Whisper error messages include cu130 nightly for RTX 5070+")


def test_pytorch_cu130_in_requirements():
    """requirements.txt must have cu130 nightly URL for RTX 5070+."""
    with open("requirements.txt", "r") as f:
        content = f.read()
    assert "whl/nightly/cu130" in content, (
        "requirements.txt must include cu130 nightly URL for RTX 5070+"
    )
    print("✓ requirements.txt includes cu130 nightly URL")


def test_nvenc_preset_is_p1_fastest():
    """NVENC preset must be p1 (fastest) for maximum export speed."""
    source = _load_source()
    assert 'NVENC_PRESET_SPEED = "p1"' in source, (
        "NVENC_PRESET_SPEED must be p1 (fastest preset)"
    )
    print("✓ NVENC preset is p1 (fastest)")


def test_get_export_settings_exists():
    """get_export_settings must return GPU settings when available."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "get_export_settings":
            src = ast.get_source_segment(source, node)
            assert "nvenc" in src.lower() or "NVENC" in src or "h264_nvenc" in src, (
                "get_export_settings must reference NVENC"
            )
            assert "libx264" in src, (
                "get_export_settings must have libx264 fallback"
            )
            print("✓ get_export_settings has GPU/CPU paths")
            return
    raise AssertionError("Could not find get_export_settings function")


def test_hybrid_gpu_overlay_with_captions():
    """When captions are present and GPU filters available, use hybrid GPU pipeline:
    overlay_cuda for bg+fg composite, then hwdownload for CPU caption burn-in."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # Must have use_gpu_hybrid variable for hybrid GPU pipeline
            assert "use_gpu_hybrid" in src, (
                "_export_with_ffmpeg_filters must define use_gpu_hybrid for hybrid GPU pipeline"
            )
            # Hybrid must use overlay_cuda + hwdownload
            assert "overlay_cuda" in src, (
                "Hybrid GPU pipeline must use overlay_cuda"
            )
            assert "hwdownload" in src, (
                "Hybrid GPU pipeline must hwdownload after overlay_cuda for CPU captions"
            )
            # Hybrid pipeline must be conditioned on gpu_filters AND has_captions
            assert "gpu_filters and has_captions" in src, (
                "use_gpu_hybrid must be True when gpu_filters available AND captions present"
            )
            print("✓ Hybrid GPU pipeline: overlay_cuda → hwdownload → CPU captions")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")


def test_pass1_filter_threads_always():
    """Pass 1 must use -filter_threads for ALL paths (GPU and CPU), since
    boxblur always runs on CPU after hwdownload."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_export_with_ffmpeg_filters":
            src = ast.get_source_segment(source, node)
            # Pass 1 filter threading must NOT be gated on 'not gpu_filters'
            # (it was previously only for CPU path, now it's for all paths)
            assert 'bg_cmd.extend(["-filter_threads"' in src, (
                "Pass 1 must add -filter_threads to bg_cmd"
            )
            # Ensure it's not conditionally skipped for GPU path
            # The old code had: if not gpu_filters: ... filter_threads
            # The new code unconditionally adds filter_threads
            lines = src.split('\n')
            for i, line in enumerate(lines):
                if 'bg_cmd.extend(["-filter_threads"' in line:
                    # Check that this line is NOT inside an 'if not gpu_filters:' block
                    # by looking at indentation vs the preceding 'if' statement
                    assert 'not gpu_filters' not in lines[max(0, i-3):i+1][-1] if i > 0 else True, (
                        "Pass 1 -filter_threads must not be gated on 'not gpu_filters'"
                    )
                    break
            print("✓ Pass 1 uses -filter_threads for all paths (GPU and CPU)")
            return
    raise AssertionError("Could not find _export_with_ffmpeg_filters function")
