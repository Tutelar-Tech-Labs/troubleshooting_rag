import json
from pathlib import Path

def deduplicate_by_title():
    base_dir = Path(__file__).resolve().parents[1]
    kb_path = base_dir / "data" / "full_kbs.json"
    output_path = base_dir / "data" / "full_kbs_deduped.json"

    if not kb_path.exists():
        print(f"File not found: {kb_path}")
        return

    with open(kb_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    seen_titles = set()
    unique_articles = []
    
    for article in data:
        title = article.get("title", "").strip()
        if title not in seen_titles:
            unique_articles.append(article)
            seen_titles.add(title)
    
    print(f"Original articles: {len(data)}")
    print(f"Unique articles: {len(unique_articles)}")
    print(f"Duplicates removed: {len(data) - len(unique_articles)}")

    # Overwrite the original full_kbs.json to keep pipeline simple
    with open(kb_path, "w", encoding="utf-8") as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)
    
    # Also save a backup just in case
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(unique_articles, f, ensure_ascii=False, indent=2)

    print("Deduplicated data saved to full_kbs.json and full_kbs_deduped.json")

if __name__ == "__main__":
    deduplicate_by_title()
