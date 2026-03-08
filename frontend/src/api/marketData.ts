import client from './client';
import { TickersResponse } from '../types/marketData';

export async function fetchTickers(): Promise<TickersResponse> {
  const { data } = await client.get<TickersResponse>('/api/v1/market-data/tickers');
  return data;
}
