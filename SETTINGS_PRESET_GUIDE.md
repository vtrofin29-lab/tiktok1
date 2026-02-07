# Settings Preset Guide

## Overview

The Settings Preset feature allows you to save ALL your current settings to a file and automatically restore them the next time you open the application. This saves time and ensures consistency across editing sessions.

## Features

### 💾 Save Preset
- Saves all current settings to a preset file
- File location: `~/.tiktok_preset.json` (in your home directory)
- Includes ALL settings from the entire application
- User-friendly JSON format for easy editing

### 📂 Load Preset
- Loads and applies all saved settings
- Updates the entire UI instantly
- Shows confirmation message
- Fails gracefully if preset file is missing or corrupted

### 🔄 Reset to Defaults
- Resets ALL settings to their default values
- Asks for confirmation before proceeding
- Useful for starting fresh or fixing issues

### ⚡ Auto-Load on Startup
- Automatically loads your preset when you start the app
- Seamless restoration of your previous session
- Silent operation (logs to widget instead of popup)

## Settings Saved

The preset saves **ALL** settings from the application:

### File Paths
- Video path
- Voice path
- Music path
- Output path

### Video Settings
- Mirror video (on/off)
- Use 4K resolution (on/off)
- Custom crop enabled (on/off)
- Crop top percentage
- Crop bottom percentage

### Audio Settings
- Voice gain (volume boost)
- Music gain (volume boost)

### Translation & TTS Settings
- Translation enabled (on/off)
- Target language
- Use AI voice replacement (on/off)
- TTS language
- TTS voice selection
- Silence threshold (ms)

### Caption Settings
- Words per caption
- Text color (RGBA)
- Stroke/border color (RGBA)
- Stroke width
- Caption Y offset

### Video Effects (All 5)
- **Resilience (Sharpness)**: enabled + intensity
- **Vibrance (Saturation)**: enabled + intensity
- **HDR (Contrast)**: enabled + intensity
- **Brightness Boost**: enabled + intensity
- **Vintage (Film Grain)**: enabled + intensity

### Background Effects
- Blur radius
- Background scale multiplier
- Dim factor

## How to Use

### Save Your Settings

1. Configure all your settings as desired:
   - Video effects
   - Colors
   - Audio levels
   - Translation options
   - Everything!

2. Click the **"💾 Save Preset"** button

3. You'll see a confirmation message with the file location

4. Your settings are now saved!

### Load Your Settings

**Manual Load:**
1. Click the **"📂 Load Preset"** button
2. All settings will be applied instantly
3. You'll see a confirmation message

**Automatic Load:**
- Just open the app!
- If a preset file exists, it will be automatically loaded
- You'll see a message in the log: "📂 Auto-loaded preset from: ..."

### Reset to Defaults

1. Click the **"🔄 Reset to Defaults"** button
2. Confirm that you want to reset
3. All settings return to their original default values

## Preset File Format

The preset is saved as JSON in `~/.tiktok_preset.json`:

```json
{
  "video_path": "",
  "voice_path": "",
  "music_path": "",
  "output_path": "final_tiktok.mp4",
  "mirror_video": false,
  "use_4k": true,
  "use_custom_crop": false,
  "top_percent": 10.0,
  "bottom_percent": 10.0,
  "voice_gain": 3.0,
  "music_gain": -15.0,
  "translation_enabled": false,
  "target_language": "es",
  "use_ai_voice": false,
  "tts_language": "en",
  "tts_voice": "Auto (Default)",
  "silence_threshold": 300,
  "words_per_caption": 2,
  "caption_text_color": [255, 255, 255, 255],
  "caption_stroke_color": [0, 0, 0, 150],
  "caption_stroke_width": 4.0,
  "caption_y_offset": 0,
  "effect_sharpness": true,
  "effect_sharpness_intensity": 1.6,
  "effect_saturation": false,
  "effect_saturation_intensity": 1.3,
  "effect_contrast": false,
  "effect_contrast_intensity": 1.2,
  "effect_brightness": false,
  "effect_brightness_intensity": 1.15,
  "effect_vintage": false,
  "effect_vintage_intensity": 0.3,
  "blur_radius": 25,
  "bg_scale_extra": 1.08,
  "dim_factor": 0.55
}
```

## Advanced Usage

### Manual Editing

You can manually edit the preset file with any text editor:

