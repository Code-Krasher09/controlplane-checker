# ControlPlane Round 2 — Database Implementation

## 1. Overview & Strategy

ControlPlane Round 2 distinguishes between the **Target Data Model** (the complete enterprise architecture documented in `ControlPlane_Round2_Database_Schema.sql`) and the **P0 MVP Runtime Schema** (the minimal persistence layer required to execute the first vertical slice from Pre-flight to Audit).

---

## 2. Implemented P0 Tables vs. Deferred Tables

### Implemented P0 Tables (13 Entities + AIModel)
1. **`applications`**: Enterprise application profiles (Customer Support, Internal KB, Decision Support).
2. **`ai_models`**: Provider and model deployment metadata (e.g. `gpt-4o-mini`, `mock-pipeline-model-v1`).
3. **`policy_configs`**: Application-level governance, thresholds, budgets, and default action precedence.
4. **`policy_versions`**: Immutable versioned policy snapshots containing specific threshold dictionaries and action rules.
5. **`requests`**: Root correlation entity tracking prompts, session IDs, execution modes, pre-flight decisions, and budgets.
6. **`responses`**: Individual response attempts, output tokens, latencies, costs, and generated content.
7. **`policy_events`**: Tier 0 detector events (PII, secrets, toxicity, hard policy violations, heuristic bias).
8. **`risk_assessments`**: Pre-Tier-1 risk scores (`task_risk`, `response_risk`, `evidence_availability`, `sensitivity`, `severity`) and routing decisions.
9. **`claims`**: Atomic extracted claims with severity and business impact.
10. **`evidence`**: Retrieved source snippets with quality metrics (`authority`, `freshness`, `relevance`, `completeness`, `quality_score`).
11. **`claim_evidence`**: Many-to-many join association mapping claims to retrieved evidence.
12. **`nli_results`**: Tier 1 NLI verification outcomes, confidence scores, adjudication triggers, and secondary judge results.
13. **`interventions`**: Final Action Engine decisions (`ALLOW`, `WARN`, `ABSTAIN`, `REPAIR`, `BLOCK`, `ESCALATE`).
14. **`repair_attempts`**: Bounded regeneration attempts linking source response, failed claim, repair prompt, and repaired response.
15. **`audit_events`**: Immutable asynchronous audit log records.

### Deferred Tables (Post-P0 / Enterprise Scale)
- **`human_feedback`**: Reviewer overrides and calibration logs (P1 Phase 4).
- **`session_risk`**: Multi-turn cumulative session score history table (P1 Phase 3; active hot state managed via Redis in P0).
- **`evaluation_cases`**, **`evaluation_runs`**, **`evaluation_case_results`**: Benchmark persistence (P0/P1 Phase 4).
- **`agent_action_gates`**: Consequential tool action gating (P2).

---

## 3. Entity Relationships Diagram

```text
applications
  │ (1:N)
  ├── policy_configs
  │     │ (1:N)
  │     └── policy_versions ──┐
  │                           │ (1:N)
  └── requests ───────────────┴── responses ─── claims ─── claim_evidence ─── evidence
        │ (1:N)                      │ (1:N)      │ (1:N)          │
        ├── risk_assessments ────────┘            └── nli_results ─┘
        ├── interventions ───────────┘
        ├── repair_attempts
        └── audit_events
```

---

## 4. Invariant Enforcement (V1.2 Constraints)

All database check constraints are codified in `app/persistence/models/nli.py` and `migrations/versions/0001_initial_p0_schema.py`:

| Invariant ID | Condition | Status / Final Label | Constraint Rule / Description |
|---|---|---|---|
| **Invariant A** | Inconclusive Adjudication | `verification_status = ADJUDICATION_INCONCLUSIVE`, `final_label = NULL` | Valid. Cannot force a semantic label. |
| **Invariant B** | Inconclusive with Label | `verification_status = ADJUDICATION_INCONCLUSIVE`, `final_label != NULL` | **Rejected** by `chk_nli_inconclusive_requires_null_label`. |
| **Invariant C** | Direct NLI without Label | `verification_status = DIRECT_NLI`, `final_label = NULL` | **Rejected** by `chk_nli_direct_requires_final_label` (unless budget exhausted). |
| **Invariant D** | Adjudicated without Label | `verification_status = ADJUDICATED`, `final_label = NULL` | **Rejected** (Adjudicator must output confident final label). |
| **Invariant E** | Clean Direct NLI | `adjudication_trigger = NONE`, `verification_status = DIRECT_NLI`, `reason = NONE` | Valid standard fast/direct execution. |
| **Invariant F** | Triggered & Adjudicated | `adjudication_trigger != NONE`, `verification_status = ADJUDICATED` | Valid. Ambiguity resolved by judge. |
| **Invariant G** | Triggered & Inconclusive | `adjudication_trigger != NONE`, `verification_status = ADJUDICATION_INCONCLUSIVE` | Valid. Judge ran but was uncertain. |
| **Invariant H** | Triggered with Direct NLI | `adjudication_trigger != NONE`, `verification_status = DIRECT_NLI`, `reason = NONE` | **Rejected** by `chk_nli_trigger_status_consistency`. Silent skip prohibited. |
| **Invariant I** | Budget Exhaustion Exception | `adjudication_trigger != NONE`, `verification_status = DIRECT_NLI`, `uncertainty_reason = ADJUDICATION_BUDGET_EXHAUSTED` | **Valid explicit exception**. Trigger is preserved, reason audited. |

---

## 5. Redis Hot State Responsibilities

`app/persistence/redis.py` provides the runtime state store interface:
- **`retry_count:{request_id}`**: Fast counter enforcing max repair limits before escalation.
- **`budget:request:{request_id}`**: In-flight token/USD budget accumulator for active request.
- **`budget:session:{session_id}`**: Cumulative session cost tracking.
- **`budget:adjudication:{session_id}`**: Dedicated secondary judge cost consumption tracker.

---

## 6. Migration and Seed Commands

### Run Alembic Migrations
```powershell
# Upgrade to latest P0 schema head
python -m alembic upgrade head

# Downgrade / Rollback
python -m alembic downgrade -1
```

### Seed Database
```powershell
# Execute seed programmatically via CLI or script
python -c "
import asyncio
from app.persistence.database import get_async_sessionmaker
from app.persistence.seed import seed_database_async

async def run():
    session_factory = get_async_sessionmaker()
    async with session_factory() as session:
        await seed_database_async(session)
    print('Database seeded successfully.')

asyncio.run(run())
"
```
