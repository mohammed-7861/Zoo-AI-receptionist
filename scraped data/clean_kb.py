#!/usr/bin/env python3
"""
Clean Safari Park knowledge base for VAPI voice AI agent.
Processes safari_park_combined.txt and outputs safari_park_clean.txt
"""

import re
from pathlib import Path


# Lines that indicate "boring" pages to skip entirely
SKIP_PAGE_URL_PATTERNS = [
    r'accessibility-statement',
    r'cookie',
    r'privacy',
    r'terms(?:-of-use)?',
    r'legal',
    r'field-trip-form',
    r'-form$',
]

# Navigation artifacts to remove
NAVIGATION_PATTERNS = [
    r'^Menu$',
    r'^\s*-\s+\[',  # Menu items like "- [Visit]"
    r'^\[Close submenu\]',
    r'^\[Open submenu\]',
    r'^\[Skip to main content\]',
    r'^\[Close menu\]',
    r'^Open submenu',
    r'^Close submenu',
    r'^Skip to main content',
    r'^Close menu',
    r'^\d+\.\s*\[\d+\]$',  # Pagination like "1. [1]"
    r'^-\s*\[Previous\]',
    r'^-\s*\[Next\]',
    r'^\d+\.\s*$',  # Numbered items that are just numbers
    r'^\d+\.\s*\[\d+\]\s*$',  # Lines like "1. [1]"
    r'^\d+\.\s*$',  # Just numbers with dots
    # Video player controls
    r'^Play$',
    r'^Pause$',
    r'^CC/subtitles',
    r'^Picture-in-Picture',
    r'^Fullscreen',
    r'^Settings',
    r'^Transcript',
    r'^Off$',
    r'^Playing in',
    r'^from (?:SDZWA|Vimeo)',
]

# Ad and promotional content to remove
AD_PATTERNS = [
    r'FILL YOUR TRUNK',
    r'ELEPHANT VALLEY GEAR IS HERE',
    r'Places to Stay',
    r'Book Your Room',
    r'Take a Wildlife Safari',
    r'Come Travel with Us',
    r'Wild Weddings',
    r'FEEL GOOD ABOUT BOOKING WITH US',
    r'SHOP NOW',
    r'Preferred Hotels',
    r'SDZWA Adventures',
    r'^Safaris$',  # As standalone heading in ad
    r'^Learn More$',  # Generic CTA
    r'^LEARN MORE$',  # Generic CTA
    r'^Join Us$',  # Generic CTA
    r'^Donate Today$',  # Generic CTA
    r'Become An Ally',
    r'Membership\s*▸',
    r'Donate\s*▸',
    r'Volunteer\s*▸',
]

# Phrases that indicate navigation content (comma-separated lists of menu items)
NAVIGATION_PHRASES = [
    r'Open submenu.*Close submenu',
    r'Visit.*Safaris.*Things to Do',
    r'Membership.*Plan Your Visit',
    r'Safaris.*Activities.*Youth Programs',
    r'View All.*Live Cameras',
    r'Mission.*Conservation.*Membership',
    r'Give Once.*Give Monthly',
    r'Previous.*Next',
]


def remove_markdown_images(text):
    """Remove all markdown image references: ![...](...)"""
    return re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)


def remove_markdown_links(text):
    """Remove markdown links but keep the label text: [text](url) -> text"""
    return re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)


def remove_raw_urls(text):
    """Remove raw URLs starting with http:// or https://"""
    return re.sub(r'https?://[^\s\)]+', '', text)


