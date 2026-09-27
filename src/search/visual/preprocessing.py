"""
Visual preprocessing module.
Purpose: Prepare images for comparison by standardizing size, format, and quality.
"""

from PIL import Image
import requests
from io import BytesIO
from pathlib import Path
from typing import Union, Optional

# Standard size for all images
STANDARD_SIZE = (256, 256)

def load_image(image_path: Union[str, Path]) -> Optional[Image.Image]:
    """Load an image from file path."""
    try:
        return Image.open(image_path)
    except Exception as e:
        print(f"[!] Failed to load image {image_path}: {e}")
        return None

def load_image_from_url(url: str, timeout: int = 10) -> Optional[Image.Image]:
    """Load an image from a URL."""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return Image.open(BytesIO(response.content))
    except Exception as e:
        print(f"[!] Failed to load image from {url}: {e}")
        return None

def preprocess_image(
    image: Image.Image,
    size: tuple = STANDARD_SIZE,
    grayscale: bool = True
) -> Image.Image:
    """
    Standardize an image for comparison.
    
    Steps:
    1. Convert to RGB (if not already) - handles RGBA, CMYK, etc.
    2. Resize to standard dimensions - ensures consistent comparison
    3. Convert to grayscale (optional) - reduces color noise
    4. Return processed image
    """
    # Convert to RGB (handles RGBA, CMYK, etc.)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Resize using high-quality Lanczos filter
    image = image.resize(size, Image.LANCZOS)
    
    # Grayscale: reduces color noise that doesn't help with shape matching
    if grayscale:
        image = image.convert('L')
    
    return image