1. Find the file: `~/.tiktok_preset.json`
   - Windows: `C:\Users\YourName\.tiktok_preset.json`
   - Mac/Linux: `/home/username/.tiktok_preset.json`

2. Edit with any text editor (Notepad, VS Code, etc.)

3. Save the file

4. Reload in the app with "📂 Load Preset" button

### Sharing Presets

1. Locate your preset file
2. Copy it to share with others
3. Others can place it in their home directory
4. It will auto-load on their next app start

### Multiple Presets

While the app only uses one preset file, you can maintain multiple:

1. Save a preset
2. Rename `~/.tiktok_preset.json` to something like `preset_social_media.json`
3. Configure different settings
4. Save another preset
5. Rename to `preset_professional.json`
6. When needed, copy the desired preset back to `~/.tiktok_preset.json`

### Backup Your Preset

It's a good idea to backup your preset file:

```bash
# Copy your preset to a backup location
cp ~/.tiktok_preset.json ~/Documents/tiktok_preset_backup.json
```

## Troubleshooting

### Preset Not Loading

**Issue**: Click "Load Preset" but nothing happens

**Solutions**:
1. Check if the preset file exists at `~/.tiktok_preset.json`
2. Verify the file is valid JSON (use a JSON validator)
3. Check the log widget for error messages
4. Try "Reset to Defaults" and save a new preset

### Settings Not Saving

**Issue**: Clicked "Save Preset" but settings don't persist

**Solutions**:
1. Check file permissions on your home directory
2. Verify you have write access
3. Check the log widget for error messages
4. Try saving to a different location manually for testing

### Auto-Load Not Working

**Issue**: Preset doesn't load automatically on startup

**Solutions**:
1. Verify the preset file exists and is named correctly
2. Check the log widget for "Auto-loaded preset" message
3. Try loading manually with "Load Preset" button
4. If manual load works, check for startup errors

### Corrupted Preset File

**Issue**: Error when loading preset

**Solutions**:
1. Delete the preset file: `rm ~/.tiktok_preset.json`
2. Click "Reset to Defaults"
3. Reconfigure your settings
4. Save a new preset

### Missing Settings

**Issue**: Some settings not restored after loading

**Solutions**:
1. Check if those settings exist in the JSON file
2. Update to the latest version of the app
3. Save a new preset to include new features
4. Manually add missing fields to the JSON

## Tips & Best Practices

### When to Save

✅ **Good times to save a preset**:
- After configuring your ideal settings
- Before experimenting with new effects
- After finding a great combination
- Before updating the app

❌ **Don't save**:
- When you have broken/test settings
- Before you've tested the results
- With temporary file paths (unless you want them)

### File Paths

The preset saves file paths, but you might not want this:

**Option 1**: Keep paths
- Useful if you work with the same files regularly
- Auto-loads your project

**Option 2**: Clear paths before saving
- Clear video/voice/music paths
- Keep only settings
- More portable preset

### Organizing Presets

Create a folder for your presets:

```bash
mkdir ~/tiktok_presets
```

Name your presets descriptively:
- `preset_social_media_bright.json`
- `preset_professional_clean.json`
- `preset_vintage_film.json`
- `preset_4k_high_quality.json`

### Version Control

If you work in a team:
1. Save your preset
2. Add it to your project repository (rename it)
3. Share with team members
4. Everyone uses consistent settings

## FAQ

**Q: Where is the preset file stored?**
A: In your home directory: `~/.tiktok_preset.json`

**Q: Can I have multiple presets?**
A: The app uses one active preset, but you can maintain multiple by renaming files.

**Q: Is the preset file safe to edit?**
A: Yes! It's standard JSON. Just maintain the structure.

**Q: What if I break the preset file?**
A: Just delete it and save a new one. Or use "Reset to Defaults".

**Q: Can I share my preset?**
A: Yes! Just copy the `.tiktok_preset.json` file to share.

**Q: Will my preset work after app updates?**
A: Usually yes. New settings will use defaults if missing.

**Q: Can I exclude certain settings?**
A: Not through the UI, but you can manually remove them from the JSON file.

**Q: Does the preset include API keys?**
A: No, API keys are stored separately for security.

## Summary

The Settings Preset feature is a powerful time-saver that:

✅ Saves ALL your settings in one click
✅ Auto-loads on startup
✅ Works with all features
✅ Uses human-readable JSON
✅ Easy to backup and share
✅ Includes reset functionality

Never waste time reconfiguring settings again!
