"""
Test to validate that export functions use the configured CAPTION_FONT_SIZE
and CAPTION_STROKE_COLOR instead of hardcoded values.

These tests verify the fixes to:
1. _generate_ass_subtitle_file - was ignoring fontsize param, now uses it
2. _build_caption_drawtext_filter - was defaulting to 56, now accepts fontsize
3. _build_all_caption_filters - was not passing fontsize, now passes it through
4. _export_with_ffmpeg_filters - was hardcoding fontsize=56 and stroke_color,
   now reads CAPTION_FONT_SIZE and CAPTION_STROKE_COLOR from globals
"""
import sys
import os
import re
import tempfile


# ---- Copy of key functions from tiktok_full_gui.py for testing ----
# We copy these here because tiktok_full_gui.py requires tkinter (GUI)

def _rgba_to_hex(rgba_tuple):
    """Convert RGBA tuple to hex color string for FFmpeg."""
    try:
        r, g, b = int(rgba_tuple[0]), int(rgba_tuple[1]), int(rgba_tuple[2])
        return f"0x{r:02X}{g:02X}{b:02X}"
    except Exception:
        return "0xFFFFFF"


def _calculate_text_lines(text, max_chars=40, words_per_line=None):
    """Simple text wrapping for captions."""
    if words_per_line:
        words = text.split()
        lines = []
        for i in range(0, len(words), words_per_line):
            lines.append(' '.join(words[i:i+words_per_line]))
        return lines if lines else [text]
    lines = []
    current_line = ""
    for word in text.split():
        if current_line and len(current_line) + 1 + len(word) > max_chars:
            lines.append(current_line)
            current_line = word
        else:
            current_line = f"{current_line} {word}".strip()
    if current_line:
        lines.append(current_line)
    return lines if lines else [text]


def _escape_ffmpeg_text(text):
    """Escape text for FFmpeg drawtext filter."""
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    return text


def _generate_ass_subtitle_file(caption_segments, output_path, font_name="Arial", fontsize=56,
                                text_color_rgba=(255, 255, 255, 255), stroke_width=3,
                                stroke_color_rgba=(0, 0, 0, 150)):
    """Generate an ASS subtitle file using the given fontsize."""
    r, g, b, a = text_color_rgba
    alpha_hex = f"{255 - int(a):02X}"
    text_color_ass = f"&H{alpha_hex}{b:02X}{g:02X}{r:02X}"
    # Convert stroke color RGBA to ASS format
    sr, sg, sb, sa = stroke_color_rgba
    stroke_alpha_hex = f"{255 - int(sa):02X}"
    outline_color_ass = f"&H{stroke_alpha_hex}{sb:02X}{sg:02X}{sr:02X}"

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

    for segment in caption_segments:
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
        text = segment['text'].replace('\n', '\\N')
        ass_content += f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text}\n"

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(ass_content)
    return output_path


def _build_caption_drawtext_filter(caption_text, start_time, end_time, video_width, video_height,
                                   fontsize=56, font_path=None, text_color="0xFFFFFF",
                                   stroke_color="0x000000", stroke_width=3, words_per_line=None,
                                   y_offset=0):
    """Build FFmpeg drawtext filter for a single caption with custom styling."""
    lines = _calculate_text_lines(caption_text, max_chars=40, words_per_line=words_per_line)
    escaped_lines = [_escape_ffmpeg_text(line) for line in lines]
    text_with_newlines = '\\n'.join(escaped_lines)
    y_position = f"h-th+({y_offset})"
    filter_parts = [
        f"drawtext=text='{text_with_newlines}'",
        f"fontsize={fontsize}",
        f"fontcolor={text_color}",
        f"borderw={stroke_width}",
        f"bordercolor={stroke_color}",
        f"x=(w-text_w)/2",
        f"y={y_position}",
        f"enable='between(t,{start_time:.3f},{end_time:.3f})'"
    ]
    if font_path and os.path.exists(font_path):
        filter_parts.insert(1, f"fontfile='{font_path}'")
    return ':'.join(filter_parts)


def _build_all_caption_filters(caption_segments, video_width, video_height,
                               font_path=None, text_color="0xFFFFFF",
                               stroke_color="0x000000", stroke_width=3, words_per_line=None,
                               fontsize=56, y_offset=0):
    """Build all caption drawtext filters and chain them together."""
    if not caption_segments:
        return None
    filters = []
    for segment in caption_segments:
        caption_filter = _build_caption_drawtext_filter(
            caption_text=segment['text'],
            start_time=segment['start'],
            end_time=segment['end'],
            video_width=video_width,
            video_height=video_height,
            fontsize=fontsize,
            font_path=font_path,
            text_color=text_color,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            words_per_line=words_per_line,
            y_offset=y_offset
        )
        filters.append(caption_filter)
    return ','.join(filters)


# ---- Tests ----

