#!/usr/bin/env python3
"""
Map the entire San Diego Safari Park website using Firecrawl's MAP endpoint.
Finds every reachable URL within the domain, deduplicates, filters, and saves results.
"""

import os
import re
import json
import requests
from datetime import datetime
from urllib.parse import urlparse, urljoin
from collections import Counter


def normalize_url(url: str) -> str:
    """
    Normalize URL for deduplication:
    - Convert to https://
    - Strip trailing slashes
    - Lowercase the domain
    - Remove www. prefix
    """
    # Strip whitespace
    url = url.strip()

    # Skip non-HTTP URLs (mailto, tel, javascript)
    if url.startswith(('mailto:', 'tel:', 'javascript:')):
        return None

    # Remove fragment identifiers (#)
    url = url.split('#')[0]

    # Parse URL
    parsed = urlparse(url)

    # Skip if no netloc (relative URLs that couldn't be resolved)
    if not parsed.netloc:
        return None

    # Lowercase the domain
    netloc = parsed.netloc.lower()

    # Remove www. prefix
    if netloc.startswith('www.'):
        netloc = netloc[4:]

    # Ensure https
    scheme = 'https'

    # Build path without trailing slash (unless it's just "/")
    path = parsed.path
    if path.endswith('/') and len(path) > 1:
        path = path[:-1]

    # Rebuild URL
    normalized = f"{scheme}://{netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def should_filter_url(url: str) -> bool:
    """
    Filter out URLs containing unwanted path segments.
    Returns True if URL should be filtered out.
    """
    filter_patterns = [
        '/cart',
        '/checkout',
        '/account',
        '/login',
        '/wp-admin',
        '/wp-json',
    ]

    # Check for fragment or non-http protocols
    if '#' in url:
        return True
    if url.startswith(('mailto:', 'tel:', 'javascript:')):
        return True

    # Check path patterns
    url_lower = url.lower()
    for pattern in filter_patterns:
        if pattern in url_lower:
            return True

    return False


def get_top_level_path(url: str) -> str:
    """Extract the top-level path segment for grouping."""
    parsed = urlparse(url)
    path = parsed.path

    if not path or path == '/':
        return '/ (root)'

    # Split path and get first non-empty segment
    parts = [p for p in path.split('/') if p]
    if parts:
        return f"/{parts[0]}"
    return '/ (root)'


def main():
    # Get API key from environment
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable is not set")
        print("Please set it with: $env:FIRECRAWL_API_KEY = 'your-key'")
        return

    base_url = "https://sdzsafaripark.org"

    print(f"Mapping {base_url}...")
    print("This may take a few minutes depending on site size.")
    print("-" * 60)

    # Call the Firecrawl REST API directly
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Calling Firecrawl /v1/map endpoint...")

    try:
        response = requests.post(
            'https://api.firecrawl.dev/v1/map',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'url': base_url,
                'includeSubdomains': False,
                'sitemapOnly': False,
                'limit': 5000
            }
        )

        print(f"Status code: {response.status_code}")

        # Print full raw response for debugging
        raw_text = response.text
        print(f"\nRaw response (first 2000 chars):")
        print(raw_text[:2000])
        if len(raw_text) > 2000:
            print("... [truncated]")

        response.raise_for_status()

        data = response.json()

        # The links are in data['links'] or data['urls'] — check both
        urls = data.get('links', data.get('urls', []))

        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Map request completed.")
        print(f"URLs found: {len(urls)}")

    except requests.exceptions.RequestException as e:
        print(f"\nError calling Firecrawl API: {e}")
        return
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        return

    total_raw = len(urls)
    print(f"\nTotal URLs found (before dedup): {total_raw}")

    # Normalize and deduplicate
    print("Normalizing and deduplicating URLs...")
    normalized_urls = set()
    filtered_count = 0

    for url in urls:
        # Filter first
        if should_filter_url(url):
            filtered_count += 1
            continue

        # Normalize
        normalized = normalize_url(url)
        if normalized:
            normalized_urls.add(normalized)

    # Convert to sorted list
    final_urls = sorted(list(normalized_urls))
    total_final = len(final_urls)

    print(f"URLs after dedup and filtering: {total_final}")
    print(f"Filtered out: {filtered_count} URLs")

    # Save to TXT file
    txt_filename = "safari_park_sitemap.txt"
    with open(txt_filename, 'w', encoding='utf-8') as f:
        for url in final_urls:
            f.write(url + '\n')

    print(f"\nSaved {total_final} URLs to {txt_filename}")

    # Save to JSON file
    json_filename = "safari_park_sitemap.json"
    json_data = {
        "domain": "sdzsafaripark.org",
        "total_urls": total_final,
        "scraped_at": datetime.now().isoformat(),
        "urls": final_urls
    }

    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=2, ensure_ascii=False)

    print(f"Saved JSON metadata to {json_filename}")

    # Generate grouped breakdown
    print("\n" + "=" * 60)
    print("GROUPED BREAKDOWN BY PATH")
    print("=" * 60)

    path_groups = Counter(get_top_level_path(url) for url in final_urls)

    # Sort by count (descending), then alphabetically
    sorted_groups = sorted(path_groups.items(), key=lambda x: (-x[1], x[0]))

    for path, count in sorted_groups:
        print(f"  {path:<25} → {count} URLs")

    print("=" * 60)

    # Final summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Base URL:            {base_url}")
    print(f"Total URLs (raw):    {total_raw}")
    print(f"Total URLs (final):  {total_final}")
    print(f"Filtered out:        {filtered_count}")
    print(f"Unique path groups:  {len(path_groups)}")
    print(f"Output files:")
    print(f"  - {txt_filename}")
    print(f"  - {json_filename}")
    print("=" * 60)

    # Show sample of found URLs
    print("\nSample URLs found:")
    for url in final_urls[:10]:
        print(f"  {url}")
    if len(final_urls) > 10:
        print(f"  ... and {len(final_urls) - 10} more")


if __name__ == "__main__":
    main()
