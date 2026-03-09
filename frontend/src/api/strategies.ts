import client from './client';
import type { StrategyEngineItem, StrategyRuntimeStatus } from '../types/research';

export async function fetchStrategies(): Promise<StrategyEngineItem[]> {
  const { data } = await client.get<StrategyEngineItem[]>('/api/v1/strategy-engine');
  return data;
}

export async function createStrategy(params: {
  name: string;
  strategy_type: string;
  trading_mode?: string;
  config_json: Record<string, unknown>;
}): Promise<StrategyEngineItem> {
  const { data } = await client.post<StrategyEngineItem>('/api/v1/strategy-engine', params);
  return data;
}

export async function startStrategy(id: string): Promise<StrategyRuntimeStatus> {
  const { data } = await client.post<StrategyRuntimeStatus>(`/api/v1/strategy-engine/${id}/start`);
  return data;
}

export async function stopStrategy(id: string): Promise<StrategyRuntimeStatus> {
  const { data } = await client.post<StrategyRuntimeStatus>(`/api/v1/strategy-engine/${id}/stop`);
  return data;
}

export async function fetchStrategyStatus(id: string): Promise<StrategyRuntimeStatus> {
  const { data } = await client.get<StrategyRuntimeStatus>(`/api/v1/strategy-engine/${id}/status`);
  return data;
}