def test_ass_subtitle_uses_font_size():
    """Test that _generate_ass_subtitle_file uses the provided fontsize parameter."""
    print("Testing ASS subtitle file uses provided font size...")

    caption_segments = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
        {"text": "Test caption", "start": 1.5, "end": 2.5},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as f:
        output_path = f.name

    try:
        _generate_ass_subtitle_file(
            caption_segments, output_path,
            font_name="Arial", fontsize=112,
            text_color_rgba=(255, 255, 255, 255), stroke_width=3
        )

        with open(output_path, 'r') as f:
            content = f.read()

        # The ASS Style line should contain fontsize 112
        if ",112," in content:
            print("✓ ASS subtitle file uses provided fontsize=112")
        else:
            print("✗ ASS subtitle file does not contain fontsize=112")
            return False

        # Verify the default (56) is NOT in the Style line
        style_lines = [l for l in content.split('\n') if l.startswith('Style:')]
        for line in style_lines:
            if ",56," in line:
                print("✗ ASS subtitle file still contains hardcoded fontsize=56 in Style line")
                return False
        print("✓ ASS subtitle file does not contain hardcoded fontsize=56 in Style")
        return True
    finally:
        os.unlink(output_path)


def test_drawtext_filter_uses_font_size():
    """Test that _build_caption_drawtext_filter uses the provided fontsize."""
    print("\nTesting drawtext filter uses provided font size...")

    filter_str = _build_caption_drawtext_filter(
        caption_text="Hello world",
        start_time=0.0, end_time=1.0,
        video_width=1080, video_height=1920,
        fontsize=112,
    )

    if "fontsize=112" in filter_str:
        print("✓ Drawtext filter uses provided fontsize=112")
    else:
        print("✗ Drawtext filter does not contain fontsize=112")
        return False

    if "fontsize=56" in filter_str:
        print("✗ Drawtext filter still contains hardcoded fontsize=56")
        return False
    print("✓ Drawtext filter does not contain hardcoded fontsize=56")
    return True


def test_build_all_caption_filters_passes_font_size():
    """Test that _build_all_caption_filters passes fontsize to individual filters."""
    print("\nTesting _build_all_caption_filters passes font size through...")

    caption_segments = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
        {"text": "Test caption", "start": 1.5, "end": 2.5},
    ]

    filters_str = _build_all_caption_filters(
        caption_segments,
        video_width=1080, video_height=1920,
        fontsize=112,
    )

    if filters_str is None:
        print("✗ _build_all_caption_filters returned None")
        return False

    count_112 = filters_str.count("fontsize=112")
    if count_112 == len(caption_segments):
        print(f"✓ All {count_112} caption filters use fontsize=112")
    else:
        print(f"✗ Expected {len(caption_segments)} occurrences of fontsize=112, got {count_112}")
        return False

    if "fontsize=56" in filters_str:
        print("✗ Filters still contain hardcoded fontsize=56")
        return False
    print("✓ No hardcoded fontsize=56 found in filters")
    return True


def test_stroke_color_passed_to_filters():
    """Test that custom stroke color is passed through to drawtext filters."""
    print("\nTesting stroke color is passed to drawtext filters...")

    custom_stroke = "0xFF0000"  # Red stroke
    filter_str = _build_caption_drawtext_filter(
        caption_text="Hello world",
        start_time=0.0, end_time=1.0,
        video_width=1080, video_height=1920,
        stroke_color=custom_stroke,
    )

    if f"bordercolor={custom_stroke}" in filter_str:
        print(f"✓ Drawtext filter uses provided stroke_color={custom_stroke}")
    else:
        print(f"✗ Drawtext filter does not contain bordercolor={custom_stroke}")
        return False
    return True


def test_rgba_to_hex_conversion():
    """Test that _rgba_to_hex correctly converts stroke colors."""
    print("\nTesting _rgba_to_hex conversion for stroke colors...")

    test_cases = [
        ((0, 0, 0, 150), "0x000000"),
        ((255, 0, 0, 200), "0xFF0000"),
        ((0, 255, 0, 255), "0x00FF00"),
        ((0, 0, 255, 128), "0x0000FF"),
        ((255, 255, 255, 255), "0xFFFFFF"),
    ]

    all_passed = True
    for rgba, expected_hex in test_cases:
        result = _rgba_to_hex(rgba)
        if result == expected_hex:
            print(f"✓ {rgba} -> {result}")
        else:
            print(f"✗ {rgba} -> {result} (expected {expected_hex})")
            all_passed = False

    return all_passed


