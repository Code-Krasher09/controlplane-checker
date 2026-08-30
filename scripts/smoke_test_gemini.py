"""Smoke test for Gemini API credentials and structured output verifier."""

import asyncio
import json
import os
import sys
import httpx
from dotenv import load_dotenv

# Load from .env
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    print("FAILURE: GEMINI_API_KEY is not set in environment or .env file.")
    sys.exit(1)

print(f"INFO: GEMINI_API_KEY is present (length: {len(GEMINI_API_KEY)} chars).")
print(f"INFO: Target model: {GEMINI_MODEL}")

SYSTEM_INSTRUCTION = """You are a strict, objective semantic verification judge for an enterprise policy governance system.
Your job is to determine whether a CLAIM is supported, contradicted, or has insufficient evidence based ONLY on the provided EVIDENCE.

You must output valid JSON strictly conforming to this schema:
{
  "label": "SUPPORTED" | "CONTRADICTED" | "INSUFFICIENT_EVIDENCE",
  "confidence": float between 0.0 and 1.0,
  "reason": "short explanation of the verification decision"
}

Definitions:
- SUPPORTED: The provided evidence directly or logically supports the claim.
- CONTRADICTED: The provided evidence directly or logically conflicts with or refutes the claim.
- INSUFFICIENT_EVIDENCE: The provided evidence does not contain enough information to confirm or refute the claim.

Rules:
1. Rely ONLY on the given evidence. Do NOT use outside world knowledge to assume unstated facts.
2. Do not mark SUPPORTED merely because a claim seems plausible.
3. If evidence is empty, ambiguous, or lacks specific details, return INSUFFICIENT_EVIDENCE.
"""

TEST_CASES = [
    {
        "name": "1. Supported claim",
        "evidence": "The retail policy allows customer returns within 30 days of purchase with original receipt.",
        "claim": "Customers can return items within 30 days of purchase if they have the original receipt.",
        "expected_label": "SUPPORTED",
    },
    {
        "name": "2. Contradicted claim",
        "evidence": "Customer courtesy waivers are strictly capped at $200 and require manager approval.",
        "claim": "All customers are entitled to an immediate $1,000 cash waiver with zero approval required.",
        "expected_label": "CONTRADICTED",
    },
    {
        "name": "3. Insufficient evidence",
        "evidence": "The server maintenance schedule is planned for Sunday 2 AM UTC.",
        "claim": "The company CEO approved the international expansion into Japan.",
        "expected_label": "INSUFFICIENT_EVIDENCE",
    },
]


async def call_gemini(client: httpx.AsyncClient, model: str, claim: str, evidence: str) -> dict:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json",
    }
    user_prompt = f"EVIDENCE:\n{evidence}\n\nCLAIM:\n{claim}\n\nVerify the claim against the evidence and output JSON."
    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json",
            "temperature": 0.0,
            "maxOutputTokens": 1024,
        },
    }

    resp = await client.post(url, headers=headers, json=payload, timeout=30.0)
    if resp.status_code != 200:
        raise RuntimeError(f"API returned HTTP {resp.status_code}: {resp.text}")

    data = resp.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise RuntimeError(f"No candidates returned: {data}")

    text = candidates[0]["content"]["parts"][0]["text"]
    usage = data.get("usageMetadata", {})
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as jde:
        raise RuntimeError(f"JSONDecodeError: {jde} on text: {repr(text)}")
    return {
        "raw": parsed,
        "usage": usage,
    }


async def list_models(client: httpx.AsyncClient) -> list:
    url = "https://generativelanguage.googleapis.com/v1beta/models"
    headers = {"x-goog-api-key": GEMINI_API_KEY}
    resp = await client.get(url, headers=headers, timeout=15.0)
    if resp.status_code == 200:
        data = resp.json()
        return [m["name"].replace("models/", "") for m in data.get("models", []) if "generateContent" in m.get("supportedGenerationMethods", [])]
    return []


async def main():
    async with httpx.AsyncClient() as client:
        available = await list_models(client)
        print(f"INFO: Available models from API ({len(available)}): {available[:10]}")
        
        models_to_try = [GEMINI_MODEL, "gemini-2.5-flash", "gemini-3.6-flash", "gemini-2.5-pro"] + available
        # De-duplicate while preserving order
        seen = set()
        models = []
        for m in models_to_try:
            if m not in seen:
                seen.add(m)
                models.append(m)

        working_model = None

        # First find a working model from available ones
        for model in models:
            print(f"\nAttempting connectivity with model: {model} ...")
            try:
                test_res = await call_gemini(
                    client,
                    model,
                    claim="The store is open on weekdays.",
                    evidence="Our store is open Monday through Friday from 9 AM to 5 PM.",
                )
                print(f"SUCCESS: Connected to {model}. Token usage: {test_res['usage']}")
                working_model = model
                break
            except Exception as e:
                print(f"FAILED on model {model}: {e}")

        if not working_model:
            print("\nFATAL: All model attempts failed. Check credentials or API access.")
            sys.exit(1)

        print(f"\n==========================================")
        print(f"RUNNING 3 SEMANTIC SMOKE TESTS ON {working_model}")
        print(f"==========================================")

        all_passed = True
        for tc in TEST_CASES:
            print(f"\nTest: {tc['name']}")
            print(f"  Claim: {tc['claim']}")
            print(f"  Evidence: {tc['evidence']}")
            try:
                res = await call_gemini(client, working_model, claim=tc["claim"], evidence=tc["evidence"])
                parsed = res["raw"]
                label = parsed.get("label")
                confidence = parsed.get("confidence")
                reason = parsed.get("reason")

                print(f"  Result -> label: {label}, confidence: {confidence}, reason: {reason}")

                # Validate structure
                if label not in ["SUPPORTED", "CONTRADICTED", "INSUFFICIENT_EVIDENCE"]:
                    print(f"  FAILED: Invalid label '{label}'")
                    all_passed = False
                elif not isinstance(confidence, (int, float)) or not (0.0 <= confidence <= 1.0):
                    print(f"  FAILED: Invalid confidence '{confidence}'")
                    all_passed = False
                elif not reason:
                    print(f"  FAILED: Empty reason")
                    all_passed = False
                elif label != tc["expected_label"]:
                    print(f"  FAILED: Expected {tc['expected_label']} but got {label}")
                    all_passed = False
                else:
                    print(f"  PASSED [Expected: {tc['expected_label']}, Got: {label}]")
            except Exception as e:
                print(f"  FAILED with exception: {e}")
                all_passed = False

        if not all_passed:
            print("\nFATAL: Smoke tests did not all pass.")
            sys.exit(1)

        print(f"\nALL 3 SMOKE TESTS PASSED! Active working model: {working_model}")
        return working_model


if __name__ == "__main__":
    asyncio.run(main())
