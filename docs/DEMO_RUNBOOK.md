# ControlPlane Checker — Executive Demo Runbook (Phase 13)

This runbook guides presenters through the 6 canonical demonstration scenarios in the ControlPlane UI.

---

### Scenario 1: Safe Fast Path (Low Risk)
- **Presenter Action:** Click Scenario `1. Safe Fast Path (Low Risk)` $\rightarrow$ Click `Run ControlPlane Inspection`.
- **Visual State:** Pipeline lights up all 5 stages in emerald/teal.
- **Architecture Stage:** Local DeBERTa-v3-small verified. Cloud Gemini judge strictly bypassed.
- **Talk Track (15s):** *"For 58% of routine enterprise traffic, we don't need expensive multi-second cloud LLM calls. ControlPlane evaluates customer inquiries locally in just 5 milliseconds with zero cloud API overhead."*
- **Key Metric:** P95 latency = **53.53 ms** | **0 Cloud Calls**.
- **What NOT to Claim:** Do not claim 0ms latency; emphasize sub-100ms local execution.

---

### Scenario 2: PII / Threat Hard Block
- **Presenter Action:** Click Scenario `2. PII / Threat Hard Block` $\rightarrow$ Click `Run ControlPlane Inspection`.
- **Visual State:** Pipeline terminates immediately at Stage 1 (Tier 0) in crimson `HARD BLOCK`.
- **Architecture Stage:** Tier 0 regex/keyword preflight intercept.
- **Talk Track (15s):** *"When a user inputs a sensitive Social Security Number, Tier 0 stops the request in 2 milliseconds before any LLM generation, embeddings, or retrieval occurs."*
- **Key Metric:** **100% of tested PII cases blocked** | **2.2 ms preflight latency**.
- **What NOT to Claim:** Do not claim ML models did the block; it is deterministic rule-based security.

---

### Scenario 3: High-Severity Gemini Judge
- **Presenter Action:** Click Scenario `3. High-Severity Gemini Judge` $\rightarrow$ Click `Run ControlPlane Inspection`.
- **Visual State:** Pipeline routes through Stage 2 (Risk = HIGH) and activates Cloud Gemini Flash Lite in purple.
- **Architecture Stage:** Gemini LLM-as-a-Judge semantic deduction.
- **Talk Track (20s):** *"When policy profile or consequence severity is HIGH—such as financial fee waivers—the system automatically escalates to Google Gemini for deep logical deduction across multi-clause contracts."*
- **Key Metric:** **86.7% microbenchmark accuracy** | **100% numerical/temporal precision**.
- **What NOT to Claim:** Do not claim it is instant; highlight it as deep deductive rigor for high-risk queries.

---

### Scenario 4: Contradiction $\rightarrow$ Self-Healing Repair $\rightarrow$ ALLOW
- **Presenter Action:** Click Scenario `4. Contradiction → Self-Healing Repair` $\rightarrow$ Click `Run ControlPlane Inspection`.
- **Visual State:** Pipeline detects initial contradiction, displays the cyan Repair Loop badge, regenerates capped $200 text, reverifies through Tier 0 $\rightarrow$ Tier 1, and grants `ALLOW`.
- **Architecture Stage:** Closed-loop repair re-entry pipeline.
- **Talk Track (25s):** *"When an AI response hallucinates an unapproved $1,000 waiver, ControlPlane doesn't just fail—it initiates a bounded repair loop, generates policy-compliant text, re-enters the full inspection pipeline, and safely emits verified content."*
- **Key Metric:** **100% pipeline re-entry on repaired outputs**.
- **What NOT to Claim:** Do not claim infinite retries; retries are strictly bounded to 2 attempts.

---

### Scenario 5: Insufficient Evidence Gate $\rightarrow$ ESCALATE
- **Presenter Action:** Click Scenario `5. Insufficient Evidence Gate` $\rightarrow$ Click `Run ControlPlane Inspection`.
- **Visual State:** Stage 3 flags `INSUFFICIENT EVIDENCE` in amber. Cloud Gemini is visibly bypassed. Action Engine resolves `ESCALATE`.
- **Architecture Stage:** Epistemic Sufficiency Gate.
- **Talk Track (20s):** *"Here is our core epistemic safety invariant: when enterprise knowledge lacks evidence for a query, the system NEVER allows an LLM judge to guess using outside knowledge. It strictly bypasses Gemini and escalates to human compliance."*
- **Key Metric:** **0% hallucinated support on missing evidence**.
- **What NOT to Claim:** Do not claim the system found the answer; it safely recognized knowledge absence.

---

### Scenario 6: Adjudication Inconclusive $\rightarrow$ ESCALATE
- **Presenter Action:** Click Scenario `6. Adjudication Inconclusive` $\rightarrow$ Click `Run ControlPlane Inspection`.
- **Visual State:** Confidence Gate detects borderline score margin (<0.15), judge returns inconclusive, Action Engine resolves `ESCALATE`.
- **Architecture Stage:** Confidence Gate & Uncertainty Engine.
- **Talk Track (15s):** *"On contested policy boundaries where classification confidence is marginal, ControlPlane refuses to guess and routes the decision safely to human compliance teams."*
- **Key Metric:** **Conservative risk-first escalation**.
- **What NOT to Claim:** Do not claim the system was confused; explain that it safely recognized ambiguity.
