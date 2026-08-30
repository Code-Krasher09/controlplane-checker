"""End-to-End Retrieval Ablation and Failure Classification Runner."""

import asyncio
import json
import os
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np

from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from app.evaluation.models import BenchmarkCase, PerCaseResult
from app.evaluation.runner import EvaluationRunner
from app.gateway.service import GatewayInspectRequest, GatewayService
from app.persistence.database import get_db_context, init_db
from app.persistence.seed import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)
from app.tier1.nli_real import RealNLIVerifier
from app.tier1.retrieval.chunking import DocumentChunk, DocumentChunker
from app.tier1.retrieval.embedding import RealEmbeddingProvider
from app.tier1.retrieval.hybrid_repo import HybridEvidenceRepository
from app.tier1.retrieval.lexical_repo import LexicalEvidenceRepository
from app.tier1.retrieval.semantic_repo import SemanticEvidenceRepository
from app.tier1.service import Tier1Service


def load_corpus_chunks(corpus_path: str = "data/corpus/enterprise_corpus.json") -> Tuple[List[DocumentChunk], List[EvidenceSnippet]]:
    """Load corpus documents and convert to DocumentChunks and EvidenceSnippets."""
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

    snippets: List[EvidenceSnippet] = []
    for ch in chunks:
        snippets.append(
            EvidenceSnippet(
                source_type=ch.policy_scope or "POLICY_DOC",
                source_id=ch.source_id,
                document_version=ch.document_version,
                chunk_id=ch.chunk_id,
                content_snippet=ch.content,
                quality=ClaimEvidenceQuality(
                    authority=ch.authority,
                    freshness=1.0,
                    relevance=0.95,
                    completeness=0.90,
                    quality_score=0.95,
                ),
            )
        )
    return chunks, snippets


