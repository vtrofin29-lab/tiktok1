def opacity_fade(t, start, dur, fade_in, fade_out):
    """Return opacity (0..1) at time t for a clip that starts at `start`, has duration `dur`,
    fades in over `fade_in` seconds and fades out over `fade_out` seconds."""
    if t < start:
        return 0.0
    rel = t - start
    # fade in
    if fade_in and rel < fade_in:
        return float(rel) / float(fade_in)
    # fade out
    if fade_out and rel > (dur - fade_out):
        val = float(dur - rel) / float(fade_out)
        return max(0.0, min(1.0, val))
    return 1.0


#!/usr/bin/env python3
"""
tiktok_full_gui.py

Versiune completă integrată:
- GUI responsive cu PanedWindow
- Mini-preview cu draggable crop lines
- Timeline slider + time label
- Save/Load crop settings
- Job queue (multiple jobs) + unique outputs (_1, _2 ... if exist)
- Pre-render foreground via ffmpeg (NVENC if available)
- Robust Whisper loading (retry + cleanup + fallback to 'small')
- Caption grouping (WORDS_PER_GROUP) + Bangers font loading + diacritics normalization
- Static blurred background from a mid frame (fast)
- Monitored export with stall detection and fallback attempts
- Auto-open output on success
"""
import os



def find_ttf_in_tiktok(font_name, search_root=r"C:\tiktok"):
    """
    Search recursively in search_root for a .ttf/.otf file whose filename matches font_name.
    Matching is case-insensitive and ignores non-alphanumeric characters (so '-' and spaces are ignored).
    Returns the first matching path or None.
    """
    try:
        if not font_name:
            return None
        import re, os
        def _norm(s):
            return re.sub(r'[^a-z0-9]', '', s.lower())
        token = _norm(font_name)
        for root, dirs, files in os.walk(search_root):
            for fn in files:
                if fn.lower().endswith((".ttf", ".otf")):
                    name_only = os.path.splitext(fn)[0]
                    name_norm = _norm(name_only)
                    if not token:
                        continue
                    if token in name_norm or name_norm in token:
                        return os.path.join(root, fn)
        return None
    except Exception:
        return None


import sys
import threading
import queue
import subprocess
import math
import time
import tempfile
import shutil
import json
import gc

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText
from pathlib import Path

import numpy as np
# --- Pillow compatibility shim: ensure Image.ANTIALIAS exists for older code / moviepy ---
try:
    from PIL import Image as _Image_for_compat
    if not hasattr(_Image_for_compat, 'ANTIALIAS'):
        try:
            # Pillow >= 10: use Resampling.LANCZOS
            _Image_for_compat.ANTIALIAS = _Image_for_compat.Resampling.LANCZOS
        except Exception:
            # fallback to Image.LANCZOS if available
            if hasattr(_Image_for_compat, 'LANCZOS'):
                _Image_for_compat.ANTIALIAS = _Image_for_compat.LANCZOS
            else:
                # last resort: set to None (resizing will still work but quality setting not applied)
                _Image_for_compat.ANTIALIAS = None
except Exception:
    pass

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageTk

# External heavy deps: moviepy, whisper
from moviepy.editor import (
    VideoFileClip, CompositeVideoClip, AudioFileClip, ImageClip,
    concatenate_videoclips, concatenate_audioclips
)
from moviepy.audio.AudioClip import CompositeAudioClip
from moviepy.video.fx.all import speedx
from moviepy.audio.fx.all import audio_fadeout

import whisper
import torch  # For GPU detection in Whisper

# ----------------- TRANSLATION & AI VOICE MODULES -----------------
try:
    from googletrans import Translator
    TRANSLATION_AVAILABLE = True
except ImportError:
    TRANSLATION_AVAILABLE = False
    Translator = None

try:
    from gtts import gTTS
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False
    gTTS = None

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    requests = None

# ----------------- TRANSLATION FUNCTIONS -----------------
def translate_text(text, target_language='en', log=None):
    """
    Translate text to target language using Google Translate API.
    
    Args:
        text: Text to translate
        target_language: Target language code (e.g., 'en', 'es', 'fr', 'ro')
        log: Optional logging function
    
    Returns:
        Translated text or original text if translation fails
    """
    if not TRANSLATION_AVAILABLE:
        if log:
            log("[TRANSLATE] googletrans not available - skipping translation")
        return text
    
    if not text or not text.strip():
        return text
    
    try:
        translator = Translator()
        result = translator.translate(text, dest=target_language)
        if log:
            log(f"[TRANSLATE] '{text[:50]}...' -> '{result.text[:50]}...' ({target_language})")
        return result.text
    except Exception as e:
        if log:
            log(f"[TRANSLATE ERROR] Failed to translate: {e}")
        return text

def translate_segments(segments, target_language='en', log=None):
    """
    Translate all caption segments to target language.
    
    Args:
        segments: List of caption segments from Whisper
        target_language: Target language code
        log: Optional logging function
    
    Returns:
        List of segments with translated text
    """
    if not TRANSLATION_AVAILABLE or target_language == 'none':
        return segments
    
    if log:
        log(f"[TRANSLATE] Translating {len(segments)} segments to {target_language}...")
    
    translated = []
    for i, seg in enumerate(segments):
        try:
            original_text = seg.get("text", "")
            translated_text = translate_text(original_text, target_language, log=None)
            
            # Create new segment with translated text
            new_seg = seg.copy()
            new_seg["text"] = translated_text
            new_seg["original_text"] = original_text
            translated.append(new_seg)
        except Exception as e:
            if log:
                log(f"[TRANSLATE ERROR] Failed segment {i}: {e}")
            translated.append(seg)
    
    if log:
        log(f"[TRANSLATE] Translation complete!")
    
    return translated

# ----------------- AI VOICE REPLACEMENT FUNCTIONS -----------------

def generate_tts_with_genaipro(text, language='en', output_path=None, api_key=None, log=None):
    """
    Generate Text-to-Speech audio using GenAI Pro API.
    
    Args:
        text: Text to convert to speech
        language: Language code for TTS
        output_path: Path to save audio file (temp file if None)
        api_key: GenAI Pro API key (JWT token)
        log: Optional logging function
    
    Returns:
        Path to generated audio file or None if failed
    """
    if not REQUESTS_AVAILABLE:
        if log:
            log("[GenAI Pro] requests library not available")
        return None
    
    if not api_key:
        if log:
            log("[GenAI Pro] No API key provided")
        return None
    
    if not text or not text.strip():
        return None
    
    try:
        import requests
        import time
        
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.mp3', prefix='genaipro_tts_')
            os.close(fd)
        
        # Map language codes to voice IDs (you can expand this mapping)
        # Check if a custom voice ID is specified, otherwise use language defaults
        global TTS_VOICE_ID
        if TTS_VOICE_ID and TTS_VOICE_ID != 'auto':
            voice_id = TTS_VOICE_ID
        else:
            voice_map = {
                'en': 'uju3wxzG5OhpWcoi3SMy',  # Default English voice
                'es': 'uju3wxzG5OhpWcoi3SMy',  # Using same for now, can be customized
                'fr': 'uju3wxzG5OhpWcoi3SMy',
                'de': 'uju3wxzG5OhpWcoi3SMy',
                'it': 'uju3wxzG5OhpWcoi3SMy',
                'pt': 'uju3wxzG5OhpWcoi3SMy',
                'ro': 'uju3wxzG5OhpWcoi3SMy',
                'ru': 'uju3wxzG5OhpWcoi3SMy',
                'zh': 'uju3wxzG5OhpWcoi3SMy',
                'ja': 'uju3wxzG5OhpWcoi3SMy',
                'ko': 'uju3wxzG5OhpWcoi3SMy',
            }
            voice_id = voice_map.get(language, 'uju3wxzG5OhpWcoi3SMy')
        
        # Step 1: Submit TTS task
        if log:
            log(f"[GenAI Pro] Submitting TTS task ({len(text)} chars)...")
        
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        }
        
        task_payload = {
            'input': text,
            'voice_id': voice_id,
            'model_id': 'eleven_turbo_v2_5',  # Fast model
            'speed': 1.0,
            'style': 0.0,
            'use_speaker_boost': False,
            'similarity': 0.75,
            'stability': 0.5
        }
        
        response = requests.post(
            'https://genaipro.vn/api/v1/labs/task',
            headers=headers,
            json=task_payload,
            timeout=30
        )
        
        if response.status_code != 200:
            if log:
                log(f"[GenAI Pro ERROR] Task submission failed: {response.status_code} - {response.text}")
            return None
        
        task_data = response.json()
        # GenAI Pro might return 'task_id' or 'id' field
        task_id = task_data.get('task_id') or task_data.get('id')
        
        if not task_id:
            if log:
                log(f"[GenAI Pro ERROR] No task_id in response: {task_data}")
            return None
        
        if log:
            log(f"[GenAI Pro] Task submitted with ID: {task_id}")
            log(f"[GenAI Pro DEBUG] Full submission response: {task_data}")
        
        # Step 2: Poll for task completion - wait as long as needed for GenAI Pro
        max_polls = 1800  # Wait up to 30 minutes (1800 iterations * 2 seconds = 3600 seconds = 60 minutes total)
        poll_interval = 2  # Poll every 2 seconds to reduce API calls
        
        if log:
            log(f"[GenAI Pro] Waiting for audio generation... (will wait as long as needed, max 60 minutes)")
        
        for i in range(max_polls):
            time.sleep(poll_interval)
            
            elapsed_seconds = (i + 1) * poll_interval
            # Show progress every 10 seconds or at start
            if i == 0 or elapsed_seconds % 10 == 0:
                elapsed_mins = elapsed_seconds // 60
                elapsed_secs = elapsed_seconds % 60
                if log:
                    log(f"[GenAI Pro] ⏳ Waiting: {elapsed_mins}m {elapsed_secs}s elapsed - Still processing...")
            
            status_response = requests.get(
                'https://genaipro.vn/api/v1/labs/task',
                headers=headers,
                timeout=10
            )
            
            if status_response.status_code != 200:
                if log:
                    log(f"[GenAI Pro ERROR] Status check failed: {status_response.status_code}")
                continue
            
            tasks = status_response.json()
            
            # Find our task in the list
            our_task = None
            if isinstance(tasks, list):
                for task in tasks:
                    # Check both 'task_id' and 'id' fields
                    task_identifier = task.get('task_id') or task.get('id')
                    if task_identifier == task_id:
                        our_task = task
                        break
            elif isinstance(tasks, dict):
                # Could be a single task response or a wrapper
                task_identifier = tasks.get('task_id') or tasks.get('id')
                if task_identifier == task_id:
                    our_task = tasks
                elif 'tasks' in tasks and isinstance(tasks['tasks'], list):
                    # Response might have tasks in a 'tasks' field
                    for task in tasks['tasks']:
                        task_identifier = task.get('task_id') or task.get('id')
                        if task_identifier == task_id:
                            our_task = task
                            break
                elif 'data' in tasks and isinstance(tasks['data'], list):
                    # Response might have tasks in a 'data' field
                    for task in tasks['data']:
                        task_identifier = task.get('task_id') or task.get('id')
                        if task_identifier == task_id:
                            our_task = task
                            break
            
            if our_task:
                status = our_task.get('status', '').lower()
                result = our_task.get('result', '')
                
                # DEBUG: Log full task object every 20 seconds to see what fields are available
                if i % 10 == 0 and log:
                    log(f"[GenAI Pro DEBUG] Current task object: {our_task}")
                
                # Check if task is complete - either by status OR by result field being populated
                # GenAI Pro fills the 'result' field with audio URL when done
                is_complete = (status in ['completed', 'done', 'success', 'succeeded', 'finished'] or 
                              (result and result != ''))
                
                if is_complete:
                    elapsed_seconds = (i + 1) * poll_interval
                    elapsed_mins = elapsed_seconds // 60
                    elapsed_secs = elapsed_seconds % 60
                    if log:
                        log(f"[GenAI Pro] ✓ Audio generation complete! (took {elapsed_mins}m {elapsed_secs}s)")
                        log(f"[GenAI Pro DEBUG] Complete task - All fields: {list(our_task.keys())}")
                        log(f"[GenAI Pro DEBUG] Complete task - Full object: {our_task}")
                    
                    # Try multiple possible field names for the audio URL, including 'result'
                    audio_url = (our_task.get('result') or
                                our_task.get('output_url') or 
                                our_task.get('audio_url') or 
                                our_task.get('result_url') or
                                our_task.get('file_url') or
                                our_task.get('url'))
                    
                    if not audio_url:
                        if log:
                            log(f"[GenAI Pro ERROR] Task completed but no audio URL found")
                            log(f"[GenAI Pro ERROR] status={status}, result={result}")
                            log(f"[GenAI Pro ERROR] Checked fields: result, output_url, audio_url, result_url, file_url, url")
                            log(f"[GenAI Pro ERROR] All available fields in task: {list(our_task.keys())}")
                        return None
                    
                    # Step 3: Download the audio file
                    if log:
                        log(f"[GenAI Pro] 📥 Downloading audio file from: {audio_url}")
                    
                    audio_response = requests.get(audio_url, timeout=30)
                    
                    if audio_response.status_code == 200:
                        with open(output_path, 'wb') as f:
                            f.write(audio_response.content)
                        
                        if log:
                            log(f"[GenAI Pro] ✅ TTS generated successfully: {output_path}")
                        return output_path
                    else:
                        if log:
                            log(f"[GenAI Pro ERROR] Failed to download audio: {audio_response.status_code}")
                        return None
                
                elif status in ['failed', 'error', 'cancelled', 'canceled']:
                    if log:
                        log(f"[GenAI Pro ERROR] ❌ Task failed with status '{status}': {our_task}")
                    return None
                
                # Show status periodically for non-completed tasks
                elif i % 10 == 0 and log and i > 0:
                    log(f"[GenAI Pro] Status: {status} (still processing...)")
            else:
                # Task not found in response - log for debugging
                if i == 0 and log:
                    log(f"[GenAI Pro DEBUG] Task {task_id} not found in initial status check.")
                    log(f"[GenAI Pro DEBUG] Response type: {type(tasks)}")
                    log(f"[GenAI Pro DEBUG] Full response: {tasks}")
                elif i % 30 == 0 and log and i > 0:
                    log(f"[GenAI Pro DEBUG] Still waiting... Task {task_id} not found in status response.")
                    # Log response structure periodically
                    if isinstance(tasks, list) and len(tasks) > 0:
                        log(f"[GenAI Pro DEBUG] Sample task structure: {tasks[0]}")
                    elif isinstance(tasks, dict):
                        log(f"[GenAI Pro DEBUG] Response keys: {list(tasks.keys())}")
        
        # If we get here, the task didn't complete within the timeout
        if log:
            elapsed_total = max_polls * poll_interval
            elapsed_mins = elapsed_total // 60
            log(f"[GenAI Pro ERROR] ⏱️ Task timeout after {elapsed_mins} minutes. Task may still be processing on GenAI Pro.")
        return None
        
    except Exception as e:
        if log:
            log(f"[GenAI Pro ERROR] Exception: {e}")
        return None

def remove_silence_from_audio(audio_path, output_path=None, log=None, min_silence_ms=300):
    """
    Remove long silences from audio file while keeping natural speech pauses.
    
    Args:
        audio_path: Path to input audio file
        output_path: Path to save processed audio (temp file if None)
        log: Optional logging function
        min_silence_ms: Minimum silence length in milliseconds to remove (default: 300ms)
    
    Returns:
        Tuple of (output_path, silence_map) where silence_map is a list of
        (original_start, original_end, new_start, new_end) for each kept segment
    """
    try:
        from pydub import AudioSegment
        from pydub.silence import detect_nonsilent
    except ImportError:
        if log:
            log("[SILENCE] pydub not available - skipping silence removal")
        return audio_path, []
    
    try:
        if log:
            log(f"[SILENCE] Loading audio: {audio_path}")
        
        # Load audio
        audio = AudioSegment.from_file(audio_path)
        
        if log:
            log(f"[SILENCE] Original duration: {len(audio)/1000.0:.2f}s")
        
        # Detect non-silent chunks (balanced - remove gaps based on user setting)
        # min_silence_len: minimum length of silence to consider (default 300ms)
        # silence_thresh: volume threshold for silence (audio.dBFS - 16 = fairly sensitive)
        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_ms,  # User-configurable threshold
            silence_thresh=audio.dBFS - 16  # Detect even quiet parts as non-silent
        )
        
        if not nonsilent_ranges:
            if log:
                log("[SILENCE] No non-silent segments found!")
            return audio_path, []
        
        if log:
            log(f"[SILENCE] Found {len(nonsilent_ranges)} non-silent segments")
        
        # Concatenate all non-silent segments
        output_audio = AudioSegment.empty()
        silence_map = []
        new_position = 0
        
        for i, (start_ms, end_ms) in enumerate(nonsilent_ranges):
            segment = audio[start_ms:end_ms]
            output_audio += segment
            
            # Track mapping: original time -> new time
            segment_duration = end_ms - start_ms
            silence_map.append((
                start_ms / 1000.0,  # original start in seconds
                end_ms / 1000.0,    # original end in seconds
                new_position / 1000.0,  # new start in seconds
                (new_position + segment_duration) / 1000.0  # new end in seconds
            ))
            new_position += segment_duration
        
        if log:
            orig_dur = len(audio) / 1000.0
            new_dur = len(output_audio) / 1000.0
            removed = orig_dur - new_dur
            log(f"[SILENCE] New duration: {new_dur:.2f}s (removed {removed:.2f}s of silence)")
        
        # Save processed audio
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.mp3', prefix='audio_no_silence_')
            os.close(fd)
        
        output_audio.export(output_path, format="mp3")
        
        if log:
            log(f"[SILENCE] ✅ Saved silence-removed audio: {output_path}")
        
        return output_path, silence_map
        
    except Exception as e:
        if log:
            log(f"[SILENCE ERROR] Failed to remove silence: {e}")
        return audio_path, []

def map_timestamps_after_silence_removal(segments, silence_map, log=None):
    """
    Re-map caption segment timestamps after silence removal.
    
    Args:
        segments: List of caption segments with 'start' and 'end' times
        silence_map: List of (orig_start, orig_end, new_start, new_end) from remove_silence_from_audio
        log: Optional logging function
    
    Returns:
        List of segments with updated 'start' and 'end' times
    """
    if not silence_map:
        if log:
            log("[TIMESTAMP] No silence map - returning original segments")
        return segments
    
    if log:
        log(f"[TIMESTAMP] Re-mapping {len(segments)} segments to compressed audio timeline")
    
    def map_time(original_time):
        """Map an original timestamp to the new timeline after silence removal."""
        # Find which segment contains this timestamp
        for orig_start, orig_end, new_start, new_end in silence_map:
            if orig_start <= original_time <= orig_end:
                # Time falls within this segment
                # Calculate relative position within the segment
                relative_pos = (original_time - orig_start) / (orig_end - orig_start) if (orig_end - orig_start) > 0 else 0
                # Map to new timeline
                return new_start + relative_pos * (new_end - new_start)
        
        # If time doesn't fall in any segment, find the closest segment
        # (this handles edge cases and slight timestamp mismatches)
        closest_segment = min(silence_map, key=lambda seg: min(abs(seg[0] - original_time), abs(seg[1] - original_time)))
        orig_start, orig_end, new_start, new_end = closest_segment
        
        if original_time < orig_start:
            return new_start  # Before first segment
        else:
            return new_end  # After last segment
    
    # Create new segments with mapped timestamps
    mapped_segments = []
    for seg in segments:
        new_seg = seg.copy()
        orig_start = seg.get('start', 0)
        orig_end = seg.get('end', 0)
        
        new_seg['start'] = map_time(orig_start)
        new_seg['end'] = map_time(orig_end)
        
        # If segment has word-level timestamps, map those too
        if 'words' in seg and seg['words']:
            new_words = []
            for word in seg['words']:
                new_word = word.copy()
                if 'start' in word:
                    new_word['start'] = map_time(word['start'])
                if 'end' in word:
                    new_word['end'] = map_time(word['end'])
                new_words.append(new_word)
            new_seg['words'] = new_words
        
        mapped_segments.append(new_seg)
    
    if log:
        orig_total = segments[-1]['end'] if segments else 0
        new_total = mapped_segments[-1]['end'] if mapped_segments else 0
        log(f"[TIMESTAMP] Timeline compressed from {orig_total:.2f}s to {new_total:.2f}s")
    
    return mapped_segments

def generate_tts_audio(text, language='en', output_path=None, log=None):
    """
    Generate Text-to-Speech audio from text using GenAI Pro (if API key available) or gTTS (fallback).
    
    Args:
        text: Text to convert to speech
        language: Language code for TTS
        output_path: Path to save audio file (temp file if None)
        log: Optional logging function
    
    Returns:
        Path to generated audio file or None if failed
    """
    # Try to load API key from config
    api_key = None
    try:
        config_path = os.path.join(os.path.dirname(__file__), "tts_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                api_key = config.get("api_key", "").strip()
    except Exception:
        pass
    
    # Try GenAI Pro first if API key is available
    if api_key:
        if log:
            log("="*60)
            log("[TTS] 🎙️  STARTING AI VOICE GENERATION")
            log(f"[TTS] Using GenAI Pro API for high-quality synthesis")
            log(f"[TTS] Text length: {len(text)} characters")
            log(f"[TTS] Language: {language}")
            log("="*60)
        result = generate_tts_with_genaipro(text, language, output_path, api_key, log)
        if result:
            if log:
                log("="*60)
                log("[TTS] ✅ AI VOICE GENERATION COMPLETE!")
                log(f"[TTS] Audio file ready: {result}")
                log("="*60)
            return result
        if log:
            log("[TTS] ⚠️  GenAI Pro failed, falling back to gTTS...")
    
    # Fallback to gTTS
    if not TTS_AVAILABLE:
        if log:
            log("[TTS] gTTS not available - skipping voice generation")
        return None
    
    if not text or not text.strip():
        return None
    
    try:
        if output_path is None:
            fd, output_path = tempfile.mkstemp(suffix='.mp3', prefix='tts_')
            os.close(fd)
        
        tts = gTTS(text=text, lang=language, slow=False)
        tts.save(output_path)
        
        if log:
            log(f"[TTS/gTTS] Generated audio: {output_path} (length: {len(text)} chars)")
        
        return output_path
    except Exception as e:
        if log:
            log(f"[TTS ERROR] Failed to generate audio: {e}")
        return None

def replace_voice_with_tts(caption_segments, language='en', log=None):
    """
    Generate AI voice audio from caption segments.
    
    Args:
        caption_segments: List of caption segments with translated text
        language: Language code for TTS
        log: Optional logging function
    
    Returns:
        Path to generated audio file or None if failed
    """
    if not TTS_AVAILABLE:
        if log:
            log("[TTS] gTTS not available - cannot replace voice")
        return None
    
    if log:
        log(f"[TTS] Generating AI voice from {len(caption_segments)} segments...")
    
    try:
        # NOTE: This implementation combines all segments into one continuous audio track.
        # For better synchronization, a future enhancement would be to:
        # 1. Generate TTS for each segment individually
        # 2. Concatenate audio clips with proper timing based on segment start/end times
        # 3. Add silence between segments to match original timing
        # Current approach works well when video speed is adjusted to match audio duration.
        
        # Combine all segment texts
        full_text = " ".join([seg.get("text", "") for seg in caption_segments])
        
        # Generate TTS audio
        output_path = generate_tts_audio(full_text, language=language, log=log)
        
        if output_path and log:
            log(f"[TTS] Voice replacement complete: {output_path}")
        
        return output_path
    except Exception as e:
        if log:
            log(f"[TTS ERROR] Failed to replace voice: {e}")
        return None

# ----------------- SETTINGS (defaults) -----------------
WIDTH = 1080
HEIGHT = 1920
IS_4K_MODE = False  # Track resolution mode for proper scaling

CROP_TOP_RATIO = 0.30
CROP_BOTTOM_RATIO = 0.35

VOICE_GAIN = 1.5  # Default: 1.5x louder for better voice clarity
MUSIC_GAIN = 0.15  # Default: 0.15x quieter for subtle background music
CAPTION_FONT_PREFERRED = "Bangers"
CAPTION_FONT_SIZE = 56

# Debug: force saving caption images and force-visible overlay for testing
CAPTION_DEBUG_SAVE_IMAGES = True
CAPTION_DEBUG_FORCE_VISIBLE = True
CAPTION_PADDING = 200

# Default caption colors (RGBA)
CAPTION_TEXT_COLOR = (255, 255, 255, 255)
CAPTION_STROKE_COLOR = (0, 0, 0, 150)
# Stroke width (pixels) for caption border
CAPTION_STROKE_WIDTH = max(1, int(CAPTION_FONT_SIZE * 0.05))

# Video zoom scale (user-controllable)
VIDEO_ZOOM_SCALE = 1.0  # 1.0 = auto-fit, <1.0 = zoom out, >1.0 = zoom in

# Translation and AI Voice settings
TRANSLATION_ENABLED = False
TARGET_LANGUAGE = 'none'  # 'none', 'en', 'es', 'fr', 'ro', etc.
USE_AI_VOICE_REPLACEMENT = False
TTS_LANGUAGE = 'en'
TTS_VOICE_ID = 'auto'  # 'auto' or specific voice ID
# Premium TTS API keys (for better quality voices)
# Supported: 'elevenlabs', 'openai', 'azure'
TTS_ENGINE = 'gtts'  # Options: 'gtts' (free, basic), 'elevenlabs', 'openai', 'azure'
ELEVENLABS_API_KEY = None
OPENAI_API_KEY = None
AZURE_SPEECH_KEY = None
AZURE_SPEECH_REGION = None

FPS = 24

MUSIC_FADEOUT_SECONDS = 0.8
MUSIC_LOOP_ALLOWED = True

STATIC_BG_BLUR_RADIUS = 25
BG_SCALE_EXTRA = 1.08
DIM_FACTOR = 0.55

USE_GPU_IF_AVAILABLE = True
PREFERRED_NVENC_CODEC = "h264_nvenc"
USE_HARDWARE_DECODING = True  # Enable GPU-accelerated decoding
NVENC_PRESET_SPEED = "p4"  # p1=fastest, p7=slowest/best quality. p4=balanced for speed

CAPTION_RAISE = 420
CAPTION_Y_OFFSET = 0  # Vertical offset in pixels (negative = move up, positive = move down)
TEMPLATE_WORDS = {1: 1, 2: 2, 3: 3}
CAPTION_TEMPLATE = 2  # 1, 2 sau 3 cuvinte pe rand

# Maximum captions for FFmpeg drawtext filters before switching to ASS subtitle file
# (avoids command line length limits and improves performance with many captions)
MAX_DRAWTEXT_CAPTIONS = 100

REQUIRE_FONT_BANGERS = False

CROP_SETTINGS_FILE = "crop_settings.json"

CREATED_OUTPUTS = set()

# ----------------- FONT / DIACRITICS / UTIL -----------------
FONT_CANDIDATES = ["Bangers-Regular.ttf", "Bangers.ttf", "bangers.ttf", "Bangers.otf", "Bangers-Regular.otf"]



# --- Custom dark CanvasSlider widget ---
class CanvasSlider(tk.Canvas):
    def __init__(self, master, from_=0.0, to=1.0, length=400, command=None, initial=0.0, bg='#111111', trough='#222222', slider_color='#2b8cff', height=24, **kwargs):
        # accept optional tk.Variable to sync value externally
        self.tk_variable = kwargs.pop('variable', None)
        # remove other widget-specific kwargs
        for _k in ('orient','resolution','sliderlength','from_','to'):
            kwargs.pop(_k, None)
        super().__init__(master, width=length, height=height, bg=bg, highlightthickness=0, **kwargs)
        self.from_ = float(from_)
        self.to = float(to)
        self.command = command
        self.length = int(length)
        self.height = int(height)
        self.trough_color = trough
        self.slider_color = slider_color
        self.bg = bg
        self.knob_radius = max(8, self.height//2 - 2)
        self.knob_pos = 0  # pixel position
        self.value = float(initial)
        # sync variable if provided
        try:
            if self.tk_variable is not None:
                try:
                    self.tk_variable.set(self.value)
                except Exception:
                    pass
        except Exception:
            pass
        # position knob according to initial value
        try:
            self.knob_pos = self._value_to_pos(self.value)
        except Exception:
            self.knob_pos = 0
        self.bind("<Button-1>", self._click)
        self.bind("<B1-Motion>", self._drag)
        self.bind("<Configure>", self._on_resize)
        self.redraw()

    def _on_resize(self, event):
        self.length = max(50, event.width)
        try:
            self.knob_pos = self._value_to_pos(self.value)
        except Exception:
            pass
        self.redraw()

    def _value_to_pos(self, v):
        frac = 0.0 if self.to == self.from_ else (v - self.from_) / (self.to - self.from_)
        return int(self.knob_radius + frac * (self.length - 2*self.knob_radius))

    def _pos_to_value(self, x):
        frac = min(1.0, max(0.0, (x - self.knob_radius) / float(max(1, self.length - 2*self.knob_radius))))
        return self.from_ + frac * (self.to - self.from_)

    def set(self, v):
        try:
            v = float(v)
        except Exception:
            return
        v = min(self.to, max(self.from_, v))
        self.value = v
        self.knob_pos = self._value_to_pos(v)
        # sync to tk variable if present
        try:
            if self.tk_variable is not None:
                try:
                    self.tk_variable.set(self.value)
                except Exception:
                    pass
        except Exception:
            pass
        self.redraw()
        # call command callback when value is set programmatically
        if self.command:
            try:
                self.command(self.value)
            except Exception:
                pass

    def get(self):
        return self.value

    def _click(self, event):
        x = event.x
        val = self._pos_to_value(x)
        self.set(val)

    def _drag(self, event):
        x = event.x
        val = self._pos_to_value(x)
        self.set(val)

    def redraw(self):
        self.delete("all")
        # draw trough
        y = self.height // 2
        self.create_rectangle(self.knob_radius, y - 6, self.length - self.knob_radius, y + 6, fill=self.trough_color, outline=self.trough_color)
        # draw progress
        self.create_rectangle(self.knob_radius, y - 6, self.knob_pos, y + 6, fill=self.slider_color, outline=self.slider_color)
        # draw knob (circle)
        self.create_oval(self.knob_pos - self.knob_radius, y - self.knob_radius, self.knob_pos + self.knob_radius, y + self.knob_radius, fill=self.slider_color, outline='')

def _common_font_dirs():
    dirs = [os.getcwd()]
    if os.name == "nt":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        dirs.append(os.path.join(windir, "Fonts"))
    else:
        dirs += ["/usr/share/fonts", "/usr/share/fonts/truetype", "/usr/local/share/fonts", "/Library/Fonts", "/System/Library/Fonts"]
    return dirs

def find_font_file_recursive(preferred_name=None):
    names_lower = set()
    if preferred_name:
        names_lower.add(preferred_name.lower())
    for n in FONT_CANDIDATES:
        names_lower.add(n.lower())
    if preferred_name:
        if os.path.isabs(preferred_name) and os.path.isfile(preferred_name):
            return os.path.abspath(preferred_name)
        if os.path.isfile(preferred_name):
            return os.path.abspath(preferred_name)
    for name in FONT_CANDIDATES:
        if os.path.isfile(name):
            return os.path.abspath(name)
    for base in _common_font_dirs():
        if not os.path.isdir(base):
            continue
        for root, dirs, files in os.walk(base):
            for f in files:
                fl = f.lower()
                tried_path = os.path.join(root, f)
                if fl in names_lower:
                    return os.path.abspath(tried_path)
                if preferred_name and preferred_name.lower() in fl:
                    return os.path.abspath(tried_path)
                if "bangers" in fl:
                    return os.path.abspath(tried_path)
    return None

LOADED_FONT = None
LOADED_FONT_PATH = None

def load_preferred_font_cached(preferred, size, log=None):
    global LOADED_FONT, LOADED_FONT_PATH
    # If a font is already loaded and the preferred request matches the cached path/family, reuse it.
    try:
        if LOADED_FONT is not None:
            if not preferred:
                try:
                    if log:
                        log(f"[FONT] Using cached font: {LOADED_FONT_PATH}")
                except Exception:
                    pass
                return LOADED_FONT
            # normalize comparison: absolute path or family marker
            try:
                pref_norm = os.path.abspath(preferred) if os.path.isabs(preferred) else preferred
            except Exception:
                pref_norm = preferred
            if LOADED_FONT_PATH:
                # exact path match
                try:
                    if os.path.isabs(str(LOADED_FONT_PATH)) and os.path.isabs(str(pref_norm)) and os.path.abspath(str(LOADED_FONT_PATH)) == os.path.abspath(str(pref_norm)):
                        try:
                            if log:
                                log(f"[FONT] Using cached font (path match): {LOADED_FONT_PATH}")
                        except Exception:
                            pass
                        return LOADED_FONT
                except Exception:
                    pass
                # family name match marker: LOADED_FONT_PATH may be 'family:<name>'
                try:
                    if isinstance(LOADED_FONT_PATH, str) and LOADED_FONT_PATH.lower().startswith('family:') and preferred and preferred.lower() in LOADED_FONT_PATH.lower():
                        try:
                            if log:
                                log(f"[FONT] Using cached font (family match): {LOADED_FONT_PATH}")
                        except Exception:
                            pass
                        return LOADED_FONT
                except Exception:
                    pass
            # otherwise fall through and attempt to load the requested preferred font
    except Exception:
        pass

    if preferred:
        if os.path.isfile(preferred):
            try:
                LOADED_FONT = ImageFont.truetype(preferred, size)
                LOADED_FONT_PATH = os.path.abspath(preferred)
                if log: log(f"[FONT] ✓ Loaded font from file: {LOADED_FONT_PATH}")
                return LOADED_FONT
            except Exception:
                pass
        found = find_font_file_recursive(preferred)
        if found:
            try:
                LOADED_FONT = ImageFont.truetype(found, size)
                LOADED_FONT_PATH = found
                if log: log(f"[FONT] ✓ Loaded font (searched): {found}")
                return LOADED_FONT
            except Exception:
                pass
        try:
            LOADED_FONT = ImageFont.truetype(preferred, size)
            LOADED_FONT_PATH = f"family:{preferred}"
            if log: log(f"[FONT] ✓ Loaded font by family name: {preferred}")
            return LOADED_FONT
        except Exception:
            pass
    found = find_font_file_recursive(None)
    if found:
        try:
            LOADED_FONT = ImageFont.truetype(found, size)
            LOADED_FONT_PATH = found
            if log: log(f"[FONT] ✓ Loaded candidate font: {found}")
            return LOADED_FONT
        except Exception:
            pass
    try:
        LOADED_FONT = ImageFont.truetype("DejaVuSans.ttf", size)
        LOADED_FONT_PATH = "DejaVuSans.ttf (fallback)"
        if log: log("[FONT] WARNING: Preferred font not found — using DejaVuSans.ttf fallback.")
        return LOADED_FONT
    except Exception:
        pass
    if log: log("[FONT] WARNING: No TrueType fonts available. Using default bitmap font.")
    LOADED_FONT = ImageFont.load_default()
    LOADED_FONT_PATH = "default"
    return LOADED_FONT

def normalize_text(s: str) -> str:
    if not s: return s
    trans = str.maketrans({
        'ă': 'a', 'Ă': 'A','â': 'a', 'Â': 'A','î': 'i', 'Î': 'I',
        'ș': 's', 'Ș': 'S', 'ş': 's', 'Ş': 'S','ț': 't', 'Ț': 'T','ţ': 't', 'Ţ': 'T'
    })
    try:
        return s.translate(trans)
    except Exception:
        repl = s
        for k, v in trans.items():
            repl = repl.replace(k, v)
        return repl

# ----------------- logging helper -----------------
class QueueWriter:
    def __init__(self, q: queue.Queue):
        self.q = q
    def write(self, s):
        if s and not s.isspace():
            self.q.put(str(s))
    def flush(self):
        pass

# ----------------- ffmpeg / pre-render / export helpers -----------------
def ffmpeg_supports_nvenc(codec_name="h264_nvenc"):
    try:
        out = subprocess.check_output(["ffmpeg", "-hide_banner", "-encoders"], stderr=subprocess.STDOUT, text=True)
        return codec_name in out
    except Exception:
        return False

def get_export_settings():
    audio_bitrate = "192k"
    threads = 4  # Use 4 threads for better CPU utilization (was 0/auto)
    libx264_params = ["-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]  # Changed from slow to ultrafast
    libx264_codec = "libx264"
    nvenc_params = ["-rc", "vbr_hq", "-cq", "19", "-b:v", "0", "-preset", NVENC_PRESET_SPEED, "-pix_fmt", "yuv420p", "-profile:v", "high", "-movflags", "+faststart"]
    if USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC):
        return PREFERRED_NVENC_CODEC, nvenc_params, threads, audio_bitrate
    return libx264_codec, libx264_params, threads, audio_bitrate

def reencode_with_libx264(input_path, output_path, log=None):
    # Use hardware acceleration if available
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    
    # Add hardware decoding
    if USE_HARDWARE_DECODING and USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC):
        cmd.extend(["-hwaccel", "cuda"])
    
    cmd.extend(["-i", input_path])
    
    # Use NVENC if available, otherwise use faster CPU preset
    if USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC):
        cmd.extend(["-c:v", PREFERRED_NVENC_CODEC, "-rc", "vbr_hq", "-cq", "20", "-b:v", "0", 
                   "-preset", NVENC_PRESET_SPEED, "-pix_fmt", "yuv420p", "-profile:v", "high"])
    else:
        cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", 
                   "-pix_fmt", "yuv420p", "-profile:v", "high"])
    
    cmd.extend(["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", output_path])
    
    if log: log(f"[ffmpeg] Re-encoding to: {output_path} (GPU={'NVENC' if USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC) else 'No'})")
    try:
        subprocess.check_call(cmd)
        if log: log("[ffmpeg] Re-encode completed.")
        return True
    except subprocess.CalledProcessError as e:
        if log: log(f"[ffmpeg] Re-encode failed: {e}")
        return False

