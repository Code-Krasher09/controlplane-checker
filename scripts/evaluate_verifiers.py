import json
import time
from collections import defaultdict
from uuid import uuid4

from app.domain.models import ClaimVerificationItem, EvidenceSnippet
from app.tier1.nli_real import RealNLIVerifier

def evaluate_verifiers():
    with open("data/evaluation/nli_microbench/microbench.jsonl", "r") as f:
        micro_cases = [json.loads(line) for line in f]
        
    configs = [
        {"name": "SMALL_LOCAL_NLI", "model": "cross-encoder/nli-deberta-v3-small"},
        {"name": "LARGER_LOCAL_NLI", "model": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"}
    ]
    
    results = {}
    
    for cfg in configs:
        print(f"\nEvaluating: {cfg['name']}")
        try:
            verifier = RealNLIVerifier(model_name=cfg["model"], truncation_strategy="only_first")
        except Exception as e:
            print(f"Failed to load {cfg['model']}: {e}")
            continue
            
        t0 = time.perf_counter()
        
        correct = 0
        per_class_total = {"SUPPORTED": 0, "CONTRADICTED": 0, "INSUFFICIENT_EVIDENCE": 0}
        per_class_correct = {"SUPPORTED": 0, "CONTRADICTED": 0, "INSUFFICIENT_EVIDENCE": 0}
        
        num_contra_total, num_contra_correct = 0, 0
        temp_contra_total, temp_contra_correct = 0, 0
        neg_total, neg_correct = 0, 0
        
        buckets = {
            "0.0-0.5": {"total": 0, "correct": 0, "errors": 0},
            "0.5-0.6": {"total": 0, "correct": 0, "errors": 0},
            "0.6-0.7": {"total": 0, "correct": 0, "errors": 0},
            "0.7-0.8": {"total": 0, "correct": 0, "errors": 0},
            "0.8-0.9": {"total": 0, "correct": 0, "errors": 0},
            "0.9-1.0": {"total": 0, "correct": 0, "errors": 0},
        }
        
        latencies = []
        
        for c in micro_cases:
            claim = ClaimVerificationItem(claim_text=c["hypothesis"])
            evidence = [EvidenceSnippet(evidence_id=uuid4(), source_type="TEST", source_id="1", content_snippet=c["premise"])]
            
            ct0 = time.perf_counter()
            resp = verifier.verify(claim, evidence)
            latencies.append(time.perf_counter() - ct0)
            
            exp = c["expected"]
            act = resp.label
            conf = resp.nli_confidence or 0.0
            
            per_class_total[exp] += 1
            if exp == act:
                correct += 1
                per_class_correct[exp] += 1
                
            tags = c.get("tags", [])
            if "numerical" in tags:
                num_contra_total += 1
                if exp == act: num_contra_correct += 1
            if "temporal" in tags:
                temp_contra_total += 1
                if exp == act: temp_contra_correct += 1
            if "negation" in tags:
                neg_total += 1
                if exp == act: neg_correct += 1
                
            # Bucketing
            if conf <= 0.5: b = "0.0-0.5"
            elif conf <= 0.6: b = "0.5-0.6"
            elif conf <= 0.7: b = "0.6-0.7"
            elif conf <= 0.8: b = "0.7-0.8"
            elif conf <= 0.9: b = "0.8-0.9"
            else: b = "0.9-1.0"
            
            buckets[b]["total"] += 1
            if exp == act:
                buckets[b]["correct"] += 1
            else:
                buckets[b]["errors"] += 1
                    
        total_time = time.perf_counter() - t0
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        recalls = {
            k: (per_class_correct[k] / per_class_total[k] if per_class_total[k] > 0 else 0.0)
            for k in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]
        }
        macro_recall = sum(recalls.values()) / 3
        
        results[cfg["name"]] = {
            "model_version": cfg["model"],
            "accuracy": correct / len(micro_cases),
            "macro_f1": macro_recall,  # using macro recall as proxy for now
            "supported_recall": recalls["SUPPORTED"],
            "contradiction_recall": recalls["CONTRADICTED"],
            "insufficient_recall": recalls["INSUFFICIENT_EVIDENCE"],
            "numerical_contradiction_accuracy": (num_contra_correct/num_contra_total) if num_contra_total > 0 else None,
            "temporal_contradiction_accuracy": (temp_contra_correct/temp_contra_total) if temp_contra_total > 0 else None,
            "negation_accuracy": (neg_correct/neg_total) if neg_total > 0 else None,
            "p95_latency": p95_latency,
            "cost_per_case": 0.0,
            "calibration": buckets
        }
        
    results["REAL_LLM_JUDGE"] = "NOT_RUN"
        
    with open("artifacts/evaluation/verifier_comparison.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("Verifier Comparison complete. Results saved.")

if __name__ == "__main__":
    evaluate_verifiers()
