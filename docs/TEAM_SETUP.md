# ControlPlane Checker — Team Setup & Collaboration Guide

This document provides exact instructions for engineers and collaborators joining the ControlPlane Checker repository.

---

## 1. Quick Developer Onboarding

### Environment & Dependencies
```bash
# Python Environment
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux / Mac:
source .venv/bin/activate

# Install Python package in editable mode with all development dependencies
pip install -e .

# Setup Configuration
cp .env.example .env
```

### Frontend Dependencies & Build
```bash
cd frontend
npm install
npm run build
cd ..
```

---

## 2. Environment Variables & Secret Handling

- **`GEMINI_API_KEY`**: Required for live cloud verification using Google Gemini Flash Lite.
- **NEVER** commit real API keys or `.env` files to Git. The root `.gitignore` explicitly prevents `.env` tracking.
- If you do not have a Gemini API key, the system runs with local NLI models and includes **Deterministic Demo Mode** for zero-cost presentation and testing.

---

## 3. Codebase Architecture & Where to Modify

- **Tier 0 Preflight & Guards:** `app/tier0/` (Regex PII scanners, toxicity models, keyword interceptors).
- **Risk & Severity Assessment:** `app/risk/` (Policy profiles, task scoring, consequence multipliers).
- **Semantic Verification (Tier 1):** `app/tier1/` (`hybrid_verifier.py`, `nli_real.py`, `semantic_verifier.py`).
- **Action Engine & Intervention Logic:** `app/actions/` (`service.py` with precedence `BLOCK > ESCALATE > REPAIR > WARN > ALLOW`).
- **Closed-Loop Repair:** `app/repair/` (Policy regenerators, diff tracing).
- **Frontend Dashboard:** `frontend/src/` (`LiveTraceView.tsx`, `ControlRoomView.tsx`, `demoScenarios.ts`).
- **Evaluation & Benchmarks:** `app/evaluation/`, `scripts/`, `artifacts/evaluation/`.

---

## 4. Testing & Quality Invariants

Before pushing any PR or branch:
1. Run full test suite:
   ```bash
   python -m pytest
   ```
   **All 130 tests must pass.**
2. Build frontend:
   ```bash
   cd frontend
   npm run build
   cd ..
   ```
3. Run demo scenario verification:
   ```bash
   python scripts/verify_demo_scenarios.py
   ```

---

## 5. Branch Naming & Contribution Flow

- **Features:** `feat/<short-description>` (e.g., `feat/add-new-pii-detector`)
- **Fixes:** `fix/<short-description>` (e.g., `fix/action-engine-precedence`)
- **Evaluation:** `eval/<short-description>` (e.g., `eval/holdout-expansion`)
- **Documentation:** `docs/<short-description>`
