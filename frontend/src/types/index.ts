export type ActionType = 'ALLOW' | 'BLOCK' | 'REPAIR' | 'WARN' | 'ABSTAIN' | 'ESCALATE';

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type SeverityLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

export type VerificationStatus =
  | 'DIRECT_NLI'
  | 'ADJUDICATED'
  | 'ADJUDICATION_INCONCLUSIVE'
  | 'INSUFFICIENT_EVIDENCE';

export type VerifierType = 'LOCAL_NLI' | 'GEMINI_LLM_JUDGE' | 'INSUFFICIENT_EVIDENCE' | 'PREFLIGHT_BLOCKED';

export interface PolicyEventItem {
  event_type: string;
  detector: string;
  severity: SeverityLevel;
  confidence: number;
  matched_text?: string;
  metadata?: Record<string, any>;
  action_taken?: ActionType;
}

export interface ClaimEvidenceQuality {
  authority?: string;
  freshness?: number;
  relevance?: number;
  completeness?: number;
  quality_score?: number;
  freshness_status?: string;
}

export interface ClaimVerificationItem {
  claim_id: string;
  claim_index: number;
  claim_text: string;
  severity?: SeverityLevel;
  verification_status?: VerificationStatus;
  nli_confidence?: number;
  top2_scores?: Record<string, number>;
  adjudication_trigger?: string;
  uncertainty_reason?: string;
  adjudicator_model?: string;
  adjudicator_confidence?: number;
  final_label?: string | null;
  evidence_quality?: ClaimEvidenceQuality;
}

export interface CostTelemetry {
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  adjudication_cost_usd: number;
  total_cost_usd: number;
  adjudication_calls: number;
  retry_attempts: number;
}

export interface TimingTelemetry {
  preflight_ms: number;
  model_ms: number;
  tier0_ms: number;
  risk_ms: number;
  evidence_ms: number;
  evidence_quality_ms: number;
  tier1_ms: number;
  adjudication_ms: number;
  repair_ms: number;
  action_ms: number;
  session_risk_ms: number;
  total_controlplane_ms: number;
}

export interface RiskAssessmentResult {
  risk_level: RiskLevel;
  severity: SeverityLevel;
  task_risk_score?: number;
  response_risk_score?: number;
  final_risk_score?: number;
  verification_required: boolean;
  risk_types?: string[];
  reasons?: string[];
  highest_severity?: SeverityLevel;
  candidate_actions?: ActionType[];
}

export interface GatewayInspectResponse {
  request_id: string;
  application_id: string;
  policy_version_id?: string;
  action: ActionType;
  final_content?: string;
  repaired_content?: string;
  policy_events: PolicyEventItem[];
  claims: ClaimVerificationItem[];
  risk_assessment: RiskAssessmentResult;
  cost_telemetry: CostTelemetry;
  timing_telemetry: TimingTelemetry;
  adjudication_invocations: number;
  error?: string;
}

export interface InspectRequestPayload {
  application_id: string;
  prompt: string;
  response?: string;
  session_id?: string;
  scenario?: string;
  judge_scenario?: string;
}

export interface DemoScenario {
  id: string;
  name: string;
  badge: string;
  description: string;
  category: 'FAST_PATH' | 'THREAT_BLOCK' | 'DEEP_VERIFICATION' | 'SELF_HEALING_REPAIR' | 'EPISTEMIC_GATE';
  payload: InspectRequestPayload;
  mockResponse: GatewayInspectResponse;
  explanation: string;
}
