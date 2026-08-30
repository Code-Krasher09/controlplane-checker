"""Comprehensive Phase 10 Evaluation Script: Real LLM Semantic Verification Evaluation."""

import asyncio
import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.domain.models import ClaimVerificationItem, EvidenceSnippet, GatewayInspectRequest
from app.evaluation.dataset_generator import generate_holdout_dataset, generate_calibration_dataset
from app.evaluation.evidence_repo import EvaluationEvidenceRepository
from app.evaluation.models import BenchmarkCase
from app.evaluation.runner import EvaluationRunner
from app.gateway.service import GatewayService
from app.persistence.database import Base
from app.persistence.seed import seed_database_async
from app.tier1.gemini_nli import GeminiNLIVerifier
from app.tier1.nli_real import RealNLIVerifier
from app.tier1.semantic_verifier import GeminiSemanticVerifier
from app.tier1.service import Tier1Service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phase10_eval")


async def run_microbenchmark(gemini_verifier: GeminiSemanticVerifier) -> Dict[str, Any]:
    """Run Part 4: 30-case NLI microbenchmark across Small NLI, Base NLI, and Real Gemini."""
    with open("data/evaluation/nli_microbench/microbench.jsonl", "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    verifiers = [
        {"name": "SMALL_NLI", "model": "cross-encoder/nli-deberta-v3-small", "type": "nli"},
        {"name": "BASE_NLI", "model": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli", "type": "nli"},
        {"name": "REAL_GEMINI", "model": gemini_verifier.model_name, "type": "gemini"},
    ]

    results = {}

    for v_info in verifiers:
        name = v_info["name"]
        print(f"\n--- Running Microbenchmark on {name} ({v_info['model']}) ---")

        if v_info["type"] == "nli":
            nli_model = RealNLIVerifier(model_name=v_info["model"], truncation_strategy="only_first")
        else:
            nli_model = None

        correct = 0
        per_class_total = defaultdict(int)
        per_class_correct = defaultdict(int)

        type_total = defaultdict(int)
        type_correct = defaultdict(int)

        latencies = []
        token_usage = {"input_tokens": 0, "output_tokens": 0}
        confidence_buckets = {
            "0.0-0.5": {"total": 0, "correct": 0, "errors": 0},
            "0.5-0.6": {"total": 0, "correct": 0, "errors": 0},
            "0.6-0.7": {"total": 0, "correct": 0, "errors": 0},
            "0.7-0.8": {"total": 0, "correct": 0, "errors": 0},
            "0.8-0.9": {"total": 0, "correct": 0, "errors": 0},
            "0.9-1.0": {"total": 0, "correct": 0, "errors": 0},
        }

        for c in cases:
            premise = c["premise"]
            hypothesis = c["hypothesis"]
            expected = c["expected"]
            case_type = c.get("type", "general")

            per_class_total[expected] += 1
            type_total[case_type] += 1

            t0 = time.perf_counter()
            if v_info["type"] == "nli":
                claim = ClaimVerificationItem(claim_text=hypothesis)
                evidence = [EvidenceSnippet(evidence_id=uuid4(), source_type="TEST", source_id="1", content_snippet=premise)]
                resp = nli_model.verify(claim, evidence)
                label = resp.label
                confidence = resp.nli_confidence or 0.0
            else:
                resp = await gemini_verifier.verify_async(hypothesis, [premise])
                label = resp.label
                confidence = resp.confidence
                token_usage["input_tokens"] += resp.input_tokens
                token_usage["output_tokens"] += resp.output_tokens

            lat_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(lat_ms)

            is_correct = (label == expected)
            if is_correct:
                correct += 1
                per_class_correct[expected] += 1
                type_correct[case_type] += 1

            # Bucketing
            if confidence <= 0.5: b = "0.0-0.5"
            elif confidence <= 0.6: b = "0.5-0.6"
            elif confidence <= 0.7: b = "0.6-0.7"
            elif confidence <= 0.8: b = "0.7-0.8"
            elif confidence <= 0.9: b = "0.8-0.9"
            else: b = "0.9-1.0"

            confidence_buckets[b]["total"] += 1
            if is_correct:
                confidence_buckets[b]["correct"] += 1
            else:
                confidence_buckets[b]["errors"] += 1

        recalls = {
            k: (per_class_correct[k] / per_class_total[k] if per_class_total[k] > 0 else 0.0)
            for k in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
        }
        macro_f1 = sum(recalls.values()) / 3.0

        p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
        p50_lat = sorted(latencies)[int(len(latencies) * 0.50)] if latencies else 0.0
        mean_lat = sum(latencies) / len(latencies) if latencies else 0.0

        results[name] = {
            "model": v_info["model"],
            "accuracy": correct / len(cases),
            "macro_f1": macro_f1,
            "supported_recall": recalls["SUPPORTED"],
            "contradiction_recall": recalls["CONTRADICTED"],
            "insufficient_recall": recalls["INSUFFICIENT_EVIDENCE"],
            "fine_grained_accuracy": {
                k: (type_correct[k] / type_total[k]) for k in type_total
            },
            "p50_latency_ms": p50_lat,
            "p95_latency_ms": p95_lat,
            "mean_latency_ms": mean_lat,
            "token_usage": token_usage,
            "confidence_calibration": confidence_buckets,
        }

    return results


async def run_adjudication_benchmark(gemini_verifier: GeminiSemanticVerifier) -> Dict[str, Any]:
    """Run 20-case adjudication benchmark."""
    with open("data/evaluation/adjudication_bench/adjudication_bench.jsonl", "r", encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    small_nli = RealNLIVerifier(model_name="cross-encoder/nli-deberta-v3-small", truncation_strategy="only_first")

    results = {
        "should_trigger_count": 0,
        "should_trigger_caught_by_gate": 0,
        "must_not_trigger_insufficient_caught": 0,
        "must_not_trigger_insufficient_total": 0,
        "must_not_trigger_confident_caught": 0,
        "must_not_trigger_confident_total": 0,
        "gemini_accuracy_on_ambiguity": 0,
        "small_nli_accuracy_on_ambiguity": 0,
        "total_ambiguity_cases": 0,
        "case_details": [],
    }

    for c in cases:
        premise = c["premise"]
        hypothesis = c["hypothesis"]
        expected_label = c["expected_label"]
        expected_trigger = c["expected_trigger"]

        # Run Small NLI
        claim = ClaimVerificationItem(claim_text=hypothesis)
        evidence = [EvidenceSnippet(evidence_id=uuid4(), source_type="TEST", source_id="1", content_snippet=premise)]
        nli_res = small_nli.verify(claim, evidence)

        # Run Gemini
        gem_res = await gemini_verifier.verify_async(hypothesis, [premise])

        # Check Confidence Gate
        gate_triggered = (nli_res.label != "INSUFFICIENT_EVIDENCE" and nli_res.nli_confidence < 0.90)

        if expected_trigger == "SHOULD_TRIGGER":
            results["should_trigger_count"] += 1
            results["total_ambiguity_cases"] += 1
            if gate_triggered:
                results["should_trigger_caught_by_gate"] += 1
            if gem_res.label == expected_label:
                results["gemini_accuracy_on_ambiguity"] += 1
            if nli_res.label == expected_label:
                results["small_nli_accuracy_on_ambiguity"] += 1
        elif expected_trigger == "MUST_NOT_TRIGGER":
            if c.get("trigger_reason") == "MISSING_EVIDENCE":
                results["must_not_trigger_insufficient_total"] += 1
                if not gate_triggered:
                    results["must_not_trigger_insufficient_caught"] += 1
            else:
                results["must_not_trigger_confident_total"] += 1
                if not gate_triggered:
                    results["must_not_trigger_confident_caught"] += 1

        results["case_details"].append({
            "case_id": c["case_id"],
            "expected_label": expected_label,
            "expected_trigger": expected_trigger,
            "nli_label": nli_res.label,
            "nli_confidence": nli_res.nli_confidence,
            "gate_triggered": gate_triggered,
            "gemini_label": gem_res.label,
            "gemini_confidence": gem_res.confidence,
        })

    return results


async def run_holdout_and_architectures(gemini_verifier: GeminiSemanticVerifier) -> Dict[str, Any]:
    """Run full holdout across all architecture configurations."""
    holdout_cases = generate_holdout_dataset()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    small_nli = RealNLIVerifier(model_name="cross-encoder/nli-deberta-v3-small", truncation_strategy="only_first")
    base_nli = RealNLIVerifier(model_name="MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli", truncation_strategy="only_first")
    gemini_nli = GeminiNLIVerifier(gemini_verifier=gemini_verifier)

    architectures = [
        {"name": "NO_CHECKER", "mode": "NO_CHECKER", "verifier": None},
        {"name": "SMALL_NLI", "mode": "CONTROLPLANE_NLI_ONLY", "verifier": small_nli},
        {"name": "BASE_NLI", "mode": "CONTROLPLANE_NLI_ONLY", "verifier": base_nli},
        {"name": "REAL_GEMINI_ALWAYS_ON", "mode": "CONTROLPLANE_NLI_ONLY", "verifier": gemini_nli},
        {"name": "NLI_SELECTIVE_REAL_GEMINI", "mode": "SELECTIVE_GEMINI", "verifier": small_nli},
        {"name": "HIGH_SEVERITY_SELECTIVE_GEMINI", "mode": "HIGH_SEVERITY_GEMINI", "verifier": small_nli},
    ]

    arch_results = {}
    gemini_failures = []

    for arch in architectures:
        arch_name = arch["name"]
        print(f"\nEvaluating Architecture: {arch_name} ...")

        async with async_session_factory() as session:
            await seed_database_async(session)
            runner = EvaluationRunner()

            total_cases = 0
            action_correct = 0
            unsafe_passes = 0
            unnecessary_escalations = 0
            repair_attempts = 0
            escalations = 0
            gemini_invocations = 0
            latencies = []
            token_usage = {"input_tokens": 0, "output_tokens": 0}

            cross_analysis = {"A": 0, "B": 0, "C": 0, "D": 0, "E": 0}

            for case in holdout_cases:
                if case.expected_final_action is None:
                    continue

                total_cases += 1
                t0 = time.perf_counter()

                # Custom execution for selective architectures
                if arch_name == "NO_CHECKER":
                    res = await runner.run_case(case, session, ablation_mode="NO_CHECKER")
                elif arch_name in ["SMALL_NLI", "BASE_NLI"]:
                    tier1 = Tier1Service(verifier=arch["verifier"])
                    runner.gateway.tier1_service = tier1
                    res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ONLY")
                elif arch_name == "REAL_GEMINI_ALWAYS_ON":
                    tier1 = Tier1Service(verifier=gemini_nli)
                    runner.gateway.tier1_service = tier1
                    res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ONLY")
                    gemini_invocations += 1
                elif arch_name == "NLI_SELECTIVE_REAL_GEMINI":
                    # Run small NLI first; if confidence gate triggers, adjudicate with Gemini
                    tier1_small = Tier1Service(verifier=small_nli)
                    runner.gateway.tier1_service = tier1_small
                    res_initial = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")

                    if res_initial.actual_adjudication_trigger != "NONE":
                        gemini_invocations += 1
                        tier1_gem = Tier1Service(verifier=gemini_nli)
                        runner.gateway.tier1_service = tier1_gem
                        res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ONLY")
                    else:
                        res = res_initial
                elif arch_name == "HIGH_SEVERITY_SELECTIVE_GEMINI":
                    # Run small NLI; if High/Critical severity AND not safe, call Gemini
                    tier1_small = Tier1Service(verifier=small_nli)
                    runner.gateway.tier1_service = tier1_small
                    res_initial = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ONLY")

                    is_high_sev = case.expected_severity in ["HIGH", "CRITICAL"]
                    needs_llm = is_high_sev or (res_initial.actual_adjudication_trigger != "NONE")

                    if needs_llm:
                        gemini_invocations += 1
                        tier1_gem = Tier1Service(verifier=gemini_nli)
                        runner.gateway.tier1_service = tier1_gem
                        res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ONLY")
                    else:
                        res = res_initial

                lat_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(lat_ms)

                # Metrics calculation
                exp_action = case.expected_final_action
                act_action = res.actual_final_action

                if act_action == exp_action:
                    action_correct += 1
                elif exp_action in ["BLOCK", "ESCALATE"] and act_action in ["ALLOW", "WARN"]:
                    unsafe_passes += 1
                elif exp_action == "ALLOW" and act_action in ["ESCALATE", "BLOCK"]:
                    unnecessary_escalations += 1

                if act_action == "ESCALATE":
                    escalations += 1

                # Cross Analysis
                if res.expected_nli_label:
                    nli_c = (res.actual_nli_label == res.expected_nli_label)
                    act_c = (act_action == exp_action)
                    if nli_c and act_c: cross_analysis["A"] += 1
                    elif nli_c and not act_c: cross_analysis["B"] += 1
                    elif not nli_c and act_c: cross_analysis["C"] += 1
                    elif not nli_c and not act_c: cross_analysis["D"] += 1
                    else: cross_analysis["E"] += 1
                else:
                    cross_analysis["E"] += 1

                # Track failure for REAL_GEMINI_ALWAYS_ON
                if arch_name == "REAL_GEMINI_ALWAYS_ON" and (res.actual_nli_label != res.expected_nli_label and res.expected_nli_label is not None):
                    gemini_failures.append({
                        "case_id": case.case_id,
                        "prompt": case.prompt,
                        "expected_nli": case.expected_nli_label,
                        "actual_nli": res.actual_nli_label,
                        "expected_action": case.expected_final_action,
                        "actual_action": act_action,
                        "error_category": "semantic reasoning error" if res.actual_nli_label != "INSUFFICIENT_EVIDENCE" else "evidence insufficiency error",
                    })

            p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0.0
            p50_lat = sorted(latencies)[int(len(latencies) * 0.50)] if latencies else 0.0

            arch_results[arch_name] = {
                "total_cases": total_cases,
                "action_accuracy": action_correct / total_cases,
                "unsafe_pass_rate": unsafe_passes / total_cases,
                "unnecessary_escalation_rate": unnecessary_escalations / total_cases,
                "escalation_rate": escalations / total_cases,
                "gemini_invocations": gemini_invocations,
                "gemini_invocation_rate": gemini_invocations / total_cases,
                "gemini_calls_saved": total_cases - gemini_invocations,
                "gemini_calls_saved_percent": (total_cases - gemini_invocations) / total_cases,
                "p50_latency_ms": p50_lat,
                "p95_latency_ms": p95_lat,
                "cross_analysis": cross_analysis,
            }

    return {
        "architectures": arch_results,
        "gemini_failures": gemini_failures,
    }


async def main():
    print("==================================================")
    print("STARTING PHASE 10: REAL GEMINI EVALUATION PIPELINE")
    print("==================================================")

    gemini_verifier = GeminiSemanticVerifier()
    print(f"Initialized GeminiSemanticVerifier with model: {gemini_verifier.model_name}")

    # 1. Microbenchmark
    micro_results = await run_microbenchmark(gemini_verifier)

    # 2. Adjudication Benchmark
    adj_results = await run_adjudication_benchmark(gemini_verifier)

    # 3. Holdout & Architectures
    holdout_data = await run_holdout_and_architectures(gemini_verifier)

    # Save Artifacts
    # 1. real_verifier_action_comparison.json
    with open("artifacts/evaluation/real_verifier_action_comparison.json", "w", encoding="utf-8") as f:
        json.dump(holdout_data["architectures"], f, indent=2)

    # 2. real_gemini_failure_analysis.json
    with open("artifacts/evaluation/real_gemini_failure_analysis.json", "w", encoding="utf-8") as f:
        json.dump({
            "total_failures": len(holdout_data["gemini_failures"]),
            "failures": holdout_data["gemini_failures"],
        }, f, indent=2)

    # 3. final_verifier_decision_matrix.json
    decision_matrix = {
        "SMALL_NLI": {
            "micro_accuracy": micro_results["SMALL_NLI"]["accuracy"],
            "macro_f1": micro_results["SMALL_NLI"]["macro_f1"],
            "contradiction_recall": micro_results["SMALL_NLI"]["contradiction_recall"],
            "insufficient_recall": micro_results["SMALL_NLI"]["insufficient_recall"],
            "holdout_action_accuracy": holdout_data["architectures"]["SMALL_NLI"]["action_accuracy"],
            "unsafe_pass_rate": holdout_data["architectures"]["SMALL_NLI"]["unsafe_pass_rate"],
            "unnecessary_escalation_rate": holdout_data["architectures"]["SMALL_NLI"]["unnecessary_escalation_rate"],
            "p95_latency_ms": holdout_data["architectures"]["SMALL_NLI"]["p95_latency_ms"],
            "gemini_invocation_rate": 0.0,
            "cost_per_case": "$0.00",
        },
        "BASE_NLI": {
            "micro_accuracy": micro_results["BASE_NLI"]["accuracy"],
            "macro_f1": micro_results["BASE_NLI"]["macro_f1"],
            "contradiction_recall": micro_results["BASE_NLI"]["contradiction_recall"],
            "insufficient_recall": micro_results["BASE_NLI"]["insufficient_recall"],
            "holdout_action_accuracy": holdout_data["architectures"]["BASE_NLI"]["action_accuracy"],
            "unsafe_pass_rate": holdout_data["architectures"]["BASE_NLI"]["unsafe_pass_rate"],
            "unnecessary_escalation_rate": holdout_data["architectures"]["BASE_NLI"]["unnecessary_escalation_rate"],
            "p95_latency_ms": holdout_data["architectures"]["BASE_NLI"]["p95_latency_ms"],
            "gemini_invocation_rate": 0.0,
            "cost_per_case": "$0.00",
        },
        "REAL_GEMINI_ALWAYS_ON": {
            "micro_accuracy": micro_results["REAL_GEMINI"]["accuracy"],
            "macro_f1": micro_results["REAL_GEMINI"]["macro_f1"],
            "contradiction_recall": micro_results["REAL_GEMINI"]["contradiction_recall"],
            "insufficient_recall": micro_results["REAL_GEMINI"]["insufficient_recall"],
            "holdout_action_accuracy": holdout_data["architectures"]["REAL_GEMINI_ALWAYS_ON"]["action_accuracy"],
            "unsafe_pass_rate": holdout_data["architectures"]["REAL_GEMINI_ALWAYS_ON"]["unsafe_pass_rate"],
            "unnecessary_escalation_rate": holdout_data["architectures"]["REAL_GEMINI_ALWAYS_ON"]["unnecessary_escalation_rate"],
            "p95_latency_ms": holdout_data["architectures"]["REAL_GEMINI_ALWAYS_ON"]["p95_latency_ms"],
            "gemini_invocation_rate": 1.0,
            "cost_per_case": "UNMEASURED (Token counts tracked)",
        },
        "NLI_SELECTIVE_REAL_GEMINI": {
            "micro_accuracy": "N/A (Architecture)",
            "macro_f1": "N/A",
            "contradiction_recall": "N/A",
            "insufficient_recall": "N/A",
            "holdout_action_accuracy": holdout_data["architectures"]["NLI_SELECTIVE_REAL_GEMINI"]["action_accuracy"],
            "unsafe_pass_rate": holdout_data["architectures"]["NLI_SELECTIVE_REAL_GEMINI"]["unsafe_pass_rate"],
            "unnecessary_escalation_rate": holdout_data["architectures"]["NLI_SELECTIVE_REAL_GEMINI"]["unnecessary_escalation_rate"],
            "p95_latency_ms": holdout_data["architectures"]["NLI_SELECTIVE_REAL_GEMINI"]["p95_latency_ms"],
            "gemini_invocation_rate": holdout_data["architectures"]["NLI_SELECTIVE_REAL_GEMINI"]["gemini_invocation_rate"],
            "calls_saved_percent": holdout_data["architectures"]["NLI_SELECTIVE_REAL_GEMINI"]["gemini_calls_saved_percent"],
            "cost_per_case": "Proportional to invocation rate",
        },
        "HIGH_SEVERITY_SELECTIVE_GEMINI": {
            "micro_accuracy": "N/A (Architecture)",
            "macro_f1": "N/A",
            "contradiction_recall": "N/A",
            "insufficient_recall": "N/A",
            "holdout_action_accuracy": holdout_data["architectures"]["HIGH_SEVERITY_SELECTIVE_GEMINI"]["action_accuracy"],
            "unsafe_pass_rate": holdout_data["architectures"]["HIGH_SEVERITY_SELECTIVE_GEMINI"]["unsafe_pass_rate"],
            "unnecessary_escalation_rate": holdout_data["architectures"]["HIGH_SEVERITY_SELECTIVE_GEMINI"]["unnecessary_escalation_rate"],
            "p95_latency_ms": holdout_data["architectures"]["HIGH_SEVERITY_SELECTIVE_GEMINI"]["p95_latency_ms"],
            "gemini_invocation_rate": holdout_data["architectures"]["HIGH_SEVERITY_SELECTIVE_GEMINI"]["gemini_invocation_rate"],
            "calls_saved_percent": holdout_data["architectures"]["HIGH_SEVERITY_SELECTIVE_GEMINI"]["gemini_calls_saved_percent"],
            "cost_per_case": "Proportional to invocation rate",
        },
    }

    with open("artifacts/evaluation/final_verifier_decision_matrix.json", "w", encoding="utf-8") as f:
        json.dump(decision_matrix, f, indent=2)

    # Output full summary to console
    print("\n==================================================")
    print("PHASE 10 EVALUATION COMPLETE")
    print("==================================================")
    print(f"Microbenchmark Results:\n{json.dumps(micro_results, indent=2)}")
    print(f"\nAdjudication Benchmark Results:\n{json.dumps(adj_results, indent=2)}")
    print(f"\nFinal Architecture Matrix:\n{json.dumps(decision_matrix, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