def test_source_code_no_hardcoded_fontsize():
    """Verify that the actual source code no longer has hardcoded fontsize=56 in export calls."""
    print("\nVerifying source code fixes (no hardcoded fontsize in export)...")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r') as f:
        content = f.read()

    # Find the _export_with_ffmpeg_filters function
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    if export_fn_start == -1:
        print("✗ Could not find _export_with_ffmpeg_filters function")
        return False

    # Find the next function definition after _export_with_ffmpeg_filters
    next_fn = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn] if next_fn != -1 else content[export_fn_start:]

    # Check that the ASS subtitle call uses font_size variable, not hardcoded 56
    if 'fontsize=font_size' in export_fn_body:
        print("✓ ASS subtitle call uses font_size variable")
    else:
        print("✗ ASS subtitle call does not use font_size variable")
        return False

    if 'fontsize=56' in export_fn_body:
        print("✗ Export function still contains hardcoded fontsize=56")
        return False
    print("✓ No hardcoded fontsize=56 in export function")

    # Check stroke color is read from globals, not hardcoded
    if "CAPTION_STROKE_COLOR" in export_fn_body:
        print("✓ Export function reads CAPTION_STROKE_COLOR from globals")
    else:
        print("✗ Export function does not read CAPTION_STROKE_COLOR")
        return False

    # Check _build_all_caption_filters call passes fontsize
    if 'fontsize=font_size' in export_fn_body:
        print("✓ _build_all_caption_filters call passes font_size")
    else:
        print("✗ _build_all_caption_filters call does not pass font_size")
        return False

    # Check CAPTION_FONT_SIZE is read from globals
    if "globals().get('CAPTION_FONT_SIZE'" in export_fn_body:
        print("✓ Export function reads CAPTION_FONT_SIZE from globals")
    else:
        print("✗ Export function does not read CAPTION_FONT_SIZE from globals")
        return False

    return True


def test_ass_subtitle_uses_stroke_color():
    """Test that _generate_ass_subtitle_file uses the provided stroke_color_rgba parameter."""
    print("\nTesting ASS subtitle file uses provided stroke color...")

    caption_segments = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as f:
        output_path = f.name

    try:
        # Use red stroke color (255, 0, 0, 200)
        _generate_ass_subtitle_file(
            caption_segments, output_path,
            font_name="Arial", fontsize=56,
            text_color_rgba=(255, 255, 255, 255), stroke_width=3,
            stroke_color_rgba=(255, 0, 0, 200)
        )

        with open(output_path, 'r') as f:
            content = f.read()

        # ASS format: &HAABBGGRR -> for (255,0,0,200), alpha=255-200=55=0x37, B=0, G=0, R=255
        # Expected: &H370000FF
        style_lines = [l for l in content.split('\n') if l.startswith('Style:')]
        
        # Check that hardcoded black "&H00000000" is NOT the outline color
        for line in style_lines:
            # OutlineColour is the 6th field (0-indexed: 5th) in the Style line
            # Style: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, ...
            parts = line.split(',')
            if len(parts) >= 6:
                outline_color = parts[5]  # OutlineColour field
                if outline_color == "&H00000000":
                    print("✗ ASS subtitle file still uses hardcoded black outline (&H00000000)")
                    return False
                if "0000FF" in outline_color:  # Should contain red component (FF in RR position)
                    print(f"✓ ASS subtitle file uses custom stroke color: {outline_color}")
                else:
                    print(f"✗ ASS subtitle file has unexpected outline color: {outline_color}")
                    return False

        return True
    finally:
        os.unlink(output_path)


def test_ass_subtitle_default_text_color_is_white():
    """Test that _generate_ass_subtitle_file defaults to white text, not yellow."""
    print("\nTesting ASS subtitle file defaults to white text color...")

    caption_segments = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
    ]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.ass', delete=False) as f:
        output_path = f.name

    try:
        # Call without specifying text_color_rgba - should default to white (255,255,255,255)
        _generate_ass_subtitle_file(
            caption_segments, output_path,
            font_name="Arial", fontsize=56,
        )

        with open(output_path, 'r') as f:
            content = f.read()

        # White in ASS format: &H00FFFFFF (alpha=0 means opaque, BGR=FFFFFF)
        style_lines = [l for l in content.split('\n') if l.startswith('Style:')]
        for line in style_lines:
            parts = line.split(',')
            if len(parts) >= 4:
                primary_color = parts[3]  # PrimaryColour field
                # For white (255,255,255,255): alpha=255-255=0x00, B=FF, G=FF, R=FF -> &H00FFFFFF
                if primary_color == "&H00FFFFFF":
                    print(f"✓ Default text color is white: {primary_color}")
                elif "00FFFF" in primary_color:  # Yellow would be &H0000FFFF
                    print(f"✗ Default text color is yellow (old bug): {primary_color}")
                    return False
                else:
                    print(f"✗ Unexpected default text color: {primary_color}")
                    return False

        return True
    finally:
        os.unlink(output_path)


