"""Tests for 4K font size limits and spot blur background fix."""
import sys, types, importlib, os, re

# ── Bootstrap: stub heavy deps so tiktok_full_gui imports quickly ──────────
for mod_name in [
    "tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox",
    "tkinter.font", "tkinter.scrolledtext",
    "PIL", "PIL.Image", "PIL.ImageTk", "PIL.ImageDraw", "PIL.ImageFont",
    "PIL.ImageFilter",
]:
    if mod_name not in sys.modules:
        sys.modules[mod_name] = types.ModuleType(mod_name)

_scrolledtext = sys.modules["tkinter.scrolledtext"]
if not hasattr(_scrolledtext, 'ScrolledText'):
    setattr(_scrolledtext, 'ScrolledText', type('ScrolledText', (), {"__init__": lambda *a, **kw: None}))

_tk = sys.modules["tkinter"]
for attr in [
    "Tk", "Toplevel", "Frame", "Label", "Entry", "Button", "Scale",
    "Scrollbar", "Canvas", "Checkbutton", "Spinbox", "OptionMenu",
    "Menu", "LabelFrame", "Text", "PhotoImage", "StringVar", "IntVar",
    "DoubleVar", "BooleanVar", "END", "HORIZONTAL", "VERTICAL",
    "LEFT", "RIGHT", "TOP", "BOTTOM", "BOTH", "X", "Y", "W", "E",
    "N", "S", "NW", "NE", "SW", "SE", "CENTER", "NORMAL", "DISABLED",
    "WORD", "NONE", "filedialog", "messagebox", "scrolledtext",
    "GROOVE", "SUNKEN", "RAISED", "FLAT", "RIDGE",
]:
    if not hasattr(_tk, attr):
        setattr(_tk, attr, type(attr, (), {"__init__": lambda *a, **kw: None}))

_ttk = sys.modules["tkinter.ttk"]
for attr in ["Frame", "Label", "Button", "Combobox", "Notebook", "Style",
             "Scrollbar", "Entry", "Checkbutton", "Separator",
             "LabelFrame", "Scale", "Progressbar"]:
    if not hasattr(_ttk, attr):
        setattr(_ttk, attr, type(attr, (), {"__init__": lambda *a, **kw: None}))

# ── Ensure repo root on path ──────────────────────────────────────────────
REPO = os.path.dirname(os.path.abspath(__file__))
if REPO not in sys.path:
    sys.path.insert(0, REPO)


def _load_source():
    """Read tiktok_full_gui.py source and return it as text."""
    with open(os.path.join(REPO, "tiktok_full_gui.py"), "r", encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════════════════════════
# 4K Font Size Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_4k_slider_max_is_800():
    """4K mode should set font size slider max to 800."""
    src = _load_source()
    # Find the 4K slider config line
    match = re.search(r'caption_font_size_scale\.config\(from_=40,\s*to=(\d+)\)', src)
    assert match, "Could not find 4K slider config"
    assert int(match.group(1)) == 800, f"4K slider max should be 800, got {match.group(1)}"


def test_hd_slider_max_is_120():
    """HD mode should set font size slider max to 120."""
    src = _load_source()
    match = re.search(r'caption_font_size_scale\.config\(from_=20,\s*to=(\d+)\)', src)
    assert match, "Could not find HD slider config"
    assert int(match.group(1)) == 120, f"HD slider max should be 120, got {match.group(1)}"


def test_4k_clamp_max_is_800():
    """Clamping logic in on_caption_font_size_changed should use 800 for 4K."""
    src = _load_source()
    match = re.search(r'max_size\s*=\s*(\d+)\s+if\s+globals', src)
    assert match, "Could not find max_size clamping line"
    assert int(match.group(1)) == 800, f"4K clamp max should be 800, got {match.group(1)}"


def test_no_duplicate_on_caption_font_size_changed():
    """There should be exactly one on_caption_font_size_changed method."""
    src = _load_source()
    count = len(re.findall(r'def on_caption_font_size_changed\(', src))
    assert count == 1, f"Expected 1 on_caption_font_size_changed, found {count}"


def test_no_hardcoded_hd_clamp():
    """No hardcoded max(20, min(120, size)) clamping that ignores 4K mode."""
    src = _load_source()
    # Look for HD-only clamping pattern like: size = max(20, min(120, size))
    # This should NOT exist - clamping should be dynamic based on IS_4K_MODE
    matches = re.findall(r'size\s*=\s*max\(20,\s*min\(120,\s*size\)\)', src)
    assert len(matches) == 0, (
        f"Found {len(matches)} hardcoded HD-only clamp(s). "
        "Clamping should use IS_4K_MODE to determine max."
    )


def test_4k_font_size_range_allows_large_values():
    """Font sizes up to 800 should be valid in 4K mode."""
    # Simulate 4K mode clamping logic
    is_4k = True
    max_size = 800 if is_4k else 120
    min_size = 40 if is_4k else 20

    # Test that 800 is within valid range
    test_size = 800
    clamped = max(min_size, min(max_size, test_size))
    assert clamped == 800, f"800 should be valid in 4K, got {clamped}"

    # Test that 600 is within valid range
    test_size = 600
    clamped = max(min_size, min(max_size, test_size))
    assert clamped == 600, f"600 should be valid in 4K, got {clamped}"


def test_hd_font_size_clamps_at_120():
    """Font sizes should be clamped to 120 in HD mode."""
    is_4k = False
    max_size = 800 if is_4k else 120
    min_size = 40 if is_4k else 20

    test_size = 200
    clamped = max(min_size, min(max_size, test_size))
    assert clamped == 120, f"200 should be clamped to 120 in HD, got {clamped}"


# ═══════════════════════════════════════════════════════════════════════════
# Spot Blur Background Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_no_spot_blur_on_background():
    """Background should not have spot blur applied (it's already fully blurred)."""
    src = _load_source()
    # The background spot blur block should be disabled
    # There should NOT be a split/crop/boxblur/overlay for _bgm/_bgc/_bgb
    assert '[_bgm]' not in src, "Background spot blur stream labels [_bgm] should be removed"
    assert '[_bgc]' not in src, "Background spot blur stream labels [_bgc] should be removed"
    assert '[_bgb]' not in src, "Background spot blur stream labels [_bgb] should be removed"


def test_bg_spot_blur_always_empty():
    """bg_spot_blur variable should always be empty string."""
    src = _load_source()
    # Find all assignments to bg_spot_blur - should only be empty string
    assignments = re.findall(r'bg_spot_blur\s*=\s*(.+)', src)
    assert len(assignments) >= 1, "Should have at least one bg_spot_blur assignment"
    for assign in assignments:
        # Should be either "" or empty - not a filter string
        stripped = assign.strip().rstrip(')')
        assert stripped == '""' or stripped == "''", (
            f"bg_spot_blur should always be empty, found: {assign}"
        )


def test_background_still_uses_boxblur():
    """Background should still have the main boxblur filter (just no spot blur)."""
    src = _load_source()
    # The background pre-render should still have boxblur for the full blur effect
    assert re.search(r'boxblur=', src), \
        "Background should still have boxblur filter for full blur"
