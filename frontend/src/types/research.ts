// Research & Backtest types

export interface DatasetInfo {
  symbol: string;
  interval: string;
  bar_count: number;
  earliest: string | null;
  latest: string | null;
}

export interface DataSummary {
  datasets: DatasetInfo[];
  total_bars: number;
}

export interface CollectionStatus {
  job_id: string;
  exchange: string;
  status: string;
  symbols_total: number;
  symbols_done: number;
  bars_inserted: number;
  bars_skipped: number;
  errors: string[];
  progress_pct: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface BacktestListItem {
  id: string;
  strategy_type: string;
  symbol: string;
  interval: string;
  status: string;
  total_trades: number;
  net_pnl: string;
  sharpe_ratio: string;
  max_drawdown_pct: string;
  win_rate: string;
  is_trustworthy: boolean;
  created_at: string;
}

export interface EquityCurvePoint {
  t: string;
  eq: string;
  dd: number;
}

export interface BacktestMetrics {
  strategy_name: string;
  symbol: string;
  period_start: string | null;
  period_end: string | null;
  total_net_pnl: string;
  total_gross_pnl: string;
  total_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown: string;
  max_drawdown_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  expectancy: string;
  expectancy_ratio: number;
  avg_win: string;
  avg_loss: string;
  avg_holding_time_minutes: number;
  total_commission: string;
  total_slippage: string;
  fee_drag_pct: number;
  total_volume: string;
  trades_per_day: number;
  initial_capital: string;
  final_equity: string;
  capital_utilization_pct: number;
  is_trustworthy: boolean;
  trust_issues: string[];
  equity_curve: Array<{ timestamp: string; equity: string; drawdown_pct: number }>;
}

export interface BacktestDetail {
  id: string;
  strategy_type: string;
  symbol: string;
  interval: string;
  status: string;
  strategy_params: Record<string, unknown>;
  cost_model: string;
  initial_capital: string;
  total_trades: number;
  total_bars: number;
  metrics: BacktestMetrics | null;
  equity_curve: EquityCurvePoint[] | null;
  is_trustworthy: boolean;
  trust_issues: string[] | null;
  error: string | null;
  created_at: string;
}

export interface SweepResultItem {
  params: Record<string, unknown>;
  sharpe_ratio: number;
  net_pnl: string;
  max_drawdown_pct: number;
  win_rate: number;
  total_trades: number;
  profit_factor: number;
  rank_score: number;
  is_trustworthy: boolean;
}

export interface ResearchDashboard {
  data_summary: DataSummary;
  active_strategies: number;
  total_backtests: number;
  best_sharpe: { strategy_type: string; symbol: string; sharpe: string; net_pnl: string } | null;
  worst_drawdown: { strategy_type: string; symbol: string; drawdown: string } | null;
  recent_backtests: BacktestListItem[];
  live_strategy_pnl: Record<string, string>;
}

export interface StrategyEngineItem {
  id: string;
  name: string;
  description: string | null;
  strategy_type: string;
  status: string;
  trading_mode: string;
  config_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface StrategyRuntimeStatus {
  name: string;
  status: string;
  strategy_type: string;
  uptime_seconds: number | null;
  ticks_processed: number;
  orders_submitted: number;
  orders_filled: number;
  active_orders: number;
  current_inventory: Record<string, string>;
  pnl: {
    strategy_name: string;
    realized_pnl: string;
    unrealized_pnl: string;
    net_pnl: string;
    total_trades: number;
    winning_trades: number;
    losing_trades: number;
    win_rate: number;
    total_volume: string;
    total_commission: string;
    pnl_per_trade: string;
    start_time: string;
  };
}
