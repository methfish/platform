import { Loader2, BarChart3, Activity, TrendingUp, TrendingDown } from 'lucide-react';
import { useMarketOverview } from '../../hooks/useMarkets';
import { formatCurrency, formatNumber } from '../../utils/formatters';
import { MoverEntry } from '../../types/market';

export default function MarketOverview() {
  const { data, isLoading } = useMarketOverview();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-5 w-5 text-accent animate-spin" />
        <span className="ml-3 text-gray-400 text-sm">Loading market data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">Total Volume 24h</span>
            <div className="p-1.5 rounded-lg bg-accent/10">
              <BarChart3 className="h-4 w-4 text-accent" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-gray-100">
            {data ? formatCurrency(data.total_volume_24h) : '...'}
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">BTC Price</span>
            <div className="p-1.5 rounded-lg bg-yellow-500/10">
              <Activity className="h-4 w-4 text-yellow-400" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-gray-100">
            {data ? formatCurrency(data.btc_price) : '...'}
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">ETH Price</span>
            <div className="p-1.5 rounded-lg bg-blue-500/10">
              <Activity className="h-4 w-4 text-blue-400" />
            </div>
          </div>
          <p className="text-xl font-bold font-mono text-gray-100">
            {data ? formatCurrency(data.eth_price) : '...'}
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">Active Symbols</span>
            <div className="p-1.5 rounded-lg bg-green-500/10">
              <BarChart3 className="h-4 w-4 text-profit" />
            </div>
          </div>
          <p className="text-xl font-bold text-gray-100">
            {data ? formatNumber(data.total_symbols, 0) : '...'}
          </p>
        </div>
      </div>

      {/* Gainers and Losers */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <MoverList
          title="Top Gainers"
          icon={<TrendingUp className="h-4 w-4 text-profit" />}
          entries={data?.top_gainers ?? []}
          colorClass="text-profit"
        />
        <MoverList
          title="Top Losers"
          icon={<TrendingDown className="h-4 w-4 text-loss" />}
          entries={data?.top_losers ?? []}
          colorClass="text-loss"
        />
      </div>

      {/* Mini Ticker Scroll */}
      {data?.tickers && data.tickers.length > 0 && (
        <div className="card overflow-hidden">
          <h3 className="text-sm font-semibold text-gray-200 mb-3">
            <Activity className="h-4 w-4 inline mr-1" />
            Live Tickers
          </h3>
          <div className="relative overflow-hidden">
            <div className="flex gap-6 animate-scroll">
              {[...data.tickers, ...data.tickers].map((ticker, idx) => (
                <div
                  key={`${ticker.symbol}-${ticker.exchange}-${idx}`}
                  className="flex items-center gap-2 shrink-0"
                >
                  <span className="text-xs text-gray-300 font-medium">{ticker.symbol}</span>
                  <span className="text-xs font-mono text-gray-200">
                    {formatCurrency(ticker.last)}
                  </span>
                  <span
                    className={`text-[10px] font-mono ${
                      ticker.change_percent_24h >= 0 ? 'text-profit' : 'text-loss'
                    }`}
                  >
                    {ticker.change_percent_24h >= 0 ? '+' : ''}
                    {ticker.change_percent_24h.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

interface MoverListProps {
  title: string;
  icon: React.ReactNode;
  entries: MoverEntry[];
  colorClass: string;
}

function MoverList({ title, icon, entries, colorClass }: MoverListProps) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
        {icon}
        {title}
      </h3>
      {entries.length === 0 ? (
        <p className="text-xs text-gray-600 py-4 text-center">No data available</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="table-header">Symbol</th>
                <th className="table-header">Price</th>
                <th className="table-header">24h Change</th>
                <th className="table-header">Volume</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {entries.map((entry) => (
                <tr key={entry.symbol} className="hover:bg-surface-overlay/30">
                  <td className="table-cell font-medium text-gray-200 text-xs">
                    {entry.symbol}
                  </td>
                  <td className="table-cell font-mono text-xs">
                    {formatCurrency(entry.price)}
                  </td>
                  <td className={`table-cell font-mono text-xs ${colorClass}`}>
                    {entry.change_percent_24h >= 0 ? '+' : ''}
                    {entry.change_percent_24h.toFixed(2)}%
                  </td>
                  <td className="table-cell font-mono text-xs">
                    {formatCurrency(entry.volume_24h)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
