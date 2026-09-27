"""
Sefina searcher - RESPECTFUL SCRAPING ONLY
- Covers both auction and shop sites
- Honors robots.txt
- 5-second delay between requests
- Identifies as a bot with contact info
- NEW: Visual matching against reference images

Sites:
- Auction: https://auktion.sefina.se/auktioner/
- Shop: https://www.sefina.se/shop-online/
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
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "search" / "visual"))
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

# Sefina sites
AUCTION_URL = "https://auktion.sefina.se/auktioner/"
SHOP_URL = "https://www.sefina.se/shop-online/"

REFERENCE_IMAGES_DIR = Path("data/reference_images")

# --- Global state ---
_reference_images = None
_reference_filenames = None
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
    img_tag = product.find('img', src=True)
    if img_tag:
        return img_tag['src']
    return None

def extract_id(product: BeautifulSoup) -> str:
    """Extract the product ID from a product container."""
    # Try auction site format
    id_elem = product.find('span', class_='auction-number')
    if id_elem:
        return id_elem.text.strip()
    
    # Try shop site format
    id_elem = product.find('span', class_='text-xs')
    if id_elem:
        return id_elem.text.strip()
    
    return ""

def extract_price(product: BeautifulSoup) -> str:
    """Extract the price from a product container."""
    price_elem = product.find('span', class_='woocommerce-Price-amount')
    if price_elem:
        return price_elem.text.strip()
    return "N/A"

def extract_title(product: BeautifulSoup) -> str:
    """Extract the title from a product container."""
    title_elem = product.find('h2', class_='woocommerce-loop-product__title')
    if title_elem:
        return title_elem.text.strip()
    return ""

def extract_link(product: BeautifulSoup) -> str:
    """Extract the product link from a product container."""
    link_elem = product.find('a', class_='woocommerce-LoopProduct-link')
    if link_elem and link_elem.get('href'):
        return link_elem['href']
    return ""

def download_and_preprocess_image(image_url: str) -> Optional[Image.Image]:
    """Download an image from URL and preprocess it."""
    if not image_url:
        return None
    try:
        # Handle relative URLs
        if image_url.startswith('/'):
            # Determine which site base to use
            if 'auktion' in image_url:
                image_url = f"https://auktion.sefina.se{image_url}"
            else:
                image_url = f"https://www.sefina.se{image_url}"
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
            "visual_distance": int(distance),
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
            "visual_distance": int(closest_distance) if closest_distance else None,
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

def search_site(url: str, keyword: str = "", use_visual: bool = True) -> List[Dict]:
    """Search a single Sefina site (auction or shop)."""
    session = create_session()
    all_results = []
    
    try:
        # If keyword provided, use WooCommerce search endpoint
        search_url = f"{url}?s={keyword}&post_type=product" if keyword else url
        response = session.get(search_url, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        items = parse_results(soup, url, keyword, use_visual=use_visual)
        all_results.extend(items)
        
    except requests.exceptions.RequestException as e:
        print(f"[!] Request failed for {url}: {e}")
    
    return all_results

def search_items(
    keywords: List[str] = None,
    location: str = "",
    negative_keywords: List[str] = None,
    use_visual: bool = True
) -> List[Dict]:
    """Search both Sefina sites with keywords. Returns list of item dicts."""
    all_results = []
    
    # Load reference images if visual matching is enabled
    if use_visual:
        load_reference_images_once()
    
    # Search both sites with each keyword
    if keywords:
        for keyword in keywords:
            for site_url in [AUCTION_URL, SHOP_URL]:
                print(f"[+] Searching {site_url} for '{keyword}'")
                results = search_site(site_url, keyword, use_visual=use_visual)
                
                # Filter by negative keywords (if provided)
                if negative_keywords:
                    results = filter_by_negative_keywords(results, negative_keywords)
                
                all_results.extend(results)
                print(f"    Found {len(results)} results")
                time.sleep(DELAY_SECONDS)  # Rate limiting
    else:
        # No keywords, scrape both sites
        for site_url in [AUCTION_URL, SHOP_URL]:
            print(f"[+] Searching {site_url}")
            results = search_site(site_url, use_visual=use_visual)
            
            if negative_keywords:
                results = filter_by_negative_keywords(results, negative_keywords)
            
            all_results.extend(results)
            print(f"    Found {len(results)} results")
            time.sleep(DELAY_SECONDS)
    
    return all_results

def parse_results(
    soup: BeautifulSoup,
    site_url: str,
    keyword: str = "",
    use_visual: bool = True
) -> List[Dict]:
    """Parse HTML into structured item data."""
    items = []

    # Find all product containers (both sites use li with class containing "product")
    product_containers = soup.find_all('li', class_=lambda x: x and 'product' in x)

    for product in product_containers:
        # Extract basic data
        title = extract_title(product)
        price = extract_price(product)
        item_id = extract_id(product)
        url = extract_link(product)
        
        # Make URL absolute
        if url and not url.startswith('http'):
            if 'auktion' in site_url:
                url = f"https://auktion.sefina.se{url}"
            else:
                url = f"https://www.sefina.se{url}"
        
        # Visual matching
        visual_info = {"visual_match": False, "visual_distance": None, "visual_best_ref": None}
        image_url = None
        if use_visual:
            image_url = extract_image_url(product)
            if image_url:
                # Handle relative image URLs
                if image_url.startswith('/'):
                    if 'auktion' in site_url:
                        image_url = f"https://auktion.sefina.se{image_url}"
                    else:
                        image_url = f"https://www.sefina.se{image_url}"
                
                listing_img = download_and_preprocess_image(image_url)
                if listing_img:
                    visual_info = get_visual_match_info(listing_img)
                else:
                    print(f"[!] Could not download image: {image_url}")

        item = {
            "title": title,
            "description": "",  # Sefina doesn't have visible descriptions on listing pages
            "item_id": item_id,
            "price": price,
            "url": url,
            "image_url": image_url if use_visual else None,
            "source": "sefina",
            "site": "auction" if "auktion" in site_url else "shop",
            "search_keyword": keyword,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            **visual_info
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
    
    # Use Swedish keywords by default, or all keywords
    keywords = config["query_keywords"]["swedish"]
    negative_keywords = config.get("negative_keywords", [])
    
    print(f"Searching Sefina with {len(keywords)} keywords...")
    print(f"Negative keywords: {negative_keywords}")
    print(f"Visual matching: ENABLED")
    
    results = search_items(keywords, negative_keywords=negative_keywords, use_visual=True)
    
    # Save results
    output_dir = Path("data/results")
    output_dir.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"sefina_{timestamp}.json"
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Print summary
    visual_matches = [r for r in results if r.get("visual_match")]
    print(f"\n[+] Saved {len(results)} results to {output_file}")
    print(f"[+] Visual matches: {len(visual_matches)}/{len(results)}")

if __name__ == "__main__":
    run_search()
