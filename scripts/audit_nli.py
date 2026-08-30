import json
from app.tier1.nli_real import RealNLIVerifier
from app.domain.models import ClaimVerificationItem, EvidenceSnippet
from uuid import uuid4

def run_nli_audit():
    print("Loading RealNLIVerifier...")
    verifier = RealNLIVerifier()
    
    print(f"Model loaded: {verifier.model_name}")
    
    cases = [
        # 1. Direct support
        {"desc": "Direct Support", "premise": "The return policy is 30 days.", "hypothesis": "You can return the item within 30 days."},
        # 2. Direct contradiction
        {"desc": "Direct Contradiction", "premise": "The return policy is 30 days.", "hypothesis": "You can return the item within 60 days."},
        # 3. Neutral
        {"desc": "Neutral", "premise": "The return policy is 30 days.", "hypothesis": "The return policy applies to electronics."},
        # 4. Paraphrase
        {"desc": "Paraphrase", "premise": "Employees must wear formal attire on Mondays.", "hypothesis": "Business formal dress code is mandatory on the first day of the work week."},
        # 5. Negation
        {"desc": "Negation", "premise": "The system does not allow root access.", "hypothesis": "The system allows root access."},
        # 6. Numerical contradiction
        {"desc": "Numerical Contradiction", "premise": "The fee is $500.", "hypothesis": "The fee is $50."},
        # 7. Partial support
        {"desc": "Partial Support", "premise": "The fee is $500 and the limit is 10 items.", "hypothesis": "The limit is 10 items."},
        # 8. Related but not supporting
        {"desc": "Related-But-Not-Supporting", "premise": "The server uses AES-256 encryption.", "hypothesis": "The server uses TLS 1.3."},
        # 9. Multiple evidence chunks (simulated by concatenation in verifier)
        {"desc": "Multiple chunks", "premise": "First part: You can travel to Europe. Second part: but you need a visa.", "hypothesis": "A visa is required for European travel."},
        # 10. Conflicting evidence
        {"desc": "Conflicting Evidence", "premise": "Rule A says refunds are allowed. Rule B says no refunds under any circumstances.", "hypothesis": "Refunds are allowed."},
        # 11. Stale evidence (dates)
        {"desc": "Stale Evidence", "premise": "As of 2020, the limit is 5. In 2024, it changed to 10.", "hypothesis": "The limit is 5."},
        # 12. Long evidence
        {"desc": "Long Evidence", "premise": " ".join(["Filler text to make it long."] * 50) + " The actual answer is 42.", "hypothesis": "The answer is 42."},
        # 13. Claim with multiple facts
        {"desc": "Multiple Facts Claim", "premise": "The color is blue.", "hypothesis": "The color is blue and the size is large."},
        # 14. Ambiguous wording
        {"desc": "Ambiguous", "premise": "Most items are eligible for return.", "hypothesis": "This specific item is eligible for return."},
        # 15. High-severity ambiguous
        {"desc": "High-Severity Ambiguous", "premise": "Use of force is only authorized in self defense.", "hypothesis": "Use of force is authorized when verbally threatened."}
    ]
    
    results = []
    
    for c in cases:
        claim = ClaimVerificationItem(claim_text=c["hypothesis"])
        evidence = [EvidenceSnippet(evidence_id=uuid4(), source_type="TEST", source_id="1", content_snippet=c["premise"])]
        
        resp = verifier.verify(claim, evidence)
        
        results.append({
            "description": c["desc"],
            "expected_relation": c["desc"],
            "actual_label": resp.label,
            "confidence": resp.nli_confidence,
            "top2": resp.top2_scores,
            "premise_length": len(c["premise"]),
            "hypothesis_length": len(c["hypothesis"])
        })
        
    with open("artifacts/evaluation/nli_audit.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("NLI Audit complete. Results saved.")

if __name__ == "__main__":
    run_nli_audit()