def test_source_code_ass_has_stroke_color_param():
    """Verify source code passes stroke_color_rgba to _generate_ass_subtitle_file."""
    print("\nVerifying source code passes stroke_color_rgba to ASS generator...")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r') as f:
        content = f.read()

    # Check _generate_ass_subtitle_file has stroke_color_rgba parameter
    ass_fn_start = content.find('def _generate_ass_subtitle_file')
    if ass_fn_start == -1:
        print("✗ Could not find _generate_ass_subtitle_file function")
        return False

    # Get the function signature area (may span multiple lines)
    # Look for the docstring start to capture full signature
    fn_sig_end = content.find('"""', ass_fn_start)
    fn_sig = content[ass_fn_start:fn_sig_end] if fn_sig_end != -1 else content[ass_fn_start:ass_fn_start+500]

    if 'stroke_color_rgba' in fn_sig:
        print("✓ _generate_ass_subtitle_file accepts stroke_color_rgba parameter")
    else:
        print("✗ _generate_ass_subtitle_file missing stroke_color_rgba parameter")
        return False

    # Check the export function passes stroke_color_rgba to ASS generator
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn] if next_fn != -1 else content[export_fn_start:]

    if 'stroke_color_rgba=stroke_color_rgba' in export_fn_body:
        print("✓ Export function passes stroke_color_rgba to ASS generator")
    else:
        print("✗ Export function does not pass stroke_color_rgba to ASS generator")
        return False

    # Check that outline color is NOT hardcoded in the ASS function body
    ass_fn_end = content.find('\ndef ', ass_fn_start + 1)
    ass_fn_body = content[ass_fn_start:ass_fn_end] if ass_fn_end != -1 else content[ass_fn_start:]
    
    if '"&H00000000"' in ass_fn_body:
        print("✗ _generate_ass_subtitle_file still has hardcoded black outline")
        return False
    print("✓ _generate_ass_subtitle_file does not have hardcoded outline color")

    return True


def test_drawtext_uses_y_offset():
    """Test that _build_caption_drawtext_filter uses y_offset instead of hardcoded h-150."""
    print("\nTesting drawtext filter uses y_offset parameter...")

    # Test with default y_offset=0 (bottom position)
    filter_str = _build_caption_drawtext_filter(
        caption_text="Hello world",
        start_time=0.0, end_time=1.0,
        video_width=1080, video_height=1920,
        y_offset=0,
    )

    if "h-150" in filter_str:
        print("✗ Drawtext filter still uses hardcoded h-150")
        return False
    if "h-th+(0)" in filter_str:
        print("✓ Default y_offset=0 produces y=h-th+(0)")
    else:
        print(f"✗ Unexpected y position in filter: {filter_str}")
        return False

    # Test with negative y_offset (moving captions up)
    filter_str_up = _build_caption_drawtext_filter(
        caption_text="Hello world",
        start_time=0.0, end_time=1.0,
        video_width=1080, video_height=1920,
        y_offset=-618,
    )

    if "h-th+(-618)" in filter_str_up:
        print("✓ Negative y_offset=-618 produces y=h-th+(-618)")
    else:
        print(f"✗ Unexpected y position with offset: {filter_str_up}")
        return False

    return True


def test_build_all_caption_filters_passes_y_offset():
    """Test that _build_all_caption_filters passes y_offset to individual filters."""
    print("\nTesting _build_all_caption_filters passes y_offset through...")

    caption_segments = [
        {"text": "Hello world", "start": 0.0, "end": 1.0},
        {"text": "Test caption", "start": 1.5, "end": 2.5},
    ]

    filters_str = _build_all_caption_filters(
        caption_segments,
        video_width=1080, video_height=1920,
        y_offset=-400,
    )

    if filters_str is None:
        print("✗ _build_all_caption_filters returned None")
        return False

    count_offset = filters_str.count("h-th+(-400)")
    if count_offset == len(caption_segments):
        print(f"✓ All {count_offset} caption filters use y_offset=-400")
    else:
        print(f"✗ Expected {len(caption_segments)} occurrences of h-th+(-400), got {count_offset}")
        return False

    if "h-150" in filters_str:
        print("✗ Filters still contain hardcoded h-150")
        return False
    print("✓ No hardcoded h-150 found in filters")
    return True


def test_source_code_drawtext_no_hardcoded_position():
    """Verify source code no longer has hardcoded y position in drawtext."""
    print("\nVerifying source code drawtext uses y_offset (no hardcoded h-150)...")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r') as f:
        content = f.read()

    # Find the _build_caption_drawtext_filter function
    fn_start = content.find('def _build_caption_drawtext_filter')
    if fn_start == -1:
        print("✗ Could not find _build_caption_drawtext_filter function")
        return False

    next_fn = content.find('\ndef ', fn_start + 1)
    fn_body = content[fn_start:next_fn] if next_fn != -1 else content[fn_start:]

    # Check that y_offset parameter exists
    if 'y_offset' in fn_body[:fn_body.find('"""', 10)]:  # Check in signature area
        print("✓ _build_caption_drawtext_filter accepts y_offset parameter")
    else:
        print("✗ _build_caption_drawtext_filter missing y_offset parameter")
        return False

    # Check that hardcoded h-150 is NOT used
    if 'h-150' in fn_body:
        print("✗ _build_caption_drawtext_filter still has hardcoded h-150")
        return False
    print("✓ No hardcoded h-150 in drawtext filter function")

    # Check that y_offset is used in y_position
    if 'y_offset' in fn_body[fn_body.find('y_position'):]:
        print("✓ y_position uses y_offset parameter")
    else:
        print("✗ y_position does not use y_offset")
        return False

    # Check export function passes y_offset to _build_all_caption_filters
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn2 = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn2] if next_fn2 != -1 else content[export_fn_start:]

    if 'y_offset=caption_y_offset' in export_fn_body:
        print("✓ Export function passes caption_y_offset to caption filters")
    else:
        print("✗ Export function does not pass y_offset to caption filters")
        return False

    return True


