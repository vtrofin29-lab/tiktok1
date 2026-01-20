# TikTok Video Editor with AI Features

A comprehensive TikTok video editor with automatic transcription, translation, and AI voice replacement capabilities.

## Features

### Core Features
- **Video cropping and editing** - Crop videos to TikTok format (9:16 aspect ratio)
- **Automatic transcription** - Convert speech to text using Whisper AI
- **Background blur** - Add blurred background to videos
- **Caption overlay** - Automatically add captions with customizable styling
- **Audio mixing** - Mix voice and background music with volume controls
- **Batch processing** - Queue multiple videos for processing

### New AI Features (v2.0)

#### 1. **Translation Support**
- Automatically translate captions to multiple languages
- Supported languages: English, Spanish, French, German, Italian, Portuguese, Romanian, Russian, Chinese, Japanese, Korean
- Uses Google Translate API for accurate translations
- Preserves timing and formatting of original captions

#### 2. **AI Voice Replacement**
- Replace original voice with AI-generated Text-to-Speech (TTS)
- Supports multiple languages for voice output
- Automatically synchronizes TTS audio with video timing
- Preserves background music during voice replacement
- Uses gTTS (Google Text-to-Speech) for natural-sounding voices

#### 3. **ClapTools Integration**
- Option to use ClapTools API for transcription (alternative to Whisper)
- Fallback to Whisper if ClapTools is unavailable
- Easy toggle between transcription methods

## Installation

### Requirements
- Python 3.8 or higher
- FFmpeg installed and available in PATH
- NVIDIA GPU (optional, for faster encoding)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `Pillow>=10.0.0` - Image processing
- `numpy>=1.24.0` - Numerical operations
- `moviepy` - Video editing
- `whisper` - Speech recognition
- `googletrans==4.0.0rc1` - Translation (new)
- `requests>=2.28.0` - HTTP requests for APIs (new)
- `gtts>=2.3.0` - Text-to-Speech (new)

## Usage

### Basic Usage

1. **Launch the application:**
   ```bash
   python tiktok_full_gui.py
   ```

2. **Select input files:**
   - Video: Choose your source video file
   - Voice: Select the voice/narration audio track
   - Music: Choose background music

3. **Configure settings:**
   - Adjust crop ratios using the preview
   - Set voice and music volume levels
   - Choose caption font and styling

4. **Run the job:**
   - Click "Run Single" for immediate processing
   - Or add to queue and click "Run Queue" for batch processing

### Using Translation

1. **Enable translation:**
   - Check "Enable translation" checkbox
   - Select target language from dropdown
   - Captions will be automatically translated during processing

2. **Supported languages:**
   - `en` - English
   - `es` - Spanish
   - `fr` - French
   - `de` - German
   - `it` - Italian
   - `pt` - Portuguese
   - `ro` - Romanian
   - `ru` - Russian
   - `zh-cn` - Chinese (Simplified)
   - `ja` - Japanese
   - `ko` - Korean

### Using AI Voice Replacement

1. **Enable AI voice:**
   - Check "Replace voice with AI (TTS)" checkbox
   - Select TTS language (should match target caption language)
   - Original voice will be replaced with AI-generated speech

2. **How it works:**
   - Transcribes original voice to text
   - Optionally translates text to target language
   - Generates AI voice from translated text
   - Synchronizes AI voice with video timing
   - Preserves background music

### Using ClapTools

1. **Enable ClapTools:**
   - Check "Use ClapTools for transcription" checkbox
   - Note: Full ClapTools API integration requires API key setup
   - Currently falls back to Whisper if ClapTools is unavailable

## Configuration

### Global Settings

Edit the settings at the top of `tiktok_full_gui.py`:

```python
# Translation and AI Voice settings
TRANSLATION_ENABLED = False
TARGET_LANGUAGE = 'none'  # 'none', 'en', 'es', 'fr', 'ro', etc.
USE_AI_VOICE_REPLACEMENT = False
TTS_LANGUAGE = 'en'
USE_CLAPTOOLS = False
CLAPTOOLS_API_KEY = None
```

### Caption Styling

```python
CAPTION_FONT_PREFERRED = "Bangers"
CAPTION_FONT_SIZE = 56
CAPTION_TEXT_COLOR = (255, 255, 255, 255)
CAPTION_STROKE_COLOR = (0, 0, 0, 150)
CAPTION_STROKE_WIDTH = max(1, int(CAPTION_FONT_SIZE * 0.05))
```

### Video Settings

```python
WIDTH = 1080  # Output width (HD)
HEIGHT = 1920  # Output height (HD)
FPS = 24
VOICE_GAIN = 1.5  # Voice volume multiplier
MUSIC_GAIN = 0.15  # Music volume multiplier
```

## Advanced Features

### Batch Processing
- Add multiple jobs to the queue
- Each job can have different settings
- Process all jobs sequentially with one click

### Custom Crop Settings
- Drag crop lines in preview to adjust framing
- Save and load crop presets
- Per-job custom crop override

### 4K Export
- Toggle "Export in 4K resolution" for 2160x3840 output
- Automatically scales fonts and settings for 4K

### GPU Acceleration
- Automatically detects and uses NVIDIA NVENC if available
- Falls back to CPU encoding if GPU is not available

## Troubleshooting

### Translation Not Working
- Ensure `googletrans==4.0.0rc1` is installed
- Check internet connection (required for translation API)
- Try disabling and re-enabling translation

### AI Voice Not Working
- Ensure `gtts` package is installed
- Check internet connection (gTTS requires internet)
- Verify TTS language matches a supported language code

### ClapTools Not Available
- ClapTools API integration is a placeholder
- Full implementation requires:
  - Valid API key from ClapTools
  - API endpoint configuration
  - Result format conversion

### FFmpeg Errors
- Ensure FFmpeg is installed and in PATH
- Try updating FFmpeg to latest version
- Check video codec compatibility

## API Reference

### Translation Functions

```python
translate_text(text, target_language='en', log=None)
# Translate a single text string

translate_segments(segments, target_language='en', log=None)
# Translate all caption segments
```

### TTS Functions

```python
generate_tts_audio(text, language='en', output_path=None, log=None)
# Generate TTS audio from text

replace_voice_with_tts(caption_segments, language='en', log=None)
# Generate AI voice from caption segments
```

### Transcription Functions

```python
transcribe_captions(voice_path, log=None, use_claptools=False, translate_to=None)
# Transcribe audio with optional ClapTools and translation

transcribe_with_claptools(video_path, api_key=None, log=None)
# Use ClapTools API for transcription (placeholder)
```

## License

This project is provided as-is for educational and personal use.

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## Changelog

### Version 2.0 (2026-01-20)
- ✨ Added translation support for captions (12+ languages)
- ✨ Added AI voice replacement using TTS
- ✨ Added ClapTools integration option
- 🔧 Improved transcription with multiple backend support
- 📝 Added comprehensive documentation

### Version 1.0
- Initial release with core video editing features
- Whisper-based transcription
- Caption overlay
- Audio mixing
- Batch processing
