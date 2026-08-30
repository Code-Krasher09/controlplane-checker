import asyncio
import os
import json
from app.persistence.database import get_db_context, init_db
from app.persistence.seed import seed_database_async
from app.evaluation.runner import EvaluationRunner

async def run_routing_test():
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
    os.environ["APP_ENV"] = "test"
    await init_db()
    
    runner = EvaluationRunner()
    
    async with get_db_context() as db:
        await seed_database_async(db)
        
        path = "data/evaluation/holdout/holdout.jsonl"
        cases = runner.load_dataset(path)
        
        print("Running Configuration A: Risk Engine WITH Semantic Consistency")
        results_with = []
        for c in cases:
            res = await runner.run_case(c, db, ablation_mode="CONTROLPLANE_NLI_ONLY")
            results_with.append(res)
            
        print("Running Configuration B: Risk Engine WITHOUT Semantic Consistency (fixed score=0.85)")
        # Monkeypatch semantic consistency
        from app.tier0.semantic_real import RealSemanticConsistencyScorer
        old_calc = RealSemanticConsistencyScorer.calculate_score
        def dummy_calc(self, prompt, response): return 0.85
        RealSemanticConsistencyScorer.calculate_score = dummy_calc
        
        results_without = []
        for c in cases:
            res = await runner.run_case(c, db, ablation_mode="CONTROLPLANE_NLI_ONLY")
            results_without.append(res)
            
        RealSemanticConsistencyScorer.calculate_score = old_calc
        
    print("\n--- Routing Impact Results ---")
    
    tier1_with = sum(1 for r in results_with if r.actual_nli_label)
    unnecessary_with = sum(1 for r in results_with if r.actual_nli_label and not r.expected_nli_label)
    missed_with = sum(1 for r in results_with if not r.actual_nli_label and r.expected_nli_label)
    
    tier1_without = sum(1 for r in results_without if r.actual_nli_label)
    unnecessary_without = sum(1 for r in results_without if r.actual_nli_label and not r.expected_nli_label)
    missed_without = sum(1 for r in results_without if not r.actual_nli_label and r.expected_nli_label)
    
    print(f"WITH Semantic Consistency:")
    print(f"  Tier 1 Invocations: {tier1_with}")
    print(f"  Unnecessary Tier 1: {unnecessary_with}")
    print(f"  Missed High-Risk: {missed_with}")
    
    print(f"\nWITHOUT Semantic Consistency:")
    print(f"  Tier 1 Invocations: {tier1_without}")
    print(f"  Unnecessary Tier 1: {unnecessary_without}")
    print(f"  Missed High-Risk: {missed_without}")
    
    if tier1_without > tier1_with:
        print(f"\nConclusion: Semantic Consistency reduces unnecessary Tier 1 by {tier1_without - tier1_with} cases.")
    elif tier1_without < tier1_with:
        print(f"\nConclusion: Semantic Consistency increases Tier 1 coverage by {tier1_with - tier1_without} cases.")
    else:
        print(f"\nConclusion: Semantic Consistency had zero routing impact on this dataset.")

if __name__ == "__main__":
    asyncio.run(run_routing_test())
