import json
import os
from pathlib import Path
from typing import List, Dict


def chunk_text(text: str, chunk_size: int = 700, overlap: int = 100) -> List[str]:
    words = text.split()
    if not words:
        return []
    chunks: List[str] = []
    start = 0
    length = len(words)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks


def build_chunks(input_path: str, output_path: str) -> List[Dict[str, str]]:
    with open(input_path, "r", encoding="utf-8") as f:
        articles = json.load(f)

    chunks: List[Dict[str, str]] = []
    for article in articles:
        title = article.get("title") or ""
        url = article.get("url") or ""
        content = article.get("content") or ""
        text_chunks = chunk_text(content)
        for text in text_chunks:
            chunks.append(
                {
                    "chunk_text": text,
                    "article_title": title,
                    "article_url": url,
                }
            )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    return chunks


if __name__ == "__main__":
    base_dir = Path(__file__).resolve().parents[2]
    data_dir = base_dir / "backend" / "data"
    input_path = data_dir / "full_kbs.json"
    output_path = data_dir / "full_kb_chunks.json"
    build_chunks(str(input_path), str(output_path))

