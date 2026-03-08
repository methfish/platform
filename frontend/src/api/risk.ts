import client from './client';
import { RiskStatus, RiskEventsResponse } from '../types/risk';

export async function fetchRiskStatus(): Promise<RiskStatus> {
  const { data } = await client.get<RiskStatus>('/api/v1/risk/status');
  return data;
}

export async function toggleKillSwitch(activate: boolean): Promise<{ kill_switch_active: boolean }> {
  const { data } = await client.post<{ kill_switch_active: boolean }>('/api/v1/risk/kill-switch', {
    activate,
  });
  return data;
}

export async function fetchRiskEvents(params?: {
  type?: string;
  limit?: number;
  offset?: number;
}): Promise<RiskEventsResponse> {
  const { data } = await client.get<RiskEventsResponse>('/api/v1/risk/events', { params });
  return data;
}
