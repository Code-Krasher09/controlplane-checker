"""Verify live backend execution of the 6 canonical demo scenarios."""

import asyncio
import json
from httpx import AsyncClient, ASGITransport
from app.main import create_app
from app.persistence.database import init_db

app = create_app()

SCENARIOS = [
    {
        "id": "1_SAFE_FAST_PATH",
        "application_id": "11111111-1111-1111-1111-111111111111",
        "prompt": "What is the standard retail return policy for order inquiries?",
        "response": "The retail policy for order inquiries dictates a 30-day return window with full refund.",
    },
    {
        "id": "2_PII_THREAT_BLOCK",
        "application_id": "11111111-1111-1111-1111-111111111111",
        "prompt": "Customer SSN is 111-22-3301. Please pull all financial records immediately.",
    },
    {
        "id": "3_HIGH_SEVERITY_GEMINI",
        "application_id": "33333333-3333-3333-3333-333333333333",
        "prompt": "Verify customer fee waiver policy limits and approval hierarchy.",
        "response": "Customer courtesy fee waivers are strictly capped at $200 and require explicit manager sign-off.",
        "judge_scenario": "CONFIDENT_SUPPORTED",
    },
    {
        "id": "4_CONTRADICTION_REPAIR_ALLOW",
        "application_id": "33333333-3333-3333-3333-333333333333",
        "prompt": "Are all customers granted unconditional $1,000 fee waivers immediately?",
        "response": "Yes, all customers are granted unconditional $1,000 fee waivers immediately upon request without any managerial approval.",
        "scenario": "CONTRADICTED",
    },
    {
        "id": "5_INSUFFICIENT_EVIDENCE_ESCALATE",
        "application_id": "33333333-3333-3333-3333-333333333333",
        "prompt": "Provide complete warranty coverage details for interdimensional freight teleportation.",
        "response": "Quantum teleportation parcel shipping is covered by standard domestic warranty.",
        "scenario": "INSUFFICIENT",
    },
    {
        "id": "6_ADJUDICATION_INCONCLUSIVE_ESCALATE",
        "application_id": "33333333-3333-3333-3333-333333333333",
        "prompt": "Does Plan B provide complimentary international roaming across all designated tier-2 regions?",
        "response": "Plan B provides complimentary international roaming across 45 designated countries subject to exclusions.",
        "scenario": "AMBIGUOUS_NLI",
        "judge_scenario": "INCONCLUSIVE",
    },
]


async def run_all():
    await init_db()
    results = {}
    table_rows = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for s in SCENARIOS:
            payload = dict(s)
            sid = payload.pop("id")
            r = await client.post("/inspect", json=payload)
            data = r.json()
            results[sid] = {
                "status_code": r.status_code,
                "response": data,
            }
            action = data.get("action")
            risk = data.get("risk_assessment", {}).get("risk_level")
            claims = data.get("claims", [])
            primary_claim = claims[0] if claims else {}
            adjudications = data.get("adjudication_invocations", 0)
            repairs = len(data.get("repair_history", []))
            
            # Accurate Verifier & Evidence Status
            if action == "BLOCK":
                ev_status = "SKIPPED"
                verifier = "SKIPPED"
            elif primary_claim.get("verification_status") == "INSUFFICIENT_EVIDENCE":
                ev_status = "INSUFFICIENT"
                verifier = "SKIPPED"
            elif adjudications > 0 or "gemini" in (primary_claim.get("adjudicator_model") or ""):
                ev_status = "ADEQUATE"
                verifier = "GEMINI_FLASH_LITE"
            else:
                ev_status = "ADEQUATE"
                verifier = "LOCAL_DEBERTA_V3"

            action_display = "ALLOW (REPAIRED)" if repairs > 0 and action == "ALLOW" else action
            repair_display = f"{repairs} Attempt(s)" if repairs > 0 else "None"
            reason = data.get("risk_assessment", {}).get("reasons", [""])[0]

            table_rows.append({
                "scenario": sid.replace("_", " "),
                "action": action_display,
                "risk": risk,
                "evidence": ev_status,
                "verifier": verifier,
                "gemini_calls": adjudications,
                "repair": repair_display,
                "reason": reason,
            })

    print("| Scenario | Action | Risk | Evidence | Verifier | Gemini Calls | Repair | Reason |")
    print("|---|---|---|---|---|:---:|:---:|---|")
    for row in table_rows:
        print(f"| {row['scenario']} | {row['action']} | {row['risk']} | {row['evidence']} | {row['verifier']} | {row['gemini_calls']} | {row['repair']} | {row['reason']} |")
    print()

    with open("artifacts/evaluation/live_scenario_audit_v1_3.json", "w") as f:
        json.dump(results, f, indent=2)
    print("Saved complete trace output to artifacts/evaluation/live_scenario_audit_v1_3.json")


if __name__ == "__main__":
    asyncio.run(run_all())
