# TTS Debug Guide - Troubleshooting Gen AI Voice Issues

**Problem:** "tot nu i a vocea de pe gen ai" (still doesn't take the voice from gen ai)

## What We've Done

We've added comprehensive diagnostic logging to track exactly what's happening with the TTS (Text-to-Speech) voice generation and integration.

### Changes Made:

1. **Added TTS Success Flag** - Tracks whether TTS was successfully applied
2. **Enhanced Logging** - Clear messages showing which audio is being used
3. **Failure Detection** - Explicit messages when TTS fails or isn't enabled

## How to Use These Diagnostics

### Step 1: Run Video Processing

1. Open the application
2. Load your video, voice, and music files
3. **Enable "Use AI Voice"** checkbox
4. Set your desired TTS language (e.g., Romanian)
5. Add job to queue or run single
6. **Watch the log output carefully**

### Step 2: Look for These Key Messages

#### If TTS is Working Correctly:

You should see:
```
[AI VOICE] 🎵 GENERATING AI VOICE REPLACEMENT
[AI VOICE] Segments to synthesize: XX
[AI VOICE] Target language: ro (or your language)
...
[AI VOICE] ✅ VOICE REPLACEMENT SUCCESSFUL!
[AI VOICE] 🎯 TTS FLAG SET: TTS audio will be used in final video
[AI VOICE] Final audio duration: X.XXs
[AI VOICE] Final video duration: X.XXs
...
[FINAL COMPOSITION] 🎤 USING AI-GENERATED TTS VOICE
[FINAL COMPOSITION] ✓ TTS voice successfully integrated
```

#### If TTS is NOT Working:

You might see one of these:

**Scenario 1: TTS Generation Failed**
```
[AI VOICE] 🎵 GENERATING AI VOICE REPLACEMENT
...
[AI VOICE ERROR] ❌ Failed to use TTS audio: {error message}
[AI VOICE ERROR] Falling back to original voice/music audio
...
[FINAL COMPOSITION] 🎵 Using original voice/music audio
[FINAL COMPOSITION] (AI voice was not enabled or failed)
```

**Scenario 2: TTS Returned None**
```
[AI VOICE] 🎵 GENERATING AI VOICE REPLACEMENT
...
[AI VOICE] ⚠️ TTS audio generation returned None - using original audio
...
[FINAL COMPOSITION] 🎵 Using original voice/music audio
```

**Scenario 3: No Captions Available**
```
[AI VOICE] No captions available - AI voice replacement skipped
[AI VOICE] Tip: Provide voice file with audio for automatic transcription
...
[FINAL COMPOSITION] 🎵 Using original voice/music audio
```

**Scenario 4: AI Voice Not Enabled**
```
[FINAL COMPOSITION] 🎵 Using original voice/music audio
[FINAL COMPOSITION] (AI voice was not enabled or failed)
```

### Step 3: Identify the Problem

Based on what you see in the logs:

#### Problem A: "TTS audio generation returned None"
- The `replace_voice_with_tts()` function is failing
- Check if you have internet connection (needed for TTS API)
- Check if API key is configured correctly
- Check if the language code is valid

#### Problem B: "Failed to use TTS audio" with error
- Look at the error message for details
- Could be file permission issues
- Could be audio processing error
- Could be silence removal failing

#### Problem C: "No captions available"
- You need a voice file with audio for transcription
- Or manually provide captions
- The system needs text to convert to speech

#### Problem D: Final composition shows "Using original voice"
- This means TTS processing completed but flag wasn't set
- Could indicate an exception was thrown silently
- Check for error messages earlier in the log

## What to Report

When reporting the issue, please include:

1. **The complete log output** from start to finish
2. **The final composition message** - specifically whether it says:
   - "🎤 USING AI-GENERATED TTS VOICE" or
   - "🎵 Using original voice/music audio"
3. **Any error messages** you see in the log
4. **Your configuration:**
   - Is "Use AI Voice" checked?
   - What TTS language is selected?
   - Do you have a voice file provided?

## Common Fixes

### Fix 1: Enable AI Voice
Make sure the "Use AI Voice" checkbox is checked when you add the job or run single.

### Fix 2: Provide Voice File
The system needs a voice file to transcribe captions, which are then used to generate TTS.

### Fix 3: Check Language Parameter
Verify that `use_ai_voice=True` and `tts_language='ro'` (or your language) are being passed to the processing function.

### Fix 4: Check Job Dictionary
The job should contain:
- `"use_ai_voice": True`
- `"tts_language": "ro"` (or your language)
- `"target_language": "ro"` (if translation enabled)
- `"translation_enabled": True` (if you want translation)

## Next Steps

1. **Run the application** with the current code
2. **Process a video** with AI Voice enabled
3. **Copy the complete log output**
4. **Share the log** so we can see exactly what's happening
5. **Based on the log**, we'll know:
   - If TTS is generating successfully
   - If TTS audio is being created
   - If TTS audio is being integrated into the final video
   - Where exactly the process is failing

The new diagnostic messages make it **impossible to miss** what's happening with the TTS voice!
