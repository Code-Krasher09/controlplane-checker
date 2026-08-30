import asyncio
import json
import os
from pathlib import Path
from collections import Counter
from typing import Any, Dict, List

from app.persistence.database import get_db_context, init_db
from app.persistence.seed import seed_database_async
from app.evaluation.runner import EvaluationRunner
from app.evaluation.models import PerCaseResult

def classify_failure(case: PerCaseResult) -> str:
    """Classify the primary failure stage based on the trace."""
    if case.passed:
        return "PASS"
        
    exp_action = case.expected_final_action
    act_action = case.actual_final_action
    
    # Check Risk Routing First
    # If the case expected NLI/Adjudication but it was bypassed by Risk Engine
    if case.expected_nli_label and not case.actual_nli_label:
        return "RISK_ROUTING"
    
    if not case.expected_nli_label and case.actual_nli_label:
        return "RISK_ROUTING"

    # Check NLI / Confidence Gate / Adjudication
    if case.expected_nli_label and case.actual_nli_label:
        if case.actual_adjudication_outcome != case.expected_adjudication_outcome:
            # If adjudication outcome is wrong, check if it's the gate or adjudicator
            if case.actual_adjudication_trigger != case.expected_adjudication_trigger:
                return "CONFIDENCE_GATE"
            else:
                return "ADJUDICATION"
        
        # If adjudication outcome is correct (or both didn't adjudicate), check NLI label
        if case.actual_nli_label != case.expected_nli_label:
            return "NLI_VERIFICATION"
            
    # Check Evidence Quality
    # In this mock evaluation, evidence is injected directly. 
    # If action is wrong but all NLI/Risk is correct, check action engine.
    if exp_action != act_action:
        return "ACTION_ENGINE"
        
    return "OTHER"

async def run_analysis():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_ENV"] = "test"
    
    print("Initializing Database...")
    await init_db()
    
    async with get_db_context() as db:
        await seed_database_async(db)
        
        runner = EvaluationRunner()
        
        print("Running Analysis on Holdout Dataset (FULL_CASCADE)...")
        holdout_path = "data/evaluation/holdout/holdout.jsonl"
        cases = runner.load_dataset(holdout_path)
        
        results: List[PerCaseResult] = []
        for c in cases:
            res = await runner.run_case(c, db, ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")
            res.likely_failure_stage = classify_failure(res)
            res.diagnostic_explanation = f"Failed at {res.likely_failure_stage}. Exp Action: {res.expected_final_action}, Act: {res.actual_final_action}"
            results.append(res)
            
        print("Running Analysis on Challenge Dataset (FULL_CASCADE)...")
        chal_path = "data/evaluation/challenge/challenge.jsonl"
        chal_cases = runner.load_dataset(chal_path)
        for c in chal_cases:
            res = await runner.run_case(c, db, ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")
            res.likely_failure_stage = classify_failure(res)
            res.diagnostic_explanation = f"Failed at {res.likely_failure_stage}. Exp Action: {res.expected_final_action}, Act: {res.actual_final_action}"
            results.append(res)
            
        # 1. Failure Distribution
        failures = [r for r in results if not r.passed]
        counts = Counter(r.likely_failure_stage for r in failures)
        
        total_failures = len(failures)
        distribution = {k: {"count": v, "percentage": (v / total_failures) * 100 if total_failures else 0} for k, v in counts.items()}
        
        # 2. Routing Coverage
        expected_tier1 = sum(1 for r in results if r.expected_nli_label)
        actual_tier1 = sum(1 for r in results if r.actual_nli_label)
        false_skips = sum(1 for r in results if r.expected_nli_label and not r.actual_nli_label)
        unnecessary_tier1 = sum(1 for r in results if not r.expected_nli_label and r.actual_nli_label)
        
        expected_adj = sum(1 for r in results if r.expected_adjudication_outcome != "NOT_REQUIRED")
        actual_adj = sum(1 for r in results if r.actual_adjudication_outcome not in ["NOT_REQUIRED", "BUDGET_EXHAUSTED"])
        missed_adj = sum(1 for r in results if r.expected_adjudication_outcome != "NOT_REQUIRED" and r.actual_adjudication_outcome == "NOT_REQUIRED")
        unnecessary_adj = sum(1 for r in results if r.expected_adjudication_outcome == "NOT_REQUIRED" and r.actual_adjudication_outcome != "NOT_REQUIRED")
        
        routing = {
            "expected_tier1": expected_tier1,
            "actual_tier1": actual_tier1,
            "false_skips": false_skips,
            "unnecessary_tier1": unnecessary_tier1,
            "expected_adjudication": expected_adj,
            "actual_adjudication": actual_adj,
            "missed_adjudication": missed_adj,
            "unnecessary_adjudication": unnecessary_adj,
        }
        
        # 3. Confusion Matrices
        nli_matrix = {"SUPPORTED": {}, "CONTRADICTED": {}, "INSUFFICIENT_EVIDENCE": {}}
        action_matrix = {"ALLOW": {}, "WARN": {}, "ABSTAIN": {}, "REPAIR": {}, "BLOCK": {}, "ESCALATE": {}}
        
        for r in results:
            if r.expected_nli_label:
                exp_nli = r.expected_nli_label
                act_nli = r.actual_nli_label or "NONE"
                if exp_nli not in nli_matrix: nli_matrix[exp_nli] = {}
                nli_matrix[exp_nli][act_nli] = nli_matrix[exp_nli].get(act_nli, 0) + 1
                
            exp_act = r.expected_final_action
            act_act = r.actual_final_action
            if exp_act not in action_matrix: action_matrix[exp_act] = {}
            action_matrix[exp_act][act_act] = action_matrix[exp_act].get(act_act, 0) + 1
            
        summary = {
            "failure_distribution": distribution,
            "routing_coverage": routing,
            "confusion_matrices": {
                "nli_label": nli_matrix,
                "final_action": action_matrix
            }
        }
        
        out_dir = Path("artifacts/evaluation")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        with open(out_dir / "failure_analysis_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
            
        with open(out_dir / "failure_analysis.json", "w") as f:
            json.dump([r.model_dump() for r in failures], f, indent=2)
            
        with open(out_dir / "confusion_matrices_v2.json", "w") as f:
            json.dump(summary["confusion_matrices"], f, indent=2)
            
        print(f"Analysis complete. Total cases: {len(results)}, Failures: {len(failures)}")
        print(f"Distribution: {counts}")

if __name__ == "__main__":
    asyncio.run(run_analysis())
