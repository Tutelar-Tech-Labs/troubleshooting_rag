import json
import sys
from pathlib import Path
from typing import Any, Dict, List

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_kb_articles(health: Dict[str, str]) -> int:
    kb_path = DATA_DIR / "full_kbs.json"
    print("=== Check 1: KB Articles ===")
    print(f"Path: {kb_path}")
    data = load_json(kb_path)
    if not isinstance(data, list):
        print("Result: full_kbs.json NOT FOUND or invalid")
        health["KB Status"] = "Problem"
        return 0
    count = len(data)
    print(f"Result: {count} articles found")
    if count < 200:
        print("Warning: KB may be too small for robust RAG")
        health["KB Status"] = "Problem"
    return count


def check_kb_chunks(health: Dict[str, str]) -> int:
    chunks_path = DATA_DIR / "full_kb_chunks.json"
    print("\n=== Check 2: KB Chunks ===")
    print(f"Path: {chunks_path}")
    data = load_json(chunks_path)
    if not isinstance(data, list):
        print("Result: full_kb_chunks.json NOT FOUND or invalid")
        health["Chunking"] = "Problem"
        return 0
    count = len(data)
    print(f"Result: {count} chunks found")
    if count < 1000:
        print("Warning: Chunk count below recommended threshold (1000)")
        health["Chunking"] = "Problem"
    return count


def check_faiss_index(health: Dict[str, str]) -> int:
    index_dir = DATA_DIR / "panos_full_index"
    index_file = index_dir / "index.faiss"
    metadata_file = index_dir / "metadata.json"
    print("\n=== Check 3: FAISS Index Files ===")
    print(f"Index directory: {index_dir}")
    missing = []
    if not index_file.exists():
        missing.append("index.faiss")
    if not metadata_file.exists():
        missing.append("metadata.json")
    if missing:
        print(f"Result: FAISS index not built (missing: {', '.join(missing)})")
        health["FAISS Index"] = "Problem"
        return 0
    print("Result: index.faiss and metadata.json found")
    data = load_json(metadata_file)
    if not isinstance(data, list):
        print("Result: metadata.json invalid")
        health["FAISS Index"] = "Problem"
        return 0
    count = len(data)
    print(f"Metadata records: {count}")
    if count < 1000:
        print("Warning: Metadata count below recommended threshold (1000)")
        health["FAISS Index"] = "Problem"
    return count


def check_faiss_retrieval(health: Dict[str, str]) -> int:
    print("\n=== Check 4: FAISS Retrieval ===")
    try:
        from app.services.faiss_service import FAISSService

        faiss = FAISSService()
        query = "GlobalProtect authentication failed"
        results = faiss.search(query, top_k=3)
        print(f"Query: {query}")
        print(f"Results: {len(results)}")
        for i, r in enumerate(results):
            title = r.get("article_title") or r.get("title")
            url = r.get("article_url") or r.get("url")
            print(f"  {i+1}. {title} ({url})")
        if len(results) == 0:
            print("FAISS retrieval returned 0 results")
            health["Retrieval"] = "Problem"
        return len(results)
    except Exception as exc:
        print(f"Error during FAISS retrieval: {exc}")
        health["FAISS Index"] = "Problem"
        health["Retrieval"] = "Problem"
        return 0


def check_llm_and_rag(health: Dict[str, str]) -> None:
    print("\n=== Check 5: LLM & End-to-End RAG ===")
    try:
        from app.services.local_llm import LocalLLMService

        llm = LocalLLMService()
        test_context = "GlobalProtect authentication failure troubleshooting steps"
        output = llm.generate_troubleshooting_steps("Authentication failure", test_context)
        length = len(output.strip()) if output else 0
        print(f"LLM output length: {length}")
        print("First 200 chars:")
        print(output[:200] if output else "")
        if length <= 50:
            print("Warning: LLM output too short")
            health["LLM"] = "Problem"
    except Exception as exc:
        print(f"Error during LLM generation: {exc}")
        health["LLM"] = "Problem"

    try:
        import asyncio
        from app.services.rag_service import RAGService

        async def run_test() -> None:
            rag = RAGService()
            issue = "GlobalProtect authentication failed timeout"
            result = await rag.analyze_issue(issue)
            related_kbs = result.get("related_kbs") or []
            steps = result.get("troubleshooting_steps") or ""
            print(f"RAG related_kbs: {len(related_kbs)}")
            print(f"RAG troubleshooting_steps length: {len(steps)}")
            if len(related_kbs) < 1 or len(steps) <= 50:
                print("Warning: RAG may not be returning sufficient context")
                health["Retrieval"] = "Problem"

        asyncio.run(run_test())
    except Exception as exc:
        print(f"Error during RAG test: {exc}")
        health["Retrieval"] = "Problem"


def main() -> None:
    health = {
        "KB Status": "OK",
        "Chunking": "OK",
        "FAISS Index": "OK",
        "Retrieval": "OK",
        "LLM": "OK",
    }

    kb_count = check_kb_articles(health)
    chunk_count = check_kb_chunks(health)
    metadata_count = check_faiss_index(health)
    faiss_results = check_faiss_retrieval(health)
    check_llm_and_rag(health)

    print("\n=== System Health Report ===")
    print(f"- KB Status: {health['KB Status']} (articles={kb_count})")
    print(f"- Chunking: {health['Chunking']} (chunks={chunk_count})")
    print(f"- FAISS Index: {health['FAISS Index']} (metadata={metadata_count})")
    print(f"- Retrieval: {health['Retrieval']} (faiss_results={faiss_results})")
    print(f"- LLM: {health['LLM']}")


if __name__ == "__main__":
    main()

