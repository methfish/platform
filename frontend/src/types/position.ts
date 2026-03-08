export interface Position {
  id: string;
  exchange: string;
  symbol: string;
  side: 'long' | 'short';
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  margin_used: number | null;
  leverage: number | null;
  liquidation_price: number | null;
  strategy_id: string | null;
  opened_at: string;
  updated_at: string;
}

export interface PositionsResponse {
  positions: Position[];
  total_unrealized_pnl: number;
  total_realized_pnl: number;
}

export interface PnLRecord {
  date: string;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  fees: number;
  trade_count: number;
}

export interface PnLResponse {
  records: PnLRecord[];
  total_realized: number;
  total_unrealized: number;
  total_fees: number;
}
