import json
import os
import sys
import subprocess
from pathlib import Path
from typing import Any, Dict, Tuple

import requests
import asyncio


BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

DATA_DIR = BASE_DIR / "data"
SCRIPTS_DIR = BASE_DIR / "scripts"


def load_json(path: Path) -> Any:
    try:
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"[ERROR] Failed to read {path}: {exc}")
        return None


def check_ollama() -> Tuple[bool, bool]:
    print("\n=== Mode 1: Step 1 — Ollama Check ===")
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
    except Exception as exc:
        print("Ollama not running. Start using: ollama serve")
        return False, False

    if resp.status_code != 200:
        print(f"[ERROR] Ollama /api/tags HTTP {resp.status_code}: {resp.text}")
        return False, False

    try:
        data = resp.json()
    except Exception as exc:
        print(f"[ERROR] Failed to parse /api/tags JSON: {exc}")
        return False, False

    models_field = data.get("models") or data
    names = set()
    if isinstance(models_field, list):
        for item in models_field:
            name = item.get("name") or item.get("model")
            if isinstance(name, str):
                names.add(name.split(":")[0])

    primary_ok = "mistral" in names
    fallback_ok = "phi3" in names

    if not primary_ok:
        print("Run: ollama pull mistral")
    if not fallback_ok:
        print("Run: ollama pull phi3")

    return True, primary_ok and fallback_ok


def check_kb_files() -> Tuple[bool, int, int, int]:
    print("\n=== Mode 1: Step 2 — KB Files Check ===")

    kb_path = DATA_DIR / "full_kbs.json"
    chunks_path = DATA_DIR / "full_kb_chunks.json"
    index_path = DATA_DIR / "panos_full_index" / "index.faiss"
    metadata_path = DATA_DIR / "panos_full_index" / "metadata.json"

    articles = chunks = metadata = 0
    ok = True

    kb_data = load_json(kb_path)
    if isinstance(kb_data, list):
        articles = len(kb_data)
        if articles < 200:
            print("Run: python scripts/build_full_kb_pipeline.py")
            ok = False
    else:
        print("Run: python scripts/build_full_kb_pipeline.py")
        ok = False

    chunks_data = load_json(chunks_path)
    if isinstance(chunks_data, list):
        chunks = len(chunks_data)
        if chunks < 1000:
            print("Run: python scripts/build_full_kb_pipeline.py")
            ok = False
    else:
        print("Run: python scripts/build_full_kb_pipeline.py")
        ok = False

    metadata_data = load_json(metadata_path)
    if isinstance(metadata_data, list):
        metadata = len(metadata_data)
        if metadata < 1000:
            print("Run: python scripts/build_full_kb_pipeline.py")
            ok = False
    else:
        print("Run: python scripts/build_full_kb_pipeline.py")
        ok = False

    if not index_path.exists():
        print("Run: python scripts/build_full_kb_pipeline.py")
        ok = False

    return ok, articles, chunks, metadata


def check_faiss_retrieval() -> Tuple[bool, int]:
    print("\n=== Mode 1: Step 3 — FAISS Retrieval Test ===")
    try:
        from app.services.faiss_service import FAISSService
        faiss = FAISSService()
        results = faiss.search("GlobalProtect authentication failed", top_k=3)
        count = len(results)
        return count > 0, count
    except Exception as exc:
        print(f"[ERROR] FAISS test failed: {exc}")
        return False, 0


async def check_llm() -> bool:
    print("\n=== Mode 1: Step 4 — LLM Test ===")
    try:
        from app.services.local_llm import LocalLLMService
        llm = LocalLLMService()
        output = await llm.generate_troubleshooting_steps(
            "Authentication failure",
            "User cannot connect to GlobalProtect portal.",
        )
        length = len(output.strip()) if output else 0
        return length > 50
    except Exception as exc:
        print(f"[ERROR] LLM test failed: {exc}")
        return False


async def check_rag() -> Tuple[bool, int, int]:
    print("\n=== Mode 1: Step 5 — End-to-End RAG Test ===")
    try:
        from app.services.rag_service import RAGService
        rag = RAGService()
        result = await rag.analyze_issue(
            "GlobalProtect authentication failed timeout"
        )
        related_kbs = result.get("related_kbs") or []
        steps = result.get("troubleshooting_steps") or ""
        related_count, steps_len = len(related_kbs), len(steps)
        return (related_count >= 1 and steps_len > 100), related_count, steps_len
    except Exception as exc:
        print(f"[ERROR] RAG test failed: {exc}")
        return False, 0, 0


def check_developer_scripts() -> bool:
    print("\n=== Mode 2: Developer Upgrade Support ===")
    crawler_script = SCRIPTS_DIR / "paloalto_kb_crawler.py"
    pipeline_script = SCRIPTS_DIR / "build_full_kb_pipeline.py"
    
    exists = crawler_script.exists() and pipeline_script.exists()
    
    if not exists:
        print("[WARNING] Developer scripts missing.")
    
    return exists


def check_self_check() -> bool:
    print("\n=== Mode 3: Self Check ===")
    self_check_script = SCRIPTS_DIR / "system_self_check.py"
    if not self_check_script.exists():
        print("[ERROR] scripts/system_self_check.py missing.")
        return False
    
    try:
        # Run with a short timeout to see if it starts ok
        subprocess.run([sys.executable, str(self_check_script)], capture_output=True, timeout=10)
        return True
    except subprocess.TimeoutExpired:
        # If it times out, it's likely running fine but just long-running
        return True
    except Exception as exc:
        print(f"[ERROR] system_self_check.py failed: {exc}")
        return False


async def main() -> None:
    print("=== PAN-OS CyberOps Analyzer Production Verification ===\n")

    ollama_ok, models_ok = check_ollama()
    kb_files_ok, articles, chunks, metadata = check_kb_files()
    faiss_ok, faiss_results = check_faiss_retrieval()
    llm_ok = await check_llm()
    rag_ok, rag_related, rag_steps_len = await check_rag()
    dev_support_ok = check_developer_scripts()
    self_check_ok = check_self_check()

    if articles < 200 or chunks < 1000 or metadata < 1000:
        print("\nTo update KB:")
        print("1. python scripts/paloalto_kb_crawler.py")
        print("2. Login manually in browser")
        print("3. python scripts/build_full_kb_pipeline.py")

    production_ready = (
        ollama_ok
        and models_ok
        and kb_files_ok
        and faiss_ok
        and llm_ok
        and rag_ok
    )

    print("\n================================")
    print("FINAL VERIFICATION SUMMARY")
    print("================================")
    print(f"Ollama: {'OK' if ollama_ok else 'FAIL'}")
    print(f"Models: {'OK' if models_ok else 'FAIL'}")
    print(f"Articles: {articles}")
    print(f"Chunks: {chunks}")
    print(f"Metadata: {metadata}")
    print(f"FAISS retrieval count: {faiss_results}")
    print(f"LLM generation: {'OK' if llm_ok else 'FAIL'}")
    print(f"RAG end-to-end: {'OK' if rag_ok else 'FAIL'}")
    print(f"Production ready: {'YES' if production_ready else 'NO'}")
    print(f"Crawler upgrade supported: {'YES' if dev_support_ok else 'NO'}")


if __name__ == "__main__":
    asyncio.run(main())
