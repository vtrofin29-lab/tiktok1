"""
Test and demonstration script for caption generation and video composition.
"""

import logging
from PIL import Image
from caption_generator import generate_caption_image, generate_multiline_caption_image
from video_composer import compose_final_video_with_static_blurred_bg, process_video_frames_with_captions
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_test_frame(width=1080, height=1920, color=(100, 150, 200)):
    """Create a test video frame with gradient."""
    import numpy as np
    
    # Create gradient image
    img_array = np.zeros((height, width, 3), dtype=np.uint8)
    
    # Vertical gradient
    for y in range(height):
        factor = y / height
        img_array[y, :, 0] = int(color[0] * (1 - factor * 0.5))
        img_array[y, :, 1] = int(color[1] * (1 - factor * 0.5))
        img_array[y, :, 2] = int(color[2] * (1 - factor * 0.5))
    
    return Image.fromarray(img_array, 'RGB')


def test_caption_generation():
    """Test caption image generation."""
    logger.info("=" * 60)
    logger.info("Testing caption generation")
    logger.info("=" * 60)
    
    # Test 1: Basic caption with default settings
    logger.info("\nTest 1: Basic caption with default settings")
    caption1 = generate_caption_image(
        "Hello TikTok!",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3
    )
    if caption1:
        logger.info("✓ Basic caption generated successfully")
    else:
        logger.error("✗ Failed to generate basic caption")
    
    # Test 2: Caption with custom colors
    logger.info("\nTest 2: Caption with custom colors")
    caption2 = generate_caption_image(
        "Colorful Caption",
        1080,
        200,
        font_size=60,
        text_color=(255, 100, 200, 255),
        stroke_color=(50, 50, 150, 255),
        stroke_width=4
    )
    if caption2:
        logger.info("✓ Custom color caption generated successfully")
    else:
        logger.error("✗ Failed to generate custom color caption")
    
    # Test 3: Multiline caption
    logger.info("\nTest 3: Multiline caption")
    long_text = "This is a very long caption that should be wrapped into multiple lines for better readability"
    caption3 = generate_multiline_caption_image(
        long_text,
        1080,
        300,
        font_size=50,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3
    )
    if caption3:
        logger.info("✓ Multiline caption generated successfully")
    else:
        logger.error("✗ Failed to generate multiline caption")
    
    # Test 4: Caption with transparency
    logger.info("\nTest 4: Caption with semi-transparent background")
    caption4 = generate_caption_image(
        "Semi-transparent",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3,
        background_color=(0, 0, 0, 128)  # Semi-transparent black
    )
    if caption4:
        logger.info("✓ Semi-transparent caption generated successfully")
    else:
        logger.error("✗ Failed to generate semi-transparent caption")
    
    return caption1, caption2, caption3, caption4


