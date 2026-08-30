# ControlPlane Checker - Runtime Pipeline Specification (V1.3)

## Architectural Evolution
- **V1.0:** Synchronous rule baseline.
- **V1.1:** Persistence Foundation (PostgreSQL/Redis) & Tier 0-2 Vertical Slice.
- **V1.2:** Enterprise Context, Selective Adjudication & Forensic Audit.
- **V1.3 (Current Production):** High-Severity Selective Gemini Hybrid Architecture. Low/medium risk flows execute via local DeBERTa-v3-small (P95 ~105ms), while High/Critical consequence scopes and boundary ambiguities route to Gemini Flash Lite (86.7% accuracy, 100% contradiction recall), saving 62% of cloud LLM invocations. Missing evidence strictly enforces `INSUFFICIENT_EVIDENCE` without invoking the LLM.

## 1. End-to-End Enterprise Context Request Lifecycle

ControlPlane operates as an intelligent runtime proxy between client applications and foundation AI models with **Evidence Quality Evaluation**, **Multi-Label Risk Aggregation**, **Session Risk Accumulation**, **Selective Adjudication**, and **Bounded Pipeline Re-entry**:

```text
Client / App Request (POST /inspect)
                 │
                 ▼
     [ 1. Pre-flight Gate ] ─────────────► (Denied / Over Budget? ──► Persist & Return BLOCK/ESCALATE)
                 │
                 ▼ (Allowed)
     [ 2. Session Risk Lookup ] ─────────► Reads hot session state from Redis (NORMAL / ELEVATED / STRICT)
                 │
                 ▼
     [ 3. AI Model Generation ] ────────► Generates candidate ModelResponse (Attempt 0)
                 │
                 ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               PIPELINE VERIFICATION LOOP                               │
│                                                                                        │
│     [ 4. Tier 0 Detectors ] ──────────► PII, Secrets, Toxicity, Bias, Consistency     │
│                 │                                                                      │
│                 ▼                                                                      │
│     [ 5. Risk & Severity Engine ] ────► Task Consequence + Session Risk + Tier 0       │
│                 │                                                                      │
│      ┌──────────┴──────────┐                                                           │
│      ▼ (Low Risk Fast Path)▼ (High Risk / Mandatory Grounding / Session STRICT)        │
│  [ Pass directly ]    [ 6. Tier 1 Semantic Verification ]                              │
│      │                     ├── Claim Extractor (Atomic Statements)                     │
│      │                     ├── Evidence Repository (Pluggable: Lexical/Semantic/Hybrid)│
│      │                     │    └── FAISS CPU Vector Search + Policy Pre-filtering     │
│      │                     └── [ 6a. Post-Retrieval Evidence Quality Evaluator ]       │
│      │                              ├── Authority, Relevance, Freshness, Completeness  │
│      │                              └── Quality >= Min Threshold?                      │
│      │                                    │                      │                     │
│      │                                    ▼ (Yes: Adequate)      ▼ (No: Inadequate)    │
│      │                           [ NLI Verifier ]          [ INSUFFICIENT_EVIDENCE ]   │
│      │                                    │                      │ (NEVER Adjudicates) │
│      │                                    ▼                      │                     │
│      │                           [ Confidence Gate ]             │                     │
│      │                                    │                      │                     │
│      │                      ┌─────────────┴─────────────┐        │                     │
│      │                      ▼ (Ambiguous NLI)           ▼ (Clean)│                     │
│      │              [ Selective Adjudication ]          │        │                     │
│      │              ├── Check/Consume Budget            │        │                     │
│      │              ├── Confident -> ADJUDICATED        │        │                     │
│      │              └── Uncertain -> INCONCLUSIVE (NULL)│        │                     │
│      │                      │                           │        │                     │
│      │                      └─────────────┬─────────────┘        │                     │
│      │                                    ▼                      │                     │
│      │                            [ Verified Claims ] ◄──────────┘                     │
│      │                                    │                                            │
│      └─────────────────┬──────────────────┘                                            │
│                        ▼                                                               │
│     [ 7. Multi-Label Risk Aggregator ] ─► Preserves independent events & detects types │
│                        │                  ["PII", "HALLUCINATION", "BIAS", ...]        │
│                        ▼                                                               │
│     [ 8. Action Engine (Precedence) ] ──► BLOCK > ESCALATE > REPAIR > WARN > ALLOW     │
│                        │                                                               │
│         ┌──────────────┴──────────────┐                                                │
│         ▼ (REPAIR + attempts < max)   ▼ (ALLOW / WARN / BLOCK / ESCALATE)              │
│  [ 9. Repair Planner ]                [ 10. Session Risk Update & Accumulator ]        │
│         │                                       │ (Updates Redis score & counters)     │
│         ▼                                       ▼                                      │
│  [ Generate Repaired Response ]       [ 11. Persistence & Audit Trail Commit ]         │
│         │                                       │                                      │
│         └──────► Re-enters full loop at Step 4  ▼                                      │
│                  (Tier 0 -> Risk -> Tier 1)   Client Response (Structured Trace)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Responsibilities & Phase 3 Enhancements

### 1. Pre-flight Policy & Budget Gate (`app.preflight`)
- **Responsibility**: Fast validation before model invocation. Resolves `Application` and active immutable `PolicyVersion`, verifies input token limits, checks request budget allowances.
- **Validation**: Enforces strict policy validation rules via `PolicyValidator` (rejects negative budgets, out-of-bounds thresholds, invalid taxonomies).

### 2. Session Risk Accumulation (`app.risk.session_risk`)
- **Responsibility**: Manages hot ephemeral multi-turn session state in Redis (`session_risk:{session_id}`).
- **Scoring Model**: Transparent policy-weighted formula:
  - `SAFE = 0.0`, `WARNING = +1.0`, `UNCERTAINTY = +1.0`, `REPAIR = +2.0`, `CONTRADICTION = +3.0`, `POLICY_VIOLATION = +5.0`, `CRITICAL_PII = +5.0`.
- **Dynamic Risk Levels**:
  - `NORMAL` ($\text{score} < 3.0$): Standard application routing.
  - `ELEVATED` ($3.0 \le \text{score} < 7.0$): Increases risk sensitivity, flags caution on borderline tasks.
  - `STRICT` ($\text{score} \ge 7.0$): Enforces mandatory Tier 1 grounding across all queries regardless of profile defaults.

### 3. Model Adapter (`app.gateway.model_adapter`)
- **Responsibility**: Standardized foundation model interface supporting initial generation and evidence-constrained repair generation (`generate_repair`).

### 4. Tier 0 Responsibility Suite (`app.tier0`)
- **Responsibility**: Lightweight, parallel detectors (`PIIDetector`, `PolicyToxicityDetector`, `HeuristicBiasDetector`, `SemanticConsistencyScorer`, and `CostEstimator`).

### 5. Risk & Severity Engine (`app.risk`)
- **Responsibility**: Multidimensional risk scoring combining task consequence, response claim density, Tier 0 signals, session risk level, and policy risk appetite.

### 6. Tier 1 Verification & Evidence Quality Depth (`app.tier1`)
- **Post-Retrieval Evidence Quality Evaluator** (`EvidenceQualityEvaluator`):
  - **Authority**: High (official policy docs), Medium (internal memos), Low (unverified).
  - **Relevance**: Claim-to-snippet stem overlap in $[0.0, 1.0]$.
  - **Freshness**: Status (`FRESH`, `STALE`, `UNKNOWN`) and timestamp validity.
  - **Completeness**: Proportion of claim factual entities covered by evidence snippet in $[0.0, 1.0]$.
  - **Composite Score**: $\text{quality\_score} = 0.35 \times \text{relevance} + 0.25 \times \text{authority} + 0.20 \times \text{freshness} + 0.20 \times \text{completeness}$.
- **Invariant Rule**: Weak evidence ($\text{quality\_score} < \text{threshold}$) immediately marks claim as `INSUFFICIENT_EVIDENCE` and **NEVER triggers Selective Adjudication**.

### 7. Multi-Label Risk Aggregator (`app.risk.multi_label`)
- **Responsibility**: Identifies multiple simultaneous risk categories (e.g. `PII + HALLUCINATION`, `BIAS + HALLUCINATION`).
- **Preservation**: Preserves all raw `policy_events` and aggregates `candidate_actions` proposed by each risk source before resolving via strict canonical precedence:
  $$\text{BLOCK} > \text{ESCALATE} > \text{REPAIR} > \text{WARN} > \text{ABSTAIN} > \text{ALLOW}$$

### 8. Repair Loop & Full Pipeline Re-entry (`app.repair`)
- **Responsibility**: Formulates targeted evidence-constrained corrective prompts. Candidate repaired responses re-enter the full pipeline (`Tier 0 -> Risk -> Tier 1 -> Action Engine`) with strict attempt bounding (`max_repair_attempts`).

---

## 3. Representative Phase 3 Pipeline Traces

### Multi-Label Risk Trace (Critical PII + Contradiction $\rightarrow$ BLOCK)
```json
{
  "request_id": "8a1b2c3d-4e5f-6789-0123-abcdef012345",
  "action": "BLOCK",
  "risk_assessment": {
    "risk_level": "CRITICAL",
    "severity": "CRITICAL",
    "highest_severity": "CRITICAL",
    "risk_types": ["HALLUCINATION", "PII"],
    "candidate_actions": ["BLOCK", "REPAIR"]
  },
  "policy_events": [
    {
      "event_type": "PII",
      "detector": "PIIDetector",
      "severity": "CRITICAL",
      "matched_text": "123-45-6789"
    }
  ],
  "claims": [
    {
      "claim_text": "All customers get unlimited $1,000 cash waivers.",
      "final_label": "CONTRADICTED",
      "severity": "HIGH",
      "evidence_quality": {
        "authority": "HIGH",
        "freshness": 1.0,
        "relevance": 0.50,
        "completeness": 0.50,
        "quality_score": 0.725
      }
    }
  ],
  "session_risk": {
    "session_id": "sess-multi-user-1",
    "prior_score": 0.0,
    "current_score": 5.0,
    "level": "ELEVATED",
    "turn_count": 1,
    "violations_count": 1
  }
}
```
