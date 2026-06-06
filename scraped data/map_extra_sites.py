#!/usr/bin/env python3
"""
Map additional sites related to San Diego Safari Park and create an extended sitemap.
Handles sites to MAP (find all links) and sites to NOTE (for scraping later).
"""

import os
import requests
from datetime import datetime
from urllib.parse import urlparse


def normalize_url(url: str) -> str:
    """Normalize URL: https://, strip trailing slashes, lowercase domain."""
    url = url.strip()

    if url.startswith(('mailto:', 'tel:', 'javascript:')):
        return None

    # Remove fragment
    url = url.split('#')[0]

    parsed = urlparse(url)
    if not parsed.netloc:
        return None

    netloc = parsed.netloc.lower()
    if netloc.startswith('www.'):
        netloc = netloc[4:]

    path = parsed.path
    if path.endswith('/') and len(path) > 1:
        path = path[:-1]

    normalized = f"https://{netloc}{path}"
    if parsed.query:
        normalized += f"?{parsed.query}"

    return normalized


def map_site(api_key: str, url: str, limit: int = 5000) -> list:
    """Call Firecrawl map endpoint and return list of URLs."""
    print(f"  Mapping {url}...")

    try:
        response = requests.post(
            'https://api.firecrawl.dev/v1/map',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'url': url,
                'includeSubdomains': False,
                'sitemapOnly': False,
                'limit': limit
            },
            timeout=300  # 5 minute timeout for large maps
        )

        print(f"    Status code: {response.status_code}")

        response.raise_for_status()
        data = response.json()

        # Extract URLs from response
        urls = data.get('links', data.get('urls', []))

        print(f"    URLs found: {len(urls)}")
        return urls

    except requests.exceptions.RequestException as e:
        print(f"    Error mapping {url}: {e}")
        return []
    except Exception as e:
        print(f"    Unexpected error: {e}")
        return []