def test_video_composition():
    """Test video composition with captions."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing video composition")
    logger.info("=" * 60)
    
    # Create test frame
    test_frame = create_test_frame(1080, 1920, (120, 180, 220))
    
    # Test 1: Composition without caption
    logger.info("\nTest 1: Composition without caption")
    result1 = compose_final_video_with_static_blurred_bg(
        test_frame,
        None,
        1080,
        1920,
        blur_radius=20,
        video_scale=0.7
    )
    if result1:
        logger.info("✓ Composition without caption successful")
    else:
        logger.error("✗ Failed to compose without caption")
    
    # Test 2: Composition with bottom caption
    logger.info("\nTest 2: Composition with bottom caption")
    caption = generate_caption_image(
        "Bottom Caption",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3
    )
    result2 = compose_final_video_with_static_blurred_bg(
        test_frame,
        caption,
        1080,
        1920,
        blur_radius=20,
        caption_position='bottom',
        caption_margin=50,
        video_scale=0.7
    )
    if result2:
        logger.info("✓ Composition with bottom caption successful")
    else:
        logger.error("✗ Failed to compose with bottom caption")
    
    # Test 3: Composition with top caption
    logger.info("\nTest 3: Composition with top caption")
    caption_top = generate_caption_image(
        "Top Caption",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3
    )
    result3 = compose_final_video_with_static_blurred_bg(
        test_frame,
        caption_top,
        1080,
        1920,
        blur_radius=20,
        caption_position='top',
        caption_margin=50,
        video_scale=0.7
    )
    if result3:
        logger.info("✓ Composition with top caption successful")
    else:
        logger.error("✗ Failed to compose with top caption")
    
    # Test 4: Composition with multiline caption
    logger.info("\nTest 4: Composition with multiline caption")
    long_caption = generate_multiline_caption_image(
        "This is a longer caption that will be wrapped into multiple lines",
        1080,
        300,
        font_size=50,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3
    )
    result4 = compose_final_video_with_static_blurred_bg(
        test_frame,
        long_caption,
        1080,
        1920,
        blur_radius=20,
        caption_position='bottom',
        caption_margin=50,
        video_scale=0.7
    )
    if result4:
        logger.info("✓ Composition with multiline caption successful")
    else:
        logger.error("✗ Failed to compose with multiline caption")
    
    return result1, result2, result3, result4


def test_alpha_channel_handling():
    """Test alpha channel and transparency handling."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing alpha channel handling")
    logger.info("=" * 60)
    
    import numpy as np
    
    # Create test frame
    test_frame = create_test_frame(1080, 1920, (150, 100, 200))
    
    # Test 1: Fully transparent background caption
    logger.info("\nTest 1: Caption with fully transparent background")
    caption1 = generate_caption_image(
        "Transparent BG",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3,
        background_color=(0, 0, 0, 0)  # Fully transparent
    )
    
    if caption1:
        # Check alpha channel
        alpha = np.array(caption1.split()[3])
        logger.info(f"  Alpha channel stats - min: {alpha.min()}, max: {alpha.max()}, mean: {alpha.mean():.2f}")
        has_transparency = np.any(alpha < 255)
        logger.info(f"  Has transparency: {has_transparency}")
        
        result1 = compose_final_video_with_static_blurred_bg(
            test_frame,
            caption1,
            1080,
            1920,
            caption_position='bottom'
        )
        if result1:
            logger.info("✓ Transparent background caption composited successfully")
        else:
            logger.error("✗ Failed to composite transparent background caption")
    else:
        logger.error("✗ Failed to generate transparent background caption")
    
    # Test 2: Semi-transparent background caption
    logger.info("\nTest 2: Caption with semi-transparent background")
    caption2 = generate_caption_image(
        "Semi-transparent",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3,
        background_color=(0, 0, 0, 128)  # 50% transparent black
    )
    
    if caption2:
        alpha = np.array(caption2.split()[3])
        logger.info(f"  Alpha channel stats - min: {alpha.min()}, max: {alpha.max()}, mean: {alpha.mean():.2f}")
        
        result2 = compose_final_video_with_static_blurred_bg(
            test_frame,
            caption2,
            1080,
            1920,
            caption_position='bottom'
        )
        if result2:
            logger.info("✓ Semi-transparent background caption composited successfully")
        else:
            logger.error("✗ Failed to composite semi-transparent background caption")
    else:
        logger.error("✗ Failed to generate semi-transparent background caption")
    
    # Test 3: Opaque background caption
    logger.info("\nTest 3: Caption with opaque background")
    caption3 = generate_caption_image(
        "Opaque Background",
        1080,
        200,
        font_size=60,
        text_color=(255, 255, 255, 255),
        stroke_color=(0, 0, 0, 255),
        stroke_width=3,
        background_color=(50, 50, 50, 255)  # Fully opaque dark gray
    )
    
    if caption3:
        alpha = np.array(caption3.split()[3])
        logger.info(f"  Alpha channel stats - min: {alpha.min()}, max: {alpha.max()}, mean: {alpha.mean():.2f}")
        
        result3 = compose_final_video_with_static_blurred_bg(
            test_frame,
            caption3,
            1080,
            1920,
            caption_position='bottom'
        )
        if result3:
            logger.info("✓ Opaque background caption composited successfully")
        else:
            logger.error("✗ Failed to composite opaque background caption")
    else:
        logger.error("✗ Failed to generate opaque background caption")


def test_edge_cases():
    """Test edge cases and error handling."""
    logger.info("\n" + "=" * 60)
    logger.info("Testing edge cases and error handling")
    logger.info("=" * 60)
    
    test_frame = create_test_frame(1080, 1920)
    
    # Test 1: Very long text
    logger.info("\nTest 1: Very long caption text")
    long_text = "This is an extremely long caption that might exceed the width " * 5
    caption = generate_multiline_caption_image(
        long_text,
        1080,
        400,
        font_size=40
    )
    if caption:
        result = compose_final_video_with_static_blurred_bg(
            test_frame,
            caption,
            1080,
            1920,
            caption_position='bottom'
        )
        if result:
            logger.info("✓ Long text handled successfully")
        else:
            logger.error("✗ Failed to handle long text")
    
    # Test 2: Empty caption text
    logger.info("\nTest 2: Empty caption text")
    caption_empty = generate_caption_image(
        "",
        1080,
        200,
        font_size=60
    )
    if caption_empty:
        logger.info("✓ Empty caption generated (expected behavior)")
    
    # Test 3: None caption
    logger.info("\nTest 3: None caption (should skip caption overlay)")
    result = compose_final_video_with_static_blurred_bg(
        test_frame,
        None,
        1080,
        1920
    )
    if result:
        logger.info("✓ None caption handled successfully")
    
    # Test 4: Invalid color values (should be normalized)
    logger.info("\nTest 4: Invalid color values (should be normalized)")
    caption_invalid = generate_caption_image(
        "Invalid Colors",
        1080,
        200,
        font_size=60,
        text_color=(300, -50, 255, 400),  # Out of range values
        stroke_color=(500, 0, 0, 300)
    )
    if caption_invalid:
        logger.info("✓ Invalid color values normalized successfully")


def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 60)
    logger.info("CAPTION GENERATION AND VIDEO COMPOSITION TEST SUITE")
    logger.info("=" * 60)
    
    try:
        # Test caption generation
        test_caption_generation()
        
        # Test video composition
        test_video_composition()
        
        # Test alpha channel handling
        test_alpha_channel_handling()
        
        # Test edge cases
        test_edge_cases()
        
        logger.info("\n" + "=" * 60)
        logger.info("ALL TESTS COMPLETED")
        logger.info("=" * 60)
        logger.info("\nPlease review the logs above for detailed results.")
        logger.info("All caption rendering errors are logged with full stack traces.")
        
    except Exception as e:
        logger.error(f"Test suite failed with error: {e}", exc_info=True)


if __name__ == "__main__":
    run_all_tests()
