import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"


def run_script(name: str) -> None:
    path = SCRIPTS_DIR / name
    print(f"[RUN] python {path}")
    subprocess.run([sys.executable, str(path)], check=True)


def ensure_structure() -> None:
    print("=== Check 0: Project Structure ===")
    for path in [DATA_DIR, DATA_DIR / "panos_full_index", SCRIPTS_DIR]:
        if not path.exists():
            print(f"[INFO] Creating missing directory: {path}")
            path.mkdir(parents=True, exist_ok=True)
    services_dir = BASE_DIR / "app" / "services"
    if not services_dir.exists():
        print(f"[WARN] Services directory not found: {services_dir}")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def check_kb() -> int:
    kb_path = DATA_DIR / "full_kbs.json"
    print("\n=== Check 1: KB Articles ===")
    print(f"Path: {kb_path}")
    data = load_json(kb_path)
    if not isinstance(data, list):
        print("Result: full_kbs.json missing or invalid, running crawler...")
        run_script("paloalto_kb_crawler.py")
        data = load_json(kb_path) or []
    count = len(data)
    print(f"Result: {count} articles")
    if count < 50:
        print("[WARN] Articles < 50, running crawler again...")
        run_script("paloalto_kb_crawler.py")
        data = load_json(kb_path) or []
        count = len(data)
        print(f"Result after crawl: {count} articles")
    return count


def check_chunks() -> int:
    chunks_path = DATA_DIR / "full_kb_chunks.json"
    print("\n=== Check 2: KB Chunks ===")
    print(f"Path: {chunks_path}")
    data = load_json(chunks_path)
    if not isinstance(data, list):
        print("Result: full_kb_chunks.json missing or invalid, building chunks...")
        run_script("process_kb_chunks.py")
        data = load_json(chunks_path) or []
    count = len(data)
    print(f"Result: {count} chunks")
    if count < 500:
        print("[WARN] Chunks < 500, rebuilding chunks...")
        run_script("process_kb_chunks.py")
        data = load_json(chunks_path) or []
        count = len(data)
        print(f"Result after rebuild: {count} chunks")
    return count


def check_faiss_index(chunk_count: int) -> int:
    index_dir = DATA_DIR / "panos_full_index"
    index_file = index_dir / "index.faiss"
    metadata_file = index_dir / "metadata.json"
    print("\n=== Check 3: FAISS Index ===")
    print(f"Index dir: {index_dir}")

    rebuild = False
    if not index_file.exists() or not metadata_file.exists():
        print("Result: index.faiss or metadata.json missing, rebuilding index...")
        rebuild = True
    else:
        metadata = load_json(metadata_file)
        if not isinstance(metadata, list):
            print("Result: metadata.json invalid, rebuilding index...")
            rebuild = True
        elif chunk_count and len(metadata) < chunk_count:
            print("Result: metadata < chunks, rebuilding index...")
            rebuild = True

    if rebuild:
        run_script("build_full_index.py")
        metadata = load_json(metadata_file) or []
    else:
        metadata = load_json(metadata_file) or []

    count = len(metadata)
    print(f"Metadata records: {count}")
    return count


def faiss_retrieval_test() -> int:
    print("\n=== Check 4: FAISS Retrieval Test ===")
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
            print("[WARN] FAISS returned 0 results, rebuilding index once...")
            run_script("build_full_index.py")
            faiss = FAISSService()
            results = faiss.search(query, top_k=3)
            print(f"Results after rebuild: {len(results)}")
        return len(results)
    except Exception as exc:
        print(f"Error during FAISS retrieval: {exc}")
        return 0


