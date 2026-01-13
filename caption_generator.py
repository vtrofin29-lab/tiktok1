"""
Caption Generator Module
Generates caption images with customizable fonts, colors, transparency, and stroke settings.
"""

import logging
from PIL import Image, ImageDraw, ImageFont
from typing import Tuple, Optional
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def generate_caption_image(
    text: str,
    width: int,
    height: int,
    font_path: Optional[str] = None,
    font_size: int = 48,
    text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    stroke_width: int = 2,
    background_color: Tuple[int, int, int, int] = (0, 0, 0, 0),
    padding: int = 20,
    max_width_ratio: float = 0.9
) -> Optional[Image.Image]:
    """
    Generate a caption image with proper font, transparency, and stroke settings.
    
    Args:
        text: The caption text to render
        width: Width of the output image
        height: Height of the output image
        font_path: Path to custom font file (uses default if None)
        font_size: Size of the font in pixels
        text_color: RGBA color tuple for text (normalized to 0-255)
        stroke_color: RGBA color tuple for text stroke (normalized to 0-255)
        stroke_width: Width of the text stroke in pixels
        background_color: RGBA color tuple for background (transparent by default)
        padding: Padding around text in pixels
        max_width_ratio: Maximum width ratio for text (0.0-1.0)
    
    Returns:
        PIL Image object with caption, or None if generation fails
    """
    try:
        logger.info(f"Generating caption image: text='{text}', size={width}x{height}")
        
        # Normalize color values to ensure they're in valid range (0-255)
        def normalize_color(color: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
            """Normalize RGBA color tuple to valid range."""
            return tuple(max(0, min(255, int(c))) for c in color)
        
        text_color = normalize_color(text_color)
        stroke_color = normalize_color(stroke_color)
        background_color = normalize_color(background_color)
        
        logger.debug(f"Normalized colors - text: {text_color}, stroke: {stroke_color}, bg: {background_color}")
        
        # Create image with RGBA mode for transparency support
        image = Image.new('RGBA', (width, height), background_color)
        draw = ImageDraw.Draw(image)
        
        # Load font with fallback to default
        try:
            if font_path and os.path.exists(font_path):
                logger.debug(f"Loading custom font from: {font_path}")
                font = ImageFont.truetype(font_path, font_size)
            else:
                logger.debug("Using default font")
                # Try to load a common system font as fallback
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        logger.warning("Could not load TrueType font, using default bitmap font")
                        font = ImageFont.load_default()
        except Exception as e:
            logger.error(f"Error loading font: {e}, using default font")
            font = ImageFont.load_default()
        
        # Calculate text bounding box for positioning
        # Use textbbox for accurate text measurement
        try:
            bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback for older PIL versions
            text_width, text_height = draw.textsize(text, font=font)
            # Add stroke width to dimensions
            text_width += stroke_width * 2
            text_height += stroke_width * 2
        
        logger.debug(f"Text dimensions: {text_width}x{text_height}")
        
        # Check if text fits within max width
        max_text_width = width * max_width_ratio
        if text_width > max_text_width:
            logger.warning(f"Text width ({text_width}px) exceeds max width ({max_text_width}px), may need wrapping")
        
        # Center text position with padding consideration
        x = (width - text_width) // 2
        y = (height - text_height) // 2
        
        # Ensure text is not clipped by padding
        x = max(padding, min(x, width - text_width - padding))
        y = max(padding, min(y, height - text_height - padding))
        
        logger.debug(f"Text position: ({x}, {y})")
        
        # Draw text with stroke for better visibility
        draw.text(
            (x, y),
            text,
            font=font,
            fill=text_color,
            stroke_width=stroke_width,
            stroke_fill=stroke_color
        )
        
        logger.info(f"Caption image generated successfully")
        return image
        
    except Exception as e:
        logger.error(f"Failed to generate caption image: {e}", exc_info=True)
        return None


def generate_multiline_caption_image(
    text: str,
    width: int,
    height: int,
    font_path: Optional[str] = None,
    font_size: int = 48,
    text_color: Tuple[int, int, int, int] = (255, 255, 255, 255),
    stroke_color: Tuple[int, int, int, int] = (0, 0, 0, 255),
    stroke_width: int = 2,
    background_color: Tuple[int, int, int, int] = (0, 0, 0, 0),
    padding: int = 20,
    line_spacing: int = 10,
    max_width_ratio: float = 0.9
) -> Optional[Image.Image]:
    """
    Generate a multiline caption image with text wrapping.
    
    Args:
        text: The caption text to render (will be split into lines)
        width: Width of the output image
        height: Height of the output image
        font_path: Path to custom font file
        font_size: Size of the font in pixels
        text_color: RGBA color tuple for text
        stroke_color: RGBA color tuple for text stroke
        stroke_width: Width of the text stroke
        background_color: RGBA color tuple for background
        padding: Padding around text
        line_spacing: Additional spacing between lines
        max_width_ratio: Maximum width ratio for text
    
    Returns:
        PIL Image object with caption, or None if generation fails
    """
    try:
        logger.info(f"Generating multiline caption image: text='{text[:50]}...', size={width}x{height}")
        
        # Normalize color values
        def normalize_color(color: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
            return tuple(max(0, min(255, int(c))) for c in color)
        
        text_color = normalize_color(text_color)
        stroke_color = normalize_color(stroke_color)
        background_color = normalize_color(background_color)
        
        # Create image with RGBA mode
        image = Image.new('RGBA', (width, height), background_color)
        draw = ImageDraw.Draw(image)
        
        # Load font
        try:
            if font_path and os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
            else:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
                except:
                    try:
                        font = ImageFont.truetype("arial.ttf", font_size)
                    except:
                        font = ImageFont.load_default()
        except Exception as e:
            logger.error(f"Error loading font: {e}")
            font = ImageFont.load_default()
        
        # Split text into words and wrap
        words = text.split()
        lines = []
        current_line = []
        max_text_width = width * max_width_ratio
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                bbox = draw.textbbox((0, 0), test_line, font=font, stroke_width=stroke_width)
                line_width = bbox[2] - bbox[0]
            except AttributeError:
                line_width, _ = draw.textsize(test_line, font=font)
                line_width += stroke_width * 2
            
            if line_width <= max_text_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        logger.debug(f"Text wrapped into {len(lines)} lines")
        
        # Calculate total text block height
        try:
            bbox = draw.textbbox((0, 0), "Ay", font=font, stroke_width=stroke_width)
            line_height = bbox[3] - bbox[1]
        except AttributeError:
            _, line_height = draw.textsize("Ay", font=font)
            line_height += stroke_width * 2
        
        total_height = len(lines) * line_height + (len(lines) - 1) * line_spacing
        
        # Starting y position (centered)
        y = (height - total_height) // 2
        y = max(padding, min(y, height - total_height - padding))
        
        # Draw each line
        for line in lines:
            try:
                bbox = draw.textbbox((0, 0), line, font=font, stroke_width=stroke_width)
                line_width = bbox[2] - bbox[0]
            except AttributeError:
                line_width, _ = draw.textsize(line, font=font)
                line_width += stroke_width * 2
            
            x = (width - line_width) // 2
            x = max(padding, min(x, width - line_width - padding))
            
            draw.text(
                (x, y),
                line,
                font=font,
                fill=text_color,
                stroke_width=stroke_width,
                stroke_fill=stroke_color
            )
            
            y += line_height + line_spacing
        
        logger.info(f"Multiline caption image generated successfully with {len(lines)} lines")
        return image
        
    except Exception as e:
        logger.error(f"Failed to generate multiline caption image: {e}", exc_info=True)
        return None
