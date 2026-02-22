import json
import os
from pathlib import Path
from typing import List, Dict


CHUNK_SIZE = 700
OVERLAP = 100


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP) -> List[str]:
    if not text:
        return []
    length = len(text)
    chunks: List[str] = []
    start = 0
    while start < length:
        end = min(start + chunk_size, length)
        chunks.append(text[start:end])
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks


def main():
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / "data"
    input_path = data_dir / "full_kbs.json"
    output_path = data_dir / "full_kb_chunks.json"

    with open(input_path, "r", encoding="utf-8") as f:
        articles: List[Dict[str, str]] = json.load(f)

    chunks: List[Dict[str, str]] = []
    for article in articles:
        title = article.get("title", "")
        url = article.get("url", "")
        content = article.get("content", "")
        for chunk in chunk_text(content):
            chunks.append(
                {
                    "chunk_text": chunk,
                    "article_title": title,
                    "article_url": url,
                }
            )

    os.makedirs(data_dir, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"Processed {len(articles)} articles into {len(chunks)} chunks")


if __name__ == "__main__":
    main()

