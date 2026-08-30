"""Domain models, enums, and API request/response schemas.

These schemas directly implement the frozen contracts defined in
ControlPlane_Round2_Component_Ownership_and_API_Contracts.md and
ControlPlane_Round2_Database_Schema.sql.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, Field


# --- Canonical Enums ---

class ActionType(str, Enum):
    """Canonical action vocabulary."""
    ALLOW = "ALLOW"
    WARN = "WARN"
    ABSTAIN = "ABSTAIN"
    REPAIR = "REPAIR"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class RiskLevel(str, Enum):
    """Canonical risk classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SeverityLevel(str, Enum):
    """Consequence of error classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class VerificationStatus(str, Enum):
    """Controlled verification status values."""
    DIRECT_NLI = "DIRECT_NLI"
    ADJUDICATED = "ADJUDICATED"
    ADJUDICATION_INCONCLUSIVE = "ADJUDICATION_INCONCLUSIVE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class AdjudicationTrigger(str, Enum):
    """Controlled adjudication trigger reasons."""
    NONE = "NONE"
    NLI_LOW_CONFIDENCE = "NLI_LOW_CONFIDENCE"
    NLI_CLOSE_TOP2 = "NLI_CLOSE_TOP2"
    NLI_EVIDENCE_LABEL_CONFLICT = "NLI_EVIDENCE_LABEL_CONFLICT"
    HIGH_SEVERITY_MARGINAL_NLI = "HIGH_SEVERITY_MARGINAL_NLI"


class UncertaintyReason(str, Enum):
    """Controlled uncertainty reasons."""
    NONE = "NONE"
    NLI_LOW_CONFIDENCE = "NLI_LOW_CONFIDENCE"
    NLI_CLOSE_TOP2 = "NLI_CLOSE_TOP2"
    NLI_EVIDENCE_LABEL_CONFLICT = "NLI_EVIDENCE_LABEL_CONFLICT"
    HIGH_SEVERITY_MARGINAL_NLI = "HIGH_SEVERITY_MARGINAL_NLI"
    JUDGE_LOW_CONFIDENCE = "JUDGE_LOW_CONFIDENCE"
    ADJUDICATION_BUDGET_EXHAUSTED = "ADJUDICATION_BUDGET_EXHAUSTED"


# --- Common Domain Objects ---

class ClaimEvidenceQuality(BaseModel):
    """Post-retrieval evidence quality scores."""
    authority: Optional[str] = "HIGH"  # HIGH, MEDIUM, LOW
    freshness: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    relevance: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    completeness: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    quality_score: Optional[float] = Field(default=1.0, ge=0.0, le=1.0)
    freshness_status: Optional[str] = "FRESH"  # FRESH, STALE, UNKNOWN


class EvidenceSnippet(BaseModel):
    """Source evidence item."""
    evidence_id: UUID = Field(default_factory=uuid4)
    content_snippet: str
    source_type: Optional[str] = "KNOWLEDGE_BASE"
    source_id: Optional[str] = None
    document_version: Optional[str] = None
    chunk_id: Optional[str] = None
    quality: Optional[ClaimEvidenceQuality] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ClaimVerificationItem(BaseModel):
    """Claim verification outcome item."""
    claim_id: UUID = Field(default_factory=uuid4)
    claim_index: int = 0
    claim_text: str
    severity: Optional[SeverityLevel] = SeverityLevel.MEDIUM
    verification_status: VerificationStatus = VerificationStatus.DIRECT_NLI
    final_label: Optional[str] = None  # None allowed when ADJUDICATION_INCONCLUSIVE
    nli_confidence: Optional[float] = None
    top2_scores: Optional[Dict[str, float]] = None
    adjudication_trigger: AdjudicationTrigger = AdjudicationTrigger.NONE
    uncertainty_reason: UncertaintyReason = UncertaintyReason.NONE
    adjudicator_model: Optional[str] = None
    adjudicator_confidence: Optional[float] = None
    adjudication_invoked: bool = False
    evidence_quality: Optional[ClaimEvidenceQuality] = None


class PolicyEventItem(BaseModel):
    """Tier 0 or policy event item."""
    event_type: str  # e.g., PII, SECRET, BIAS, TOXICITY, POLICY_VIOLATION, HALLUCINATION
    detector: str
    severity: Optional[SeverityLevel] = SeverityLevel.MEDIUM
    confidence: float = 1.0
    matched_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    action_taken: Optional[ActionType] = None


class TimingTelemetry(BaseModel):
    """Stage-by-stage timing instrumentation (ms)."""
    preflight_ms: float = 0.0
    model_ms: float = 0.0
    tier0_ms: float = 0.0
    risk_ms: float = 0.0
    tier1_ms: float = 0.0
    evidence_quality_ms: float = 0.0
    adjudication_ms: float = 0.0
    repair_ms: float = 0.0
    action_ms: float = 0.0
    session_risk_ms: float = 0.0
    total_controlplane_ms: float = 0.0


class CostTelemetry(BaseModel):
    """Runtime cost & latency metrics."""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_latency_ms: int = 0
    estimated_model_cost_usd: float = 0.0
    estimated_adjudication_cost_usd: float = 0.0
    total_cost_usd: float = 0.0
    adjudication_calls: int = 0
    repair_attempts: int = 0


class SessionRiskTelemetry(BaseModel):
    """Session risk tracking state."""
    session_id: str
    prior_score: float = 0.0
    current_score: float = 0.0
    level: str = "NORMAL"  # NORMAL, ELEVATED, STRICT
    turn_count: int = 1
    violations_count: int = 0
    contradictions_count: int = 0
    repairs_count: int = 0
    uncertainties_count: int = 0


# --- Pre-Flight API Contracts ---

class PreflightRequest(BaseModel):
    """Pre-flight check request before invoking AI model."""
    application_id: UUID
    policy_version_id: Optional[UUID] = None
    prompt: str
    mode: str = "REALTIME"
    session_id: Optional[str] = None
    estimated_input_tokens: Optional[int] = None


class PreflightResponse(BaseModel):
    """Pre-flight check decision."""
    request_id: UUID = Field(default_factory=uuid4)
    action: ActionType = ActionType.ALLOW
    application_id: Optional[UUID] = None
    policy_version_id: Optional[UUID] = None
    mode: str = "REALTIME"
    allowed_model: Optional[str] = None
    output_token_budget: Optional[int] = None
    cost_budget_usd: Optional[float] = None
    reasons: List[str] = Field(default_factory=list)


# --- Risk API Contracts ---

class RiskRequest(BaseModel):
    """Risk & Severity Engine request."""
    request_id: UUID
    application_id: UUID
    policy_version_id: Optional[UUID] = None
    mode: str = "REALTIME"
    task_signals: Dict[str, Any] = Field(default_factory=dict)
    response_signals: Dict[str, Any] = Field(default_factory=dict)
    evidence_availability: Dict[str, Any] = Field(default_factory=dict)
    session_state: Dict[str, Any] = Field(default_factory=dict)
    cost_state: Dict[str, Any] = Field(default_factory=dict)


class RiskAssessmentResult(BaseModel):
    """Multi-label risk scoring details."""
    task_risk_score: Optional[float] = None
    response_risk_score: Optional[float] = None
    evidence_availability_score: Optional[float] = None
    sensitivity_score: Optional[float] = None
    severity_score: Optional[float] = None
    session_risk_score: Optional[float] = None
    final_risk_score: Optional[float] = None
    risk_level: RiskLevel
    severity: SeverityLevel
    highest_severity: Optional[SeverityLevel] = None
    verification_required: bool
    risk_types: List[str] = Field(default_factory=list)  # e.g. ["PII", "HALLUCINATION", "BIAS"]
    candidate_actions: List[ActionType] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class RiskResponse(BaseModel):
    """Risk & Severity Engine response."""
    risk_level: RiskLevel
    severity: SeverityLevel
    verification_required: bool
    reasons: List[str] = Field(default_factory=list)


# --- Verifier API Contracts ---

class VerifierRequest(BaseModel):
    """Tier 1 Verifier request."""
    claim_id: UUID
    claim_text: str
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    policy_thresholds: Dict[str, Any] = Field(default_factory=dict)


class VerifierResponse(BaseModel):
    """Tier 1 Verifier response."""
    label: str  # SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE
    nli_confidence: float
    top2_scores: Optional[Dict[str, float]] = None
    evidence_ids: List[UUID] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.DIRECT_NLI
    adjudication_trigger: AdjudicationTrigger = AdjudicationTrigger.NONE
    uncertainty_reason: UncertaintyReason = UncertaintyReason.NONE
    evidence_quality: Optional[ClaimEvidenceQuality] = None
    adjudicator_model: Optional[str] = None
    adjudicator_confidence: Optional[float] = None


# --- Adjudication API Contracts ---

class AdjudicationRequest(BaseModel):
    """Selective Adjudication request."""
    claim_id: UUID
    claim_text: str
    evidence: List[EvidenceSnippet] = Field(default_factory=list)
    nli_label: str
    nli_confidence: float
    trigger: AdjudicationTrigger
    policy_thresholds: Dict[str, Any] = Field(default_factory=dict)
    scenario: Optional[str] = None


class AdjudicationResponse(BaseModel):
    """Selective Adjudication response."""
    verification_status: VerificationStatus
    final_label: Optional[str] = None  # None for ADJUDICATION_INCONCLUSIVE
    adjudicator_model: Optional[str] = "mock-judge-v1"
    adjudicator_confidence: Optional[float] = None
    uncertainty_reason: UncertaintyReason = UncertaintyReason.NONE
    adjudication_invoked: bool = True
    estimated_cost_usd: float = 0.005


# --- Gateway API Contracts ---

class GatewayInspectRequest(BaseModel):
    """Gateway inspection request for full pipeline orchestration."""
    request_id: Optional[UUID] = None
    application_id: UUID
    policy_version_id: Optional[UUID] = None
    prompt: str
    response: Optional[str] = None
    scenario: Optional[str] = None  # Scenario override for MockModel: SAFE, PII, CONTRADICTED, INSUFFICIENT, AMBIGUOUS_NLI, etc.
    judge_scenario: Optional[str] = None  # Scenario override for MockAdjudicator: CONFIDENT_SUPPORTED, CONFIDENT_CONTRADICTED, INCONCLUSIVE
    model_metadata: Dict[str, Any] = Field(default_factory=dict)
    session_id: Optional[str] = None


class GatewayInspectResponse(BaseModel):
    """Gateway inspection result."""
    request_id: UUID
    application_id: UUID
    policy_version_id: Optional[UUID] = None
    action: ActionType
    final_content: Optional[str] = None
    risk_assessment: RiskAssessmentResult
    policy_events: List[PolicyEventItem] = Field(default_factory=list)
    claims: List[ClaimVerificationItem] = Field(default_factory=list)
    repair_history: List[Dict[str, Any]] = Field(default_factory=list)
    adjudication_invocations: int = 0
    session_risk: Optional[SessionRiskTelemetry] = None
    applied_policy: Dict[str, Any] = Field(default_factory=dict)
    cost_telemetry: CostTelemetry
    timing_telemetry: TimingTelemetry = Field(default_factory=TimingTelemetry)


# --- Health & Diagnostic Contract ---

class HealthStatusResponse(BaseModel):
    """System health check response."""
    status: str
    version: str
    environment: str
    database: str
    redis: str
