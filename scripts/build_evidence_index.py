"""Index building pipeline for semantic evidence retrieval."""

import json
import os
import sys
import time
from pathlib import Path
from typing import List

from app.tier1.retrieval.chunking import DocumentChunk, DocumentChunker
from app.tier1.retrieval.embedding import RealEmbeddingProvider
from app.tier1.retrieval.semantic_repo import SemanticEvidenceRepository


def build_index(
    corpus_path: str = "data/corpus/enterprise_corpus.json",
    output_dir: str = "data/index",
    model_name: str = "all-MiniLM-L6-v2",
) -> SemanticEvidenceRepository:
    """Build a deterministic FAISS vector index from enterprise corpus documents."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    index_file = str(out_path / "faiss_index.bin")
    meta_file = str(out_path / "metadata.json")
    manifest_file = str(out_path / "manifest.json")

    print(f"Loading corpus from {corpus_path}...")
    with open(corpus_path, "r", encoding="utf-8") as f:
        docs = json.load(f)

    print(f"Loaded {len(docs)} documents. Chunking...")
    chunker = DocumentChunker(target_chunk_chars=250, overlap_sentences=1, min_chunk_chars=30)
    all_chunks: List[DocumentChunk] = []

    for doc in docs:
        chunks = chunker.chunk_document(
            document_id=doc["document_id"],
            source_id=doc["source_id"],
            text=doc["content"],
            document_version=doc.get("document_version", "v1.0"),
            timestamp=doc.get("timestamp", "2026-01-01T00:00:00Z"),
            authority=doc.get("authority", "HIGH"),
            application_profile=doc.get("application_profile"),
            policy_scope=doc.get("policy_scope"),
            extra_metadata=doc.get("extra_metadata", {}),
        )
        all_chunks.extend(chunks)

    print(f"Generated {len(all_chunks)} chunks across {len(docs)} documents.")

    print(f"Initializing embedding provider ({model_name})...")
    provider = RealEmbeddingProvider(model_name=model_name)

    print("Building FAISS index...")
    repo = SemanticEvidenceRepository(embedding_provider=provider)
    repo.index_chunks(all_chunks)

    print(f"Saving index to {index_file}, metadata to {meta_file}, manifest to {manifest_file}...")
    repo.save_index(index_file, meta_file, manifest_file)

    print("Index build completed successfully.")
    return repo


if __name__ == "__main__":
    corpus = sys.argv[1] if len(sys.argv) > 1 else "data/corpus/enterprise_corpus.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "data/index"
    build_index(corpus_path=corpus, output_dir=out)
