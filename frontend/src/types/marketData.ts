export interface Ticker {
  symbol: string;
  exchange: string;
  bid: number;
  ask: number;
  last: number;
  volume_24h: number;
  change_24h: number;
  change_percent_24h: number;
  high_24h: number;
  low_24h: number;
  timestamp: string;
}

export interface TickersResponse {
  tickers: Ticker[];
}

export interface WebSocketMessage {
  type: string;
  channel: string;
  data: unknown;
  timestamp: string;
}
