#!/usr/bin/env python3
"""
Tests for parallel voice generation pipeline.
Validates that queue_worker generates voices in parallel when multiple
AI-voice jobs are queued, and processes videos as-ready (out of order).
"""
import ast


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_prepare_voice_for_job_exists():
    """_prepare_voice_for_job function must exist for parallel voice generation."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_prepare_voice_for_job":
            src = ast.get_source_segment(source, node)
            # Must call TTS generation
            assert "replace_voice_with_tts" in src, (
                "_prepare_voice_for_job must call replace_voice_with_tts"
            )
            # Must call silence removal
            assert "remove_silence_from_audio" in src, (
                "_prepare_voice_for_job must call remove_silence_from_audio"
            )
            # Must call transcribe
            assert "transcribe_captions" in src, (
                "_prepare_voice_for_job must call transcribe_captions"
            )
            # Must return voice data dict
            assert "compressed_tts_path" in src, (
                "_prepare_voice_for_job must return compressed_tts_path"
            )
            print("✓ _prepare_voice_for_job exists with full voice pipeline")
            return
    raise AssertionError("Could not find _prepare_voice_for_job function")


def test_extract_effect_settings_exists():
    """_extract_effect_settings helper must exist and include all effect keys."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_extract_effect_settings":
            src = ast.get_source_segment(source, node)
            for key in [
                "effect_sharpness",
                "effect_saturation",
                "effect_contrast",
                "blur_overlay_enabled",
                "blur_overlay_x",
            ]:
                assert key in src, f"_extract_effect_settings must include {key}"
            print("✓ _extract_effect_settings includes all effect keys")
            return
    raise AssertionError("Could not find _extract_effect_settings function")


def test_run_video_job_exists():
    """_run_video_job must exist and pass pre_generated_voice to process_single_job."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_video_job":
            src = ast.get_source_segment(source, node)
            assert "process_single_job" in src, (
                "_run_video_job must call process_single_job"
            )
            assert "pre_generated_voice" in src, (
                "_run_video_job must pass pre_generated_voice to process_single_job"
            )
            print("✓ _run_video_job passes pre_generated_voice")
            return
    raise AssertionError("Could not find _run_video_job function")


def test_queue_worker_parallel_voice_pipeline():
    """queue_worker must implement parallel voice generation for multiple AI voice jobs."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            # Must check for AI voice jobs
            assert "use_ai_voice" in src, (
                "queue_worker must check use_ai_voice to decide pipeline"
            )
            # Must use threading for parallel voice generation
            assert "threading.Thread" in src or "_voice_worker" in src, (
                "queue_worker must use threads for parallel voice generation"
            )
            # Must use events or similar for ready-signaling
            assert "Event" in src or "voice_done" in src, (
                "queue_worker must use events to signal when voices are ready"
            )
            # Must process as-ready (not in fixed order)
            assert "ready_idx" in src or "processed" in src, (
                "queue_worker must process jobs as their voice becomes ready"
            )
            # Must still emit QUEUE_DONE
            assert "QUEUE_DONE" in src, (
                "queue_worker must emit QUEUE_DONE when finished"
            )
            print("✓ queue_worker implements parallel voice pipeline")
            return
    raise AssertionError("Could not find queue_worker function")


def test_process_single_job_accepts_pre_generated_voice():
    """process_single_job must accept pre_generated_voice parameter."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "process_single_job":
            arg_names = [a.arg for a in node.args.args]
            assert "pre_generated_voice" in arg_names, (
                "process_single_job must accept pre_generated_voice parameter"
            )
            src = ast.get_source_segment(source, node)
            # Must use pre_generated_voice when available
            assert "pre_generated_voice" in src, (
                "process_single_job must use pre_generated_voice data when provided"
            )
            # Must still have fallback to inline generation
            assert "replace_voice_with_tts" in src, (
                "process_single_job must still support inline TTS as fallback"
            )
            print("✓ process_single_job accepts and uses pre_generated_voice")
            return
    raise AssertionError("Could not find process_single_job function")


def test_queue_worker_sequential_fallback():
    """queue_worker must fall back to sequential processing when no AI voice jobs."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            # Must check if any jobs use AI voice
            assert "any_ai_voice" in src or "any(" in src, (
                "queue_worker must check if any jobs use AI voice"
            )
            # Must have sequential fallback
            assert "_run_video_job" in src, (
                "queue_worker must call _run_video_job for sequential processing"
            )
            print("✓ queue_worker falls back to sequential when no AI voice")
            return
    raise AssertionError("Could not find queue_worker function")
