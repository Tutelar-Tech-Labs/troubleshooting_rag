KB Ingestion Pipeline
=====================

This project uses an **offline** Palo Alto Knowledge Base ingestion pipeline. All crawling and indexing happens on a developer machine. Runtime users never contact the Palo Alto website.

Developer workflow
------------------

1. Crawl KB with Selenium (manual login)

   ```bash
   cd backend
   python scripts/paloalto_kb_crawler.py
   ```

   - A Chrome window opens using the persistent profile `./chrome_profile`.
   - On first run, log in to the Palo Alto Knowledge Base manually.
   - The crawler runs a set of KB search queries (GlobalProtect, Panorama commit, Prisma Access, IPsec VPN, etc.), collects up to the configured maximum number of articles, and saves them to:

     - `backend/data/full_kbs.json`

2. Build chunks and FAISS index

   ```bash
   cd backend
   python scripts/build_full_kb_pipeline.py
   ```

   This script:

   - Uses the existing `full_kbs.json` (it does **not** call Selenium or crawl).
   - Runs the chunk processor to create:

     - `backend/data/full_kb_chunks.json`

   - Builds the unified FAISS index:

     - `backend/data/panos_full_index/index.faiss`
     - `backend/data/panos_full_index/metadata.json`

3. Verify full pipeline health

   ```bash
   cd backend
   python scripts/verify_full_pipeline.py
   ```

   The verification script checks:

   - KB articles count (`full_kbs.json`)
   - Chunk count (`full_kb_chunks.json`)
   - FAISS index files and metadata size (`panos_full_index/`)
   - FAISS retrieval for a sample query
   - LLM generation and end-to-end RAG behavior

   Recommended targets:

   - KB articles: > 200
   - Chunks: > 1000
   - Metadata records: > 1000
   - FAISS retrieval returns at least one result for sample queries

Runtime behavior
----------------

At runtime:

- The API and RAG pipeline **only** read from the prebuilt FAISS index under `backend/data/panos_full_index/`.
- No crawling, Selenium, or live HTTP calls to the Palo Alto Knowledge Base occur.
- No automatic rebuilding of the index is performed; if the KB needs to be refreshed, a developer reruns the three steps above.

Files and directories
---------------------

- Scripts (developer-only):
  - `backend/scripts/paloalto_kb_crawler.py`
  - `backend/scripts/build_full_kb_pipeline.py`
  - `backend/scripts/verify_full_pipeline.py`

- Data (runtime inputs for RAG):
  - `backend/data/full_kbs.json`
  - `backend/data/full_kb_chunks.json`
  - `backend/data/panos_full_index/`
    - `index.faiss`
    - `metadata.json`

No other KB index directories (globalprotect_index, panorama_index, prisma_index, ipsec_index) are used. The system relies on this single unified index for all domains.

