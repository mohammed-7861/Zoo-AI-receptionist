#!/usr/bin/env python3
"""
Scrape San Diego Safari Park website using Firecrawl REST API.
Reads URLs from sitemap files and scrapes each one individually.
Optimized for RAG with voice agent (Vapi).
"""

import os
import re
import json
import time
import requests
from datetime import datetime
from urllib.parse import urlparse


def clean_markdown(text: str) -> str:
    """Collapse 3+ consecutive blank lines into one."""
    cleaned = re.sub(r'\n{3,}', '\n\n', text)
    return cleaned.strip()


def parse_simple_sitemap(filepath: str) -> list:
    """
    Parse safari_park_sitemap.txt format.
    Every line is a URL. Skip blank lines and lines starting with # or =
    """
    urls = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines
            if not line:
                continue
            # Skip comment lines
            if line.startswith('#') or line.startswith('='):
                continue
            # Valid URL line
            urls.append(line)
    return urls


def parse_extended_sitemap(filepath: str) -> list:
    """
    Parse safari_park_sitemap_more.txt format.
    Extract any line that starts with http:// or https://
    Skip lines starting with "NOTE:", skip "AGENT BEHAVIOR NOTES" section entirely.
    """
    urls = []
    in_agent_notes_section = False

    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            original_line = line
            line = line.strip()

            # Skip empty lines
            if not line:
                continue

            # Check for section headers
            if 'AGENT BEHAVIOR NOTES' in line:
                in_agent_notes_section = True
                continue

            # If we're in agent notes section, skip everything until EOF or new section
            if in_agent_notes_section:
                continue

            # Skip NOTE: lines
            if line.startswith('NOTE:'):
                continue

            # Check if line starts with http (URL)
            if line.startswith('http://') or line.startswith('https://'):
                urls.append(line)

    return urls


def scrape_url(api_key: str, url: str) -> dict:
    """
    Scrape a single URL using Firecrawl REST API.
    Returns dict with source, title, text or None if failed.
    """
    try:
        response = requests.post(
            'https://api.firecrawl.dev/v1/scrape',
            headers={
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            },
            json={
                'url': url,
                'formats': ['markdown'],
                'onlyMainContent': True
            },
            timeout=60
        )

        response.raise_for_status()
        data = response.json()

        # Extract data from response
        # Handle different response structures
        if 'data' in data:
            page_data = data['data']
        else:
            page_data = data

        markdown = page_data.get('markdown', '')
        metadata = page_data.get('metadata', {})
        title = metadata.get('title', '')

        # Fallback title: use URL path if no title
        if not title:
            parsed = urlparse(url)
            title = parsed.path.strip('/') or 'Home'
            title = title.replace('/', ' ').replace('-', ' ').title()

        # Clean the markdown
        cleaned_text = clean_markdown(markdown)

        return {
            'source': url,
            'title': title,
            'text': cleaned_text,
            'success': True
        }

    except requests.exceptions.RequestException as e:
        return {
            'source': url,
            'success': False,
            'error': str(e)
        }
    except Exception as e:
        return {
            'source': url,
            'success': False,
            'error': str(e)
        }


