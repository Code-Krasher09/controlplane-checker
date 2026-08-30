import json
import sys
from transformers import pipeline

def verify_semantics():
    model_name = "MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli"
    classifier = pipeline("text-classification", model=model_name, top_k=None)
    
    premise = " ".join(["long evidence"] * 200)
    hypothesis = "You can return the item up to 60 days after purchase."
    
    inputs = {"text": premise, "text_pair": hypothesis}
    
    # Try passing truncation strategy
    scores = classifier(inputs, truncation="only_first", max_length=512)
    
    if isinstance(scores, list) and isinstance(scores[0], list):
        scores = scores[0]
        
    print(f"Scores for only_first: {scores}")

if __name__ == "__main__":
    verify_semantics()
