"""Offline Ground-Truth Benchmark Evaluation Runner and Ablation Engine."""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.models import ActionType, GatewayInspectRequest
from app.gateway.service import GatewayService
from app.tier1.service import Tier1Service
from app.evaluation.evidence_repo import EvaluationEvidenceRepository
from app.persistence import (
    CUSTOMER_SUPPORT_APP_ID,
    DECISION_SUPPORT_APP_ID,
    INTERNAL_KB_APP_ID,
    seed_database_async,
)
from .metrics import MetricsCalculator
from .models import (
    AblationResult,
    BenchmarkCase,
    EvaluationMetrics,
    PerCaseResult,
)


class EvaluationRunner:
    """Orchestrates offline benchmark dataset execution, trace collection, and ablation studies."""

    PROFILE_MAP = {
        "CUSTOMER_SUPPORT": CUSTOMER_SUPPORT_APP_ID,
        "INTERNAL_KNOWLEDGE": INTERNAL_KB_APP_ID,
        "DECISION_SUPPORT": DECISION_SUPPORT_APP_ID,
    }

    def __init__(
        self,
        gateway_service: Optional[GatewayService] = None,
        metrics_calculator: Optional[MetricsCalculator] = None,
    ):
        if not gateway_service:
            from app.tier1.service import Tier1Service
            from app.tier1.nli_real import RealNLIVerifier
            tier1 = Tier1Service(verifier=RealNLIVerifier())
            self.gateway = GatewayService(tier1_service=tier1)
        else:
            self.gateway = gateway_service
            
        self.metrics_calc = metrics_calculator or MetricsCalculator()

    def load_dataset(self, filepath: str) -> List[BenchmarkCase]:
        """Load benchmark cases from a JSONL file."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Benchmark dataset file not found: {filepath}")

        cases: List[BenchmarkCase] = []
        with open(path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                clean = line.strip()
                if not clean:
                    continue
                try:
                    case_dict = json.loads(clean)
                    cases.append(BenchmarkCase(**case_dict))
                except Exception as e:
                    raise ValueError(f"Failed to parse case at line {line_num} in {filepath}: {e}")
        return cases

    async def run_case(
        self,
        case: BenchmarkCase,
        db_session: AsyncSession,
        ablation_mode: Optional[str] = None,
    ) -> PerCaseResult:
        """Execute a single benchmark case and evaluate actual against expected outcome."""
        app_id = self.PROFILE_MAP.get(case.application_profile.upper(), CUSTOMER_SUPPORT_APP_ID)
        session_id = case.session_id or f"eval-sess-{uuid4()}"

        req = GatewayInspectRequest(
            application_id=app_id,
            prompt=case.prompt,
            response=case.response_fixture,
            session_id=session_id,
            model_metadata={"ablation_mode": ablation_mode} if ablation_mode else {},
        )
        
        # Inject isolated evidence repository for this case
        eval_repo = EvaluationEvidenceRepository(case.reference_evidence)
        tier1 = Tier1Service(
            evidence_repo=eval_repo,
            verifier=self.gateway.tier1_service.verifier,
            quality_evaluator=self.gateway.tier1_service.quality_evaluator,
        )
        
        case_gateway = GatewayService(
            model_provider=self.gateway.model_provider,
            preflight_service=self.gateway.preflight_service,
            tier0_service=self.gateway.tier0_service,
            risk_engine=self.gateway.risk_engine,
            tier1_service=tier1,
            adjudication_service=self.gateway.adjudication_service,
            repair_service=self.gateway.repair_service,
            action_engine=self.gateway.action_engine,
            state_store=self.gateway.state_store,
            session_risk_tracker=self.gateway.session_risk_tracker,
            multi_label_aggregator=self.gateway.multi_label_aggregator,
        )

        t_start = time.perf_counter()
        resp = await case_gateway.inspect(req, db_session)
        tot_time = round((time.perf_counter() - t_start) * 1000, 2)

        # Extract actual outcomes
        actual_risk_types = resp.risk_assessment.risk_types
        actual_severity = resp.risk_assessment.severity.value
        actual_highest_sev = resp.risk_assessment.highest_severity.value if resp.risk_assessment.highest_severity else actual_severity
        actual_action = resp.action.value

        primary_claim = resp.claims[0] if resp.claims else None
        actual_nli_label = primary_claim.final_label if primary_claim else None
        actual_status = primary_claim.verification_status.value if primary_claim else "NOT_REQUIRED"
        actual_trigger = primary_claim.adjudication_trigger.value if primary_claim else "NONE"

        # Resolve actual adjudication outcome category
        if resp.adjudication_invocations == 0:
            if primary_claim and primary_claim.uncertainty_reason.value == "ADJUDICATION_BUDGET_EXHAUSTED":
                actual_outcome = "BUDGET_EXHAUSTED"
            else:
                actual_outcome = "NOT_REQUIRED"
        else:
            if actual_status == "ADJUDICATED":
                actual_outcome = "ADJUDICATED"
            elif actual_status == "ADJUDICATION_INCONCLUSIVE":
                actual_outcome = "INCONCLUSIVE"
            else:
                actual_outcome = "ADJUDICATED"

        # Compare expected vs actual
        error_categories: List[str] = []

        # 1. Action Check
        if actual_action != case.expected_final_action:
            error_categories.append(f"ACTION_MISMATCH(exp={case.expected_final_action},act={actual_action})")

        # 2. Risk Types Check (for cases expecting specific risks)
        if case.expected_risk_types:
            missing_risks = set(case.expected_risk_types) - set(actual_risk_types)
            if missing_risks:
                error_categories.append(f"RISK_TYPE_MISMATCH(missing={list(missing_risks)})")

        # 3. Adjudication Trigger Check
        if case.expected_adjudication_trigger != "NONE":
            if actual_trigger != case.expected_adjudication_trigger:
                error_categories.append(f"TRIGGER_MISMATCH(exp={case.expected_adjudication_trigger},act={actual_trigger})")

        # 4. Adjudication Outcome Check
        if case.expected_adjudication_outcome != "NOT_REQUIRED":
            if actual_outcome != case.expected_adjudication_outcome:
                error_categories.append(f"OUTCOME_MISMATCH(exp={case.expected_adjudication_outcome},act={actual_outcome})")

        passed = len(error_categories) == 0

        return PerCaseResult(
            case_id=case.case_id,
            passed=passed,
            error_categories=error_categories,
            expected_risk_types=case.expected_risk_types,
            expected_severity=case.expected_severity,
            expected_nli_label=case.expected_nli_label,
            expected_adjudication_trigger=case.expected_adjudication_trigger,
            expected_adjudication_outcome=case.expected_adjudication_outcome,
            expected_final_action=case.expected_final_action,
            actual_risk_types=actual_risk_types,
            actual_severity=actual_severity,
            actual_highest_severity=actual_highest_sev,
            actual_nli_label=actual_nli_label,
            actual_verification_status=actual_status,
            actual_adjudication_trigger=actual_trigger,
            actual_adjudication_outcome=actual_outcome,
            actual_final_action=actual_action,
            nli_confidence=primary_claim.nli_confidence if primary_claim else None,
            nli_top2_scores=primary_claim.top2_scores if primary_claim else None,
            total_latency_ms=tot_time,
            tier0_latency_ms=resp.timing_telemetry.tier0_ms,
            risk_latency_ms=resp.timing_telemetry.risk_ms,
            tier1_latency_ms=resp.timing_telemetry.tier1_ms,
            adjudication_latency_ms=resp.timing_telemetry.adjudication_ms,
            repair_latency_ms=resp.timing_telemetry.repair_ms,
            action_latency_ms=resp.timing_telemetry.action_ms,
            session_risk_latency_ms=resp.timing_telemetry.session_risk_ms,
            estimated_cost_usd=resp.cost_telemetry.total_cost_usd,
            total_tokens=resp.cost_telemetry.total_tokens,
            adjudication_calls=resp.adjudication_invocations,
            repair_attempts=resp.cost_telemetry.repair_attempts,
            notes=", ".join(error_categories) if error_categories else "PASS",
        )

    async def run_dataset(
        self,
        dataset_path: str,
        db_session: AsyncSession,
        dataset_name: Optional[str] = None,
        ablation_mode: Optional[str] = None,
    ) -> Tuple[EvaluationMetrics, List[PerCaseResult]]:
        """Run full evaluation suite on a dataset file."""
        cases = self.load_dataset(dataset_path)
        results: List[PerCaseResult] = []

        for case in cases:
            res = await self.run_case(case, db_session, ablation_mode=ablation_mode)
            results.append(res)

        dname = dataset_name or Path(dataset_path).stem
        metrics = self.metrics_calc.calculate_metrics(
            results,
            dataset_name=dname,
            metadata={
                "dataset_path": dataset_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "evaluator_version": "2.0.0",
            },
        )
        return metrics, results

    async def run_ablations(
        self,
        dataset_path: str,
        db_session: AsyncSession,
    ) -> List[AblationResult]:
        """Execute required Task 8 ablations: No Checker, Always-on Judge, NLI-only, Full Cascade."""
        ablations: List[AblationResult] = []

        # 1. Ablation A: No Checker
        m_raw, r_raw = await self.run_dataset(dataset_path, db_session, dataset_name="ablation_eval", ablation_mode="NO_CHECKER")
        ablations.append(AblationResult(
            configuration_name="NO_CHECKER",
            description="Raw LLM output with no safety filters or verification",
            accuracy=m_raw.overall_accuracy,
            fpr=m_raw.risk_detection_fpr,
            fnr=m_raw.risk_detection_fnr,
            unsafe_pass_rate=m_raw.unsafe_pass_rate,
            avg_latency_ms=m_raw.avg_latency_ms,
            p95_latency_ms=m_raw.p95_latency_ms,
            avg_cost_per_request_usd=m_raw.avg_cost_per_request_usd,
            adjudication_rate=m_raw.adjudication_invocation_rate,
        ))

        # 2. Ablation B: Always-on LLM Judge
        m_on, r_on = await self.run_dataset(dataset_path, db_session, dataset_name="ablation_eval", ablation_mode="ALWAYS_ON_JUDGE_MOCK")
        ablations.append(AblationResult(
            configuration_name="ALWAYS_ON_JUDGE_MOCK",
            description="Always invoke secondary LLM judge on every single request",
            accuracy=m_on.overall_accuracy,
            fpr=m_on.risk_detection_fpr,
            fnr=m_on.risk_detection_fnr,
            unsafe_pass_rate=m_on.unsafe_pass_rate,
            avg_latency_ms=m_on.avg_latency_ms,
            p95_latency_ms=m_on.p95_latency_ms,
            avg_cost_per_request_usd=m_on.avg_cost_per_request_usd,
            adjudication_rate=m_on.adjudication_invocation_rate,
            cost_per_corrected_ambiguity_usd=m_on.cost_per_corrected_ambiguity_usd,
        ))

        # 3. Ablation C: ControlPlane Cascade with NLI-Only (No Selective Adjudication)
        m_nli, r_nli = await self.run_dataset(dataset_path, db_session, dataset_name="ablation_eval", ablation_mode="CONTROLPLANE_NLI_ONLY")
        ablations.append(AblationResult(
            configuration_name="CONTROLPLANE_NLI_ONLY",
            description="ControlPlane tiered cascade with NLI as single verifier (no LLM adjudication)",
            accuracy=m_nli.overall_accuracy,
            fpr=m_nli.risk_detection_fpr,
            fnr=m_nli.risk_detection_fnr,
            unsafe_pass_rate=m_nli.unsafe_pass_rate,
            avg_latency_ms=m_nli.avg_latency_ms,
            p95_latency_ms=m_nli.p95_latency_ms,
            avg_cost_per_request_usd=m_nli.avg_cost_per_request_usd,
            adjudication_rate=m_nli.adjudication_invocation_rate,
        ))

        # 4. Ablation D: ControlPlane Full Cascade (NLI + Selective Adjudication)
        metrics_full, full_results = await self.run_dataset(dataset_path, db_session, dataset_name="ablation_eval", ablation_mode="CONTROLPLANE_NLI_ADJUDICATION")
        ablations.append(AblationResult(
            configuration_name="FULL_CASCADE_NLI_PLUS_ADJUDICATION",
            description="Complete ControlPlane architecture: Tier 0 -> Risk -> Tier 1 -> Confidence Gate -> Selective Adjudication",
            accuracy=metrics_full.overall_accuracy,
            fpr=metrics_full.risk_detection_fpr,
            fnr=metrics_full.risk_detection_fnr,
            unsafe_pass_rate=metrics_full.unsafe_pass_rate,
            avg_latency_ms=metrics_full.avg_latency_ms,
            p95_latency_ms=metrics_full.p95_latency_ms,
            avg_cost_per_request_usd=metrics_full.avg_cost_per_request_usd,
            adjudication_rate=metrics_full.adjudication_invocation_rate,
            cost_per_corrected_ambiguity_usd=metrics_full.cost_per_corrected_ambiguity_usd,
        ))

        return ablations