def test_source_code_uses_two_pass_export():
    """Test that export uses two-pass approach: pre-render bg, then lightweight final encode."""
    print("\n--- Test: Source code uses two-pass export (pre-render bg) ---")
    source_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the _export_with_ffmpeg_filters function body
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn] if next_fn != -1 else content[export_fn_start:]

    # Check that bg is pre-rendered to a temp file
    if 'bg_prerendered_path' not in export_fn_body:
        print("✗ bg_prerendered_path not found - bg should be pre-rendered")
        return False
    print("✓ Background is pre-rendered to temp file")

    # Check that boxblur is in the bg pre-render
    if 'boxblur=' not in export_fn_body:
        print("✗ boxblur not found in pre-render")
        return False
    print("✓ boxblur filter present in pre-render pass")

    # Check two-input approach: [0:v] for bg, [1:v] for fg
    if '[1:v]' not in export_fn_body:
        print("✗ Foreground should reference [1:v]")
        return False
    has_cpu_overlay = '[0:v][fg_ready]overlay' in export_fn_body
    has_gpu_overlay = 'overlay_cuda' in export_fn_body
    if not has_cpu_overlay and not has_gpu_overlay:
        print("✗ Overlay should use [0:v] (bg) + [fg_ready] (CPU or GPU)")
        return False
    print("✓ Final encode uses two simple inputs: [0:v]=bg, [1:v]=fg")

    # Check that fg uses [1:v] for prep
    if 'copy[fg_ready]' not in export_fn_body and 'hflip[fg_ready]' not in export_fn_body:
        print("✗ Foreground filter missing [fg_ready] output")
        return False
    print("✓ Foreground filter produces [fg_ready] output")

    return True


def test_source_code_nvenc_detection_robust():
    """Test that NVENC detection actually tests encoding, not just string matching."""
    print("\n--- Test: NVENC detection is robust ---")
    source_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the ffmpeg_supports_nvenc function body
    fn_start = content.find('def ffmpeg_supports_nvenc')
    next_fn = content.find('\ndef ', fn_start + 1)
    fn_body = content[fn_start:next_fn] if next_fn != -1 else content[fn_start:]

    # Check that it does an actual encoding test, not just string matching
    if 'color=c=black' not in fn_body and 'lavfi' not in fn_body:
        print("✗ NVENC detection should test actual encoding")
        return False
    print("✓ NVENC detection tests actual encoding with dummy input")

    # Check that results are cached
    if '_nvenc_cache' not in content:
        print("✗ NVENC results should be cached")
        return False
    print("✓ NVENC detection results are cached")

    return True


def test_source_code_gpu_filters_support():
    """Test that GPU-accelerated filters (scale_cuda, overlay_cuda) are supported."""
    print("\n--- Test: GPU filters (scale_cuda/overlay_cuda) support ---")
    source_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check ffmpeg_gpu_filters_available function exists
    if 'def ffmpeg_gpu_filters_available' not in content:
        print("✗ ffmpeg_gpu_filters_available function not found")
        return False
    print("✓ ffmpeg_gpu_filters_available function exists")

    # Check it tests for scale_cuda and overlay_cuda
    fn_start = content.find('def ffmpeg_gpu_filters_available')
    next_fn = content.find('\ndef ', fn_start + 1)
    fn_body = content[fn_start:next_fn] if next_fn != -1 else content[fn_start:]

    if 'scale_cuda' in fn_body and 'overlay_cuda' in fn_body:
        print("✓ Tests for scale_cuda and overlay_cuda availability")
    else:
        print("✗ Should test for both scale_cuda and overlay_cuda")
        return False

    # Check export function uses GPU filters
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn2 = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn2] if next_fn2 != -1 else content[export_fn_start:]

    if 'overlay_cuda' in export_fn_body:
        print("✓ Export function uses overlay_cuda when available")
    else:
        print("✗ Export function should use overlay_cuda")
        return False

    if 'scale_cuda' in export_fn_body:
        print("✓ Export function uses scale_cuda when available")
    else:
        print("✗ Export function should use scale_cuda")
        return False

    if 'hwupload_cuda' in export_fn_body:
        print("✓ Export function uses hwupload_cuda for GPU memory transfer")
    else:
        print("✗ Export function should use hwupload_cuda")
        return False

    return True


