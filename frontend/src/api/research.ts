import client from './client';
import type {
  BacktestDetail,
  BacktestListItem,
  CollectionStatus,
  DataSummary,
  ResearchDashboard,
  StrategyEngineItem,
  StrategyRuntimeStatus,
  SweepResultItem,
} from '../types/research';

// --- Data Collection ---

export async function startCollection(params: {
  exchange?: string;
  symbols?: string[];
  intervals?: string[];
  limit?: number;
}): Promise<CollectionStatus> {
  const { data } = await client.post('/api/v1/research/collect', params);
  return data;
}

export async function fetchCollectionStatus(): Promise<CollectionStatus> {
  const { data } = await client.get('/api/v1/research/collect/status');
  return data;
}

export async function fetchDataSummary(): Promise<DataSummary> {
  const { data } = await client.get('/api/v1/research/data/summary');
  return data;
}

// --- Backtesting ---

export async function runBacktest(params: {
  strategy_type: string;
  symbol?: string;
  interval?: string;
  initial_capital?: number;
  cost_model?: string;
  strategy_params?: Record<string, unknown>;
  max_position_size?: number;
  stop_loss_pct?: number | null;
  take_profit_pct?: number | null;
}): Promise<BacktestDetail> {
  const { data } = await client.post('/api/v1/research/backtest', params);
  return data;
}

export async function fetchBacktests(params?: {
  limit?: number;
  strategy_type?: string;
  symbol?: string;
}): Promise<BacktestListItem[]> {
  const { data } = await client.get('/api/v1/research/backtests', { params });
  return data;
}

export async function fetchBacktestDetail(id: string): Promise<BacktestDetail> {
  const { data } = await client.get(`/api/v1/research/backtest/${id}`);
  return data;
}

// --- Parameter Sweep ---

export async function runSweep(params: {
  strategy_type: string;
  symbol?: string;
  interval?: string;
  param_grid: Record<string, unknown[]>;
}): Promise<{ strategy_type: string; symbol: string; total_combinations: number; results: SweepResultItem[] }> {
  const { data } = await client.post('/api/v1/research/sweep', params);
  return data;
}

// --- Dashboard ---

export async function fetchResearchDashboard(): Promise<ResearchDashboard> {
  const { data } = await client.get('/api/v1/research/dashboard');
  return data;
}

// --- Strategy Engine ---

export async function fetchStrategies(): Promise<StrategyEngineItem[]> {
  const { data } = await client.get('/api/v1/strategy-engine');
  return data;
}

export async function createStrategy(params: {
  name: string;
  strategy_type: string;
  trading_mode?: string;
  config_json: Record<string, unknown>;
}): Promise<StrategyEngineItem> {
  const { data } = await client.post('/api/v1/strategy-engine', params);
  return data;
}

export async function startStrategy(id: string): Promise<StrategyRuntimeStatus> {
  const { data } = await client.post(`/api/v1/strategy-engine/${id}/start`);
  return data;
}

export async function stopStrategy(id: string): Promise<StrategyRuntimeStatus> {
  const { data } = await client.post(`/api/v1/strategy-engine/${id}/stop`);
  return data;
}

export async function fetchStrategyStatus(id: string): Promise<StrategyRuntimeStatus> {
  const { data } = await client.get(`/api/v1/strategy-engine/${id}/status`);
  return data;
}
