import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Set

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from config.kb_config import MAX_ARTICLES, DELAY_SECONDS, MIN_CONTENT_LENGTH, QUERIES


def create_driver() -> webdriver.Chrome:
    options = Options()
    options.add_argument("user-data-dir=./chrome_profile")
    driver = webdriver.Chrome(options=options)
    driver.set_page_load_timeout(60)
    return driver


def load_existing_kb(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return []


def collect_search_links(driver: webdriver.Chrome) -> List[str]:
    seen: Set[str] = set()
    links: List[str] = []
    for query in QUERIES:
        url = f"https://knowledgebase.paloaltonetworks.com/?q={quote_plus(query)}"
        driver.get(url)
        time.sleep(DELAY_SECONDS)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "KCSArticleDetail" in href and "id=" in href:
                if href.startswith("/"):
                    full_url = "https://knowledgebase.paloaltonetworks.com" + href
                else:
                    full_url = href
                if full_url not in seen:
                    seen.add(full_url)
                    links.append(full_url)
            if len(links) >= MAX_ARTICLES:
                return links
    return links


def extract_article(driver: webdriver.Chrome, url: str) -> Dict[str, str]:
    driver.get(url)
    time.sleep(DELAY_SECONDS)
    html = driver.page_source
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else url

    content = ""
    for selector in [
        "div.article-body",
        "div#article-content",
        "div.slds-rich-text-editor__output",
    ]:
        node = soup.select_one(selector)
        if node:
            text = node.get_text(separator="\n", strip=True)
            if text:
                content = text
                break
    if not content:
        content = soup.get_text(separator="\n", strip=True)

    if not content or len(content) < MIN_CONTENT_LENGTH:
        return {}

    return {
        "title": title,
        "url": url,
        "content": content,
    }


def main() -> None:
    data_dir = BASE_DIR / "data"
    os.makedirs(data_dir, exist_ok=True)
    kb_path = data_dir / "full_kbs.json"

    articles = load_existing_kb(kb_path)
    existing_urls: Set[str] = set()
    for item in articles:
        url = item.get("url")
        if url:
            existing_urls.add(url)

    driver = create_driver()
    try:
        links = collect_search_links(driver)
        for url in links:
            if url in existing_urls:
                continue
            if len(articles) >= MAX_ARTICLES:
                break
            try:
                article = extract_article(driver, url)
                if not article:
                    continue
                articles.append(article)
                existing_urls.add(url)
                if len(articles) % 50 == 0:
                    with open(kb_path, "w", encoding="utf-8") as f:
                        json.dump(articles, f, ensure_ascii=False)
            except Exception:
                continue
        with open(kb_path, "w", encoding="utf-8") as f:
            json.dump(articles, f, ensure_ascii=False)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()