def probe_file_with_ffmpeg(path):
    cmd = ["ffmpeg", "-hide_banner", "-i", path]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = proc.communicate(timeout=30)
    except Exception as e:
        return False, f"Probe error: {e}"
    bad_signals = ["Invalid data found", "moov atom not found", "Error while decoding", "corrupt", "missing"]
    for sig in bad_signals:
        if sig.lower() in err.lower():
            return False, err
    return True, err

def pre_render_foreground_ffmpeg(input_path, out_path, crop_x, crop_y, crop_w, crop_h, scale_w, scale_h, fps, use_nvenc, log):
    vf = f"crop={crop_w}:{crop_h}:{crop_x}:{crop_y},scale={scale_w}:{scale_h}:flags=lanczos"
    
    # Build command with hardware acceleration if available
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    
    # Add hardware decoding for speed (without output format to maintain filter compatibility)
    if USE_HARDWARE_DECODING and use_nvenc:
        cmd.extend(["-hwaccel", "cuda"])
    
    cmd.extend(["-i", input_path, "-an", "-vf", vf, "-r", str(int(fps))])
    
    if use_nvenc and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC):
        codec = PREFERRED_NVENC_CODEC
        # Use faster preset for pre-render (p2 instead of p4)
        vparams = ["-c:v", codec, "-rc", "vbr_hq", "-cq", "22", "-b:v", "0", "-preset", "p2"]
    else:
        codec = "libx264"
        vparams = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "22"]  # Changed from veryfast to ultrafast
    
    cmd.extend(vparams + ["-pix_fmt", "yuv420p", out_path])
    
    if log: log(f"[ffmpeg] Pre-render starting -> {os.path.basename(out_path)} (nvenc={use_nvenc}, hwaccel={USE_HARDWARE_DECODING and use_nvenc})")
    try:
        subprocess.check_call(cmd)
        if log: log(f"[ffmpeg] Pre-render completed: {out_path}")
        return True
    except subprocess.CalledProcessError as e:
        if log:
            log(f"[ffmpeg] Pre-render FAILED (return code {e.returncode}).")
            log(" ".join(cmd))
            log(str(e))
        return False
    except Exception as e:
        if log: log(f"[ffmpeg] Pre-render exception: {e}")
        return False

def make_unique_output_path(requested_path, log=None):
    base = os.path.abspath(requested_path)
    dirn, fname = os.path.split(base)
    name, ext = os.path.splitext(fname)
    candidate = base
    if candidate in CREATED_OUTPUTS or os.path.exists(candidate):
        i = 1
        while True:
            new_name = f"{name}_{i}{ext}"
            candidate = os.path.join(dirn, new_name)
            if candidate not in CREATED_OUTPUTS and not os.path.exists(candidate):
                break
            i += 1
        if log: log(f"[output] '{requested_path}' exists -> using '{candidate}' instead")
    else:
        if log: log(f"[output] Using requested output: {candidate}")
    CREATED_OUTPUTS.add(candidate)
    return candidate

# ----------------- Whisper robust loading & transcription -----------------
def _find_and_remove_corrupted_whisper_models(model_name, log=None):
    removed = []
    possible_roots = [
        os.path.join(os.path.expanduser("~"), ".cache", "whisper"),
        os.path.join(os.path.expanduser("~"), ".cache"),
        os.path.join(os.getcwd(), "models"),
        os.path.join(os.getcwd(), ".cache"),
    ]
    possible_roots.append(os.path.expanduser("~"))
    lower_name = model_name.lower()
    for root in possible_roots:
        if not os.path.isdir(root):
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            for fn in filenames:
                fn_lower = fn.lower()
                full = os.path.join(dirpath, fn)
                if lower_name in fn_lower and (fn_lower.endswith(".pt") or fn_lower.endswith(".bin") or ".part" in fn_lower or fn_lower.endswith(".tmp")):
                    try:
                        os.remove(full)
                        removed.append(full)
                        if log: log(f"[whisper-cleanup] removed: {full}")
                    except Exception as e:
                        if log: log(f"[whisper-cleanup] failed to remove {full}: {e}")
    return removed

def _load_whisper_model_with_retries(model_name="large-v3", tries=3, log=None):
    last_exc = None
    
    # Detect GPU availability for Whisper with improved detection
    device = "cpu"  # Default to CPU
    cuda_available = False
    
    try:
        cuda_available = torch.cuda.is_available()
        if cuda_available:
            device_count = torch.cuda.device_count()
            if device_count > 0:
                device = "cuda"
                if log:
                    gpu_name = torch.cuda.get_device_name(0)
                    log(f"[whisper] GPU detected: {gpu_name}")
                    log(f"[whisper] Will use CUDA acceleration for transcription")
            else:
                if log:
                    log(f"[whisper] CUDA available but no GPU devices found - will use CPU")
        else:
            if log:
                log(f"[whisper] CUDA not available in PyTorch - will use CPU (slower)")
                log(f"[whisper] For GPU support, install PyTorch with CUDA: pip install torch --index-url https://download.pytorch.org/whl/cu118")
    except Exception as e:
        if log:
            log(f"[whisper] GPU detection failed ({str(e)}) - will use CPU")
    
    for attempt in range(1, tries + 1):
        try:
            if log: log(f"[whisper] Loading model '{model_name}' on {device.upper()} (attempt {attempt}/{tries})...")
            model = whisper.load_model(model_name, device=device)
            if log: log(f"[whisper] Model '{model_name}' loaded successfully on {device.upper()}.")
            return model, device  # Return both model and device used
        except RuntimeError as e:
            msg = str(e).lower()
            error_str = str(e)
            last_exc = e
            if "sha256" in msg or "checksum" in msg or "downloaded but the sha256" in msg:
                if log: log(f"[whisper] Checksum error for '{model_name}': {e}")
                removed = _find_and_remove_corrupted_whisper_models(model_name, log=log)
                if removed:
                    if log: log(f"[whisper] Removed {len(removed)} suspected corrupted file(s). Retrying download...")
                    time.sleep(1.0 + attempt * 0.5)
                    continue
                else:
                    if log: log("[whisper] Could not find model file(s) to remove — retrying download anyway.")
                    time.sleep(1.0 + attempt * 0.5)
                    continue
            elif "cuda" in msg and device == "cuda":
                # CUDA error - check if it's architecture mismatch
                if "no kernel image" in error_str or ("kernel" in error_str and "sm" in error_str):
                    # Architecture mismatch - PyTorch built without support for this GPU
                    if log:
                        log("[whisper] ========================================")
                        log("[whisper] ERROR: PyTorch Architecture Mismatch!")
                        log("[whisper] ========================================")
                        log("[whisper] PyTorch was built without support for your GPU architecture")
                        log("[whisper] ")
                        log("[whisper] SOLUTION: Reinstall PyTorch with proper GPU support:")
                        log("[whisper]   pip uninstall torch torchvision torchaudio")
                        log("[whisper]   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121")
                        log("[whisper] ")
                        log("[whisper] Or as temporary workaround, using CPU (slower)...")
                        log("[whisper] ========================================")
                    device = "cpu"
                    if attempt < tries:
                        time.sleep(0.5)
                        continue
                else:
                    # Other CUDA error - try falling back to CPU
                    if log: log(f"[whisper] CUDA error loading model: {e}")
                    if log: log(f"[whisper] Falling back to CPU...")
                    device = "cpu"
                    if attempt < tries:
                        time.sleep(0.5)
                        continue
            else:
                if log: log(f"[whisper] RuntimeError loading model '{model_name}': {e}")
                raise
        except Exception as e:
            last_exc = e
            if log: log(f"[whisper] Unexpected error while loading model '{model_name}': {e}")
            time.sleep(0.5 + attempt * 0.5)
            continue
    if last_exc:
        raise last_exc
    raise RuntimeError(f"Could not load whisper model '{model_name}' for unknown reason.")

def transcribe_captions(voice_path, log=None, translate_to=None):
    """
    Transcribe audio to text captions using Whisper, with optional translation.
    
    Args:
        voice_path: Path to audio file
        log: Optional logging function
        translate_to: Target language code for translation (None or 'none' to skip)
    
    Returns:
        List of caption segments
    """
    def _default_log(s):
        try:
            print(s)
        except Exception:
            pass
    log_fn = _default_log if log is None else log
    
    # Use Whisper for transcription
    # Using 'large' (not large-v3) for accurate word-level timestamps needed for caption sync
    # Medium/small models are faster but timestamps not accurate enough, causing caption-voice mismatch
    try:
        model, device = _load_whisper_model_with_retries("large", tries=3, log=log_fn)
    except Exception as e_large:
        log_fn(f"[whisper] Failed to load 'large' model after retries: {e_large}")
        log_fn("[whisper] Falling back to 'medium' model (faster but less accurate timestamps).")
        try:
            model, device = _load_whisper_model_with_retries("medium", tries=2, log=log_fn)
        except Exception as e_medium:
            log_fn(f"[whisper] Failed to load 'medium' model as well: {e_medium}")
            raise RuntimeError("Whisper models unavailable. Verifică conexiunea la internet și spațiul pe disc.") from e_medium
    
    # Show appropriate message based on actual device being used
    if device == "cuda":
        log_fn("[whisper] Transcribing audio with word-level timestamps (5-8 minutes on GPU)...")
    else:
        log_fn("[whisper] Transcribing audio with word-level timestamps (15-20 minutes on CPU)...")
    
    # Enable word_timestamps for precise caption synchronization
    # Use FP16 on GPU for faster inference (2x speedup with minimal quality loss)
    # Only enable FP16 if actually running on GPU
    use_fp16 = (device == "cuda")
    if use_fp16:
        log_fn("[whisper] Using FP16 precision on GPU for faster transcription (2x speedup)")
    
    result = model.transcribe(voice_path, word_timestamps=True, fp16=use_fp16)
    log_fn("[whisper] Transcription finished.")
    segments = result["segments"]
    
    # Apply translation if requested
    # Translation is enabled when translate_to is specified and not 'none'
    if translate_to and translate_to != 'none':
        log_fn(f"[TRANSCRIBE] Translating to {translate_to}...")
        segments = translate_segments(segments, target_language=translate_to, log=log_fn)
    
    return segments

# ----------------- caption generation -----------------
def generate_caption_image(text, preferred_font=None, log=None):
    """
    Generate caption image with visible background and proper transparency settings.
    
    FIXED ISSUES:
    - Changed bubble background from transparent (0,0,0,0) to semi-opaque white (255,255,255,220)
    - Removed duplicate shadow drawing code
    - Added logging for caption rendering errors
    - Normalized color values to ensure valid RGBA ranges
    """
    try:
        if log:
            log(f"[CAPTION-GEN] ═══════════════════════════════════════════════")
            log(f"[CAPTION-GEN] Starting caption generation")
            log(f"[CAPTION-GEN] Text: '{text[:80]}{'...' if len(text) > 80 else ''}'")
            log(f"[CAPTION-GEN] Text length: {len(text)} characters")
            log(f"[CAPTION-GEN] Preferred font: {preferred_font or 'default'}")
    except Exception:
        pass
    
    try:
        font = load_preferred_font_cached(preferred_font or CAPTION_FONT_PREFERRED, CAPTION_FONT_SIZE, log=log)
        try:
            if log:
                font_info = f"{LOADED_FONT_PATH}" if LOADED_FONT_PATH else "unknown"
                log(f"[CAPTION-GEN] Font loaded successfully: {font_info}")
                log(f"[CAPTION-GEN] Font size: {CAPTION_FONT_SIZE}px")
        except Exception:
            pass
    except Exception as e:
        try:
            if log:
                log(f"[CAPTION-GEN ERROR] Failed to load font: {e}")
        except Exception:
            pass
        raise
    
    text = normalize_text(text)
    
    def measure_text(draw, s):
        try:
            l, t, r, b = draw.textbbox((0,0), s, font=font)
            return (r-l, b-t)
        except Exception:
            return font.getsize(s)
    
    tmp_img = Image.new("RGBA", (WIDTH, 10), (0,0,0,0))
    draw_tmp = ImageDraw.Draw(tmp_img)
    max_text_width = WIDTH - 160
    words = text.split()
    lines, current = [], ""
    for w in words:
        test = (current + " " + w).strip()
        w_width, _ = measure_text(draw_tmp, test)
        if w_width <= max_text_width:
            current = test
        else:
            if current: lines.append(current)
            current = w
    if current: lines.append(current)
    
    line_heights = []
    max_line_w = 0
    for line in lines:
        lw, lh = measure_text(draw_tmp, line)
        line_heights.append(lh)
        max_line_w = max(max_line_w, lw)
    
    line_spacing = int(CAPTION_FONT_SIZE * 0.18)
    padding_x = 24; padding_y = 24  # increased vertical padding to avoid bottom cutoff
    extra_bottom_margin = int(CAPTION_FONT_SIZE * 0.35)  # extra transparent margin at bottom
    total_height = sum(line_heights) + line_spacing*(len(lines)-1) + padding_y*2 + extra_bottom_margin
    bubble_width = min(WIDTH - 80, max_line_w + padding_x*2)
    
    try:
        if log:
            log(f"[CAPTION-GEN] Image dimensions: {WIDTH}x{total_height + 8 + extra_bottom_margin}")
            log(f"[CAPTION-GEN] Number of lines: {len(lines)}")
            log(f"[CAPTION-GEN] Bubble width: {bubble_width}px, height: {total_height - extra_bottom_margin}px")
            log(f"[CAPTION-GEN] Padding: x={padding_x}px, y={padding_y}px")
    except Exception:
        pass
    
    img = Image.new("RGBA", (WIDTH, total_height + 8 + extra_bottom_margin), (0,0,0,0))
    draw = ImageDraw.Draw(img)
    bubble_x0 = (WIDTH - bubble_width)//2; bubble_x1 = bubble_x0 + bubble_width
    bubble_y0 = 4; bubble_y1 = bubble_y0 + (total_height - extra_bottom_margin)  # bubble excludes the extra bottom margin
    
    # Draw shadow (FIXED: removed duplicate code)
    shadow = Image.new("RGBA", (bubble_width, total_height - extra_bottom_margin), (0,0,0,0))
    sd = ImageDraw.Draw(shadow)
    try:
        radius = int(padding_y*0.8)
        sd.rounded_rectangle([0,0,bubble_width,total_height - extra_bottom_margin], radius=radius, fill=(0,0,0,200))
        shadow = shadow.filter(ImageFilter.GaussianBlur(radius=6))
        img.paste(shadow, (bubble_x0+0, bubble_y0+2), shadow)
        try:
            if log:
                log(f"[CAPTION-GEN] Shadow drawn successfully with rounded corners, radius={radius}px")
        except Exception:
            pass
    except Exception as e:
        try:
            if log:
                log(f"[CAPTION-GEN WARNING] Rounded shadow failed, using rectangle: {e}")
        except Exception:
            pass
        sd.rectangle([0,0,bubble_width,total_height - extra_bottom_margin], fill=(0,0,0,140))
        sd_im = shadow.filter(ImageFilter.GaussianBlur(radius=6))
        img.paste(sd_im, (bubble_x0+0, bubble_y0+2), sd_im)
    
    # Draw bubble background - TRANSPARENT (user requested no white box, just text)
    # Background is now transparent - text visibility comes from strong stroke outline
    bubble_fill = (0, 0, 0, 0)  # Fully transparent - no white box behind text
    try:
        draw.rounded_rectangle([bubble_x0,bubble_y0,bubble_x1,bubble_y1], radius=int(padding_y*0.8), fill=bubble_fill)
        try:
            if log:
                log(f"[CAPTION-GEN] Background: TRANSPARENT (no white box - text only with stroke)")
        except Exception:
            pass
    except Exception as e:
        try:
            if log:
                log(f"[CAPTION-GEN WARNING] Rounded bubble failed, using rectangle: {e}")
        except Exception:
            pass
        draw.rectangle([bubble_x0,bubble_y0,bubble_x1,bubble_y1], fill=bubble_fill)
    
    # Normalize and validate color values (FIXED: ensure colors are in valid range)
    def normalize_color(color):
        """Ensure RGBA color tuple is in valid range (0-255)."""
        return tuple(max(0, min(255, int(c))) for c in color)
    
    try:
        stroke_w = int(CAPTION_STROKE_WIDTH)
    except Exception:
        stroke_w = max(1, int(CAPTION_FONT_SIZE * 0.05))
    
    # Increase stroke width for better visibility without white background
    # Make stroke at least 3 pixels for good visibility
    stroke_w = max(3, stroke_w)
    
    try:
        stroke_fill = normalize_color(tuple(CAPTION_STROKE_COLOR))
    except Exception:
        stroke_fill = (0,0,0,150)
    
    # Make stroke fully opaque (255 alpha) for better visibility without background
    stroke_fill = (stroke_fill[0], stroke_fill[1], stroke_fill[2], 255)
    
    try:
        text_fill = normalize_color(tuple(CAPTION_TEXT_COLOR))
    except Exception:
        text_fill = (255,255,255,255)
    
    try:
        if log:
            log(f"[CAPTION-GEN] Text color: RGBA{text_fill}")
            log(f"[CAPTION-GEN] Stroke color: RGBA{stroke_fill}")
            log(f"[CAPTION-GEN] Stroke width: {stroke_w}px (enhanced for visibility)")
    except Exception:
        pass
    
    # Draw text
    y = bubble_y0 + padding_y
    for line_idx, line in enumerate(lines):
        lw, lh = measure_text(draw, line)
        x = bubble_x0 + (bubble_width - lw)//2
        try:
            draw.text((x,y), line, font=font, fill=text_fill, stroke_width=stroke_w, stroke_fill=stroke_fill)
        except TypeError as e:
            try:
                if log:
                    log(f"[CAPTION-GEN WARNING] stroke_width not supported, using manual stroke: {e}")
            except Exception:
                pass
            # Fallback for older Pillow versions
            offs = [(dx, dy) for dx in (-stroke_w,0,stroke_w) for dy in (-stroke_w,0,stroke_w)]
            for dx, dy in offs:
                if dx==0 and dy==0: continue
                draw.text((x+dx, y+dy), line, font=font, fill=stroke_fill)
            draw.text((x,y), line, font=font, fill=text_fill)
        except Exception as e:
            try:
                if log:
                    log(f"[CAPTION-GEN ERROR] Failed to draw text line {line_idx}: {e}")
            except Exception:
                pass
            raise
        y += lh + line_spacing
    
    try:
        if log:
            log(f"[CAPTION-GEN] ✓ Caption image generated successfully!")
            log(f"[CAPTION-GEN] Final image size: {img.size[0]}x{img.size[1]}px")
            log(f"[CAPTION-GEN] ═══════════════════════════════════════════════")
    except Exception:
        pass
    
    return img
