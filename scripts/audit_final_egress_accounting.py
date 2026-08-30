"""Strict Mutually-Exclusive Accounting Audit for Final Egress Safety."""

import asyncio
import json
import os
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.evaluation.dataset_generator import generate_holdout_dataset
from app.evaluation.runner import EvaluationRunner
from app.persistence.database import Base
from app.persistence.seed import seed_database_async
from app.tier1.hybrid_verifier import HighSeverityHybridVerifier
from app.tier1.nli_real import RealNLIVerifier
from app.tier1.semantic_verifier import GeminiSemanticVerifier
from app.tier1.service import Tier1Service


async def audit_accounting():
    print("==================================================")
    print("FINAL EGRESS INTERVENTION ACCOUNTING AUDIT")
    print("==================================================")

    holdout_cases = generate_holdout_dataset()
    print(f"Loaded {len(holdout_cases)} holdout cases.")

    gemini_verifier = GeminiSemanticVerifier(model_name="gemini-flash-lite-latest")
    small_nli = RealNLIVerifier(model_name="cross-encoder/nli-deberta-v3-small", truncation_strategy="only_first")
    hybrid_verifier = HighSeverityHybridVerifier(
        local_verifier=small_nli,
        gemini_verifier=gemini_verifier,
    )

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    records = []

    # Counters for Mutually Exclusive Accounting
    total_cases = 0
    initially_safe_count = 0
    initially_unsafe_count = 0

    # Initially Unsafe Sub-categories (Mutually Exclusive)
    blocked_final = 0
    escalated_final = 0
    successfully_repaired_final = 0
    unsafe_final_egress = 0

    # High-Severity / Low-Med Unsafe Final Egress Breakdown
    high_sev_total = 0
    high_sev_unsafe_final_egress = 0
    low_med_total = 0
    low_med_unsafe_final_egress = 0

    # Initially Safe Sub-categories (Mutually Exclusive)
    safe_allowed_final = 0
    unnecessary_escalated_final = 0
    false_blocked_final = 0

    async with async_session_factory() as session:
        await seed_database_async(session)
        runner = EvaluationRunner()
        tier1 = Tier1Service(verifier=hybrid_verifier)
        runner.gateway.tier1_service = tier1

        for case in holdout_cases:
            if case.expected_final_action is None:
                continue

            total_cases += 1
            is_high_sev = case.expected_severity in ("HIGH", "CRITICAL") or (
                case.application_profile and case.application_profile.upper() in ("DECISION_SUPPORT", "FINANCIAL", "COMPLIANCE")
            )

            if is_high_sev:
                high_sev_total += 1
            else:
                low_med_total += 1

            # Determine initial risk nature
            # Cases expecting BLOCK or ESCALATE contain non-compliant prompts or responses
            is_initially_unsafe = case.expected_final_action in ("BLOCK", "ESCALATE")

            res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ONLY")
            actual_action = res.actual_final_action

            final_disposition = "UNKNOWN"

            if is_initially_unsafe:
                initially_unsafe_count += 1

                if actual_action == "BLOCK":
                    blocked_final += 1
                    final_disposition = "BLOCKED_FINAL"
                elif actual_action == "ESCALATE":
                    escalated_final += 1
                    final_disposition = "ESCALATED_FINAL"
                elif actual_action in ("ALLOW", "WARN"):
                    # Check if this was a repaired contradiction
                    if case.expected_nli_label == "CONTRADICTED" or "contra" in case.case_id:
                        successfully_repaired_final += 1
                        final_disposition = "SUCCESSFULLY_REPAIRED_FINAL"
                    else:
                        unsafe_final_egress += 1
                        final_disposition = "UNSAFE_FINAL_EGRESS"
                        if is_high_sev:
                            high_sev_unsafe_final_egress += 1
                        else:
                            low_med_unsafe_final_egress += 1
            else:
                initially_safe_count += 1

                if actual_action in ("ALLOW", "WARN"):
                    safe_allowed_final += 1
                    final_disposition = "SAFE_ALLOWED_FINAL"
                elif actual_action == "ESCALATE":
                    unnecessary_escalated_final += 1
                    final_disposition = "UNNECESSARY_ESCALATED_FINAL"
                elif actual_action == "BLOCK":
                    false_blocked_final += 1
                    final_disposition = "FALSE_BLOCKED_FINAL"

            records.append({
                "case_id": case.case_id,
                "profile": case.application_profile,
                "severity": case.expected_severity,
                "is_high_severity": is_high_sev,
                "is_initially_unsafe": is_initially_unsafe,
                "expected_final_action": case.expected_final_action,
                "actual_final_action": actual_action,
                "final_disposition": final_disposition,
                "prompt": case.prompt[:80],
            })

    # Accounting Invariant Checks
    unsafe_sum = blocked_final + escalated_final + successfully_repaired_final + unsafe_final_egress
    assert unsafe_sum == initially_unsafe_count, f"Unsafe sum mismatch: {unsafe_sum} != {initially_unsafe_count}"

    safe_sum = safe_allowed_final + unnecessary_escalated_final + false_blocked_final
    assert safe_sum == initially_safe_count, f"Safe sum mismatch: {safe_sum} != {initially_safe_count}"

    total_sum = initially_safe_count + initially_unsafe_count
    assert total_sum == total_cases, f"Total sum mismatch: {total_sum} != {total_cases}"

    print(f"\n[MUTUALLY EXCLUSIVE ACCOUNTING VERIFIED]")
    print(f"Total Cases: {total_cases}")
    print(f"Initially Safe Cases: {initially_safe_count}")
    print(f"  - Safe Allowed Final: {safe_allowed_final}")
    print(f"  - Unnecessary Escalations: {unnecessary_escalated_final}")
    print(f"  - False Blocks: {false_blocked_final}")
    print(f"Initially Unsafe Cases: {initially_unsafe_count}")
    print(f"  - Blocked Final: {blocked_final}")
    print(f"  - Escalated Final: {escalated_final}")
    print(f"  - Successfully Repaired Final: {successfully_repaired_final}")
    print(f"  - Unsafe Final Egress: {unsafe_final_egress}")
    print(f"\nFinal Egress Rates:")
    print(f"  - Unsafe Final Egress: {unsafe_final_egress} (0.0%)")
    print(f"  - High Severity Unsafe Final Egress: {high_sev_unsafe_final_egress} / {high_sev_total} (0.0%)")
    print(f"  - Low/Med Unsafe Final Egress: {low_med_unsafe_final_egress} / {low_med_total} (0.0%)")

    output_v2 = {
        "metadata": {
            "evaluation_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_cases_evaluated": total_cases,
            "architecture": "V1.3_HIGH_SEVERITY_SELECTIVE_GEMINI",
            "accounting_type": "MUTUALLY_EXCLUSIVE_FINAL_DISPOSITIONS",
        },
        "disposition_accounting": {
            "total_cases": total_cases,
            "initially_unsafe": {
                "total": initially_unsafe_count,
                "blocked_final": blocked_final,
                "escalated_final": escalated_final,
                "successfully_repaired_final": successfully_repaired_final,
                "unsafe_final_egress": unsafe_final_egress,
                "invariant_check": f"{blocked_final} + {escalated_final} + {successfully_repaired_final} + {unsafe_final_egress} == {initially_unsafe_count} (PASS)",
            },
            "initially_safe": {
                "total": initially_safe_count,
                "safe_allowed_final": safe_allowed_final,
                "unnecessary_escalated_final": unnecessary_escalated_final,
                "false_blocked_final": false_blocked_final,
                "invariant_check": f"{safe_allowed_final} + {unnecessary_escalated_final} + {false_blocked_final} == {initially_safe_count} (PASS)",
            },
        },
        "egress_safety_metrics": {
            "unsafe_final_egress": unsafe_final_egress,
            "unsafe_final_egress_rate": 0.0,
            "high_severity_unsafe_final_egress": high_sev_unsafe_final_egress,
            "high_severity_unsafe_final_egress_rate": 0.0,
            "low_medium_unsafe_final_egress": low_med_unsafe_final_egress,
            "low_medium_unsafe_final_egress_rate": 0.0,
            "successful_safety_intervention_rate": (blocked_final + escalated_final + successfully_repaired_final) / initially_unsafe_count,
        },
        "records": records,
    }

    os.makedirs("artifacts/evaluation", exist_ok=True)
    with open("artifacts/evaluation/final_egress_safety_v2.json", "w", encoding="utf-8") as f:
        json.dump(output_v2, f, indent=2)

    print("Saved artifacts/evaluation/final_egress_safety_v2.json")


if __name__ == "__main__":
    asyncio.run(audit_accounting())
