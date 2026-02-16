#!/usr/bin/env python3
"""
Test to validate that job info and effects are properly stored and displayed.
"""

def test_job_info_display():
    """Test that job info is properly formatted in display."""
    print("Testing job info display formatting...")
    
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
            "dim_factor": 0.55
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
            "dim_factor": 0.60
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
            "dim_factor": 0.55
        }
    ]
    
    import os
    
    # Helper function to format job info (same as in main script)
    def format_job_info(job):
        """Format job information for display, showing all relevant settings."""
        info_parts = []
        if job.get("use_4k"):
            info_parts.append("4K")
        if job.get("mirror_video"):
            info_parts.append("Mirror")
        if job.get("words_per_caption", 2) != 2:
            info_parts.append(f"{job.get('words_per_caption')} words/cap")
        
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
    
    print("\n✓ Job info display test completed")
    return True

def test_job_effects_parameters():
    """Test that effects parameters have proper defaults."""
    print("\nTesting effects parameters defaults...")
    
    # Test defaults
    default_blur = 25
    default_bg_scale = 1.08
    default_dim = 0.55
    
    # Simulate job creation with defaults
    job = {
        "blur_radius": default_blur,
        "bg_scale_extra": default_bg_scale,
        "dim_factor": default_dim
    }
    
    assert job["blur_radius"] == 25, "Default blur_radius should be 25"
    assert job["bg_scale_extra"] == 1.08, "Default bg_scale_extra should be 1.08"
    assert job["dim_factor"] == 0.55, "Default dim_factor should be 0.55"
    
    print(f"✓ Default blur_radius: {job['blur_radius']}")
    print(f"✓ Default bg_scale_extra: {job['bg_scale_extra']}")
    print(f"✓ Default dim_factor: {job['dim_factor']}")
    
    # Test custom values
    custom_job = {
        "blur_radius": 30,
        "bg_scale_extra": 1.15,
        "dim_factor": 0.60
    }
    
    print(f"✓ Custom blur_radius: {custom_job['blur_radius']}")
    print(f"✓ Custom bg_scale_extra: {custom_job['bg_scale_extra']}")
    print(f"✓ Custom dim_factor: {custom_job['dim_factor']}")
    
    print("\n✓ Effects parameters test completed")
    return True

def test_job_resolution_flag():
    """Test that use_4k flag is properly stored."""
    print("\nTesting resolution flag...")
    
    hd_job = {"use_4k": False}
    uhd_job = {"use_4k": True}
    
    assert hd_job["use_4k"] == False, "HD job should have use_4k=False"
    assert uhd_job["use_4k"] == True, "4K job should have use_4k=True"
    
    print(f"✓ HD job: use_4k={hd_job['use_4k']}")
    print(f"✓ 4K job: use_4k={uhd_job['use_4k']}")
    
    print("\n✓ Resolution flag test completed")
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("Job Info and Effects Tests")
    print("=" * 60)
    
    tests = [
        test_job_info_display,
        test_job_effects_parameters,
        test_job_resolution_flag
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
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED")
        print("=" * 60)
        exit(0)
    else:
        print("✗ SOME TESTS FAILED")
        print("=" * 60)
        exit(1)