# ----------------- preview helpers (with timeline support) -----------------
def extract_and_scale_frame(video_path, time_sec=None, desired_width=360):
    # video_path may be a path (str) or a VideoFileClip instance. If it's a clip, reuse it.
    created_clip = False
    if isinstance(video_path, VideoFileClip):
        clip = video_path
    else:
        clip = VideoFileClip(video_path)
        created_clip = True
    if time_sec is None:
        t = min(max(0.001, clip.duration / 2.0), clip.duration - 0.001)
    else:
        t = min(max(0.0, float(time_sec)), max(0.001, clip.duration - 0.001))
    frame = clip.get_frame(t)
    if created_clip:
        try:
            clip.close()
        except Exception:
            pass
    img = Image.fromarray(frame).convert("RGB")
    w, h = img.size
    scale = desired_width / w
    new_w = desired_width
    new_h = int(round(h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    return img, scale

def overlay_crop_on_image(base_img, top_ratio, bottom_ratio, bar_color=(0,0,0,140), line_color=(0,0,0,255)):
    img_rgba = base_img.convert("RGBA")
    w, h = img_rgba.size
    top_y = int(round(h * top_ratio))
    bottom_y = int(round(h * (1.0 - bottom_ratio)))
    if top_y >= bottom_y - 2:
        if top_y > h//2:
            top_y = max(0, bottom_y - 2)
        else:
            bottom_y = min(h, top_y + 2)
    overlay = Image.new("RGBA", (w, h), (0,0,0,0))
    draw = ImageDraw.Draw(overlay)
    if top_y > 0:
        draw.rectangle([0, 0, w, top_y], fill=bar_color)
    if bottom_y < h:
        draw.rectangle([0, bottom_y, w, h], fill=bar_color)
    line_thickness = max(1, int(round(2 * (w/360))))
    draw.rectangle([0, top_y-line_thickness//2, w, top_y+line_thickness//2], fill=line_color)
    draw.rectangle([0, bottom_y-line_thickness//2, w, bottom_y+line_thickness//2], fill=line_color)
    composed = Image.alpha_composite(img_rgba, overlay)
    return composed

# ----------------- Save / Load crop settings -----------------
def save_crop_settings(top_pct, bottom_pct, filepath=CROP_SETTINGS_FILE):
    data = {"top_pct": float(top_pct), "bottom_pct": float(bottom_pct)}
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True, filepath
    except Exception as e:
        return False, str(e)

def load_crop_settings(filepath=CROP_SETTINGS_FILE):
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception:
        return None

# ----------------- Export composer with monitoring & fallback -----------------
def _make_ffmpeg_params_for_codec(codec):
    """
    Get FFmpeg encoding parameters for the specified codec.
    
    Note: These are OUTPUT encoding parameters only. MoviePy passes these to FFmpeg
    for the final encoding step. Hardware decoding (-hwaccel) doesn't work here
    because MoviePy reads/processes frames in Python before encoding.
    
    The main export bottleneck is MoviePy's Python frame processing, not encoding.
    GPU acceleration is already being used optimally via:
    - pre_render_foreground_ffmpeg() uses -hwaccel cuda for foreground (works!)
    - NVENC encoding below (works!)
    """
    if codec in ("h264_nvenc", "hevc_nvenc"):
        # GPU encoding with NVENC - optimized for speed and quality
        return [
            "-rc", "vbr_hq",           # Variable bitrate, high quality
            "-cq", "19",               # Constant quality level (lower = better)
            "-b:v", "0",               # Let CQ control quality
            "-preset", NVENC_PRESET_SPEED,  # p4 for speed (configurable)
            "-pix_fmt", "yuv420p",     # Standard pixel format
            "-profile:v", "high",      # H.264 High profile
            "-movflags", "+faststart"  # Web streaming optimization
        ]
    else:
        # CPU encoding with libx264 - fallback option
        return [
            "-preset", "ultrafast",    # Fastest CPU preset
            "-crf", "20",              # Constant quality
            "-pix_fmt", "yuv420p",     # Standard pixel format
            "-movflags", "+faststart"  # Web streaming optimization
        ]

# ----------------- FFmpeg Fast Export Functions -----------------

def _calculate_text_lines(text, max_chars=40, words_per_line=None):
    """
    Calculate line breaks for text to fit within max_chars per line or words per line.
    Breaks at word boundaries when possible.
    
    Args:
        text: String to wrap
        max_chars: Maximum characters per line (used if words_per_line is None)
        words_per_line: Maximum words per line (overrides max_chars if provided)
        
    Returns:
        List of text lines
    """
    # Handle empty or whitespace-only text
    if not text or not text.strip():
        return [""]
    
    words = text.split()
    
    # If words_per_line is specified, group by word count instead of characters
    if words_per_line and words_per_line > 0:
        if not words:
            return [""]
        lines = []
        for i in range(0, len(words), words_per_line):
            line_words = words[i:i + words_per_line]
            lines.append(' '.join(line_words))
        return lines
    
    # Otherwise use character-based wrapping (original logic)
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        word_len = len(word)
        # +1 for space between words
        needed = word_len if not current_line else current_length + 1 + word_len
        
        if needed <= max_chars:
            current_line.append(word)
            current_length = needed
        else:
            # Start new line
            if current_line:
                lines.append(' '.join(current_line))
            # Handle very long words
            if word_len > max_chars:
                lines.append(word[:max_chars])
                current_line = [word[max_chars:]] if len(word) > max_chars else []
                current_length = len(word[max_chars:]) if len(word) > max_chars else 0
            else:
                current_line = [word]
                current_length = word_len
    
    if current_line:
        lines.append(' '.join(current_line))
    
    return lines if lines else [text]


def _escape_ffmpeg_text(text):
    """
    Escape special characters for FFmpeg drawtext filter.
    
    Args:
        text: String to escape
        
    Returns:
        Escaped string safe for FFmpeg
    """
    # FFmpeg drawtext special characters that need escaping
    text = text.replace('\\', '\\\\')  # Backslash first!
    text = text.replace("'", "\\'")    # Single quote
    text = text.replace(':', '\\:')    # Colon
    text = text.replace('%', '\\%')    # Percent
    text = text.replace('[', '\\[')    # Square brackets
    text = text.replace(']', '\\]')
    return text


def _rgba_to_hex(rgba_tuple):
    """
    Convert RGBA tuple to hex color string for FFmpeg.
    
    Args:
        rgba_tuple: (R, G, B, A) tuple with values 0-255
        
    Returns:
        Hex color string like '#RRGGBB' or '0xRRGGBB'
    """
    try:
        r, g, b = int(rgba_tuple[0]), int(rgba_tuple[1]), int(rgba_tuple[2])
        # FFmpeg accepts #RRGGBB or 0xRRGGBB format
        return f"0x{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "0xFFFFFF"  # Default to white


def _generate_ass_subtitle_file(caption_segments, output_path, font_name="Arial", fontsize=56, 
                                text_color_rgba=(255, 255, 0, 255), stroke_width=3):
    """
    Generate an ASS (Advanced SubStation Alpha) subtitle file for word-by-word captions.
    
    Args:
        caption_segments: List of caption dictionaries with 'text', 'start', 'end'
        output_path: Path where to save the .ass file
        font_name: Font name (e.g., "Bangers", "Arial")
        fontsize: Font size in pixels
        text_color_rgba: Text color as RGBA tuple
        stroke_width: Outline/border width
        
    Returns:
        Path to generated ASS file
    """
    import re
    
    # Convert RGBA to ASS color format (BGR in hex with alpha)
    # ASS uses &HAABBGGRR format
    r, g, b, a = text_color_rgba
    # Convert alpha: 255 = fully opaque = 00, 0 = fully transparent = FF
    alpha_hex = f"{255 - int(a):02X}"
    text_color_ass = f"&H{alpha_hex}{b:02X}{g:02X}{r:02X}"
    outline_color_ass = "&H00000000"  # Black outline, fully opaque
    
    # ASS file header
    ass_content = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
PlayResX: 1080
PlayResY: 1920
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{fontsize},{text_color_ass},&H00FFFFFF,{outline_color_ass},&H00000000,0,0,0,0,100,100,0,0,1,{stroke_width},0,2,10,10,150,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    # Add each caption as a dialogue line
    for segment in caption_segments:
        # Convert time to ASS format (H:MM:SS.CS where CS is centiseconds)
        start_time = segment['start']
        end_time = segment['end']
        
        start_h = int(start_time // 3600)
        start_m = int((start_time % 3600) // 60)
        start_s = int(start_time % 60)
        start_cs = int((start_time % 1) * 100)
        start_str = f"{start_h}:{start_m:02d}:{start_s:02d}.{start_cs:02d}"
        
        end_h = int(end_time // 3600)
        end_m = int((end_time % 3600) // 60)
        end_s = int(end_time % 60)
        end_cs = int((end_time % 1) * 100)
        end_str = f"{end_h}:{end_m:02d}:{end_s:02d}.{end_cs:02d}"
        
        # Escape text for ASS (replace newlines with \N)
        text = segment['text'].replace('\n', '\\N')
        
        ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"
    
    # Write ASS file
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    
    return output_path


def _build_caption_drawtext_filter(caption_text, start_time, end_time, video_width, video_height, 
                                   fontsize=56, font_path=None, text_color="0xFFFFFF", 
                                   stroke_color="0x000000", stroke_width=3, words_per_line=None):
    """
    Build FFmpeg drawtext filter for a single caption with custom styling.
    
    Args:
        caption_text: Text to display
        start_time: Start time in seconds
        end_time: End time in seconds
        video_width: Video width in pixels
        video_height: Video height in pixels
        fontsize: Font size in pixels
        font_path: Path to custom font file (optional)
        text_color: Text color in hex format (e.g., '0xFFFFFF')
        stroke_color: Stroke/border color in hex format (e.g., '0x000000')
        stroke_width: Stroke width in pixels
        words_per_line: Maximum words per line (optional, overrides character-based wrapping)
        
    Returns:
        FFmpeg drawtext filter string
    """
    # Calculate text wrapping with word-based grouping if specified
    lines = _calculate_text_lines(caption_text, max_chars=40, words_per_line=words_per_line)
    
    # Escape text for FFmpeg
    escaped_lines = [_escape_ffmpeg_text(line) for line in lines]
    text_with_newlines = '\\n'.join(escaped_lines)
    
    # Position: bottom-center with safer offset from bottom
    # Use h-150 instead of video_height-100 to ensure captions stay within bounds
    y_position = "h-150"  # 150px from bottom for multi-line text (dynamic, works with any height)
    
    # Build drawtext filter with custom styling
    filter_parts = [
        f"drawtext=text='{text_with_newlines}'",
        f"fontsize={fontsize}",
        f"fontcolor={text_color}",
        f"borderw={stroke_width}",
        f"bordercolor={stroke_color}",
        f"x=(w-text_w)/2",  # Center horizontally
        f"y={y_position}",   # Bottom positioning (safe margin)
        f"enable='between(t,{start_time:.3f},{end_time:.3f})'"  # Timing
    ]
    
    # Add custom font if provided
    if font_path and os.path.exists(font_path):
        # Escape font path for FFmpeg (handle spaces and special chars)
        escaped_font_path = font_path.replace('\\', '/').replace(':', '\\:')
        filter_parts.insert(1, f"fontfile='{escaped_font_path}'")
    
    return ':'.join(filter_parts)


def _build_all_caption_filters(caption_segments, video_width, video_height, 
                               font_path=None, text_color="0xFFFFFF", 
                               stroke_color="0x000000", stroke_width=3, words_per_line=None):
    """
    Build all caption drawtext filters and chain them together with custom styling.
    
    Args:
        caption_segments: List of caption dictionaries with 'text', 'start', 'end'
        video_width: Video width in pixels
        video_height: Video height in pixels
        font_path: Path to custom font file (optional)
        text_color: Text color in hex format
        stroke_color: Stroke color in hex format
        stroke_width: Stroke width in pixels
        words_per_line: Maximum words per line (optional)
        
    Returns:
        Complete filter_complex string for all captions
    """
    if not caption_segments:
        return None
    
    filters = []
    
    for i, segment in enumerate(caption_segments):
        caption_filter = _build_caption_drawtext_filter(
            caption_text=segment['text'],
            start_time=segment['start'],
            end_time=segment['end'],
            video_width=video_width,
            video_height=video_height,
            font_path=font_path,
            text_color=text_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            words_per_line=words_per_line  # Pass through words_per_line
        )
        filters.append(caption_filter)
    
    # Chain all filters together
    return ','.join(filters)


def _build_ffmpeg_effect_filters(effect_settings, log_fn=None):
    """
    Build FFmpeg filter string for video effects (to match MoviePy effects).
    
    FFmpeg equivalents:
    - Sharpness: unsharp filter
    - Saturation: eq filter (saturation parameter)
    - Contrast: eq filter (contrast parameter)
    - Brightness: eq filter (brightness parameter)
    - Vintage: colorbalance + noise filters
    
    Args:
        effect_settings: Dictionary with effect settings
        log_fn: Optional logging function
        
    Returns:
        FFmpeg filter string or empty string if no effects
    """
    if not effect_settings:
        return ""
    
    effect_filters = []
    active_effects = []
    
    # Check for sharpness effect (Resilience)
    if effect_settings.get('effect_sharpness', False):
        intensity = effect_settings.get('effect_sharpness_intensity', 1.5)
        # unsharp filter: luma_msize_x:luma_msize_y:luma_amount
        # intensity 1.5 -> luma_amount 1.5, intensity 2.0 -> luma_amount 2.0
        luma_amount = min(5.0, max(0.5, intensity))  # Clamp between 0.5 and 5.0
        effect_filters.append(f"unsharp=5:5:{luma_amount}")
        active_effects.append(f"Sharpness ({intensity}x)")
    
    # Build eq filter parameters for saturation, contrast, brightness
    eq_params = []
    
    # Check for saturation effect (Vibrance)
    if effect_settings.get('effect_saturation', False):
        intensity = effect_settings.get('effect_saturation_intensity', 1.3)
        # eq saturation: 1.0 = normal, >1.0 = more saturated
        saturation = min(3.0, max(0.0, intensity))
        eq_params.append(f"saturation={saturation}")
        active_effects.append(f"Saturation ({intensity}x)")
    
    # Check for contrast effect (HDR)
    if effect_settings.get('effect_contrast', False):
        intensity = effect_settings.get('effect_contrast_intensity', 1.2)
        # eq contrast: 1.0 = normal, >1.0 = more contrast
        contrast = min(2.0, max(-2.0, intensity))
        eq_params.append(f"contrast={contrast}")
        active_effects.append(f"Contrast ({intensity}x)")
    
    # Check for brightness effect
    if effect_settings.get('effect_brightness', False):
        intensity = effect_settings.get('effect_brightness_intensity', 1.15)
        # eq brightness: 0.0 = normal, >0 = brighter, <0 = darker
        # Convert multiplier to additive: 1.15 -> 0.15
        brightness = min(1.0, max(-1.0, intensity - 1.0))
        eq_params.append(f"brightness={brightness}")
        active_effects.append(f"Brightness ({intensity}x)")
    
    # Add eq filter if any eq parameters were set
    if eq_params:
        effect_filters.append(f"eq={':'.join(eq_params)}")
    
    # Check for vintage effect
    if effect_settings.get('effect_vintage', False):
        grain_intensity = effect_settings.get('effect_vintage_intensity', 0.3)
        # Vintage effect: sepia tone via colorbalance + optional noise
        # colorbalance for warm sepia tones: increase red/yellow in highlights/midtones
        # Note: intensity 0.3 -> moderate vintage look
        shadow_red = min(1.0, max(-1.0, grain_intensity * 0.3))
        midtone_red = min(1.0, max(-1.0, grain_intensity * 0.2))
        highlight_yellow = min(1.0, max(-1.0, grain_intensity * 0.15))
        effect_filters.append(f"colorbalance=rs={shadow_red}:gs=-{shadow_red*0.5}:bs=-{shadow_red}:rm={midtone_red}:gm=0:bm=-{midtone_red*0.5}:rh=0:gh={highlight_yellow}:bh=-{highlight_yellow}")
        active_effects.append(f"Vintage ({grain_intensity}x)")
    
    # Log active effects
    if log_fn and active_effects:
        log_fn(f"[EXPORT] Applying FFmpeg effects: {', '.join(active_effects)}")
    
    # Combine all effect filters
    if effect_filters:
        return ','.join(effect_filters)
    return ""


def _export_with_ffmpeg_filters(bg_path, fg_path, caption_segments, audio_path, output_path, video_width, video_height, log_fn, effect_settings=None, mirror_video=False, target_duration=None):
    """
    Fast export using pure FFmpeg complex filters.
    2-3x faster than MoviePy's Python frame processing.
    
    Args:
        bg_path: Path to background image/video
        fg_path: Path to foreground video
        caption_segments: List of caption dictionaries
        audio_path: Path to audio file
        output_path: Path for output video
        video_width: Video width
        video_height: Video height
        log_fn: Logging function
        effect_settings: Dictionary with video effect settings (sharpness, saturation, contrast, etc.)
        mirror_video: Whether to apply horizontal flip to the foreground video
        target_duration: Target duration for the final video (for speed adjustment)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        log_fn("[EXPORT] ═══════════════════════════════════════════════════")
        log_fn("[EXPORT] Using fast FFmpeg filter-based export...")
        log_fn(f"[EXPORT] Building filter chain for {len(caption_segments)} caption segments...")
        if mirror_video:
            log_fn("[EXPORT] Mirror/flip: enabled")
        if target_duration:
            log_fn(f"[EXPORT] Target duration: {target_duration:.2f}s")
        
        # Get current font and color settings from globals
        try:
            font_path = globals().get('LOADED_FONT_PATH', None)
            text_color_rgba = globals().get('CAPTION_TEXT_COLOR', (255, 255, 255, 255))
            stroke_width = globals().get('CAPTION_STROKE_WIDTH', 3)
            words_per_caption = globals().get('WORDS_PER_CAPTION', None)  # Get words per caption setting
            
            # Convert colors to hex for FFmpeg
            text_color_hex = _rgba_to_hex(text_color_rgba)
            stroke_color_hex = "0x000000"  # Black stroke (can be made customizable later)
            
            if font_path:
                log_fn(f"[EXPORT] Using custom font: {font_path}")
            log_fn(f"[EXPORT] Text color: {text_color_hex} (RGBA: {text_color_rgba})")
            log_fn(f"[EXPORT] Stroke width: {stroke_width}px")
            if words_per_caption:
                log_fn(f"[EXPORT] Words per caption: {words_per_caption}")
        except Exception as e:
            log_fn(f"[EXPORT] Warning: Could not get custom settings, using defaults: {e}")
            font_path = None
            text_color_hex = "0xFFFFFF"
            stroke_color_hex = "0x000000"
            stroke_width = 3
            words_per_caption = None
        
        # For many captions (>MAX_DRAWTEXT_CAPTIONS), use subtitle file approach to avoid command line length limits
        # Otherwise use drawtext filters for better compatibility
        use_subtitle_file = len(caption_segments) > MAX_DRAWTEXT_CAPTIONS
        ass_subtitle_path = None
        
        if use_subtitle_file:
            log_fn(f"[EXPORT] Using ASS subtitle file for {len(caption_segments)} captions (efficient for many captions)")
            # Generate ASS subtitle file in temp directory
            import tempfile
            temp_dir = tempfile.mkdtemp(prefix="tiktok_subtitles_")
            ass_subtitle_path = os.path.join(temp_dir, "captions.ass")
            
            # Extract font name from font path
            font_name = "Arial"  # Default
            if font_path and os.path.exists(font_path):
                font_name = os.path.splitext(os.path.basename(font_path))[0]
            
            _generate_ass_subtitle_file(
                caption_segments, 
                ass_subtitle_path,
                font_name=font_name,
                fontsize=56,
                text_color_rgba=text_color_rgba,
                stroke_width=stroke_width
            )
            log_fn(f"[EXPORT] ASS subtitle file generated: {ass_subtitle_path}")
            caption_filters = None
        else:
            log_fn(f"[EXPORT] Using drawtext filters for {len(caption_segments)} captions")
            # Build caption filters with custom styling and words per caption
            caption_filters = _build_all_caption_filters(
                caption_segments, video_width, video_height,
                font_path=font_path,
                text_color=text_color_hex,
                stroke_color=stroke_color_hex,
                stroke_width=stroke_width,
                words_per_line=words_per_caption  # Pass words per caption setting
            )
        
        # Build video effect filters (to match MoviePy effects)
        effect_filter_str = _build_ffmpeg_effect_filters(effect_settings, log_fn)
        
        # Build complete filter chain
        # [0:v] = background, [1:v] = foreground
        # Overlay foreground on background centered (x=(W-w)/2) to fill width and crop equally from both sides
        
        # Build foreground filter chain (apply mirror if needed)
        # Note: When mirroring, we use a labeled intermediate output [fg_flipped]
        # When not mirroring, we directly combine [0:v] and [1:v] in the overlay filter
        # Both approaches work correctly - the mirrored case needs the semicolon to chain filters
        if mirror_video:
            # First apply hflip to foreground [1:v], output as [fg_flipped]
            # Then overlay [fg_flipped] on background [0:v]
            fg_filter = "[1:v]hflip[fg_flipped];[0:v][fg_flipped]"
            log_fn("[EXPORT] ✓ Mirror/flip filter added")
        else:
            # No pre-processing needed, directly overlay foreground [1:v] on background [0:v]
            fg_filter = "[0:v][1:v]"
        
        if use_subtitle_file and ass_subtitle_path:
            # Use ass subtitle filter (burns subtitles into video)
            # Escape path for Windows
            escaped_ass_path = ass_subtitle_path.replace('\\', '/').replace(':', '\\:')
            filter_chain = f"{fg_filter}overlay=x=(W-w)/2:y=(H-h)/2,ass='{escaped_ass_path}'"
        else:
            filter_chain = f"{fg_filter}overlay=x=(W-w)/2:y=(H-h)/2"
            if caption_filters:
                filter_chain += "," + caption_filters
        
        # Add video effects to filter chain (same as MoviePy applies)
        if effect_filter_str:
            filter_chain += "," + effect_filter_str
            log_fn(f"[EXPORT] ✓ Video effects added to FFmpeg filter chain")
        
        # Label the filter output for mapping
        filter_chain += "[vout]"
        
        # Build FFmpeg command
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", bg_path,  # Background (looped image) [0:v]
            "-i", fg_path,                # Foreground video [1:v]
            "-i", audio_path,             # Audio [2:a]
            "-filter_complex", filter_chain,
            "-map", "[vout]",             # Use video from filter_complex output
            "-map", "2:a",                # Use audio from audio file
            "-shortest",                   # End when shortest input ends
            "-c:a", "aac",                # Audio codec
            "-b:a", "192k",               # Audio bitrate
        ]
        
        # Add video encoding parameters
        if USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC):
            log_fn(f"[EXPORT] Using GPU acceleration (NVENC: {PREFERRED_NVENC_CODEC})...")
            cmd.extend([
                "-c:v", PREFERRED_NVENC_CODEC,
                "-rc", "vbr_hq",
                "-cq", "19",
                "-b:v", "0",
                "-preset", NVENC_PRESET_SPEED,
                "-pix_fmt", "yuv420p",
                "-profile:v", "high"
            ])
        else:
            log_fn("[EXPORT] Using CPU encoding (libx264)...")
            cmd.extend([
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "20",
                "-pix_fmt", "yuv420p"
            ])
        
        cmd.extend([
            "-movflags", "+faststart",
            output_path
        ])
        
        log_fn("[EXPORT] Executing FFmpeg command...")
        log_fn(f"[EXPORT] Full command: {' '.join(cmd)}")
        
        # Run FFmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600  # 10 minute timeout
        )
        
        if result.returncode == 0:
            log_fn("[EXPORT] ✅ Fast FFmpeg export completed successfully!")
            return True
        else:
            log_fn(f"[EXPORT] ❌ FFmpeg failed with return code {result.returncode}")
            log_fn(f"[EXPORT] FFmpeg stderr output:")
            log_fn(f"{result.stderr[-1500:]}")  # Show last 1500 chars of error
            return False
            
    except Exception as e:
        log_fn(f"[EXPORT] ❌ FFmpeg export exception: {e}")
        import traceback
        log_fn(f"[EXPORT] Traceback: {traceback.format_exc()}")
        return False


# ----------------- Video Effects (CapCut-style) -----------------
def apply_video_effects(frame, effect_settings):
    """
    Apply CapCut-style effects to a video frame.
    
    Args:
        frame: numpy array or PIL Image representing the frame
        effect_settings: dict containing effect parameters
        
    Returns:
        Modified frame as numpy array or PIL Image (same type as input)
    """
    import numpy as np
    
    # Convert to PIL if needed
    is_numpy = isinstance(frame, np.ndarray)
    if is_numpy:
        img = Image.fromarray(frame.astype('uint8'), 'RGB')
    else:
        img = frame
    
    # Apply Sharpness/Resilience effect
    if effect_settings.get('effect_sharpness', False):
        intensity = effect_settings.get('effect_sharpness_intensity', 1.5)
        sharpness = ImageEnhance.Sharpness(img)
        img = sharpness.enhance(intensity)
    
    # Apply Saturation/Vibrance effect
    if effect_settings.get('effect_saturation', False):
        intensity = effect_settings.get('effect_saturation_intensity', 1.3)
        color = ImageEnhance.Color(img)
        img = color.enhance(intensity)
    
    # Apply Contrast/HDR effect
    if effect_settings.get('effect_contrast', False):
        intensity = effect_settings.get('effect_contrast_intensity', 1.2)
        contrast = ImageEnhance.Contrast(img)
        img = contrast.enhance(intensity)
    
    # Apply Brightness effect
    if effect_settings.get('effect_brightness', False):
        intensity = effect_settings.get('effect_brightness_intensity', 1.15)
        brightness = ImageEnhance.Brightness(img)
        img = brightness.enhance(intensity)
    
    # Apply Vintage/Film Grain effect
    if effect_settings.get('effect_vintage', False):
        grain_intensity = effect_settings.get('effect_vintage_intensity', 0.3)
        # Add film grain noise
        width, height = img.size
        noise = np.random.normal(0, grain_intensity * 25, (height, width, 3))
        img_array = np.array(img).astype('float')
        img_array = np.clip(img_array + noise, 0, 255)
        img = Image.fromarray(img_array.astype('uint8'), 'RGB')
        
        # Apply slight sepia tone for vintage look
        sepia_r = np.array([[0.393 + 0.607 * (1 - grain_intensity), 0.769 - 0.769 * (1 - grain_intensity), 0.189 - 0.189 * (1 - grain_intensity)]])
        sepia_g = np.array([[0.349 - 0.349 * (1 - grain_intensity), 0.686 + 0.314 * (1 - grain_intensity), 0.168 - 0.168 * (1 - grain_intensity)]])
        sepia_b = np.array([[0.272 - 0.272 * (1 - grain_intensity), 0.534 - 0.534 * (1 - grain_intensity), 0.131 + 0.869 * (1 - grain_intensity)]])
        
        img_array = np.array(img)
        r = np.dot(img_array, sepia_r.T)
        g = np.dot(img_array, sepia_g.T)
        b = np.dot(img_array, sepia_b.T)
        sepia_img = np.dstack([r, g, b])
        img = Image.fromarray(np.clip(sepia_img, 0, 255).astype('uint8'), 'RGB')
    
    # Convert back to numpy if needed
    if is_numpy:
        return np.array(img)
    return img

def compose_final_video_with_static_blurred_bg(video_clip, audio_clip, caption_segments, output_path, preferred_font=None, log=None, blur_radius=STATIC_BG_BLUR_RADIUS, bg_scale_extra=BG_SCALE_EXTRA, dim_factor=DIM_FACTOR, words_per_caption=2, effect_settings=None, pre_rendered_fg_path=None, mirror_video=False, target_duration=None):
    """
    Compose final video with blurred background and caption overlays.
    
    FIXED ISSUES:
    - Removed duplicated and nested caption generation loops
    - Fixed alpha channel handling for caption masks
    - Added logging for caption composition errors
    - Verified caption layer creation and positioning
    - Ensured captions are properly composited onto final video
    
    Args:
        pre_rendered_fg_path: Optional path to pre-rendered foreground video for fast FFmpeg export
        mirror_video: Whether to apply horizontal flip to the video
        target_duration: Target duration for the final video (for speed adjustment in FFmpeg)
    """
    try:
        log("Composing final video (with monitored export).")
    except Exception:
        print("Composing final video (no log callable).")
    
    try:
        log(f"[compose] Starting composition with {len(caption_segments)} caption segments")
        if pre_rendered_fg_path:
            log(f"[compose] Pre-rendered foreground available: {pre_rendered_fg_path}")
        if mirror_video:
            log(f"[compose] Mirror video: enabled")
        if target_duration:
            log(f"[compose] Target duration: {target_duration:.2f}s")
    except Exception:
        pass
    
    # build background (static blurred frame)
    t_mid = min(max(0.001, video_clip.duration / 2.0), max(0.001, video_clip.duration - 0.01))
    frame = video_clip.get_frame(t_mid)
    img = Image.fromarray(frame)
    img_w, img_h = img.size
    scale_needed = max(WIDTH / img_w, HEIGHT / img_h) * bg_scale_extra
    new_w = int(img_w * scale_needed)
    new_h = int(img_h * scale_needed)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = max(0, (new_w - WIDTH) // 2)
    top = max(0, (new_h - HEIGHT) // 2)
    img = img.crop((left, top, left + WIDTH, top + HEIGHT))
    img = img.filter(ImageFilter.GaussianBlur(blur_radius))
    img = ImageEnhance.Brightness(img).enhance(dim_factor)
    bg_static = ImageClip(np.array(img)).set_duration(video_clip.duration)
    
    try:
        log(f"[compose] Background created: {WIDTH}x{HEIGHT}, blur={blur_radius}")
    except Exception:
        pass

    # foreground: zoom to fill width (left/right borders) with user-controllable zoom
    # Calculate scale to fill the canvas width while maintaining aspect ratio
    try:
        # Get user's zoom setting
        zoom_factor = globals().get('VIDEO_ZOOM_SCALE', 1.0)
        
        # Scale to fill width (left/right borders)
        scale_w = WIDTH / video_clip.w
        # Apply user's zoom factor
        fg_scale = scale_w * zoom_factor
    except Exception:
        fg_scale = 1.0
    
    # Remove original audio from video clip to prevent duplicate audio
    # Only the mixed_audio (TTS + music) should be used
    fg = video_clip.without_audio().resize(fg_scale).set_position(("center", "center")).set_duration(video_clip.duration)
    
    # Apply video effects (CapCut-style) if enabled
    if effect_settings and any([
        effect_settings.get('effect_sharpness', False),
        effect_settings.get('effect_saturation', False),
        effect_settings.get('effect_contrast', False),
        effect_settings.get('effect_brightness', False),
        effect_settings.get('effect_vintage', False)
    ]):
        try:
            log(f"[EFFECTS] Applying CapCut-style effects to video...")
            active_effects = []
            if effect_settings.get('effect_sharpness'): active_effects.append('Resilience')
            if effect_settings.get('effect_saturation'): active_effects.append('Vibrance')
            if effect_settings.get('effect_contrast'): active_effects.append('HDR')
            if effect_settings.get('effect_brightness'): active_effects.append('Brightness')
            if effect_settings.get('effect_vintage'): active_effects.append('Vintage')
            log(f"[EFFECTS] Active effects: {', '.join(active_effects)}")
            
            # Apply effects to each frame
            fg = fg.fl_image(lambda frame: apply_video_effects(frame, effect_settings))
            log(f"[EFFECTS] ✓ Effects applied successfully")
        except Exception as e:
            log(f"[EFFECTS] Warning: Could not apply effects: {e}")
    
    try:
        log(f"[compose] Foreground scaled: {fg_scale:.3f}x (fills canvas completely)")
    except Exception:
        pass

    # Build caption clips (FIXED: single clean loop, no duplication)
    caption_clips = []
    caption_data_for_ffmpeg = []  # Collect word-group caption data for FFmpeg export
    MIN_GROUP_DURATION = 0.25
    
    # Use the words_per_caption parameter (from UI control)
    tpl = words_per_caption
    
    try:
        log(f"[COMPOSE] Using {tpl} word(s) per caption (CapCut-style)")
    except Exception:
        pass
    
    for seg_idx, segment in enumerate(caption_segments):
        try:
            start_t = float(segment.get("start", segment.get("start_time", 0)))
            end_t = float(segment.get("end", segment.get("end_time", start_t + 3)))
            seg_dur = max(0.05, end_t - start_t)
            text = normalize_text(segment.get("text", "").strip())
            
            if not text:
                try:
                    log(f"[compose WARNING] Segment {seg_idx} has empty text, skipping")
                except Exception:
                    pass
                continue
            
            try:
                log(f"[COMPOSE] ═══════════════════════════════════════════════")
                log(f"[COMPOSE] Processing segment #{seg_idx}")
                log(f"[COMPOSE] Text: '{text[:80]}{'...' if len(text) > 80 else ''}'")
                log(f"[COMPOSE] Time range: {start_t:.2f}s - {end_t:.2f}s (duration: {seg_dur:.2f}s)")
                log(f"[COMPOSE] Preferred font: {preferred_font or 'default'}")
            except Exception:
                pass
            
            # Use word-level timestamps if available (CapCut-style auto-captions)
            # Check if segment has word-level timing data
            word_data = segment.get("words", [])
            
            if word_data:
                # Word-by-word captions like CapCut
                groups_with_timing = []
                for word_idx in range(0, len(word_data), tpl):
                    # Group up to tpl words together
                    word_group = word_data[word_idx:word_idx + tpl]
                    grp_text = " ".join([w.get("word", "").strip() for w in word_group])
                    # Use the start time of the first word and end time of the last word
                    grp_start = word_group[0].get("start", start_t)
                    grp_end = word_group[-1].get("end", end_t)
                    groups_with_timing.append({
                        "text": grp_text,
                        "start": grp_start,
                        "end": grp_end
                    })
            else:
                # Fallback: split text evenly if no word timestamps
                words = text.split()
                groups_with_timing = []
                raw_group_dur = seg_dur / max(1, len(words) // tpl + (1 if len(words) % tpl else 0))
                for i in range(0, len(words), tpl):
                    grp_text = " ".join(words[i:i+tpl])
                    g_start = start_t + (i // tpl) * raw_group_dur
                    g_end = min(end_t, g_start + raw_group_dur)
                    groups_with_timing.append({
                        "text": grp_text,
                        "start": g_start,
                        "end": g_end
                    })
            
            for i, group_data in enumerate(groups_with_timing):
                grp_text = group_data["text"]
                g_start = group_data["start"]
                g_dur = max(MIN_GROUP_DURATION, group_data["end"] - group_data["start"])
                if g_start >= end_t:
                    g_start = max(start_t, end_t - g_dur)
                
                try:
                    try:
                        log(f"[COMPOSE]   Caption group {i+1}/{len(groups_with_timing)}: '{grp_text}'")
                        log(f"[COMPOSE]   Display time: {g_start:.2f}s - {g_start + g_dur:.2f}s (duration: {g_dur:.2f}s)")
                    except Exception:
                        pass
                    
                    # generate PIL image for the caption group (FIXED: proper function call)
                    pil_img = generate_caption_image(grp_text, preferred_font=preferred_font, log=log)
                    if pil_img is None:
                        try:
                            log(f"[COMPOSE ERROR] generate_caption_image returned None for '{grp_text}'")
                        except Exception:
                            pass
                        continue
                    
                    # Ensure RGBA mode
                    pil_rgba = pil_img.convert("RGBA")
                    
                    # Verify alpha channel is not completely transparent (FIXED: added validation)
                    alpha_channel = pil_rgba.split()[-1]
                    alpha_arr_check = np.array(alpha_channel)
                    if not np.any(alpha_arr_check > 0):  # Performance: short-circuits on first non-zero
                        try:
                            log(f"[COMPOSE ERROR] Caption image for '{grp_text}' has completely transparent alpha channel!")
                        except Exception:
                            pass
                        continue
                    
                    try:
                        log(f"[COMPOSE]   Alpha channel stats: min={alpha_arr_check.min()}, max={alpha_arr_check.max()}, mean={alpha_arr_check.mean():.1f}")
                    except Exception:
                        pass
                    
                    # convert to numpy arrays for moviepy ImageClip + mask (FIXED: proper mask handling)
                    rgb_arr = np.array(pil_rgba.convert("RGB"))
                    alpha_arr = np.array(pil_rgba.split()[-1]).astype("float32") / 255.0
                    
                    # ImageClip is already imported at top of file
                    img_clip = ImageClip(rgb_arr).set_start(g_start).set_duration(g_dur)
                    mask_clip = ImageClip(alpha_arr, ismask=True).set_start(g_start).set_duration(g_dur)
                    img_clip = img_clip.set_mask(mask_clip)
                    
                    # Position: use CAPTION_Y_OFFSET for vertical positioning
                    # Negative offset moves captions up, positive moves down
                    y_offset = globals().get('CAPTION_Y_OFFSET', 0)
                    if y_offset == 0:
                        # Default: bottom center
                        img_clip = img_clip.set_position(("center", "bottom"))
                    else:
                        # Custom position with offset from bottom
                        # Lambda function to calculate position: (x, y) where y = HEIGHT - caption_height + offset
                        # offset = -1080 → y = 1080 - h - 1080 = -h (top), offset = 0 → y = 1080 - h (bottom)
                        img_clip = img_clip.set_position(lambda t: ("center", HEIGHT - img_clip.h + y_offset))
                    
                    caption_clips.append(img_clip)
                    
                    # Also collect data for FFmpeg export (word-by-word captions)
                    caption_data_for_ffmpeg.append({
                        'text': grp_text,
                        'start': g_start,
                        'end': g_start + g_dur
                    })
                    
                    try:
                        y_offset_value = globals().get('CAPTION_Y_OFFSET', 0)
                        log(f"[COMPOSE]   ✓ Caption clip created successfully")
                        log(f"[COMPOSE]   Position: Y offset = {y_offset_value}px")
                        if y_offset_value < 0:
                            log(f"[COMPOSE]   (captions positioned {abs(y_offset_value)}px from bottom, moving UP)")
                        elif y_offset_value > 0:
                            log(f"[COMPOSE]   (captions positioned {y_offset_value}px below bottom, moving DOWN)")
                        else:
                            log(f"[COMPOSE]   (captions at default BOTTOM position)")
                    except Exception:
                        pass
                    
                except Exception as e_img:
                    try:
                        log(f"[COMPOSE ERROR] Failed creating clip for group '{grp_text}': {e_img}")
                        import traceback
                        log(f"[COMPOSE ERROR] Traceback: {traceback.format_exc()}")
                    except Exception:
                        pass
                    continue
                    
        except Exception as e_seg:
            try:
                log(f"[COMPOSE ERROR] Failed processing segment {seg_idx}: {e_seg}")
                import traceback
                log(f"[COMPOSE ERROR] Traceback: {traceback.format_exc()}")
            except Exception:
                pass
            continue
    
    try:
        log(f"[COMPOSE] ═══════════════════════════════════════════════")
        log(f"[COMPOSE] Total caption clips created: {len(caption_clips)}")
        log(f"[COMPOSE] ═══════════════════════════════════════════════")
    except Exception:
        pass
    
    # Try fast FFmpeg export first (2-3x faster than MoviePy)
    try_ffmpeg_export = True  # Set to False to force MoviePy
    ffmpeg_export_successful = False
    
    # Determine which caption data to use for FFmpeg
    captions_for_ffmpeg = caption_data_for_ffmpeg if caption_data_for_ffmpeg else caption_segments
    
    # Note: FFmpeg export handles many captions (>MAX_DRAWTEXT_CAPTIONS) via ASS subtitle files
    # which is efficient and avoids command line length limits. No need to disable FFmpeg.
    if len(captions_for_ffmpeg) > MAX_DRAWTEXT_CAPTIONS:
        log(f"[EXPORT] Many captions detected ({len(captions_for_ffmpeg)}) - will use ASS subtitle file for efficient FFmpeg rendering")
    
    if try_ffmpeg_export:
        try:
            import tempfile
            log("[EXPORT] Attempting fast FFmpeg filter-based export...")
            if not caption_segments:
                log("[EXPORT] Note: No captions to render (video will have no text overlay)")
            
            # Save background image to temp file
            temp_dir = tempfile.mkdtemp(prefix="tiktok_ffmpeg_export_")
            bg_image_path = os.path.join(temp_dir, "background.png")
            bg_array = bg_static.get_frame(0)
            # Image is already imported at top of file
            Image.fromarray(bg_array).save(bg_image_path)
            log(f"[EXPORT] Background saved to: {bg_image_path}")
            
            # Save audio to temp file
            audio_temp_path = os.path.join(temp_dir, "audio.mp3")
            audio_clip.write_audiofile(audio_temp_path, fps=44100, codec='mp3', verbose=False, logger=None)
            log(f"[EXPORT] Audio saved to: {audio_temp_path}")
            
            # Get foreground video path - use pre-rendered path if available
            fg_video_path = None
            if pre_rendered_fg_path and os.path.exists(pre_rendered_fg_path):
                fg_video_path = pre_rendered_fg_path
                log(f"[EXPORT] Using pre-rendered foreground: {fg_video_path}")
            elif hasattr(fg, 'filename') and fg.filename and os.path.exists(fg.filename):
                fg_video_path = fg.filename
                log(f"[EXPORT] Using foreground from clip: {fg_video_path}")
            else:
                # Need to save foreground video first (slow path - shows MoviePy progress)
                fg_video_path = os.path.join(temp_dir, "foreground.mp4")
                log(f"[EXPORT] ⚠️ No pre-rendered foreground - saving via MoviePy: {fg_video_path}")
                log(f"[EXPORT] (This may show a progress bar - consider using pre-render)")
                fg.write_videofile(fg_video_path, fps=FPS, codec='libx264', audio=False, verbose=False, logger=None, preset='ultrafast')
            
            # Try FFmpeg export with word-by-word caption data
            ffmpeg_export_successful = _export_with_ffmpeg_filters(
                bg_path=bg_image_path,
                fg_path=fg_video_path,
                caption_segments=captions_for_ffmpeg,
                audio_path=audio_temp_path,
                output_path=output_path,
                video_width=WIDTH,
                video_height=HEIGHT,
                log_fn=log,
                effect_settings=effect_settings,
                mirror_video=mirror_video,
                target_duration=target_duration
            )
            
            if ffmpeg_export_successful:
                log("[EXPORT] ✅ Fast FFmpeg export completed successfully!")
                log("[EXPORT] Skipping MoviePy export (not needed)")
                # Clean up temp files
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                except:
                    pass
                return True
            else:
                log("[EXPORT] ⚠️ FFmpeg export failed, falling back to MoviePy...")
                
        except Exception as e:
            log(f"[EXPORT] ⚠️ FFmpeg export exception: {e}")
            log("[EXPORT] Falling back to MoviePy export...")
            import traceback
            log(f"[EXPORT] Traceback: {traceback.format_exc()}")
    
    # Fallback to MoviePy export (original code)
    if not ffmpeg_export_successful:
        try:
            log("[EXPORT] Using MoviePy export (fallback or FFmpeg disabled)...")
            # Verify audio clip before compositing
            if audio_clip is None:
                try:
                    log(f"[COMPOSE WARNING] ⚠️ audio_clip is None! Final video will have no audio!")
                except Exception:
                    pass
            else:
                try:
                    log(f"[COMPOSE] Audio clip duration: {audio_clip.duration:.2f}s")
                except Exception:
                    pass
            
            final = CompositeVideoClip([bg_static, fg] + caption_clips, size=(WIDTH, HEIGHT)).set_audio(audio_clip)
            try:
                log(f"[COMPOSE] ✓ Final composition created successfully")
                log(f"[COMPOSE] Layers: background + foreground + {len(caption_clips)} caption overlays")
            except Exception:
                pass
        except Exception as e:
            try:
                log(f"[COMPOSE ERROR] Failed to create CompositeVideoClip: {e}")
                import traceback
                log(f"[COMPOSE ERROR] Traceback: {traceback.format_exc()}")
            except Exception:
                pass
            raise

        # export monitoring and fallback
        codec_try_order = []
        if USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC):
            codec_try_order.append(PREFERRED_NVENC_CODEC)
            log(f"[EXPORT] GPU acceleration enabled for export (NVENC: {PREFERRED_NVENC_CODEC})")
        else:
            log("[EXPORT] Using CPU encoding for export (libx264)")
        codec_try_order.append("libx264")

        STALL_TIMEOUT = 90
        CHECK_INTERVAL = 8
        MAX_ATTEMPTS_PER_CODEC = 1

        def _run_write(final_clip, out_path, codec_name, ffmpeg_params, threads_setting, result_dict):
            try:
                final_clip.write_videofile(
                    out_path,
                    fps=FPS,
                    codec=codec_name,
                    audio_codec="aac",
                    audio_bitrate="192k",
                    threads=threads_setting,
                    ffmpeg_params=ffmpeg_params,
                    verbose=False,
                    logger="bar"
                )
                result_dict["ok"] = True
            except Exception as e:
                result_dict["ok"] = False
                result_dict["error"] = str(e)
            finally:
                try:
                    final_clip.close()
                except Exception:
                    pass
                gc.collect()

        last_error = None
        for codec in codec_try_order:
            for attempt in range(MAX_ATTEMPTS_PER_CODEC):
                ffmpeg_params = _make_ffmpeg_params_for_codec(codec)
                threads_setting = 4  # Use 4 threads for better performance (was 0/auto)
                # Log GPU usage status for user clarity
                gpu_status = "GPU (NVENC)" if codec in ("h264_nvenc", "hevc_nvenc") else "CPU (libx264)"
                log(f"[EXPORT] Starting export with {gpu_status}")
                log(f"[EXPORT] Codec: {codec}, Params: {ffmpeg_params}, Threads: {threads_setting}, Attempt: {attempt+1}")
                result = {"ok": False, "error": None}
                writer_thread = threading.Thread(target=_run_write, args=(final, output_path, codec, ffmpeg_params, threads_setting, result), daemon=True)
                writer_thread.start()

                prev_size = -1
                stalled_since = None
                start_t = time.time()
                while writer_thread.is_alive():
                    time.sleep(CHECK_INTERVAL)
                    try:
                        cur_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
                    except Exception:
                        cur_size = 0
                    log(f"[export-monitor] {codec} out_size={cur_size} bytes (elapsed {int(time.time()-start_t)}s)")
                    if cur_size > prev_size:
                        prev_size = cur_size
                        stalled_since = None
                    else:
                        if stalled_since is None:
                            stalled_since = time.time()
                        else:
                            if (time.time() - stalled_since) > STALL_TIMEOUT:
                                log(f"[export-monitor] Detected stall for {STALL_TIMEOUT}s. Attempting to abort and retry.")
                                try:
                                    os.remove(output_path)
                                    log("[export-monitor] Removed partial output file.")
                                except Exception as e_rm:
                                    log(f"[export-monitor] Could not remove partial file: {e_rm}")
                                result["ok"] = False
                                result["error"] = f"Stalled export (no growth for {STALL_TIMEOUT}s)"
                                break
                writer_thread.join(timeout=1.0)
                if result.get("ok"):
                    gpu_used = "GPU (NVENC)" if codec in ("h264_nvenc", "hevc_nvenc") else "CPU (libx264)"
                    log(f"[EXPORT] ✅ Export finished successfully using {gpu_used}")
                    ok_probe, probe_out = probe_file_with_ffmpeg(output_path)
                    if ok_probe:
                        log("Export OK — ffmpeg probe didn't find fatal errors.")
                        try:
                            if os.name == "nt":
                                os.startfile(output_path)
                            elif sys.platform == "darwin":
                                subprocess.Popen(["open", output_path])
                            else:
                                subprocess.Popen(["xdg-open", output_path])
                        except Exception as eopen:
                            log(f"Could not open output automatically: {eopen}")
                        return True
                    else:
                        log("[export-monitor] Probe reported issues, attempting re-encode.")
                        last_error = probe_out
                        reencoded = output_path.replace(".mp4", "_reencoded.mp4")
                        success = reencode_with_libx264(output_path, reencoded, log)
                        if success:
                            try:
                                os.replace(reencoded, output_path)
                                log("Re-encoded succeeded and replaced original output.")
                                return True
                            except Exception:
                                log(f"Re-encoded saved at: {reencoded}")
                                return True
                        else:
                            log("Re-encode failed.")
                else:
                    last_error = result.get("error")
                    log(f"[export-monitor] Export attempt failed/aborted: {last_error}")
                    time.sleep(1.0)
                    continue

        log(f"[export-monitor] All export attempts exhausted. Last error: {last_error}")
        return False

# ----------------- Processing pipeline (single job) -----------------
def crop_precise_top_bottom_return_cropped(video_clip, log, top_ratio=None, bottom_ratio=None):
    tr = CROP_TOP_RATIO if top_ratio is None else top_ratio
    br = CROP_BOTTOM_RATIO if bottom_ratio is None else bottom_ratio
    log(f"Cropping using ratios top={tr:.4f}, bottom={br:.4f} (return cropped clip).")
    original_width, original_height = video_clip.size
    crop_top = int(original_height * tr)
    crop_bottom = int(original_height * br)
    crop_y_start = crop_top
    crop_y_end = original_height - crop_bottom
    cropped_video = video_clip.crop(x1=0, y1=crop_y_start, x2=original_width, y2=crop_y_end)
    log(f"Crop done. Cropped size: {cropped_video.size}, duration: {cropped_video.duration:.2f}s")
    return cropped_video

def _compose_with_pref_font(preferred_font, video_clip, audio_clip, caption_segments, output_path, log, blur_radius=STATIC_BG_BLUR_RADIUS, bg_scale_extra=BG_SCALE_EXTRA, dim_factor=DIM_FACTOR, words_per_caption=2, effect_settings=None, pre_rendered_fg_path=None, mirror_video=False, target_duration=None):
    """Helper to temporarily override global CAPTION_FONT_PREFERRED for the duration of compose."""
    old = globals().get('CAPTION_FONT_PREFERRED')
    try:
        if preferred_font:
            globals()['CAPTION_FONT_PREFERRED'] = preferred_font
            try:
                if log: log(f"[FONT] Overriding CAPTION_FONT_PREFERRED -> {preferred_font}")
            except Exception:
                pass
        # call compose with keyword args to avoid positional mismatch
        return compose_final_video_with_static_blurred_bg(video_clip=video_clip, audio_clip=audio_clip, caption_segments=caption_segments, output_path=output_path, log=log, blur_radius=blur_radius, bg_scale_extra=bg_scale_extra, dim_factor=dim_factor, words_per_caption=words_per_caption, effect_settings=effect_settings, pre_rendered_fg_path=pre_rendered_fg_path, mirror_video=mirror_video, target_duration=target_duration)
    finally:
        try:
            if preferred_font and old is not None:
                globals()['CAPTION_FONT_PREFERRED'] = old
                try:
                    if log: log(f"[FONT] Restored CAPTION_FONT_PREFERRED -> {old}")
                except Exception:
                    pass
        except Exception:
            pass



def adjust_video_speed(video_clip, audio_duration, log, max_change=2.0):
    old_dur = video_clip.duration
    target = float(audio_duration)
    if abs(old_dur - target) < 0.01:
        log("Video already approximately matches audio duration.")
        return video_clip.set_duration(target)
    factor = old_dur / target
    log(f"Adjust video: {old_dur:.2f}s -> {target:.2f}s ; speedx factor = {factor:.4f}")
    min_factor = 1.0 / max_change
    max_factor = max_change
    if factor < min_factor or factor > max_factor:
        log(f"Factor {factor:.4f} out of bounds ({min_factor:.3f}..{max_factor:.3f}). Using fallback.")
        if old_dur < target:
            loops = int(np.ceil(target / old_dur))
            log(f"Looping video {loops} times then subclip to {target:.2f}s")
            looped = concatenate_videoclips([video_clip] * loops).subclip(0, target)
            return looped.set_duration(target)
        else:
            log("Trimming video to target duration.")
            return video_clip.subclip(0, target).set_duration(target)
    adjusted = video_clip.fx(speedx, factor).set_duration(target)
    log(f"Speed adjusted by factor {factor:.4f}. New duration: {adjusted.duration:.2f}s")
    return adjusted

def make_music_match_duration(music_clip, target_duration, log):
    if music_clip.duration <= 0.01:
        raise ValueError("Music clip invalid / durată zero.")
    if abs(music_clip.duration - target_duration) < 0.01:
        return music_clip.volumex(MUSIC_GAIN).set_duration(target_duration)
    if music_clip.duration < target_duration:
        loops = int(np.ceil(target_duration / music_clip.duration))
        log(f"Music too short ({music_clip.duration:.2f}s). Looping {loops} times to reach {target_duration:.2f}s")
        looped = concatenate_audioclips([music_clip] * loops).subclip(0, target_duration)
        return looped.volumex(MUSIC_GAIN)
    else:
        log(f"Music longer ({music_clip.duration:.2f}s). Trimming to {target_duration:.2f}s and applying fadeout {MUSIC_FADEOUT_SECONDS}s.")
        trimmed = music_clip.subclip(0, target_duration)
        trimmed = trimmed.fx(audio_fadeout, MUSIC_FADEOUT_SECONDS)
        return trimmed.volumex(MUSIC_GAIN).set_duration(target_duration)

def process_single_job(video_path, voice_path, music_path, requested_output_path, q, preferred_font=None, custom_top_ratio=None, custom_bottom_ratio=None, mirror_video=False, words_per_caption=2, use_4k=False, blur_radius=None, bg_scale_extra=None, dim_factor=None, effect_settings=None, use_ai_voice=None, target_language=None, translation_enabled=None, tts_language=None, silence_threshold_ms=300):
    def log(s):
        q.put(str(s))
    old_stdout, old_stderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = QueueWriter(q)
    temp_fg = None
    
    # Log received crop parameters for debugging
    log(f"[DEBUG] Received custom_top_ratio: {custom_top_ratio}")
    log(f"[DEBUG] Received custom_bottom_ratio: {custom_bottom_ratio}")
    
    # Set defaults for effects if not provided
    if blur_radius is None:
        blur_radius = globals().get('STATIC_BG_BLUR_RADIUS', 25)
    if bg_scale_extra is None:
        bg_scale_extra = globals().get('BG_SCALE_EXTRA', 1.08)
    if dim_factor is None:
        dim_factor = globals().get('DIM_FACTOR', 0.55)
    
    # Determine if AI voice should be used - prefer parameter over global
    if use_ai_voice is None:
        use_ai_voice = globals().get('USE_AI_VOICE_REPLACEMENT', False)
    
    # Determine language settings - prefer parameters over globals
    if target_language is None:
        target_language = globals().get('TARGET_LANGUAGE', 'none')
    if translation_enabled is None:
        translation_enabled = globals().get('TRANSLATION_ENABLED', False)
    if tts_language is None:
        tts_language = globals().get('TTS_LANGUAGE', 'en')
    
    # Set 4K mode if requested
    # NOTE: Using global state for IS_4K_MODE. This is safe because:
    # 1. Jobs are processed sequentially (one at a time) via queue_worker
    # 2. Single jobs via on_run_single run in separate threads but don't overlap
    # 3. The old value is saved and restored in the finally block
    old_is_4k = globals().get('IS_4K_MODE', False)
    if use_4k:
        globals()['IS_4K_MODE'] = True
        log("[RESOLUTION] Job set to 4K mode (2160x3840)")
    else:
        globals()['IS_4K_MODE'] = False
        log("[RESOLUTION] Job set to HD mode (1080x1920)")
    
    try:
        load_preferred_font_cached(preferred_font or CAPTION_FONT_PREFERRED, CAPTION_FONT_SIZE, log=log)
        if REQUIRE_FONT_BANGERS and (LOADED_FONT_PATH is None or ("bangers" not in str(LOADED_FONT_PATH).lower())):
            log("Error: Bangers font required but not found. Aborting job.")
            return

        output_path = make_unique_output_path(requested_output_path, log=log)

        if not os.path.exists(video_path):
            log(f"Error: VIDEO missing: {video_path}")
            return
        
        # Voice is now optional - extract from video if not provided
        voice_from_video = False
        if not voice_path or not os.path.exists(voice_path):
            log("[VOICE] No separate voice file provided - extracting audio from video...")
            voice_from_video = True
            # Extract audio from video to a temporary file
            temp_voice_path = tempfile.mktemp(suffix='.mp3', prefix='extracted_voice_')
            try:
                video_clip_for_audio = VideoFileClip(video_path)
                if video_clip_for_audio.audio is None:
                    log("[VOICE ERROR] Video has no audio track!")
                    if not use_ai_voice:
                        log("[VOICE ERROR] Cannot proceed without voice audio or AI voice enabled.")
                        return
                    log("[VOICE] Will generate AI voice from text/captions only.")
                    voice_path = None
                else:
                    video_clip_for_audio.audio.write_audiofile(temp_voice_path, logger=None)
                    voice_path = temp_voice_path
                    log(f"[VOICE] ✓ Extracted audio from video: {temp_voice_path}")
                    video_clip_for_audio.close()
            except Exception as e:
                log(f"[VOICE ERROR] Failed to extract audio from video: {e}")
                if not use_ai_voice:
                    return
                log("[VOICE] Will proceed with AI voice generation only.")
                voice_path = None
        
        if not os.path.exists(music_path):
            log(f"Error: MUSIC missing: {music_path}")
            return

        # Load video first to get dimensions
        original_clip = VideoFileClip(video_path)
        cropped = crop_precise_top_bottom_return_cropped(original_clip, log, top_ratio=custom_top_ratio, bottom_ratio=custom_bottom_ratio)

        orig_w, orig_h = original_clip.size
        crop_top = int(orig_h * (CROP_TOP_RATIO if custom_top_ratio is None else custom_top_ratio))
        crop_bottom = int(orig_h * (CROP_BOTTOM_RATIO if custom_bottom_ratio is None else custom_bottom_ratio))
        crop_h = orig_h - crop_top - crop_bottom
        crop_w = orig_w
        crop_x = 0
        crop_y = crop_top
        
        # Log crop values for debugging
        log(f"[CROP] Custom crop enabled: {custom_top_ratio is not None or custom_bottom_ratio is not None}")
        log(f"[CROP] Top ratio: {custom_top_ratio if custom_top_ratio is not None else CROP_TOP_RATIO} ({crop_top}px)")
        log(f"[CROP] Bottom ratio: {custom_bottom_ratio if custom_bottom_ratio is not None else CROP_BOTTOM_RATIO} ({crop_bottom}px)")
        log(f"[CROP] Original: {orig_w}x{orig_h}, Cropped: {crop_w}x{crop_h}")

        try:
            min_scale_to_fit = min(WIDTH / cropped.w, HEIGHT / cropped.h)
        except Exception:
            min_scale_to_fit = 1.0
        
        # Calculate scale with dynamic limits based on resolution mode
        # In 4K mode, we need higher scale limits to maintain same zoom effect
        is_4k = globals().get('IS_4K_MODE', False)
        base_scale_factor = 1.03
        max_scale_limit = 1.06
        
        # Get user's zoom setting
        user_zoom = globals().get('VIDEO_ZOOM_SCALE', 1.0)
        
        if is_4k:
            # For 4K, double the scale factors to maintain same visual zoom
            # This ensures the video is zoomed in properly to cover edges
            fg_scale = max(1.0, min_scale_to_fit) * (base_scale_factor * 2.0)
            fg_scale = min(fg_scale, max_scale_limit * 2.0)  # Allow up to 2.12x for 4K
        else:
            # HD mode - use original logic
            fg_scale = max(1.0, min_scale_to_fit) * base_scale_factor
            fg_scale = min(fg_scale, max_scale_limit)
        
        # Apply user's zoom factor (0.5x to 2.0x from slider)
        fg_scale = fg_scale * user_zoom
        
        scale_w = max(1, int(round(crop_w * fg_scale)))
        scale_h = max(1, int(round(crop_h * fg_scale)))
        
        # Get caption offset for logging
        y_offset = globals().get('CAPTION_Y_OFFSET', 0)
        offset_desc = f"moving {abs(y_offset)}px {'UP' if y_offset < 0 else 'DOWN'} from bottom" if y_offset != 0 else "at BOTTOM (default)"
        
        # Enhanced detailed logging - now that we have all values
        log("═══════════════ PROCESSING JOB ═══════════════")
        log(f"VIDEO: {os.path.basename(video_path)} ({orig_w}x{orig_h}, {original_clip.duration:.1f}s)")
        log(f"VOICE: {os.path.basename(voice_path)} (volume: {VOICE_GAIN:.1f}x)")
        log(f"MUSIC: {os.path.basename(music_path)} (volume: {MUSIC_GAIN:.2f}x)")
        
        # Font information
        font_info = "default"
        if LOADED_FONT_PATH:
            font_info = f"{os.path.basename(LOADED_FONT_PATH)}"
            try:
                if LOADED_FONT_FAMILY:
                    font_info += f" ({LOADED_FONT_FAMILY})"
            except:
                pass
        log(f"FONT: {font_info}")
        
        # Crop information
        crop_top_pct = (custom_top_ratio if custom_top_ratio is not None else CROP_TOP_RATIO) * 100
        crop_bottom_pct = (custom_bottom_ratio if custom_bottom_ratio is not None else CROP_BOTTOM_RATIO) * 100
        
        # Check NVENC support before logging
        use_nvenc = USE_GPU_IF_AVAILABLE and ffmpeg_supports_nvenc(PREFERRED_NVENC_CODEC)
        
        log(f"CROP: Top {crop_top_pct:.1f}%, Bottom {crop_bottom_pct:.1f}% → {crop_w}x{crop_h}")
        log(f"ZOOM: User setting {user_zoom:.2f}x")
        log(f"SCALE: {fg_scale:.2f}x → {scale_w}x{scale_h}")
        log(f"CAPTION OFFSET: {y_offset}px ({offset_desc})")
        log(f"MIRROR: {'Enabled' if mirror_video else 'Disabled'}")
        log(f"OUTPUT: {os.path.basename(output_path)} ({WIDTH}x{HEIGHT}, {FPS}fps{',' if use_nvenc else ''}{' NVENC' if use_nvenc else ''})")
        log("══════════════════════════════════════════════")

        temp_dir = tempfile.mkdtemp(prefix="tiktok_prerender_")
        temp_fg = os.path.join(temp_dir, "fg_prerender.mp4")
        log(f"Attempting ffmpeg pre-render -> {os.path.basename(temp_fg)} (nvenc={use_nvenc})")
        prer_ok = pre_render_foreground_ffmpeg(video_path, temp_fg, crop_x, crop_y, crop_w, crop_h, scale_w, scale_h, FPS, use_nvenc, log)

        if prer_ok and os.path.exists(temp_fg):
            log("Using pre-rendered foreground clip.")
            fg_clip = VideoFileClip(temp_fg)
        else:
            log("Pre-render failed or missing — falling back to MoviePy in-memory crop/resize.")
            fg_clip = cropped.resize(fg_scale).set_position(("center", "center")).set_duration(cropped.duration)
        
        # Remove original audio from video clip to prevent duplicate audio
        # Only the mixed_audio (voice/TTS + music) should be used
        log("Removing original audio from video clip...")
        fg_clip = fg_clip.without_audio()
        log("✓ Original video audio removed (will use voice/TTS + music only)")
        
        # Apply mirror if enabled
        if mirror_video:
            log("Applying horizontal mirror/flip to video...")
            from moviepy.video.fx.mirror_x import mirror_x
            fg_clip = mirror_x(fg_clip)
            log("✓ Video mirrored successfully")

        # Handle audio based on whether we have a voice file
        if voice_path and os.path.exists(voice_path):
            voice_clip = AudioFileClip(voice_path).volumex(VOICE_GAIN)
            music_clip = AudioFileClip(music_path)
            target_duration = voice_clip.duration
            log(f"Voice duration (target): {target_duration:.2f}s")
            music_matched = make_music_match_duration(music_clip, target_duration, log)
            mixed_audio = CompositeAudioClip([music_matched, voice_clip.set_start(0)]).set_duration(target_duration)
            
            synced_video = adjust_video_speed(fg_clip, mixed_audio.duration, log, max_change=2.0)
            
            # Transcribe captions ONLY if AI voice replacement is NOT enabled
            # If AI voice is enabled, we'll transcribe from the TTS audio later
            if not use_ai_voice:
                log("[CAPTION] Transcribing captions from original voice...")
                caption_segments = transcribe_captions(
                    voice_path, 
                    log, 
                    translate_to=target_language if translation_enabled else None
                )
            else:
                log("[CAPTION] Deferring caption generation until after TTS voice is created...")
                # Generate initial caption segments from original voice for TTS generation
                caption_segments = transcribe_captions(
                    voice_path, 
                    log, 
                    translate_to=target_language if translation_enabled else None
                )
        else:
            # No voice file - use video duration as target
            log("[NO VOICE] Using video duration as target")
            target_duration = fg_clip.duration
            music_clip = AudioFileClip(music_path)
            music_matched = make_music_match_duration(music_clip, target_duration, log)
            mixed_audio = music_matched.set_duration(target_duration)
            synced_video = fg_clip
            caption_segments = []
            
            # If AI voice is enabled, we still need to generate it even without a voice file
            # We'll need to create dummy caption segments from user input or skip captions
            if use_ai_voice:
                log("[NO VOICE + AI TTS] Will generate AI voice without captions")
                # For now, we'll skip caption generation when there's no voice to transcribe
                # The TTS will be generated below if caption_segments exists or can be created
            else:
                log("[NO VOICE] No captions will be generated (no voice to transcribe)")
        
        # Track if TTS was successfully applied
        tts_successfully_applied = False
        
        # Optional: Replace voice with AI-generated TTS or generate from scratch
        if use_ai_voice:
            if caption_segments:
                log("")
                log("━"*60)
                log("[AI VOICE] 🎵 GENERATING AI VOICE REPLACEMENT")
                log(f"[AI VOICE] Segments to synthesize: {len(caption_segments)}")
                log(f"[AI VOICE] Target language: {tts_language}")
                log("━"*60)
                log("")
                
                tts_audio_path = replace_voice_with_tts(
                    caption_segments, 
                    language=tts_language,
                    log=log
                )
                if tts_audio_path:
                    # Replace voice_clip with TTS audio
                    try:
                        log("")
                        log("[AI VOICE] 🔊 Integrating AI voice into video...")
                        
                        # STEP 1: Remove all silences from TTS audio FIRST for continuous speech
                        log("")
                        log("[AI VOICE] 📝 Removing silences from TTS audio for continuous playback...")
                        log(f"[AI VOICE] Using silence threshold: {silence_threshold_ms}ms")
                        compressed_tts_path, silence_map = remove_silence_from_audio(
                            tts_audio_path, 
                            output_path=None,
                            log=log,
                            min_silence_ms=silence_threshold_ms
                        )
                        
                        # STEP 2: Re-transcribe captions from the SILENCE-REMOVED audio
                        # This ensures captions match exactly with the final compressed audio
                        # CapCut-style: transcribe from final audio for perfect sync
                        log("")
                        log("[AI VOICE] 📝 TRANSCRIBING CAPTIONS FROM SILENCE-REMOVED TTS AUDIO")
                        log("[AI VOICE] CapCut-style: Captions generated from final compressed audio...")
                        caption_segments = transcribe_captions(
                            compressed_tts_path,  # Use compressed audio instead of original
                            log, 
                            translate_to=None  # Already translated during TTS generation
                        )
                        log(f"[AI VOICE] ✓ Generated {len(caption_segments)} caption segments with perfect timing")
                        log("")
                        
                        # No need for timestamp remapping - captions already match the compressed audio!
                        
                        # STEP 2.5: Extend last caption to cover full video duration
                        # This ensures captions display throughout the entire video
                        compressed_tts_clip = AudioFileClip(compressed_tts_path)
                        tts_final_duration = compressed_tts_clip.duration
                        compressed_tts_clip.close()
                        
                        if caption_segments:
                            last_caption_end = caption_segments[-1].get('end', 0)
                            if last_caption_end < tts_final_duration:
                                # Extend last caption to match video/audio duration
                                caption_segments[-1]['end'] = tts_final_duration
                                log(f"[AI VOICE] Extended last caption from {last_caption_end:.2f}s to {tts_final_duration:.2f}s (full video duration)")
                        
                        # Load the silence-removed TTS audio
                        tts_clip = AudioFileClip(compressed_tts_path).volumex(VOICE_GAIN)
                        
                        # Use TTS duration as the new target - DO NOT speed up/slow down the voice
                        tts_duration = tts_clip.duration
                        log(f"[AI VOICE] TTS voice duration (after silence removal): {tts_duration:.2f}s")
                        log(f"[AI VOICE] Keeping TTS voice at original speed (natural sound)")
                        
                        # Adjust music to match TTS duration
                        log(f"[AI VOICE] Adjusting music to match TTS duration...")
                        music_matched = make_music_match_duration(music_clip, tts_duration, log)
                        
                        # Composite ONLY TTS + music (no original voice to avoid duplicate audio)
                        log(f"[AI VOICE] 🎬 Compositing audio tracks (TTS + Music only)...")
                        mixed_audio = CompositeAudioClip([music_matched, tts_clip.set_start(0)]).set_duration(tts_duration)
                        
                        # Adjust VIDEO speed to match TTS duration (slow down or speed up video)
                        log(f"[AI VOICE] 🎬 Adjusting video speed to sync with TTS voice...")
                        synced_video = adjust_video_speed(fg_clip, tts_duration, log, max_change=2.0)
                        
                        log("")
                        log("━"*60)
                        log("[AI VOICE] ✅ VOICE REPLACEMENT SUCCESSFUL!")
                        log("[AI VOICE] Voice plays continuously (silences removed)")
                        log("[AI VOICE] Captions synchronized with word timestamps")
                        log("[AI VOICE] Video speed adjusted to match AI voice (voice kept at natural speed)")
                        log(f"[AI VOICE] Final audio duration: {mixed_audio.duration:.2f}s")
                        log(f"[AI VOICE] Final video duration: {synced_video.duration:.2f}s")
                        log("━"*60)
                        log("")
                        
                        # Mark that TTS was successfully applied
                        tts_successfully_applied = True
                        log("[AI VOICE] 🎯 TTS FLAG SET: TTS audio will be used in final video")
                        
                    except Exception as e:
                        log(f"[AI VOICE ERROR] ❌ Failed to use TTS audio: {e}")
                        import traceback
                        log(traceback.format_exc())
                        log("[AI VOICE ERROR] Falling back to original voice/music audio")
                        tts_successfully_applied = False
                else:
                    log("[AI VOICE] ⚠️ TTS audio generation returned None - using original audio")
                    tts_successfully_applied = False
            else:
                log("[AI VOICE] No captions available - AI voice replacement skipped")
                log("[AI VOICE] Tip: Provide voice file with audio for automatic transcription and AI voice generation")
                tts_successfully_applied = False

        # Final verification of what audio is being used
        log("")
        log("━"*60)
        log("[FINAL COMPOSITION] Preparing to create final video...")
        if tts_successfully_applied:
            log("[FINAL COMPOSITION] 🎤 USING AI-GENERATED TTS VOICE")
            log(f"[FINAL COMPOSITION] ✓ TTS voice successfully integrated")
        else:
            log("[FINAL COMPOSITION] 🎵 Using original voice/music audio")
            log(f"[FINAL COMPOSITION] (AI voice was not enabled or failed)")
        log(f"[FINAL COMPOSITION] Video duration: {synced_video.duration:.2f}s")
        log(f"[FINAL COMPOSITION] Audio duration: {mixed_audio.duration:.2f}s")
        log(f"[FINAL COMPOSITION] Caption segments: {len(caption_segments)}")
        if temp_fg and os.path.exists(temp_fg):
            log(f"[FINAL COMPOSITION] Pre-rendered foreground: {temp_fg}")
        log("━"*60)
        log("")
        
        # Pass mirror_video and target_duration for FFmpeg export optimization
        # Calculate target duration from audio or video, with fallback
        target_duration = None
        if mixed_audio and hasattr(mixed_audio, 'duration') and mixed_audio.duration:
            target_duration = mixed_audio.duration
        elif synced_video and hasattr(synced_video, 'duration') and synced_video.duration:
            target_duration = synced_video.duration
        
        ok = _compose_with_pref_font(preferred_font, synced_video, mixed_audio, caption_segments, output_path, log, blur_radius=blur_radius, bg_scale_extra=bg_scale_extra, dim_factor=dim_factor, words_per_caption=words_per_caption, effect_settings=effect_settings, pre_rendered_fg_path=temp_fg, mirror_video=mirror_video, target_duration=target_duration)
        if ok:
            log(f"Job finished successfully. Output: {output_path}")
        else:
            log("Job finished with errors.")
    except Exception as e:
        q.put(f"Exception: {e}")
        import traceback
        q.put(traceback.format_exc())
    finally:
            # Robust cleanup: close any MoviePy/AudioClip objects we created and remove temporary directories.
        def _safe_close(obj, name=None):
            try:
                if obj is None:
                    return
                if hasattr(obj, "close"):
                    obj.close()
            except Exception as e:
                try:
                    q.put(f"[cleanup] Failed to close {name or str(obj)}: {e}")
                except Exception:
                    pass
    
        try:
            _safe_close(globals().get("fg_clip") if "fg_clip" in globals() else locals().get("fg_clip"), "fg_clip")
            _safe_close(locals().get("fg_clip"), "fg_clip")
            _safe_close(locals().get("original_clip"), "original_clip")
            _safe_close(locals().get("voice_clip"), "voice_clip")
            _safe_close(locals().get("music_clip"), "music_clip")
            _safe_close(locals().get("music_matched"), "music_matched")
            _safe_close(locals().get("mixed_audio"), "mixed_audio")
            _safe_close(locals().get("synced_video"), "synced_video")
        except Exception:
            pass
    
        # Remove temp dir if it was created
        try:
            if 'temp_dir' in locals() and temp_dir and os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    q.put(f"[cleanup] Removed temp dir: {temp_dir}")
                except Exception as e_rm:
                    q.put(f"[cleanup] Could not remove temp dir {temp_dir}: {e_rm}")
        except Exception:
            pass
        
        # Remove temp voice file if it was created
        try:
            if 'temp_voice_path' in locals() and temp_voice_path and os.path.exists(temp_voice_path):
                try:
                    os.remove(temp_voice_path)
                    q.put(f"[cleanup] Removed temp voice file: {temp_voice_path}")
                except Exception as e_rm:
                    q.put(f"[cleanup] Could not remove temp voice file {temp_voice_path}: {e_rm}")
        except Exception:
            pass

    # restore stdout/stderr no matter what
    try:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
    except Exception:
        pass
    
    # Restore IS_4K_MODE
    try:
        globals()['IS_4K_MODE'] = old_is_4k
    except Exception:
        pass


def queue_worker(jobs, q):
    def log(s):
        q.put(str(s))
    log(f"[QUEUE] Starting queue with {len(jobs)} job(s).")
    for i, job in enumerate(jobs, start=1):
        log(f"\n===== START JOB {i}/{len(jobs)} =====")
        # Extract effect settings from job
        effect_settings = {
            'effect_sharpness': job.get("effect_sharpness", False),
            'effect_sharpness_intensity': job.get("effect_sharpness_intensity", 1.5),
            'effect_saturation': job.get("effect_saturation", False),
            'effect_saturation_intensity': job.get("effect_saturation_intensity", 1.3),
            'effect_contrast': job.get("effect_contrast", False),
            'effect_contrast_intensity': job.get("effect_contrast_intensity", 1.2),
            'effect_brightness': job.get("effect_brightness", False),
            'effect_brightness_intensity': job.get("effect_brightness_intensity", 1.15),
            'effect_vintage': job.get("effect_vintage", False),
            'effect_vintage_intensity': job.get("effect_vintage_intensity", 0.3)
        }
        process_single_job(job["video"], job["voice"], job["music"], job["output"], q, job.get("font"),
                           custom_top_ratio=job.get("custom_top_ratio"),
                           custom_bottom_ratio=job.get("custom_bottom_ratio"),
                           mirror_video=job.get("mirror_video", False),
                           words_per_caption=job.get("words_per_caption", 2),
                           use_4k=job.get("use_4k", False),
                           blur_radius=job.get("blur_radius"),
                           bg_scale_extra=job.get("bg_scale_extra"),
                           dim_factor=job.get("dim_factor"),
                           effect_settings=effect_settings,
                           use_ai_voice=job.get("use_ai_voice", False),
                           target_language=job.get("target_language", 'none'),
                           translation_enabled=job.get("translation_enabled", False),
                           tts_language=job.get("tts_language", 'en'),
                           silence_threshold_ms=job.get("silence_threshold_ms", 300))
        log(f"===== END JOB {i} =====\n")
    log("[QUEUE_DONE]")

# ----------------- GUI: responsive layout with PanedWindow -----------------
def seconds_to_hms(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

class App:
    def __init__(self, root):
        self.root = root
        root.title("TikTok Auto — Responsive UI")
        # --- Apply dark UI theme ---
        try:
            style = ttk.Style()
            try:
                style.theme_use('clam')
            except Exception:
                pass
            style.configure('TFrame', background='#0b0b0b')
            style.configure('TLabel', background='#0b0b0b', foreground='#FFFFFF')
            style.configure('TButton', background='#1f1f1f', foreground='#FFFFFF')
            style.configure('TEntry', fieldbackground='#1a1a1a', foreground='#FFFFFF')
            style.configure('TCheckbutton', background='#0b0b0b', foreground='#FFFFFF')
            style.configure('TMenubutton', background='#1f1f1f', foreground='#FFFFFF')
            style.configure('Horizontal.TProgressbar', troughcolor='#151515', background='#2b8cff')
        except Exception:
            pass

        try:
            root.configure(bg='#0b0b0b')
        except Exception:
            pass

        # Helper to force dark colors for native tk widgets that ttk styles don't affect.
        def apply_dark_theme_to(root_widget):
            try:
                import tkinter as _tk
                from tkinter import ttk as _ttk
            except Exception:
                return

            def _apply(w):
                # set native tk widget colors
                try:
                    if isinstance(w, _tk.Listbox) or isinstance(w, _tk.Text):
                        w.config(bg='#111111', fg='#FFFFFF', insertbackground='#FFFFFF', selectbackground='#2b2b2b', selectforeground='#FFFFFF')
                    elif isinstance(w, _tk.Canvas):
                        w.config(bg='#141414')
                    elif isinstance(w, _tk.Scrollbar):
                        try:
                            w.config(bg='#0b0b0b', troughcolor='#0b0b0b', activebackground='#333333')
                        except Exception:
                            w.config(bg='#0b0b0b')
                    elif isinstance(w, _tk.Entry):
                        try:
                            w.config(bg='#1a1a1a', fg='#FFFFFF', insertbackground='#FFFFFF')
                        except Exception:
                            pass
                except Exception:
                    pass
                # recurse into children
                try:
                    for c in w.winfo_children():
                        _apply(c)
                except Exception:
                    pass

            _apply(root_widget)

        # schedule to apply after mainloop starts so all widgets exist
        try:
            root.after(150, lambda: apply_dark_theme_to(root))
        except Exception:
            pass

        except Exception:
            pass

        self.q = queue.Queue()

        try:
            root.state('zoomed')
        except Exception:
            pass

        pw = ttk.PanedWindow(root, orient="horizontal")
        pw.pack(fill="both", expand=True)
        try:
            pw.config(style='TPanedwindow')
            pw.config(bg='#0b0b0b')
        except Exception:
            pass

        # Create a container frame for the left side with scrollbar
        left_container = ttk.Frame(pw)
        try:
            left_container.configure(style='TFrame')
            left_container.config(bg='#0b0b0b')
        except Exception:
            pass
        
        # Create Canvas and Scrollbar for scrollable left panel
        left_canvas = tk.Canvas(left_container, bg='#0b0b0b', highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        
        # Create the actual frame that will contain all controls
        left_frame = ttk.Frame(left_canvas, padding=8)
        try:
            left_frame.configure(style='TFrame')
            left_frame.config(bg='#0b0b0b')
        except Exception:
            pass
        left_frame.columnconfigure(1, weight=1)
        
        # Pack scrollbar and canvas
        left_scrollbar.pack(side="right", fill="y")
        left_canvas.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas for the frame
        canvas_frame = left_canvas.create_window((0, 0), window=left_frame, anchor="nw")
        
        # Configure canvas scrolling
        left_canvas.configure(yscrollcommand=left_scrollbar.set)
        
        # Update scroll region when frame changes size
        def configure_scroll_region(event=None):
            left_canvas.configure(scrollregion=left_canvas.bbox("all"))
            # Also update the canvas window width to match canvas width
            canvas_width = left_canvas.winfo_width()
            left_canvas.itemconfig(canvas_frame, width=canvas_width)
        
        left_frame.bind("<Configure>", configure_scroll_region)
        left_canvas.bind("<Configure>", configure_scroll_region)
        
        # Enable mousewheel scrolling
        def on_mousewheel(event):
            left_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def bind_mousewheel(event):
            left_canvas.bind_all("<MouseWheel>", on_mousewheel)
        
        def unbind_mousewheel(event):
            left_canvas.unbind_all("<MouseWheel>")
        
        left_canvas.bind('<Enter>', bind_mousewheel)
        left_canvas.bind('<Leave>', unbind_mousewheel)
        
        pw.add(left_container, weight=1)

        right_outer = ttk.PanedWindow(pw, orient="vertical")
        pw.add(right_outer, weight=2)

        preview_frame = ttk.Frame(right_outer, padding=8)
        try:
            preview_frame.configure(style='TFrame')
            preview_frame.config(bg='#0b0b0b')
        except Exception:
            pass
        right_outer.add(preview_frame, weight=3)

        bottom_frame = ttk.Frame(right_outer, padding=8)
        try:
            bottom_frame.configure(style='TFrame')
            bottom_frame.config(bg='#0b0b0b')
        except Exception:
            pass
        right_outer.add(bottom_frame, weight=2)

        # left controls
        row = 0
        ttk.Label(left_frame, text="VIDEO:").grid(row=row, column=0, sticky="w")
        self.video_var = tk.StringVar(value="")
        self.video_entry = ttk.Entry(left_frame, textvariable=self.video_var)
        self.video_entry.grid(row=row, column=1, sticky="we", padx=(6,0))
        ttk.Button(left_frame, text="Browse...", command=self.browse_video).grid(row=row, column=2, padx=6)
        row += 1

        ttk.Label(left_frame, text="VOICE (optional):").grid(row=row, column=0, sticky="w")
        self.voice_var = tk.StringVar(value="")
        self.voice_entry = ttk.Entry(left_frame, textvariable=self.voice_var)
        self.voice_entry.grid(row=row, column=1, sticky="we", padx=(6,0))
        ttk.Button(left_frame, text="Browse...", command=self.browse_voice).grid(row=row, column=2, padx=6)
        row += 1

        ttk.Label(left_frame, text="MUSIC:").grid(row=row, column=0, sticky="w")
        self.music_var = tk.StringVar(value="")
        self.music_entry = ttk.Entry(left_frame, textvariable=self.music_var)
        self.music_entry.grid(row=row, column=1, sticky="we", padx=(6,0))
        ttk.Button(left_frame, text="Browse...", command=self.browse_music).grid(row=row, column=2, padx=6)
        row += 1

        ttk.Label(left_frame, text="OUTPUT:").grid(row=row, column=0, sticky="w")
        self.output_var = tk.StringVar(value="final_tiktok.mp4")
        self.output_entry = ttk.Entry(left_frame, textvariable=self.output_var)
        self.output_entry.grid(row=row, column=1, sticky="we", padx=(6,0))
        ttk.Button(left_frame, text="Choose...", command=self.choose_output).grid(row=row, column=2, padx=6)
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        self.use_custom_crop_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Use custom crop for this job", variable=self.use_custom_crop_var).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        
        self.mirror_video_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Mirror video horizontally", variable=self.mirror_video_var).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1
        
        self.use_4k_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Export in 4K resolution (2160x3840)", variable=self.use_4k_var, command=self.on_4k_toggle).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1

        # --- Voice Volume Control ---
        ttk.Label(left_frame, text="Voice volume:").grid(row=row, column=0, sticky="e")
        self.voice_gain_var = tk.DoubleVar(value=VOICE_GAIN)
        self.voice_gain_scale = tk.Scale(left_frame, from_=0.0, to=3.0, resolution=0.1, orient='horizontal', length=120, showvalue=0, variable=self.voice_gain_var, command=self.on_voice_gain_changed)
        self.voice_gain_scale.grid(row=row, column=1, padx=(6,0))
        self.voice_gain_label = ttk.Label(left_frame, text=f"{self.voice_gain_var.get():.1f}x")
        self.voice_gain_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        row += 1

        # --- Music Volume Control ---
        ttk.Label(left_frame, text="Music volume:").grid(row=row, column=0, sticky="e")
        self.music_gain_var = tk.DoubleVar(value=MUSIC_GAIN)
        self.music_gain_scale = tk.Scale(left_frame, from_=0.0, to=2.0, resolution=0.05, orient='horizontal', length=120, showvalue=0, variable=self.music_gain_var, command=self.on_music_gain_changed)
        self.music_gain_scale.grid(row=row, column=1, padx=(6,0))
        self.music_gain_label = ttk.Label(left_frame, text=f"{self.music_gain_var.get():.2f}x")
        self.music_gain_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        # --- Translation Controls ---
        ttk.Label(left_frame, text="Translation & AI Voice", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1

        self.translation_enabled_var = tk.BooleanVar(value=TRANSLATION_ENABLED)
        ttk.Checkbutton(left_frame, text="Enable translation", variable=self.translation_enabled_var, 
                       command=self.on_translation_toggle).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1

        ttk.Label(left_frame, text="Target language:").grid(row=row, column=0, sticky="e")
        self.target_language_var = tk.StringVar(value=TARGET_LANGUAGE)
        languages = ['none', 'en', 'es', 'fr', 'de', 'it', 'pt', 'ro', 'ru', 'zh-cn', 'ja', 'ko']
        language_combo = ttk.Combobox(left_frame, textvariable=self.target_language_var, values=languages, state='readonly', width=10)
        language_combo.grid(row=row, column=1, sticky="w", padx=(6,0))
        language_combo.bind('<<ComboboxSelected>>', self.on_language_selected)
        ttk.Label(left_frame, text="(for captions)").grid(row=row, column=2, sticky='w', padx=(4,0))
        row += 1

        self.use_ai_voice_var = tk.BooleanVar(value=USE_AI_VOICE_REPLACEMENT)
        ttk.Checkbutton(left_frame, text="Replace voice with AI (TTS)", variable=self.use_ai_voice_var,
                       command=self.on_ai_voice_toggle).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1

        ttk.Label(left_frame, text="TTS language:").grid(row=row, column=0, sticky="e")
        self.tts_language_var = tk.StringVar(value=TTS_LANGUAGE)
        tts_languages = ['en', 'es', 'fr', 'de', 'it', 'pt', 'ro', 'ru', 'zh', 'ja', 'ko']
        tts_combo = ttk.Combobox(left_frame, textvariable=self.tts_language_var, values=tts_languages, state='readonly', width=10)
        tts_combo.grid(row=row, column=1, sticky="w", padx=(6,0))
        tts_combo.bind('<<ComboboxSelected>>', self.on_tts_language_selected)
        ttk.Label(left_frame, text="(voice output)").grid(row=row, column=2, sticky='w', padx=(4,0))
        row += 1

        # Voice selection dropdown - shows voices for selected TTS language
        ttk.Label(left_frame, text="Voice:").grid(row=row, column=0, sticky="e")
        
        # Available voices per language (from GenAI Pro API)
        self.voice_options = {
            'en': ['Auto (Default)', 'Voice 1', 'Voice 2', 'Voice 3'],
            'es': ['Auto (Default)', 'Voice 1', 'Voice 2'],
            'fr': ['Auto (Default)', 'Voice 1', 'Voice 2'],
            'de': ['Auto (Default)', 'Voice 1'],
            'it': ['Auto (Default)', 'Voice 1'],
            'pt': ['Auto (Default)', 'Voice 1'],
            'ro': ['Auto (Default)', 'Voice 1'],
            'ru': ['Auto (Default)', 'Voice 1'],
            'zh': ['Auto (Default)', 'Voice 1'],
            'ja': ['Auto (Default)', 'Voice 1'],
            'ko': ['Auto (Default)', 'Voice 1'],
        }
        
        # Voice ID mappings (extend this as you discover more voice IDs from GenAI Pro)
        self.voice_id_map = {
            'Auto (Default)': 'auto',
            'Voice 1': 'uju3wxzG5OhpWcoi3SMy',
            'Voice 2': 'uju3wxzG5OhpWcoi3SMy',  # Replace with actual voice IDs
            'Voice 3': 'uju3wxzG5OhpWcoi3SMy',  # Replace with actual voice IDs
        }
        
        self.tts_voice_var = tk.StringVar(value='Auto (Default)')
        current_voices = self.voice_options.get(TTS_LANGUAGE, ['Auto (Default)'])
        self.tts_voice_combo = ttk.Combobox(left_frame, textvariable=self.tts_voice_var, 
                                            values=current_voices, state='readonly', width=15)
        self.tts_voice_combo.grid(row=row, column=1, sticky="w", padx=(6,0))
        self.tts_voice_combo.bind('<<ComboboxSelected>>', self.on_voice_selected)
        ttk.Label(left_frame, text="(select voice)").grid(row=row, column=2, sticky='w', padx=(4,0))
        
        # Load custom voices on startup
        self.update_voice_dropdown(TTS_LANGUAGE)
        
        row += 1

        # API Key input for premium TTS services
        ttk.Label(left_frame, text="TTS API Key:").grid(row=row, column=0, sticky="e")
        
        # Load saved API key
        saved_api_key = ""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "tts_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    saved_api_key = config.get("api_key", "")
        except Exception:
            pass
        
        self.tts_api_key_var = tk.StringVar(value=saved_api_key)
        self.tts_api_key_entry = ttk.Entry(left_frame, textvariable=self.tts_api_key_var, show="*", width=30)
        self.tts_api_key_entry.grid(row=row, column=1, columnspan=2, sticky="we", padx=(6,0))
        row += 1
        
        # Button to save API key
        ttk.Button(left_frame, text="Save API Key", command=self.on_save_api_key).grid(row=row, column=1, sticky="w", padx=(6,0))
        row += 1
        
        # Custom Voice Management Section
        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1
        
        ttk.Label(left_frame, text="Custom Voice ID:").grid(row=row, column=0, sticky="e")
        self.custom_voice_id_var = tk.StringVar()
        self.custom_voice_id_entry = ttk.Entry(left_frame, textvariable=self.custom_voice_id_var, width=30)
        self.custom_voice_id_entry.grid(row=row, column=1, columnspan=2, sticky="we", padx=(6,0))
        row += 1
        
        ttk.Label(left_frame, text="Voice Name:").grid(row=row, column=0, sticky="e")
        self.custom_voice_name_var = tk.StringVar()
        self.custom_voice_name_entry = ttk.Entry(left_frame, textvariable=self.custom_voice_name_var, width=30)
        self.custom_voice_name_entry.grid(row=row, column=1, columnspan=2, sticky="we", padx=(6,0))
        row += 1
        
        ttk.Label(left_frame, text="Language Category:").grid(row=row, column=0, sticky="e")
        self.custom_voice_lang_var = tk.StringVar(value="en")
        lang_options = ["en", "es", "fr", "de", "it", "pt", "ro", "ru", "zh", "ja", "ko", "ar"]
        self.custom_voice_lang_combo = ttk.Combobox(left_frame, textvariable=self.custom_voice_lang_var, values=lang_options, state="readonly", width=10)
        self.custom_voice_lang_combo.grid(row=row, column=1, sticky="w", padx=(6,0))
        row += 1
        
        ttk.Button(left_frame, text="Save Custom Voice", command=self.on_save_custom_voice).grid(row=row, column=1, sticky="w", padx=(6,0))
        row += 1
        
        # Silence Removal Threshold Section
        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1
        
        ttk.Label(left_frame, text="Silence Threshold (ms):").grid(row=row, column=0, sticky="e")
        self.silence_threshold_var = tk.IntVar(value=300)
        silence_threshold_spinbox = ttk.Spinbox(
            left_frame, 
            from_=100, 
            to=2000, 
            increment=50,
            textvariable=self.silence_threshold_var,
            width=10
        )
        silence_threshold_spinbox.grid(row=row, column=1, sticky="w", padx=(6,0))
        ttk.Label(left_frame, text="(Gaps to remove from AI voice)").grid(row=row, column=2, sticky="w", padx=(3,0))
        row += 1
        
        # Words per caption control (CapCut-style)
        ttk.Label(left_frame, text="Words per caption:").grid(row=row, column=0, sticky="e")
        self.words_per_caption_var = tk.IntVar(value=2)
        words_per_caption_spinbox = ttk.Spinbox(
            left_frame, 
            from_=1, 
            to=3, 
            increment=1,
            textvariable=self.words_per_caption_var,
            width=10
        )
        words_per_caption_spinbox.grid(row=row, column=1, sticky="w", padx=(6,0))
        ttk.Label(left_frame, text="(1=single word, 2-3=groups)").grid(row=row, column=2, sticky="w", padx=(3,0))
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        # --- Video Effects (CapCut-style) ---
        ttk.Label(left_frame, text="Video Effects", font=("Arial", 10, "bold")).grid(row=row, column=0, columnspan=3, sticky="w")
        row += 1

        # Sharpness/Resilience effect
        self.effect_sharpness_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Resilience (Sharpness)", variable=self.effect_sharpness_var,
                       command=self._mini_update_worker_async).grid(row=row, column=0, columnspan=2, sticky="w")
        ttk.Label(left_frame, text="💎").grid(row=row, column=2, sticky="w")
        row += 1
        
        ttk.Label(left_frame, text="Intensity:").grid(row=row, column=0, sticky="e", padx=(20,0))
        self.effect_sharpness_intensity_var = tk.DoubleVar(value=1.5)
        sharpness_scale = tk.Scale(left_frame, from_=0.5, to=3.0, resolution=0.1, orient='horizontal', 
                                   length=120, showvalue=0, variable=self.effect_sharpness_intensity_var,
                                   command=lambda v: self._mini_update_worker_async())
        sharpness_scale.grid(row=row, column=1, padx=(6,0))
        self.sharpness_label = ttk.Label(left_frame, text=f"{self.effect_sharpness_intensity_var.get():.1f}x")
        self.sharpness_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        self.effect_sharpness_intensity_var.trace('w', lambda *args: self.sharpness_label.config(text=f"{self.effect_sharpness_intensity_var.get():.1f}x"))
        row += 1

        # Saturation boost
        self.effect_saturation_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Vibrance (Saturation)", variable=self.effect_saturation_var,
                       command=self._mini_update_worker_async).grid(row=row, column=0, columnspan=2, sticky="w")
        ttk.Label(left_frame, text="🌈").grid(row=row, column=2, sticky="w")
        row += 1
        
        ttk.Label(left_frame, text="Intensity:").grid(row=row, column=0, sticky="e", padx=(20,0))
        self.effect_saturation_intensity_var = tk.DoubleVar(value=1.3)
        saturation_scale = tk.Scale(left_frame, from_=0.5, to=2.0, resolution=0.1, orient='horizontal', 
                                    length=120, showvalue=0, variable=self.effect_saturation_intensity_var,
                                    command=lambda v: self._mini_update_worker_async())
        saturation_scale.grid(row=row, column=1, padx=(6,0))
        self.saturation_label = ttk.Label(left_frame, text=f"{self.effect_saturation_intensity_var.get():.1f}x")
        self.saturation_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        self.effect_saturation_intensity_var.trace('w', lambda *args: self.saturation_label.config(text=f"{self.effect_saturation_intensity_var.get():.1f}x"))
        row += 1

        # Contrast enhancement
        self.effect_contrast_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="HDR (Contrast)", variable=self.effect_contrast_var,
                       command=self._mini_update_worker_async).grid(row=row, column=0, columnspan=2, sticky="w")
        ttk.Label(left_frame, text="⚡").grid(row=row, column=2, sticky="w")
        row += 1
        
        ttk.Label(left_frame, text="Intensity:").grid(row=row, column=0, sticky="e", padx=(20,0))
        self.effect_contrast_intensity_var = tk.DoubleVar(value=1.2)
        contrast_scale = tk.Scale(left_frame, from_=0.5, to=2.0, resolution=0.1, orient='horizontal', 
                                 length=120, showvalue=0, variable=self.effect_contrast_intensity_var,
                                 command=lambda v: self._mini_update_worker_async())
        contrast_scale.grid(row=row, column=1, padx=(6,0))
        self.contrast_label = ttk.Label(left_frame, text=f"{self.effect_contrast_intensity_var.get():.1f}x")
        self.contrast_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        self.effect_contrast_intensity_var.trace('w', lambda *args: self.contrast_label.config(text=f"{self.effect_contrast_intensity_var.get():.1f}x"))
        row += 1

        # Brightness adjustment
        self.effect_brightness_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Brightness Boost", variable=self.effect_brightness_var,
                       command=self._mini_update_worker_async).grid(row=row, column=0, columnspan=2, sticky="w")
        ttk.Label(left_frame, text="☀️").grid(row=row, column=2, sticky="w")
        row += 1
        
        ttk.Label(left_frame, text="Intensity:").grid(row=row, column=0, sticky="e", padx=(20,0))
        self.effect_brightness_intensity_var = tk.DoubleVar(value=1.15)
        brightness_scale = tk.Scale(left_frame, from_=0.5, to=2.0, resolution=0.05, orient='horizontal', 
                                    length=120, showvalue=0, variable=self.effect_brightness_intensity_var,
                                    command=lambda v: self._mini_update_worker_async())
        brightness_scale.grid(row=row, column=1, padx=(6,0))
        self.brightness_label = ttk.Label(left_frame, text=f"{self.effect_brightness_intensity_var.get():.2f}x")
        self.brightness_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        self.effect_brightness_intensity_var.trace('w', lambda *args: self.brightness_label.config(text=f"{self.effect_brightness_intensity_var.get():.2f}x"))
        row += 1

        # Film grain / Vintage
        self.effect_vintage_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(left_frame, text="Vintage (Film Grain)", variable=self.effect_vintage_var,
                       command=self._mini_update_worker_async).grid(row=row, column=0, columnspan=2, sticky="w")
        ttk.Label(left_frame, text="📽️").grid(row=row, column=2, sticky="w")
        row += 1
        
        ttk.Label(left_frame, text="Grain:").grid(row=row, column=0, sticky="e", padx=(20,0))
        self.effect_vintage_intensity_var = tk.DoubleVar(value=0.3)
        vintage_scale = tk.Scale(left_frame, from_=0.1, to=1.0, resolution=0.05, orient='horizontal', 
                                length=120, showvalue=0, variable=self.effect_vintage_intensity_var,
                                command=lambda v: self._mini_update_worker_async())
        vintage_scale.grid(row=row, column=1, padx=(6,0))
        self.vintage_label = ttk.Label(left_frame, text=f"{self.effect_vintage_intensity_var.get():.2f}")
        self.vintage_label.grid(row=row, column=2, sticky='w', padx=(4,0))
        self.effect_vintage_intensity_var.trace('w', lambda *args: self.vintage_label.config(text=f"{self.effect_vintage_intensity_var.get():.2f}"))
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        ttk.Label(left_frame, text="Top:").grid(row=row, column=0, sticky="e")
        self.top_percent_var = tk.DoubleVar(value=CROP_TOP_RATIO*100)
        self.top_label = ttk.Label(left_frame, text=f"{self.top_percent_var.get():.1f}%")
        self.top_label.grid(row=row, column=1, sticky="w", padx=(6,0))
        row += 1

        ttk.Label(left_frame, text="Bottom:").grid(row=row, column=0, sticky="e")
        self.bottom_percent_var = tk.DoubleVar(value=CROP_BOTTOM_RATIO*100)
        self.bottom_label = ttk.Label(left_frame, text=f"{self.bottom_percent_var.get():.1f}%")
        self.bottom_label.grid(row=row, column=1, sticky="w", padx=(6,0))
        row += 1

        btns = ttk.Frame(left_frame)
        try:
            btns.configure(style='TFrame')
            btns.config(bg='#0b0b0b')
        except Exception:
            pass
        btns.grid(row=row, column=0, columnspan=3, sticky="w", pady=(6,0))
        ttk.Button(btns, text="Save crop settings", command=self.on_save_crop).pack(side="left", padx=4)
        ttk.Button(btns, text="Load crop settings", command=self.on_load_crop).pack(side="left", padx=4)
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        # Settings Preset Section
        ttk.Label(left_frame, text="Settings Presets:").grid(row=row, column=0, sticky="w")
        row += 1
        preset_btns = ttk.Frame(left_frame)
        try:
            preset_btns.configure(style='TFrame')
            preset_btns.config(bg='#0b0b0b')
        except Exception:
            pass
        preset_btns.grid(row=row, column=0, columnspan=3, sticky="w", pady=(6,0))
        ttk.Button(preset_btns, text="💾 Save Preset", command=self.save_preset).pack(side="left", padx=4)
        ttk.Button(preset_btns, text="📂 Load Preset", command=self.load_preset).pack(side="left", padx=4)
        ttk.Button(preset_btns, text="🔄 Reset to Defaults", command=self.reset_to_defaults).pack(side="left", padx=4)
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        ttk.Label(left_frame, text="Job queue:").grid(row=row, column=0, sticky="w")
        row += 1
        self.job_listbox = tk.Listbox(left_frame, height=10, selectmode=tk.EXTENDED, bg='#111111', fg='#FFFFFF')
        self.job_listbox.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(4,0))
        try:
            self.job_listbox.config(selectbackground='#2b2b2b', selectforeground='#FFFFFF', highlightthickness=1, highlightbackground='#222222', bd=2, relief='groove')
        except Exception:
            pass
        # Add double-click binding to load job settings
        self.job_listbox.bind('<Double-Button-1>', self.on_job_double_click)
        left_frame.rowconfigure(row, weight=1)
        row += 1

        job_btns = ttk.Frame(left_frame)
        try:
            job_btns.configure(style='TFrame')
            job_btns.config(bg='#0b0b0b')
        except Exception:
            pass
        job_btns.grid(row=row, column=0, columnspan=3, sticky="w", pady=(6,0))
        ttk.Button(job_btns, text="Add job", command=self.add_job).pack(side="left", padx=4)
        ttk.Button(job_btns, text="Remove selected", command=self.remove_job).pack(side="left", padx=4)
        self.run_queue_btn = ttk.Button(job_btns, text="Run queue", command=self.run_queue)
        self.run_queue_btn.pack(side="left", padx=4)
        row += 1

        ttk.Separator(left_frame).grid(row=row, column=0, columnspan=3, sticky="we", pady=6)
        row += 1

        bottom_controls = ttk.Frame(left_frame)
        try:
            bottom_controls.configure(style='TFrame')
            bottom_controls.config(bg='#0b0b0b')
        except Exception:
            pass
        bottom_controls.grid(row=row, column=0, columnspan=3, sticky="we")
        self.run_single_btn = ttk.Button(bottom_controls, text="Run (single)", command=self.on_run_single)
        self.run_single_btn.pack(side="left", padx=4)
        ttk.Button(bottom_controls, text="Toggle Fullscreen", command=self.toggle_fullscreen).pack(side="left", padx=4)
        ttk.Button(bottom_controls, text="Quit", command=root.quit).pack(side="left", padx=4)

        # preview
        ttk.Label(preview_frame, text="Mini preview: drag lines to adjust crop").pack(anchor="w")
        self.mini_canvas_container = ttk.Frame(preview_frame)
        self.mini_canvas_container.pack(side='left', pady=(6,4), fill="both", expand=False)
        try:
            self.mini_canvas_container.config(style='MiniCanvas.TFrame')
        except Exception:
            pass
        # create a visible dark border by using a frame with padding and a slightly lighter inner bg
        self.mini_canvas_border = tk.Frame(self.mini_canvas_container, bg='#222222', bd=2, relief='solid')
        self.mini_canvas_border.pack(fill='both', expand=True, padx=0, pady=0)
        self.mini_canvas = tk.Canvas(self.mini_canvas_border, width=360, height=640, bg='#111111', highlightthickness=0)
        self.mini_canvas.pack(fill='both', expand=True)
        
        self.mini_image_ref = None
        # font selection panel to the right of the mini preview
        self.font_panel = ttk.Frame(preview_frame)
        self.font_panel.pack(side='left', fill='y', padx=(8,0), pady=(6,4))
        try:
            self.font_panel.configure(style='TFrame')
        except Exception:
            pass
        ttk.Label(self.font_panel, text='Fonts:').pack(anchor='nw')
        self.font_listbox = tk.Listbox(self.font_panel, height=12, exportselection=False)
        self.font_listbox.pack(fill='y', expand=True)
        # preview sample
        self.font_preview = ttk.Label(self.font_panel, text='Sample: Hello!', anchor='center')
        self.font_preview.pack(fill='x', pady=6)
        # --- Color selectors for caption text and stroke (inserted) ---
        try:
            color_frame = ttk.Frame(self.font_panel)
            color_frame.pack(fill='x', pady=(6,4))
            ttk.Label(color_frame, text='Text color:').grid(row=0, column=0, sticky='w')
            self.text_color_canvas = tk.Canvas(color_frame, width=28, height=28, bg='#222222', highlightthickness=1, bd=0)
            self.text_color_canvas.grid(row=0, column=1, padx=(6,12))
            ttk.Button(color_frame, text='Custom...', command=self.on_pick_text_color).grid(row=0, column=2, padx=(0,6))
            ttk.Label(color_frame, text='Stroke color:').grid(row=1, column=0, sticky='w', pady=(6,0))
            self.stroke_color_canvas = tk.Canvas(color_frame, width=28, height=28, bg='#222222', highlightthickness=1, bd=0)
            self.stroke_color_canvas.grid(row=1, column=1, padx=(6,12), pady=(6,0))
            ttk.Button(color_frame, text='Custom...', command=self.on_pick_stroke_color).grid(row=1, column=2, padx=(0,6), pady=(6,0))
            # quick preset swatches below
            swatch_frame = ttk.Frame(self.font_panel)
            swatch_frame.pack(fill='x', pady=(4,6))
            PRESET_SWATCHES = ['#FFFFFF', '#000000', '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF', '#FFA500', '#800080']
            ttk.Label(swatch_frame, text='Presets:').pack(anchor='w')
            sf = tk.Frame(swatch_frame, bg='#0b0b0b')
            sf.pack(fill='x', pady=(4,0))

            # --- Stroke width control ---
            try:
                sw_frame = ttk.Frame(self.font_panel)
                sw_frame.pack(fill='x', pady=(6,4))
                ttk.Label(sw_frame, text='Stroke width:').grid(row=0, column=0, sticky='w')
                max_w = max(1, int(CAPTION_FONT_SIZE * 0.5))
                self.stroke_width_var = tk.DoubleVar(value=float(globals().get('CAPTION_STROKE_WIDTH', max(1, int(CAPTION_FONT_SIZE * 0.05)))))
                self.stroke_width_scale = tk.Scale(sw_frame, from_=0, to=max_w, orient='horizontal', length=140, showvalue=0, variable=self.stroke_width_var, command=self.on_stroke_width_changed)
                self.stroke_width_scale.grid(row=0, column=1, padx=(6,8))
                self.stroke_width_label = ttk.Label(sw_frame, text=str(int(self.stroke_width_var.get())))
                self.stroke_width_label.grid(row=0, column=2, sticky='w')
            except Exception:
                pass

            # --- Caption vertical position control (NEW) ---
            try:
                pos_frame = ttk.Frame(self.font_panel)
                pos_frame.pack(fill='x', pady=(6,4))
                ttk.Label(pos_frame, text='Caption Y offset:').grid(row=0, column=0, sticky='w')
                # Offset from bottom in pixels (0 = at bottom, negative = move up, positive = move down)
                self.caption_y_offset_var = tk.IntVar(value=0)
                self.caption_y_offset_scale = tk.Scale(pos_frame, from_=-1080, to=200, orient='horizontal', length=140, showvalue=0, variable=self.caption_y_offset_var, command=self.on_caption_position_changed)
                self.caption_y_offset_scale.grid(row=0, column=1, padx=(6,8))
                self.caption_y_offset_label = ttk.Label(pos_frame, text=f"{self.caption_y_offset_var.get()}px")
                self.caption_y_offset_label.grid(row=0, column=2, sticky='w')
            except Exception:
                pass

            for c in PRESET_SWATCHES:
                b = tk.Canvas(sf, width=22, height=22, bg=c, highlightthickness=1, bd=0)
                b.pack(side='left', padx=4)
                b.bind('<Button-1>', lambda e, col=c: self._set_text_color_hex(col))
                b.bind('<Button-3>', lambda e, col=c: self._set_stroke_color_hex(col))
        except Exception:
            pass

        # --- Caption template selector + preview ---
        try:
            self.template_var = tk.StringVar(value='2 words')
            ttk.Label(self.font_panel, text='Caption template:').pack(anchor='nw', pady=(6,0))
            self.template_cb = ttk.Combobox(self.font_panel, values=['1 word', '2 words', '3 words'], textvariable=self.template_var, state='readonly', width=20)
            self.template_cb.pack(fill='x', pady=(2,4))
            self.template_cb.bind('<<ComboboxSelected>>', self.on_template_selected)
            # Preview area for generated caption image
            self.caption_preview_canvas = tk.Canvas(self.font_panel, width=320, height=120, bg='#111111', highlightthickness=0)
            self.caption_preview_canvas.pack(pady=(4,6))
            ttk.Button(self.font_panel, text='Preview template', command=self.on_preview_template).pack(pady=(0,6))
        except Exception:
            pass

        
# load only fonts from the C:	iktok folder (only .ttf/.otf)
        try:
            self._tiktok_font_paths = {}
            fams = []
            search_root = os.path.normpath("C:\\tiktok")
            for root, dirs, files in os.walk(search_root):
                for fn in files:
                    if fn.lower().endswith((".ttf", ".otf")):
                        name = os.path.splitext(fn)[0]
                        display = name
                        path = os.path.join(root, fn)
                        if display not in self._tiktok_font_paths:
                            self._tiktok_font_paths[display] = path
                            fams.append(display)
            fams = sorted(fams, key=lambda s: s.lower())
        except Exception:
            fams = ['Arial', 'Helvetica', 'Times']
        for f in fams:
            try:
                self.font_listbox.insert('end', f)
            except Exception:
                pass
        self.font_listbox.bind('<<ListboxSelect>>', self.on_font_selected)
        if not hasattr(self, 'saved_fonts'):
            self.saved_fonts = {}

        # save/load font buttons
        btn_frame = ttk.Frame(self.font_panel)
        try:
            btn_frame.configure(style='TFrame')
        except Exception:
            pass
        btn_frame.pack(fill='x', pady=(4,0))
        self.save_font_btn = ttk.Button(btn_frame, text='Save font for video', command=self.on_save_font_clicked)
        self.save_font_btn.pack(side='left', padx=(0,4))
        self.load_font_btn = ttk.Button(btn_frame, text='Load saved font', command=self.on_load_font_clicked)
        self.load_font_btn.pack(side='left')
        self.saved_font_label = ttk.Label(self.font_panel, text='Saved: None', anchor='w')
        self.saved_font_label.pack(fill='x', pady=(4,0))
        self.selected_font = None

        self.selected_font_path = None
        self.mini_worker_thread = None

        tl_frame = ttk.Frame(preview_frame)
        try:
            tl_frame.configure(style='TFrame')
            tl_frame.config(bg='#0b0b0b')
        except Exception:
            pass
        tl_frame.pack(fill="x", pady=(4,0))
        self.time_var = tk.DoubleVar(value=0.0)
        self.time_scale = CanvasSlider(tl_frame, from_=0.0, to=1.0, orient="horizontal", length=360, resolution=0.1, variable=self.time_var, command=self.on_time_changed)
        self.time_scale.pack(side="left", fill="x", expand=True)
        self.time_label = ttk.Label(tl_frame, text="00:00")
        self.time_label.pack(side="left", padx=6)
        
        # --- Zoom Control Slider ---
        zoom_frame = ttk.Frame(preview_frame)
        try:
            zoom_frame.configure(style='TFrame')
            zoom_frame.config(bg='#0b0b0b')
        except Exception:
            pass
        zoom_frame.pack(fill="x", pady=(4,0))
        ttk.Label(zoom_frame, text="Video Zoom:").pack(side="left")
        self.zoom_var = tk.DoubleVar(value=1.0)
        self.zoom_scale = CanvasSlider(zoom_frame, from_=0.5, to=2.0, orient="horizontal", length=300, resolution=0.01, variable=self.zoom_var, command=self.on_zoom_changed)
        self.zoom_scale.pack(side="left", fill="x", expand=True, padx=4)
        self.zoom_label = ttk.Label(zoom_frame, text="1.00x")
        self.zoom_label.pack(side="left", padx=6)
        
        ttk.Button(preview_frame, text="Refresh mini preview", command=self.on_mini_refresh_clicked).pack(pady=(6,0))
        
        # --- TikTok Format Preview (9:16 aspect ratio) ---
        tiktok_preview_frame = ttk.Frame(preview_frame)
        try:
            tiktok_preview_frame.configure(style='TFrame')
            tiktok_preview_frame.config(bg='#0b0b0b')
        except Exception:
            pass
        tiktok_preview_frame.pack(fill='both', expand=False, pady=(6,0))
        ttk.Label(tiktok_preview_frame, text="TikTok Preview (9:16):").pack(anchor="w")
        self.tiktok_preview_border = tk.Frame(tiktok_preview_frame, bg='#222222', bd=2, relief='solid')
        self.tiktok_preview_border.pack(fill='both', expand=True, padx=0, pady=(4,0))
        # 180x320 = 9:16 aspect ratio
        self.tiktok_preview_canvas = tk.Canvas(self.tiktok_preview_border, width=180, height=320, bg='#111111', highlightthickness=0)
        self.tiktok_preview_canvas.pack(fill='both', expand=True)
        self.tiktok_preview_image_ref = None
        
        ttk.Button(preview_frame, text="Refresh TikTok Preview", command=self.on_tiktok_preview_refresh).pack(pady=(6,0))

        self.mini_canvas.bind("<ButtonPress-1>", self._mini_on_mouse_down)
        self.mini_canvas.bind("<B1-Motion>", self._mini_on_mouse_move)
        self.mini_canvas.bind("<ButtonRelease-1>", self._mini_on_mouse_up)

        self.mini_base_img = None
        self.mini_scale = 1.0
        self.dragging = None
        self.drag_threshold_px = 9

        bottom_frame.columnconfigure(0, weight=1)
        bottom_frame.columnconfigure(1, weight=1)

        log_label = ttk.Label(bottom_frame, text="Log:")
        log_label.grid(row=0, column=0, sticky="w")
        self.log_widget = ScrolledText(bottom_frame, width=80, height=12, state="disabled", wrap="word")
        self.log_widget.grid(row=1, column=0, sticky="nsew", padx=(0,8))
        try:
            self.log_widget.config(bg='#0f0f0f', fg='#FFFFFF', insertbackground='#FFFFFF', selectbackground='#2b2b2b', selectforeground='#FFFFFF')
        except Exception:
            pass

        right_status = ttk.Frame(bottom_frame)
        try:
            right_status.configure(style='TFrame')
            right_status.config(bg='#0b0b0b')
        except Exception:
            pass
        right_status.grid(row=1, column=1, sticky="nsew")
        right_status.columnconfigure(0, weight=1)
        ttk.Label(right_status, text="Preview info:").grid(row=0, column=0, sticky="w")
        self.preview_info = ttk.Label(right_status, text="No preview")
        self.preview_info.grid(row=1, column=0, sticky="nw")
        self.font_info = ttk.Label(right_status, text="")
        self.font_info.grid(row=2, column=0, sticky="nw", pady=(6,0))

        # internal job list
        self.jobs = []

        self.root.after(200, self.poll_queue)
        try:
            self._update_color_canvases()
        except Exception:
            pass


        data = load_crop_settings()
        if data:
            try:
                self.top_percent_var.set(float(data.get("top_pct", CROP_TOP_RATIO*100)))
                self.bottom_percent_var.set(float(data.get("bottom_pct", CROP_BOTTOM_RATIO*100)))
                self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
                self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")
                self.use_custom_crop_var.set(True)
            except Exception:
                pass

        self.time_update_after_id = None
        # last time we triggered a preview update (used for simple throttling)
        self._last_time_update_ts = 0.0
        # cached preview clip for faster scrubbing
        self._preview_clip = None
        # ensure we cleanup moviepy processes on window close
        try:
            self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        except Exception:
            pass

        # persistent mini-preview request handling
        self._mini_request_time = None
        try:
            self._mini_request_event = threading.Event()
        except Exception:
            self._mini_request_event = None
        self._mini_persistent_thread = None
        self._mini_request_stop = False
        self._mini_update_worker_async()

    def _rgba_from_hex(self, hx):
        try:
            if hx.startswith('#'): hx = hx[1:]
            if len(hx) == 6:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16)
                return (r,g,b,255)
            if len(hx) == 8:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16); a = int(hx[6:8],16)
                return (r,g,b,a)
        except Exception:
            pass
        return (255,255,255,255)

    def _update_color_canvases(self):
        try:
            try:
                txt = CAPTION_TEXT_COLOR
                col = '#%02x%02x%02x' % (txt[0], txt[1], txt[2])
                if hasattr(self, 'text_color_canvas') and self.text_color_canvas:
                    self.text_color_canvas.delete('all')
                    self.text_color_canvas.create_oval(2,2,26,26, fill=col, outline='white')
            except Exception:
                pass
            try:
                st = CAPTION_STROKE_COLOR
                col2 = '#%02x%02x%02x' % (st[0], st[1], st[2])
                if hasattr(self, 'stroke_color_canvas') and self.stroke_color_canvas:
                    self.stroke_color_canvas.delete('all')
                    self.stroke_color_canvas.create_oval(2,2,26,26, fill=col2, outline='white')
            except Exception:
                pass
        except Exception:
            pass

    def on_pick_text_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption text color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                globals()['CAPTION_TEXT_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_pick_stroke_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption stroke color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                if len(rgba) == 4 and rgba[3] == 255:
                    rgba = (rgba[0], rgba[1], rgba[2], 150)
                globals()['CAPTION_STROKE_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def _set_text_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            globals()['CAPTION_TEXT_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass

    def _set_stroke_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            rgba = (rgba[0], rgba[1], rgba[2], 150)
            globals()['CAPTION_STROKE_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass


    


    def on_stroke_width_changed(self, val):
        try:
            # val comes as string; set global and update label
            try:
                w = int(float(val))
            except Exception:
                try:
                    w = int(val)
                except Exception:
                    w = max(1, int(CAPTION_FONT_SIZE * 0.05))
            globals()['CAPTION_STROKE_WIDTH'] = max(0, w)
            try:
                if hasattr(self, 'stroke_width_label') and self.stroke_width_label:
                    self.stroke_width_label.config(text=str(int(globals().get('CAPTION_STROKE_WIDTH', w))))
            except Exception:
                pass
        except Exception as e:
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[STROKE-ERR] {e}\n")
                self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_voice_gain_changed(self, val):
        """Callback when voice volume slider changes"""
        try:
            gain = float(val)
            globals()['VOICE_GAIN'] = gain
            if hasattr(self, 'voice_gain_label') and self.voice_gain_label:
                self.voice_gain_label.config(text=f"{gain:.1f}x")
        except Exception:
            pass

    def on_music_gain_changed(self, val):
        """Callback when music volume slider changes"""
        try:
            gain = float(val)
            globals()['MUSIC_GAIN'] = gain
            if hasattr(self, 'music_gain_label') and self.music_gain_label:
                self.music_gain_label.config(text=f"{gain:.2f}x")
        except Exception:
            pass
    
    def on_translation_toggle(self):
        """Callback when translation checkbox is toggled"""
        try:
            enabled = self.translation_enabled_var.get()
            globals()['TRANSLATION_ENABLED'] = enabled
            if enabled and not TRANSLATION_AVAILABLE:
                messagebox.showwarning(
                    "Translation Unavailable",
                    "Translation library (googletrans) is not installed.\nPlease install it with: pip install googletrans==4.0.0rc1"
                )
                self.translation_enabled_var.set(False)
                globals()['TRANSLATION_ENABLED'] = False
        except Exception as e:
            print(f"Translation toggle error: {e}")
    
    def on_language_selected(self, event=None):
        """Callback when target language is selected"""
        try:
            lang = self.target_language_var.get()
            globals()['TARGET_LANGUAGE'] = lang
        except Exception as e:
            print(f"Language selection error: {e}")
    
    def on_ai_voice_toggle(self):
        """Callback when AI voice replacement checkbox is toggled"""
        try:
            enabled = self.use_ai_voice_var.get()
            globals()['USE_AI_VOICE_REPLACEMENT'] = enabled
            if enabled and not TTS_AVAILABLE:
                messagebox.showwarning(
                    "TTS Unavailable",
                    "Text-to-Speech library (gTTS) is not installed.\nPlease install it with: pip install gtts"
                )
                self.use_ai_voice_var.set(False)
                globals()['USE_AI_VOICE_REPLACEMENT'] = False
        except Exception as e:
            print(f"AI voice toggle error: {e}")
    
    def on_tts_language_selected(self, event=None):
        """Callback when TTS language is selected"""
        try:
            lang = self.tts_language_var.get()
            globals()['TTS_LANGUAGE'] = lang
            
            # Update voice dropdown based on selected language (including custom voices)
            self.update_voice_dropdown(lang)
        except Exception as e:
            print(f"TTS language selection error: {e}")
    
    def load_custom_voices(self):
        """Load custom voices from config file"""
        try:
            config_path = os.path.join(os.path.dirname(__file__), "tts_config.json")
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    return config.get("custom_voices", {})
        except Exception as e:
            print(f"Error loading custom voices: {e}")
        return {}
    
    def update_voice_dropdown(self, language=None):
        """Update voice dropdown with default and custom voices for the selected language"""
        try:
            if language is None:
                language = self.tts_language_var.get()
            
            # Start with default voices
            voices = self.voice_options.get(language, ['Auto (Default)']).copy()
            
            # Load and add custom voices
            custom_voices = self.load_custom_voices()
            if language in custom_voices:
                for voice_data in custom_voices[language]:
                    if isinstance(voice_data, dict):
                        voice_name = voice_data.get("name")
                        voice_id = voice_data.get("id")
                        if voice_name and voice_id:
                            # Add to voices list if not already there
                            if voice_name not in voices:
                                voices.append(voice_name)
                            # Update the voice ID map
                            self.voice_id_map[voice_name] = voice_id
            
            # Update the combobox
            self.tts_voice_combo['values'] = voices
            self.tts_voice_var.set('Auto (Default)')  # Reset to auto
            globals()['TTS_VOICE_ID'] = 'auto'
            
            print(f"[Voice Dropdown] Updated for {language}: {len(voices)} voices available")
        except Exception as e:
            print(f"Update voice dropdown error: {e}")
    
    def on_voice_selected(self, event=None):
        """Callback when a specific voice is selected"""
        try:
            voice_name = self.tts_voice_var.get()
            voice_id = self.voice_id_map.get(voice_name, 'auto')
            globals()['TTS_VOICE_ID'] = voice_id
            print(f"[Voice Selection] Selected: {voice_name} (ID: {voice_id})")
        except Exception as e:
            print(f"Voice selection error: {e}")
    
    def on_save_api_key(self):
        """Callback when Save API Key button is clicked"""
        try:
            api_key = self.tts_api_key_var.get().strip()
            if not api_key:
                messagebox.showwarning("No API Key", "Please enter an API key.")
                return
            
            # Save to config file
            config_path = os.path.join(os.path.dirname(__file__), "tts_config.json")
            config = {"api_key": api_key}
            
            try:
                with open(config_path, 'w') as f:
                    json.dump(config, f)
                messagebox.showinfo("API Key Saved", "Your API key has been saved successfully!")
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save API key: {e}")
        except Exception as e:
            print(f"Save API key error: {e}")
    
    def on_save_custom_voice(self):
        """Callback when Save Custom Voice button is clicked"""
        try:
            voice_id = self.custom_voice_id_var.get().strip()
            voice_name = self.custom_voice_name_var.get().strip()
            language = self.custom_voice_lang_var.get()
            
            if not voice_id:
                messagebox.showwarning("No Voice ID", "Please enter a voice ID.")
                return
            
            if not voice_name:
                messagebox.showwarning("No Voice Name", "Please enter a name for this voice.")
                return
            
            # Load existing config
            config_path = os.path.join(os.path.dirname(__file__), "tts_config.json")
            config = {}
            try:
                if os.path.exists(config_path):
                    with open(config_path, 'r') as f:
                        config = json.load(f)
            except Exception:
                pass
            
            # Add custom voices section if not exists
            if "custom_voices" not in config:
                config["custom_voices"] = {}
            
            # Add the custom voice
            if language not in config["custom_voices"]:
                config["custom_voices"][language] = []
            
            # Check if voice name already exists for this language
            existing_voices = config["custom_voices"][language]
            voice_exists = any(v["name"] == voice_name for v in existing_voices if isinstance(v, dict))
            
            if voice_exists:
                response = messagebox.askyesno(
                    "Voice Exists", 
                    f"A voice named '{voice_name}' already exists for {language}. Do you want to update it?"
                )
                if not response:
                    return
                # Remove the old one
                config["custom_voices"][language] = [v for v in existing_voices if not (isinstance(v, dict) and v.get("name") == voice_name)]
            
            # Add the new voice
            config["custom_voices"][language].append({
                "name": voice_name,
                "id": voice_id
            })
            
            # Save config
            try:
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                messagebox.showinfo("Custom Voice Saved", f"Voice '{voice_name}' has been saved for {language.upper()}!")
                
                # Clear the input fields
                self.custom_voice_id_var.set("")
                self.custom_voice_name_var.set("")
                
                # Reload voices in the dropdown
                self.update_voice_dropdown()
                
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save custom voice: {e}")
        except Exception as e:
            print(f"Save custom voice error: {e}")
    
    def on_4k_toggle(self):
        """Toggle between HD (1080x1920) and 4K (2160x3840) resolution"""
        try:
            use_4k = self.use_4k_var.get()
            if use_4k:
                # 4K is 2x HD resolution
                globals()['WIDTH'] = 2160
                globals()['HEIGHT'] = 3840
                # Scale caption font size for 4K (2x)
                globals()['CAPTION_FONT_SIZE'] = 112  # 56 * 2
                # Update stroke width based on new font size
                globals()['CAPTION_STROKE_WIDTH'] = max(1, int(112 * 0.05))
                # Scale background zoom factor for 4K
                globals()['BG_SCALE_EXTRA'] = 1.08  # Keep same for both (proportional to resolution)
                # Mark that we're in 4K mode for scaling calculations
                globals()['IS_4K_MODE'] = True
                # Update caption Y offset slider range for 4K (-3840 to +200)
                if hasattr(self, 'caption_y_offset_scale'):
                    self.caption_y_offset_scale.config(from_=-3840, to=200)
                    # Scale current offset value (multiply by 2)
                    current_offset = self.caption_y_offset_var.get()
                    self.caption_y_offset_var.set(current_offset * 2)
                # Log resolution change
                try:
                    self.log_widget.config(state='normal')
                    self.log_widget.insert('end', "Resolution set to 4K: 2160x3840\n")
                    self.log_widget.insert('end', "Caption font size scaled to: 112px\n")
                    self.log_widget.insert('end', "Zoom/scale factors adjusted for 4K\n")
                    self.log_widget.see('end')
                    self.log_widget.config(state='disabled')
                except Exception:
                    pass
            else:
                # HD resolution
                globals()['WIDTH'] = 1080
                globals()['HEIGHT'] = 1920
                # Reset caption font size to default HD (56)
                globals()['CAPTION_FONT_SIZE'] = 56
                # Update stroke width based on default font size
                globals()['CAPTION_STROKE_WIDTH'] = max(1, int(56 * 0.05))
                # Reset background zoom factor for HD
                globals()['BG_SCALE_EXTRA'] = 1.08
                # Mark that we're in HD mode
                globals()['IS_4K_MODE'] = False
                # Reset caption Y offset slider range for HD (-1080 to +200)
                if hasattr(self, 'caption_y_offset_scale'):
                    self.caption_y_offset_scale.config(from_=-1920, to=200)
                    # Scale current offset value back (divide by 2)
                    current_offset = self.caption_y_offset_var.get()
                    self.caption_y_offset_var.set(current_offset // 2)
                # Log resolution change
                try:
                    self.log_widget.config(state='normal')
                    self.log_widget.insert('end', "Resolution set to HD: 1080x1920\n")
                    self.log_widget.insert('end', "Caption font size reset to: 56px\n")
                    self.log_widget.insert('end', "Zoom/scale factors reset to HD\n")
                    self.log_widget.see('end')
                    self.log_widget.config(state='disabled')
                except Exception:
                    pass
        except Exception as e:
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[4K-TOGGLE-ERR] {e}\n")
                self.log_widget.see('end')
                self.log_widget.config(state='disabled')
            except Exception:
                pass

    def _draw_caption_indicator_on_preview(self, composed, h, top_y, bottom_y, offset):
        """Draw the caption position indicator on the mini preview canvas.
        
        Args:
            composed: The composed PIL image
            h: Canvas height
            top_y: Top crop line Y position
            bottom_y: Bottom crop line Y position
            offset: Caption Y offset value
        """
        try:
            # DELETE old caption indicator items first to prevent stacking
            self.mini_canvas.delete("caption_line")
            self.mini_canvas.delete("caption_box")
            self.mini_canvas.delete("caption_label")
            
            # Calculate where caption will appear on the preview
            # offset: negative = move up, positive = move down
            # In actual video: y = HEIGHT - caption_height + offset
            # In preview: caption_y = h - (scaled distance from bottom)
            # distance_from_bottom in video = HEIGHT - (HEIGHT - caption_height + offset) = caption_height - offset
            # For indicator baseline (bottom of caption): distance_from_bottom = -offset (approximately, ignoring caption height)
            preview_ratio = h / HEIGHT if HEIGHT > 0 else 1.0
            caption_baseline_from_bottom = int(-offset * preview_ratio)  # Negative offset means higher (less from bottom)
            caption_y = h - caption_baseline_from_bottom
            
            # DO NOT clamp to crop lines - show actual caption position even if outside crop area
            # Only clamp to canvas boundaries (0 to h)
            caption_y = max(5, min(h - 5, caption_y))
            
            # Draw green dashed line showing caption baseline - PERMANENT
            self.mini_canvas.create_line(0, caption_y, composed.width, caption_y, 
                                        fill="#00FF00", dash=(6, 4), width=3, tags="caption_line")
            
            # Draw outlined box showing caption area
            box_width = 80
            box_height = 18
            self.mini_canvas.create_rectangle(composed.width//2 - box_width, caption_y - box_height, 
                                             composed.width//2 + box_width, caption_y, 
                                             fill="", outline="#00FF00", width=2, tags="caption_box")
            
            # Draw label with offset value
            self.mini_canvas.create_text(composed.width//2, caption_y - box_height//2, 
                                        text=f"Caption Y: {offset}px", 
                                        fill="#00FF00", font=("Arial", 9, "bold"), tags="caption_label")
            
            # Removed repetitive logging - caption position only logged once during processing
                
        except Exception as e:
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[CAPTION-INDICATOR-ERR] {e}\n")
                self.log_widget.config(state='disabled')
            except Exception:
                pass

    def _redraw_mini_canvas_with_caption_indicator(self, composed, top_pct, bottom_pct):
        """Helper to redraw the entire mini canvas with crop lines and caption indicator.
        
        This ensures the caption indicator is ALWAYS drawn on every mini preview update.
        """
        try:
            photo = ImageTk.PhotoImage(composed)
            h = composed.height
            top_y = int(round(h * top_pct))
            bottom_y = int(round(h * (1.0 - bottom_pct)))
            
            # Clear and redraw canvas
            self.mini_canvas.delete("all")
            self.mini_canvas.create_image(0, 0, anchor="nw", image=photo, tags="base_img")
            self.mini_image_ref = photo  # Keep reference
            
            # Draw crop lines
            self.mini_canvas.create_rectangle(0, top_y-4, composed.width, top_y+4, 
                                            fill="#000000", stipple="gray50", tags="line_top")
            self.mini_canvas.create_rectangle(0, bottom_y-4, composed.width, bottom_y+4, 
                                            fill="#000000", stipple="gray50", tags="line_bottom")
            self.mini_canvas.create_text(6, max(6, top_y-18), anchor="nw", 
                                        text=f"Top {int(top_pct*100)}% ({top_y}px)", 
                                        fill="#fff", font=("Arial",9), tags="label_top")
            self.mini_canvas.create_text(6, min(h-18, bottom_y+6), anchor="nw", 
                                        text=f"Bottom {int(bottom_pct*100)}% ({h - bottom_y}px)", 
                                        fill="#fff", font=("Arial",9), tags="label_bottom")
            
            # ALWAYS draw caption position indicator
            y_offset = globals().get('CAPTION_Y_OFFSET', 0)
            self._draw_caption_indicator_on_preview(composed, h, top_y, bottom_y, y_offset)
            
            # Removed repetitive mini-redraw logging
                
        except Exception as e:
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[MINI-REDRAW-ERR] {e}\n")
                self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_caption_position_changed(self, val):
        """Callback when caption vertical position slider changes."""
        try:
            # val comes as string; set global and update label
            try:
                offset = int(float(val))
            except Exception:
                try:
                    offset = int(val)
                except Exception:
                    offset = 0
            globals()['CAPTION_Y_OFFSET'] = offset
            try:
                if hasattr(self, 'caption_y_offset_label') and self.caption_y_offset_label:
                    self.caption_y_offset_label.config(text=f"{offset}px")
            except Exception:
                pass
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[CAPTION-POS-CHANGE] Y offset changed to: {offset}px\n")
                self.log_widget.config(state='disabled')
                self.log_widget.see('end')
            except Exception:
                pass
            
            # Update mini preview to show new caption position - FORCE REDRAW
            try:
                if hasattr(self, 'mini_base_img') and self.mini_base_img is not None:
                    # Redraw the mini preview with updated caption indicator
                    top_pct = float(self.top_percent_var.get())/100.0
                    bottom_pct = float(self.bottom_percent_var.get())/100.0
                    composed = overlay_crop_on_image(self.mini_base_img, top_pct, bottom_pct)
                    # Use centralized redraw method that ALWAYS includes caption indicator
                    self._redraw_mini_canvas_with_caption_indicator(composed, top_pct, bottom_pct)
                    # Force canvas update
                    self.mini_canvas.update_idletasks()
                    
            except Exception as e:
                try:
                    self.log_widget.config(state='normal')
                    self.log_widget.insert('end', f"[CAPTION-UPDATE-ERR] {e}\n")
                    self.log_widget.config(state='disabled')
                except Exception:
                    pass
        except Exception as e:
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[CAPTION-POS-ERR] {e}\n")
                self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_template_selected(self, event=None):
        try:
            sel = (self.template_var.get() if hasattr(self, 'template_var') else '2 words').strip()
            num = 2
            try:
                if sel and sel[0].isdigit():
                    num = int(sel[0])
            except Exception:
                num = 2
            globals()['CAPTION_TEMPLATE'] = num
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[TEMPLATE] Selected: {sel} -> CAPTION_TEMPLATE={globals().get('CAPTION_TEMPLATE')}\n")
                self.log_widget.see('end')
                self.log_widget.config(state='disabled')
            except Exception:
                pass
        except Exception as e:
            print('Template select error:', e)


    def on_preview_template(self):
        # Generate a sample caption image using the selected template and show only ONE group (1/2/3 words)
        try:
            sample_text = "THIS IS A SAMPLE PREVIEW\nHow will it look?"
            sel = self.template_var.get() if hasattr(self, 'template_var') else '2 words'
            try:
                val = int(sel[0]) if sel and sel[0].isdigit() else 2
            except Exception:
                val = 2
            if val <= 0:
                val = 2
            # split into words and take the first 'val' words as a single caption
            words = sample_text.split()
            first_group = ' '.join(words[0:val]) if words else sample_text
            preview_text = first_group

                        # determine preferred font: prefer selected_font_path (ttf path) else selected_font family name
            pf = None
            try:
                if getattr(self, 'selected_font_path', None):
                    pf = self.selected_font_path
                elif getattr(self, 'selected_font', None):
                    pf = self.selected_font
            except Exception:
                pf = None
            img_obj = generate_caption_image(preview_text, preferred_font=pf, log=lambda s: None)
            from PIL import Image
            # Accept either PIL.Image or numpy.ndarray (compatibility)
            if isinstance(img_obj, Image.Image):
                im = img_obj.convert('RGBA')
            else:
                im = Image.fromarray(img_obj).convert('RGBA')
            # resize to fit canvas width if necessary
            max_w = int(self.caption_preview_canvas['width']); max_h = int(self.caption_preview_canvas['height'])
            w, h = im.size
            scale = min(max_w / w, max_h / h, 1.0)
            if scale < 1.0:
                im = im.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
            im_tk = ImageTk.PhotoImage(im)
            # store ref to avoid GC
            self._caption_preview_im = im_tk
            self.caption_preview_canvas.delete('all')
            
            # Get caption Y offset for position visualization
            y_offset = globals().get('CAPTION_Y_OFFSET', 0)
            cw = int(self.caption_preview_canvas['width']); ch = int(self.caption_preview_canvas['height'])
            
            # Simulate caption position in preview
            # In actual video: y = HEIGHT - caption_height - y_offset
            # In preview: proportional position from bottom
            preview_ratio = ch / HEIGHT if HEIGHT > 0 else 1.0
            simulated_y_pos = ch - im.height - int(y_offset * preview_ratio)
            
            # Clamp to canvas bounds
            simulated_y_pos = max(0, min(ch - im.height, simulated_y_pos))
            
            # Center image horizontally, position vertically based on offset
            x = (cw - im.width) // 2
            y = simulated_y_pos
            
            # Draw position indicator line at bottom to show baseline
            baseline_y = ch - int(y_offset * preview_ratio)
            self.caption_preview_canvas.create_line(0, baseline_y, cw, baseline_y, fill='#00FF00', dash=(4, 4), width=1)
            self.caption_preview_canvas.create_text(5, baseline_y - 10, text=f'Y offset: {y_offset}px', anchor='w', fill='#00FF00', font=('Arial', 8))
            
            self.caption_preview_canvas.create_image(x, y, anchor='nw', image=im_tk)
        except Exception as e:
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[PREVIEW-ERR] {e}\n")
                self.log_widget.see('end')
                self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_save_font_clicked(self):
        try:
            font = self.selected_font or (self.font_listbox.get(self.font_listbox.curselection()) if self.font_listbox.curselection() else None)
        except Exception:
            font = None
        video = self.video_var.get().strip() or self.output_var.get().strip()
        if not video:
            messagebox.showwarning("No video", "Select a video or set output filename before saving a font.")
            return
        if font:
            try:
                self.saved_fonts[video] = font
                self.saved_font_label.config(text=f"Saved: {font}")
                messagebox.showinfo("Saved", f"Saved font '{font}' for this video.")
            except Exception:
                pass
        else:
            messagebox.showwarning("No font", "Select a font first.")

    def on_load_font_clicked(self):
        video = self.video_var.get().strip() or self.output_var.get().strip()
        if not video:
            messagebox.showwarning("No video", "Select a video or set output filename before loading a font.")
            return
        font = self.saved_fonts.get(video)
        if not font:
            messagebox.showinfo("No saved font", "No font saved for this video.")
            return
        # select in listbox if available
        try:
            idxs = self.font_listbox.get(0, 'end')
            if font in idxs:
                i = idxs.index(font)
                self.font_listbox.selection_clear(0, 'end')
                self.font_listbox.selection_set(i)
                self.font_listbox.see(i)
                self.on_font_selected()
                messagebox.showinfo("Loaded", f"Loaded font '{font}' for this video.")
                self.saved_font_label.config(text=f"Saved: {font}")
        except Exception:
            pass
# ---------- UI callbacks & helpers ----------
    def toggle_fullscreen(self):
        try:
            if sys.platform == "win32":
                if self.root.state() == "normal":
                    self.root.state('zoomed')
                else:
                    self.root.state('normal')
            else:
                cur = bool(self.root.attributes("-fullscreen"))
                self.root.attributes("-fullscreen", not cur)
        except Exception:
            pass

    def browse_video(self):
        path = filedialog.askopenfilename(title="Select video", filetypes=[("Video files", "*.mp4 *.mov *.mkv *.avi"), ("All files", "*.*")])
        if path:
            self.video_var.set(path)
            try:
                # close previous preview clip if present
                try:
                    if hasattr(self, "_preview_clip") and self._preview_clip:
                        try:
                            self.safe_close_clip(self._preview_clip)
                        except Exception:
                            pass
                except Exception:
                    pass
                try:
                    self._preview_clip = VideoFileClip(path)
                    dur = self._preview_clip.duration
                except Exception:
                    # fallback if caching fails
                    clip = VideoFileClip(path)
                    dur = clip.duration
                    clip.close()
                try:
                    self.time_scale.to = max(0.1, dur)
                    self.time_scale.set(min(self.time_var.get(), self.time_scale.to))
                except Exception:
                    try:
                        self.time_scale.config(to=max(0.1, dur))
                    except Exception:
                        pass
                try:
                    self.time_var.set(min(self.time_var.get(), dur))
                    self.time_label.config(text=seconds_to_hms(self.time_var.get()))
                except Exception:
                    pass
            except Exception:
                try:
                    self.time_scale.to = 1.0
                    self.time_scale.set(min(self.time_var.get(), 1.0))
                except Exception:
                    try:
                        self.time_scale.config(to=1.0)
                    except Exception:
                        pass
            self._mini_update_worker_async()

    def _rgba_from_hex(self, hx):
        try:
            if hx.startswith('#'): hx = hx[1:]
            if len(hx) == 6:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16)
                return (r,g,b,255)
            if len(hx) == 8:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16); a = int(hx[6:8],16)
                return (r,g,b,a)
        except Exception:
            pass
        return (255,255,255,255)

    def _update_color_canvases(self):
        try:
            try:
                txt = CAPTION_TEXT_COLOR
                col = '#%02x%02x%02x' % (txt[0], txt[1], txt[2])
                if hasattr(self, 'text_color_canvas') and self.text_color_canvas:
                    self.text_color_canvas.delete('all')
                    self.text_color_canvas.create_oval(2,2,26,26, fill=col, outline='white')
            except Exception:
                pass
            try:
                st = CAPTION_STROKE_COLOR
                col2 = '#%02x%02x%02x' % (st[0], st[1], st[2])
                if hasattr(self, 'stroke_color_canvas') and self.stroke_color_canvas:
                    self.stroke_color_canvas.delete('all')
                    self.stroke_color_canvas.create_oval(2,2,26,26, fill=col2, outline='white')
            except Exception:
                pass
        except Exception:
            pass

    def on_pick_text_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption text color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                globals()['CAPTION_TEXT_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_pick_stroke_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption stroke color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                if len(rgba) == 4 and rgba[3] == 255:
                    rgba = (rgba[0], rgba[1], rgba[2], 150)
                globals()['CAPTION_STROKE_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def _set_text_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            globals()['CAPTION_TEXT_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass

    def _set_stroke_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            rgba = (rgba[0], rgba[1], rgba[2], 150)
            globals()['CAPTION_STROKE_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass


    def safe_close_clip(self, clip):
        """Închide în siguranță un VideoFileClip/reader fără a arunca excepții."""
        if not clip:
            return
        try:
            # If there's a reader with a proc, try to terminate it safely
            reader = getattr(clip, "reader", None)
            if reader is not None:
                proc = getattr(reader, "proc", None)
                if proc is not None:
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                try:
                    reader.close()
                except Exception:
                    pass
        except Exception:
            pass

        try:
            clip.close()
        except Exception:
            pass

    def on_close(self):
        try:
            self._stop_mini_persistent_worker()
        except Exception:
            pass

        """Cleanup la închiderea aplicației: închide clipurile din cache și distruge fereastra."""
        try:
            if hasattr(self, "_preview_clip") and self._preview_clip:
                try:
                    self.safe_close_clip(self._preview_clip)
                except Exception:
                    pass
                self._preview_clip = None
        except Exception:
            pass

        # (optional) close any other cached clips here if you added them

        try:
            self.root.destroy()
        except Exception:
            try:
                import sys
                sys.exit(0)
            except Exception:
                pass


    def browse_voice(self):
        path = filedialog.askopenfilename(title="Select voice audio", filetypes=[("Audio files", "*.wav *.mp3 *.m4a"), ("All files", "*.*")])
        if path: self.voice_var.set(path)

    def browse_music(self):
        path = filedialog.askopenfilename(title="Select music", filetypes=[("Audio files", "*.mp3 *.wav *.m4a *.ogg"), ("All files", "*.*")])
        if path: self.music_var.set(path)

    def choose_output(self):
        path = filedialog.asksaveasfilename(title="Output file", defaultextension=".mp4", filetypes=[("MP4 file", "*.mp4")])
        if path: self.output_var.set(path)

    def _format_job_info(self, job):
        """Format job information for display, showing all relevant settings."""
        info_parts = []
        
        # Resolution and basic settings
        if job.get("use_4k"):
            info_parts.append("4K")
        if job.get("mirror_video"):
            info_parts.append("Mirror")
        if job.get("words_per_caption", 2) != 2:
            info_parts.append(f"{job.get('words_per_caption')} words/cap")
        
        # AI and translation settings
        if job.get("use_ai_voice"):
            info_parts.append("AI-TTS")
        if job.get("translation_enabled"):
            lang = job.get("target_language", "?")
            info_parts.append(f"Translate:{lang}")
        
        # Silence threshold (only show if AI voice is enabled and not default)
        if job.get("use_ai_voice") and job.get("silence_threshold_ms", 300) != 300:
            info_parts.append(f"silence:{job.get('silence_threshold_ms')}ms")
        
        # Font color (show if not default white)
        text_color = job.get("caption_text_color", (255, 255, 255, 255))
        if text_color != (255, 255, 255, 255):
            info_parts.append(f"color:RGB({text_color[0]},{text_color[1]},{text_color[2]})")
        
        # Stroke/border settings (show if not default)
        stroke_color = job.get("caption_stroke_color", (0, 0, 0, 150))
        stroke_width = job.get("caption_stroke_width", 3)
        if stroke_color != (0, 0, 0, 150) or stroke_width != 3:
            info_parts.append(f"border:w={stroke_width},RGB({stroke_color[0]},{stroke_color[1]},{stroke_color[2]})")
        
        # Add effects info if different from defaults
        blur = job.get("blur_radius", 25)
        bg_scale = job.get("bg_scale_extra", 1.08)
        dim = job.get("dim_factor", 0.55)
        if blur != 25 or bg_scale != 1.08 or dim != 0.55:
            info_parts.append(f"effects:blur={blur}/scale={bg_scale:.2f}/dim={dim:.2f}")
        
        # Video effects (CapCut-style)
        effects_active = []
        if job.get("effect_sharpness"):
            effects_active.append("Resilience")
        if job.get("effect_saturation"):
            effects_active.append("Vibrance")
        if job.get("effect_contrast"):
            effects_active.append("HDR")
        if job.get("effect_brightness"):
            effects_active.append("Brightness")
        if job.get("effect_vintage"):
            effects_active.append("Vintage")
        if effects_active:
            info_parts.append(f"fx:{','.join(effects_active)}")
        
        return " [" + ", ".join(info_parts) + "]" if info_parts else ""

    def add_job(self):
        try:
            video = self.video_var.get().strip()
            voice = self.voice_var.get().strip()
            music = self.music_var.get().strip()
            output = self.output_var.get().strip() or "final_tiktok.mp4"
            if not video or not music:
                messagebox.showwarning("Missing fields", "Please select VIDEO and MUSIC before adding a job.")
                return
            # preferred font: prefer selected_font_path (.ttf) else selected_font family name
            try:
                pref_font = None
                if getattr(self, 'selected_font_path', None):
                    pref_font = self.selected_font_path
                elif getattr(self, 'selected_font', None):
                    pref_font = self.selected_font
            except Exception:
                pref_font = None
            
            # Log crop settings for debugging
            use_custom = self.use_custom_crop_var.get()
            top_val = self.top_percent_var.get()
            bottom_val = self.bottom_percent_var.get()
            self.log_to_console(f"\n[DEBUG JOB] Creating job with:")
            self.log_to_console(f"[DEBUG JOB] Use custom crop checkbox: {use_custom}")
            self.log_to_console(f"[DEBUG JOB] Top percent: {top_val}")
            self.log_to_console(f"[DEBUG JOB] Bottom percent: {bottom_val}")
            self.log_to_console(f"[DEBUG JOB] Will send custom_top_ratio: {(top_val/100.0) if use_custom else None}")
            self.log_to_console(f"[DEBUG JOB] Will send custom_bottom_ratio: {(bottom_val/100.0) if use_custom else None}")
            
            job = {
                "video": video,
                "voice": voice,
                "music": music,
                "output": output,
                "font": pref_font,
                "custom_top_ratio": (self.top_percent_var.get()/100.0) if self.use_custom_crop_var.get() else None,
                "custom_bottom_ratio": (self.bottom_percent_var.get()/100.0) if self.use_custom_crop_var.get() else None,
                "mirror_video": self.mirror_video_var.get(),
                "words_per_caption": self.words_per_caption_var.get(),
                "use_4k": self.use_4k_var.get(),
                "blur_radius": globals().get('STATIC_BG_BLUR_RADIUS', 25),
                "bg_scale_extra": globals().get('BG_SCALE_EXTRA', 1.08),
                "dim_factor": globals().get('DIM_FACTOR', 0.55),
                # AI and caption settings
                "use_ai_voice": self.use_ai_voice_var.get(),
                "translation_enabled": self.translation_enabled_var.get(),
                "target_language": self.target_language_var.get() if hasattr(self, 'target_language_var') else 'none',
                "tts_language": self.tts_language_var.get() if hasattr(self, 'tts_language_var') else 'en',
                "silence_threshold_ms": self.silence_threshold_var.get(),
                # Font and border settings
                "caption_text_color": globals().get('CAPTION_TEXT_COLOR', (255, 255, 255, 255)),
                "caption_stroke_color": globals().get('CAPTION_STROKE_COLOR', (0, 0, 0, 150)),
                "caption_stroke_width": globals().get('CAPTION_STROKE_WIDTH', 3),
                # Video effects (CapCut-style)
                "effect_sharpness": self.effect_sharpness_var.get(),
                "effect_sharpness_intensity": self.effect_sharpness_intensity_var.get(),
                "effect_saturation": self.effect_saturation_var.get(),
                "effect_saturation_intensity": self.effect_saturation_intensity_var.get(),
                "effect_contrast": self.effect_contrast_var.get(),
                "effect_contrast_intensity": self.effect_contrast_intensity_var.get(),
                "effect_brightness": self.effect_brightness_var.get(),
                "effect_brightness_intensity": self.effect_brightness_intensity_var.get(),
                "effect_vintage": self.effect_vintage_var.get(),
                "effect_vintage_intensity": self.effect_vintage_intensity_var.get()
            }
            self.jobs.append(job)
            # Show complete job info in the display using helper
            info = self._format_job_info(job)
            display = f"{Path(video).name} | {Path(voice).name} | {Path(music).name} -> {Path(output).name} (font={pref_font or 'default'}){info}"
            self.job_listbox.insert('end', display)
        except Exception as e:
            messagebox.showerror("Error adding job", str(e))

    def _refresh_job_listbox(self):
        self.job_listbox.delete(0, tk.END)
        for i, j in enumerate(self.jobs, start=1):
            tag = ""
            if j.get("custom_top_ratio") is not None:
                tag = f" (crop {int(j['custom_top_ratio']*100)}%/{int(j['custom_bottom_ratio']*100)}%)"
            
            # Use helper to format job info consistently
            info = self._format_job_info(j)
            
            display = f"{i}. {os.path.basename(j['video'])} | {os.path.basename(j['voice'])} | {os.path.basename(j['music'])}{tag}{info}"
            self.job_listbox.insert(tk.END, display)

    def remove_job(self):
        sel = self.job_listbox.curselection()
        if not sel:
            return
        selected_indices = sorted(sel, reverse=True)
        for idx in selected_indices:
            try:
                self.jobs.pop(idx)
            except Exception:
                pass
        self._refresh_job_listbox()

    def on_job_double_click(self, event):
        """Load job settings when double-clicking a job in the list."""
        try:
            # Get selected job index
            sel = self.job_listbox.curselection()
            if not sel:
                return
            
            job_idx = sel[0]
            if job_idx >= len(self.jobs):
                return
            
            job = self.jobs[job_idx]
            
            # Load file paths
            self.video_var.set(job.get("video", ""))
            self.voice_var.set(job.get("voice", ""))
            self.music_var.set(job.get("music", ""))
            self.output_var.set(job.get("output", ""))
            
            # Load basic settings
            self.mirror_video_var.set(job.get("mirror_video", False))
            self.words_per_caption_var.set(job.get("words_per_caption", 2))
            self.use_4k_var.set(job.get("use_4k", False))
            
            # Load crop settings
            if job.get("custom_top_ratio") is not None:
                self.use_custom_crop_var.set(True)
                self.top_percent_var.set(job.get("custom_top_ratio", 0.0) * 100.0)
                self.bottom_percent_var.set(job.get("custom_bottom_ratio", 0.0) * 100.0)
            else:
                self.use_custom_crop_var.set(False)
            
            # Load effects settings
            globals()['STATIC_BG_BLUR_RADIUS'] = job.get("blur_radius", 25)
            globals()['BG_SCALE_EXTRA'] = job.get("bg_scale_extra", 1.08)
            globals()['DIM_FACTOR'] = job.get("dim_factor", 0.55)
            
            # Load AI and translation settings
            self.use_ai_voice_var.set(job.get("use_ai_voice", False))
            self.translation_enabled_var.set(job.get("translation_enabled", False))
            if hasattr(self, 'target_language_var'):
                self.target_language_var.set(job.get("target_language", "none"))
            self.silence_threshold_var.set(job.get("silence_threshold_ms", 300))
            
            # Load video effects (CapCut-style)
            if hasattr(self, 'effect_sharpness_var'):
                self.effect_sharpness_var.set(job.get("effect_sharpness", False))
                self.effect_sharpness_intensity_var.set(job.get("effect_sharpness_intensity", 1.5))
            if hasattr(self, 'effect_saturation_var'):
                self.effect_saturation_var.set(job.get("effect_saturation", False))
                self.effect_saturation_intensity_var.set(job.get("effect_saturation_intensity", 1.3))
            if hasattr(self, 'effect_contrast_var'):
                self.effect_contrast_var.set(job.get("effect_contrast", False))
                self.effect_contrast_intensity_var.set(job.get("effect_contrast_intensity", 1.2))
            if hasattr(self, 'effect_brightness_var'):
                self.effect_brightness_var.set(job.get("effect_brightness", False))
                self.effect_brightness_intensity_var.set(job.get("effect_brightness_intensity", 1.15))
            if hasattr(self, 'effect_vintage_var'):
                self.effect_vintage_var.set(job.get("effect_vintage", False))
                self.effect_vintage_intensity_var.set(job.get("effect_vintage_intensity", 0.3))
            
            # Load font and border settings
            text_color = job.get("caption_text_color", (255, 255, 255, 255))
            stroke_color = job.get("caption_stroke_color", (0, 0, 0, 150))
            stroke_width = job.get("caption_stroke_width", 3)
            
            globals()['CAPTION_TEXT_COLOR'] = text_color
            globals()['CAPTION_STROKE_COLOR'] = stroke_color
            globals()['CAPTION_STROKE_WIDTH'] = stroke_width
            
            # Update UI elements for colors if they exist
            try:
                if hasattr(self, 'text_color_canvas') and self.text_color_canvas:
                    col = f'#{text_color[0]:02x}{text_color[1]:02x}{text_color[2]:02x}'
                    self.text_color_canvas.delete('all')
                    self.text_color_canvas.create_oval(2,2,26,26, fill=col, outline='white')
            except Exception:
                pass
            
            try:
                if hasattr(self, 'stroke_color_canvas') and self.stroke_color_canvas:
                    col = f'#{stroke_color[0]:02x}{stroke_color[1]:02x}{stroke_color[2]:02x}'
                    self.stroke_color_canvas.delete('all')
                    self.stroke_color_canvas.create_oval(2,2,26,26, fill=col, outline='white')
            except Exception:
                pass
            
            try:
                if hasattr(self, 'stroke_width_var'):
                    self.stroke_width_var.set(stroke_width)
                if hasattr(self, 'stroke_width_label') and self.stroke_width_label:
                    self.stroke_width_label.config(text=str(int(stroke_width)))
            except Exception:
                pass
            
            # Load font if specified
            font_path = job.get("font")
            if font_path:
                try:
                    self.selected_font_path = font_path
                    self.selected_font = os.path.basename(font_path) if font_path else None
                except Exception:
                    pass
            
            # Update video preview if video file exists
            video_path = job.get("video", "")
            if video_path and os.path.exists(video_path):
                try:
                    # Trigger mini preview update
                    self._mini_update_worker_async()
                except Exception as e:
                    print(f"Could not update preview: {e}")
            
            # Log the load action
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"\n[LOAD] Loaded settings from job #{job_idx + 1}\n")
                self.log_widget.see('end')
                self.log_widget.config(state='disabled')
            except Exception:
                pass
                
        except Exception as e:
            messagebox.showerror("Error loading job", str(e))

    def on_run_single(self):
        try:
            video = self.video_var.get().strip()
            voice = self.voice_var.get().strip()
            music = self.music_var.get().strip()
            output = self.output_var.get().strip() or "final_tiktok.mp4"
            if not video or not music:
                messagebox.showwarning("Missing fields", "Please select VIDEO and MUSIC before running.")
                return
            try:
                pref_font = None
                if getattr(self, 'selected_font_path', None):
                    pref_font = self.selected_font_path
                elif getattr(self, 'selected_font', None):
                    pref_font = self.selected_font
            except Exception:
                pref_font = None
            # create a queue for logs and start the job in a worker thread
            job = {"video": video, "voice": voice, "music": music, "output": output, "font": pref_font,
                   "custom_top_ratio": (self.top_percent_var.get()/100.0) if self.use_custom_crop_var.get() else None,
                   "custom_bottom_ratio": (self.bottom_percent_var.get()/100.0) if self.use_custom_crop_var.get() else None,
                   "mirror_video": self.mirror_video_var.get(),
                   "words_per_caption": self.words_per_caption_var.get(),
                   "use_4k": self.use_4k_var.get(),
                   "blur_radius": globals().get('STATIC_BG_BLUR_RADIUS', 25),
                   "bg_scale_extra": globals().get('BG_SCALE_EXTRA', 1.08),
                   "dim_factor": globals().get('DIM_FACTOR', 0.55),
                   # AI and caption settings
                   "use_ai_voice": self.use_ai_voice_var.get(),
                   "translation_enabled": self.translation_enabled_var.get(),
                   "target_language": self.target_language_var.get() if hasattr(self, 'target_language_var') else 'none',
                   "silence_threshold_ms": self.silence_threshold_var.get(),
                   # Font and border settings
                   "caption_text_color": globals().get('CAPTION_TEXT_COLOR', (255, 255, 255, 255)),
                   "caption_stroke_color": globals().get('CAPTION_STROKE_COLOR', (0, 0, 0, 150)),
                   "caption_stroke_width": globals().get('CAPTION_STROKE_WIDTH', 3),
                   # Video effects (CapCut-style)
                   "effect_sharpness": self.effect_sharpness_var.get(),
                   "effect_sharpness_intensity": self.effect_sharpness_intensity_var.get(),
                   "effect_saturation": self.effect_saturation_var.get(),
                   "effect_saturation_intensity": self.effect_saturation_intensity_var.get(),
                   "effect_contrast": self.effect_contrast_var.get(),
                   "effect_contrast_intensity": self.effect_contrast_intensity_var.get(),
                   "effect_brightness": self.effect_brightness_var.get(),
                   "effect_brightness_intensity": self.effect_brightness_intensity_var.get(),
                   "effect_vintage": self.effect_vintage_var.get(),
                   "effect_vintage_intensity": self.effect_vintage_intensity_var.get()}
            q = self.q
            # Extract effect settings
            effect_settings = {
                'effect_sharpness': job.get("effect_sharpness", False),
                'effect_sharpness_intensity': job.get("effect_sharpness_intensity", 1.5),
                'effect_saturation': job.get("effect_saturation", False),
                'effect_saturation_intensity': job.get("effect_saturation_intensity", 1.3),
                'effect_contrast': job.get("effect_contrast", False),
                'effect_contrast_intensity': job.get("effect_contrast_intensity", 1.2),
                'effect_brightness': job.get("effect_brightness", False),
                'effect_brightness_intensity': job.get("effect_brightness_intensity", 1.15),
                'effect_vintage': job.get("effect_vintage", False),
                'effect_vintage_intensity': job.get("effect_vintage_intensity", 0.3)
            }
            # Run in background thread so GUI remains responsive
            t = threading.Thread(target=process_single_job, args=(job["video"], job["voice"], job["music"], job["output"], q, job.get("font")), kwargs={"custom_top_ratio": job.get("custom_top_ratio"), "custom_bottom_ratio": job.get("custom_bottom_ratio"), "mirror_video": job.get("mirror_video", False), "words_per_caption": job.get("words_per_caption", 2), "use_4k": job.get("use_4k", False), "blur_radius": job.get("blur_radius"), "bg_scale_extra": job.get("bg_scale_extra"), "dim_factor": job.get("dim_factor"), "effect_settings": effect_settings, "use_ai_voice": job.get("use_ai_voice", False), "target_language": job.get("target_language", 'none'), "translation_enabled": job.get("translation_enabled", False), "tts_language": job.get("tts_language", 'en')}, daemon=True)
            t.start()
            try:
                self.log_widget.config(state='normal')
                self.log_widget.insert('end', f"[RUN] Started single job -> {Path(output).name}\n")
                self.log_widget.see('end')
                self.log_widget.config(state='disabled')
            except Exception:
                pass
        except Exception as e:
            messagebox.showerror("Run error", str(e))

    def _run_single_thread(self, video, voice, music, output, top_ratio, bottom_ratio):
        words_per_caption = self.words_per_caption_var.get()
        use_ai_voice = self.use_ai_voice_var.get()
        target_language = self.target_language_var.get()
        translation_enabled = self.translation_enabled_var.get()
        tts_language = self.tts_language_var.get()
        silence_threshold_ms = self.silence_threshold_var.get()
        process_single_job(video, voice, music, output, self.q, custom_top_ratio=top_ratio, custom_bottom_ratio=bottom_ratio, words_per_caption=words_per_caption, use_ai_voice=use_ai_voice, target_language=target_language, translation_enabled=translation_enabled, tts_language=tts_language, silence_threshold_ms=silence_threshold_ms)
        self.q.put("[SINGLE_DONE]")

    def run_queue(self):
        if not self.jobs:
            messagebox.showerror("Empty queue", "Nu ai niciun job în listă")
            return
        self.run_queue_btn.config(state="disabled")
        self.run_single_btn.config(state="disabled")
        self.log_widget.config(state="normal")
        self.log_widget.delete("1.0", tk.END)
        self.log_widget.config(state="disabled")
        t = threading.Thread(target=queue_worker, args=(list(self.jobs), self.q), daemon=True)
        t.start()

    def on_mini_refresh_clicked(self):
        self._mini_update_worker_async()

    def _rgba_from_hex(self, hx):
        try:
            if hx.startswith('#'): hx = hx[1:]
            if len(hx) == 6:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16)
                return (r,g,b,255)
            if len(hx) == 8:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16); a = int(hx[6:8],16)
                return (r,g,b,a)
        except Exception:
            pass
        return (255,255,255,255)

    def _update_color_canvases(self):
        try:
            try:
                txt = CAPTION_TEXT_COLOR
                col = '#%02x%02x%02x' % (txt[0], txt[1], txt[2])
                if hasattr(self, 'text_color_canvas') and self.text_color_canvas:
                    self.text_color_canvas.delete('all')
                    self.text_color_canvas.create_oval(2,2,26,26, fill=col, outline='white')
            except Exception:
                pass
            try:
                st = CAPTION_STROKE_COLOR
                col2 = '#%02x%02x%02x' % (st[0], st[1], st[2])
                if hasattr(self, 'stroke_color_canvas') and self.stroke_color_canvas:
                    self.stroke_color_canvas.delete('all')
                    self.stroke_color_canvas.create_oval(2,2,26,26, fill=col2, outline='white')
            except Exception:
                pass
        except Exception:
            pass

    def on_pick_text_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption text color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                globals()['CAPTION_TEXT_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_pick_stroke_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption stroke color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                if len(rgba) == 4 and rgba[3] == 255:
                    rgba = (rgba[0], rgba[1], rgba[2], 150)
                globals()['CAPTION_STROKE_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def _set_text_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            globals()['CAPTION_TEXT_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass

    def _set_stroke_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            rgba = (rgba[0], rgba[1], rgba[2], 150)
            globals()['CAPTION_STROKE_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass


    def _get_current_effect_settings(self):
        """Get current effect settings from UI for preview."""
        return {
            'effect_sharpness': self.effect_sharpness_var.get(),
            'effect_sharpness_intensity': self.effect_sharpness_intensity_var.get(),
            'effect_saturation': self.effect_saturation_var.get(),
            'effect_saturation_intensity': self.effect_saturation_intensity_var.get(),
            'effect_contrast': self.effect_contrast_var.get(),
            'effect_contrast_intensity': self.effect_contrast_intensity_var.get(),
            'effect_brightness': self.effect_brightness_var.get(),
            'effect_brightness_intensity': self.effect_brightness_intensity_var.get(),
            'effect_vintage': self.effect_vintage_var.get(),
            'effect_vintage_intensity': self.effect_vintage_intensity_var.get()
        }

    def _mini_update_worker_async(self):
        video = self.video_var.get().strip()
        if not video or not os.path.isfile(video):
            self._set_mini_canvas_placeholder("No video selected")
            return
        if self.mini_worker_thread and self.mini_worker_thread.is_alive(): return
        tval = float(self.time_var.get())
        # decide whether to pass cached clip or path
        clip_or_path = video
        try:
            if hasattr(self, '_preview_clip') and self._preview_clip and getattr(self._preview_clip, 'filename', None):
                try:
                    if os.path.abspath(video) == os.path.abspath(self._preview_clip.filename):
                        clip_or_path = self._preview_clip
                except Exception:
                    clip_or_path = video
        except Exception:
            clip_or_path = video
        self.mini_worker_thread = threading.Thread(target=self._mini_extract_and_update, args=(clip_or_path, tval), daemon=True)
        self.mini_worker_thread.start()

    def _mini_extract_and_update(self, video_path, time_val):
        try:
            img, scale = extract_and_scale_frame(video_path, time_sec=time_val, desired_width=360)
            
            # Apply video effects to preview
            effect_settings = self._get_current_effect_settings()
            if any([effect_settings.get('effect_sharpness', False),
                    effect_settings.get('effect_saturation', False),
                    effect_settings.get('effect_contrast', False),
                    effect_settings.get('effect_brightness', False),
                    effect_settings.get('effect_vintage', False)]):
                img = apply_video_effects(img, effect_settings)
            
            self.mini_base_img = img
            self.mini_scale = scale
            top_pct = float(self.top_percent_var.get())/100.0
            bottom_pct = float(self.bottom_percent_var.get())/100.0
            composed = overlay_crop_on_image(img, top_pct, bottom_pct)
            photo = ImageTk.PhotoImage(composed)
            def apply():
                self.mini_canvas.config(width=composed.width, height=composed.height)
                # Use centralized redraw method that ALWAYS includes caption indicator
                self._redraw_mini_canvas_with_caption_indicator(composed, top_pct, bottom_pct)
                self.preview_info.config(text=f"Preview at {seconds_to_hms(time_val)} | scale={self.mini_scale:.2f}")
                self.font_info.config(text=f"Font: {LOADED_FONT_PATH or 'not loaded'}")
            self.root.after(0, apply)
        except Exception as e:
            self.root.after(0, lambda: self._set_mini_canvas_placeholder("Preview error"))
            self.q.put(f"Mini-preview error: {e}")

    def _start_mini_persistent_worker(self):
        # Start a background thread that listens for slider requests and updates preview in-place.
        if self._mini_persistent_thread and self._mini_persistent_thread.is_alive():
            return
        self._mini_request_stop = False
        self._mini_persistent_thread = threading.Thread(target=self._mini_persistent_worker, daemon=True)
        self._mini_persistent_thread.start()

    def _stop_mini_persistent_worker(self):
        try:
            self._mini_request_stop = True
            if self._mini_request_event:
                self._mini_request_event.set()
        except Exception:
            pass

    def _mini_persistent_worker(self):
        # Background loop that processes the latest requested time and updates the mini preview.
        # It uses the cached VideoFileClip if available for faster seeks.
        min_interval = 0.03  # aim for up to ~30 FPS responsiveness during scrubbing
        last_ts = 0.0
        cap = None
        while not getattr(self, '_mini_request_stop', False):
            try:
                self._mini_request_event.wait(timeout=min_interval)
            except Exception:
                pass
            if getattr(self, '_mini_request_stop', False):
                break
            req_time = None
            try:
                req_time = self._mini_request_time
            except Exception:
                req_time = None
            if req_time is None:
                self._mini_request_event.clear()
                continue
            now = time.time()
            if now - last_ts < min_interval:
                time.sleep(max(0.0, min_interval - (now - last_ts)))
            last_ts = time.time()
            video_path = self.video_var.get().strip()
            clip_to_use = None
            created_local_clip = False
            try:
                if hasattr(self, '_preview_clip') and self._preview_clip and getattr(self._preview_clip, 'filename', None):
                    try:
                        if os.path.abspath(video_path) == os.path.abspath(self._preview_clip.filename):
                            clip_to_use = self._preview_clip
                    except Exception:
                        clip_to_use = None
                if clip_to_use is None:
                    clip_to_use = VideoFileClip(video_path)
                    created_local_clip = True
            except Exception:
                clip_to_use = None
                created_local_clip = False
                try:
                    import cv2
                    if cap is None:
                        cap = cv2.VideoCapture(video_path)
                except Exception:
                    cap = None
            try:
                if clip_to_use is not None:
                    t = float(max(0.0, min(req_time, max(0.001, clip_to_use.duration - 0.001))))
                    frame = clip_to_use.get_frame(t)
                    img = Image.fromarray(frame).convert('RGB')
                elif cap is not None and cap.isOpened():
                    import cv2
                    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
                    frame_num = int(round(req_time * fps))
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_num)
                    ret, fr = cap.read()
                    if ret:
                        img = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2RGB)).convert('RGB')
                    else:
                        img = None
                else:
                    img = None
                if img is not None:
                    w, h = img.size
                    desired_width = 360
                    scale = desired_width / float(w) if w else 1.0
                    new_w = desired_width
                    new_h = int(round(h * scale))
                    img = img.resize((new_w, new_h), Image.LANCZOS)
                    
                    # Apply video effects to preview
                    effect_settings = self._get_current_effect_settings()
                    if any([effect_settings.get('effect_sharpness', False),
                            effect_settings.get('effect_saturation', False),
                            effect_settings.get('effect_contrast', False),
                            effect_settings.get('effect_brightness', False),
                            effect_settings.get('effect_vintage', False)]):
                        img = apply_video_effects(img, effect_settings)
                    
                    top_pct = float(self.top_percent_var.get())/100.0
                    bottom_pct = float(self.bottom_percent_var.get())/100.0
                    composed = overlay_crop_on_image(img, top_pct, bottom_pct)
                    try:
                        def _update_with_caption():
                            try:
                                # Use centralized redraw method that ALWAYS includes caption indicator
                                self._redraw_mini_canvas_with_caption_indicator(composed, top_pct, bottom_pct)
                            except Exception:
                                pass
                        self.root.after(0, _update_with_caption)
                    except Exception:
                        pass
            except Exception:
                pass
            finally:
                try:
                    if clip_to_use is not None and created_local_clip:
                        try:
                            clip_to_use.close()
                        except Exception:
                            pass
                except Exception:
                    pass
            try:
                self._mini_request_event.clear()
            except Exception:
                pass
        try:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        except Exception:
            pass


    def _set_mini_canvas_placeholder(self, text):
        self.mini_canvas.delete("all")
        w = int(self.mini_canvas.cget("width"))
        h = int(self.mini_canvas.cget("height"))
        self.mini_canvas.create_rectangle(0,0,w,h, fill="#222222", outline="")
        self.mini_canvas.create_text(w//2, h//2, text=text, fill="#ddd", font=("Arial", 12))

    def update_mini_preview_immediate(self):
        if self.mini_base_img is None:
            self._mini_update_worker_async()
        else:
            # Redraw with current crop settings and caption indicator
            try:
                top_pct = float(self.top_percent_var.get())/100.0
                bottom_pct = float(self.bottom_percent_var.get())/100.0
                composed = overlay_crop_on_image(self.mini_base_img, top_pct, bottom_pct)
                self._redraw_mini_canvas_with_caption_indicator(composed, top_pct, bottom_pct)
            except Exception:
                pass

    def _rgba_from_hex(self, hx):
        try:
            if hx.startswith('#'): hx = hx[1:]
            if len(hx) == 6:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16)
                return (r,g,b,255)
            if len(hx) == 8:
                r = int(hx[0:2],16); g = int(hx[2:4],16); b = int(hx[4:6],16); a = int(hx[6:8],16)
                return (r,g,b,a)
        except Exception:
            pass
        return (255,255,255,255)

    def _update_color_canvases(self):
        try:
            try:
                txt = CAPTION_TEXT_COLOR
                col = '#%02x%02x%02x' % (txt[0], txt[1], txt[2])
                if hasattr(self, 'text_color_canvas') and self.text_color_canvas:
                    self.text_color_canvas.delete('all')
                    self.text_color_canvas.create_oval(2,2,26,26, fill=col, outline='white')
            except Exception:
                pass
            try:
                st = CAPTION_STROKE_COLOR
                col2 = '#%02x%02x%02x' % (st[0], st[1], st[2])
                if hasattr(self, 'stroke_color_canvas') and self.stroke_color_canvas:
                    self.stroke_color_canvas.delete('all')
                    self.stroke_color_canvas.create_oval(2,2,26,26, fill=col2, outline='white')
            except Exception:
                pass
        except Exception:
            pass

    def on_pick_text_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption text color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                globals()['CAPTION_TEXT_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def on_pick_stroke_color(self):
        try:
            from tkinter import colorchooser
            col = colorchooser.askcolor(title='Choose caption stroke color')
            if col and col[1]:
                rgba = self._rgba_from_hex(col[1])
                if len(rgba) == 4 and rgba[3] == 255:
                    rgba = (rgba[0], rgba[1], rgba[2], 150)
                globals()['CAPTION_STROKE_COLOR'] = rgba
                self._update_color_canvases()
                # Trigger live preview update
                self._mini_update_worker_async()
        except Exception as e:
            try:
                self.log_widget.config(state='normal'); self.log_widget.insert('end', f"[COLOR-ERR] {e}\n"); self.log_widget.config(state='disabled')
            except Exception:
                pass

    def _set_text_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            globals()['CAPTION_TEXT_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass

    def _set_stroke_color_hex(self, hx):
        try:
            rgba = self._rgba_from_hex(hx)
            rgba = (rgba[0], rgba[1], rgba[2], 150)
            globals()['CAPTION_STROKE_COLOR'] = rgba
            self._update_color_canvases()
            # Trigger live preview update
            self._mini_update_worker_async()
        except Exception:
            pass

            return
        top_pct = float(self.top_percent_var.get())/100.0
        bottom_pct = float(self.bottom_percent_var.get())/100.0
        if top_pct + bottom_pct > 0.95:
            bottom_pct = max(0.0, 0.95 - top_pct)
            self.bottom_percent_var.set(bottom_pct*100)
        composed = overlay_crop_on_image(self.mini_base_img.copy(), top_pct, bottom_pct)
        photo = ImageTk.PhotoImage(composed)
        self.mini_canvas.config(width=composed.width, height=composed.height)
        self.mini_canvas.delete("all")
        self.mini_canvas.create_image(0, 0, anchor="nw", image=photo, tags="base_img")
        self.mini_image_ref = photo
        h = composed.height
        top_y = int(round(h * top_pct))
        bottom_y = int(round(h * (1.0 - bottom_pct)))
        self.mini_canvas.create_rectangle(0, top_y-4, composed.width, top_y+4, fill="#000000", stipple="gray50", tags="line_top")
        self.mini_canvas.create_rectangle(0, bottom_y-4, composed.width, bottom_y+4, fill="#000000", stipple="gray50", tags="line_bottom")
        self.mini_canvas.create_text(6, max(6, top_y-18), anchor="nw", text=f"Top {int(top_pct*100)}% ({top_y}px)", fill="#fff", font=("Arial",9), tags="label_top")
        self.mini_canvas.create_text(6, min(h-18, bottom_y+6), anchor="nw", text=f"Bottom {int(bottom_pct*100)}% ({h - bottom_y}px)", fill="#fff", font=("Arial",9), tags="label_bottom")
        self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
        self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")

    def on_time_changed(self, _=None):
        # update the time label immediately
        t = float(self.time_var.get())
        self.time_label.config(text=seconds_to_hms(t))

        # live scrubbing: set desired preview time and notify persistent worker
        try:
            self._mini_request_time = t
            try:
                if not (self._mini_persistent_thread and self._mini_persistent_thread.is_alive()):
                    self._start_mini_persistent_worker()
            except Exception:
                pass
            try:
                self._mini_request_event.set()
            except Exception:
                pass
        except Exception:
            pass
    
    def on_zoom_changed(self, _=None):
        """Called when zoom slider is moved"""
        global VIDEO_ZOOM_SCALE
        zoom = float(self.zoom_var.get())
        VIDEO_ZOOM_SCALE = zoom
        self.zoom_label.config(text=f"{zoom:.2f}x")
        # Update TikTok preview when zoom changes
        self.on_tiktok_preview_refresh()
    
    def on_tiktok_preview_refresh(self):
        """Refresh the TikTok format preview with current settings"""
        try:
            if not self.video_var.get() or not os.path.isfile(self.video_var.get()):
                return
            
            # Get current video path and time
            video_path = self.video_var.get()
            current_time = float(self.time_var.get())
            
            # Load video clip at current time
            from moviepy.editor import VideoFileClip
            video_clip = VideoFileClip(video_path)
            
            # Get frame at current time
            if current_time > video_clip.duration:
                current_time = 0.0
            
            frame = video_clip.get_frame(current_time)
            video_clip.close()
            
            # Get crop settings
            crop_top_ratio = float(self.top_percent_var.get()) / 100.0
            crop_bottom_ratio = float(self.bottom_percent_var.get()) / 100.0
            
            # Calculate crop coordinates
            img_h, img_w = frame.shape[:2]
            crop_y = int(img_h * crop_top_ratio)
            crop_h = int(img_h * (1.0 - crop_top_ratio - crop_bottom_ratio))
            crop_x = 0
            crop_w = img_w
            
            # Crop the frame
            cropped_frame = frame[crop_y:crop_y+crop_h, crop_x:crop_x+crop_w]
            
            # Apply zoom scaling
            zoom = float(self.zoom_var.get())
            scale_w = WIDTH / crop_w
            fg_scale = scale_w * zoom
            
            # Scale the frame
            scaled_h = int(crop_h * fg_scale)
            scaled_w = int(crop_w * fg_scale)
            
            from PIL import Image
            import numpy as np
            
            pil_img = Image.fromarray(cropped_frame)
            pil_img = pil_img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
            
            # Create 9:16 canvas (1080x1920 scaled down to 180x320)
            canvas = Image.new('RGB', (WIDTH, HEIGHT), color=(20, 20, 20))
            
            # Center the scaled image on canvas
            paste_x = (WIDTH - scaled_w) // 2
            paste_y = (HEIGHT - scaled_h) // 2
            canvas.paste(pil_img, (paste_x, paste_y))
            
            # Scale down to preview size (180x320)
            preview_canvas = canvas.resize((180, 320), Image.Resampling.LANCZOS)
            
            # Display in TikTok preview canvas
            photo = ImageTk.PhotoImage(preview_canvas)
            self.tiktok_preview_canvas.delete("all")
            self.tiktok_preview_canvas.create_image(90, 160, image=photo)
            self.tiktok_preview_image_ref = photo  # Keep reference
            
        except Exception as e:
            print(f"TikTok preview error: {e}")
            import traceback
            traceback.print_exc()

    def on_font_selected(self, event=None):
        try:
            sel = None
            w = self.font_listbox
            if w.curselection():
                sel = w.get(w.curselection()[0])
        
            if sel:
                self.selected_font = sel
                try:
                    fnt = tkfont.Font(family=sel, size=16)
                    self.font_preview.config(font=fnt)
                except Exception:
                    try:
                        self.font_preview.config(font=(sel, 14))
                    except Exception:
                        pass
                # try to find a matching .ttf in C:\tiktok and store path
                try:
                    found = find_ttf_in_tiktok(sel, search_root=os.path.normpath("C:\\tiktok"))
                    if found:
                        self.selected_font_path = found
                        try:
                            self.saved_font_label.config(text=f"Found TTF: {os.path.basename(found)}")
                        except Exception:
                            pass
                    else:
                        self.selected_font_path = None
                except Exception:
                    self.selected_font_path = None

        except Exception:
            pass

    def _mini_on_mouse_down(self, event):
        if self.mini_base_img is None: return
        canvas_h = int(self.mini_canvas.cget("height"))
        y = event.y
        top_y = int(round(canvas_h * (float(self.top_percent_var.get())/100.0)))
        bottom_y = int(round(canvas_h * (1.0 - float(self.bottom_percent_var.get())/100.0)))
        if abs(y - top_y) <= max(self.drag_threshold_px, 6):
            self.dragging = "top"
        elif abs(y - bottom_y) <= max(self.drag_threshold_px, 6):
            self.dragging = "bottom"
        else:
            self.dragging = None

    def _mini_on_mouse_move(self, event):
        if self.dragging is None: return
        canvas_h = int(self.mini_canvas.cget("height"))
        y = max(0, min(canvas_h-1, event.y))
        if self.dragging == "top":
            top_ratio = y / float(canvas_h)
            bottom_ratio = float(self.bottom_percent_var.get())/100.0
            if top_ratio + bottom_ratio > 0.95:
                top_ratio = max(0.0, 0.95 - bottom_ratio)
            self.top_percent_var.set(round(top_ratio*100, 2))
        elif self.dragging == "bottom":
            bottom_ratio = 1.0 - (y / float(canvas_h))
            top_ratio = float(self.top_percent_var.get())/100.0
            if top_ratio + bottom_ratio > 0.95:
                bottom_ratio = max(0.0, 0.95 - top_ratio)
            self.bottom_percent_var.set(round(bottom_ratio*100, 2))
        self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
        self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")
        self.update_mini_preview_immediate()
        self.use_custom_crop_var.set(True)

    def _mini_on_mouse_up(self, event):
        self.dragging = None

    def on_save_crop(self):
        top = float(self.top_percent_var.get())
        bottom = float(self.bottom_percent_var.get())
        ok, info = save_crop_settings(top, bottom)
        if ok:
            messagebox.showinfo("Saved", f"Crop settings saved to {info}")
        else:
            messagebox.showerror("Save failed", f"Could not save crop settings: {info}")

    def on_load_crop(self):
        data = load_crop_settings()
        if not data:
            messagebox.showwarning("Not found", f"No saved settings at '{CROP_SETTINGS_FILE}'")
            return
        try:
            self.top_percent_var.set(float(data.get("top_pct", CROP_TOP_RATIO*100)))
            self.bottom_percent_var.set(float(data.get("bottom_pct", CROP_BOTTOM_RATIO*100)))
            self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
            self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")
            self.use_custom_crop_var.set(True)
            self.update_mini_preview_immediate()
            messagebox.showinfo("Loaded", "Crop settings loaded and applied to UI (Use custom crop enabled).")
        except Exception as e:
            messagebox.showerror("Load failed", f"Could not load crop settings: {e}")

    def save_preset(self):
        """Save all current settings to a preset file."""
        try:
            preset_data = {
                # File paths (optional - user might not want to save these)
                "video_path": self.video_var.get(),
                "voice_path": self.voice_var.get(),
                "music_path": self.music_var.get(),
                "output_path": self.output_var.get(),
                
                # Video settings
                "mirror_video": self.mirror_video_var.get(),
                "use_4k": self.use_4k_var.get(),
                "use_custom_crop": self.use_custom_crop_var.get(),
                "top_percent": self.top_percent_var.get(),
                "bottom_percent": self.bottom_percent_var.get(),
                
                # Audio settings
                "voice_gain": self.voice_gain_var.get(),
                "music_gain": self.music_gain_var.get(),
                
                # Translation/TTS settings
                "translation_enabled": self.translation_enabled_var.get(),
                "target_language": self.target_language_var.get(),
                "use_ai_voice": self.use_ai_voice_var.get(),
                "tts_language": self.tts_language_var.get(),
                "tts_voice": self.tts_voice_var.get(),
                "silence_threshold": self.silence_threshold_var.get(),
                
                # Caption settings
                "words_per_caption": self.words_per_caption_var.get(),
                "caption_text_color": list(globals()['CAPTION_TEXT_COLOR']),
                "caption_stroke_color": list(globals()['CAPTION_STROKE_COLOR']),
                "caption_stroke_width": self.stroke_width_var.get(),
                "caption_y_offset": self.caption_y_offset_var.get(),
                
                # Video effects
                "effect_sharpness": self.effect_sharpness_var.get(),
                "effect_sharpness_intensity": self.effect_sharpness_intensity_var.get(),
                "effect_saturation": self.effect_saturation_var.get(),
                "effect_saturation_intensity": self.effect_saturation_intensity_var.get(),
                "effect_contrast": self.effect_contrast_var.get(),
                "effect_contrast_intensity": self.effect_contrast_intensity_var.get(),
                "effect_brightness": self.effect_brightness_var.get(),
                "effect_brightness_intensity": self.effect_brightness_intensity_var.get(),
                "effect_vintage": self.effect_vintage_var.get(),
                "effect_vintage_intensity": self.effect_vintage_intensity_var.get(),
                
                # Background effects
                "blur_radius": globals().get('STATIC_BG_BLUR_RADIUS', 25),
                "bg_scale_extra": globals().get('BG_SCALE_EXTRA', 1.08),
                "dim_factor": globals().get('DIM_FACTOR', 0.55),
            }
            
            # Save to file
            preset_file = Path.home() / ".tiktok_preset.json"
            with open(preset_file, 'w', encoding='utf-8') as f:
                json.dump(preset_data, f, indent=2)
            
            self.log_widget.config(state="normal")
            self.log_widget.insert(tk.END, f"\n💾 Settings preset saved to: {preset_file}\n")
            self.log_widget.config(state="disabled")
            self.log_widget.see(tk.END)
            
            messagebox.showinfo("Preset Saved", f"All settings saved successfully!\n\nLocation: {preset_file}")
        except Exception as e:
            messagebox.showerror("Save Failed", f"Could not save preset: {e}")

    def load_preset(self):
        """Load settings from preset file and apply them to the UI."""
        preset_file = Path.home() / ".tiktok_preset.json"
        
        if not preset_file.exists():
            messagebox.showwarning("No Preset", f"No preset file found at:\n{preset_file}\n\nSave a preset first!")
            return
        
        try:
            with open(preset_file, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Apply file paths (optional)
            if preset_data.get("video_path"):
                self.video_var.set(preset_data["video_path"])
            if preset_data.get("voice_path"):
                self.voice_var.set(preset_data["voice_path"])
            if preset_data.get("music_path"):
                self.music_var.set(preset_data["music_path"])
            if preset_data.get("output_path"):
                self.output_var.set(preset_data["output_path"])
            
            # Apply video settings
            self.mirror_video_var.set(preset_data.get("mirror_video", False))
            self.use_4k_var.set(preset_data.get("use_4k", False))
            self.top_percent_var.set(preset_data.get("top_percent", CROP_TOP_RATIO*100))
            self.bottom_percent_var.set(preset_data.get("bottom_percent", CROP_BOTTOM_RATIO*100))
            self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
            self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")
            # Auto-enable custom crop if preset has non-default crop values
            top_val = preset_data.get("top_percent", CROP_TOP_RATIO*100)
            bottom_val = preset_data.get("bottom_percent", CROP_BOTTOM_RATIO*100)
            if abs(top_val - CROP_TOP_RATIO*100) > 0.1 or abs(bottom_val - CROP_BOTTOM_RATIO*100) > 0.1:
                self.use_custom_crop_var.set(True)
            else:
                self.use_custom_crop_var.set(preset_data.get("use_custom_crop", False))
            
            # Apply audio settings
            self.voice_gain_var.set(preset_data.get("voice_gain", VOICE_GAIN))
            self.music_gain_var.set(preset_data.get("music_gain", MUSIC_GAIN))
            
            # Apply translation/TTS settings
            self.translation_enabled_var.set(preset_data.get("translation_enabled", TRANSLATION_ENABLED))
            self.target_language_var.set(preset_data.get("target_language", TARGET_LANGUAGE))
            self.use_ai_voice_var.set(preset_data.get("use_ai_voice", USE_AI_VOICE_REPLACEMENT))
            self.tts_language_var.set(preset_data.get("tts_language", TTS_LANGUAGE))
            self.tts_voice_var.set(preset_data.get("tts_voice", 'Auto (Default)'))
            self.silence_threshold_var.set(preset_data.get("silence_threshold", 300))
            
            # Apply caption settings
            self.words_per_caption_var.set(preset_data.get("words_per_caption", 2))
            if "caption_text_color" in preset_data:
                globals()['CAPTION_TEXT_COLOR'] = tuple(preset_data["caption_text_color"])
            if "caption_stroke_color" in preset_data:
                globals()['CAPTION_STROKE_COLOR'] = tuple(preset_data["caption_stroke_color"])
            self.stroke_width_var.set(preset_data.get("caption_stroke_width", max(1, int(CAPTION_FONT_SIZE * 0.05))))
            self.caption_y_offset_var.set(preset_data.get("caption_y_offset", 0))
            
            # Apply video effects
            self.effect_sharpness_var.set(preset_data.get("effect_sharpness", False))
            self.effect_sharpness_intensity_var.set(preset_data.get("effect_sharpness_intensity", 1.5))
            self.effect_saturation_var.set(preset_data.get("effect_saturation", False))
            self.effect_saturation_intensity_var.set(preset_data.get("effect_saturation_intensity", 1.3))
            self.effect_contrast_var.set(preset_data.get("effect_contrast", False))
            self.effect_contrast_intensity_var.set(preset_data.get("effect_contrast_intensity", 1.2))
            self.effect_brightness_var.set(preset_data.get("effect_brightness", False))
            self.effect_brightness_intensity_var.set(preset_data.get("effect_brightness_intensity", 1.15))
            self.effect_vintage_var.set(preset_data.get("effect_vintage", False))
            self.effect_vintage_intensity_var.set(preset_data.get("effect_vintage_intensity", 0.3))
            
            # Apply background effects
            globals()['STATIC_BG_BLUR_RADIUS'] = preset_data.get("blur_radius", 25)
            globals()['BG_SCALE_EXTRA'] = preset_data.get("bg_scale_extra", 1.08)
            globals()['DIM_FACTOR'] = preset_data.get("dim_factor", 0.55)
            
            # Update UI elements that show values
            self._update_color_canvases()
            self.update_mini_preview_immediate()
            
            self.log_widget.config(state="normal")
            self.log_widget.insert(tk.END, f"\n📂 Settings preset loaded from: {preset_file}\n")
            self.log_widget.config(state="disabled")
            self.log_widget.see(tk.END)
            
            messagebox.showinfo("Preset Loaded", "All settings loaded and applied successfully!")
        except Exception as e:
            messagebox.showerror("Load Failed", f"Could not load preset: {e}")

    def load_preset_silent(self):
        """Load settings from preset file silently (no popup messages) - used for auto-load on startup."""
        preset_file = Path.home() / ".tiktok_preset.json"
        
        if not preset_file.exists():
            return
        
        try:
            with open(preset_file, 'r', encoding='utf-8') as f:
                preset_data = json.load(f)
            
            # Apply file paths (optional)
            if preset_data.get("video_path"):
                self.video_var.set(preset_data["video_path"])
            if preset_data.get("voice_path"):
                self.voice_var.set(preset_data["voice_path"])
            if preset_data.get("music_path"):
                self.music_var.set(preset_data["music_path"])
            if preset_data.get("output_path"):
                self.output_var.set(preset_data["output_path"])
            
            # Apply video settings
            self.mirror_video_var.set(preset_data.get("mirror_video", False))
            self.use_4k_var.set(preset_data.get("use_4k", False))
            self.top_percent_var.set(preset_data.get("top_percent", CROP_TOP_RATIO*100))
            self.bottom_percent_var.set(preset_data.get("bottom_percent", CROP_BOTTOM_RATIO*100))
            self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
            self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")
            # Auto-enable custom crop if preset has non-default crop values
            top_val = preset_data.get("top_percent", CROP_TOP_RATIO*100)
            bottom_val = preset_data.get("bottom_percent", CROP_BOTTOM_RATIO*100)
            if abs(top_val - CROP_TOP_RATIO*100) > 0.1 or abs(bottom_val - CROP_BOTTOM_RATIO*100) > 0.1:
                self.use_custom_crop_var.set(True)
            else:
                self.use_custom_crop_var.set(preset_data.get("use_custom_crop", False))
            
            # Apply audio settings
            self.voice_gain_var.set(preset_data.get("voice_gain", VOICE_GAIN))
            self.music_gain_var.set(preset_data.get("music_gain", MUSIC_GAIN))
            
            # Apply translation/TTS settings
            self.translation_enabled_var.set(preset_data.get("translation_enabled", TRANSLATION_ENABLED))
            self.target_language_var.set(preset_data.get("target_language", TARGET_LANGUAGE))
            self.use_ai_voice_var.set(preset_data.get("use_ai_voice", USE_AI_VOICE_REPLACEMENT))
            self.tts_language_var.set(preset_data.get("tts_language", TTS_LANGUAGE))
            self.tts_voice_var.set(preset_data.get("tts_voice", 'Auto (Default)'))
            self.silence_threshold_var.set(preset_data.get("silence_threshold", 300))
            
            # Apply caption settings
            self.words_per_caption_var.set(preset_data.get("words_per_caption", 2))
            if "caption_text_color" in preset_data:
                globals()['CAPTION_TEXT_COLOR'] = tuple(preset_data["caption_text_color"])
            if "caption_stroke_color" in preset_data:
                globals()['CAPTION_STROKE_COLOR'] = tuple(preset_data["caption_stroke_color"])
            self.stroke_width_var.set(preset_data.get("caption_stroke_width", max(1, int(CAPTION_FONT_SIZE * 0.05))))
            self.caption_y_offset_var.set(preset_data.get("caption_y_offset", 0))
            
            # Apply video effects
            self.effect_sharpness_var.set(preset_data.get("effect_sharpness", False))
            self.effect_sharpness_intensity_var.set(preset_data.get("effect_sharpness_intensity", 1.5))
            self.effect_saturation_var.set(preset_data.get("effect_saturation", False))
            self.effect_saturation_intensity_var.set(preset_data.get("effect_saturation_intensity", 1.3))
            self.effect_contrast_var.set(preset_data.get("effect_contrast", False))
            self.effect_contrast_intensity_var.set(preset_data.get("effect_contrast_intensity", 1.2))
            self.effect_brightness_var.set(preset_data.get("effect_brightness", False))
            self.effect_brightness_intensity_var.set(preset_data.get("effect_brightness_intensity", 1.15))
            self.effect_vintage_var.set(preset_data.get("effect_vintage", False))
            self.effect_vintage_intensity_var.set(preset_data.get("effect_vintage_intensity", 0.3))
            
            # Apply background effects
            globals()['STATIC_BG_BLUR_RADIUS'] = preset_data.get("blur_radius", 25)
            globals()['BG_SCALE_EXTRA'] = preset_data.get("bg_scale_extra", 1.08)
            globals()['DIM_FACTOR'] = preset_data.get("dim_factor", 0.55)
            
            # Update UI elements that show values
            self._update_color_canvases()
            
            self.log_widget.config(state="normal")
            self.log_widget.insert(tk.END, f"\n📂 Auto-loaded preset from: {preset_file}\n")
            self.log_widget.config(state="disabled")
            self.log_widget.see(tk.END)
        except Exception as e:
            # Silently fail on auto-load
            self.log_widget.config(state="normal")
            self.log_widget.insert(tk.END, f"\n⚠️ Could not auto-load preset: {e}\n")
            self.log_widget.config(state="disabled")
            self.log_widget.see(tk.END)

    def reset_to_defaults(self):
        """Reset all settings to their default values."""
        result = messagebox.askyesno("Reset to Defaults", 
                                      "This will reset ALL settings to their default values.\n\nAre you sure?")
        if not result:
            return
        
        try:
            # Reset file paths
            self.video_var.set("")
            self.voice_var.set("")
            self.music_var.set("")
            self.output_var.set("final_tiktok.mp4")
            
            # Reset video settings
            self.mirror_video_var.set(False)
            self.use_4k_var.set(False)
            self.use_custom_crop_var.set(False)
            self.top_percent_var.set(CROP_TOP_RATIO*100)
            self.bottom_percent_var.set(CROP_BOTTOM_RATIO*100)
            self.top_label.config(text=f"{self.top_percent_var.get():.1f}%")
            self.bottom_label.config(text=f"{self.bottom_percent_var.get():.1f}%")
            
            # Reset audio settings
            self.voice_gain_var.set(VOICE_GAIN)
            self.music_gain_var.set(MUSIC_GAIN)
            
            # Reset translation/TTS settings
            self.translation_enabled_var.set(TRANSLATION_ENABLED)
            self.target_language_var.set(TARGET_LANGUAGE)
            self.use_ai_voice_var.set(USE_AI_VOICE_REPLACEMENT)
            self.tts_language_var.set(TTS_LANGUAGE)
            self.tts_voice_var.set('Auto (Default)')
            self.silence_threshold_var.set(300)
            
            # Reset caption settings
            self.words_per_caption_var.set(2)
            globals()['CAPTION_TEXT_COLOR'] = (255, 255, 255, 255)
            globals()['CAPTION_STROKE_COLOR'] = (0, 0, 0, 150)
            self.stroke_width_var.set(max(1, int(CAPTION_FONT_SIZE * 0.05)))
            self.caption_y_offset_var.set(0)
            
            # Reset video effects
            self.effect_sharpness_var.set(False)
            self.effect_sharpness_intensity_var.set(1.5)
            self.effect_saturation_var.set(False)
            self.effect_saturation_intensity_var.set(1.3)
            self.effect_contrast_var.set(False)
            self.effect_contrast_intensity_var.set(1.2)
            self.effect_brightness_var.set(False)
            self.effect_brightness_intensity_var.set(1.15)
            self.effect_vintage_var.set(False)
            self.effect_vintage_intensity_var.set(0.3)
            
            # Reset background effects
            globals()['STATIC_BG_BLUR_RADIUS'] = 25
            globals()['BG_SCALE_EXTRA'] = 1.08
            globals()['DIM_FACTOR'] = 0.55
            
            # Update UI
            self._update_color_canvases()
            self.update_mini_preview_immediate()
            
            self.log_widget.config(state="normal")
            self.log_widget.insert(tk.END, "\n🔄 All settings reset to defaults\n")
            self.log_widget.config(state="disabled")
            self.log_widget.see(tk.END)
            
            messagebox.showinfo("Reset Complete", "All settings have been reset to their default values.")
        except Exception as e:
            messagebox.showerror("Reset Failed", f"Could not reset settings: {e}")

    def poll_queue(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg == "[SINGLE_DONE]":
                    self.run_single_btn.config(state="normal")
                    self.run_queue_btn.config(state="normal")
                    self.log_widget.config(state="normal")
                    self.log_widget.insert(tk.END, "\n[Single job finished]\n")
                    self.log_widget.config(state="disabled")
                    self.log_widget.see(tk.END)
                    continue
                if msg == "[QUEUE_DONE]":
                    self.run_queue_btn.config(state="normal")
                    self.run_single_btn.config(state="normal")
                    self.log_widget.config(state="normal")
                    self.log_widget.insert(tk.END, "\n✔ ALL JOBS FINISHED\n")
                    self.log_widget.config(state="disabled")
                    self.log_widget.see(tk.END)
                    continue
                self.log_widget.config(state="normal")
                self.log_widget.insert(tk.END, str(msg))
                if not str(msg).endswith("\n"):
                    self.log_widget.insert(tk.END, "\n")
                self.log_widget.config(state="disabled")
                self.log_widget.see(tk.END)
        except queue.Empty:
            pass
        self.root.after(200, self.poll_queue)
        try:
            self._update_color_canvases()
        except Exception:
            pass


# ----------------- entrypoint -----------------
def main():
    root = tk.Tk()
    app = App(root)
    
    # Auto-load preset if it exists
    preset_file = Path.home() / ".tiktok_preset.json"
    if preset_file.exists():
        try:
            # Use root.after to load preset after UI is fully initialized
            root.after(100, app.load_preset_silent)
        except Exception:
            pass  # Silently ignore errors during auto-load
    
    root.mainloop()

if __name__ == "__main__":
    main()
# Could not insert color UI automatically; please add manually.
