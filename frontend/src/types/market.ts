export interface TickerResponse {
  symbol: string;
  exchange: string;
  last: number;
  bid: number;
  ask: number;
  volume_24h: number;
  change_percent_24h: number;
  timestamp: string;
}

export interface MoverEntry {
  symbol: string;
  price: number;
  change_percent_24h: number;
  volume_24h: number;
}

export interface SymbolAnalysisResponse {
  symbol: string;
  price: number;
  change_24h: number;
  volume_24h: number;
  trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  rsi_value: number;
  rsi_zone: string;
  volatility_score: number;
  momentum_score: number;
  volume_trend: string;
  signals: string[];
}

export interface OHLCVBarResponse {
  open_time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  close_time: string;
}

export interface HeatmapEntry {
  symbol: string;
  price: number;
  change_percent_24h: number;
  volume_24h: number;
  market_cap_rank: number;
}

export interface MarketOverview {
  total_symbols: number;
  total_volume_24h: number;
  btc_price: number;
  eth_price: number;
  top_gainers: MoverEntry[];
  top_losers: MoverEntry[];
  tickers: TickerResponse[];
}

export interface SymbolsResponse {
  symbols: SymbolAnalysisResponse[];
  total: number;
  page: number;
  page_size: number;
}

export interface MoversResponse {
  gainers: MoverEntry[];
  losers: MoverEntry[];
}

export interface ScreenerFilters {
  trend?: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  min_rsi?: number;
  max_rsi?: number;
  min_volume?: number;
  sort_by?: string;
  page?: number;
  page_size?: number;
}