def is_navigation_line(line):
    """Check if a line is navigation-related"""
    stripped = line.strip()
    if not stripped:
        return False

    for pattern in NAVIGATION_PATTERNS:
        if re.match(pattern, stripped, re.IGNORECASE):
            return True

    # Check for navigation phrase patterns (comma-separated menu items)
    # These are lines that look like: "Visit Open submenu, Safaris, Things to Do..."
    if re.search(r'\b\w+\s+Open submenu\b', stripped):
        return True

    # Common standalone navigation phrases that should be removed
    standalone_nav = [
        'Help Center',
        'Plan Your Visit',
        'Skip to main content',
        'Close menu',
        'Close submenu',
        'Open submenu',
        'Menu',
        'View All',
        'Live Cameras',
        'Videos',
    ]
    if stripped in standalone_nav:
        return True

    # Navigation phrases containing these patterns
    nav_phrases = [
        'Student & Youth Groups',
        'Events & Catering',
        'Youth Programs',
        'Plan Your Visit',
        'Help Center',
        'View All, Live Cameras',
    ]
    for phrase in nav_phrases:
        if phrase in stripped:
            return True

    # Lines that are just comma-separated lists of capitalized menu items
    # Check for patterns like "Activities, Youth Programs, Student & Youth Groups, Events & Catering, and Weddings"
    if re.match(r'^([A-Z][a-z]+(?:\s+\&?\s*[A-Z][a-z]+)?(?:,\s*(?:and\s+)?|$))+$', stripped):
        # Check if it contains common menu words
        menu_words = ['Visit', 'Safaris', 'Membership', 'Shop', 'Wildlife', 'Support', 'Mission', 'Tickets', 'Plan', 'Things', 'Dining', 'Events', 'Activities', 'Programs', 'Groups', 'Cameras', 'Videos']
        if any(word in stripped for word in menu_words):
            return True

    # Check for simple lists of menu-like items separated by commas and "and"
    # Pattern: "Word, Word, Word, and Word" where words are capitalized
    if re.search(r'(?:[A-Z][a-z]+(?:\s[A-Z][a-z]+)?(?:,\s+|$))+(?:and\s+[A-Z][a-z]+)', stripped):
        menu_indicators = ['Visit', 'Safaris', 'Activities', 'Dining', 'Events', 'Youth', 'Groups', 'Cameras', 'Videos', 'Membership', 'Plan']
        if any(word in stripped for word in menu_indicators):
            return True

    return False


def is_ad_line(line):
    """Check if a line is part of an ad or promotional block"""
    stripped = line.strip()
    if not stripped:
        return False

    for pattern in AD_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return True

    return False


def is_content_free(line):
    """Check if a line has no meaningful content"""
    stripped = line.strip()
    if not stripped:
        return True

    # Empty brackets artifacts
    if stripped == '[]':
        return True
    if re.match(r'^\[\s*\(\)\s*\]$', stripped):
        return True
    if re.match(r'^\[\(\)\]$', stripped):
        return True

    # Lines that are just symbols
    if re.match(r'^[\s\-\*\|>_:;,"\'\.\(\)\[\]]*$', stripped):
        return True

    # Video player artifacts
    if re.match(r'^[Pp]laying in', stripped):
        return True

    return False


def convert_headings(text):
    """Convert markdown headings to plain text CAPS"""
    lines = text.split('\n')
    result = []

    for line in lines:
        stripped = line.strip()

        # Convert ## style headings to CAPS (handles # to ######)
        if re.match(r'^#{1,6}\s+', stripped):
            # Remove # symbols and convert to caps
            heading_text = re.sub(r'^#{1,6}\s*', '', stripped).strip()
            # Also remove any bold markers
            heading_text = re.sub(r'^\*\*\s*', '', heading_text)
            heading_text = re.sub(r'\s*\*\*$', '', heading_text)
            heading_text = heading_text.strip()
            if heading_text:
                result.append(heading_text.upper())
        else:
            result.append(line)

    return '\n'.join(result)


def is_nav_bullet_text(text):
    """Check if a bullet text is navigation content that should be removed"""
    # Short text that's mostly navigation words
    nav_words = ['Visit', 'Safaris', 'Activities', 'Programs', 'Groups', 'Events', 'Weddings', 'Help', 'Membership', 'Shop', 'Wildlife', 'Support', 'Mission', 'Tickets', 'Plan', 'Things', 'Dining', 'Cameras', 'Videos', 'View', 'All']
    words = text.split()
    if len(words) <= 5:
        nav_word_count = sum(1 for w in words if any(nav in w for nav in nav_words))
        if nav_word_count >= len(words) * 0.5:  # If half the words are nav words
            return True
    return False


