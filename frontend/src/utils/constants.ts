export const ORDER_STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  pending: { bg: 'bg-yellow-500/15', text: 'text-yellow-400' },
  open: { bg: 'bg-blue-500/15', text: 'text-blue-400' },
  partially_filled: { bg: 'bg-indigo-500/15', text: 'text-indigo-400' },
  filled: { bg: 'bg-green-500/15', text: 'text-green-400' },
  cancelled: { bg: 'bg-gray-500/15', text: 'text-gray-400' },
  rejected: { bg: 'bg-red-500/15', text: 'text-red-400' },
  expired: { bg: 'bg-gray-500/15', text: 'text-gray-500' },
};

export const ORDER_STATUS_LABELS: Record<string, string> = {
  pending: 'Pending',
  open: 'Open',
  partially_filled: 'Partial Fill',
  filled: 'Filled',
  cancelled: 'Cancelled',
  rejected: 'Rejected',
  expired: 'Expired',
};

export const SIDE_COLORS: Record<string, { bg: string; text: string }> = {
  buy: { bg: 'bg-green-500/15', text: 'text-green-400' },
  sell: { bg: 'bg-red-500/15', text: 'text-red-400' },
  long: { bg: 'bg-green-500/15', text: 'text-green-400' },
  short: { bg: 'bg-red-500/15', text: 'text-red-400' },
};

export const STRATEGY_STATUS_COLORS: Record<string, { bg: string; text: string; dot: string }> = {
  running: { bg: 'bg-green-500/15', text: 'text-green-400', dot: 'bg-green-400' },
  stopped: { bg: 'bg-gray-500/15', text: 'text-gray-400', dot: 'bg-gray-400' },
  error: { bg: 'bg-red-500/15', text: 'text-red-400', dot: 'bg-red-400' },
  paused: { bg: 'bg-yellow-500/15', text: 'text-yellow-400', dot: 'bg-yellow-400' },
};

export const RISK_EVENT_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  info: { bg: 'bg-blue-500/10', text: 'text-blue-400', border: 'border-blue-500/30' },
  warning: { bg: 'bg-yellow-500/10', text: 'text-yellow-400', border: 'border-yellow-500/30' },
  breach: { bg: 'bg-red-500/10', text: 'text-red-400', border: 'border-red-500/30' },
  kill_switch: { bg: 'bg-red-500/20', text: 'text-red-300', border: 'border-red-500/50' },
};

export const EXCHANGES = ['binance', 'coinbase', 'kraken', 'bybit'];
export const ORDER_TYPES = ['market', 'limit', 'stop', 'stop_limit'] as const;
export const ORDER_SIDES = ['buy', 'sell'] as const;
export const TIME_IN_FORCES = ['gtc', 'ioc', 'fok', 'day'] as const;

export const REFETCH_INTERVALS = {
  fast: 5000,
  normal: 10000,
  slow: 30000,
} as const;
