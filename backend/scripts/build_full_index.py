import json
import os
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer


def main():
    base_dir = Path(__file__).resolve().parents[1]
    data_dir = base_dir / "data"
    chunks_path = data_dir / "full_kb_chunks.json"
    output_dir = data_dir / "panos_full_index"

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    texts = [c.get("chunk_text", "") for c in chunks]

    model = SentenceTransformer("all-MiniLM-L6-v2")

    if texts:
        embeddings = model.encode(texts)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(np.array(embeddings).astype("float32"))
    else:
        dummy_embedding = model.encode([""])
        dimension = dummy_embedding.shape[1]
        index = faiss.IndexFlatL2(dimension)

    os.makedirs(output_dir, exist_ok=True)
    index_path = output_dir / "index.faiss"
    metadata_path = output_dir / "metadata.json"

    faiss.write_index(index, str(index_path))
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)

    print(f"FAISS index created with {len(chunks)} chunks")


if __name__ == "__main__":
    main()
