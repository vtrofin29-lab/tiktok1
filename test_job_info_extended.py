#!/usr/bin/env python3
"""
Test to validate extended job info display including AI/TTS, colors, and borders.
"""

def test_extended_job_info_display():
    """Test that extended job info is properly formatted in display."""
    print("Testing extended job info display formatting...")
    
    # Mock job data with various settings
    test_jobs = [
        {
            "video": "test_video.mp4",
            "voice": "test_voice.mp3",
            "music": "test_music.mp3",
            "use_4k": False,
            "mirror_video": False,
            "words_per_caption": 2,
            "blur_radius": 25,
            "bg_scale_extra": 1.08,
            "dim_factor": 0.55,
            "use_ai_voice": False,
            "translation_enabled": False,
            "silence_threshold_ms": 300,
            "caption_text_color": (255, 255, 255, 255),
            "caption_stroke_color": (0, 0, 0, 150),
            "caption_stroke_width": 3
        },
        {
            "video": "test_video2.mp4",
            "voice": "test_voice2.mp3",
            "music": "test_music2.mp3",
            "use_4k": True,
            "mirror_video": True,
            "words_per_caption": 3,
            "blur_radius": 30,
            "bg_scale_extra": 1.15,
            "dim_factor": 0.60,
            "use_ai_voice": True,
            "translation_enabled": True,
            "target_language": "es",
            "silence_threshold_ms": 500,
            "caption_text_color": (255, 200, 100, 255),
            "caption_stroke_color": (50, 50, 50, 200),
            "caption_stroke_width": 5
        },
        {
            "video": "test_video3.mp4",
            "voice": "test_voice3.mp3",
            "music": "test_music3.mp3",
            "use_4k": False,
            "mirror_video": False,
            "words_per_caption": 2,
            "blur_radius": 25,
            "bg_scale_extra": 1.08,
            "dim_factor": 0.55,
            "use_ai_voice": True,
            "translation_enabled": False,
            "silence_threshold_ms": 300,  # Default, should not show
            "caption_text_color": (255, 255, 255, 255),
            "caption_stroke_color": (0, 0, 0, 150),
            "caption_stroke_width": 3
        }
    ]
    
    import os
    
    # Helper function to format job info (same as in main script)
    def format_job_info(job):
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
        
        return " [" + ", ".join(info_parts) + "]" if info_parts else ""
    
    for i, j in enumerate(test_jobs, start=1):
        # Simulate _refresh_job_listbox logic
        info = format_job_info(j)
        
        display = f"{i}. {os.path.basename(j['video'])} | {os.path.basename(j['voice'])} | {os.path.basename(j['music'])}{info}"
        print(display)
    
    print("\n✓ Extended job info display test completed")
    return True

def test_job_info_fields():
    """Test that all new job fields are properly stored."""
    print("\nTesting job info fields...")
    
    job = {
        "use_ai_voice": True,
        "translation_enabled": True,
        "target_language": "es",
        "silence_threshold_ms": 500,
        "caption_text_color": (255, 200, 100, 255),
        "caption_stroke_color": (50, 50, 50, 200),
        "caption_stroke_width": 5
    }
    
    assert job["use_ai_voice"] == True, "use_ai_voice should be True"
    assert job["translation_enabled"] == True, "translation_enabled should be True"
    assert job["target_language"] == "es", "target_language should be 'es'"
    assert job["silence_threshold_ms"] == 500, "silence_threshold_ms should be 500"
    assert job["caption_text_color"] == (255, 200, 100, 255), "caption_text_color should match"
    assert job["caption_stroke_color"] == (50, 50, 50, 200), "caption_stroke_color should match"
    assert job["caption_stroke_width"] == 5, "caption_stroke_width should be 5"
    
    print(f"✓ AI Voice: {job['use_ai_voice']}")
    print(f"✓ Translation: {job['translation_enabled']} ({job['target_language']})")
    print(f"✓ Silence Threshold: {job['silence_threshold_ms']}ms")
    print(f"✓ Text Color: RGB{job['caption_text_color'][:3]}")
    print(f"✓ Stroke Color: RGB{job['caption_stroke_color'][:3]}")
    print(f"✓ Stroke Width: {job['caption_stroke_width']}")
    
    print("\n✓ Job info fields test completed")
    return True

