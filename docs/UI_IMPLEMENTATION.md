# ControlPlane Demo-First UI Implementation (Phase 12B)

## 1. Overview & Frontend Architecture
The ControlPlane UI is a modern, high-performance, dark-mode first enterprise AI observability dashboard designed to make the **risk-adaptive semantic verification** architecture intuitive and verifiable within seconds.

- **Stack:** React 19, TypeScript, Vite, Vanilla CSS Design System, Lucide React.
- **Location:** `frontend/` directory (static build hosted on FastAPI at `/ui` and `/assets`).
- **Core Design Maxim:** *"Verify cheaply by default. Escalate intelligently when risk demands it."*

---

## 2. Implemented Primary Screens

### View 1 — Live Request Trace (`LiveTraceView.tsx`)
The primary live demonstration screen, divided into three synchronized columns:
1. **Left Column (Request & Scenario Launcher):**
   - Scenario Quick-Launcher with 6 deterministic scenario buttons.
   - Interactive prompt and candidate response input forms.
   - Run ControlPlane Inspection trigger.
2. **Center Column (Multi-Tier Pipeline Visualizer):**
   - **Stage 1:** Input / AI Response (Candidate content, token count).
   - **Stage 2:** Tier 0 Preflight & Guards (PII, Secrets, Policy, Toxicity, Cost estimation $\rightarrow$ `PASS` / `HARD BLOCK`).
   - **Stage 3:** Risk & Consequence Assessment (Risk Level, Severity Level, Contextual Scope $\rightarrow$ `LOW`/`MED` vs `HIGH`/`CRITICAL`).
   - **Stage 4:** Evidence Sufficiency Gate (Source count, quality score, authority, adequacy score $\rightarrow$ Inadequate bypasses Gemini).
   - **Stage 5:** Semantic Verification Layer (Local DeBERTa-v3-small fast path vs Gemini Flash Lite LLM-as-a-Judge vs Insufficient Evidence).
   - **Stage 6:** Action Engine & Closed-Loop Repair (`ALLOW`, `BLOCK`, `REPAIR` attempt trace with diff, `ESCALATE`).
3. **Right Column (Decision & Telemetry):**
   - Enforced Action Badge (`ALLOW`, `BLOCK`, `REPAIR`, `ESCALATE`).
   - Action Explainability ("WHY") block.
   - Millisecond latency breakdown table and visual progress bars.
   - Real-time token consumption and cloud calls avoided.

### View 2 — Control Room (`ControlRoomView.tsx`)
Executive AI observability dashboard featuring:
1. **Conceptual Pitch Banner:** Prominent architectural philosophy with 126/126 test verification badge.
2. **Real-time KPI Cards:**
   - Observed Holdout Accuracy: **74.0%** (+24.0% vs unprotected baseline)
   - Cloud LLM Calls Saved: **58.0%** (29 of 50 holdout requests avoided cloud API)
   - Low-Risk Path P95 Latency: **53.53 ms**
   - Critical Threats Blocked: **100.0%** (4/4 PII & threats blocked)
   - Self-Healing Repairs: **8 Cases** auto-repaired and verified
   - Conservative Escalations: **18 Cases** routed to humans
3. **Verification Architecture Distribution:** Local Fast Path (58.0%) vs Cloud LLM Judge (42.0%).
4. **Recent Decisions Audit Table:** Interactive stream of representative inspection decisions with direct drill-down into full execution traces.

---

## 3. Supported Deterministic Demo Scenarios
1. **1. Safe Fast Path (Low Risk):** Routine customer support return inquiry $\rightarrow$ Local DeBERTa $\rightarrow$ `ALLOW` (5.24 ms, 0 cloud calls).
2. **2. PII / Threat Hard Block:** Prompt with SSN 111-22-3301 $\rightarrow$ Tier 0 Preflight Guard $\rightarrow$ `BLOCK` (2.20 ms, 0 LLM calls).
3. **3. High-Severity Gemini Judge:** Decision support financial fee waiver query $\rightarrow$ Gemini Flash Lite LLM Judge $\rightarrow$ `ALLOW` (487.6 ms).
4. **4. Contradiction $\rightarrow$ Self-Healing Repair $\rightarrow$ ALLOW:** Initial $1,000 waiver contradiction $\rightarrow$ Auto-repair to $200 capped waiver $\rightarrow$ Pipeline re-entry $\rightarrow$ `ALLOW` (154.2 ms).
5. **5. Insufficient Evidence Gate $\rightarrow$ ESCALATE:** Interdimensional teleportation warranty $\rightarrow$ Insufficient evidence gate $\rightarrow$ Gemini strictly bypassed $\rightarrow$ `ESCALATE` (13.5 ms).
6. **6. Adjudication Inconclusive $\rightarrow$ ESCALATE:** Plan B roaming boundary ambiguity $\rightarrow$ Inconclusive judge $\rightarrow$ Conservative `ESCALATE` (517.9 ms).

---

## 4. API Dependencies & Endpoints
- `GET /health` — Verifies backend connection status.
- `GET /` — Root metadata and service status.
- `GET /ui` — Serves built React dashboard.
- `POST /inspect` — Executes synchronous end-to-end ControlPlane inspection.
- **Graceful Fallback:** When the backend server is unreachable, the UI automatically transitions to Deterministic Demo Mode with a visible status chip.

---

## 5. Verification & Build Status
- **Frontend Build (`npm run build`):** 100% clean production bundle (241 kB gzipped JS, 3.3 kB CSS).
- **Backend API Integration Tests (`test_ui_api_integration.py`):** 4/4 passing.
- **Complete Test Suite:** 130/130 passing.
