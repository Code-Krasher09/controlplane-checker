import json
import asyncio
import time
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.evaluation.runner import EvaluationRunner
from app.evaluation.dataset_generator import generate_holdout_dataset
from app.persistence.database import Base
from app.domain.models import VerificationStatus

async def evaluate_selective_architecture():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async_session_factory = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    
    holdout_cases = generate_holdout_dataset()
    
    configs = [
        {"name": "ALWAYS_ON_MOCK_JUDGE", "mode": "ALWAYS_ON_LLM_JUDGE_MOCK"},
        {"name": "NLI_ONLY", "mode": "CONTROLPLANE_NLI_ONLY"},
        {"name": "NLI_SELECTIVE_LLM", "mode": "CONTROLPLANE_NLI_ADJUDICATION"}
    ]
    
    results = {}
    
    for cfg in configs:
        print(f"\nRunning config: {cfg['name']}")
        async with async_session_factory() as session:
            from app.persistence.seed import seed_database_async
            await seed_database_async(session)
            
            runner = EvaluationRunner()
            
            t0 = time.perf_counter()
            latencies = []
            
            correct = 0
            unsafe_pass = 0
            judge_invocations = 0
            
            applicable_cases = 0
            
            verifier_action_cross = []
            
            for case in holdout_cases:
                if case.expected_final_action is None:
                    continue
                    
                ct0 = time.perf_counter()
                res = await runner.run_case(case, session, ablation_mode=cfg["mode"])
                latencies.append(time.perf_counter() - ct0)
                
                applicable_cases += 1
                
                # Check correctness
                if res.actual_final_action == case.expected_final_action:
                    correct += 1
                elif case.expected_final_action in ["BLOCK", "ESCALATE"] and res.actual_final_action in ["ALLOW", "WARN"]:
                    unsafe_pass += 1
                    
                # Check judge invocation (Proxy: if VerificationStatus is ADJUDICATED)
                if res.actual_adjudication_outcome != "NOT_REQUIRED" and res.actual_adjudication_outcome != "INCONCLUSIVE" and res.actual_adjudication_outcome is not None:
                    # Actually, if actual_adjudication_outcome is present and not NOT_REQUIRED
                    # Let's be safer: if adjudication_trigger != NONE
                    if res.actual_adjudication_trigger != "NONE":
                        judge_invocations += 1
                        
                # Cross check
                if res.expected_nli_label:
                    nli_c = (res.actual_nli_label == res.expected_nli_label)
                    act_c = (res.actual_final_action == case.expected_final_action)
                    if nli_c and act_c: cat = "A"
                    elif nli_c and not act_c: cat = "B"
                    elif not nli_c and act_c: cat = "C"
                    elif not nli_c and not act_c: cat = "D"
                    else: cat = "E"
                    verifier_action_cross.append(cat)
                else:
                    verifier_action_cross.append("E")
                    
            p95 = sorted(latencies)[int(len(latencies)*0.95)] if latencies else 0.0
            
            cross_counts = {k: verifier_action_cross.count(k) for k in ["A", "B", "C", "D", "E"]}
            
            results[cfg["name"]] = {
                "accuracy": correct / applicable_cases,
                "unsafe_pass_rate": unsafe_pass / applicable_cases,
                "judge_invocation_rate": judge_invocations / applicable_cases,
                "p95_latency": p95,
                "cross_analysis": cross_counts,
                "total_cases": applicable_cases
            }
            
    with open("artifacts/evaluation/selective_architecture.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("Selective Architecture test complete.")

if __name__ == "__main__":
    asyncio.run(evaluate_selective_architecture())