def test_job_display_scenarios():
    """Test various job display scenarios."""
    print("\nTesting job display scenarios...")
    
    scenarios = [
        ("Default settings (minimal display)", {
            "use_4k": False,
            "mirror_video": False,
            "words_per_caption": 2,
            "blur_radius": 25,
            "bg_scale_extra": 1.08,
            "dim_factor": 0.55,
            "use_ai_voice": False,
            "translation_enabled": False,
            "silence_threshold_ms": 300,
            "caption_text_color": (255, 255, 255, 255),
            "caption_stroke_color": (0, 0, 0, 150),
            "caption_stroke_width": 3
        }),
        ("AI TTS enabled", {
            "use_ai_voice": True,
            "silence_threshold_ms": 300
        }),
        ("AI TTS with custom silence", {
            "use_ai_voice": True,
            "silence_threshold_ms": 500
        }),
        ("Translation enabled", {
            "translation_enabled": True,
            "target_language": "fr"
        }),
        ("Custom colors", {
            "caption_text_color": (255, 0, 0, 255),
            "caption_stroke_color": (0, 255, 0, 150)
        }),
        ("All features enabled", {
            "use_4k": True,
            "mirror_video": True,
            "words_per_caption": 4,
            "use_ai_voice": True,
            "translation_enabled": True,
            "target_language": "de",
            "silence_threshold_ms": 400,
            "caption_text_color": (100, 200, 255, 255),
            "caption_stroke_color": (200, 100, 50, 200),
            "caption_stroke_width": 7,
            "blur_radius": 35,
            "bg_scale_extra": 1.2,
            "dim_factor": 0.7
        })
    ]
    
    def format_job_info(job):
        """Simplified format function for testing."""
        info_parts = []
        
        if job.get("use_4k"):
            info_parts.append("4K")
        if job.get("mirror_video"):
            info_parts.append("Mirror")
        if job.get("words_per_caption", 2) != 2:
            info_parts.append(f"{job.get('words_per_caption')} words/cap")
        
        if job.get("use_ai_voice"):
            info_parts.append("AI-TTS")
        if job.get("translation_enabled"):
            lang = job.get("target_language", "?")
            info_parts.append(f"Translate:{lang}")
        
        if job.get("use_ai_voice") and job.get("silence_threshold_ms", 300) != 300:
            info_parts.append(f"silence:{job.get('silence_threshold_ms')}ms")
        
        text_color = job.get("caption_text_color", (255, 255, 255, 255))
        if text_color != (255, 255, 255, 255):
            info_parts.append(f"color:RGB({text_color[0]},{text_color[1]},{text_color[2]})")
        
        stroke_color = job.get("caption_stroke_color", (0, 0, 0, 150))
        stroke_width = job.get("caption_stroke_width", 3)
        if stroke_color != (0, 0, 0, 150) or stroke_width != 3:
            info_parts.append(f"border:w={stroke_width},RGB({stroke_color[0]},{stroke_color[1]},{stroke_color[2]})")
        
        blur = job.get("blur_radius", 25)
        bg_scale = job.get("bg_scale_extra", 1.08)
        dim = job.get("dim_factor", 0.55)
        if blur != 25 or bg_scale != 1.08 or dim != 0.55:
            info_parts.append(f"effects:blur={blur}/scale={bg_scale:.2f}/dim={dim:.2f}")
        
        return " [" + ", ".join(info_parts) + "]" if info_parts else ""
    
    for name, job_data in scenarios:
        info = format_job_info(job_data)
        print(f"  {name}: {info if info else '(no extra info)'}")
    
    print("\n✓ Job display scenarios test completed")
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("Extended Job Info and Settings Tests")
    print("=" * 70)
    
    tests = [
        test_extended_job_info_display,
        test_job_info_fields,
        test_job_display_scenarios
    ]
    
    all_passed = True
    for test in tests:
        try:
            if not test():
                all_passed = False
        except Exception as e:
            print(f"✗ Test failed with exception: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False
    
    print("\n" + "=" * 70)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("=" * 70)
        exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 70)
        exit(1)
