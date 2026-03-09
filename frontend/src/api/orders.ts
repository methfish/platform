import client from './client';
import { OrdersResponse, OrderCreateRequest, Order, Fill } from '../types/order';

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
  const payload = {
    symbol: order.symbol,
    side: order.side.toUpperCase(),
    order_type: order.order_type.toUpperCase(),
    quantity: order.quantity,
    price: order.price,
    time_in_force: (order.time_in_force || 'gtc').toUpperCase(),
  };
  const { data } = await client.post<Order>('/api/v1/orders', payload);
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
}): Promise<Fill[]> {
  const { data } = await client.get<Fill[]>('/api/v1/fills', { params });
  return data;
}
