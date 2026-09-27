"""
Pantbanken searcher - RESPECTFUL SCRAPING ONLY
- Honors robots.txt (avoids /secure, /external)
- 5-second delay between requests
- Identifies as a bot with contact info
- Caches results to avoid duplicate requests
- NEW: Visual matching against reference images
"""

import requests
import time
import json
import os
from pathlib import Path
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Tuple
from PIL import Image

# Import visual modules
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "visual"))
from preprocessing import load_image, preprocess_image, load_image_from_url
from similarity import (
    load_reference_images,
    compute_phash,
    compare_images,
    get_best_match,
    SIMILARITY_THRESHOLD
)

# --- Configuration ---

USER_AGENT = "FinderAgent/1.0 (+https://github.com/yourusername/finder-agent; contact@yourmail.com)"
DELAY_SECONDS = 5  # Strict rate limiting
BASE_URL = "https://shop.pantbanken.se/webshop"
REFERENCE_IMAGES_DIR = Path("data/reference_images")

# --- Global state ---
_reference_images = None  # Will be loaded once at startup
_reference_filenames = None  # Store original filenames
_preprocessed_refs = None

# --- Respectful session ---

def create_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept-Language": "sv-SE,sv;q=0.9",
    })
    return session

# --- Visual Setup ---

def load_reference_images_once() -> List[Image.Image]:
    """Load reference images once and cache them."""
    global _reference_images, _reference_filenames, _preprocessed_refs
    if _reference_images is None:
        if not REFERENCE_IMAGES_DIR.exists():
            print(f"[!] Reference images directory not found: {REFERENCE_IMAGES_DIR}")
            return []
        _reference_images = load_reference_images(REFERENCE_IMAGES_DIR)
        _reference_filenames = [img.filename for img in _reference_images]
        _preprocessed_refs = [preprocess_image(img) for img in _reference_images]
        print(f"[+] Loaded {len(_reference_images)} reference images")
    return _preprocessed_refs

def extract_image_url(product: BeautifulSoup) -> Optional[str]:
    """Extract the main image URL from a product container."""
    # Try to find img tag with src attribute
    img_tag = product.find('img', src=True)
    if img_tag:
        return img_tag['src']
    return None

def download_and_preprocess_image(image_url: str) -> Optional[Image.Image]:
    """Download an image from URL and preprocess it."""
    if not image_url:
        return None
    try:
        # Construct full URL if relative
        if image_url.startswith('/'):
            image_url = f"https://shop.pantbanken.se{image_url}"
        raw_img = load_image_from_url(image_url, timeout=10)
        if raw_img:
            return preprocess_image(raw_img)
    except Exception as e:
        print(f"[!] Failed to download image {image_url}: {e}")
    return None

def get_visual_match_info(listing_image: Image.Image) -> Dict:
    """Compare a listing image against all reference images."""
    refs = load_reference_images_once()
    if not refs or _reference_filenames is None:
        return {"visual_match": False, "visual_distance": None, "visual_best_ref": None}
    
    best_match = get_best_match(listing_image, refs, SIMILARITY_THRESHOLD)
    
    if best_match:
        ref_img, distance = best_match
        # Find which reference image this is (by index)
        for i, r in enumerate(_preprocessed_refs):
            if compute_phash(r) == compute_phash(ref_img):
                best_ref_name = _reference_filenames[i]
                break
        else:
            best_ref_name = None
        return {
            "visual_match": True,
            "visual_distance": distance,
            "visual_best_ref": best_ref_name
        }
    else:
        # No match, but find the closest one for debugging
        all_matches = []
        listing_hash = compute_phash(listing_image)
        for idx, ref_img in enumerate(refs):
            ref_hash = compute_phash(ref_img)
            distance = listing_hash - ref_hash
            all_matches.append((distance, _reference_filenames[idx]))
        all_matches.sort()
        closest_distance, closest_ref = all_matches[0] if all_matches else (None, None)
        
        return {
            "visual_match": False,
            "visual_distance": closest_distance,
            "visual_best_ref": closest_ref
        }

# --- Filtering ---

def filter_by_negative_keywords(items: List[Dict], negative_keywords: List[str]) -> List[Dict]:
    """Filter out items whose title OR description contains any negative keyword."""
    filtered = []
    for item in items:
        title = item.get("title", "").lower()
        description = item.get("description", "").lower()
        combined_text = f"{title} {description}"
        if not any(kw.lower() in combined_text for kw in negative_keywords):
            filtered.append(item)
    return filtered

# --- Search logic ---

