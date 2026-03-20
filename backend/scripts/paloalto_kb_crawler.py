"""
Palo Alto Networks GlobalProtect KB Crawler (Full)
===================================================
Scrapes ALL GlobalProtect articles by:
1. Starting from the Resource List page (seed ~212 links)
2. Recursively following kA10g links found inside each article (spider)
3. No article limit — captures everything reachable

No Selenium or login required.
"""

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Set

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

RESOURCE_LIST_URL = "https://knowledgebase.paloaltonetworks.com/KCSArticleDetail?id=kA10g000000ClfXCAS"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

KB_ID_PATTERN = re.compile(r"(kA1[0-9a-zA-Z]{2,})")
RESOURCE_LIST_ID = "kA10g000000ClfXCAS"


def normalize_url(kb_id: str) -> str:
    """Build a canonical article URL from a KB ID."""
    return f"https://knowledgebase.paloaltonetworks.com/KCSArticleDetail?id={kb_id}"


def extract_kb_ids_from_html(html: str) -> Set[str]:
    """Pull every unique kA1* ID from raw HTML."""
    return set(KB_ID_PATTERN.findall(html)) - {RESOURCE_LIST_ID}


def collect_seed_links() -> Set[str]:
    """Fetch the GlobalProtect Resource List and extract all KB IDs."""
    print(f"[1/3] Fetching seed links from Resource List...")
    resp = requests.get(RESOURCE_LIST_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    ids = extract_kb_ids_from_html(resp.text)
    print(f"      Found {len(ids)} unique KB IDs from Resource List.")
    return ids


def extract_article(url: str) -> tuple:
    """
    Download article, extract title+content, and discover linked KB IDs.
    Returns (article_dict_or_None, set_of_discovered_kb_ids).
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as e:
        return None, set()

    html = resp.text
    soup = BeautifulSoup(html, "html.parser")

    # Discover new KB IDs linked from this article
    discovered = extract_kb_ids_from_html(html)

    # Title
    title_tag = soup.find("h1")
    title = title_tag.get_text(strip=True) if title_tag else ""
    if not title:
        title = url

    # Content — try selectors in priority order
    selectors = [
        "div.slds-rich-text-editor__output",
        "div.lia-message-template-content-zone",
        "article",
        "div.content-body",
        "div.cKnowledgeArticle",
        "div[class*='article']",
        "main",
    ]

    content = ""
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            content = node.get_text(separator="\n", strip=True)
            if len(content) >= 100:
                break

    if len(content) < 100:
        return None, discovered

    return {"title": title, "url": url, "content": content}, discovered


def main() -> None:
    data_dir = BASE_DIR / "data"
    os.makedirs(data_dir, exist_ok=True)
    kb_path = data_dir / "full_kbs.json"

    print("=" * 60)
    print("  Palo Alto GlobalProtect KB Crawler (FULL — No Limit)")
    print("=" * 60)

    # Step 1 — Seed from resource list
    all_ids = collect_seed_links()
    queue = list(all_ids)
    visited: Set[str] = set()
    articles = []
    failed = 0

    # Step 2 — Spider: process queue, discover new IDs from each article
    print(f"\n[2/3] Spidering articles (seed: {len(queue)}, discovering more as we go)...\n")

    while queue:
        kb_id = queue.pop(0)

        if kb_id in visited:
            continue
        visited.add(kb_id)

        url = normalize_url(kb_id)
        article, discovered_ids = extract_article(url)

        if article:
            articles.append(article)
        else:
            failed += 1

        # Add any newly discovered IDs to the queue
        new_ids = discovered_ids - visited - set(queue)
        if new_ids:
            queue.extend(new_ids)

        # Progress reporting every 20
        total_processed = len(visited)
        if total_processed % 20 == 0 or not queue:
            remaining = len(queue)
            print(
                f"      Processed: {total_processed} | "
                f"Saved: {len(articles)} | "
                f"Skipped: {failed} | "
                f"Queue: {remaining}"
            )

        # Progressive save every 50 articles
        if len(articles) % 50 == 0 and len(articles) > 0:
            with open(kb_path, "w", encoding="utf-8") as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)

        # Polite delay
        time.sleep(0.3)

    # Step 3 — Final save
    print(f"\n[3/3] Writing {len(articles)} articles to {kb_path}")
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print(f"  DONE: {len(articles)} articles saved, {failed} skipped.")
    print(f"  Total KB IDs discovered: {len(visited)}")
    print(f"  Output: {kb_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
