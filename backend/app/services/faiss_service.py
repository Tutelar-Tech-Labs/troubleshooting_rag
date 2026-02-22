import faiss
import numpy as np
import os
import json
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any

class FAISSService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2", index_path: str = "data/panos_full_index"):
        self.model = SentenceTransformer(model_name)
        self.index_path = index_path
        self.index = None
        self.kb_chunks = []  # Stores metadata for each chunk

    def create_index(self, chunks: List[Dict[str, Any]]):
        """
        Creates a FAISS index from a list of KB chunks.
        chunks: List of dicts with 'chunk_text', 'article_title', 'article_url'
        """
        self.kb_chunks = chunks
        texts = [chunk['chunk_text'] for chunk in chunks]
        embeddings = self.model.encode(texts)
        
        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatL2(dimension)
        self.index.add(np.array(embeddings).astype('float32'))
        
        self.save_index()

    def search(self, query: str, domain: str = "globalprotect", top_k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None:
            self.load_index()
        query_embedding = self.model.encode([query])
        distances, indices = self.index.search(np.array(query_embedding).astype('float32'), top_k)

        results = []
        for i in range(len(indices[0])):
            idx = indices[0][i]
            if idx != -1 and idx < len(self.kb_chunks):
                results.append(self.kb_chunks[idx])

        return results

    def save_index(self):
        if not os.path.exists(self.index_path):
            os.makedirs(self.index_path)
        
        faiss.write_index(self.index, os.path.join(self.index_path, "index.faiss"))
        with open(os.path.join(self.index_path, "metadata.json"), "w") as f:
            json.dump(self.kb_chunks, f)

    def load_index(self):
        index_file = os.path.join(self.index_path, "index.faiss")
        metadata_file = os.path.join(self.index_path, "metadata.json")
        if not os.path.exists(index_file) or not os.path.exists(metadata_file):
            raise RuntimeError("PAN-OS KB index not built. Run scripts/build_full_index.py")
        self.index = faiss.read_index(index_file)
        with open(metadata_file, "r", encoding="utf-8") as f:
            self.kb_chunks = json.load(f)
