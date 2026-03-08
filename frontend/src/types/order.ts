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
  exchange: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  status: OrderStatus;
  quantity: number;
  filled_quantity: number;
  price: number | null;
  average_fill_price: number | null;
  stop_price: number | null;
  time_in_force: TimeInForce;
  strategy_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface OrdersResponse {
  orders: Order[];
  total: number;
}

export interface OrderCreateRequest {
  exchange: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price?: number;
  stop_price?: number;
  time_in_force?: TimeInForce;
}

export interface Fill {
  id: string;
  order_id: string;
  exchange: string;
  symbol: string;
  side: OrderSide;
  price: number;
  quantity: number;
  fee: number;
  fee_currency: string;
  timestamp: string;
}

export interface FillsResponse {
  fills: Fill[];
  total: number;
}
