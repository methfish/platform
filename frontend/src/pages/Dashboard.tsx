import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  DollarSign,
  ShoppingCart,
  TrendingUp,
  Loader2,
} from 'lucide-react';
import { fetchOrders } from '../api/orders';
import { fetchPositions } from '../api/positions';
import { fetchRiskStatus } from '../api/risk';
import { fetchHealth, fetchExchangeStatus } from '../api/admin';
import { fetchTickers } from '../api/marketData';
import { formatCurrency, formatNumber, pnlColor, formatTimeAgo, formatUptime } from '../utils/formatters';
import { ORDER_STATUS_COLORS, ORDER_STATUS_LABELS, SIDE_COLORS } from '../utils/constants';
import StatusIndicator from '../components/common/StatusIndicator';

export default function Dashboard() {
  const { data: orders, isLoading: ordersLoading } = useQuery({
    queryKey: ['orders', { limit: 10 }],
    queryFn: () => fetchOrders({ limit: 10 }),
    refetchInterval: 5000,
  });

  const { data: positions, isLoading: positionsLoading } = useQuery({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 5000,
  });

  const { data: risk } = useQuery({
    queryKey: ['riskStatus'],
    queryFn: fetchRiskStatus,
    refetchInterval: 5000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 10000,
  });

  const { data: exchanges } = useQuery({
    queryKey: ['exchangeStatus'],
    queryFn: fetchExchangeStatus,
    refetchInterval: 10000,
  });

  const { data: tickers } = useQuery({
    queryKey: ['tickers'],
    queryFn: fetchTickers,
    refetchInterval: 5000,
  });

  const totalPnl = (positions?.total_unrealized_pnl ?? 0) + (positions?.total_realized_pnl ?? 0);
  const openOrdersCount = orders?.orders?.filter((o) =>
    ['pending', 'open', 'partially_filled'].includes(o.status),
  ).length ?? 0;

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Dashboard</h1>
        <p className="text-sm text-gray-500 mt-1">Platform overview and key metrics</p>
      </div>

      {/* Kill Switch Alert */}
      {risk?.kill_switch_active && (
        <div className="p-4 bg-red-600/20 border border-red-500/40 rounded-lg flex items-center gap-3 animate-pulse">
          <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
          <p className="text-sm font-semibold text-red-300">
            Kill switch is active -- all trading is halted
          </p>
        </div>
      )}

      {/* Summary Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">Total P&L</span>
            <div className={`p-1.5 rounded-lg ${totalPnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
              <DollarSign className={`h-4 w-4 ${totalPnl >= 0 ? 'text-profit' : 'text-loss'}`} />
            </div>
          </div>
          <p className={`text-xl font-bold font-mono ${pnlColor(totalPnl)}`}>
            {positionsLoading ? '...' : (totalPnl >= 0 ? '+' : '') + formatCurrency(totalPnl)}
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">Open Positions</span>
            <div className="p-1.5 rounded-lg bg-accent/10">
              <BarChart3 className="h-4 w-4 text-accent" />
            </div>
          </div>
          <p className="text-xl font-bold text-gray-100">
            {positionsLoading ? '...' : positions?.positions?.length ?? 0}
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">Active Orders</span>
            <div className="p-1.5 rounded-lg bg-blue-500/10">
              <ShoppingCart className="h-4 w-4 text-blue-400" />
            </div>
          </div>
          <p className="text-xl font-bold text-gray-100">
            {ordersLoading ? '...' : openOrdersCount}
          </p>
        </div>

        <div className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">Daily Loss</span>
            <div className={`p-1.5 rounded-lg ${(risk?.daily_loss ?? 0) < 0 ? 'bg-red-500/10' : 'bg-green-500/10'}`}>
              <TrendingUp className={`h-4 w-4 ${(risk?.daily_loss ?? 0) < 0 ? 'text-loss' : 'text-profit'}`} />
            </div>
          </div>
          <p className={`text-xl font-bold font-mono ${pnlColor(risk?.daily_loss ?? 0)}`}>
            {risk ? formatCurrency(risk.daily_loss) : '...'}
          </p>
          <p className="text-[10px] text-gray-600 mt-1">
            Limit: {risk ? formatCurrency(risk.daily_loss_limit) : '-'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Orders */}
        <div className="lg:col-span-2 card">
          <h3 className="text-sm font-semibold text-gray-200 mb-3">Recent Orders</h3>
          {ordersLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 text-accent animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-border">
                    <th className="table-header">Symbol</th>
                    <th className="table-header">Side</th>
                    <th className="table-header">Qty</th>
                    <th className="table-header">Price</th>
                    <th className="table-header">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/50">
                  {(orders?.orders ?? []).slice(0, 8).map((order) => {
                    const sideColors = SIDE_COLORS[order.side];
                    const statusColors = ORDER_STATUS_COLORS[order.status] ?? ORDER_STATUS_COLORS.pending;
                    return (
                      <tr key={order.id} className="hover:bg-surface-overlay/30">
                        <td className="table-cell font-medium text-gray-200 text-xs">
                          {order.symbol}
                        </td>
                        <td className="table-cell">
                          <span className={`badge ${sideColors.bg} ${sideColors.text} text-[10px] uppercase font-bold`}>
                            {order.side}
                          </span>
                        </td>
                        <td className="table-cell font-mono text-xs">
                          {formatNumber(order.quantity, 4)}
                        </td>
                        <td className="table-cell font-mono text-xs">
                          {order.price ? formatCurrency(order.price) : 'MKT'}
                        </td>
                        <td className="table-cell">
                          <span className={`badge ${statusColors.bg} ${statusColors.text} text-[10px]`}>
                            {ORDER_STATUS_LABELS[order.status] ?? order.status}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                  {(!orders?.orders || orders.orders.length === 0) && (
                    <tr>
                      <td colSpan={5} className="table-cell text-center text-gray-600 py-6">
                        No recent orders
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* System Status */}
        <div className="space-y-4">
          {/* Health */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">System Health</h3>
            <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Status</span>
                <StatusIndicator
                  status={health?.status === 'healthy' ? 'green' : 'red'}
                  label={health?.status ?? 'Unknown'}
                  pulse={health?.status === 'healthy'}
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Uptime</span>
                <span className="text-xs text-gray-300 font-mono">
                  {health?.uptime ? formatUptime(health.uptime) : '-'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-400">Version</span>
                <span className="text-xs text-gray-500">{health?.version ?? '-'}</span>
              </div>
            </div>
          </div>

          {/* Exchange Status */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">Exchanges</h3>
            <div className="space-y-2">
              {(exchanges ?? []).map((ex) => (
                <div
                  key={ex.exchange}
                  className="flex items-center justify-between py-1"
                >
                  <div className="flex items-center gap-2">
                    <StatusIndicator
                      status={ex.connected ? 'green' : 'red'}
                      pulse={ex.connected}
                    />
                    <span className="text-xs text-gray-300 capitalize">{ex.exchange}</span>
                  </div>
                  <span className="text-[10px] text-gray-500 font-mono">
                    {ex.connected ? `${ex.latency_ms}ms` : 'Disconnected'}
                  </span>
                </div>
              ))}
              {(!exchanges || exchanges.length === 0) && (
                <p className="text-xs text-gray-600">No exchange data</p>
              )}
            </div>
          </div>

          {/* Market Tickers */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              <Activity className="h-4 w-4 inline mr-1" />
              Tickers
            </h3>
            <div className="space-y-2">
              {(tickers?.tickers ?? []).slice(0, 6).map((t) => (
                <div key={`${t.exchange}-${t.symbol}`} className="flex items-center justify-between py-0.5">
                  <span className="text-xs text-gray-300">{t.symbol}</span>
                  <div className="text-right">
                    <span className="text-xs font-mono text-gray-200">
                      {formatCurrency(t.last)}
                    </span>
                    <span
                      className={`ml-2 text-[10px] font-mono ${
                        t.change_percent_24h >= 0 ? 'text-profit' : 'text-loss'
                      }`}
                    >
                      {t.change_percent_24h >= 0 ? '+' : ''}{t.change_percent_24h.toFixed(2)}%
                    </span>
                  </div>
                </div>
              ))}
              {(!tickers?.tickers || tickers.tickers.length === 0) && (
                <p className="text-xs text-gray-600">No ticker data</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Risk Summary */}
      {risk && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-200 mb-3">Risk Overview</h3>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {[
              {
                label: 'Daily Loss',
                value: `${formatCurrency(Math.abs(risk.daily_loss))} / ${formatCurrency(risk.daily_loss_limit)}`,
                pct: risk.daily_loss_limit > 0 ? (Math.abs(risk.daily_loss) / risk.daily_loss_limit) * 100 : 0,
              },
              {
                label: 'Open Orders',
                value: `${risk.open_orders_count} / ${risk.max_open_orders}`,
                pct: risk.max_open_orders > 0 ? (risk.open_orders_count / risk.max_open_orders) * 100 : 0,
              },
              {
                label: 'Margin Usage',
                value: `${risk.margin_usage_percent.toFixed(1)}% / ${risk.margin_limit_percent}%`,
                pct: risk.margin_limit_percent > 0 ? (risk.margin_usage_percent / risk.margin_limit_percent) * 100 : 0,
              },
              {
                label: 'Daily Volume',
                value: `${formatCurrency(risk.daily_volume)} / ${formatCurrency(risk.daily_volume_limit)}`,
                pct: risk.daily_volume_limit > 0 ? (risk.daily_volume / risk.daily_volume_limit) * 100 : 0,
              },
              {
                label: 'Last Check',
                value: risk.last_check_at ? formatTimeAgo(risk.last_check_at) : 'N/A',
                pct: 0,
                noBar: true,
              },
            ].map((item) => (
              <div key={item.label}>
                <p className="text-[10px] text-gray-500 mb-1">{item.label}</p>
                <p className="text-xs font-mono text-gray-300 mb-1.5">{item.value}</p>
                {!('noBar' in item && item.noBar) && (
                  <div className="h-1 bg-surface rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${
                        item.pct > 90 ? 'bg-red-500' : item.pct > 70 ? 'bg-yellow-500' : 'bg-green-500'
                      }`}
                      style={{ width: `${Math.min(item.pct, 100)}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
