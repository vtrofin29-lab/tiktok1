#!/usr/bin/env python3
"""
Tests for non-blocking voice generation pipeline.
Validates that queue_worker submits ALL TTS tasks first (non-blocking),
then polls for completions in parallel, processing videos as-ready (out of order).
"""
import ast


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_prepare_voice_for_job_exists():
    """_prepare_voice_for_job function must exist for single-job voice generation."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_prepare_voice_for_job":
            src = ast.get_source_segment(source, node)
            assert "replace_voice_with_tts" in src, (
                "_prepare_voice_for_job must call replace_voice_with_tts"
            )
            assert "remove_silence_from_audio" in src, (
                "_prepare_voice_for_job must call remove_silence_from_audio"
            )
            assert "transcribe_captions" in src, (
                "_prepare_voice_for_job must call transcribe_captions"
            )
            assert "compressed_tts_path" in src, (
                "_prepare_voice_for_job must return compressed_tts_path"
            )
            print("✓ _prepare_voice_for_job exists with full voice pipeline")
            return
    raise AssertionError("Could not find _prepare_voice_for_job function")


def test_submit_genaipro_task_exists():
    """_submit_genaipro_task must exist for non-blocking TTS submission."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_submit_genaipro_task":
            src = ast.get_source_segment(source, node)
            # Must do HTTP POST to GenAI Pro
            assert "requests.post" in src, (
                "_submit_genaipro_task must do HTTP POST"
            )
            # Must return task_id and headers
            assert "task_id" in src, (
                "_submit_genaipro_task must return task_id"
            )
            # Must NOT contain polling loop
            assert "while True" not in src, (
                "_submit_genaipro_task must NOT poll — submission only"
            )
            print("✓ _submit_genaipro_task exists (non-blocking submission)")
            return
    raise AssertionError("Could not find _submit_genaipro_task function")


def test_poll_and_download_genaipro_exists():
    """_poll_and_download_genaipro must exist for polling TTS completion."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_poll_and_download_genaipro":
            src = ast.get_source_segment(source, node)
            # Must have polling loop
            assert "while True" in src or "while" in src, (
                "_poll_and_download_genaipro must have polling loop"
            )
            # Must download audio
            assert "requests.get" in src, (
                "_poll_and_download_genaipro must download audio"
            )
            # Must check for completion status
            assert "completed" in src or "is_complete" in src, (
                "_poll_and_download_genaipro must check completion status"
            )
            print("✓ _poll_and_download_genaipro exists (polling + download)")
            return
    raise AssertionError("Could not find _poll_and_download_genaipro function")


def test_submit_voice_for_job_exists():
    """_submit_voice_for_job must exist for Phase 1 of non-blocking pipeline."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_submit_voice_for_job":
            src = ast.get_source_segment(source, node)
            # Must extract audio / transcribe
            assert "transcribe_captions" in src, (
                "_submit_voice_for_job must transcribe audio"
            )
            # Must submit to GenAI Pro (non-blocking)
            assert "_submit_genaipro_task" in src, (
                "_submit_voice_for_job must call _submit_genaipro_task"
            )
            # Must return needs_polling flag
            assert "needs_polling" in src, (
                "_submit_voice_for_job must return needs_polling flag"
            )
            # Must have gTTS fallback
            assert "gTTS" in src, (
                "_submit_voice_for_job must fall back to gTTS"
            )
            print("✓ _submit_voice_for_job exists (non-blocking submission)")
            return
    raise AssertionError("Could not find _submit_voice_for_job function")


def test_complete_voice_for_job_exists():
    """_complete_voice_for_job must exist for Phase 2 of non-blocking pipeline."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_complete_voice_for_job":
            src = ast.get_source_segment(source, node)
            # Must poll GenAI if needed
            assert "_poll_and_download_genaipro" in src, (
                "_complete_voice_for_job must call _poll_and_download_genaipro"
            )
            # Must remove silences
            assert "remove_silence_from_audio" in src, (
                "_complete_voice_for_job must call remove_silence_from_audio"
            )
            # Must re-transcribe
            assert "transcribe_captions" in src, (
                "_complete_voice_for_job must re-transcribe compressed audio"
            )
            # Must return voice data
            assert "compressed_tts_path" in src, (
                "_complete_voice_for_job must return compressed_tts_path"
            )
            print("✓ _complete_voice_for_job exists (polling + post-processing)")
            return
    raise AssertionError("Could not find _complete_voice_for_job function")


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


def test_queue_worker_nonblocking_voice_pipeline():
    """queue_worker must implement non-blocking voice submission for multiple AI voice jobs."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            # Must check for AI voice jobs
            assert "use_ai_voice" in src, (
                "queue_worker must check use_ai_voice to decide pipeline"
            )
            # Must call _submit_voice_for_job (Phase 1: non-blocking submission)
            assert "_submit_voice_for_job" in src, (
                "queue_worker must call _submit_voice_for_job for non-blocking submission"
            )
            # Must call _complete_voice_for_job via threads (Phase 2: parallel completion)
            assert "_complete_voice_for_job" in src or "_completion_worker" in src, (
                "queue_worker must call _complete_voice_for_job for parallel completion"
            )
            # Must use threading for parallel completion
            assert "threading.Thread" in src, (
                "queue_worker must use threads for parallel voice completion"
            )
            # Must use events for ready-signaling
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
            print("✓ queue_worker implements non-blocking voice pipeline")
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
            assert "pre_generated_voice" in src, (
                "process_single_job must use pre_generated_voice data when provided"
            )
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
            assert "any_ai_voice" in src or "any(" in src, (
                "queue_worker must check if any jobs use AI voice"
            )
            assert "_run_video_job" in src, (
                "queue_worker must call _run_video_job for sequential processing"
            )
            print("✓ queue_worker falls back to sequential when no AI voice")
            return
    raise AssertionError("Could not find queue_worker function")


def test_queue_worker_phase1_submits_all_before_phase2():
    """Phase 1 must submit ALL voices before Phase 2 starts polling."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            # Phase 1 submission loop must come before Phase 2 completion threads
            submit_pos = src.find("_submit_voice_for_job")
            complete_pos = src.find("_completion_worker")
            assert submit_pos >= 0, "queue_worker must call _submit_voice_for_job"
            assert complete_pos >= 0, "queue_worker must define _completion_worker"
            assert submit_pos < complete_pos, (
                "Phase 1 (submit) must come before Phase 2 (completion) in queue_worker"
            )
            print("✓ Phase 1 submits all voices before Phase 2 starts")
            return
    raise AssertionError("Could not find queue_worker function")