def clean_bullet_points(text):
    """Convert markdown bullet points to plain text sentences"""
    lines = text.split('\n')
    result = []
    bullet_items = []
    in_bullet_list = False

    for line in lines:
        stripped = line.strip()

        # Check if it's a bullet point
        bullet_match = re.match(r'^[-\*]\s+(.+)$', stripped)

        if bullet_match:
            content = bullet_match.group(1).strip()
            # Clean up the content
            content = remove_raw_urls(content)
            # Skip navigation/ad content in bullets
            if content and not is_navigation_line(content) and not is_ad_line(content) and not is_nav_bullet_text(content):
                bullet_items.append(content)
            in_bullet_list = True
        else:
            # If we were in a bullet list, output it
            if in_bullet_list and bullet_items:
                # Convert bullet items to a sentence
                if len(bullet_items) == 1:
                    result.append(bullet_items[0])
                elif len(bullet_items) == 2:
                    result.append(f"{bullet_items[0]} and {bullet_items[1]}")
                else:
                    bullet_text = ", ".join(bullet_items[:-1]) + f", and {bullet_items[-1]}"
                    result.append(bullet_text)
                bullet_items = []
                in_bullet_list = False

            result.append(line)

    # Handle any remaining bullet items at end
    if in_bullet_list and bullet_items:
        if len(bullet_items) == 1:
            result.append(bullet_items[0])
        elif len(bullet_items) == 2:
            result.append(f"{bullet_items[0]} and {bullet_items[1]}")
        else:
            bullet_text = ", ".join(bullet_items[:-1]) + f", and {bullet_items[-1]}"
            result.append(bullet_text)

    return '\n'.join(result)


def remove_duplicate_blank_lines(text):
    """Replace multiple blank lines with a single blank line"""
    lines = text.split('\n')
    result = []
    prev_blank = False

    for line in lines:
        is_blank = not line.strip()
        if is_blank and prev_blank:
            continue
        result.append(line)
        prev_blank = is_blank

    return '\n'.join(result)


def clean_line(line):
    """Clean up a single line of text"""
    stripped = line.strip()

    # Skip navigation lines
    if is_navigation_line(stripped):
        return None

    # Skip ad lines
    if is_ad_line(stripped):
        return None

    # Skip content-free lines
    if is_content_free(stripped):
        return None

    # Clean up stray artifacts
    # Remove empty brackets
    cleaned = re.sub(r'\[\s*\(\)\s*\]', '', stripped)
    cleaned = re.sub(r'\[\(\)\]', '', cleaned)
    cleaned = re.sub(r'\[\]', '', cleaned)

    # Remove markdown heading markers that might have been missed and convert to plain text
    if re.match(r'^#{1,6}\s+', cleaned):
        cleaned = re.sub(r'^#{1,6}\s*', '', cleaned).strip()
        cleaned = cleaned.upper()

    # Remove special unicode artifacts
    cleaned = cleaned.replace('\\', '')

    # Skip if line is now empty after cleaning
    if not cleaned.strip():
        return None

    return cleaned  # Return cleaned line


def clean_page(page_content, page_title):
    """Clean a single page of content"""
    # Step 1: Remove markdown images
    text = remove_markdown_images(page_content)

    # Step 2: Remove markdown links (keep text)
    text = remove_markdown_links(text)

    # Step 3: Remove raw URLs
    text = remove_raw_urls(text)

    # Step 4: Convert headings to CAPS (before other cleaning)
    text = convert_headings(text)

    # Step 5: Clean bullet points
    text = clean_bullet_points(text)

    # Step 6: Clean individual lines
    lines = text.split('\n')
    cleaned_lines = []

    for line in lines:
        cleaned = clean_line(line)
        if cleaned is not None:
            cleaned_lines.append(cleaned)

    # Step 7: Remove duplicate blank lines
    text = '\n'.join(cleaned_lines)
    text = remove_duplicate_blank_lines(text)

    return text


