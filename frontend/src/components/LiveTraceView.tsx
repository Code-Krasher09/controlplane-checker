import React, { useState } from 'react';
import {
  Play,
  RotateCcw,
  ShieldCheck,
  Clock,
  Sparkles,
  ChevronRight,
  ChevronDown,
  Shield,
  AlertTriangle,
  Search,
  Brain,
  Cpu,
  Wrench,
  Zap,
  FileCheck,
  Minus,
  Plus,
} from 'lucide-react';
import type { GatewayInspectResponse, InspectRequestPayload, DemoScenario } from '../types';
import { DEMO_SCENARIOS } from '../data/demoScenarios';

/* ═══════════════════════════════════════════════════════════════════════
   Props & Types
   ═══════════════════════════════════════════════════════════════════════ */
interface LiveTraceViewProps {
  onRunInspect: (payload: InspectRequestPayload) => Promise<void>;
  currentResponse: GatewayInspectResponse | null;
  isLoading: boolean;
  activeScenarioId: string | null;
  onSelectScenario: (scenario: DemoScenario) => void;
  selectedProfile: string;
}

type StageStatus = 'pass' | 'warn' | 'fail' | 'skip' | 'active';

interface WaterfallStage {
  id: string;
  label: string;
  icon: React.ReactNode;
  durationMs: number;
  status: StageStatus;
  badgeText: string;
  isChild?: boolean;
  isVisible: boolean;
  autoExpand?: boolean;
  renderDetail: () => React.ReactNode;
}

/* ═══════════════════════════════════════════════════════════════════════
   Helpers
   ═══════════════════════════════════════════════════════════════════════ */

/** Map a verdict action to its CSS variable name */
const verdictColor = (action: string): string => {
  switch (action) {
    case 'ALLOW': return 'var(--verdict-allow)';
    case 'BLOCK': return 'var(--verdict-block)';
    case 'ESCALATE': return 'var(--verdict-escalate)';
    case 'REPAIR': return 'var(--verdict-repair)';
    default: return 'var(--verdict-allow)';
  }
};

/** Map a verdict action to its badge class */
const verdictBadgeClass = (action: string): string => {
  switch (action) {
    case 'ALLOW': return 'badge badge-verdict-allow';
    case 'BLOCK': return 'badge badge-verdict-block';
    case 'ESCALATE': return 'badge badge-verdict-escalate';
    case 'REPAIR': return 'badge badge-verdict-repair';
    default: return 'badge badge-verdict-allow';
  }
};

/** Map a stage status to its badge class */
const stateBadgeClass = (status: StageStatus): string => {
  switch (status) {
    case 'pass': return 'state-badge state-badge-pass';
    case 'warn': return 'state-badge state-badge-warn';
    case 'fail': return 'state-badge state-badge-fail';
    case 'skip': return 'state-badge state-badge-skip';
    case 'active': return 'state-badge state-badge-active';
  }
};

/** Format milliseconds for display */
const fmtMs = (ms: number): string => {
  if (ms === 0) return '0.0 ms';
  if (ms < 1) return `${ms.toFixed(1)} ms`;
  if (ms < 100) return `${ms.toFixed(1)} ms`;
  return `${ms.toFixed(0)} ms`;
};

/* ═══════════════════════════════════════════════════════════════════════
   Known "before" texts for repair diff in demo mode
   ═══════════════════════════════════════════════════════════════════════ */
const REPAIR_BEFORE_TEXT: Record<string, string> = {
  'contradicted-repair': 'Yes, all customers are granted unconditional $1,000 fee waivers immediately upon request without any managerial approval.',
};

/* ═══════════════════════════════════════════════════════════════════════
   Sub-components
   ═══════════════════════════════════════════════════════════════════════ */

