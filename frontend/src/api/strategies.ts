import client from './client';
import { Strategy } from '../types/risk';

export async function fetchStrategies(): Promise<Strategy[]> {
  const { data } = await client.get<Strategy[]>('/api/v1/strategies');
  return data;
}

export async function enableStrategy(id: string): Promise<Strategy> {
  const { data } = await client.post<Strategy>(`/api/v1/strategies/${id}/enable`);
  return data;
}

export async function disableStrategy(id: string): Promise<Strategy> {
  const { data } = await client.post<Strategy>(`/api/v1/strategies/${id}/disable`);
  return data;
}