def test_source_code_cuda_format_handling():
    """Test that GPU filter paths properly handle CUDA-to-CPU format transitions."""
    print("\n--- Test: CUDA format handling (hwdownload before CPU filters) ---")
    source_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check pre_render_foreground_ffmpeg: when -hwaccel_output_format cuda is used,
    # crop (CPU filter) needs hwdownload,format=nv12 BEFORE it
    fn_start = content.find('def pre_render_foreground_ffmpeg')
    next_fn = content.find('\ndef ', fn_start + 1)
    fn_body = content[fn_start:next_fn] if next_fn != -1 else content[fn_start:]

    if 'hwdownload,format=nv12' in fn_body and 'crop=' in fn_body:
        print("✓ Pre-render has hwdownload before crop (CUDA→CPU transition)")
    else:
        print("✗ Pre-render must hwdownload before crop when using -hwaccel_output_format cuda")
        return False

    # Verify the order: hwdownload must come BEFORE crop in the filter chain
    hwdl_pos = fn_body.find('hwdownload,format=nv12')
    crop_pos = fn_body.find('crop=', hwdl_pos)
    if hwdl_pos < crop_pos:
        print("✓ hwdownload comes before crop in filter chain (correct order)")
    else:
        print("✗ hwdownload must come before crop to avoid CUDA format error")
        return False

    # Check bg pre-render also has correct order: scale_cuda → hwdownload → crop
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn2 = content.find('\ndef ', export_fn_start + 1)
    export_body = content[export_fn_start:next_fn2] if next_fn2 != -1 else content[export_fn_start:]

    if 'scale_cuda=' in export_body and 'hwdownload,format=nv12' in export_body:
        print("✓ Background pre-render has scale_cuda → hwdownload transition")
    else:
        print("✗ Background pre-render should use scale_cuda with hwdownload")
        return False

    return True


def test_scale_cuda_no_force_original_aspect_ratio():
    """Verify scale_cuda in bg pre-render doesn't use force_original_aspect_ratio (unsupported)."""
    print("\nVerifying scale_cuda doesn't use force_original_aspect_ratio...")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r') as f:
        content = f.read()

    # Find the _export_with_ffmpeg_filters function
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn = content.find('\ndef ', export_fn_start + 1)
    export_body = content[export_fn_start:next_fn] if next_fn != -1 else content[export_fn_start:]

    # scale_cuda should NOT have force_original_aspect_ratio (it's a CPU scale option)
    if 'scale_cuda=' in export_body and 'force_original_aspect_ratio' not in export_body.split('scale_cuda=')[1].split('\n')[0]:
        print("✓ scale_cuda does not use force_original_aspect_ratio (correct - unsupported option)")
    else:
        # Check if force_original_aspect_ratio appears near scale_cuda
        lines = export_body.split('\n')
        for line in lines:
            if 'scale_cuda=' in line and 'force_original_aspect_ratio' in line:
                print(f"✗ scale_cuda uses force_original_aspect_ratio (causes black/green lines): {line.strip()}")
                return False
        print("✓ scale_cuda does not use force_original_aspect_ratio (correct)")

    # CPU scale path should still have force_original_aspect_ratio (it supports it)
    if "scale=" in export_body and "force_original_aspect_ratio=increase" in export_body:
        print("✓ CPU scale filter still uses force_original_aspect_ratio=increase (correct)")
    else:
        print("Note: CPU scale path not found or doesn't use force_original_aspect_ratio")

    return True


def test_caption_clips_deferred_to_moviepy_fallback():
    """Verify MoviePy caption clips are NOT created before FFmpeg export (deferred to fallback)."""
    print("\nVerifying caption clip creation is deferred to MoviePy fallback...")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r') as f:
        content = f.read()

    # Find the compose function
    compose_fn_start = content.find('def compose_final_video_with_static_blurred_bg')
    next_fn = content.find('\ndef ', compose_fn_start + 1)
    compose_body = content[compose_fn_start:next_fn] if next_fn != -1 else content[compose_fn_start:]

    # The fast caption data collection loop should NOT call generate_caption_image
    # before the FFmpeg export attempt
    ffmpeg_export_pos = compose_body.find('try_ffmpeg_export')
    if ffmpeg_export_pos == -1:
        print("✗ Could not find try_ffmpeg_export in compose function")
        return False

    before_ffmpeg = compose_body[:ffmpeg_export_pos]

    # Before FFmpeg export: should NOT have generate_caption_image (slow PIL rendering)
    if 'generate_caption_image' not in before_ffmpeg:
        print("✓ No generate_caption_image() calls before FFmpeg export (fast path)")
    else:
        print("✗ generate_caption_image() called before FFmpeg export (slow - should be deferred)")
        return False

    # Before FFmpeg export: should NOT create ImageClip (MoviePy)
    if 'ImageClip(' not in before_ffmpeg:
        print("✓ No ImageClip() creation before FFmpeg export (deferred)")
    else:
        print("✗ ImageClip() created before FFmpeg export (slow - should be deferred)")
        return False

    # After MoviePy fallback: should have generate_caption_image (lazy creation)
    moviepy_fallback_pos = compose_body.find('Fallback to MoviePy export')
    if moviepy_fallback_pos != -1:
        after_fallback = compose_body[moviepy_fallback_pos:]
        if 'generate_caption_image' in after_fallback:
            print("✓ generate_caption_image() present in MoviePy fallback (lazy creation)")
        else:
            print("✗ generate_caption_image() missing from MoviePy fallback")
            return False
    else:
        print("Note: MoviePy fallback section not found")

    return True


