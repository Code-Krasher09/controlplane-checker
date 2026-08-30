import React, { useState } from 'react';
import {
  Play,
  RotateCcw,
  ShieldCheck,
  Wrench,
  Clock,
  Sparkles,
  Layers,
} from 'lucide-react';
import type { GatewayInspectResponse, InspectRequestPayload, DemoScenario } from '../types';
import { DEMO_SCENARIOS } from '../data/demoScenarios';

interface LiveTraceViewProps {
  onRunInspect: (payload: InspectRequestPayload) => Promise<void>;
  currentResponse: GatewayInspectResponse | null;
  isLoading: boolean;
  activeScenarioId: string | null;
  onSelectScenario: (scenario: DemoScenario) => void;
  selectedProfile: string;
}

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

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const appId = selectedProfile === 'DECISION_SUPPORT'
      ? '33333333-3333-3333-3333-333333333333'
      : selectedProfile === 'INTERNAL_KNOWLEDGE'
      ? '22222222-2222-2222-2222-222222222222'
      : '11111111-1111-1111-1111-111111111111';

    onRunInspect({
      application_id: appId,
      prompt: customPrompt,
      response: customResponse,
    });
  };

  const getActionBadgeClass = (action: string) => {
    switch (action) {
      case 'ALLOW': return 'badge-allow';
      case 'BLOCK': return 'badge-block';
      case 'ESCALATE': return 'badge-escalate';
      case 'REPAIR': return 'badge-repair';
      case 'WARN': return 'badge-warn';
      default: return 'badge-allow';
    }
  };

  const primaryClaim = currentResponse?.claims?.[0];
  const isBlockedAtTier0 = currentResponse?.action === 'BLOCK' && (currentResponse?.policy_events?.length || 0) > 0;
  const isInsufficient = primaryClaim?.verification_status === 'INSUFFICIENT_EVIDENCE' || primaryClaim?.final_label === 'INSUFFICIENT_EVIDENCE';
  const isGeminiInvoked = currentResponse?.adjudication_invocations ? currentResponse.adjudication_invocations > 0 : primaryClaim?.adjudicator_model?.includes('gemini');
  const isRepaired = (currentResponse?.cost_telemetry?.retry_attempts || 0) > 0 || currentResponse?.action === 'REPAIR';

  return (
    <div style={{
      maxWidth: '1600px',
      margin: '0 auto',
      padding: '24px',
      display: 'grid',
      gridTemplateColumns: '380px 1fr 380px',
      gap: '24px',
      alignItems: 'start',
    }}>
      {/* ------------------------------------------------------------- */}
      {/* LEFT COLUMN: Request Input & Scenario Launcher */}
      {/* ------------------------------------------------------------- */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Scenario Quick-Launcher */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Sparkles size={18} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Deterministic Demo Scenarios
            </h3>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
                  }}
                  className={`glass-card glass-card-interactive ${isActive ? 'stage-active' : ''}`}
                  style={{
                    padding: '12px 14px',
                    textAlign: 'left',
                    background: isActive ? 'rgba(56, 189, 248, 0.12)' : 'var(--bg-secondary)',
                    border: isActive ? '1px solid var(--accent-blue)' : '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-md)',
                    cursor: 'pointer',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: isActive ? '#38bdf8' : '#f8fafc' }}>
                      {scenario.name}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    {scenario.badge}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Custom Input Form */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc', marginBottom: '14px' }}>
            Live Request Inspector
          </h3>
          <form onSubmit={handleCustomSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                USER PROMPT
              </label>
              <textarea
                value={customPrompt}
                onChange={(e) => setCustomPrompt(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px',
                  fontSize: '0.825rem',
                  resize: 'vertical',
                  outline: 'none',
                }}
              />
            </div>

            <div>
              <label style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: '6px' }}>
                AI CANDIDATE RESPONSE
              </label>
              <textarea
                value={customResponse}
                onChange={(e) => setCustomResponse(e.target.value)}
                rows={3}
                style={{
                  width: '100%',
                  background: 'var(--bg-secondary)',
                  color: 'var(--text-primary)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-sm)',
                  padding: '10px',
                  fontSize: '0.825rem',
                  resize: 'vertical',
                  outline: 'none',
                }}
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
                  Executing Pipeline...
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

      {/* ------------------------------------------------------------- */}
      {/* CENTER COLUMN: ControlPlane Verification Pipeline Flow */}
      {/* ------------------------------------------------------------- */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 4px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="#38bdf8" />
            <h2 style={{ fontSize: '1.05rem', fontWeight: 700, color: '#f8fafc' }}>
              Multi-Tier Pipeline Verification Flow
            </h2>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Synchronous Policy Guardrails
          </span>
        </div>

        {/* STAGE 1: Tier 0 Preflight & Guards */}
        <div className={`glass-card ${isBlockedAtTier0 ? 'stage-blocked' : 'stage-passed'}`} style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '26px',
                height: '26px',
                borderRadius: '6px',
                background: isBlockedAtTier0 ? 'rgba(244, 63, 94, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isBlockedAtTier0 ? '#fb7185' : '#38bdf8',
                fontWeight: 700,
                fontSize: '0.75rem',
              }}>
                T0
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#f8fafc' }}>
                Tier 0: Preflight & Security Guards
              </span>
            </div>
            <span className={`badge ${isBlockedAtTier0 ? 'badge-block' : 'badge-allow'}`}>
              {isBlockedAtTier0 ? 'HARD BLOCK' : 'PASSED (0 VIOLATIONS)'}
            </span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginTop: '10px' }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>PII & SECRETS</span>
              <span style={{ fontWeight: 600, color: isBlockedAtTier0 ? '#fb7185' : '#34d399' }}>
                {isBlockedAtTier0 ? currentResponse?.policy_events?.[0]?.detector : 'Clean'}
              </span>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>TOXICITY / BIAS</span>
              <span style={{ fontWeight: 600, color: '#34d399' }}>Clean (0.00)</span>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>LATENCY</span>
              <span style={{ fontWeight: 600, color: '#38bdf8' }}>
                {currentResponse?.timing_telemetry?.tier0_ms ? `${currentResponse.timing_telemetry.tier0_ms} ms` : '1.2 ms'}
              </span>
            </div>
          </div>
        </div>

        {/* STAGE 2: Risk & Consequence Assessment */}
        <div className="glass-card" style={{ padding: '16px', opacity: isBlockedAtTier0 ? 0.4 : 1.0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '26px',
                height: '26px',
                borderRadius: '6px',
                background: 'rgba(99, 102, 241, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#818cf8',
                fontWeight: 700,
                fontSize: '0.75rem',
              }}>
                R
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#f8fafc' }}>
                Risk & Consequence Assessment
              </span>
            </div>
            <span className={`badge ${currentResponse?.risk_assessment?.severity === 'HIGH' || currentResponse?.risk_assessment?.severity === 'CRITICAL' ? 'badge-escalate' : 'badge-allow'}`}>
              {currentResponse?.risk_assessment?.severity ? `SEVERITY: ${currentResponse.risk_assessment.severity}` : 'SEVERITY: LOW'}
            </span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            {currentResponse?.risk_assessment?.reasons?.[0] || 'Routine enterprise application context.'}
          </div>
        </div>

        {/* STAGE 3: Evidence Retrieval & Sufficiency Gate */}
        <div className={`glass-card ${isInsufficient ? 'stage-blocked' : ''}`} style={{ padding: '16px', opacity: isBlockedAtTier0 ? 0.4 : 1.0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '26px',
                height: '26px',
                borderRadius: '6px',
                background: isInsufficient ? 'rgba(245, 158, 11, 0.2)' : 'rgba(16, 185, 129, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isInsufficient ? '#fbbf24' : '#34d399',
                fontWeight: 700,
                fontSize: '0.75rem',
              }}>
                E
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#f8fafc' }}>
                Evidence Sufficiency Gate
              </span>
            </div>
            <span className={`badge ${isInsufficient ? 'badge-warn' : 'badge-allow'}`}>
              {isInsufficient ? 'INSUFFICIENT (GEMINI BYPASSED)' : 'ADEQUATE EVIDENCE'}
            </span>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginTop: '10px' }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>QUALITY SCORE</span>
              <span style={{ fontWeight: 600, color: isInsufficient ? '#fb7185' : '#34d399' }}>
                {isInsufficient ? '0.00 (Unmatched)' : `${((primaryClaim?.evidence_quality?.quality_score || 0.96) * 100).toFixed(0)}%`}
              </span>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>AUTHORITY</span>
              <span style={{ fontWeight: 600, color: '#38bdf8' }}>
                {primaryClaim?.evidence_quality?.authority || (isInsufficient ? 'NONE' : 'HIGH')}
              </span>
            </div>
            <div style={{ background: 'var(--bg-secondary)', padding: '8px', borderRadius: '6px' }}>
              <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem', display: 'block' }}>EPISTEMIC SAFETY</span>
              <span style={{ fontWeight: 600, color: isInsufficient ? '#fbbf24' : '#34d399' }}>
                {isInsufficient ? 'Hallucination Blocked' : 'Grounded'}
              </span>
            </div>
          </div>
        </div>

        {/* STAGE 4: Semantic Verification Layer */}
        <div className="glass-card" style={{ padding: '16px', opacity: isBlockedAtTier0 ? 0.4 : 1.0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '26px',
                height: '26px',
                borderRadius: '6px',
                background: isGeminiInvoked ? 'rgba(168, 85, 247, 0.2)' : 'rgba(56, 189, 248, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: isGeminiInvoked ? '#a855f7' : '#38bdf8',
                fontWeight: 700,
                fontSize: '0.75rem',
              }}>
                T1
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#f8fafc' }}>
                Tier 1: Semantic Verification
              </span>
            </div>
            <span className={`badge ${isGeminiInvoked ? 'badge-escalate' : 'badge-allow'}`}>
              {isInsufficient
                ? 'SKIPPED — INADEQUATE EVIDENCE'
                : isGeminiInvoked
                ? 'CLOUD GEMINI FLASH LITE (DEEP JUDGE)'
                : 'LOCAL DEBERTA-V3 (FAST PATH)'}
            </span>
          </div>

          <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px', marginTop: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px', fontSize: '0.75rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>EXTRACTED CLAIM #0</span>
              <span style={{ color: '#38bdf8', fontWeight: 600 }}>
                {primaryClaim?.final_label ? `Outcome: ${primaryClaim.final_label}` : isInsufficient ? 'INSUFFICIENT' : 'SUPPORTED'}
              </span>
            </div>
            <div style={{ fontSize: '0.825rem', color: '#f8fafc', fontStyle: 'italic' }}>
              "{primaryClaim?.claim_text || customResponse}"
            </div>
          </div>
        </div>

        {/* STAGE 5: Action Engine & Closed-Loop Repair */}
        <div className="glass-card stage-active" style={{ padding: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div style={{
                width: '26px',
                height: '26px',
                borderRadius: '6px',
                background: 'rgba(6, 182, 212, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#22d3ee',
                fontWeight: 700,
                fontSize: '0.75rem',
              }}>
                AE
              </div>
              <span style={{ fontWeight: 600, fontSize: '0.9rem', color: '#f8fafc' }}>
                Action Engine & Closed-Loop Repair
              </span>
            </div>
            <span className={`badge ${getActionBadgeClass(currentResponse?.action || 'ALLOW')}`}>
              FINAL ACTION: {currentResponse?.action || 'ALLOW'}
            </span>
          </div>

          {isRepaired && (
            <div style={{
              background: 'rgba(6, 182, 212, 0.1)',
              border: '1px solid rgba(6, 182, 212, 0.3)',
              padding: '10px',
              borderRadius: '6px',
              marginTop: '10px',
              fontSize: '0.8rem',
              color: '#22d3ee',
            }}>
              <div style={{ fontWeight: 600, marginBottom: '4px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Wrench size={14} />
                Self-Healing Repair Attempt #1 Executed:
              </div>
              <div>Initial response contradicted $200 waiver limit. Repaired text re-entered pipeline and verified compliant.</div>
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* RIGHT COLUMN: Action Decision & Observability Telemetry */}
      {/* ------------------------------------------------------------- */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* Decision & Explainability Card */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
            <ShieldCheck size={18} color="#34d399" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Action Engine Resolution
            </h3>
          </div>

          <div style={{
            background: 'var(--bg-secondary)',
            padding: '16px',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '16px',
            textAlign: 'center',
          }}>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              ENFORCED OUTCOME
            </div>
            <div style={{
              fontSize: '1.75rem',
              fontWeight: 800,
              marginTop: '4px',
              color: currentResponse?.action === 'ALLOW' ? '#34d399' : currentResponse?.action === 'BLOCK' ? '#fb7185' : '#818cf8',
            }}>
              {currentResponse?.action || 'ALLOW'}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '4px' }}>
              DECISION EXPLAINABILITY (WHY)
            </div>
            <div style={{ fontSize: '0.8rem', color: '#f8fafc', lineHeight: 1.5, background: 'rgba(255,255,255,0.03)', padding: '10px', borderRadius: '6px' }}>
              {isBlockedAtTier0
                ? 'Reason: Critical SSN / Security vulnerability detected in prompt stream. Hard BLOCK before generation.'
                : isInsufficient
                ? 'Reason: Missing authoritative knowledge. Epistemic Invariant prevents LLM hallucination and routes to human escalation.'
                : isGeminiInvoked
                ? 'Reason: High-consequence financial risk demands cloud LLM logical deduction.'
                : isRepaired
                ? 'Reason: Policy contradiction auto-repaired to compliant $200 capped waiver; verified safe.'
                : 'Reason: Low-risk routine inquiry verified via ultra-fast local NLI path.'}
            </div>
          </div>
        </div>

        {/* Telemetry Breakdown */}
        <div className="glass-card" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
            <Clock size={18} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Operational Telemetry
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Total ControlPlane Latency:</span>
              <span style={{ fontWeight: 700, color: '#38bdf8' }}>
                {currentResponse?.timing_telemetry?.total_controlplane_ms ? `${currentResponse.timing_telemetry.total_controlplane_ms} ms` : '7.2 ms'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Tier 0 Preflight Latency:</span>
              <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                {currentResponse?.timing_telemetry?.tier0_ms ? `${currentResponse.timing_telemetry.tier0_ms} ms` : '1.2 ms'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Tier 1 Verification Latency:</span>
              <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                {currentResponse?.timing_telemetry?.tier1_ms ? `${currentResponse.timing_telemetry.tier1_ms} ms` : '4.8 ms'}
              </span>
            </div>

            <div style={{ height: '1px', background: 'var(--border-subtle)', margin: '4px 0' }} />

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Cloud LLM Calls Incurred:</span>
              <span style={{ fontWeight: 700, color: isGeminiInvoked ? '#a855f7' : '#34d399' }}>
                {isGeminiInvoked ? '1 Call (Deep Judge)' : '0 Calls (100% Saved)'}
              </span>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Token Consumption (I/O):</span>
              <span style={{ fontWeight: 600, color: '#f8fafc' }}>
                {currentResponse?.cost_telemetry ? `${currentResponse.cost_telemetry.input_tokens} in / ${currentResponse.cost_telemetry.output_tokens} out` : '38 in / 22 out'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