def extract_page_title(page_header):
    """Extract a clean page title from the page header URL"""
    # Extract URL from ===== PAGE: URL ===== format
    match = re.search(r'===== PAGE:\s*(.+?)\s*=====', page_header)
    if match:
        url = match.group(1)
        # Extract the last part of the path
        path = url.split('/')[-1]
        if path:
            # Remove query parameters and clean up
            path = path.split('?')[0]
            path = path.split('#')[0]
            path = path.replace('-', ' ').replace('_', ' ')
            # Clean up common patterns
            path = re.sub(r'\s+', ' ', path).strip()
            if path:
                return path.upper()
    return "UNKNOWN"


def is_boring_page_url(url):
    """Check if page should be skipped entirely based on URL"""
    url_lower = url.lower()
    for pattern in SKIP_PAGE_URL_PATTERNS:
        if re.search(pattern, url_lower):
            return True
    return False


def process_file(input_path, output_path):
    """Main processing function"""
    input_path = Path(input_path)
    output_path = Path(output_path)

    # Read the input file
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into pages using the page separator pattern
    # Pattern matches lines like: ===== PAGE: https://... =====
    page_split_pattern = r'(===== PAGE:[^=]+=====)'
    parts = re.split(page_split_pattern, content)

    pages_processed = 0
    pages_skipped = 0
    unique_content_hashes = set()
    output_pages = []

    i = 0
    while i < len(parts):
        part = parts[i].strip()

        # Check if this is a page header
        if part.startswith('===== PAGE:'):
            # Extract the URL from the header
            url_match = re.search(r'===== PAGE:\s*(.+?)\s*=====', part)
            page_url = url_match.group(1) if url_match else ""
            page_title = extract_page_title(part)

            # Check if this is a boring page to skip
            if is_boring_page_url(page_url):
                pages_skipped += 1
                i += 2  # Skip header and content
                continue

            # Get the page content
            if i + 1 < len(parts):
                page_content = parts[i + 1]
            else:
                page_content = ""

            # Clean the page
            cleaned = clean_page(page_content, page_title)

            # Check if page has meaningful content after cleaning
            meaningful_text = ' '.join(cleaned.split())
            if len(meaningful_text) < 100:  # Skip very short pages
                pages_skipped += 1
                i += 2
                continue

            # Check for exact duplicates using hash of meaningful content
            content_hash = hash(meaningful_text[:800])  # First 800 chars
            if content_hash in unique_content_hashes:
                pages_skipped += 1
                i += 2
                continue
            unique_content_hashes.add(content_hash)

            # Format the cleaned page
            formatted_page = f"--- {page_title} ---\n\n{cleaned.strip()}"
            output_pages.append(formatted_page)
            pages_processed += 1

            i += 2
        else:
            # Not a page header, skip
            i += 1

    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=" * 79 + "\n")
        f.write("SAN DIEGO ZOO SAFARI PARK KNOWLEDGE BASE\n")
        f.write("=" * 79 + "\n")
        f.write("\n")

        for i, page in enumerate(output_pages):
            if i > 0:
                f.write("\n")
            f.write("=" * 79 + "\n")
            f.write(page)
            f.write("\n")

    # Count lines in output
    with open(output_path, 'r', encoding='utf-8') as f:
        output_lines = len(f.readlines())

    return pages_processed, pages_skipped, output_lines


if __name__ == "__main__":
    input_file = "safari_park_combined.txt"
    output_file = "safari_park_clean.txt"

    print("Cleaning Safari Park knowledge base...")
    print(f"Input: {input_file}")
    print(f"Output: {output_file}")
    print()

    processed, skipped, lines = process_file(input_file, output_file)

    print("=" * 50)
    print("CLEANING COMPLETE")
    print("=" * 50)
    print(f"Pages processed: {processed}")
    print(f"Pages skipped: {skipped}")
    print(f"Output file line count: {lines}")
    print()
    print(f"Cleaned knowledge base saved to: {output_file}")