def main():
    # Get API key from environment
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable is not set")
        print("Please set it with: $env:FIRECRAWL_API_KEY = 'your-key'")
        return

    print("=" * 70)
    print("MAPPING ADDITIONAL SITES")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Track results
    all_results = {}

    # =============================================================
    # SITE 1: events.sandiegozoo.org
    # =============================================================
    print("[1/2] Mapping events.sandiegozoo.org...")
    events_urls = map_site(
        api_key=api_key,
        url='https://events.sandiegozoo.org/',
        limit=5000
    )

    # Normalize and deduplicate
    events_normalized = set()
    for url in events_urls:
        normalized = normalize_url(url)
        if normalized and 'events.sandiegozoo.org' in normalized:
            events_normalized.add(normalized)

    events_final = sorted(list(events_normalized))
    all_results['events.sandiegozoo.org'] = events_final
    print(f"    Final unique URLs: {len(events_final)}")
    print()

    # =============================================================
    # SITE 2: zoodeals.com
    # =============================================================
    print("[2/2] Mapping zoodeals.com...")
    zoodeals_urls = map_site(
        api_key=api_key,
        url='https://zoodeals.com/site/welcome/4952/places-to-stay',
        limit=500
    )

    # Normalize and deduplicate
    zoodeals_normalized = set()
    for url in zoodeals_urls:
        normalized = normalize_url(url)
        if normalized and 'zoodeals.com' in normalized:
            zoodeals_normalized.add(normalized)

    zoodeals_final = sorted(list(zoodeals_normalized))
    all_results['zoodeals.com'] = zoodeals_final
    print(f"    Final unique URLs: {len(zoodeals_final)}")
    print()

    # =============================================================
    # WRITE OUTPUT FILE
    # =============================================================
    output_filename = "safari_park_sitemap_more.txt"

    print(f"Writing results to {output_filename}...")

    with open(output_filename, 'w', encoding='utf-8') as f:
        # Header
        f.write("=" * 70 + "\n")
        f.write("SAN DIEGO SAFARI PARK - EXTENDED SITEMAP\n")
        f.write("Additional sites and resources for voice agent knowledge base\n")
        f.write(f"Generated: {datetime.now().isoformat()}\n")
        f.write("=" * 70 + "\n\n")

        # =============================================================
        # SECTION 1: ADDITIONAL MAPPED SITES
        # =============================================================
        f.write("=" * 70 + "\n")
        f.write("SECTION 1: ADDITIONAL MAPPED SITES\n")
        f.write("=" * 70 + "\n")
        f.write("These sites were mapped using the Firecrawl REST API\n")
        f.write("(POST to https://api.firecrawl.dev/v1/map)\n\n")

        # events.sandiegozoo.org
        f.write("=== events.sandiegozoo.org URLS ===\n")
        f.write(f"Source: https://events.sandiegozoo.org/\n")
        f.write(f"Total URLs found: {len(events_final)}\n\n")
        for url in events_final:
            f.write(url + "\n")
        f.write("\n")

        # zoodeals.com
        f.write("=== zoodeals.com URLS ===\n")
        f.write(f"Source: https://zoodeals.com/site/welcome/4952/places-to-stay\n")
        f.write(f"Total URLs found: {len(zoodeals_final)}\n\n")
        for url in zoodeals_final:
            f.write(url + "\n")
        f.write("\n")

        # =============================================================
        # SECTION 2: SINGLE PAGES — SCRAPE ONLY (NO MAPPING NEEDED)
        # =============================================================
        f.write("=" * 70 + "\n")
        f.write("SECTION 2: SINGLE PAGES — SCRAPE ONLY (NO MAPPING NEEDED)\n")
        f.write("=" * 70 + "\n")
        f.write("These are single pages, not sites to map. Scrape them directly.\n\n")

        # Membership page
        f.write("=== sandiegozoowildlifealliance.org — MEMBERSHIP PAGE ===\n")
        f.write("https://sandiegozoowildlifealliance.org/membership\n\n")
        f.write("NOTE: Membership info — useful for agent to answer questions \n")
        f.write("about membership pricing and benefits. Do not map, scrape page directly.\n\n")

        # About page
        f.write("=== sandiegozoowildlifealliance.org — ABOUT PAGE ===\n")
        f.write("https://sandiegozoowildlifealliance.org/about-us/about-san-diego-zoo-wildlife-alliance\n\n")
        f.write("NOTE: Mission and overview of San Diego Zoo Wildlife Alliance \n")
        f.write("(parent org of Safari Park and Zoo). Do not map, scrape directly.\n\n")

        # =============================================================
        # SECTION 3: AGENT BEHAVIOR NOTES
        # =============================================================
        f.write("=" * 70 + "\n")
        f.write("SECTION 3: AGENT BEHAVIOR NOTES\n")
        f.write("=" * 70 + "\n\n")

        f.write("- zoodeals.com: If user asks about places to stay near Safari Park, \n")
        f.write("  direct them to zoodeals.com/site/welcome/4952/places-to-stay \n")
        f.write("  or offer to transfer to a reservations agent. Do not attempt to book.\n\n")

        f.write("- events.sandiegozoo.org: If user asks about events or booking, \n")
        f.write("  direct them to events.sandiegozoo.org or transfer to a live agent.\n\n")

        f.write("- membership: If user asks about membership, direct them to \n")
        f.write("  sandiegozoowildlifealliance.org/membership\n\n")

    print(f"Saved to {output_filename}")
    print()

    # =============================================================
    # SUMMARY
    # =============================================================
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("Mapped sites:")
    for domain, urls in all_results.items():
        print(f"  {domain}: {len(urls)} URLs")
    print()
    print("Single pages to scrape:")
    print("  - https://sandiegozoowildlifealliance.org/membership")
    print("  - https://sandiegozoowildlifealliance.org/about-us/about-san-diego-zoo-wildlife-alliance")
    print()
    print(f"Output file: {output_filename}")
    print("=" * 70)


if __name__ == "__main__":
    main()
