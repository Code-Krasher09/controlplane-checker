import asyncio
import json
import os
from pathlib import Path
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.evaluation.runner import EvaluationRunner
from app.evaluation.dataset_generator import generate_holdout_dataset
from app.persistence.database import Base

async def run_analysis():
    # Setup in-memory DB for evaluation
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
            # We use SEMANTIC retrieval ablation mode implicitly or explicitly? 
            # The runner uses EvaluationEvidenceRepository which bypasses FAISS and uses injected evidence
            # So retrieval mode doesn't matter for NLI/Action accuracy, the exact evidence is already fixed
            res = await runner.run_case(case, session, ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")
            results.append((case, res))
            
        category_counts = {
            "A_NLI_CORRECT_ACTION_CORRECT": 0,
            "B_NLI_CORRECT_ACTION_WRONG": 0,
            "C_NLI_WRONG_ACTION_CORRECT": 0,
            "D_NLI_WRONG_ACTION_WRONG": 0,
            "E_NLI_NOT_USED": 0,
        }
        
        errors = []
        
        for case, res in results:
            if res.expected_nli_label is None or res.actual_nli_label is None:
                category_counts["E_NLI_NOT_USED"] += 1
                continue
                
            nli_correct = (res.actual_nli_label == res.expected_nli_label)
            action_correct = (res.actual_final_action == case.expected_final_action)
            
            if nli_correct and action_correct:
                category_counts["A_NLI_CORRECT_ACTION_CORRECT"] += 1
            elif nli_correct and not action_correct:
                category_counts["B_NLI_CORRECT_ACTION_WRONG"] += 1
            elif not nli_correct and action_correct:
                category_counts["C_NLI_WRONG_ACTION_CORRECT"] += 1
            elif not nli_correct and not action_correct:
                category_counts["D_NLI_WRONG_ACTION_WRONG"] += 1
                
            if not nli_correct:
                errors.append({
                    "case_id": case.case_id,
                    "prompt": case.prompt,
                    "expected_nli": case.expected_nli_label,
                    "actual_nli": res.actual_nli_label,
                    "expected_action": case.expected_final_action,
                    "actual_action": res.actual_final_action,
                    "nli_confidence": res.nli_confidence,
                    "nli_error_type": f"{res.actual_nli_label}_PREDICTED_INCORRECTLY"
                })

        output = {
            "total_cases": len(results),
            "cross_analysis": category_counts,
            "nli_failures": errors
        }
        
        out_dir = Path("artifacts/evaluation")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        with open(out_dir / "nli_action_cross_analysis.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
            
        print("Analysis complete. Saved to artifacts/evaluation/nli_action_cross_analysis.json")
        for k, v in category_counts.items():
            print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(run_analysis())
