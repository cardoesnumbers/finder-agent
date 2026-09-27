"""
Visual similarity module.
Purpose: Compare images and determine if they represent the same necklace.
Uses perceptual hashing (pHash) for efficient and robust image comparison.
"""

from PIL import Image
import imagehash
from pathlib import Path
from typing import List, Tuple, Optional

# Threshold: Maximum Hamming distance to consider images "similar"
# Lower = stricter (fewer matches, but more accurate)
# Higher = more lenient (more matches, but more false positives)
# Typical range: 5-10 for pHash
# NOTE: User's reference images have distance=28, so threshold needs to be >= 28
# Set to 25 to reduce false positives
SIMILARITY_THRESHOLD = 25

def compute_phash(image: Image.Image) -> imagehash.ImageHash:
    """
    Compute perceptual hash of an image.
    
    pHash works by:
    1. Reducing image to small size (we use 256x256 in preprocessing)
    2. Computing DCT (Discrete Cosine Transform)
    3. Extracting the lowest frequency components
    4. Creating a binary hash
    
    Result: Two similar images will have similar hashes.
    """
    return imagehash.phash(image)

def compare_images(
    image1: Image.Image,
    image2: Image.Image,
    threshold: int = SIMILARITY_THRESHOLD
) -> Tuple[bool, int]:
    """
    Compare two images using perceptual hashing.
    
    Returns:
        (is_similar: bool, hamming_distance: int)
        - is_similar: True if distance <= threshold
        - hamming_distance: How different the images are (0 = identical)
    """
    hash1 = compute_phash(image1)
    hash2 = compute_phash(image2)
    distance = hash1 - hash2  # Hamming distance
    
    return (distance <= threshold, distance)

def load_reference_images(ref_dir: Path) -> List[Image.Image]:
    """
    Load all reference images from a directory.
    Supports .jpg, .jpeg, .png files.
    """
    ref_images = []
    for ext in ['*.jpg', '*.jpeg', '*.png']:
        for img_path in ref_dir.glob(ext):
            img = Image.open(img_path)
            ref_images.append(img)
    return ref_images

def find_matches(
    listing_image: Image.Image,
    reference_images: List[Image.Image],
    threshold: int = SIMILARITY_THRESHOLD
) -> List[Tuple[Image.Image, int]]:
    """
    Find which reference images match the listing image.
    
    Returns list of (reference_image, hamming_distance) tuples,
    sorted by distance (closest matches first).
    """
    listing_hash = compute_phash(listing_image)
    matches = []
    
    for ref_img in reference_images:
        ref_hash = compute_phash(ref_img)
        distance = listing_hash - ref_hash
        matches.append((ref_img, distance))
    
    # Sort by distance (ascending: closest matches first)
    matches.sort(key=lambda x: x[1])
    return matches

def get_best_match(
    listing_image: Image.Image,
    reference_images: List[Image.Image],
    threshold: int = SIMILARITY_THRESHOLD
) -> Optional[Tuple[Image.Image, int]]:
    """
    Get the best matching reference image, if any.
    Returns (reference_image, distance) or None if no match.
    """
    matches = find_matches(listing_image, reference_images, threshold)
    if matches and matches[0][1] <= threshold:
        return matches[0]
    return None