def llm_test() -> int:
    print("\n=== Check 5: LLM Test ===")
    try:
        from app.services.local_llm import LocalLLMService

        llm = LocalLLMService()
        output = llm.generate_troubleshooting_steps(
            "Authentication failure",
            "User cannot connect",
        )
        length = len(output.strip()) if output else 0
        print(f"LLM output length: {length}")
        if length < 20:
            print("[WARN] LLM output too short, retrying with google/flan-t5-base")
            llm = LocalLLMService(model_name="google/flan-t5-base")
            output = llm.generate_troubleshooting_steps(
                "Authentication failure",
                "User cannot connect",
            )
            length = len(output.strip()) if output else 0
            print(f"LLM output length with flan-t5-base: {length}")
        return length
    except Exception as exc:
        print(f"Error during LLM test: {exc}")
        return 0


def rag_test() -> Tuple[int, int]:
    print("\n=== Check 6: End-to-End RAG Test ===")
    try:
        import asyncio
        from app.services.rag_service import RAGService

        async def run_test() -> Tuple[int, int]:
            rag = RAGService()
            result = await rag.analyze_issue(
                "GlobalProtect authentication failed timeout"
            )
            related_kbs = result.get("related_kbs") or []
            steps = result.get("troubleshooting_steps") or ""
            print(f"RAG related_kbs: {len(related_kbs)}")
            print(f"RAG troubleshooting_steps length: {len(steps)}")
            return len(related_kbs), len(steps)

        return asyncio.run(run_test())
    except Exception as exc:
        print(f"Error during RAG test: {exc}")
        return 0, 0


def system_healthy(
    articles: int,
    chunks: int,
    metadata: int,
    faiss_results: int,
    llm_len: int,
    rag_related: int,
    rag_steps_len: int,
) -> bool:
    return (
        articles >= 100
        and chunks >= 1000
        and metadata >= 1000
        and faiss_results > 0
        and llm_len > 50
        and rag_related >= 1
        and rag_steps_len >= 50
    )


def main() -> None:
    print("=== Environment Check ===")
    env_result = subprocess.run(
        [sys.executable, "scripts/setup_environment.py"]
    )
    env_ok = env_result.returncode == 0

    max_rounds = 3
    articles = chunks = metadata = faiss_results = llm_len = rag_related = rag_steps_len = 0
    ready = False

    for round_idx in range(1, max_rounds + 1):
        print(f"\n=== SYSTEM SELF CHECK ROUND {round_idx} ===")
        ensure_structure()

        articles = check_kb()
        chunks = check_chunks()
        metadata = check_faiss_index(chunks)
        faiss_results = faiss_retrieval_test()
        llm_len = llm_test()
        rag_related, rag_steps_len = rag_test()

        print("\n--- Round Summary ---")
        print(f"Articles: {articles}")
        print(f"Chunks: {chunks}")
        print(f"Metadata: {metadata}")
        print(f"FAISS results: {faiss_results}")
        print(f"LLM output length: {llm_len}")
        print(f"RAG related_kbs: {rag_related}")
        print(f"RAG steps length: {rag_steps_len}")

        if system_healthy(
            articles,
            chunks,
            metadata,
            faiss_results,
            llm_len,
            rag_related,
            rag_steps_len,
        ):
            ready = True
            break

        time.sleep(2)

    faiss_ok = faiss_results > 0
    llm_ok = llm_len > 50
    rag_ok = rag_related >= 1 and rag_steps_len >= 50

    print("\n=============================")
    print("SYSTEM STATUS SUMMARY")
    print("=============================")
    print(f"Environment: {'OK' if env_ok else 'Failed'}")
    print(f"KB Articles: {articles}")
    print(f"Chunks: {chunks}")
    print(f"FAISS Metadata: {metadata}")
    print(f"FAISS Retrieval: {'OK' if faiss_ok else 'Failed'}")
    print(f"LLM: {'OK' if llm_ok else 'Failed'}")
    print(f"RAG: {'OK' if rag_ok else 'Failed'}")

    if env_ok and ready and faiss_ok and llm_ok and rag_ok:
        print("\nPAN-OS RAG SYSTEM READY FOR PRODUCTION")
    else:
        print(
            "\nSystem self-check completed but did not reach production-ready criteria."
        )


if __name__ == "__main__":
    main()

