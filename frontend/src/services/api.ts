import type { GatewayInspectResponse, InspectRequestPayload } from '../types';
import { DEMO_SCENARIOS } from '../data/demoScenarios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ApiStatus {
  isOnline: boolean;
  version?: string;
  env?: string;
}

export async function checkBackendHealth(): Promise<ApiStatus> {
  try {
    const res = await fetch(`${API_BASE_URL}/health`, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      signal: AbortSignal.timeout(2000),
    });
    if (res.ok) {
      const data = await res.json();
      return { isOnline: true, version: data.version, env: data.environment };
    }
    return { isOnline: false };
  } catch {
    return { isOnline: false };
  }
}

export async function inspectRequest(
  payload: InspectRequestPayload,
  forceDemoMode: boolean = false
): Promise<{ response: GatewayInspectResponse; isDemo: boolean }> {
  // If explicitly in Demo Mode or payload matches a specific scenario
  if (forceDemoMode) {
    const matched = DEMO_SCENARIOS.find((s) => s.payload.prompt === payload.prompt || s.payload.scenario === payload.scenario);
    if (matched) {
      // Simulate real micro-latency for UX
      await new Promise((r) => setTimeout(r, matched.mockResponse.timing_telemetry.total_controlplane_ms > 100 ? 500 : 150));
      return { response: matched.mockResponse, isDemo: true };
    }
  }

  try {
    const res = await fetch(`${API_BASE_URL}/inspect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: AbortSignal.timeout(15000),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(errData.detail || `Server responded with ${res.status}`);
    }

    const data: GatewayInspectResponse = await res.json();
    return { response: data, isDemo: false };
  } catch (err: any) {
    console.warn('Backend /inspect call failed or offline, falling back to deterministic demo response:', err);
    // Graceful fallback to matching demo scenario
    const matched = DEMO_SCENARIOS.find((s) => s.payload.prompt === payload.prompt || s.payload.scenario === payload.scenario) || DEMO_SCENARIOS[0];
    return { response: matched.mockResponse, isDemo: true };
  }
}