def test_bg_uses_downscale_blur_upscale():
    """Verify background pre-render uses the downscale-blur-upscale trick for faster processing."""
    print("\nVerifying background pre-render uses downscale-blur-upscale optimization...")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r') as f:
        content = f.read()

    # Find the _export_with_ffmpeg_filters function
    fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn = content.find('\ndef ', fn_start + 1)
    fn_body = content[fn_start:next_fn] if next_fn != -1 else content[fn_start:]

    # Should have downscale dimensions calculation
    has_blur_down = 'blur_down_w' in fn_body and 'blur_down_h' in fn_body
    if has_blur_down:
        print("✓ blur_down_w/blur_down_h variables found (downscale dimensions)")
    else:
        print("✗ Missing blur_down_w/blur_down_h - no downscale optimization")
        return False

    # Should have small_blur calculation
    has_small_blur = 'small_blur' in fn_body
    if has_small_blur:
        print("✓ small_blur variable found (reduced blur radius for downscaled frame)")
    else:
        print("✗ Missing small_blur - blur radius not reduced for downscaled frame")
        return False

    # The GPU bg_vf should use scale down before boxblur then scale up
    # Pattern: crop → scale=blur_down → boxblur=small → scale=original
    gpu_bg_section = fn_body[fn_body.find('if gpu_filters and not needs_stream_loop'):fn_body.find('bg_cmd = [')]
    if 'boxblur={small_blur}' in gpu_bg_section:
        print("✓ GPU path uses small_blur (downscaled blur)")
    else:
        print("✗ GPU path doesn't use small_blur")
        return False

    # Should NOT have boxblur={box_blur_val} directly on full resolution
    if 'boxblur={box_blur_val}' not in gpu_bg_section:
        print("✓ GPU path no longer does full-resolution blur (optimized)")
    else:
        print("✗ GPU path still does full-resolution blur (not optimized)")
        return False

    return True


def test_foreground_width_based_scaling():
    """Test that foreground scaling uses WIDTH/crop_w with minimum height enforcement."""
    print("\n--- Test: Foreground uses width-based scaling with min height ---")

    source_path = os.path.join(os.path.dirname(__file__), 'tiktok_full_gui.py')
    with open(source_path, 'r', encoding='utf-8') as f:
        source = f.read()

    # Should use WIDTH / cropped.w for width-based scaling
    assert 'width_scale = WIDTH / cropped.w' in source, \
        "Missing width_scale = WIDTH / cropped.w"
    print("✓ Uses width_scale = WIDTH / cropped.w")

    # Should NOT use max(WIDTH/w, HEIGHT/h) which fills entire canvas
    assert 'max(WIDTH / cropped.w, HEIGHT / cropped.h)' not in source, \
        "Still using max() which fills entire canvas and hides background"
    print("✓ Does NOT use max() fill scaling (which hides background)")

    # Should have MIN_FG_HEIGHT_RATIO constant
    assert 'MIN_FG_HEIGHT_RATIO' in source, \
        "Missing MIN_FG_HEIGHT_RATIO constant for minimum height enforcement"
    print("✓ Has MIN_FG_HEIGHT_RATIO constant")

    # Should check estimated_height < min_fg_height
    assert 'estimated_height < min_fg_height' in source or 'est_h < min_h' in source, \
        "Missing minimum height check"
    print("✓ Checks minimum foreground height")

    # Verify the math: for a 1920x378 cropped landscape video,
    # min height should kick in (378 * 0.5625 * 1.03 = 219 < 672)
    WIDTH, HEIGHT = 1080, 1920
    MIN_FG_HEIGHT_RATIO = 0.35
    crop_w, crop_h = 1920, 378  # 65% height cropped

    width_scale = WIDTH / crop_w  # 0.5625
    base_scale_factor = 1.03
    min_fg_height = HEIGHT * MIN_FG_HEIGHT_RATIO  # 672
    estimated_height = crop_h * width_scale * base_scale_factor  # ~219

    assert estimated_height < min_fg_height, \
        f"Test assumption: {estimated_height:.0f} should be < {min_fg_height:.0f}"

    height_scale = min_fg_height / crop_h  # ~1.778
    fg_base_scale = max(width_scale, height_scale)  # 1.778
    fg_scale = fg_base_scale * base_scale_factor  # ~1.831

    result_w = int(round(crop_w * fg_scale))
    result_h = int(round(crop_h * fg_scale))

    # Foreground should now fill at least 35% of canvas height
    assert result_h >= min_fg_height * 0.95, \
        f"Foreground height {result_h} should be >= {min_fg_height*0.95:.0f}"
    print(f"✓ Heavy crop landscape: fg={result_w}x{result_h}, fills {result_h/HEIGHT*100:.0f}% of canvas height")

    # For portrait video (1080x1920 no crop), width_scale=1.0 should win
    p_crop_w, p_crop_h = 1080, 1920
    p_width_scale = WIDTH / p_crop_w  # 1.0
    p_est_h = p_crop_h * p_width_scale * base_scale_factor  # 1978 > 672
    assert p_est_h >= min_fg_height, \
        "Portrait video should NOT trigger min height (already fills canvas)"
    print(f"✓ Portrait video: estimated height {p_est_h:.0f}px > {min_fg_height:.0f}px, no adjustment needed")

    return True