def main():
    # Get API key from environment
    api_key = os.environ.get('FIRECRAWL_API_KEY')
    if not api_key:
        print("Error: FIRECRAWL_API_KEY environment variable is not set")
        print("Please set it with: $env:FIRECRAWL_API_KEY = 'your-key'")
        return

    # Check for input files
    simple_sitemap = "safari_park_sitemap.txt"
    extended_sitemap = "safari_park_sitemap_more.txt"

    all_urls = []

    # Read simple sitemap
    if os.path.exists(simple_sitemap):
        print(f"Reading {simple_sitemap}...")
        urls = parse_simple_sitemap(simple_sitemap)
        print(f"  Found {len(urls)} URLs")
        all_urls.extend(urls)
    else:
        print(f"Warning: {simple_sitemap} not found, skipping")

    # Read extended sitemap
    if os.path.exists(extended_sitemap):
        print(f"Reading {extended_sitemap}...")
        urls = parse_extended_sitemap(extended_sitemap)
        print(f"  Found {len(urls)} URLs")
        all_urls.extend(urls)
    else:
        print(f"Warning: {extended_sitemap} not found, skipping")

    total_urls = len(all_urls)
    if total_urls == 0:
        print("\nError: No URLs to scrape. Please ensure sitemap files exist.")
        return

    # Deduplicate URLs
    all_urls = list(dict.fromkeys(all_urls))  # Preserves order
    unique_count = len(all_urls)
    if unique_count < total_urls:
        print(f"  Removed {total_urls - unique_count} duplicate URLs")
        total_urls = unique_count

    print(f"\nTotal URLs to scrape: {total_urls}")
    print("-" * 60)

    # Scrape each URL
    successful = []
    failed = []

    for i, url in enumerate(all_urls, 1):
        print(f"Scraping [{i}/{total_urls}] {url}")

        result = scrape_url(api_key, url)

        if result['success']:
            successful.append(result)
            print(f"  ✓ Success - Title: {result['title'][:60]}..." if len(result['title']) > 60 else f"  ✓ Success - Title: {result['title']}")
        else:
            failed.append({'url': url, 'error': result.get('error', 'Unknown error')})
            print(f"  ✗ Failed - {result.get('error', 'Unknown error')}")

        # Delay between requests to avoid rate limiting
        if i < total_urls:
            time.sleep(0.5)

    print("\n" + "-" * 60)
    print(f"Scraping complete! Processing {len(successful)} successful pages...")

    # Save JSONL file
    jsonl_filename = "safari_park_data.jsonl"
    with open(jsonl_filename, 'w', encoding='utf-8') as f:
        for entry in successful:
            jsonl_entry = {
                "source": entry['source'],
                "title": entry['title'],
                "text": entry['text']
            }
            f.write(json.dumps(jsonl_entry, ensure_ascii=False) + '\n')

    print(f"Saved {len(successful)} pages to {jsonl_filename}")

    # Save combined text file
    combined_filename = "safari_park_combined.txt"
    with open(combined_filename, 'w', encoding='utf-8') as f:
        for entry in successful:
            separator = f"\n\n===== PAGE: {entry['source']} =====\n\n"
            f.write(separator + entry['text'])

    print(f"Saved combined text to {combined_filename}")

    # Calculate stats
    total_chars = sum(len(entry['text']) for entry in successful)
    estimated_tokens = total_chars // 4

    # Final summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total URLs attempted:    {total_urls}")
    print(f"Successfully scraped:      {len(successful)}")
    print(f"Failed / skipped:        {len(failed)}")
    print(f"Total characters:        {total_chars:,}")
    print(f"Estimated tokens:        {estimated_tokens:,}")
    print("=" * 60)

    # List failed URLs
    if failed:
        print("\nFailed URLs:")
        for item in failed:
            print(f"  - {item['url']}")
            print(f"    Error: {item['error']}")
        print()

    # Verify known pages were captured
    known_pages = [
        "https://sdzsafaripark.org/safaris",
        "https://sdzsafaripark.org/safaris/wildlife-safari",
        "https://sdzsafaripark.org/safaris/flightline-safari",
        "https://sdzsafaripark.org/safaris/cart-safaris",
        "https://sdzsafaripark.org/safaris/ultimate-safari",
        "https://sdzsafaripark.org/safaris/behind-scenes-safari",
        "https://sdzsafaripark.org/safaris/roar-snore-safaris",
        "https://sdzsafaripark.org/safaris/roar-snore-girl-scouts",
        "https://sdzsafaripark.org/safaris/roar-snore-adults-only",
        "https://sdzsafaripark.org/safaris/roar-snore-school-nights",
        "https://sdzsafaripark.org/safaris/roar-snore-all-ages",
        "https://sdzsafaripark.org/safaris/wildlife-trek",
    ]

    captured_urls = {entry['source'] for entry in successful}

    print("\nVerification of known pages:")
    all_found = True
    for url in known_pages:
        found = url in captured_urls
        status = "✓" if found else "✗"
        print(f"  {status} {url}")
        if not found:
            all_found = False

    if all_found:
        print("\n✓ All known pages were successfully captured!")
    else:
        print("\n⚠ Some known pages were not captured (may not exist or failed to scrape)")


if __name__ == "__main__":
    main()
