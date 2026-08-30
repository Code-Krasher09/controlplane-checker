"""Standalone retrieval evaluation runner for Lexical, Semantic, and Hybrid modes."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from app.tier1.retrieval.chunking import DocumentChunk, DocumentChunker
from app.tier1.retrieval.embedding import RealEmbeddingProvider
from app.tier1.retrieval.hybrid_repo import HybridEvidenceRepository
from app.tier1.retrieval.lexical_repo import LexicalEvidenceRepository
from app.tier1.retrieval.semantic_repo import SemanticEvidenceRepository


def load_retrieval_cases(benchmark_path: str) -> List[Dict[str, Any]]:
    """Load benchmark cases from JSONL."""
    cases = []
    with open(benchmark_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                cases.append(json.loads(line.strip()))
    return cases


def evaluate_retriever(
    name: str,
    repo: Any,
    cases: List[Dict[str, Any]],
    top_k_list: List[int] = [1, 3, 5, 10],
) -> Dict[str, Any]:
    """Evaluate a retriever instance against benchmark cases."""
    print(f"\n--- Evaluating {name} ---")

    metrics = {
        "mode": name,
        "total_cases": len(cases),
        "recall_at_k_relevant": {k: 0.0 for k in top_k_list},
        "recall_at_k_required": {k: 0.0 for k in top_k_list},
        "mrr_required": 0.0,
        "irrelevant_retrieval_count": 0,
        "total_retrieved_snippets": 0,
        "cold_latencies_ms": [],
        "warm_latencies_ms": [],
    }

    cases_with_required = 0
    cases_with_relevant = 0

    # 1. Cold run
    for c in cases:
        query = c["query"]
        app_profile = c.get("application_profile")
        pol_scope = c.get("policy_scope")
        relevant_ids = set(c.get("relevant_evidence_ids", []))
        required_ids = set(c.get("required_evidence_ids", []))

        t0 = time.perf_counter()
        retrieved_top10 = repo.retrieve(
            query=query,
            application_profile=app_profile,
            policy=pol_scope,
            top_k=10,
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        metrics["cold_latencies_ms"].append(latency_ms)

        retrieved_source_ids = [snip.source_id for snip in retrieved_top10]
        metrics["total_retrieved_snippets"] += len(retrieved_top10)

        # Irrelevant retrieval check for distractor/out-of-scope cases
        if not relevant_ids and retrieved_top10:
            metrics["irrelevant_retrieval_count"] += len(retrieved_top10)

        # Recall for relevant evidence
        if relevant_ids:
            cases_with_relevant += 1
            for k in top_k_list:
                top_k_sources = set(retrieved_source_ids[:k])
                hits = len(relevant_ids.intersection(top_k_sources))
                metrics["recall_at_k_relevant"][k] += hits / len(relevant_ids)

        # Recall and MRR for required evidence
        if required_ids:
            cases_with_required += 1
            # MRR
            found_rank = 0
            for rank, s_id in enumerate(retrieved_source_ids, start=1):
                if s_id in required_ids:
                    found_rank = rank
                    break
            if found_rank > 0:
                metrics["mrr_required"] += 1.0 / found_rank

            for k in top_k_list:
                top_k_sources = set(retrieved_source_ids[:k])
                hits = len(required_ids.intersection(top_k_sources))
                metrics["recall_at_k_required"][k] += hits / len(required_ids)

    # 2. Warm run for latency comparison
    for c in cases:
        t0 = time.perf_counter()
        _ = repo.retrieve(
            query=c["query"],
            application_profile=c.get("application_profile"),
            policy=c.get("policy_scope"),
            top_k=3,
        )
        metrics["warm_latencies_ms"].append((time.perf_counter() - t0) * 1000.0)

    # Normalize metrics
    if cases_with_relevant > 0:
        for k in top_k_list:
            metrics["recall_at_k_relevant"][k] /= cases_with_relevant

    if cases_with_required > 0:
        for k in top_k_list:
            metrics["recall_at_k_required"][k] /= cases_with_required
        metrics["mrr_required"] /= cases_with_required

    avg_cold_ms = sum(metrics["cold_latencies_ms"]) / len(metrics["cold_latencies_ms"]) if metrics["cold_latencies_ms"] else 0.0
    avg_warm_ms = sum(metrics["warm_latencies_ms"]) / len(metrics["warm_latencies_ms"]) if metrics["warm_latencies_ms"] else 0.0
    irrelevant_rate = (
        metrics["irrelevant_retrieval_count"] / metrics["total_retrieved_snippets"]
        if metrics["total_retrieved_snippets"] > 0
        else 0.0
    )

    summary = {
        "mode": name,
        "cases_evaluated": len(cases),
        "recall_at_1_required": round(metrics["recall_at_k_required"][1], 4),
        "recall_at_3_required": round(metrics["recall_at_k_required"][3], 4),
        "recall_at_5_required": round(metrics["recall_at_k_required"][5], 4),
        "recall_at_10_required": round(metrics["recall_at_k_required"][10], 4),
        "recall_at_3_relevant": round(metrics["recall_at_k_relevant"][3], 4),
        "mrr_required": round(metrics["mrr_required"], 4),
        "irrelevant_retrieval_rate": round(irrelevant_rate, 4),
        "avg_cold_latency_ms": round(avg_cold_ms, 2),
        "avg_warm_latency_ms": round(avg_warm_ms, 2),
    }

    print(f"Recall@1 (Required): {summary['recall_at_1_required']:.4f}")
    print(f"Recall@3 (Required): {summary['recall_at_3_required']:.4f}")
    print(f"Recall@5 (Required): {summary['recall_at_5_required']:.4f}")
    print(f"MRR (Required):      {summary['mrr_required']:.4f}")
    print(f"Irrelevant Rate:     {summary['irrelevant_retrieval_rate']:.4f}")
    print(f"Avg Cold Latency:    {summary['avg_cold_latency_ms']:.2f} ms")
    print(f"Avg Warm Latency:    {summary['avg_warm_latency_ms']:.2f} ms")

    return summary


def run_all_evaluations(
    benchmark_path: str = "data/evaluation/retrieval_bench/retrieval_cases.jsonl",
    corpus_path: str = "data/corpus/enterprise_corpus.json",
    index_dir: str = "data/index",
    out_file: str = "artifacts/evaluation/retrieval_comparison.json",
):
    """Run full comparative retrieval benchmark across LEXICAL, SEMANTIC, and HYBRID."""
    cases = load_retrieval_cases(benchmark_path)
    print(f"Loaded {len(cases)} retrieval benchmark cases from {benchmark_path}")

    # 1. Load corpus chunks
    with open(corpus_path, "r", encoding="utf-8") as f:
        docs = json.load(f)
    chunker = DocumentChunker(target_chunk_chars=250, overlap_sentences=1)
    chunks: List[DocumentChunk] = []
    for doc in docs:
        c_list = chunker.chunk_document(
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
        chunks.extend(c_list)

    # Convert chunks to EvidenceSnippets for Lexical repository
    lexical_snippets: List[EvidenceSnippet] = []
    for ch in chunks:
        lexical_snippets.append(
            EvidenceSnippet(
                source_type=ch.policy_scope or "POLICY_DOC",
                source_id=ch.source_id,
                document_version=ch.document_version,
                chunk_id=ch.chunk_id,
                content_snippet=ch.content,
                quality=ClaimEvidenceQuality(
                    authority=ch.authority,
                    freshness=1.0,
                    relevance=0.9,
                    completeness=0.9,
                    quality_score=0.9,
                ),
            )
        )

    # Setup repositories
    lexical_repo = LexicalEvidenceRepository(snippets=lexical_snippets)

    index_file = os.path.join(index_dir, "faiss_index.bin")
    meta_file = os.path.join(index_dir, "metadata.json")
    embedding_provider = RealEmbeddingProvider()

    if os.path.exists(index_file) and os.path.exists(meta_file):
        semantic_repo = SemanticEvidenceRepository(
            embedding_provider=embedding_provider,
            index_path=index_file,
            metadata_path=meta_file,
        )
    else:
        semantic_repo = SemanticEvidenceRepository(
            embedding_provider=embedding_provider,
            chunks=chunks,
        )

    hybrid_repo = HybridEvidenceRepository(
        semantic_repo=semantic_repo,
        lexical_repo=lexical_repo,
        alpha=0.5,
    )

    # Evaluate each
    results = {}
    results["LEXICAL"] = evaluate_retriever("LEXICAL", lexical_repo, cases)
    results["SEMANTIC"] = evaluate_retriever("SEMANTIC", semantic_repo, cases)
    results["HYBRID"] = evaluate_retriever("HYBRID", hybrid_repo, cases)

    # Write output
    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"\nRetrieval comparison saved to {out_file}")


if __name__ == "__main__":
    run_all_evaluations()
