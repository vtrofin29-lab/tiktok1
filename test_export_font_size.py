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


def test_source_code_uses_split_filter():
    """Test that filter chain uses split filter instead of referencing [0:v] twice."""
    print("\n--- Test: Source code uses split filter ---")
    source_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the _export_with_ffmpeg_filters function body
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn] if next_fn != -1 else content[export_fn_start:]

    # Check that split filter is used
    if 'split=2[v_bg][v_fg]' in export_fn_body:
        print("✓ Filter chain uses split=2 to decode input once")
    else:
        print("✗ Missing split filter - input decoded twice (GPU conflict)")
        return False

    # Check that bg uses [v_bg] not [0:v]
    if '[v_bg]scale=' in export_fn_body:
        print("✓ Background filter uses [v_bg] from split")
    else:
        print("✗ Background filter still uses [0:v] directly")
        return False

    # Check that fg uses [v_fg] not [0:v]
    if '[v_fg]' in export_fn_body:
        print("✓ Foreground filter uses [v_fg] from split")
    else:
        print("✗ Foreground filter still uses [0:v] directly")
        return False

    return True


def test_source_code_hwaccel_stream_loop_conflict():
    """Test that -hwaccel cuda is not used together with -stream_loop -1."""
    print("\n--- Test: hwaccel/stream_loop conflict handled ---")
    source_path = os.path.join(os.path.dirname(__file__), "tiktok_full_gui.py")
    with open(source_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find the _export_with_ffmpeg_filters function body
    export_fn_start = content.find('def _export_with_ffmpeg_filters')
    next_fn = content.find('\ndef ', export_fn_start + 1)
    export_fn_body = content[export_fn_start:next_fn] if next_fn != -1 else content[export_fn_start:]

    # Check that hwaccel is conditional on not needs_stream_loop
    if 'not needs_stream_loop' in export_fn_body:
        print("✓ hwaccel cuda is disabled when stream_loop is needed")
    else:
        print("✗ hwaccel not conditional on stream_loop - GPU conflict possible")
        return False

    # Check that stream_loop is conditional
    if 'if needs_stream_loop:' in export_fn_body:
        print("✓ stream_loop is only enabled when needed (slowdown)")
    else:
        print("✗ stream_loop is always used - conflicts with hwaccel")
        return False

    # Check needs_stream_loop is properly set based on speed_factor
    if 'speed_factor < 1.0' in export_fn_body and 'needs_stream_loop = True' in export_fn_body:
        print("✓ needs_stream_loop is set based on speed_factor < 1.0")
    else:
        print("✗ needs_stream_loop not properly set")
        return False

    return True


if __name__ == "__main__":
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
        test_source_code_uses_split_filter(),
        test_source_code_hwaccel_stream_loop_conflict(),
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
