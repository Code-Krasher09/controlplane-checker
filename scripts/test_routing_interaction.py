"""Routing Interaction Experiment with fixed Semantic Retrieval."""

import asyncio
import json
import os
import sys
import time
from typing import Any, Dict, List

from app.domain.models import ClaimEvidenceQuality, EvidenceSnippet
from app.evaluation.runner import EvaluationRunner
from app.gateway.service import GatewayInspectRequest, GatewayService
from app.persistence.database import get_db_context, init_db
from app.persistence.seed import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)
from app.tier0.semantic_real import RealSemanticConsistencyScorer
from app.tier1.nli_real import RealNLIVerifier
from app.tier1.retrieval.chunking import DocumentChunker
from app.tier1.retrieval.embedding import RealEmbeddingProvider
from app.tier1.retrieval.semantic_repo import SemanticEvidenceRepository
from app.tier1.service import Tier1Service


async def run_routing_interaction_experiment(
    holdout_path: str = "data/evaluation/holdout/holdout.jsonl",
    corpus_path: str = "data/corpus/enterprise_corpus.json",
    index_dir: str = "data/index",
    out_file: str = "artifacts/evaluation/routing_interaction.json",
):
    """Evaluate Risk Engine Tier 1 routing behavior with and without Tier 0 Semantic Consistency."""
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_ENV"] = "test"
    await init_db()

    index_file = os.path.join(index_dir, "faiss_index.bin")
    meta_file = os.path.join(index_dir, "metadata.json")
    embedding_provider = RealEmbeddingProvider()
    semantic_repo = SemanticEvidenceRepository(
        embedding_provider=embedding_provider,
        index_path=index_file,
        metadata_path=meta_file,
    )
    nli_verifier = RealNLIVerifier()

    runner = EvaluationRunner()
    cases = runner.load_dataset(holdout_path)
    print(f"Running Routing Interaction Experiment across {len(cases)} holdout cases...")

    results_data = {}

    async with get_db_context() as db:
        await seed_database_async(db)

        # 1. WITH Real Semantic Consistency
        print("\n--- Running Configuration A: Risk Engine WITH Semantic Consistency (Semantic Retrieval Fixed) ---")
        t0_all = time.perf_counter()
        t1_invocations_with = 0
        unnecessary_t1_with = 0
        missed_high_risk_with = 0
        latencies_with = []
        costs_with = []

        for case in cases:
            tier1 = Tier1Service(
                evidence_repo=semantic_repo,
                verifier=nli_verifier,
                quality_evaluator=runner.gateway.tier1_service.quality_evaluator,
            )
            gw = GatewayService(
                model_provider=runner.gateway.model_provider,
                preflight_service=runner.gateway.preflight_service,
                tier0_service=runner.gateway.tier0_service,
                risk_engine=runner.gateway.risk_engine,
                tier1_service=tier1,
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

            req = GatewayInspectRequest(
                application_id=app_id,
                prompt=case.prompt,
                response=case.response_fixture,
                session_id=f"routing-with-{case.case_id}",
            )

            t0 = time.perf_counter()
            resp = await gw.inspect(req, db)
            lat = (time.perf_counter() - t0) * 1000.0
            latencies_with.append(lat)
            costs_with.append(resp.cost_telemetry.total_cost_usd)

            has_tier1 = len(resp.claims) > 0
            if has_tier1:
                t1_invocations_with += 1
                if case.expected_nli_label is None and case.expected_evidence_state == "NOT_REQUIRED":
                    unnecessary_t1_with += 1
            else:
                if case.expected_severity in ["HIGH", "CRITICAL"] and case.expected_nli_label is not None:
                    missed_high_risk_with += 1

        results_data["WITH_SEMANTIC_CONSISTENCY"] = {
            "tier1_invocations": t1_invocations_with,
            "tier1_invocation_rate": round(t1_invocations_with / len(cases), 4),
            "unnecessary_tier1_count": unnecessary_t1_with,
            "missed_high_risk_count": missed_high_risk_with,
            "avg_latency_ms": round(sum(latencies_with) / len(latencies_with), 2),
            "total_cost_usd": round(sum(costs_with), 6),
        }

        # 2. WITHOUT Semantic Consistency (Fixed neutral score = 0.85)
        print("\n--- Running Configuration B: Risk Engine WITHOUT Semantic Consistency (Fixed Neutral Score = 0.85) ---")
        old_scorer = RealSemanticConsistencyScorer.calculate_score
        RealSemanticConsistencyScorer.calculate_score = lambda self, prompt, response: 0.85

        t1_invocations_without = 0
        unnecessary_t1_without = 0
        missed_high_risk_without = 0
        latencies_without = []
        costs_without = []

        for case in cases:
            tier1 = Tier1Service(
                evidence_repo=semantic_repo,
                verifier=nli_verifier,
                quality_evaluator=runner.gateway.tier1_service.quality_evaluator,
            )
            gw = GatewayService(
                model_provider=runner.gateway.model_provider,
                preflight_service=runner.gateway.preflight_service,
                tier0_service=runner.gateway.tier0_service,
                risk_engine=runner.gateway.risk_engine,
                tier1_service=tier1,
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

            req = GatewayInspectRequest(
                application_id=app_id,
                prompt=case.prompt,
                response=case.response_fixture,
                session_id=f"routing-without-{case.case_id}",
            )

            t0 = time.perf_counter()
            resp = await gw.inspect(req, db)
            lat = (time.perf_counter() - t0) * 1000.0
            latencies_without.append(lat)
            costs_without.append(resp.cost_telemetry.total_cost_usd)

            has_tier1 = len(resp.claims) > 0
            if has_tier1:
                t1_invocations_without += 1
                if case.expected_nli_label is None and case.expected_evidence_state == "NOT_REQUIRED":
                    unnecessary_t1_without += 1
            else:
                if case.expected_severity in ["HIGH", "CRITICAL"] and case.expected_nli_label is not None:
                    missed_high_risk_without += 1

        RealSemanticConsistencyScorer.calculate_score = old_scorer

        results_data["WITHOUT_SEMANTIC_CONSISTENCY"] = {
            "tier1_invocations": t1_invocations_without,
            "tier1_invocation_rate": round(t1_invocations_without / len(cases), 4),
            "unnecessary_tier1_count": unnecessary_t1_without,
            "missed_high_risk_count": missed_high_risk_without,
            "avg_latency_ms": round(sum(latencies_without) / len(latencies_without), 2),
            "total_cost_usd": round(sum(costs_without), 6),
        }

    # Summary
    print("\n================== ROUTING INTERACTION RESULTS ==================")
    print(f"WITH Semantic Consistency:    Invocations={t1_invocations_with}/{len(cases)} ({results_data['WITH_SEMANTIC_CONSISTENCY']['tier1_invocation_rate']}), Unnecessary={unnecessary_t1_with}, MissedHighRisk={missed_high_risk_with}, Latency={results_data['WITH_SEMANTIC_CONSISTENCY']['avg_latency_ms']}ms")
    print(f"WITHOUT Semantic Consistency: Invocations={t1_invocations_without}/{len(cases)} ({results_data['WITHOUT_SEMANTIC_CONSISTENCY']['tier1_invocation_rate']}), Unnecessary={unnecessary_t1_without}, MissedHighRisk={missed_high_risk_without}, Latency={results_data['WITHOUT_SEMANTIC_CONSISTENCY']['avg_latency_ms']}ms")

    os.makedirs(os.path.dirname(os.path.abspath(out_file)), exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print(f"Results saved to {out_file}")


if __name__ == "__main__":
    asyncio.run(run_routing_interaction_experiment())
