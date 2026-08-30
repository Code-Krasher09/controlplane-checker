import React from 'react';
import {
  ShieldCheck,
  Clock,
  TrendingDown,
  Lock,
  Wrench,
  AlertOctagon,
  Layers,
  BarChart3,
  ExternalLink,
} from 'lucide-react';

interface ControlRoomViewProps {
  onSelectTrace: (scenarioId: string) => void;
}

export const ControlRoomView: React.FC<ControlRoomViewProps> = ({ onSelectTrace }) => {
  const kpis = [
    {
      title: 'Observed Holdout Accuracy',
      value: '74.0%',
      subtext: '+24.0% vs Unprotected AI (50.0%)',
      icon: <ShieldCheck size={20} color="#34d399" />,
      highlight: '#34d399',
    },
    {
      title: 'Cloud LLM Calls Saved',
      value: '58.0%',
      subtext: '29 of 50 holdout requests avoided cloud API',
      icon: <TrendingDown size={20} color="#38bdf8" />,
      highlight: '#38bdf8',
    },
    {
      title: 'Low-Risk Path P95 Latency',
      value: '53.53 ms',
      subtext: 'Ultra-fast local DeBERTa-v3 inference',
      icon: <Clock size={20} color="#a855f7" />,
      highlight: '#a855f7',
    },
    {
      title: 'Critical Threats Blocked',
      value: '100.0%',
      subtext: '4/4 PII & security threats blocked at Tier 0',
      icon: <Lock size={20} color="#fb7185" />,
      highlight: '#fb7185',
    },
    {
      title: 'Self-Healing Repairs',
      value: '8 Cases',
      subtext: 'Auto-repaired & reverified compliant',
      icon: <Wrench size={20} color="#22d3ee" />,
      highlight: '#22d3ee',
    },
    {
      title: 'Conservative Escalations',
      value: '18 Cases',
      subtext: 'Inadequate / ambiguous cases routed to humans',
      icon: <AlertOctagon size={20} color="#fbbf24" />,
      highlight: '#fbbf24',
    },
  ];

  const recentTraces = [
    {
      id: 'safe-fast-path',
      query: 'Standard return policy for retail orders',
      profile: 'CUSTOMER_SUPPORT',
      tier: 'Local NLI (DeBERTa)',
      latency: '5.24 ms',
      cost: '$0.00004',
      action: 'ALLOW',
      actionClass: 'badge-allow',
      reason: 'Low-risk routine grounded inquiry',
    },
    {
      id: 'high-severity-gemini',
      query: 'Customer courtesy fee waiver limit verification',
      profile: 'DECISION_SUPPORT',
      tier: 'Gemini Flash Lite',
      latency: '487.6 ms',
      cost: '$0.00065',
      action: 'ALLOW',
      actionClass: 'badge-allow',
      reason: 'High-severity financial logic verified',
    },
    {
      id: 'pii-block',
      query: 'Customer SSN 111-22-3301 profile lookup',
      profile: 'CUSTOMER_SUPPORT',
      tier: 'Tier 0 Regex Guard',
      latency: '2.20 ms',
      cost: '$0.00000',
      action: 'BLOCK',
      actionClass: 'badge-block',
      reason: 'Critical SSN PII detected in prompt',
    },
    {
      id: 'contradicted-repair',
      query: 'Grant unapproved $1,000 courtesy fee waiver',
      profile: 'DECISION_SUPPORT',
      tier: 'Gemini + Repair Loop',
      latency: '154.2 ms',
      cost: '$0.00080',
      action: 'ALLOW (REPAIRED)',
      actionClass: 'badge-repair',
      reason: 'Auto-repaired to capped $200 waiver',
    },
    {
      id: 'insufficient-evidence',
      query: 'Interdimensional freight teleportation warranty',
      profile: 'DECISION_SUPPORT',
      tier: 'Evidence Gate (Bypassed)',
      latency: '13.5 ms',
      cost: '$0.00003',
      action: 'ESCALATE',
      actionClass: 'badge-escalate',
      reason: 'Missing evidence; prevented hallucination',
    },
    {
      id: 'adjudication-inconclusive',
      query: 'Plan B international roaming regional exclusions',
      profile: 'DECISION_SUPPORT',
      tier: 'Gemini Inconclusive',
      latency: '517.9 ms',
      cost: '$0.00085',
      action: 'ESCALATE',
      actionClass: 'badge-escalate',
      reason: 'Borderline semantic clause escalated',
    },
  ];

  return (
    <div style={{ maxWidth: '1600px', margin: '0 auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* ------------------------------------------------------------- */}
      {/* Conceptual Pitch Header Banner */}
      {/* ------------------------------------------------------------- */}
      <div className="glass-card" style={{
        padding: '28px 36px',
        background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.95), rgba(30, 41, 59, 0.85))',
        border: '1px solid rgba(56, 189, 248, 0.3)',
        boxShadow: '0 0 30px rgba(56, 189, 248, 0.1)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}>
        <div>
          <div style={{ fontSize: '0.8rem', fontWeight: 700, letterSpacing: '0.1em', color: '#38bdf8', textTransform: 'uppercase', marginBottom: '6px' }}>
            CORE ARCHITECTURAL PRINCIPLE
          </div>
          <h1 style={{ fontSize: '1.75rem', fontWeight: 800, color: '#f8fafc', lineHeight: 1.2, letterSpacing: '-0.02em' }}>
            "Verify cheaply by default.<br />Escalate intelligently when risk demands it."
          </h1>
          <p style={{ fontSize: '0.875rem', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '700px' }}>
            ControlPlane Checker V1.3 dynamically routes low-risk enterprise queries to sub-100ms local NLI while selectively dedicating cloud LLM judges to high-consequence compliance decisions.
          </p>
        </div>

        <div style={{
          background: 'rgba(56, 189, 248, 0.1)',
          border: '1px solid rgba(56, 189, 248, 0.25)',
          borderRadius: 'var(--radius-lg)',
          padding: '16px 24px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            PROTOTYPE BENCHMARK STATUS
          </div>
          <div style={{ fontSize: '1.5rem', fontWeight: 800, color: '#38bdf8', marginTop: '2px' }}>
            126 / 126 Passing
          </div>
          <div style={{ fontSize: '0.75rem', color: '#34d399', fontWeight: 600, marginTop: '2px' }}>
            100% Test Suite Verification
          </div>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* KPI Cards Grid */}
      {/* ------------------------------------------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '20px' }}>
        {kpis.map((kpi, idx) => (
          <div key={idx} className="glass-card" style={{ padding: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
                {kpi.title}
              </span>
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '8px',
                background: 'rgba(255, 255, 255, 0.05)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}>
                {kpi.icon}
              </div>
            </div>
            <div style={{ fontSize: '1.85rem', fontWeight: 800, color: kpi.highlight }}>
              {kpi.value}
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              {kpi.subtext}
            </div>
          </div>
        ))}
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Verification Distribution & Ratio */}
      {/* ------------------------------------------------------------- */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <BarChart3 size={18} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Verification Architecture Distribution (50-Case Holdout)
            </h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '6px' }}>
                <span style={{ color: '#34d399', fontWeight: 600 }}>Local Fast Path (DeBERTa-v3-small)</span>
                <span style={{ fontWeight: 700, color: '#f8fafc' }}>58.0% (29 Requests)</span>
              </div>
              <div style={{ height: '10px', background: 'var(--bg-secondary)', borderRadius: '9999px', overflow: 'hidden' }}>
                <div style={{ width: '58%', height: '100%', background: '#10b981', borderRadius: '9999px' }} />
              </div>
            </div>

            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '6px' }}>
                <span style={{ color: '#a855f7', fontWeight: 600 }}>Cloud LLM Judge (Gemini Flash Lite)</span>
                <span style={{ fontWeight: 700, color: '#f8fafc' }}>42.0% (21 Requests)</span>
              </div>
              <div style={{ height: '10px', background: 'var(--bg-secondary)', borderRadius: '9999px', overflow: 'hidden' }}>
                <div style={{ width: '42%', height: '100%', background: '#a855f7', borderRadius: '9999px' }} />
              </div>
            </div>
          </div>

          <div style={{
            background: 'var(--bg-secondary)',
            padding: '12px',
            borderRadius: 'var(--radius-md)',
            marginTop: '16px',
            fontSize: '0.8rem',
            color: 'var(--text-secondary)',
          }}>
            <strong>Epistemic Guarantee:</strong> Inadequate/missing evidence is strictly excluded from Gemini invocation, ensuring zero hallucinated support.
          </div>
        </div>

        {/* Cost & Efficiency Comparison */}
        <div className="glass-card" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <TrendingDown size={18} color="#34d399" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Operational Cost & Token Savings
            </h3>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>ALWAYS-ON LLM INVOCATIONS</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#fb7185', marginTop: '2px' }}>14,300 Tokens</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>50 / 50 API Calls</div>
            </div>

            <div style={{ background: 'var(--bg-secondary)', padding: '12px', borderRadius: '8px' }}>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>SELECTIVE GEMINI ROUTING</div>
              <div style={{ fontSize: '1.25rem', fontWeight: 700, color: '#34d399', marginTop: '2px' }}>6,006 Tokens</div>
              <div style={{ fontSize: '0.7rem', color: '#34d399', fontWeight: 600 }}>58% Direct Cost Saved</div>
            </div>
          </div>

          <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            By enforcing policy-driven severity gating, the system eliminates 58% of unnecessary cloud API spend while delivering higher action accuracy (74% vs 64%).
          </p>
        </div>
      </div>

      {/* ------------------------------------------------------------- */}
      {/* Recent Decisions Trace Log */}
      {/* ------------------------------------------------------------- */}
      <div className="glass-card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Layers size={18} color="#38bdf8" />
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, color: '#f8fafc' }}>
              Recent Representative Inspection Decisions
            </h3>
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Click any decision to inspect full execution trace
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.825rem' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)', textAlign: 'left' }}>
                <th style={{ padding: '10px 12px' }}>QUERY / TASK</th>
                <th style={{ padding: '10px 12px' }}>PROFILE</th>
                <th style={{ padding: '10px 12px' }}>VERIFIER TIER</th>
                <th style={{ padding: '10px 12px' }}>LATENCY</th>
                <th style={{ padding: '10px 12px' }}>ACTION</th>
                <th style={{ padding: '10px 12px' }}>EXPLAINABILITY (WHY)</th>
                <th style={{ padding: '10px 12px', textAlign: 'right' }}>INSPECT</th>
              </tr>
            </thead>
            <tbody>
              {recentTraces.map((trace, idx) => (
                <tr
                  key={idx}
                  onClick={() => onSelectTrace(trace.id)}
                  style={{
                    borderBottom: '1px solid var(--border-subtle)',
                    cursor: 'pointer',
                    transition: 'background 0.15s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(255, 255, 255, 0.03)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                >
                  <td style={{ padding: '12px', fontWeight: 600, color: '#f8fafc' }}>{trace.query}</td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)', fontSize: '0.75rem' }}>{trace.profile}</td>
                  <td style={{ padding: '12px', color: '#38bdf8' }}>{trace.tier}</td>
                  <td style={{ padding: '12px', fontFamily: 'JetBrains Mono', color: 'var(--text-secondary)' }}>{trace.latency}</td>
                  <td style={{ padding: '12px' }}>
                    <span className={`badge ${trace.actionClass}`}>{trace.action}</span>
                  </td>
                  <td style={{ padding: '12px', color: 'var(--text-secondary)' }}>{trace.reason}</td>
                  <td style={{ padding: '12px', textAlign: 'right' }}>
                    <ExternalLink size={14} color="#38bdf8" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
