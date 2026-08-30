import json
from app.tier0.semantic_real import RealSemanticConsistencyScorer

def run_embedding_audit():
    print("Loading RealSemanticConsistencyScorer...")
    scorer = RealSemanticConsistencyScorer()
    print("Model loaded.")
    
    cases = [
        {"desc": "Direct factual response", "prompt": "What is the return policy?", "response": "The return policy is 30 days."},
        {"desc": "Paraphrase", "prompt": "Can you explain the remote work rules?", "response": "The telecommuting guidelines state you can work from home twice a week."},
        {"desc": "Creative response", "prompt": "Write a poem about returns.", "response": "Roses are red, returns are neat, bring it back in 30 days, keep your receipt."},
        {"desc": "Indirect explanation", "prompt": "My laptop broke, what do I do?", "response": "You should contact IT support and file a hardware replacement ticket."},
        {"desc": "Unrelated response", "prompt": "What is the return policy?", "response": "The weather today is sunny with a chance of rain."},
        {"desc": "Long response", "prompt": "Explain the policy.", "response": " ".join(["Here is a long detailed explanation."] * 50)}
    ]
    
    results = []
    
    for c in cases:
        score = scorer.calculate_score(c["prompt"], c["response"])
        results.append({
            "description": c["desc"],
            "prompt": c["prompt"],
            "response_snippet": c["response"][:50] + "...",
            "score": score
        })
        
    with open("artifacts/evaluation/embedding_audit.json", "w") as f:
        json.dump(results, f, indent=2)
        
    print("Embedding Audit complete. Results saved.")

if __name__ == "__main__":
    run_embedding_audit()
