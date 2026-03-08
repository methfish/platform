import client from './client';
import { PositionsResponse, PnLResponse } from '../types/position';

export async function fetchPositions(): Promise<PositionsResponse> {
  const { data } = await client.get<PositionsResponse>('/api/v1/positions');
  return data;
}

export async function fetchPnL(params?: {
  start_date?: string;
  end_date?: string;
}): Promise<PnLResponse> {
  const { data } = await client.get<PnLResponse>('/api/v1/pnl', { params });
  return data;
}
