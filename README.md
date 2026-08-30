# ControlPlane Checker (v1.3 Prototype)

> **Model-Agnostic, Policy-Aware, Risk-Adaptive Runtime Control Plane for Enterprise AI**
> 
> *Selected Architecture: `HIGH_SEVERITY_SELECTIVE_GEMINI` (Prototype v1.3)*

ControlPlane Checker is a synchronous runtime governance gateway for enterprise AI systems. It evaluates interactions through a multi-tier safety architecture: lightweight Tier 0 checks across all traffic, sub-100ms local NLI verification for routine queries, selective cloud LLM adjudication (Google Gemini) for high-consequence compliance workflows, and closed-loop self-healing repairs.

```text
"Verify cheaply by default. Escalate intelligently when risk demands it."
```

---

## 1. Multi-Tier Architecture Pipeline

```text
User / Application Request
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│ 1. Tier 0 Preflight & Security Interceptors                 │
│    • PII (Regex/SSN/Email)    • Secrets / API Keys          │
│    • Toxicity / Bias Guards   • Token Cost Pre-estimation   │
└──────────────────────────────┬──────────────────────────────┘
                               │ (Pass)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Risk & Consequence Assessment Engine                     │
│    • Policy Profiles: Customer Support / Decision Support   │
│    • Task & Response Consequence Scoring                    │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               │ (Low / Medium)                │ (High / Critical)
               ▼                               ▼
┌──────────────────────────────┐┌──────────────────────────────┐
│ 3A. Local NLI Fast Path      ││ 3B. Cloud Gemini Adjudication │
│     DeBERTa-v3-small (<10ms) ││     Gemini Flash Lite Judge  │
└──────────────┬───────────────┘└──────────────┬───────────────┘
               │                               │
               └───────────────┬───────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. Epistemic Gate & Action Engine Resolution                │
│    • ALLOW: Verified Grounded Content                       │
│    • BLOCK: Critical Security / PII Threats (0ms LLM burn)  │
│    • REPAIR: Closed-loop policy regeneration & reverify     │
│    • ESCALATE: Missing evidence or borderline ambiguity     │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Key Empirical Benchmark Results (50-Case Frozen Holdout)

- **Observed Action Accuracy:** **74.0%** (+24.0% vs unprotected baseline)
- **Cloud Gemini Calls Avoided:** **58.0%** (29 of 50 holdout requests routed to local fast path)
- **Low-Risk Path P95 Latency:** **53.53 ms** in local prototype environment
- **High-Severity Unsafe Final Egress:** **0.0% (0 / 28 cases)**
- **Tested PII / Threats Blocked:** **100.0% (4 / 4 SSN prompt cases)**
- **Epistemic Invariant:** Missing knowledge strictly bypasses Gemini to prevent hallucination

---

## 3. Repository Structure

```text
├── app/                          # Python Backend Modular Monolith
│   ├── actions/                  # Action Engine (ALLOW, BLOCK, REPAIR, ESCALATE)
│   ├── adjudication/             # Cloud LLM Adjudication
│   ├── api/v1/                   # FastAPI Endpoints (/inspect, /health, /preflight)
│   ├── core/                     # Configuration, Settings & Pydantic models
│   ├── domain/                   # Shared Domain Contracts
│   ├── evaluation/               # Holdout & Microbenchmark Runners
│   ├── gateway/                  # Gateway Orchestrator & Intercept Loop
│   ├── persistence/              # SQLAlchemy Models, PostgreSQL & SQLite Engine
│   ├── repair/                   # Closed-Loop Policy Repair Service
│   ├── risk/                     # Multi-Label Risk & Severity Engine
│   ├── tier0/                    # PII, Secrets, Toxicity Preflight Guards
│   └── tier1/                    # Hybrid Verifier (DeBERTa-v3-small + Gemini)
├── artifacts/                    # Frozen Evaluation & Benchmark Data
│   ├── demo/                     # Manifests & Scenario Traces
│   └── evaluation/               # Raw Evaluation JSON & Accounting Dumps
├── data/                         # Knowledge Base Corpora & Vector Indexes
│   └── corpus/                   # Standard Enterprise Policy Documents
├── docs/                         # Architecture Specs, Runbooks & Pitch Evidence
│   ├── DEMO_RUNBOOK.md           # 6 Canonical Demo Presentation Runbook
│   ├── FINAL_DEMO_EVIDENCE.md    # Source of Truth Evidence Pack
│   ├── FINAL_EGRESS_SAFETY.md    # Mutually Exclusive Disposition Accounting
│   └── CLAIM_VALIDATION.md       # Audit of Prospective Pitch Claims
├── frontend/                     # React 19 + TypeScript + Vite UI Dashboard
│   └── src/                      # Live Request Trace & Control Room Views
├── scripts/                      # Evaluation, Verification & Benchmarking Scripts
└── tests/                        # 130 Regression & Safety Integration Tests
```

---

## 4. Prerequisites

- **Python:** Version 3.11+ (tested on Python 3.11 – 3.14)
- **Node.js:** Version 18+ (tested on Node v24)
- **Optional Services:** PostgreSQL 16 & Redis 7 (or run fully in-memory with SQLite async)

---

## 5. Quickstart & Local Setup

### Step 1: Environment Setup
```bash
# Create and activate virtual environment
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e .
```

### Step 2: Environment Configuration
```bash
cp .env.example .env
```
> **Note on GEMINI_API_KEY:**
> - To execute live cloud adjudication against Google Gemini, populate `GEMINI_API_KEY=your_key` in `.env`.
> - If running purely with local models or in **Deterministic Demo Mode**, `GEMINI_API_KEY` may remain blank.

### Step 3: Frontend Setup & Build
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## 6. Running the System

### Option A: Run Backend & UI Together
```bash
# Start FastAPI backend (serves API at :8000 and UI dashboard at :8000/ui)
python -m app.main
```
Open **http://localhost:8000/ui** in your browser.

### Option B: Run Frontend in Vite Hot-Reload Dev Mode
```bash
cd frontend
npm run dev
```
Open **http://localhost:5173** in your browser.

---

## 7. Running Tests & Benchmarks

### Run Complete Test Suite (130 Tests)
```bash
python -m pytest
```

### Run 6 Canonical Demo Scenarios
```bash
python scripts/verify_demo_scenarios.py
```

### Run Full 50-Case Holdout Evaluation Matrix
```bash
python scripts/run_phase12a_evidence_pack.py
```

---

## 8. Demo Scenarios (Interactive UI)

1. **Safe Fast Path (Low Risk):** Routine retail return inquiry $\rightarrow$ Local DeBERTa-v3 $\rightarrow$ `ALLOW` (~5ms, 0 cloud calls).
2. **PII / Threat Hard Block:** Prompt contains SSN `111-22-3301` $\rightarrow$ Tier 0 Guard $\rightarrow$ `BLOCK` (~2ms, 0 tokens).
3. **High-Severity Gemini Judge:** Financial courtesy fee waiver $\rightarrow$ Gemini Flash Lite $\rightarrow$ `ALLOW` (~480ms, deep deduction).
4. **Contradiction $\rightarrow$ Repair $\rightarrow$ ALLOW:** Hallucinated $1,000 waiver $\rightarrow$ Auto-repaired to $200 capped waiver $\rightarrow$ Reverified $\rightarrow$ `ALLOW`.
5. **Insufficient Evidence Gate $\rightarrow$ ESCALATE:** Quantum teleportation warranty $\rightarrow$ Epistemic gate bypasses Gemini $\rightarrow$ `ESCALATE`.
6. **Adjudication Inconclusive $\rightarrow$ ESCALATE:** Borderline roaming ambiguity $\rightarrow$ Inconclusive judge $\rightarrow$ `ESCALATE`.
