import json
from pathlib import Path
from collections import Counter

def run_dataset_quality():
    out_dir = Path("artifacts/evaluation")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    datasets = ["data/evaluation/calibration/calibration.jsonl",
                "data/evaluation/holdout/holdout.jsonl",
                "data/evaluation/challenge/challenge.jsonl"]
                
    total_cases = 0
    prompts = []
    normalized_prompts = []
    actions = Counter()
    nli_labels = Counter()
    categories = Counter()
    
    for path in datasets:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                c = json.loads(line)
                total_cases += 1
                prompt = c["prompt"]
                prompts.append(prompt)
                normalized_prompts.append(prompt.lower().strip().replace(" ", "").replace(".", ""))
                
                actions[c["expected_final_action"]] += 1
                if c["expected_nli_label"]:
                    nli_labels[c["expected_nli_label"]] += 1
                categories[c.get("application_profile", "UNKNOWN")] += 1
                
    exact_duplicates = len(prompts) - len(set(prompts))
    normalized_duplicates = len(normalized_prompts) - len(set(normalized_prompts))
    
    report = {
        "total_cases": total_cases,
        "exact_duplicates": exact_duplicates,
        "normalized_duplicates": normalized_duplicates,
        "action_distribution": dict(actions),
        "nli_label_distribution": dict(nli_labels),
        "category_distribution": dict(categories),
    }
    
    with open(out_dir / "dataset_quality_report_v2.json", "w") as f:
        json.dump(report, f, indent=2)
        
    print("Dataset quality report saved.")

if __name__ == "__main__":
    run_dataset_quality()
