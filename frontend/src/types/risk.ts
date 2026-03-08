export type TradingMode = 'paper' | 'live';

export interface RiskStatus {
  kill_switch_active: boolean;
  trading_mode: TradingMode;
  daily_loss: number;
  daily_loss_limit: number;
  max_position_size: number;
  current_max_position: number;
  max_order_size: number;
  open_orders_count: number;
  max_open_orders: number;
  margin_usage_percent: number;
  margin_limit_percent: number;
  daily_volume: number;
  daily_volume_limit: number;
  last_check_at: string;
}

export interface RiskEvent {
  id: string;
  type: 'warning' | 'breach' | 'kill_switch' | 'info';
  rule: string;
  message: string;
  details: Record<string, unknown>;
  timestamp: string;
  acknowledged: boolean;
}

export interface RiskEventsResponse {
  events: RiskEvent[];
  total: number;
}

export interface Strategy {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  exchange: string;
  symbols: string[];
  parameters: Record<string, unknown>;
  status: 'running' | 'stopped' | 'error' | 'paused';
  pnl: number;
  trade_count: number;
  last_trade_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface HealthStatus {
  status: string;
  version: string;
  uptime: number;
  components: Record<string, { status: string; latency_ms?: number }>;
}

export interface ExchangeStatus {
  exchange: string;
  connected: boolean;
  latency_ms: number;
  last_heartbeat: string;
  rate_limit_remaining: number;
}

export interface AuditLog {
  id: string;
  action: string;
  actor: string;
  details: Record<string, unknown>;
  ip_address: string;
  timestamp: string;
}

export interface ReconciliationRun {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  exchange: string;
  started_at: string;
  completed_at: string | null;
  discrepancies: number;
  details: Record<string, unknown> | null;
}

export interface TradingModeResponse {
  mode: TradingMode;
  live_enabled: boolean;
  operator_confirmed: boolean;
  kill_switch: boolean;
}
