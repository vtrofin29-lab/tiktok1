# Extended Job Info and Double-Click Load Feature

## Overview
This update adds comprehensive job information display and double-click functionality to load job settings back into the UI for the TikTok video editor.

## Problem Statement (Romanian)
"acum adauga mai mult info cum ar fii daca are ai tts si captions generate ce silence tresh hold are culoarea la font ce border are si daca apas pe unul din joburi de 2 ori sa imi dea load la tot cu imaginea si setarile de la jobul acela"

**Translation:**
"now add more info like if it has AI TTS and captions generate what silence threshold it has what font color what border it has and if I press on one of the jobs twice it should load everything with the image and settings from that job"

## Features Implemented

### 1. Extended Job Information Display

Jobs now display comprehensive information about all their settings:

#### New Fields Added to Job Dictionary:
- `use_ai_voice` (bool) - AI TTS enabled/disabled
- `translation_enabled` (bool) - Translation enabled/disabled
- `target_language` (str) - Target language code (e.g., 'es', 'fr', 'de')
- `silence_threshold_ms` (int) - Silence threshold in milliseconds for AI voice
- `caption_text_color` (tuple) - Font/text color as RGBA (e.g., (255, 255, 255, 255))
- `caption_stroke_color` (tuple) - Border/stroke color as RGBA (e.g., (0, 0, 0, 150))
- `caption_stroke_width` (int) - Border/stroke width in pixels

#### Display Format

The `_format_job_info()` method now shows:

**AI and Translation Settings:**
- `AI-TTS` - When AI voice is enabled
- `Translate:es` - When translation is enabled (shows target language)
- `silence:500ms` - Silence threshold (only when AI voice enabled and non-default 300ms)

**Font and Border Settings:**
- `color:RGB(255,200,100)` - Font color (only when non-default white)
- `border:w=5,RGB(50,50,50)` - Border width and color (only when non-default)

**Example Job Display:**
```
2. video.mp4 | voice.mp3 | music.mp3 [4K, Mirror, 3 words/cap, AI-TTS, Translate:es, silence:500ms, color:RGB(255,200,100), border:w=5,RGB(50,50,50), effects:blur=30/scale=1.15/dim=0.60]
```

### 2. Double-Click Job Loading

Users can now double-click any job in the queue to load all its settings back into the UI.

#### Implementation:
- Added `<Double-Button-1>` event binding to job listbox
- Created `on_job_double_click()` handler method

#### What Gets Loaded:

**File Paths:**
- Video file path
- Voice file path
- Music file path
- Output file path

**Basic Settings:**
- 4K resolution mode
- Mirror video
- Words per caption
- Custom crop settings (top/bottom ratios)

**Effects Settings:**
- Blur radius
- Background scale extra
- Dim factor

**AI and Translation Settings:**
- AI voice enabled/disabled
- Translation enabled/disabled
- Target language
- Silence threshold

**Font and Border Settings:**
- Caption text color (with color picker UI update)
- Caption stroke color (with color picker UI update)
- Caption stroke width (with slider UI update)

**Additional Features:**
- Updates video preview automatically
- Loads font selection if specified
- Logs the load action in the log widget

## Technical Details

### Modified Methods

**1. `add_job()`**
- Extended to capture all new settings
- Stores AI voice, translation, silence threshold
- Stores font and border colors/settings

**2. `on_run_single()`**
- Updated to include all new fields in job dictionary
- Ensures consistency between queued and single jobs

**3. `_format_job_info(job)`**
- Enhanced to display all new settings
- Shows settings only when they differ from defaults (cleaner display)
- Formats colors and settings in readable format

**4. `on_job_double_click(event)` [NEW]**
- Loads all job settings back into UI
- Updates all UI elements (sliders, checkboxes, color pickers)
- Triggers video preview update
- Handles errors gracefully

## Testing

Created comprehensive test suite in `test_job_info_extended.py`:

### Test Coverage:
1. **Extended job info display** - Validates formatting of all new fields
2. **Job info fields** - Verifies all new fields are properly stored
3. **Display scenarios** - Tests various combinations of settings

### Test Results:
✅ All tests pass
✅ CodeQL security scan: 0 alerts

## Usage

### Viewing Job Information
Simply look at the job in the queue. All non-default settings are displayed in brackets after the file names.

### Loading Job Settings
1. Double-click any job in the queue
2. All settings from that job will be loaded into the UI
3. Video preview will update automatically
4. Color pickers and all UI elements will reflect the job's settings
5. You can now modify and run or save the loaded settings

## Benefits

1. **Complete Visibility** - Users can see all job settings at a glance
2. **Easy Reuse** - Double-click to reuse any previous job's configuration
3. **Less Repetition** - No need to manually reconfigure settings
4. **Better Organization** - Clear display of what makes each job unique
5. **Faster Workflow** - Quick configuration switching between jobs

## Files Modified

- `tiktok_full_gui.py` - Main implementation
  - Added 7 new fields to job dictionary
  - Enhanced `_format_job_info()` method
  - Implemented `on_job_double_click()` handler
  - Added double-click event binding
  
- `test_job_info_extended.py` - Test suite (new file)
  - Comprehensive test coverage
  - All tests passing

## Backward Compatibility

- All new fields have sensible defaults
- Existing jobs will continue to work
- Old job format is compatible (missing fields use defaults)
- No breaking changes to existing functionality

## Security

- ✅ CodeQL security scan: 0 alerts
- No sensitive data exposed
- Safe handling of color values and settings
- Proper error handling in all new code

## Example Scenarios

### Scenario 1: Simple Job (Default Settings)
```
1. intro.mp4 | narration.mp3 | background.mp3
```
No extra info shown - all settings are default.

### Scenario 2: AI TTS Enabled
```
2. video.mp4 | voice.mp3 | music.mp3 [AI-TTS]
```
Shows that AI voice is enabled with default silence threshold.

### Scenario 3: Full Featured Job
```
3. promo.mp4 | voice.mp3 | beat.mp3 [4K, AI-TTS, Translate:es, silence:500ms, color:RGB(255,200,100), border:w=7,RGB(200,100,50)]
```
Shows all enabled features and custom settings.

### Scenario 4: Double-Click to Reuse
1. See job #3 in the list with custom settings
2. Double-click on job #3
3. All settings load: 4K mode, AI TTS, Spanish translation, custom colors, etc.
4. Video preview updates automatically
5. Make any adjustments if needed
6. Run or add to queue with the loaded configuration

## Future Enhancements

Potential improvements for future versions:
- Drag and drop to reorder jobs
- Copy/paste job settings
- Save job templates
- Batch edit multiple jobs
- Export/import job configurations

