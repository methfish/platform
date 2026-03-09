export type OrderSide = 'buy' | 'sell';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type OrderStatus =
  | 'pending'
  | 'open'
  | 'partially_filled'
  | 'filled'
  | 'cancelled'
  | 'rejected'
  | 'expired';
export type TimeInForce = 'gtc' | 'ioc' | 'fok' | 'day';

export interface Order {
  id: string;
  client_order_id: string;
  exchange_order_id: string | null;
  symbol: string;
  side: string;
  order_type: string;
  status: string;
  quantity: number;
  filled_quantity: number;
  price: number | null;
  avg_fill_price: number | null;
  reject_reason: string | null;
  trading_mode: string;
  time_in_force: string;
  strategy_id: string | null;
  created_at: string;
  updated_at: string;
  fills: Fill[];
}

export interface OrdersResponse {
  orders: Order[];
  total: number;
}

export interface OrderCreateRequest {
  symbol: string;
  side: OrderSide;
  order_type: OrderType;
  quantity: number;
  price?: number;
  time_in_force?: TimeInForce;
}

export interface Fill {
  id: string;
  order_id: string;
  quantity: number;
  price: number;
  commission: number;
  fill_time: string;
}
