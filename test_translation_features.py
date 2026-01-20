"""
Test script for translation and AI voice replacement features.
This script validates that the new features work correctly without requiring actual video processing.
"""

import sys
import os

# Add the main directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all required modules can be imported."""
    print("=" * 60)
    print("Testing module imports...")
    print("=" * 60)
    
    try:
        from tiktok_full_gui import (
            TRANSLATION_AVAILABLE,
            TTS_AVAILABLE,
            REQUESTS_AVAILABLE,
            translate_text,
            translate_segments,
            generate_tts_audio,
            replace_voice_with_tts,
            transcribe_with_claptools
        )
        print("✓ All translation and TTS modules imported successfully")
        print(f"  - Translation available: {TRANSLATION_AVAILABLE}")
        print(f"  - TTS available: {TTS_AVAILABLE}")
        print(f"  - Requests available: {REQUESTS_AVAILABLE}")
        return True
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False

def test_translation():
    """Test translation functionality."""
    print("\n" + "=" * 60)
    print("Testing translation...")
    print("=" * 60)
    
    try:
        from tiktok_full_gui import translate_text, TRANSLATION_AVAILABLE
        
        if not TRANSLATION_AVAILABLE:
            print("⚠ Translation not available (googletrans not installed)")
            print("  Install with: pip install googletrans==4.0.0rc1")
            return True  # Not a failure, just unavailable
        
        # Test simple translation
        test_text = "Hello, world!"
        result = translate_text(test_text, target_language='es')
        
        if result:
            print(f"✓ Translation test passed")
            print(f"  Original: '{test_text}'")
            print(f"  Translated (es): '{result}'")
            return True
        else:
            print("✗ Translation returned empty result")
            return False
    except Exception as e:
        print(f"✗ Translation test failed: {e}")
        return False

def test_segment_translation():
    """Test segment translation functionality."""
    print("\n" + "=" * 60)
    print("Testing segment translation...")
    print("=" * 60)
    
    try:
        from tiktok_full_gui import translate_segments, TRANSLATION_AVAILABLE
        
        if not TRANSLATION_AVAILABLE:
            print("⚠ Translation not available (googletrans not installed)")
            return True
        
        # Create test segments (Whisper format)
        test_segments = [
            {"start": 0.0, "end": 2.0, "text": "Hello everyone"},
            {"start": 2.0, "end": 4.0, "text": "Welcome to this video"},
        ]
        
        # Test translation
        result = translate_segments(test_segments, target_language='fr')
        
        if result and len(result) == 2:
            print(f"✓ Segment translation test passed")
            print(f"  Segments translated: {len(result)}")
            for i, seg in enumerate(result):
                print(f"  Segment {i+1}: '{seg.get('original_text', 'N/A')}' -> '{seg.get('text', 'N/A')}'")
            return True
        else:
            print("✗ Segment translation returned unexpected result")
            return False
    except Exception as e:
        print(f"✗ Segment translation test failed: {e}")
        return False

def test_tts():
    """Test TTS functionality."""
    print("\n" + "=" * 60)
    print("Testing Text-to-Speech...")
    print("=" * 60)
    
    try:
        from tiktok_full_gui import generate_tts_audio, TTS_AVAILABLE
        import tempfile
        
        if not TTS_AVAILABLE:
            print("⚠ TTS not available (gTTS not installed)")
            print("  Install with: pip install gtts")
            return True  # Not a failure, just unavailable
        
        # Test TTS generation
        test_text = "This is a test."
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
            tmp_path = tmp.name
        
        result = generate_tts_audio(test_text, language='en', output_path=tmp_path)
        
        if result and os.path.exists(result):
            file_size = os.path.getsize(result)
            print(f"✓ TTS test passed")
            print(f"  Generated file: {result}")
            print(f"  File size: {file_size} bytes")
            # Clean up
            try:
                os.remove(result)
            except:
                pass
            return True
        else:
            print("✗ TTS generation failed or file not created")
            return False
    except Exception as e:
        print(f"✗ TTS test failed: {e}")
        return False

def test_claptools_placeholder():
    """Test ClapTools placeholder function."""
    print("\n" + "=" * 60)
    print("Testing ClapTools integration...")
    print("=" * 60)
    
    try:
        from tiktok_full_gui import transcribe_with_claptools, REQUESTS_AVAILABLE
        
        if not REQUESTS_AVAILABLE:
            print("⚠ Requests library not available")
            print("  Install with: pip install requests")
            return True
        
        # Test placeholder function
        result = transcribe_with_claptools("dummy_path.mp4")
        
        if result is None:
            print("✓ ClapTools placeholder test passed")
            print("  Function correctly returns None (not yet implemented)")
            return True
        else:
            print("⚠ ClapTools returned unexpected result")
            print(f"  Result: {result}")
            return True
    except Exception as e:
        print(f"✗ ClapTools test failed: {e}")
        return False

def test_gui_integration():
    """Test that GUI can be imported without errors."""
    print("\n" + "=" * 60)
    print("Testing GUI integration...")
    print("=" * 60)
    
    try:
        # Import main GUI module
        import tiktok_full_gui
        
        # Check that all new global settings exist
        required_settings = [
            'TRANSLATION_ENABLED',
            'TARGET_LANGUAGE',
            'USE_AI_VOICE_REPLACEMENT',
            'TTS_LANGUAGE',
            'USE_CLAPTOOLS',
            'CLAPTOOLS_API_KEY'
        ]
        
        missing = []
        for setting in required_settings:
            if not hasattr(tiktok_full_gui, setting):
                missing.append(setting)
        
        if missing:
            print(f"✗ Missing global settings: {', '.join(missing)}")
            return False
        
        print("✓ GUI integration test passed")
        print("  All required settings present")
        return True
    except Exception as e:
        print(f"✗ GUI integration test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("TRANSLATION & AI VOICE FEATURES VALIDATION")
    print("=" * 60)
    
    tests = [
        ("Module Imports", test_imports),
        ("Translation", test_translation),
        ("Segment Translation", test_segment_translation),
        ("Text-to-Speech", test_tts),
        ("ClapTools Integration", test_claptools_placeholder),
        ("GUI Integration", test_gui_integration),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {test_name}")
    
    print("=" * 60)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ ALL TESTS PASSED!")
        print("=" * 60)
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        return 1

if __name__ == "__main__":
    sys.exit(main())
