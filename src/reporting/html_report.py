"""
HTML Report Generator for Finder Agent

Generates a visual HTML report from search results with:
- Product thumbnails
- Reference image previews
- Match scores
- Direct links to listings
- Filtering options (all results, visual matches only, etc.)

Usage:
    python src/reporting/html_report.py
    # Or specify a results file:
    python src/reporting/html_report.py data/results/pantit_*.json
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


def load_results(result_files: List[str] = None) -> List[Dict]:
    """Load results from JSON files."""
    all_results = []
    
    if result_files:
        # Load specific files
        for file_path in result_files:
            path = Path(file_path)
            if path.exists() and path.stat().st_size > 10:  # Skip empty files
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        results = json.load(f)
                        all_results.extend(results)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"[!] Skipping invalid file {path}: {e}")
                    continue
    else:
        # Load all results from data/results/
        results_dir = Path("data/results")
        if results_dir.exists():
            for result_file in sorted(results_dir.glob("*.json"), reverse=True):
                # Skip empty files and safety limit
                if result_file.stat().st_size < 10:
                    continue
                if len(all_results) >= 100:  # Safety limit
                    break
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        results = json.load(f)
                        # Add source file info
                        for r in results:
                            r['_source_file'] = result_file.name
                        all_results.extend(results)
                except (json.JSONDecodeError, Exception) as e:
                    print(f"[!] Skipping invalid file {result_file}: {e}")
                    continue
    
    return all_results


def get_reference_images_info() -> List[Dict]:
    """Get list of reference images with their paths."""
    ref_dir = Path("data/reference_images")
    ref_images = []
    
    if ref_dir.exists():
        for img_path in ref_dir.rglob('*'):
            if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # Use absolute path and then make it relative to cwd
                abs_path = img_path.absolute()
                try:
                    rel_path = str(img_path.relative_to(Path.cwd()))
                except ValueError:
                    # If the path is not relative to cwd, use absolute path
                    rel_path = str(abs_path)
                ref_images.append({
                    'name': img_path.name,
                    'path': rel_path
                })
    
    return ref_images


def generate_html_report(
    results: List[Dict],
    output_file: str = "data/reports/report.html",
    show_all: bool = False,
    min_distance: int = None
) -> None:
    """Generate an HTML report from search results."""
    
    # Filter results
    if show_all:
        filtered_results = results
    else:
        # Only show visual matches by default
        filtered_results = [r for r in results if r.get('visual_match', False)]
    
    # Additional filter by minimum distance
    if min_distance is not None:
        filtered_results = [r for r in filtered_results 
                          if r.get('visual_distance') is not None and r['visual_distance'] <= min_distance]
    
    # Sort by visual distance (best matches first)
    filtered_results.sort(key=lambda x: x.get('visual_distance') or 999)
    
    # Get reference images
    ref_images = get_reference_images_info()
    
    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Finder Agent - Search Results</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{ 
            color: #333;
            border-bottom: 2px solid #333;
            padding-bottom: 10px;
        }}
        .stats {{ 
            background: #fff;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .stats span {{ 
            margin-right: 20px;
            font-weight: bold;
        }}
        .filters {{ 
            background: #e8f4f8;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .filters a {{ 
            margin-right: 15px;
            color: #0066cc;
            text-decoration: none;
        }}
        .results-grid {{ 
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        .result-card {{ 
            background: #fff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}
        .result-card:hover {{ 
            transform: translateY(-5px);
            box-shadow: 0 4px 16px rgba(0,0,0,0.2);
        }}
        .result-image {{ 
            width: 100%;
            height: 250px;
            object-fit: contain;
            background: #f9f9f9;
            border-bottom: 1px solid #eee;
        }}
        .result-info {{ 
            padding: 15px;
        }}
        .result-title {{ 
            font-size: 14px;
            font-weight: bold;
            color: #333;
            margin-bottom: 8px;
            line-height: 1.4;
        }}
        .result-meta {{ 
            font-size: 13px;
            color: #666;
            margin-bottom: 8px;
        }}
        .result-price {{ 
            font-size: 16px;
            font-weight: bold;
            color: #e67e22;
            margin-bottom: 8px;
        }}
        .match-badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
            color: #fff;
            margin-bottom: 5px;
        }}
        .match-true {{ background: #27ae60; }}
        .match-false {{ background: #e74c3c; }}
        .distance-tag {{ 
            display: inline-block;
            background: #3498db;
            color: #fff;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 11px;
            margin-left: 5px;
        }}
        .ref-image {{ 
            width: 60px;
            height: 60px;
            object-fit: contain;
            border: 2px solid #3498db;
            border-radius: 4px;
            margin-top: 8px;
        }}
        .result-link {{ 
            display: block;
            margin-top: 10px;
            text-align: center;
            color: #0066cc;
            font-size: 12px;
            text-decoration: none;
        }}
        .result-link:hover {{ 
            text-decoration: underline;
        }}
        .no-results {{ 
            text-align: center;
            padding: 40px;
            color: #888;
        }}
        .source-tag {{ 
            display: inline-block;
            background: #9b59b6;
            color: #fff;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 10px;
            margin-left: 5px;
        }}
    </style>
</head>
<body>
    <h1>🎯 Finder Agent - Search Results</h1>
    
    <div class="stats">
        <span>Total Results: {len(results)}</span>
        <span>Visual Matches: {len([r for r in results if r.get('visual_match')])}</span>
        <span>Showing: {len(filtered_results)} items</span>
        <span>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</span>
    </div>
    
    <div class="filters">
        <strong>Filter:</strong>
        <a href="#" onclick="filterReport('all')">All Results</a>
        <a href="#" onclick="filterReport('matches')">Visual Matches Only</a>
        <a href="#" onclick="filterReport('distance-25')">Distance ≤ 25</a>
        <a href="#" onclick="filterReport('distance-20')">Distance ≤ 20</a>
        <a href="#" onclick="filterReport('distance-15')">Distance ≤ 15</a>
        <a href="#" onclick="location.reload()">Reset</a>
    </div>
    
    <div class="results-grid" id="results">
"""
    
    if not filtered_results:
        html += '<div class="no-results">No results to display. Try adjusting your filters.</div>'
    else:
        for i, result in enumerate(filtered_results):
            title = result.get('title', 'Unknown')
            price = result.get('price', 'N/A')
            url = result.get('url', '')
            image_url = result.get('image_url', '')
            item_id = result.get('item_id', '')
            source = result.get('source', 'unknown')
            
            is_match = result.get('visual_match', False)
            distance = result.get('visual_distance')
            best_ref = result.get('visual_best_ref', '')
            
            # Find the reference image path
            ref_img_path = ""
            if best_ref:
                for ref in ref_images:
                    if ref['name'] == best_ref:
                        ref_img_path = ref['path']
                        break
            
            # Determine match status
            if is_match:
                match_class = "match-true"
                match_text = "✓ MATCH"
            else:
                match_class = "match-false"
                match_text = "✗ No Match"
            
            # Card HTML
            html += f"""
        <div class="result-card" data-match="{str(is_match).lower()}" data-distance="{distance or 999}">
            <img src="{image_url}" alt="{title[:50]}" class="result-image" onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 width=%22300%22 height=%22250%22><rect fill=%22%23f0f0f0%22 width=%22300%22 height=%22250%22/><text x=%2250%25%22 y=%2250%25%22 text-anchor=%22middle%22 dy=%22.3em%22 fill=%22%23999%22>No Image</text></svg>'">
            <div class="result-info">
                <div>
                    <span class="match-badge {match_class}">{match_text}</span>
                    {f'<span class="distance-tag">dist: {distance}</span>' if distance is not None else ''}
                    <span class="source-tag">{source}</span>
                </div>
                <div class="result-title">{title}</div>
                {f'<div class="result-meta">ID: {item_id}</div>' if item_id else ''}
                <div class="result-price">{price}</div>
                {f'<img src="{ref_img_path}" class="ref-image" title="Matched: {best_ref}">' if ref_img_path else ''}
                <a href="{url}" class="result-link" target="_blank">View Listing →</a>
            </div>
        </div>
        """
    
    # Add JavaScript for filtering
    html += """
    </div>
    
    <script>
        function filterReport(type) {
            const allCards = document.querySelectorAll('.result-card');
            
            allCards.forEach(card => {
                const isMatch = card.dataset.match === 'true';
                const distance = parseInt(card.dataset.distance) || 999;
                
                let show = true;
                switch(type) {
                    case 'matches':
                        show = isMatch;
                        break;
                    case 'distance-25':
                        show = isMatch && distance <= 25;
                        break;
                    case 'distance-20':
                        show = isMatch && distance <= 20;
                        break;
                    case 'distance-15':
                        show = isMatch && distance <= 15;
                        break;
                    case 'all':
                        show = true;
                        break;
                }
                card.style.display = show ? 'block' : 'none';
            });
        }
    </script>
</body>
</html>
"""
    
    # Save the HTML
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"✅ HTML report generated: {output_path}")
    print(f"   Open it in your browser: file://{output_path.absolute()}")


if __name__ == "__main__":
    import sys
    
    # Get result files from command line or use all
    result_files = sys.argv[1:] if len(sys.argv) > 1 else None
    
    # Load results
    results = load_results(result_files)
    
    if not results:
        print("❌ No results found to generate report")
        sys.exit(1)
    
    # Generate report
    generate_html_report(results)
