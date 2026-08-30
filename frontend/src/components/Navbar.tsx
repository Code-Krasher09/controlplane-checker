import React from 'react';
import { ShieldCheck, Activity, LayoutDashboard, Cpu, Sparkles } from 'lucide-react';
import type { ApiStatus } from '../services/api';

interface NavbarProps {
  currentView: 'trace' | 'control_room';
  onViewChange: (view: 'trace' | 'control_room') => void;
  apiStatus: ApiStatus;
  isDemoMode: boolean;
  onToggleDemoMode: () => void;
  selectedProfile: string;
  onProfileChange: (profile: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  currentView,
  onViewChange,
  apiStatus,
  isDemoMode,
  onToggleDemoMode,
  selectedProfile,
  onProfileChange,
}) => {
  return (
    <header style={{
      borderBottom: '1px solid var(--border-subtle)',
      background: 'rgba(9, 13, 22, 0.85)',
      backdropFilter: 'blur(16px)',
      position: 'sticky',
      top: 0,
      zIndex: 50,
      padding: '12px 24px',
    }}>
      <div style={{
        maxWidth: '1600px',
        margin: '0 auto',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        {/* Brand Logo & Tagline */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #38bdf8, #6366f1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 0 16px rgba(56, 189, 248, 0.4)',
          }}>
            <ShieldCheck size={22} color="#ffffff" />
          </div>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontSize: '1.125rem', fontWeight: 700, letterSpacing: '-0.02em', color: '#f8fafc' }}>
                ControlPlane Checker
              </span>
              <span style={{
                fontSize: '0.7rem',
                fontWeight: 600,
                padding: '2px 6px',
                borderRadius: '4px',
                background: 'rgba(56, 189, 248, 0.15)',
                color: '#38bdf8',
                border: '1px solid rgba(56, 189, 248, 0.3)',
              }}>
                V1.3 HYBRID
              </span>
            </div>
            <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Risk-Adaptive Enterprise AI Guardrails
            </div>
          </div>
        </div>

        {/* Primary View Switcher */}
        <div style={{
          display: 'flex',
          background: 'var(--bg-secondary)',
          padding: '4px',
          borderRadius: 'var(--radius-md)',
          border: '1px solid var(--border-subtle)',
          gap: '4px',
        }}>
          <button
            id="btn-view-trace"
            onClick={() => onViewChange('trace')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: 'none',
              transition: 'all 0.2s',
              background: currentView === 'trace' ? 'linear-gradient(135deg, #38bdf8, #6366f1)' : 'transparent',
              color: currentView === 'trace' ? '#ffffff' : 'var(--text-secondary)',
              boxShadow: currentView === 'trace' ? '0 2px 8px rgba(56, 189, 248, 0.25)' : 'none',
            }}
          >
            <Activity size={16} />
            Live Request Trace
          </button>
          <button
            id="btn-view-control-room"
            onClick={() => onViewChange('control_room')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 14px',
              borderRadius: 'var(--radius-sm)',
              fontSize: '0.85rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: 'none',
              transition: 'all 0.2s',
              background: currentView === 'control_room' ? 'linear-gradient(135deg, #38bdf8, #6366f1)' : 'transparent',
              color: currentView === 'control_room' ? '#ffffff' : 'var(--text-secondary)',
              boxShadow: currentView === 'control_room' ? '0 2px 8px rgba(56, 189, 248, 0.25)' : 'none',
            }}
          >
            <LayoutDashboard size={16} />
            Control Room (KPIs)
          </button>
        </div>

        {/* Status & Profile Controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {/* Application Profile Selector */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
            <Cpu size={14} />
            <select
              value={selectedProfile}
              onChange={(e) => onProfileChange(e.target.value)}
              style={{
                background: 'var(--bg-secondary)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-sm)',
                padding: '4px 8px',
                fontSize: '0.8rem',
                outline: 'none',
                cursor: 'pointer',
              }}
            >
              <option value="CUSTOMER_SUPPORT">Customer Support (Low/Med Risk)</option>
              <option value="DECISION_SUPPORT">Decision Support (High Consequence)</option>
              <option value="INTERNAL_KNOWLEDGE">Internal Knowledge Base</option>
            </select>
          </div>

          {/* Mode Switcher Badge */}
          <button
            onClick={onToggleDemoMode}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 600,
              cursor: 'pointer',
              border: isDemoMode ? '1px solid rgba(245, 158, 11, 0.4)' : '1px solid rgba(16, 185, 129, 0.4)',
              background: isDemoMode ? 'rgba(245, 158, 11, 0.12)' : 'rgba(16, 185, 129, 0.12)',
              color: isDemoMode ? '#fbbf24' : '#34d399',
            }}
          >
            <Sparkles size={13} />
            {isDemoMode ? 'Deterministic Demo Mode' : 'Live API Active'}
          </button>

          {/* Backend Status Dot */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '0.75rem',
            color: apiStatus.isOnline ? '#34d399' : '#94a3b8',
          }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: apiStatus.isOnline ? '#10b981' : '#64748b',
              boxShadow: apiStatus.isOnline ? '0 0 8px #10b981' : 'none',
            }} />
            {apiStatus.isOnline ? 'Backend 8000 Online' : 'Backend Offline (Demo Fallback)'}
          </div>
        </div>
      </div>
    </header>
  );
};