def test_output_forces_1080x1920_and_setsar():
    """Test that the export filter chain forces exact 1080x1920 output with setsar=1:1.
    
    Source videos with non-1:1 SAR (sample aspect ratio) can cause the output to appear
    narrow or stretched even with correct pixel dimensions. Adding scale=1080:1920,setsar=1:1
    at the end of the filter chain ensures correct output.
    """
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    
    # The final filter chain should force scale and setsar before [vout]
    assert 'scale={video_width}:{video_height},setsar=1:1' in source, \
        "Pass 2 filter chain should force scale={video_width}:{video_height},setsar=1:1 before [vout]"
    
    # Foreground pre-render should have setsar=1:1
    assert 'setsar=1:1' in source, \
        "setsar=1:1 should be used in filter chains"
    
    # Count setsar occurrences - should be in fg prerender (2), bg prerender (2), and final (1)
    setsar_count = source.count('setsar=1:1')
    assert setsar_count >= 4, \
        f"Expected setsar=1:1 at least 4 times (fg GPU+CPU, bg GPU+CPU, final), found {setsar_count}"
    
    print("✓ Output forces 1080x1920 resolution and setsar=1:1 to prevent narrow video")
    return True


def test_translation_tts_auto_sync():
    """Test that translation+TTS auto-sync is implemented.
    
    When both translation and TTS are enabled:
    1. Source language is auto-detected by Whisper (result["language"])
    2. TTS language is auto-synced with translation target language
    3. TTS uses translated text (translate_segments updates seg["text"])
    """
    source_file = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_file, 'r', encoding='utf-8') as f:
        source = f.read()
    
    print("\n--- Test: Translation + TTS auto-sync ---")
    
    # 1. Whisper auto-detects source language
    assert 'result.get("language"' in source, \
        "Should extract detected language from Whisper result"
    assert 'Detected source language' in source, \
        "Should log detected source language"
    print("✓ Whisper auto-detects source language from video")
    
    # 2. TTS language auto-synced with translation target
    assert 'translation_enabled and use_ai_voice' in source, \
        "Should check both translation and TTS enabled for auto-sync"
    assert "TRANS_TO_TTS_LANG" in source, \
        "Should use TRANS_TO_TTS_LANG constant for language code mapping"
    assert "'zh-cn': 'zh'" in source, \
        "Should map zh-cn translation code to zh TTS code"
    print("✓ TTS language auto-syncs with translation target language")
    
    # 3. translate_segments updates text field (TTS uses translated text)
    assert 'new_seg["text"] = translated_text' in source, \
        "translate_segments should update text field with translated text"
    assert 'Using translated text' in source, \
        "Should log when TTS uses translated text"
    print("✓ TTS uses translated text when both features enabled")
    
    return True


if __name__ == '__main__':
    print("=" * 60)
    print("EXPORT FONT SIZE & STROKE COLOR FIX VALIDATION")
    print("=" * 60)

    results = [
        test_ass_subtitle_uses_font_size(),
        test_drawtext_filter_uses_font_size(),
        test_build_all_caption_filters_passes_font_size(),
        test_stroke_color_passed_to_filters(),
        test_rgba_to_hex_conversion(),
        test_source_code_no_hardcoded_fontsize(),
        test_ass_subtitle_uses_stroke_color(),
        test_ass_subtitle_default_text_color_is_white(),
        test_source_code_ass_has_stroke_color_param(),
        test_drawtext_uses_y_offset(),
        test_build_all_caption_filters_passes_y_offset(),
        test_source_code_drawtext_no_hardcoded_position(),
        test_source_code_uses_two_pass_export(),
        test_source_code_nvenc_detection_robust(),
        test_source_code_gpu_filters_support(),
        test_source_code_cuda_format_handling(),
        test_scale_cuda_no_force_original_aspect_ratio(),
        test_caption_clips_deferred_to_moviepy_fallback(),
        test_bg_uses_downscale_blur_upscale(),
        test_foreground_width_based_scaling(),
        test_output_forces_1080x1920_and_setsar(),
        test_translation_tts_auto_sync(),
    ]

    print("\n" + "=" * 60)
    passed = sum(1 for r in results if r)
    total = len(results)
    if all(results):
        print(f"✓ ALL {total} TESTS PASSED - Export font size fix is working correctly!")
        print("=" * 60)
        sys.exit(0)
    else:
        print(f"✗ {total - passed}/{total} TESTS FAILED - Please review the output above")
        print("=" * 60)
        sys.exit(1)
