#!/usr/bin/env python3
"""
Tests for GPU memory management during multi-job voice processing.
Validates that Whisper model is cached (not re-loaded per call) and
GPU memory is properly released before FFmpeg NVENC export.
"""
import ast


def _load_source():
    with open("tiktok_full_gui.py", "r") as f:
        return f.read()


def test_whisper_model_cache_exists():
    """Global _whisper_model_cache dict must exist for model reuse."""
    source = _load_source()
    assert "_whisper_model_cache" in source, (
        "Global _whisper_model_cache must exist to avoid re-loading ~3GB model per transcription call"
    )
    print("✓ _whisper_model_cache exists")


def test_whisper_transcription_lock_exists():
    """Global _whisper_transcription_lock must exist to serialize GPU transcription."""
    source = _load_source()
    assert "_whisper_transcription_lock" in source, (
        "Global _whisper_transcription_lock must exist to prevent concurrent GPU transcription"
    )
    # Must be threading.Lock()
    assert "threading.Lock()" in source, (
        "_whisper_transcription_lock must be a threading.Lock()"
    )
    print("✓ _whisper_transcription_lock exists as threading.Lock()")


def test_get_cached_whisper_model_exists():
    """_get_cached_whisper_model function must exist for cache-first model loading."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_get_cached_whisper_model":
            src = ast.get_source_segment(source, node)
            # Must check cache first
            assert "_whisper_model_cache" in src, (
                "_get_cached_whisper_model must check _whisper_model_cache"
            )
            # Must call _load_whisper_model_with_retries as fallback
            assert "_load_whisper_model_with_retries" in src, (
                "_get_cached_whisper_model must call _load_whisper_model_with_retries for first load"
            )
            # Must store in cache
            assert "_whisper_model_cache[" in src, (
                "_get_cached_whisper_model must store loaded model in cache"
            )
            print("✓ _get_cached_whisper_model exists with cache-first logic")
            return
    raise AssertionError("Could not find _get_cached_whisper_model function")


def test_release_whisper_model_exists():
    """_release_whisper_model function must exist for GPU memory cleanup."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_release_whisper_model":
            src = ast.get_source_segment(source, node)
            # Must clear cache
            assert "_whisper_model_cache" in src, (
                "_release_whisper_model must reference _whisper_model_cache"
            )
            assert ".clear()" in src, (
                "_release_whisper_model must clear the cache"
            )
            # Must call gc.collect()
            assert "gc.collect()" in src, (
                "_release_whisper_model must call gc.collect() to free Python objects"
            )
            # Must call torch.cuda.empty_cache()
            assert "empty_cache" in src, (
                "_release_whisper_model must call torch.cuda.empty_cache() to free GPU memory"
            )
            # Must acquire lock
            assert "_whisper_transcription_lock" in src, (
                "_release_whisper_model must use _whisper_transcription_lock for thread safety"
            )
            print("✓ _release_whisper_model exists with proper cleanup")
            return
    raise AssertionError("Could not find _release_whisper_model function")


def test_transcribe_captions_uses_cached_model():
    """transcribe_captions must use _get_cached_whisper_model (not direct _load_whisper_model_with_retries)."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "transcribe_captions":
            src = ast.get_source_segment(source, node)
            # Must use cached model
            assert "_get_cached_whisper_model" in src, (
                "transcribe_captions must use _get_cached_whisper_model (not direct _load_whisper_model_with_retries)"
            )
            # Must NOT call _load_whisper_model_with_retries directly
            assert "_load_whisper_model_with_retries" not in src, (
                "transcribe_captions must NOT call _load_whisper_model_with_retries directly — use cache"
            )
            print("✓ transcribe_captions uses cached model")
            return
    raise AssertionError("Could not find transcribe_captions function")


def test_transcribe_captions_uses_lock():
    """transcribe_captions must serialize GPU access via _whisper_transcription_lock."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "transcribe_captions":
            src = ast.get_source_segment(source, node)
            # Must use the transcription lock
            assert "_whisper_transcription_lock" in src, (
                "transcribe_captions must use _whisper_transcription_lock to serialize GPU access"
            )
            print("✓ transcribe_captions serializes GPU access with lock")
            return
    raise AssertionError("Could not find transcribe_captions function")


def test_run_video_job_releases_model():
    """_run_video_job must release Whisper model before starting FFmpeg export."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_run_video_job":
            src = ast.get_source_segment(source, node)
            assert "_release_whisper_model" in src, (
                "_run_video_job must call _release_whisper_model before export to free GPU for NVENC"
            )
            print("✓ _run_video_job releases Whisper model before export")
            return
    raise AssertionError("Could not find _run_video_job function")


def test_queue_worker_releases_model_at_end():
    """queue_worker must release Whisper model at the end for GPU cleanup."""
    source = _load_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "queue_worker":
            src = ast.get_source_segment(source, node)
            assert "_release_whisper_model" in src, (
                "queue_worker must call _release_whisper_model for final GPU cleanup"
            )
            print("✓ queue_worker releases Whisper model at end")
            return
    raise AssertionError("Could not find queue_worker function")


def test_whisper_and_torch_are_lazy_imports():
    """whisper and torch must NOT be imported at module level — they must be lazy."""
    source = _load_source()
    tree = ast.parse(source)

    # Check top-level statements only (direct children of the module)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("whisper", "torch"), (
                    f"'{alias.name}' is imported at module level (line {node.lineno}). "
                    f"It must be a lazy import inside the function that uses it to avoid "
                    f"loading heavy modules (~5-10 s) at app startup."
                )
        elif isinstance(node, ast.ImportFrom) and node.module and node.module in ("whisper", "torch"):
            raise AssertionError(
                f"'from {node.module} import ...' at module level (line {node.lineno}). "
                f"Must be a lazy import inside the function that uses it."
            )

    # Verify lazy imports exist inside _load_whisper_model_with_retries
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "_load_whisper_model_with_retries":
            src = ast.get_source_segment(source, node)
            assert "import torch" in src, (
                "_load_whisper_model_with_retries must have 'import torch' inside the function"
            )
            assert "import whisper" in src, (
                "_load_whisper_model_with_retries must have 'import whisper' inside the function"
            )
            break

    print("✓ whisper and torch are lazy imports (not loaded at app startup)")
