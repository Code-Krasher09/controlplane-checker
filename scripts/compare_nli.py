import json
import time
from collections import defaultdict
from app.tier1.nli_real import RealNLIVerifier
from app.domain.models import ClaimVerificationItem, EvidenceSnippet
from uuid import uuid4

def run_comparison():
    with open("data/evaluation/nli_microbench/microbench.jsonl", "r") as f:
        cases = [json.loads(line) for line in f]
        
    configs = [
        {
            "name": "Current Adapter + Current Model",
            "model": "cross-encoder/nli-deberta-v3-small",
            "truncation": True
        },
        {
            "name": "Corrected Semantics + Current Model",
            "model": "cross-encoder/nli-deberta-v3-small",
            "truncation": "only_first"
        },
        {
            "name": "Alternative Model + Correct Semantics",
            "model": "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli",
            "truncation": "only_first"
        }
    ]
    
    results = {}
    
    for cfg in configs:
        print(f"\nEvaluating: {cfg['name']}")
        try:
            verifier = RealNLIVerifier(model_name=cfg["model"], truncation_strategy=cfg["truncation"])
        except Exception as e:
            print(f"Failed to load {cfg['model']}: {e}")
            continue
            
        t0 = time.perf_counter()
        
        correct = 0
        per_class_total = {"SUPPORTED": 0, "CONTRADICTED": 0, "INSUFFICIENT_EVIDENCE": 0}
        per_class_correct = {"SUPPORTED": 0, "CONTRADICTED": 0, "INSUFFICIENT_EVIDENCE": 0}
        
        # Confidence calibration buckets
        buckets = {
            "0.0-0.5": {"total": 0, "correct": 0, "ambiguous": 0},
            "0.5-0.6": {"total": 0, "correct": 0, "ambiguous": 0},
            "0.6-0.7": {"total": 0, "correct": 0, "ambiguous": 0},
            "0.7-0.8": {"total": 0, "correct": 0, "ambiguous": 0},
            "0.8-0.9": {"total": 0, "correct": 0, "ambiguous": 0},
            "0.9-1.0": {"total": 0, "correct": 0, "ambiguous": 0},
        }
        
        for c in cases:
            claim = ClaimVerificationItem(claim_text=c["hypothesis"])
            evidence = [EvidenceSnippet(evidence_id=uuid4(), source_type="TEST", source_id="1", content_snippet=c["premise"])]
            
            resp = verifier.verify(claim, evidence)
            
            exp = c["expected"]
            act = resp.label
            conf = resp.nli_confidence or 0.0
            
            per_class_total[exp] += 1
            if exp == act:
                correct += 1
                per_class_correct[exp] += 1
                
            # Bucket
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
                if act == "INSUFFICIENT_EVIDENCE" and exp != "INSUFFICIENT_EVIDENCE":
                    buckets[b]["ambiguous"] += 1
                    
        latency = time.perf_counter() - t0
        
        # Calculate Macro F1 / Recall
        recalls = []
        for k in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]:
            if per_class_total[k] > 0:
                recalls.append(per_class_correct[k] / per_class_total[k])
            else:
                recalls.append(0.0)
        macro_recall = sum(recalls) / 3
        
        print(f"Accuracy: {correct}/{len(cases)} ({correct/len(cases):.2f})")
        print(f"Macro Recall: {macro_recall:.2f}")
        print(f"Supported Recall: {recalls[0]:.2f}")
        print(f"Contradicted Recall: {recalls[1]:.2f}")
        print(f"Insufficient Recall: {recalls[2]:.2f}")
        print(f"Latency: {latency:.2f}s")
        
        print("Confidence Calibration:")
        for b, v in buckets.items():
            if v["total"] > 0:
                acc = v["correct"] / v["total"]
                err = (v["total"] - v["correct"]) / v["total"]
                print(f"  {b}: N={v['total']}, Acc={acc:.2f}, Err={err:.2f}")
                
        results[cfg["name"]] = {
            "accuracy": correct/len(cases),
            "macro_recall": macro_recall,
            "latency": latency,
            "calibration": buckets
        }
        
    with open("artifacts/evaluation/nli_comparison.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_comparison()
