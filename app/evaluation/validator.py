"""Ground-Truth Benchmark Dataset Validation."""

from typing import Dict, List, Set, Tuple
from app.domain.models import ActionType, AdjudicationTrigger, SeverityLevel
from .models import BenchmarkCase


class BenchmarkValidator:
    """Validates benchmark cases for semantic consistency, valid enums, and non-negotiable rules."""

    VALID_PROFILES = {"CUSTOMER_SUPPORT", "INTERNAL_KNOWLEDGE", "DECISION_SUPPORT"}
    VALID_SEVERITIES = {s.value for s in SeverityLevel}
    VALID_ACTIONS = {a.value for a in ActionType}
    VALID_TRIGGERS = {t.value for t in AdjudicationTrigger}
    VALID_OUTCOMES = {"NOT_REQUIRED", "ADJUDICATED", "INCONCLUSIVE", "BUDGET_EXHAUSTED"}
    VALID_EVIDENCE_STATES = {"ADEQUATE", "INSUFFICIENT", "NOT_REQUIRED"}

    def validate_case(self, case: BenchmarkCase) -> Tuple[bool, List[str]]:
        """Validate a single benchmark case, returning (is_valid, errors)."""
        errors: List[str] = []

        # 1. Field non-empty checks
        if not case.case_id or not case.case_id.strip():
            errors.append("case_id cannot be empty")
        if not case.prompt or not case.prompt.strip():
            errors.append("prompt cannot be empty")

        # 2. Vocabulary & Taxonomy Checks
        if case.application_profile.upper() not in self.VALID_PROFILES:
            errors.append(f"Invalid application_profile '{case.application_profile}'. Valid: {self.VALID_PROFILES}")

        if case.expected_severity.upper() not in self.VALID_SEVERITIES:
            errors.append(f"Invalid expected_severity '{case.expected_severity}'. Valid: {self.VALID_SEVERITIES}")

        if case.expected_final_action.upper() not in self.VALID_ACTIONS:
            errors.append(f"Invalid expected_final_action '{case.expected_final_action}'. Valid: {self.VALID_ACTIONS}")

        if case.expected_adjudication_trigger.upper() not in self.VALID_TRIGGERS:
            errors.append(f"Invalid expected_adjudication_trigger '{case.expected_adjudication_trigger}'. Valid: {self.VALID_TRIGGERS}")

        if case.expected_adjudication_outcome.upper() not in self.VALID_OUTCOMES:
            errors.append(f"Invalid expected_adjudication_outcome '{case.expected_adjudication_outcome}'. Valid: {self.VALID_OUTCOMES}")

        if case.expected_evidence_state.upper() not in self.VALID_EVIDENCE_STATES:
            errors.append(f"Invalid expected_evidence_state '{case.expected_evidence_state}'. Valid: {self.VALID_EVIDENCE_STATES}")

        # 3. Non-Negotiable Semantic Rules
        # Rule A: Evidence insufficiency MUST NEVER trigger Selective Adjudication
        if case.expected_evidence_state.upper() == "INSUFFICIENT":
            if case.expected_adjudication_trigger.upper() != "NONE":
                errors.append(
                    f"Invalid case '{case.case_id}': Evidence insufficiency MUST NEVER trigger adjudication "
                    f"(expected_adjudication_trigger is '{case.expected_adjudication_trigger}', must be 'NONE')"
                )
            if case.expected_adjudication_outcome.upper() != "NOT_REQUIRED":
                errors.append(
                    f"Invalid case '{case.case_id}': Evidence insufficiency MUST have expected_adjudication_outcome 'NOT_REQUIRED' "
                    f"(got '{case.expected_adjudication_outcome}')"
                )

        # Rule B: Trigger 'NONE' must correspond to outcome 'NOT_REQUIRED'
        if case.expected_adjudication_trigger.upper() == "NONE":
            if case.expected_adjudication_outcome.upper() != "NOT_REQUIRED":
                errors.append(
                    f"Invalid case '{case.case_id}': When expected_adjudication_trigger is 'NONE', "
                    f"expected_adjudication_outcome must be 'NOT_REQUIRED' (got '{case.expected_adjudication_outcome}')"
                )

        # Rule C: Active trigger must have active adjudication outcome
        if case.expected_adjudication_trigger.upper() != "NONE":
            if case.expected_adjudication_outcome.upper() == "NOT_REQUIRED":
                errors.append(
                    f"Invalid case '{case.case_id}': Active trigger '{case.expected_adjudication_trigger}' "
                    "cannot have expected_adjudication_outcome 'NOT_REQUIRED'"
                )

        # Rule D: PII Hard Block Precedence
        if "PII" in [r.upper() for r in case.expected_risk_types] and case.expected_severity.upper() == "CRITICAL":
            if case.expected_final_action.upper() != "BLOCK":
                errors.append(
                    f"Invalid case '{case.case_id}': Critical PII must have expected_final_action 'BLOCK' "
                    f"(got '{case.expected_final_action}')"
                )

        return (len(errors) == 0, errors)

    def _normalize_text(self, text: str) -> str:
        """Strip numbers and punctuation for structural similarity."""
        import re
        t = re.sub(r'[\d\W_]+', ' ', text.lower())
        return " ".join(t.split())

    def validate_dataset(self, cases: List[BenchmarkCase], generate_report: bool = True) -> Tuple[bool, Dict[str, List[str]]]:
        """Validate an entire dataset of benchmark cases and detect structural leakage."""
        import json
        from pathlib import Path
        
        dataset_errors: Dict[str, List[str]] = {}
        seen_ids: Set[str] = set()
        
        exact_prompts: Dict[str, str] = {}
        normalized_prompts: Dict[str, str] = {}
        
        exact_dups = 0
        norm_dups = 0
        struct_dups = 0
        
        for case in cases:
            if case.case_id in seen_ids:
                dataset_errors.setdefault(case.case_id, []).append(f"Duplicate case_id: '{case.case_id}'")
            seen_ids.add(case.case_id)

            # Leakage checks: Ensure 'scenario' or 'judge_scenario' are NOT present in extra dict fields
            extra = case.model_dump(exclude_unset=True)
            if "scenario" in extra or "judge_scenario" in extra:
                dataset_errors.setdefault(case.case_id, []).append("Leakage detected: 'scenario' or 'judge_scenario' found in case.")

            is_valid, case_errors = self.validate_case(case)
            if not is_valid:
                dataset_errors[case.case_id] = case_errors
                
            # Duplicate detection
            p_exact = case.prompt.strip()
            p_norm = self._normalize_text(case.prompt)
            
            if p_exact in exact_prompts:
                exact_dups += 1
                dataset_errors.setdefault(case.case_id, []).append(f"Exact prompt duplicate of {exact_prompts[p_exact]}")
            else:
                exact_prompts[p_exact] = case.case_id
                
            if p_norm in normalized_prompts and p_exact not in exact_prompts:
                norm_dups += 1
                dataset_errors.setdefault(case.case_id, []).append(f"Normalized text duplicate of {normalized_prompts[p_norm]}")
            else:
                normalized_prompts[p_norm] = case.case_id
                
        # Optional semantic near duplicate check could be added here via embeddings

        if generate_report:
            report = {
                "total_cases": len(cases),
                "exact_duplicates": exact_dups,
                "normalized_duplicates": norm_dups,
                "structural_duplicates": struct_dups,
                "errors": dataset_errors,
            }
            out_dir = Path("artifacts/evaluation")
            out_dir.mkdir(parents=True, exist_ok=True)
            with open(out_dir / "dataset_quality_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)

        return (len(dataset_errors) == 0, dataset_errors)
