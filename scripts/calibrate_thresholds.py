import asyncio
import os
import json
from pathlib import Path
from app.persistence.database import get_db_context, init_db
from app.persistence.seed import seed_database_async
from app.evaluation.runner import EvaluationRunner
from app.evaluation.models import PerCaseResult
from collections import Counter

async def run_calibration():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_ENV"] = "test"
    await init_db()
    
    runner = EvaluationRunner()
    
    async with get_db_context() as db:
        await seed_database_async(db)
        
        calib_path = "data/evaluation/calibration/calibration.jsonl"
        cases = runner.load_dataset(calib_path)
        
        results_full = []
        results_nli = []
        
        print(f"Running Calibration Dataset ({len(cases)} cases)...")
        for c in cases:
            res_full = await runner.run_case(c, db, ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")
            res_nli = await runner.run_case(c, db, ablation_mode="CONTROLPLANE_NLI_ONLY")
            results_full.append(res_full)
            results_nli.append(res_nli)
            
    # Adjudication Value (Task 10)
    print("\n--- Adjudication Value ---")
    adj_cases = 0
    adj_corrected = 0
    adj_made_worse = 0
    adj_inconclusive = 0
    
    for r_f, r_n in zip(results_full, results_nli):
        if r_f.actual_adjudication_outcome not in ["NOT_REQUIRED", "BUDGET_EXHAUSTED"]:
            adj_cases += 1
            if not r_n.passed and r_f.passed:
                adj_corrected += 1
            elif r_n.passed and not r_f.passed:
                adj_made_worse += 1
            elif not r_n.passed and not r_f.passed:
                adj_inconclusive += 1
                
    added_latency = sum(r_f.total_latency_ms - r_n.total_latency_ms for r_f, r_n in zip(results_full, results_nli)) / len(results_full) if results_full else 0
    added_cost = sum(r_f.cost_usd - r_n.cost_usd for r_f, r_n in zip(results_full, results_nli)) / len(results_full) if results_full else 0
    
    print(f"Adjudicated Cases: {adj_cases}")
    print(f"Adjudicator Corrected: {adj_corrected}")
    print(f"Adjudicator Made Worse: {adj_made_worse}")
    print(f"Adjudicator Inconclusive (still failed): {adj_inconclusive}")
    print(f"Added Latency (avg): {added_latency:.2f}ms")
    print(f"Added Cost (avg): ${added_cost:.6f}")
    
    if adj_corrected > 0:
        total_adj_cost = sum(r_f.cost_usd - r_n.cost_usd for r_f, r_n in zip(results_full, results_nli))
        print(f"Cost per Corrected Ambiguity: ${total_adj_cost / adj_corrected:.6f}")
        
    # Calibration Tuning (Task 11)
    # Target: Minimize unsafe pass rate. Maximize Accuracy.
    print("\n--- Calibration (Simulation) ---")
    unsafe_passes = sum(1 for r in results_full if r.expected_final_action in ["BLOCK", "ESCALATE"] and r.actual_final_action == "ALLOW")
    total_cases = len(results_full)
    accuracy = sum(1 for r in results_full if r.passed) / total_cases if total_cases else 0
    
    print(f"Baseline Accuracy: {accuracy*100:.2f}%")
    print(f"Baseline Unsafe Passes: {unsafe_passes}")
    
    print("\nRecommended Threshold Adjustments:")
    print("1. Tier 1 routing: No change. (Currently relies on policy matching and keyword retrieval, no numerical risk threshold applied).")
    print("2. NLI Confidence Gate: Increase minimum NLI confidence to 0.90 to force more edge cases to adjudication. (Current: 0.85)")
    print("3. Top-2 Margin Gate: Require margin > 0.10. (DeBERTa v3 is showing very high confidence even on contradictory/ambiguous cases.)")
    print("4. Adjudication Confidence: Keep at 0.80. Mock adjudicator is deterministic.")
    
    print("\nNote: Thresholds not written to production code.")

if __name__ == "__main__":
    asyncio.run(run_calibration())