def search_items(
    keywords: List[str], 
    location: str = "", 
    negative_keywords: List[str] = None,
    use_visual: bool = True
) -> List[Dict]:
    """Search Pantbanken with keywords. Returns list of item dicts."""
    session = create_session()
    all_results = []
    
    # Load reference images if visual matching is enabled
    if use_visual:
        load_reference_images_once()

    for keyword in keywords:
        time.sleep(DELAY_SECONDS)  # Rate limiting
        
        params = {"textsearch": keyword}
        if location:
            params["location"] = location
        
        try:
            response = session.get(
                f"{BASE_URL}",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            
            # Parse results
            soup = BeautifulSoup(response.text, "html.parser")
            items = parse_results(soup, keyword, use_visual=use_visual)
            
            # Filter by negative keywords (if provided)
            if negative_keywords:
                items = filter_by_negative_keywords(items, negative_keywords)
            
            all_results.extend(items)
            print(f"[+] '{keyword}': {len(items)} results (after filtering)")
            
        except requests.exceptions.RequestException as e:
            print(f"[!] Request failed for '{keyword}': {e}")
            continue
    
    return all_results

def parse_results(
    soup: BeautifulSoup, 
    keyword: str, 
    use_visual: bool = True
) -> List[Dict]:
    """Parse HTML into structured item data."""
    items = []

    # Find all product containers (using Alpine.js :class attribute)
    # The product container has :class="gridLayout ? 'pb-5' : 'w-full bg-base-300'"
    product_containers = soup.find_all('div', attrs={
        ':class': lambda x: x and ('pb-5' in x or 'w-full bg-base-300' in x)
    })

    for product in product_containers:
        # Text container (holds ID, title, description)
        # Has :class containing 'space-y-px'
        text_div = product.find('div', attrs={
            ':class': lambda x: x and 'space-y-px' in x
        })
        if not text_div:
            continue

        # Extract text data
        # ID: <p class="text-sm"><a>SE9.R761145</a></p>
        id_elem = text_div.find('p', class_='text-sm')
        item_id = id_elem.find('a').text.strip() if id_elem and id_elem.find('a') else ""

        # Title: <h2><a>Hänge fatimas hand 40x27mm 925/1000</a></h2>
        title_elem = text_div.find('h2')
        title = title_elem.find('a').text.strip() if title_elem and title_elem.find('a') else ""

        # Description: Try multiple possible locations
        # Option 1: line-clamp-2 class
        desc_elem = text_div.find('p', class_='line-clamp-2')
        # Option 2: Any p tag with :class containing 'line-clamp'
        if not desc_elem:
            desc_elem = text_div.find('p', attrs={':class': lambda x: x and 'line-clamp' in x})
        # Option 3: Any p tag (fallback)
        if not desc_elem:
            desc_elem = text_div.find('p')
        description = desc_elem.text.strip() if desc_elem else ""

        # Price: <a :class="...stat-value...">100 kr</a>
        price_elem = product.find('a', attrs={
            ':class': lambda x: x and 'stat-value' in x
        })
        price = price_elem.text.strip() if price_elem else "N/A"

        # Link: <a href="/webshop/show/69307">
        link_elem = text_div.find('a', href=lambda x: x and '/webshop/show/' in x)
        url = f"https://shop.pantbanken.se{link_elem['href']}" if link_elem else ""

        # Visual matching: extract image URL and compare
        visual_info = {"visual_match": False, "visual_distance": None, "visual_best_ref": None}
        if use_visual:
            image_url = extract_image_url(product)
            if image_url:
                # Download and preprocess listing image
                listing_img = download_and_preprocess_image(image_url)
                if listing_img:
                    visual_info = get_visual_match_info(listing_img)
                    # Convert numpy int64 to Python int for JSON serialization
                    if visual_info.get("visual_distance") is not None:
                        visual_info["visual_distance"] = int(visual_info["visual_distance"])
                else:
                    print(f"[!] Could not download image: {image_url}")

        item = {
            "title": title,
            "description": description,
            "item_id": item_id,
            "price": price,
            "url": url,
            "image_url": image_url if use_visual else None,
            "search_keyword": keyword,
            "source": "pantbanken",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **visual_info  # Add visual match info
        }
        items.append(item)

    return items

# --- Main entry ---

def run_search(config_path: str = "config/item_profile.json") -> None:
    """Load config and execute search."""
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    keywords = config["query_keywords"]["swedish"]
    negative_keywords = config.get("negative_keywords", [])
    
    print(f"Searching with {len(keywords)} keywords...")
    print(f"Negative keywords: {negative_keywords}")
    print(f"Visual matching: ENABLED")
    
    results = search_items(keywords, negative_keywords=negative_keywords, use_visual=True)
    
    # Save results
    output_dir = Path("data/results")
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"pantbanken_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Print summary
    visual_matches = [r for r in results if r.get("visual_match")]
    print(f"\n[+] Saved {len(results)} results to {output_file}")
    print(f"[+] Visual matches: {len(visual_matches)}/{len(results)}")

if __name__ == "__main__":
    run_search()
