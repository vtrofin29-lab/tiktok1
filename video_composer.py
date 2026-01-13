"""
Video Composer Module
Composes final videos with captions and blurred backgrounds.
"""

import logging
from typing import Optional, Tuple, List
from PIL import Image
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def apply_gaussian_blur(image: Image.Image, radius: int = 10) -> Image.Image:
    """
    Apply Gaussian blur to an image.
    
    Args:
        image: PIL Image to blur
        radius: Blur radius
    
    Returns:
        Blurred PIL Image
    """
    try:
        from PIL import ImageFilter
        logger.debug(f"Applying Gaussian blur with radius {radius}")
        return image.filter(ImageFilter.GaussianBlur(radius=radius))
    except Exception as e:
        logger.error(f"Failed to apply blur: {e}")
        return image


def create_blurred_background(
    source_image: Image.Image,
    target_width: int,
    target_height: int,
    blur_radius: int = 20
) -> Image.Image:
    """
    Create a blurred background from a source image.
    
    Args:
        source_image: Source image to blur
        target_width: Target width for background
        target_height: Target height for background
        blur_radius: Radius for Gaussian blur
    
    Returns:
        Blurred background image
    """
    try:
        logger.info(f"Creating blurred background: {target_width}x{target_height}")
        
        # Resize source image to fill target dimensions
        # Calculate aspect ratios
        source_ratio = source_image.width / source_image.height
        target_ratio = target_width / target_height
        
        if source_ratio > target_ratio:
            # Source is wider, scale by height
            new_height = target_height
            new_width = int(new_height * source_ratio)
        else:
            # Source is taller, scale by width
            new_width = target_width
            new_height = int(new_width / source_ratio)
        
        # Resize with high quality
        resized = source_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Crop to target dimensions (center crop)
        left = (new_width - target_width) // 2
        top = (new_height - target_height) // 2
        right = left + target_width
        bottom = top + target_height
        
        cropped = resized.crop((left, top, right, bottom))
        
        # Apply blur
        blurred = apply_gaussian_blur(cropped, blur_radius)
        
        logger.info("Blurred background created successfully")
        return blurred
        
    except Exception as e:
        logger.error(f"Failed to create blurred background: {e}", exc_info=True)
        # Return a default blurred background
        bg = Image.new('RGB', (target_width, target_height), (50, 50, 50))
        return apply_gaussian_blur(bg, blur_radius)


def composite_image_with_alpha(
    background: Image.Image,
    foreground: Image.Image,
    position: Tuple[int, int] = (0, 0)
) -> Image.Image:
    """
    Composite a foreground image with alpha channel onto a background.
    
    Args:
        background: Background PIL Image
        foreground: Foreground PIL Image (should have alpha channel)
        position: (x, y) position for foreground on background
    
    Returns:
        Composited PIL Image
    """
    try:
        logger.debug(f"Compositing image at position {position}")
        
        # Ensure background is in RGBA mode
        if background.mode != 'RGBA':
            background = background.convert('RGBA')
        
        # Ensure foreground is in RGBA mode
        if foreground.mode != 'RGBA':
            foreground = foreground.convert('RGBA')
        
        # Create a copy of background to avoid modifying original
        result = background.copy()
        
        # Extract alpha channel from foreground
        alpha = foreground.split()[3]
        
        # Verify alpha channel is valid
        alpha_array = np.array(alpha)
        has_transparency = np.any(alpha_array < 255)
        logger.debug(f"Foreground has transparency: {has_transparency}")
        
        # Paste foreground onto background using alpha as mask
        result.paste(foreground, position, foreground)
        
        logger.debug("Image composited successfully")
        return result
        
    except Exception as e:
        logger.error(f"Failed to composite images: {e}", exc_info=True)
        return background


