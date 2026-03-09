import client from './client';
import {
  HealthStatus,
  ExchangeStatus,
  AuditLog,
  ReconciliationRun,
  TradingModeResponse,
} from '../types/risk';

export async function login(username: string, password: string): Promise<{ access_token: string; token_type: string }> {
  const { data } = await client.post<{ access_token: string; token_type: string }>(
    '/api/v1/auth/login',
    { username, password },
  );
  return data;
}

export async function fetchHealth(): Promise<HealthStatus> {
  const { data } = await client.get<HealthStatus>('/api/v1/health');
  return data;
}

export async function fetchExchangeStatus(): Promise<ExchangeStatus[]> {
  const { data } = await client.get<{ exchanges: ExchangeStatus[] }>('/api/v1/exchanges/status');
  return data.exchanges ?? [];
}

export async function fetchTradingMode(): Promise<TradingModeResponse> {
  const { data } = await client.get<TradingModeResponse>('/api/v1/admin/trading-mode');
  return data;
}

export async function confirmLiveMode(): Promise<TradingModeResponse> {
  const { data } = await client.post<TradingModeResponse>('/api/v1/admin/live-mode-confirm');
  return data;
}

export async function fetchAuditLogs(params?: {
  limit?: number;
  offset?: number;
}): Promise<AuditLog[]> {
  const { data } = await client.get<AuditLog[]>('/api/v1/audit-logs', { params });
  return data;
}

export async function fetchReconciliationRuns(): Promise<ReconciliationRun[]> {
  const { data } = await client.get<ReconciliationRun[]>('/api/v1/reconciliation/runs');
  return data;
}

export async function triggerReconciliation(): Promise<ReconciliationRun> {
  const { data } = await client.post<ReconciliationRun>('/api/v1/reconciliation/run');
  return data;
}
