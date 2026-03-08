import { useQuery } from '@tanstack/react-query';
import { fetchPositions, fetchPnL } from '../api/positions';

export function usePositions() {
  return useQuery({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 5000,
  });
}

export function usePnL(params?: { start_date?: string; end_date?: string }) {
  return useQuery({
    queryKey: ['pnl', params],
    queryFn: () => fetchPnL(params),
    refetchInterval: 10000,
  });
}
