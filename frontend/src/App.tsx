import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { LiveTraceView } from './components/LiveTraceView';
import { ControlRoomView } from './components/ControlRoomView';
import type { GatewayInspectResponse, InspectRequestPayload, DemoScenario } from './types';
import { DEMO_SCENARIOS } from './data/demoScenarios';
import { checkBackendHealth, inspectRequest } from './services/api';
import type { ApiStatus } from './services/api';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<'trace' | 'control_room'>('trace');
  const [apiStatus, setApiStatus] = useState<ApiStatus>({ isOnline: false });
  const [isDemoMode, setIsDemoMode] = useState<boolean>(true);
  const [selectedProfile, setSelectedProfile] = useState<string>('CUSTOMER_SUPPORT');
  const [activeScenarioId, setActiveScenarioId] = useState<string | null>('safe-fast-path');
  const [currentResponse, setCurrentResponse] = useState<GatewayInspectResponse | null>(DEMO_SCENARIOS[0].mockResponse);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  useEffect(() => {
    // Check backend health on mount and periodically
    const pollHealth = async () => {
      const status = await checkBackendHealth();
      setApiStatus(status);
      if (status.isOnline) {
        setIsDemoMode(false);
      }
    };
    pollHealth();
    const interval = setInterval(pollHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectScenario = (scenario: DemoScenario) => {
    setActiveScenarioId(scenario.id);
    setCurrentResponse(scenario.mockResponse);
    if (scenario.payload.application_id === '33333333-3333-3333-3333-333333333333') {
      setSelectedProfile('DECISION_SUPPORT');
    } else if (scenario.payload.application_id === '22222222-2222-2222-2222-222222222222') {
      setSelectedProfile('INTERNAL_KNOWLEDGE');
    } else {
      setSelectedProfile('CUSTOMER_SUPPORT');
    }
  };

  const handleRunInspect = async (payload: InspectRequestPayload) => {
    setIsLoading(true);
    try {
      const { response, isDemo } = await inspectRequest(payload, isDemoMode);
      setCurrentResponse(response);
      if (isDemo) {
        setIsDemoMode(true);
      }
    } catch (error) {
      console.error('Inspection failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSelectTraceFromControlRoom = (scenarioId: string) => {
    const matched = DEMO_SCENARIOS.find((s) => s.id === scenarioId);
    if (matched) {
      handleSelectScenario(matched);
      setCurrentView('trace');
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-primary)', display: 'flex', flexDirection: 'column' }}>
      <Navbar
        currentView={currentView}
        onViewChange={setCurrentView}
        apiStatus={apiStatus}
        isDemoMode={isDemoMode}
        onToggleDemoMode={() => setIsDemoMode(!isDemoMode)}
        selectedProfile={selectedProfile}
        onProfileChange={setSelectedProfile}
      />

      <main style={{ flex: 1 }}>
        {currentView === 'trace' ? (
          <LiveTraceView
            onRunInspect={handleRunInspect}
            currentResponse={currentResponse}
            isLoading={isLoading}
            activeScenarioId={activeScenarioId}
            onSelectScenario={handleSelectScenario}
            selectedProfile={selectedProfile}
          />
        ) : (
          <ControlRoomView onSelectTrace={handleSelectTraceFromControlRoom} />
        )}
      </main>

      {/* Footer Disclaimer */}
      <footer style={{
        borderTop: '1px solid var(--border-subtle)',
        padding: '16px 24px',
        textAlign: 'center',
        fontSize: '0.75rem',
        color: 'var(--text-muted)',
      }}>
        ControlPlane Checker Prototype V1.3 • High-Severity Selective Gemini Hybrid Architecture • Tested across 130 regression benchmarks
      </footer>
    </div>
  );
};

export default App;
