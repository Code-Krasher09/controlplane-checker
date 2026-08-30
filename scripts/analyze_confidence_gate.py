import json
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.evaluation.runner import EvaluationRunner
from app.evaluation.dataset_generator import generate_holdout_dataset
from app.persistence.database import Base

async def analyze_confidence_gate():
    # Setup DB
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    async with async_session_factory() as session:
        from app.persistence.seed import seed_database_async
        await seed_database_async(session)
        
        runner = EvaluationRunner()
        holdout_cases = generate_holdout_dataset()
        
        results = []
        for case in holdout_cases:
            res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")
            if res.expected_nli_label is not None:  # Only cases where NLI runs
                results.append((case, res))
                
        metrics = {
            "total_applicable_cases": len(results),
            "nli_errors": 0,
            "gate_triggered": 0,
            "gate_precision_num": 0, # Triggered AND was an NLI error
            "gate_precision_denom": 0, # Triggered at all (including false triggers)
            "gate_recall_num": 0, # NLI errors caught by gate
            "gate_recall_denom": 0, # Total NLI errors
            "false_triggers": 0, # Triggered but NLI was correct
            "missed_ambiguities": 0 # Not triggered but NLI was wrong
        }
        
        fourteen_errors = []
        
        for case, res in results:
            nli_correct = (res.actual_nli_label == res.expected_nli_label)
            if not nli_correct:
                metrics["nli_errors"] += 1
                
            gate_triggered = res.actual_adjudication_trigger != "NONE"
            
            if gate_triggered:
                metrics["gate_triggered"] += 1
                metrics["gate_precision_denom"] += 1
                if not nli_correct:
                    metrics["gate_precision_num"] += 1
                    metrics["gate_recall_num"] += 1
                else:
                    metrics["false_triggers"] += 1
            else:
                if not nli_correct:
                    metrics["missed_ambiguities"] += 1
                    
            if not nli_correct:
                fourteen_errors.append({
                    "case_id": case.case_id,
                    "expected": case.expected_nli_label,
                    "actual": res.actual_nli_label,
                    "confidence": res.nli_confidence,
                    "gate_triggered": gate_triggered,
                    "trigger_reason": res.actual_adjudication_trigger
                })

        metrics["gate_recall_denom"] = metrics["nli_errors"]
        metrics["gate_precision"] = metrics["gate_precision_num"] / max(1, metrics["gate_precision_denom"])
        metrics["gate_recall"] = metrics["gate_recall_num"] / max(1, metrics["gate_recall_denom"])
        metrics["false_trigger_rate"] = metrics["false_triggers"] / max(1, metrics["total_applicable_cases"])
        metrics["missed_ambiguity_rate"] = metrics["missed_ambiguities"] / max(1, metrics["nli_errors"])
        metrics["adjudication_coverage"] = metrics["gate_triggered"] / max(1, metrics["total_applicable_cases"])
        
        output = {
            "all_case_metrics": metrics,
            "diagnostic_subset": fourteen_errors
        }
        
        with open("artifacts/evaluation/confidence_gate_analysis.json", "w") as f:
            json.dump(output, f, indent=2)
            
        print("Confidence Gate analysis complete. Saved to artifacts/evaluation/confidence_gate_analysis.json")
        for k, v in metrics.items():
            print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(analyze_confidence_gate())
