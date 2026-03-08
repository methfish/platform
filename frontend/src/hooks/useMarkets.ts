import { useQuery } from '@tanstack/react-query';
import {
  fetchMarketOverview,
  fetchSymbols,
  fetchSymbolDetail,
  fetchOHLCV,
  fetchHeatmap,
  fetchMovers,
} from '../api/markets';
import { ScreenerFilters } from '../types/market';

export function useMarketOverview() {
  return useQuery({
    queryKey: ['marketOverview'],
    queryFn: fetchMarketOverview,
    refetchInterval: 30000,
  });
}

export function useSymbols(filters: ScreenerFilters) {
  return useQuery({
    queryKey: ['symbols', filters],
    queryFn: () => fetchSymbols(filters),
    refetchInterval: 60000,
  });
}

export function useSymbolDetail(symbol: string) {
  return useQuery({
    queryKey: ['symbolDetail', symbol],
    queryFn: () => fetchSymbolDetail(symbol),
    enabled: !!symbol,
  });
}

export function useOHLCV(symbol: string, interval: string) {
  return useQuery({
    queryKey: ['ohlcv', symbol, interval],
    queryFn: () => fetchOHLCV(symbol, interval),
    enabled: !!symbol,
  });
}

export function useHeatmap() {
  return useQuery({
    queryKey: ['heatmap'],
    queryFn: fetchHeatmap,
    refetchInterval: 30000,
  });
}

export function useMovers() {
  return useQuery({
    queryKey: ['movers'],
    queryFn: fetchMovers,
    refetchInterval: 30000,
  });
}