/** A single row in the waterfall trace */
const WaterfallRow: React.FC<{
  stage: WaterfallStage;
  totalMs: number;
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ stage, totalMs, isExpanded, onToggle }) => {
  const barWidth = totalMs > 0 ? Math.max(2, (stage.durationMs / totalMs) * 100) : 0;

  return (
    <>
      <div
        className={`waterfall-row ${stage.isChild ? 'is-child' : ''} ${stage.status === 'skip' ? 'is-skipped' : ''}`}
        onClick={stage.status !== 'skip' ? onToggle : undefined}
        role={stage.status !== 'skip' ? 'button' : undefined}
        tabIndex={stage.status !== 'skip' ? 0 : undefined}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onToggle(); } }}
      >
        {/* Expand/collapse chevron */}
        <div style={{ width: '16px', flexShrink: 0, color: 'var(--text-muted)' }}>
          {stage.status !== 'skip' ? (
            isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />
          ) : (
            <Minus size={12} />
          )}
        </div>

        {/* Stage icon */}
        <div style={{ flexShrink: 0, display: 'flex', alignItems: 'center' }}>
          {stage.icon}
        </div>

        {/* Stage name */}
        <span style={{ flex: 1, fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-primary)' }}>
          {stage.label}
        </span>

        {/* Status badge */}
        <span className={stateBadgeClass(stage.status)}>
          {stage.badgeText}
        </span>

        {/* Timing bar + duration */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: '120px', justifyContent: 'flex-end' }}>
          <div style={{ width: '60px', background: 'var(--bg-surface-2)', borderRadius: '2px', height: '3px' }}>
            <div
              className="waterfall-timing-bar"
              style={{
                width: `${barWidth}%`,
                background: stage.status === 'fail' ? 'var(--state-fail)' :
                             stage.status === 'warn' ? 'var(--state-warn)' :
                             stage.status === 'skip' ? 'var(--state-skip)' :
                             'var(--state-pass)',
              }}
            />
          </div>
          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: '0.75rem',
            fontWeight: 500,
            color: 'var(--text-secondary)',
            minWidth: '55px',
            textAlign: 'right',
          }}>
            {fmtMs(stage.durationMs)}
          </span>
        </div>
      </div>

      {/* Expanded detail panel */}
      <div className={`waterfall-row-detail ${isExpanded ? 'is-expanded' : ''} ${stage.isChild ? 'is-child' : ''}`}>
        {isExpanded && stage.renderDetail()}
      </div>
    </>
  );
};

/** Label + value pair used inside expanded details */
const DetailField: React.FC<{ label: string; value: string | number; mono?: boolean; color?: string }> = ({ label, value, mono = false, color }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
    <span style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
      {label}
    </span>
    <span style={{
      fontSize: '0.85rem',
      fontWeight: 500,
      fontFamily: mono ? "'JetBrains Mono', monospace" : undefined,
      color: color || 'var(--text-primary)',
    }}>
      {value}
    </span>
  </div>
);

/* ═══════════════════════════════════════════════════════════════════════
   Main Component
   ═══════════════════════════════════════════════════════════════════════ */