def compose_final_video_with_static_blurred_bg(
    main_video_frame: Image.Image,
    caption_image: Optional[Image.Image],
    output_width: int,
    output_height: int,
    blur_radius: int = 20,
    caption_position: str = 'bottom',
    caption_margin: int = 50,
    video_scale: float = 0.7
) -> Optional[Image.Image]:
    """
    Compose final video frame with blurred background and caption overlay.
    
    This function creates a final composition by:
    1. Creating a blurred background from the main video frame
    2. Overlaying the original video frame (scaled) in the center
    3. Adding caption text at the specified position with proper alpha handling
    
    Args:
        main_video_frame: Main video frame as PIL Image
        caption_image: Caption image with transparency (RGBA)
        output_width: Width of output composition
        output_height: Height of output composition
        blur_radius: Blur radius for background
        caption_position: Caption position ('top', 'bottom', 'center')
        caption_margin: Margin from edge for caption positioning
        video_scale: Scale factor for main video (0.0-1.0)
    
    Returns:
        Composited frame as PIL Image, or None if composition fails
    """
    try:
        logger.info(f"Composing final video frame: {output_width}x{output_height}")
        logger.debug(f"Settings - blur_radius: {blur_radius}, caption_position: {caption_position}, "
                    f"caption_margin: {caption_margin}, video_scale: {video_scale}")
        
        # Validate inputs
        if main_video_frame is None:
            logger.error("Main video frame is None")
            return None
        
        # Step 1: Create blurred background
        logger.debug("Step 1: Creating blurred background")
        blurred_bg = create_blurred_background(
            main_video_frame,
            output_width,
            output_height,
            blur_radius
        )
        
        # Convert to RGBA for composition
        if blurred_bg.mode != 'RGBA':
            blurred_bg = blurred_bg.convert('RGBA')
        
        # Step 2: Scale and position main video frame
        logger.debug("Step 2: Scaling and positioning main video frame")
        video_scale = max(0.1, min(1.0, video_scale))  # Clamp to valid range
        
        scaled_width = int(output_width * video_scale)
        scaled_height = int(output_height * video_scale)
        
        # Maintain aspect ratio
        video_ratio = main_video_frame.width / main_video_frame.height
        output_ratio = scaled_width / scaled_height
        
        if video_ratio > output_ratio:
            # Video is wider
            final_width = scaled_width
            final_height = int(final_width / video_ratio)
        else:
            # Video is taller
            final_height = scaled_height
            final_width = int(final_height * video_ratio)
        
        scaled_video = main_video_frame.resize(
            (final_width, final_height),
            Image.Resampling.LANCZOS
        )
        
        # Center position for video
        video_x = (output_width - final_width) // 2
        video_y = (output_height - final_height) // 2
        
        logger.debug(f"Scaled video size: {final_width}x{final_height}, position: ({video_x}, {video_y})")
        
        # Composite video onto blurred background
        composition = composite_image_with_alpha(blurred_bg, scaled_video, (video_x, video_y))
        
        # Step 3: Add caption if provided
        if caption_image is not None:
            logger.debug("Step 3: Adding caption overlay")
            
            # Ensure caption has alpha channel
            if caption_image.mode != 'RGBA':
                logger.warning(f"Caption image mode is {caption_image.mode}, converting to RGBA")
                caption_image = caption_image.convert('RGBA')
            
            # Verify alpha channel is properly set
            alpha_channel = caption_image.split()[3]
            alpha_array = np.array(alpha_channel)
            logger.debug(f"Caption alpha channel - min: {alpha_array.min()}, max: {alpha_array.max()}, "
                        f"mean: {alpha_array.mean():.2f}")
            
            # Check if caption has any non-transparent pixels
            if alpha_array.max() == 0:
                logger.error("Caption image is completely transparent! All alpha values are 0.")
                return composition
            
            # Calculate caption position
            caption_x = (output_width - caption_image.width) // 2
            
            if caption_position == 'top':
                caption_y = caption_margin
            elif caption_position == 'bottom':
                caption_y = output_height - caption_image.height - caption_margin
            else:  # center
                caption_y = (output_height - caption_image.height) // 2
            
            # Ensure caption is within bounds
            caption_x = max(0, min(caption_x, output_width - caption_image.width))
            caption_y = max(0, min(caption_y, output_height - caption_image.height))
            
            logger.debug(f"Caption position: ({caption_x}, {caption_y}), size: {caption_image.width}x{caption_image.height}")
            
            # Composite caption onto composition with alpha handling
            try:
                composition = composite_image_with_alpha(composition, caption_image, (caption_x, caption_y))
                logger.info("Caption added successfully to composition")
            except Exception as e:
                logger.error(f"Failed to composite caption: {e}", exc_info=True)
                logger.error("Continuing without caption overlay")
        else:
            logger.debug("No caption image provided, skipping caption overlay")
        
        logger.info("Final video frame composed successfully")
        return composition
        
    except Exception as e:
        logger.error(f"Failed to compose final video frame: {e}", exc_info=True)
        return None


def process_video_frames_with_captions(
    video_frames: List[Image.Image],
    captions: List[Tuple[str, int, int]],  # (text, start_frame, end_frame)
    output_width: int,
    output_height: int,
    caption_config: Optional[dict] = None,
    composition_config: Optional[dict] = None
) -> List[Image.Image]:
    """
    Process multiple video frames with time-based captions.
    
    Args:
        video_frames: List of video frames as PIL Images
        captions: List of (caption_text, start_frame, end_frame) tuples
        output_width: Output video width
        output_height: Output video height
        caption_config: Configuration dict for caption generation
        composition_config: Configuration dict for video composition
    
    Returns:
        List of processed frames with captions
    """
    from caption_generator import generate_caption_image
    
    try:
        logger.info(f"Processing {len(video_frames)} frames with {len(captions)} captions")
        
        # Default configurations
        if caption_config is None:
            caption_config = {
                'font_size': 48,
                'text_color': (255, 255, 255, 255),
                'stroke_color': (0, 0, 0, 255),
                'stroke_width': 3,
                'padding': 20
            }
        
        if composition_config is None:
            composition_config = {
                'blur_radius': 20,
                'caption_position': 'bottom',
                'caption_margin': 50,
                'video_scale': 0.7
            }
        
        processed_frames = []
        
        # Create caption cache
        caption_cache = {}
        for text, start, end in captions:
            if text not in caption_cache:
                caption_img = generate_caption_image(
                    text,
                    output_width,
                    200,  # Caption height
                    **caption_config
                )
                caption_cache[text] = caption_img
        
        # Process each frame
        for frame_idx, frame in enumerate(video_frames):
            # Find active caption for this frame
            active_caption = None
            for text, start, end in captions:
                if start <= frame_idx <= end:
                    active_caption = caption_cache.get(text)
                    break
            
            # Compose frame
            composed_frame = compose_final_video_with_static_blurred_bg(
                frame,
                active_caption,
                output_width,
                output_height,
                **composition_config
            )
            
            if composed_frame:
                processed_frames.append(composed_frame)
            else:
                logger.warning(f"Failed to process frame {frame_idx}, using original")
                processed_frames.append(frame)
        
        logger.info(f"Successfully processed {len(processed_frames)} frames")
        return processed_frames
        
    except Exception as e:
        logger.error(f"Failed to process video frames: {e}", exc_info=True)
        return video_frames