async def run_end_to_end_ablation(
    holdout_path: str = "data/evaluation/holdout/holdout.jsonl",
    corpus_path: str = "data/corpus/enterprise_corpus.json",
    index_dir: str = "data/index",
    out_file: str = "artifacts/evaluation/retrieval_failure_analysis.json",
):
    """Run full pipeline ablation comparing LEXICAL, SEMANTIC, and HYBRID retrieval."""
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_ENV"] = "test"
    await init_db()

    chunks, snippets = load_corpus_chunks(corpus_path)
    embedding_provider = RealEmbeddingProvider()
    nli_verifier = RealNLIVerifier()

    # Repositories
    lexical_repo = LexicalEvidenceRepository(snippets=snippets)

    index_file = os.path.join(index_dir, "faiss_index.bin")
    meta_file = os.path.join(index_dir, "metadata.json")
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

    runner = EvaluationRunner()
    cases = runner.load_dataset(holdout_path)
    print(f"Running end-to-end retrieval ablation on {len(cases)} holdout cases...")

    modes = {
        "LEXICAL": lexical_repo,
        "SEMANTIC": semantic_repo,
        "HYBRID": hybrid_repo,
    }

    mode_results: Dict[str, List[PerCaseResult]] = {}

    async with get_db_context() as db:
        await seed_database_async(db)

        for mode_name, repo in modes.items():
            print(f"\n--- Running Mode: {mode_name} ---")
            results: List[PerCaseResult] = []

            for case in cases:
                # Build custom Tier1 with selected repository
                custom_tier1 = Tier1Service(
                    evidence_repo=repo,
                    verifier=nli_verifier,
                    quality_evaluator=runner.gateway.tier1_service.quality_evaluator,
                )
                custom_gateway = GatewayService(
                    model_provider=runner.gateway.model_provider,
                    preflight_service=runner.gateway.preflight_service,
                    tier0_service=runner.gateway.tier0_service,
                    risk_engine=runner.gateway.risk_engine,
                    tier1_service=custom_tier1,
                    adjudication_service=runner.gateway.adjudication_service,
                    repair_service=runner.gateway.repair_service,
                    action_engine=runner.gateway.action_engine,
                    state_store=runner.gateway.state_store,
                    session_risk_tracker=runner.gateway.session_risk_tracker,
                    multi_label_aggregator=runner.gateway.multi_label_aggregator,
                )

                app_id = CUSTOMER_SUPPORT_APP_ID
                if case.application_profile == "INTERNAL_KNOWLEDGE":
                    app_id = INTERNAL_KB_APP_ID
                elif case.application_profile == "DECISION_SUPPORT":
                    app_id = DECISION_SUPPORT_APP_ID

                session_id = case.session_id or f"ablation-{mode_name}-{case.case_id}"
                req = GatewayInspectRequest(
                    application_id=app_id,
                    prompt=case.prompt,
                    response=case.response_fixture,
                    session_id=session_id,
                )

                t0 = time.perf_counter()
                resp = await custom_gateway.inspect(req, db)
                tot_time = round((time.perf_counter() - t0) * 1000.0, 2)

                actual_action = resp.action.value
                actual_risk_types = list(resp.risk_assessment.risk_types) if resp.risk_assessment else []
                actual_severity = resp.risk_assessment.severity.value if resp.risk_assessment and hasattr(resp.risk_assessment.severity, "value") else "LOW"
                actual_highest_sev = resp.risk_assessment.highest_severity.value if resp.risk_assessment and hasattr(resp.risk_assessment.highest_severity, "value") else "LOW"

                primary_claim = resp.claims[0] if resp.claims else None
                actual_nli = primary_claim.final_label if primary_claim else None
                actual_conf = primary_claim.nli_confidence if primary_claim else None
                actual_status = primary_claim.verification_status.value if primary_claim else "NOT_REQUIRED"
                actual_trigger = primary_claim.adjudication_trigger.value if primary_claim else "NONE"
                top2_scores = primary_claim.top2_scores if primary_claim else None

                if resp.adjudication_invocations == 0:
                    if primary_claim and primary_claim.uncertainty_reason.value == "ADJUDICATION_BUDGET_EXHAUSTED":
                        actual_outcome = "BUDGET_EXHAUSTED"
                    else:
                        actual_outcome = "NOT_REQUIRED"
                else:
                    if actual_status == "ADJUDICATED":
                        actual_outcome = "ADJUDICATED"
                    elif actual_status == "ADJUDICATION_INCONCLUSIVE":
                        actual_outcome = "INCONCLUSIVE"
                    else:
                        actual_outcome = "ADJUDICATED"

                passed = (actual_action == case.expected_final_action)

                pcr = PerCaseResult(
                    case_id=case.case_id,
                    passed=passed,
                    expected_final_action=case.expected_final_action,
                    actual_final_action=actual_action,
                    expected_nli_label=case.expected_nli_label,
                    actual_nli_label=actual_nli,
                    nli_confidence=actual_conf,
                    nli_top2_scores=top2_scores,
                    expected_risk_types=case.expected_risk_types,
                    actual_risk_types=actual_risk_types,
                    expected_severity=case.expected_severity,
                    actual_severity=actual_severity,
                    actual_highest_severity=actual_highest_sev,
                    actual_verification_status=actual_status,
                    expected_adjudication_trigger=case.expected_adjudication_trigger,
                    actual_adjudication_trigger=actual_trigger,
                    expected_adjudication_outcome=case.expected_adjudication_outcome,
                    actual_adjudication_outcome=actual_outcome,
                    total_latency_ms=tot_time,
                    tier0_latency_ms=resp.timing_telemetry.tier0_ms,
                    risk_latency_ms=resp.timing_telemetry.risk_ms,
                    tier1_latency_ms=resp.timing_telemetry.tier1_ms,
                    adjudication_latency_ms=resp.timing_telemetry.adjudication_ms,
                    repair_latency_ms=resp.timing_telemetry.repair_ms,
                    action_latency_ms=resp.timing_telemetry.action_ms,
                    session_risk_latency_ms=resp.timing_telemetry.session_risk_ms,
                    estimated_cost_usd=resp.cost_telemetry.total_cost_usd,
                    total_tokens=resp.cost_telemetry.total_tokens,
                    adjudication_calls=resp.adjudication_invocations,
                    repair_attempts=resp.cost_telemetry.repair_attempts,
                )
                results.append(pcr)

            mode_results[mode_name] = results

    # Compute comparative metrics
    comparison_summary = {}
    for mode_name, res_list in mode_results.items():
        total = len(res_list)
        passed_count = sum(1 for r in res_list if r.passed)
        accuracy = passed_count / total if total > 0 else 0.0

        action_matches = sum(1 for r in res_list if r.actual_final_action == r.expected_final_action)
        action_acc = action_matches / total if total > 0 else 0.0

        nli_evaluated = [r for r in res_list if r.expected_nli_label is not None]
        nli_matches = sum(1 for r in nli_evaluated if r.actual_nli_label == r.expected_nli_label)
        nli_acc = nli_matches / len(nli_evaluated) if nli_evaluated else 0.0

        unsafe_passes = sum(
            1 for r in res_list
            if r.expected_final_action in ["BLOCK", "ESCALATE"] and r.actual_final_action == "ALLOW"
        )
        unsafe_rate = unsafe_passes / total if total > 0 else 0.0

        adj_calls = sum(r.adjudication_calls for r in res_list)
        repair_calls = sum(r.repair_attempts for r in res_list)

        latencies = [r.total_latency_ms for r in res_list]
        p50_lat = float(np.percentile(latencies, 50)) if latencies else 0.0
        p95_lat = float(np.percentile(latencies, 95)) if latencies else 0.0
        tier1_lats = [r.tier1_latency_ms for r in res_list]
        avg_t1_lat = sum(tier1_lats) / len(tier1_lats) if tier1_lats else 0.0

        cost_total = sum(r.estimated_cost_usd for r in res_list)

        comparison_summary[mode_name] = {
            "total_cases": total,
            "overall_accuracy": round(accuracy, 4),
            "final_action_accuracy": round(action_acc, 4),
            "nli_accuracy": round(nli_acc, 4),
            "unsafe_pass_rate": round(unsafe_rate, 4),
            "adjudication_count": adj_calls,
            "repair_count": repair_calls,
            "latency_p50_ms": round(p50_lat, 2),
            "latency_p95_ms": round(p95_lat, 2),
            "avg_tier1_latency_ms": round(avg_t1_lat, 2),
            "total_estimated_cost_usd": round(cost_total, 6),
        }

        print(f"Mode {mode_name}: Accuracy={accuracy:.4f}, ActionAcc={action_acc:.4f}, NLIAcc={nli_acc:.4f}, UnsafePasses={unsafe_passes}, P95Lat={p95_lat:.2f}ms")

    # Failure Classification & Comparison between LEXICAL and SEMANTIC
    lex_res = {r.case_id: r for r in mode_results["LEXICAL"]}
    sem_res = {r.case_id: r for r in mode_results["SEMANTIC"]}
    hyb_res = {r.case_id: r for r in mode_results["HYBRID"]}

    classification_counts = {
        "LEXICAL_ONLY_SUCCESS": 0,
        "SEMANTIC_ONLY_SUCCESS": 0,
        "BOTH_SUCCESS": 0,
        "BOTH_FAILURE": 0,
        "RETRIEVAL_MISS": 0,
        "RETRIEVAL_IRRELEVANT": 0,
        "EVIDENCE_QUALITY_FAILURE": 0,
        "NLI_FAILURE": 0,
        "DOWNSTREAM_DECISION_FAILURE": 0,
    }

    case_diagnostics = []

    for c_id, l_r in lex_res.items():
        s_r = sem_res[c_id]
        h_r = hyb_res[c_id]

        if l_r.passed and s_r.passed:
            classification_counts["BOTH_SUCCESS"] += 1
            cat = "BOTH_SUCCESS"
        elif s_r.passed and not l_r.passed:
            classification_counts["SEMANTIC_ONLY_SUCCESS"] += 1
            classification_counts["RETRIEVAL_MISS"] += 1
            cat = "SEMANTIC_ONLY_SUCCESS (Semantic fixed lexical retrieval miss)"
        elif l_r.passed and not s_r.passed:
            classification_counts["LEXICAL_ONLY_SUCCESS"] += 1
            classification_counts["RETRIEVAL_IRRELEVANT"] += 1
            cat = "LEXICAL_ONLY_SUCCESS (Semantic retrieved irrelevant context)"
        else:
            classification_counts["BOTH_FAILURE"] += 1
            # Classify root cause of failure
            if l_r.expected_nli_label != l_r.actual_nli_label and s_r.expected_nli_label != s_r.actual_nli_label:
                classification_counts["NLI_FAILURE"] += 1
                cat = "BOTH_FAILURE (NLI model verifier limitation)"
            elif l_r.expected_final_action != l_r.actual_final_action:
                classification_counts["DOWNSTREAM_DECISION_FAILURE"] += 1
                cat = "BOTH_FAILURE (Action engine / policy routing)"
            else:
                classification_counts["EVIDENCE_QUALITY_FAILURE"] += 1
                cat = "BOTH_FAILURE (Evidence quality inadequate)"

        case_diagnostics.append({
            "case_id": c_id,
            "lexical_passed": l_r.passed,
            "semantic_passed": s_r.passed,
            "hybrid_passed": h_r.passed,
            "category": cat,
        })

    output_data = {
        "summary": comparison_summary,
        "failure_classification": classification_counts,
        "case_diagnostics": case_diagnostics,
    }

    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"\nEnd-to-end ablation results saved to {out_file}")
    print(f"Classification Breakdown: {classification_counts}")


if __name__ == "__main__":
    asyncio.run(run_end_to_end_ablation())
