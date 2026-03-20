import asyncio
import json
import sys
import os

# Add the project root to sys.path to import app modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.rag_service import RAGService

async def verify_links():
    rag = RAGService()
    print("Simulating RAG analysis for: 'GlobalProtect connection timeout'...")
    
    # We use a dummy issue to trigger the search
    result = await rag.analyze_issue("GlobalProtect connection timeout")
    
    print("\n--- RESULTS ---")
    if "related_kbs" in result:
        for idx, kb in enumerate(result["related_kbs"]):
            print(f"{idx+1}. {kb['title']}")
            print(f"   URL: {kb['url']}")
            if "?q=" in kb['url']:
                print("   ❌ ERROR: Still found search query URL!")
            elif "KCSArticleDetail" in kb['url']:
                print("   ✅ SUCCESS: Direct article URL found.")
            else:
                print(f"   ❓ WARNING: Unexpected URL format: {kb['url']}")
    else:
        print("❌ No related_kbs found in result.")

if __name__ == "__main__":
    asyncio.run(verify_links())
