import json

def generate_taxonomy():
    with open("artifacts/evaluation/nli_action_cross_analysis.json", "r") as f:
        data = json.load(f)
        
    failures = data.get("nli_failures", [])
    
    taxonomy = {
        "SUPPORT_PREDICTED_INCORRECTLY": 0,
        "CONTRADICTION_PREDICTED_INCORRECTLY": 0,
        "INSUFFICIENT_EVIDENCE_PREDICTED_INCORRECTLY": 0,
        "SUPPORTED_PREDICTED_AS_CONTRADICTION": 0,
        "SUPPORTED_PREDICTED_AS_INSUFFICIENT": 0,
        "CONTRADICTION_PREDICTED_AS_SUPPORTED": 0,
        "CONTRADICTION_PREDICTED_AS_INSUFFICIENT": 0,
        "INSUFFICIENT_PREDICTED_AS_SUPPORTED": 0,
        "INSUFFICIENT_PREDICTED_AS_CONTRADICTION": 0,
        "total_errors": len(failures)
    }
    
    for fail in failures:
        exp = fail.get("expected_nli")
        act = fail.get("actual_nli")
        
        if act == "SUPPORTED":
            taxonomy["SUPPORT_PREDICTED_INCORRECTLY"] += 1
            if exp == "CONTRADICTED":
                taxonomy["CONTRADICTION_PREDICTED_AS_SUPPORTED"] += 1
            elif exp == "INSUFFICIENT_EVIDENCE":
                taxonomy["INSUFFICIENT_PREDICTED_AS_SUPPORTED"] += 1
        elif act == "CONTRADICTED":
            taxonomy["CONTRADICTION_PREDICTED_INCORRECTLY"] += 1
            if exp == "SUPPORTED":
                taxonomy["SUPPORTED_PREDICTED_AS_CONTRADICTION"] += 1
            elif exp == "INSUFFICIENT_EVIDENCE":
                taxonomy["INSUFFICIENT_PREDICTED_AS_CONTRADICTION"] += 1
        elif act == "INSUFFICIENT_EVIDENCE":
            taxonomy["INSUFFICIENT_EVIDENCE_PREDICTED_INCORRECTLY"] += 1
            if exp == "SUPPORTED":
                taxonomy["SUPPORTED_PREDICTED_AS_INSUFFICIENT"] += 1
            elif exp == "CONTRADICTED":
                taxonomy["CONTRADICTION_PREDICTED_AS_INSUFFICIENT"] += 1
                
    with open("artifacts/evaluation/nli_error_taxonomy.json", "w") as f:
        json.dump(taxonomy, f, indent=2)

if __name__ == "__main__":
    generate_taxonomy()
