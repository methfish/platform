import client from './client';
import {
  MarketOverview,
  SymbolsResponse,
  SymbolAnalysisResponse,
  OHLCVBarResponse,
  HeatmapEntry,
  MoversResponse,
  ScreenerFilters,
} from '../types/market';

export async function fetchMarketOverview(): Promise<MarketOverview> {
  const { data } = await client.get<MarketOverview>('/api/v1/markets/overview');
  return data;
}

export async function fetchSymbols(filters?: ScreenerFilters): Promise<SymbolsResponse> {
  const params: Record<string, string | number> = {};

  if (filters?.trend) params.trend = filters.trend;
  if (filters?.min_rsi !== undefined) params.min_rsi = filters.min_rsi;
  if (filters?.max_rsi !== undefined) params.max_rsi = filters.max_rsi;
  if (filters?.min_volume !== undefined) params.min_volume = filters.min_volume;
  if (filters?.sort_by) params.sort_by = filters.sort_by;
  if (filters?.page !== undefined) params.page = filters.page;
  if (filters?.page_size !== undefined) params.page_size = filters.page_size;

  const { data } = await client.get<SymbolsResponse>('/api/v1/markets/symbols', { params });
  return data;
}

export async function fetchSymbolDetail(symbol: string): Promise<SymbolAnalysisResponse> {
  const { data } = await client.get<SymbolAnalysisResponse>(`/api/v1/markets/symbols/${symbol}`);
  return data;
}

export async function fetchOHLCV(
  symbol: string,
  interval: string = '1h',
  limit: number = 100,
): Promise<OHLCVBarResponse[]> {
  const { data } = await client.get<OHLCVBarResponse[]>(
    `/api/v1/markets/symbols/${symbol}/ohlcv`,
    { params: { interval, limit } },
  );
  return data;
}

export async function fetchHeatmap(): Promise<HeatmapEntry[]> {
  const { data } = await client.get<HeatmapEntry[]>('/api/v1/markets/heatmap');
  return data;
}

export async function fetchMovers(): Promise<MoversResponse> {
  const { data } = await client.get<MoversResponse>('/api/v1/markets/movers');
  return data;
}
