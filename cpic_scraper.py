"""
cpic_scraper.py  –  Scrape "Updates since publication" from a CPIC guideline page.

Logic:
  1. Find the tag whose text is "Updates since publication:"
  2. Collect the next 4 non-empty paragraphs after it

Usage:
    from cpic_scraper import scrape_cpic_updates, get_most_recent_update

Or run directly:
    python cpic_scraper.py <url>
    python cpic_scraper.py <url> --paragraphs 6
"""

from __future__ import annotations

import re
import sys
import textwrap
from typing import Optional

try:
    import requests
    from bs4 import BeautifulSoup, NavigableString, Tag
except ImportError:
    sys.exit("Install with:  pip install requests beautifulsoup4")


def _text(tag: Tag) -> str:
    return re.sub(r"\s+", " ", tag.get_text(" ", strip=True)).strip()


def scrape_cpic_updates(url: str, *, timeout: int = 20, num_paragraphs: int = 4) -> list[dict]:
    """
    Fetch *url*, find "Updates since publication:", then collect the next
    `num_paragraphs` non-empty text blocks after it.

    Returns a list with one dict:
        label  – first paragraph (up to 120 chars), used as a heading
        text   – all collected paragraphs joined together
        pmids  – list of PMID strings found in the text
    """
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    # ── 1. Find the marker tag ────────────────────────────────────────────────
    marker: Optional[Tag] = None
    for tag in soup.find_all(True):
        t = _text(tag)
        if re.search(r"updates?\s+since\s+publication", t, re.IGNORECASE) and len(t) < 160:
            marker = tag  # keep iterating → innermost match wins

    if marker is None:
        return []

    # ── 2. Walk every tag after the marker, harvest text-bearing ones ─────────
    harvest_tags = {"p", "li", "h2", "h3", "h4", "h5", "h6", "strong", "b"}
    all_tags = list(soup.find_all(True))
    try:
        start = all_tags.index(marker)
    except ValueError:
        start = 0

    paragraphs: list[str] = []
    for tag in all_tags[start + 1:]:
        if tag.name not in harvest_tags:
            continue
        t = _text(tag)
        if not t:
            continue
        # Stop at an unrelated section heading (no month/year in it)
        if tag.name in {"h2", "h3", "h4"} and not re.search(
            r"\b(january|february|march|april|may|june|july|august|"
            r"september|october|november|december|\d{4})\b", t, re.IGNORECASE
        ):
            if paragraphs:
                break
        # Skip if this text is already contained in a previous paragraph
        if any(t in prior for prior in paragraphs):
            continue
        paragraphs.append(t)
        if len(paragraphs) >= num_paragraphs:
            break

    if not paragraphs:
        return []

    full_text = " ".join(paragraphs)
    pmids = re.findall(r"PMID\s*[:\s]?(\d{6,9})", full_text)
    label = paragraphs[0][:120].rstrip() + ("..." if len(paragraphs[0]) > 120 else "")

    return [{"label": label, "text": full_text, "pmids": pmids}]


def get_most_recent_update(url: str) -> Optional[dict]:
    """Return the update block, or None if not found."""
    updates = scrape_cpic_updates(url)
    return updates[0] if updates else None


# ─── CLI ──────────────────────────────────────────────────────────────────────

def _print_update(upd: dict, width: int = 100) -> None:
    print(f"\n{'=' * width}")
    print(f"  {upd['label']}")
    print(f"{'=' * width}")
    print(textwrap.fill(upd["text"], width=width))
    if upd["pmids"]:
        print(f"\n  PMIDs referenced: {', '.join(upd['pmids'])}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:\n"
              "  python cpic_scraper.py <url>\n"
              "  python cpic_scraper.py <url> --paragraphs 6\n")
        sys.exit(0)

    target_url = sys.argv[1]
    n = int(sys.argv[sys.argv.index("--paragraphs") + 1]) if "--paragraphs" in sys.argv else 4

    print(f"Fetching: {target_url}")
    result = get_most_recent_update(target_url)
    if result is None:
        print("No updates found after 'Updates since publication:'")
    else:
        _print_update(result)
