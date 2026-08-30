"""Benchmark and evaluation data models, metrics contracts, and results schemas."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from app.domain.models import ActionType, AdjudicationTrigger, RiskLevel, SeverityLevel, VerificationStatus


class BenchmarkCase(BaseModel):
    """Single ground-truth benchmark test case."""
    case_id: str
    application_profile: str  # CUSTOMER_SUPPORT, INTERNAL_KNOWLEDGE, DECISION_SUPPORT
    policy_version: int = 1
    mode: str = "REALTIME"
    prompt: str
    response_fixture: str
    reference_evidence: List[Dict[str, Any]] = Field(default_factory=list)
    session_id: Optional[str] = None
    expected_risk_types: List[str] = Field(default_factory=list)
    expected_severity: str = "LOW"  # LOW, MEDIUM, HIGH, CRITICAL
    expected_evidence_state: str = "ADEQUATE"  # ADEQUATE, INSUFFICIENT, NOT_REQUIRED
    expected_nli_label: Optional[str] = "SUPPORTED"  # SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE, None
    expected_final_action: str = "ALLOW"  # ALLOW, WARN, ABSTAIN, REPAIR, BLOCK, ESCALATE
    expected_adjudication_trigger: str = "NONE"  # NONE, NLI_LOW_CONFIDENCE, NLI_CLOSE_TOP2, etc.
    expected_adjudication_outcome: str = "NOT_REQUIRED"  # NOT_REQUIRED, ADJUDICATED, INCONCLUSIVE, BUDGET_EXHAUSTED
    expected_session_behavior: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    difficulty: str = "NORMAL"  # NORMAL, HARD_NEGATIVE, ADVERSARIAL


class PerCaseResult(BaseModel):
    """Execution and evaluation result for a single benchmark case."""
    case_id: str
    passed: bool
    error_categories: List[str] = Field(default_factory=list)

    # Expected values
    expected_risk_types: List[str]
    expected_severity: str
    expected_nli_label: Optional[str]
    expected_adjudication_trigger: str
    expected_adjudication_outcome: str
    expected_final_action: str

    # Actual values
    actual_risk_types: List[str]
    actual_severity: str
    actual_highest_severity: Optional[str] = None
    actual_nli_label: Optional[str] = None
    actual_verification_status: str
    actual_adjudication_trigger: str
    actual_adjudication_outcome: str
    actual_final_action: str
    nli_confidence: Optional[float] = None
    nli_top2_scores: Optional[Dict[str, float]] = None
    likely_failure_stage: Optional[str] = None
    diagnostic_explanation: Optional[str] = None

    # Runtime & Telemetry
    total_latency_ms: float
    tier0_latency_ms: float
    risk_latency_ms: float
    tier1_latency_ms: float
    adjudication_latency_ms: float
    repair_latency_ms: float
    action_latency_ms: float
    session_risk_latency_ms: float
    estimated_cost_usd: float
    total_tokens: int
    adjudication_calls: int
    repair_attempts: int

    # Quality notes
    notes: Optional[str] = None


class RiskTypeMetrics(BaseModel):
    """Precision, recall, and error rates per risk category."""
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    true_negatives: int = 0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0
    fpr: float = 0.0
    fnr: float = 0.0


class EvaluationMetrics(BaseModel):
    """Comprehensive evaluation metrics summary."""
    dataset_name: str
    total_cases: int
    passed_cases: int
    overall_accuracy: float

    # Risk Detection
    risk_detection_precision: float
    risk_detection_recall: float
    risk_detection_f1: float
    risk_detection_fpr: float
    risk_detection_fnr: float
    per_risk_metrics: Dict[str, RiskTypeMetrics] = Field(default_factory=dict)

    # Decision & Policy Quality
    action_accuracy: float
    safe_intervention_rate: float
    unsafe_pass_rate: float
    unnecessary_escalation_rate: float
    repair_success_rate: float
    action_precedence_correctness: float

    # Adjudication Metrics
    adjudication_trigger_precision: float
    adjudication_trigger_recall: float
    adjudication_invocation_rate: float
    adjudication_inconclusive_rate: float
    nli_only_accuracy: float
    nli_plus_adjudication_accuracy: float
    accuracy_gain_from_adjudication: float
    unsafe_pass_reduction_rate: float
    cost_per_corrected_ambiguity_usd: float

    # Runtime & Latency Percentiles (Local Dev Environment)
    p50_latency_ms: float
    p90_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_latency_ms: float
    tier1_invocation_rate: float
    avg_repairs_per_request: float
    avg_cost_per_request_usd: float
    total_cost_usd: float

    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AblationResult(BaseModel):
    """Comparison of system performance under different architectural configurations."""
    configuration_name: str  # NO_CHECKER, ALWAYS_ON_JUDGE, NLI_ONLY, FULL_CASCADE
    description: str
    accuracy: float
    fpr: float
    fnr: float
    unsafe_pass_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    avg_cost_per_request_usd: float
    adjudication_rate: float
    cost_per_corrected_ambiguity_usd: Optional[float] = None


class HumanFeedbackItem(BaseModel):
    """Offline human reviewer feedback record."""
    feedback_id: UUID = Field(default_factory=uuid4)
    case_id: str
    system_action: str
    reviewer_action: str
    reviewer_reason: str
    correct_action: str
    is_override: bool
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CalibrationRecommendation(BaseModel):
    """Threshold calibration recommendations generated from benchmark/feedback analysis."""
    parameter: str
    current_value: Any
    recommended_value: Any
    rationale: str
    expected_impact: str