export const LiveTraceView: React.FC<LiveTraceViewProps> = ({
  onRunInspect,
  currentResponse,
  isLoading,
  activeScenarioId,
  onSelectScenario,
  selectedProfile,
}) => {
  const [customPrompt, setCustomPrompt] = useState('What is the standard retail return policy for order inquiries?');
  const [customResponse, setCustomResponse] = useState('The retail policy for order inquiries dictates a 30-day return window with full refund.');
  const [expandedStages, setExpandedStages] = useState<Set<string>>(new Set());

  /* ── Derived state from response ── */
  const resp = currentResponse;
  const primaryClaim = resp?.claims?.[0];
  const action = resp?.action || 'ALLOW';
  const timing = resp?.timing_telemetry;
  const cost = resp?.cost_telemetry;
  const risk = resp?.risk_assessment;
  const isBlockedAtTier0 = action === 'BLOCK' && (resp?.policy_events?.length || 0) > 0;
  const isInsufficient = primaryClaim?.verification_status === 'INSUFFICIENT_EVIDENCE' || primaryClaim?.final_label === 'INSUFFICIENT_EVIDENCE';
  const isInconclusive = primaryClaim?.verification_status === 'ADJUDICATION_INCONCLUSIVE';
  const isGeminiInvoked = resp?.adjudication_invocations ? resp.adjudication_invocations > 0 : primaryClaim?.adjudicator_model?.includes('gemini') || false;
  const isRepaired = (cost?.retry_attempts || 0) > 0;
  const totalMs = timing?.total_controlplane_ms || 0;

  /* Effective display action: REPAIR scenarios show as ALLOW (REPAIRED) */
  const displayAction = isRepaired ? 'REPAIR' : action;
  const displayActionText = isRepaired ? 'ALLOW (REPAIRED)' : action;

  /* ── Form handler ── */
  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const appId = selectedProfile === 'DECISION_SUPPORT'
      ? '33333333-3333-3333-3333-333333333333'
      : selectedProfile === 'INTERNAL_KNOWLEDGE'
      ? '22222222-2222-2222-2222-222222222222'
      : '11111111-1111-1111-1111-111111111111';
    onRunInspect({ application_id: appId, prompt: customPrompt, response: customResponse });
  };

  /* ── Toggle expand/collapse ── */
  const toggleStage = (id: string) => {
    setExpandedStages((prev) => {
      const next = new Set(prev);
      if (next.has(id)) { next.delete(id); } else { next.add(id); }
      return next;
    });
  };

  /* Helper to check if a stage should be auto-expanded */
  const isStageExpanded = (id: string, autoExpand?: boolean): boolean =>
    expandedStages.has(id) || (!!autoExpand && !expandedStages.has(`_collapsed_${id}`));

  /* Toggle that respects auto-expand */
  const handleToggle = (id: string, autoExpand?: boolean) => {
    if (autoExpand && !expandedStages.has(id) && !expandedStages.has(`_collapsed_${id}`)) {
      // First click on an auto-expanded stage: collapse it
      setExpandedStages((prev) => new Set(prev).add(`_collapsed_${id}`));
    } else if (expandedStages.has(`_collapsed_${id}`)) {
      // Re-expand an auto-expanded stage
      setExpandedStages((prev) => {
        const next = new Set(prev);
        next.delete(`_collapsed_${id}`);
        return next;
      });
    } else {
      toggleStage(id);
    }
  };

  /* ── Decision explainability text ── */
  const decisionReason = isBlockedAtTier0
    ? 'Critical SSN / security vulnerability detected in prompt stream. Hard BLOCK before generation.'
    : isInsufficient
    ? 'Missing authoritative knowledge. Epistemic invariant prevents LLM hallucination → human escalation.'
    : isInconclusive
    ? 'Borderline classification confidence on contested policy clause. Conservative escalation enforced.'
    : isRepaired
    ? 'Policy contradiction auto-repaired to compliant $200 capped waiver; verified safe on re-entry.'
    : isGeminiInvoked
    ? 'High-consequence financial risk demands cloud LLM logical deduction for multi-clause verification.'
    : 'Low-risk routine inquiry verified via ultra-fast local NLI path. Cloud judge bypassed (100% cost saved).';

  /* ══════════════════════════════════════════════════════════════════════
     Build waterfall stages from response data
     ══════════════════════════════════════════════════════════════════════ */
  const stages: WaterfallStage[] = [];

  // — Preflight —
  stages.push({
    id: 'preflight',
    label: 'Pre-flight Policy Gate',
    icon: <FileCheck size={15} color="var(--state-pass)" />,
    durationMs: timing?.preflight_ms || 0,
    status: 'pass',
    badgeText: 'PASSED',
    isVisible: true,
    renderDetail: () => (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <DetailField label="Policy Version" value={resp?.policy_version_id || 'default'} mono />
        <DetailField label="Application ID" value={resp?.application_id || '—'} mono />
      </div>
    ),
  });

  // — Tier 0: Security Guards —
  const t0Status: StageStatus = isBlockedAtTier0 ? 'fail' : 'pass';
  stages.push({
    id: 'tier0',
    label: 'Tier 0: Security Guards',
    icon: <Shield size={15} color={isBlockedAtTier0 ? 'var(--state-fail)' : 'var(--state-pass)'} />,
    durationMs: timing?.tier0_ms || 0,
    status: t0Status,
    badgeText: isBlockedAtTier0 ? 'HARD BLOCK' : 'CLEAN',
    isVisible: true,
    autoExpand: isBlockedAtTier0,
    renderDetail: () => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {resp?.policy_events && resp.policy_events.length > 0 ? (
          resp.policy_events.map((evt, i) => (
            <div key={i} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', padding: '8px', background: 'var(--bg-surface-2)', borderRadius: 'var(--radius-sm)' }}>
              <DetailField label="Detector" value={evt.detector} mono />
              <DetailField label="Severity" value={evt.severity} color="var(--state-fail)" />
              <DetailField label="Confidence" value={`${(evt.confidence * 100).toFixed(0)}%`} mono />
              {evt.matched_text && <DetailField label="Matched Text" value={evt.matched_text} mono />}
              <DetailField label="Action" value={evt.action_taken || 'BLOCK'} color="var(--state-fail)" />
            </div>
          ))
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
            <DetailField label="PII & Secrets" value="Clean" color="var(--state-pass)" />
            <DetailField label="Toxicity / Bias" value="Clean (0.00)" color="var(--state-pass)" />
            <DetailField label="Prompt Injection" value="Clean" color="var(--state-pass)" />
          </div>
        )}
      </div>
    ),
  });

  // — Risk & Severity Engine —
  const riskSeverity = risk?.severity || 'LOW';
  const riskStatus: StageStatus = isBlockedAtTier0 ? 'skip' : (riskSeverity === 'HIGH' || riskSeverity === 'CRITICAL') ? 'warn' : 'pass';
  stages.push({
    id: 'risk',
    label: 'Risk & Severity Engine',
    icon: <AlertTriangle size={15} color={isBlockedAtTier0 ? 'var(--state-skip)' : riskStatus === 'warn' ? 'var(--state-warn)' : 'var(--state-pass)'} />,
    durationMs: timing?.risk_ms || 0,
    status: riskStatus,
    badgeText: isBlockedAtTier0 ? 'SKIPPED' : `SEVERITY: ${riskSeverity}`,
    isVisible: true,
    renderDetail: () => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
          <DetailField label="Risk Level" value={risk?.risk_level || 'LOW'} color={riskStatus === 'warn' ? 'var(--state-warn)' : 'var(--state-pass)'} />
          <DetailField label="Final Risk Score" value={risk?.final_risk_score?.toFixed(2) || '0.00'} mono />
          <DetailField label="Verification Required" value={risk?.verification_required ? 'YES' : 'NO'} />
        </div>
        {risk?.reasons?.[0] && (
          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
            {risk.reasons[0]}
          </div>
        )}
      </div>
    ),
  });

  // — Evidence Retrieval & Sufficiency Gate —
  const evidenceStatus: StageStatus = isBlockedAtTier0 ? 'skip' : isInsufficient ? 'fail' : 'pass';
  stages.push({
    id: 'evidence',
    label: 'Evidence Sufficiency Gate',
    icon: <Search size={15} color={isBlockedAtTier0 ? 'var(--state-skip)' : isInsufficient ? 'var(--state-fail)' : 'var(--state-pass)'} />,
    durationMs: (timing?.evidence_ms || 0) + (timing?.evidence_quality_ms || 0),
    status: evidenceStatus,
    badgeText: isBlockedAtTier0 ? 'SKIPPED' : isInsufficient ? 'INSUFFICIENT' : 'ADEQUATE',
    isVisible: true,
    autoExpand: isInsufficient,
    renderDetail: () => {
      const eq = primaryClaim?.evidence_quality;
      return (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
          <DetailField
            label="Quality Score"
            value={eq?.quality_score != null ? `${(eq.quality_score * 100).toFixed(0)}%` : '—'}
            mono
            color={isInsufficient ? 'var(--state-fail)' : 'var(--state-pass)'}
          />
          <DetailField label="Authority" value={eq?.authority || (isInsufficient ? 'NONE' : 'HIGH')} />
          <DetailField
            label="Epistemic Safety"
            value={isInsufficient ? 'Hallucination Blocked' : 'Grounded'}
            color={isInsufficient ? 'var(--state-warn)' : 'var(--state-pass)'}
          />
          <DetailField label="Relevance" value={eq?.relevance?.toFixed(2) || '—'} mono />
          <DetailField label="Freshness" value={eq?.freshness_status || '—'} />
        </div>
      );
    },
  });

  // — Tier 1: Semantic Verification —
  const t1Skipped = isBlockedAtTier0;
  const t1SkippedInsufficient = isInsufficient;
  const t1Status: StageStatus = t1Skipped ? 'skip' : t1SkippedInsufficient ? 'skip' : isInconclusive ? 'warn' : 'pass';
  const t1Badge = t1Skipped ? 'SKIPPED — BLOCKED'
    : t1SkippedInsufficient ? 'SKIPPED — NO EVIDENCE'
    : isGeminiInvoked ? 'GEMINI FLASH LITE' : 'LOCAL DEBERTA-V3';

  stages.push({
    id: 'tier1',
    label: 'Tier 1: Semantic Verification',
    icon: <Brain size={15} color={t1Status === 'skip' ? 'var(--state-skip)' : isGeminiInvoked ? 'var(--accent-purple)' : 'var(--state-active)'} />,
    durationMs: timing?.tier1_ms || 0,
    status: t1Status,
    badgeText: t1Badge,
    isVisible: true,
    autoExpand: isInconclusive,
    renderDetail: () => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {primaryClaim && (
          <>
            <div style={{
              padding: '10px',
              background: 'var(--bg-surface-2)',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.8rem',
              color: 'var(--text-primary)',
              fontStyle: 'italic',
            }}>
              "{primaryClaim.claim_text}"
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
              <DetailField
                label="Verification"
                value={primaryClaim.verification_status || '—'}
              />
              <DetailField
                label="NLI Confidence"
                value={primaryClaim.nli_confidence?.toFixed(2) || '—'}
                mono
              />
              <DetailField
                label="Final Label"
                value={primaryClaim.final_label || 'PENDING'}
                color={
                  primaryClaim.final_label === 'SUPPORTED' ? 'var(--state-pass)' :
                  primaryClaim.final_label === 'INSUFFICIENT_EVIDENCE' ? 'var(--state-fail)' :
                  primaryClaim.final_label === null ? 'var(--state-warn)' :
                  'var(--text-primary)'
                }
              />
            </div>
            {primaryClaim.top2_scores && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <DetailField label="SUPPORTED Score" value={primaryClaim.top2_scores.SUPPORTED?.toFixed(2) || '—'} mono />
                <DetailField label="CONTRADICTED Score" value={primaryClaim.top2_scores.CONTRADICTED?.toFixed(2) || '—'} mono />
              </div>
            )}
            {primaryClaim.uncertainty_reason && (
              <div style={{ fontSize: '0.8rem', color: 'var(--state-warn)' }}>
                Uncertainty: {primaryClaim.uncertainty_reason}
              </div>
            )}
          </>
        )}
      </div>
    ),
  });

  // — Cloud Adjudication (child of T1, only if invoked) —
  const adjVisible = (timing?.adjudication_ms || 0) > 0;
  stages.push({
    id: 'adjudication',
    label: 'Cloud Adjudication',
    icon: <Cpu size={14} color={isInconclusive ? 'var(--state-warn)' : 'var(--accent-purple)'} />,
    durationMs: timing?.adjudication_ms || 0,
    status: isInconclusive ? 'warn' : adjVisible ? 'pass' : 'skip',
    badgeText: isInconclusive ? 'INCONCLUSIVE' : adjVisible ? 'RESOLVED' : 'NOT INVOKED',
    isChild: true,
    isVisible: adjVisible || isInconclusive,
    autoExpand: isInconclusive,
    renderDetail: () => (
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
        <DetailField label="Model" value={primaryClaim?.adjudicator_model || 'gemini-flash-lite-latest'} mono />
        <DetailField label="Confidence" value={primaryClaim?.adjudicator_confidence?.toFixed(2) || '—'} mono />
        {primaryClaim?.adjudication_trigger && (
          <DetailField label="Trigger" value={primaryClaim.adjudication_trigger} />
        )}
      </div>
    ),
  });

  // — Self-Healing Repair Loop (only if repair occurred) —
  const repairVisible = isRepaired || (timing?.repair_ms || 0) > 0;
  const repairBeforeText = activeScenarioId ? REPAIR_BEFORE_TEXT[activeScenarioId] : null;
  stages.push({
    id: 'repair',
    label: 'Self-Healing Repair Loop',
    icon: <Wrench size={15} color={repairVisible ? 'var(--verdict-repair)' : 'var(--state-skip)'} />,
    durationMs: timing?.repair_ms || 0,
    status: repairVisible ? 'pass' : 'skip',
    badgeText: repairVisible ? `${cost?.retry_attempts || 1} ATTEMPT` : 'NOT NEEDED',
    isVisible: true,
    autoExpand: repairVisible,
    renderDetail: () => (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {repairBeforeText && (
          <>
            <div style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Before (Contradicted)
            </div>
            <div className="diff-line-removed">
              <Minus size={12} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
              {repairBeforeText}
            </div>
          </>
        )}
        <div style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          After (Repaired & Verified)
        </div>
        <div className="diff-line-added">
          <Plus size={12} style={{ display: 'inline', marginRight: '6px', verticalAlign: 'middle' }} />
          {resp?.repaired_content || resp?.final_content || '—'}
        </div>
      </div>
    ),
  });

  // — Action Engine Resolution —
  stages.push({
    id: 'action',
    label: 'Action Engine Resolution',
    icon: <Zap size={15} color={verdictColor(displayAction)} />,
    durationMs: timing?.action_ms || 0,
    status: 'pass',
    badgeText: displayActionText,
    isVisible: true,
    renderDetail: () => (
      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        {decisionReason}
      </div>
    ),
  });

  const visibleStages = stages.filter((s) => s.isVisible);

  /* ══════════════════════════════════════════════════════════════════════
     Render
     ══════════════════════════════════════════════════════════════════════ */
  return (
    <div style={{
      maxWidth: '1600px',
      margin: '0 auto',
      padding: '24px',
      display: 'grid',
      gridTemplateColumns: '340px 1fr 340px',
      gap: '20px',
      alignItems: 'start',
    }}>
      {/* ─────────────────────────────────────────────────────────────────
          LEFT COLUMN: Scenarios + Custom Input
          ───────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Scenario Launcher */}
        <div className="surface-panel" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Sparkles size={16} color="var(--state-active)" />
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Demo Scenarios
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            {DEMO_SCENARIOS.map((scenario) => {
              const isActive = activeScenarioId === scenario.id;
              return (
                <button
                  key={scenario.id}
                  id={`btn-scenario-${scenario.id}`}
                  onClick={() => {
                    setCustomPrompt(scenario.payload.prompt);
                    setCustomResponse(scenario.payload.response || '');
                    onSelectScenario(scenario);
                    setExpandedStages(new Set()); // reset expansions
                  }}
                  className={`scenario-btn ${isActive ? 'is-active' : ''}`}
                >
                  <span style={{ fontSize: '0.8rem', fontWeight: 500, color: isActive ? 'var(--state-active)' : 'var(--text-primary)' }}>
                    {scenario.name}
                  </span>
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    {scenario.badge}
                  </span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom Input Form */}
        <div className="surface-panel" style={{ padding: '16px' }}>
          <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px' }}>
            Live Request Inspector
          </h3>
          <form onSubmit={handleCustomSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div>
              <label style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                User Prompt
              </label>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-1)',
                  color: 'var(--text-primary)',
                  border: '1px solid transparent',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px',
                  fontSize: '0.8rem',
                  resize: 'vertical',
                  outline: 'none',
                  fontFamily: "'Inter', sans-serif",
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--border-active)'}
                onBlur={(e) => e.target.style.borderColor = 'transparent'}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', display: 'block', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                AI Candidate Response
              </label>
              <textarea
                value={customResponse}
                onChange={(e) => setCustomResponse(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--bg-surface-1)',
                  color: 'var(--text-primary)',
                  border: '1px solid transparent',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px',
                  fontSize: '0.8rem',
                  resize: 'vertical',
                  outline: 'none',
                  fontFamily: "'Inter', sans-serif",
                  transition: 'border-color 0.15s',
                }}
                onFocus={(e) => e.target.style.borderColor = 'var(--border-active)'}
                onBlur={(e) => e.target.style.borderColor = 'transparent'}
              />
            </div>

            <button
              id="btn-inspect-submit"
              type="submit"
              disabled={isLoading}
              className="btn btn-primary"
              style={{ width: '100%', padding: '10px', marginTop: '4px' }}
            >
              {isLoading ? (
                <>
                  <RotateCcw size={16} className="animate-spin" />
                  Executing Pipeline…
                </>
              ) : (
                <>
                  <Play size={16} fill="currentColor" />
                  Run ControlPlane Inspection
                </>
              )}
            </button>
          </form>
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────
          CENTER COLUMN: Sticky Verdict + Waterfall Trace
          ───────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {/* ── Sticky Verdict Header ── */}
        <div className="verdict-sticky" style={{
          background: isLoading ? 'var(--bg-surface-0)' : undefined,
        }}>
          {isLoading ? (
            /* Loading state */
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <div className="verdict-loading" style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <span className="verdict-label">Enforced Outcome</span>
                <span className="verdict-text" style={{ color: 'var(--state-active)' }}>
                  EXECUTING…
                </span>
              </div>
              <div style={{ flex: 1 }}>
                <div className="shimmer-bar" style={{ width: '60%', marginBottom: '8px' }} />
                <div className="shimmer-bar" style={{ width: '40%' }} />
              </div>
            </div>
          ) : (
            /* Results state */
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <span className="verdict-label">Enforced Outcome</span>
                <span className="verdict-text" style={{ color: verdictColor(displayAction) }}>
                  {displayActionText}
                </span>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '6px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '0.85rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                    {fmtMs(totalMs)}
                  </span>
                  <span className={verdictBadgeClass(displayAction)}>
                    {displayAction}
                  </span>
                </div>
                <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', maxWidth: '300px', textAlign: 'right', lineHeight: 1.4 }}>
                  {decisionReason.length > 100 ? decisionReason.slice(0, 100) + '…' : decisionReason}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ── Waterfall Trace ── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
          {/* Column header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            padding: '6px 14px',
            fontSize: '0.7rem',
            fontWeight: 500,
            color: 'var(--text-muted)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
          }}>
            <span style={{ width: '16px' }} />
            <span style={{ width: '20px' }} />
            <span style={{ flex: 1, marginLeft: '10px' }}>Stage</span>
            <span style={{ minWidth: '120px' }}>Status</span>
            <span style={{ minWidth: '120px', textAlign: 'right' }}>Duration</span>
          </div>

          {isLoading ? (
            /* Shimmer skeleton rows */
            Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className={`waterfall-row cascade-delay-${i + 1}`}
                style={{ opacity: 0.5 }}
              >
                <div style={{ width: '16px' }}><ChevronRight size={14} color="var(--text-muted)" /></div>
                <div className="shimmer-bar" style={{ width: '16px', height: '16px', borderRadius: '4px' }} />
                <div className="shimmer-bar" style={{ flex: 1, marginLeft: '10px', height: '12px' }} />
                <div className="shimmer-bar" style={{ width: '70px', height: '12px' }} />
                <div className="shimmer-bar" style={{ width: '55px', height: '12px' }} />
              </div>
            ))
          ) : (
            /* Real waterfall rows */
            visibleStages.map((stage) => (
              <WaterfallRow
                key={stage.id}
                stage={stage}
                totalMs={totalMs}
                isExpanded={isStageExpanded(stage.id, stage.autoExpand)}
                onToggle={() => handleToggle(stage.id, stage.autoExpand)}
              />
            ))
          )}
        </div>
      </div>

      {/* ─────────────────────────────────────────────────────────────────
          RIGHT COLUMN: Decision Detail + Telemetry
          ───────────────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Decision Explainability */}
        <div className="surface-panel" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
            <ShieldCheck size={16} color={verdictColor(displayAction)} />
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Decision Explainability
            </h3>
          </div>

          <div style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Why This Decision
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-primary)', lineHeight: 1.6, background: 'var(--bg-surface-1)', padding: '10px', borderRadius: 'var(--radius-sm)' }}>
            {decisionReason}
          </div>

          {/* Claim text */}
          {primaryClaim && (
            <div style={{ marginTop: '12px' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 500, color: 'var(--text-muted)', marginBottom: '4px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Primary Claim
              </div>
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic', lineHeight: 1.5 }}>
                "{primaryClaim.claim_text}"
              </div>
            </div>
          )}
        </div>

        {/* Operational Telemetry */}
        <div className="surface-panel" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <Clock size={16} color="var(--state-active)" />
            <h3 style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
              Operational Telemetry
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <TelemetryRow label="Total ControlPlane Latency" value={fmtMs(totalMs)} highlight />
            <TelemetryRow label="Tier 0 Preflight" value={fmtMs(timing?.tier0_ms || 0)} />
            <TelemetryRow label="Risk Assessment" value={fmtMs(timing?.risk_ms || 0)} />
            <TelemetryRow label="Evidence Retrieval" value={fmtMs((timing?.evidence_ms || 0) + (timing?.evidence_quality_ms || 0))} />
            <TelemetryRow label="Tier 1 Verification" value={fmtMs(timing?.tier1_ms || 0)} />
            {(timing?.repair_ms || 0) > 0 && (
              <TelemetryRow label="Repair Loop" value={fmtMs(timing?.repair_ms || 0)} />
            )}

            <div style={{ height: '1px', background: 'var(--bg-surface-2)', margin: '4px 0' }} />

            <TelemetryRow
              label="Cloud LLM Calls"
              value={isGeminiInvoked ? `${resp?.adjudication_invocations || 1} Call` : '0 Calls'}
              valueColor={isGeminiInvoked ? 'var(--accent-purple)' : 'var(--state-pass)'}
            />
            <TelemetryRow
              label="Token Consumption (I/O)"
              value={`${cost?.input_tokens || 0} in / ${cost?.output_tokens || 0} out`}
            />
            <TelemetryRow
              label="Estimated Cost"
              value={`$${(cost?.total_cost_usd || 0).toFixed(5)}`}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════════════
   Telemetry Row sub-component
   ═══════════════════════════════════════════════════════════════════════ */
const TelemetryRow: React.FC<{
  label: string;
  value: string;
  highlight?: boolean;
  valueColor?: string;
}> = ({ label, value, highlight, valueColor }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
    <span style={{ color: 'var(--text-muted)' }}>{label}</span>
    <span style={{
      fontWeight: highlight ? 700 : 500,
      fontFamily: "'JetBrains Mono', monospace",
      color: valueColor || (highlight ? 'var(--state-active)' : 'var(--text-primary)'),
    }}>
      {value}
    </span>
  </div>
);
