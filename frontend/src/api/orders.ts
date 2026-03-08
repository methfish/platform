import client from './client';
import { OrdersResponse, OrderCreateRequest, Order, FillsResponse } from '../types/order';

export async function fetchOrders(params?: {
  status?: string;
  symbol?: string;
  limit?: number;
  offset?: number;
}): Promise<OrdersResponse> {
  const { data } = await client.get<OrdersResponse>('/api/v1/orders', { params });
  return data;
}

export async function createOrder(order: OrderCreateRequest): Promise<Order> {
  const { data } = await client.post<Order>('/api/v1/orders', order);
  return data;
}

export async function cancelOrder(orderId: string): Promise<void> {
  await client.post(`/api/v1/orders/${orderId}/cancel`);
}

export async function fetchFills(params?: {
  order_id?: string;
  symbol?: string;
  limit?: number;
  offset?: number;
}): Promise<FillsResponse> {
  const { data } = await client.get<FillsResponse>('/api/v1/fills', { params });
  return data;
}
