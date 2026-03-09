import { useQuery } from '@tanstack/react-query';
import {
  Activity,
  AlertTriangle,
  Database,
  FlaskConical,
  Loader2,
  ShieldCheck,
  ShieldAlert,
  TrendingUp,
  Zap,
  CheckCircle2,
  XCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { fetchResearchDashboard, fetchStrategies } from '../api/research';
import { fetchRiskStatus } from '../api/risk';
import { fetchHealth } from '../api/admin';
import { formatCurrency, pnlColor, formatUptime } from '../utils/formatters';
import StatusIndicator from '../components/common/StatusIndicator';

export default function Dashboard() {
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ['researchDashboard'],
    queryFn: fetchResearchDashboard,
    refetchInterval: 10000,
  });

  const { data: strategies } = useQuery({
    queryKey: ['liveStrategies'],
    queryFn: fetchStrategies,
    refetchInterval: 10000,
  });

  const { data: risk } = useQuery({
    queryKey: ['riskStatus'],
    queryFn: fetchRiskStatus,
    refetchInterval: 5000,
  });

  const { data: health } = useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
    refetchInterval: 15000,
  });

  const activeStrategies = strategies?.filter((s: any) => s.status === 'ACTIVE') ?? [];
  const totalBacktests = dashboard?.total_backtests ?? 0;
  const totalBars = dashboard?.data_summary?.total_bars ?? 0;
  const datasets = dashboard?.data_summary?.datasets ?? [];

  const livePnl = dashboard?.live_strategy_pnl ?? {};
  const totalLivePnl = Object.values(livePnl).reduce((sum: number, v: any) => sum + parseFloat(v || '0'), 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Research Lab</h1>
        <p className="text-sm text-gray-500 mt-1">
          Quantitative trading research — data, backtests, live strategies
        </p>
      </div>

      {/* Kill Switch Alert */}
      {risk?.kill_switch_active && (
        <div className="p-4 bg-red-600/20 border border-red-500/40 rounded-lg flex items-center gap-3 animate-pulse">
          <AlertTriangle className="h-5 w-5 text-red-400 shrink-0" />
          <p className="text-sm font-semibold text-red-300">
            Kill switch is active — all trading is halted
          </p>
        </div>
      )}

      {/* Top Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <MetricCard
          label="Data Collected"
          value={totalBars > 0 ? `${(totalBars / 1000).toFixed(1)}K bars` : 'No data'}
          sub={`${datasets.length} datasets`}
          icon={<Database className="h-4 w-4 text-blue-400" />}
          iconBg="bg-blue-500/10"
        />
        <MetricCard
          label="Backtests Run"
          value={totalBacktests.toString()}
          sub={dashboard?.best_sharpe ? `Best: ${parseFloat(dashboard.best_sharpe.sharpe).toFixed(2)} SR` : 'None yet'}
          icon={<FlaskConical className="h-4 w-4 text-purple-400" />}
          iconBg="bg-purple-500/10"
        />
        <MetricCard
          label="Live Strategies"
          value={activeStrategies.length.toString()}
          sub={`${strategies?.length ?? 0} total`}
          icon={<Zap className="h-4 w-4 text-yellow-400" />}
          iconBg="bg-yellow-500/10"
        />
        <MetricCard
          label="Live P&L"
          value={totalLivePnl !== 0 ? `${totalLivePnl >= 0 ? '+' : ''}${formatCurrency(totalLivePnl)}` : '$0.00'}
          sub="Paper trading"
          icon={<TrendingUp className={`h-4 w-4 ${totalLivePnl >= 0 ? 'text-profit' : 'text-loss'}`} />}
          iconBg={totalLivePnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}
          valueColor={pnlColor(totalLivePnl)}
        />
        <MetricCard
          label="System"
          value={health?.status === 'healthy' ? 'Healthy' : 'Unknown'}
          sub={health?.uptime ? formatUptime(health.uptime) : '-'}
          icon={
            health?.status === 'healthy'
              ? <ShieldCheck className="h-4 w-4 text-green-400" />
              : <ShieldAlert className="h-4 w-4 text-gray-400" />
          }
          iconBg={health?.status === 'healthy' ? 'bg-green-500/10' : 'bg-gray-500/10'}
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Backtests Table */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-200">Recent Backtests</h3>
            <a href="/research" className="text-[10px] text-accent hover:text-accent-hover">
              View all →
            </a>
          </div>
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 text-accent animate-spin" />
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-border">
                    <th className="table-header">Strategy</th>
                    <th className="table-header">Symbol</th>
                    <th className="table-header">Net P&L</th>
                    <th className="table-header">Sharpe</th>
                    <th className="table-header">Max DD</th>
                    <th className="table-header">Trades</th>
                    <th className="table-header">Trust</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-border/50">
                  {(dashboard?.recent_backtests ?? []).slice(0, 8).map((bt: any) => {
                    const pnl = parseFloat(bt.net_pnl);
                    const sharpe = parseFloat(bt.sharpe_ratio);
                    const dd = parseFloat(bt.max_drawdown_pct);
                    return (
                      <tr key={bt.id} className="hover:bg-surface-overlay/30">
                        <td className="table-cell text-xs">
                          <span className="badge bg-purple-500/15 text-purple-300 text-[10px]">
                            {bt.strategy_type}
                          </span>
                        </td>
                        <td className="table-cell font-mono text-xs text-gray-300">{bt.symbol}</td>
                        <td className={`table-cell font-mono text-xs ${pnlColor(pnl)}`}>
                          {pnl >= 0 ? '+' : ''}{formatCurrency(pnl)}
                        </td>
                        <td className={`table-cell font-mono text-xs ${sharpe > 1 ? 'text-profit' : sharpe > 0 ? 'text-yellow-400' : 'text-loss'}`}>
                          {sharpe.toFixed(2)}
                        </td>
                        <td className="table-cell font-mono text-xs text-loss">
                          -{dd.toFixed(1)}%
                        </td>
                        <td className="table-cell font-mono text-xs text-gray-400">{bt.total_trades}</td>
                        <td className="table-cell">
                          {bt.is_trustworthy ? (
                            <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                          ) : (
                            <XCircle className="h-3.5 w-3.5 text-yellow-500" />
                          )}
                        </td>
                      </tr>
                    );
                  })}
                  {(!dashboard?.recent_backtests || dashboard.recent_backtests.length === 0) && (
                    <tr>
                      <td colSpan={7} className="table-cell text-center text-gray-600 py-6">
                        No backtests yet — go to Research to run your first
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-4">
          {/* Data Inventory */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              <Database className="h-4 w-4 inline mr-1" />
              Data Inventory
            </h3>
            {datasets.length === 0 ? (
              <p className="text-xs text-gray-600">No data collected yet</p>
            ) : (
              <div className="space-y-2">
                {datasets.slice(0, 6).map((ds: any) => (
                  <div key={`${ds.symbol}-${ds.interval}`} className="flex items-center justify-between">
                    <div>
                      <span className="text-xs text-gray-300 font-medium">{ds.symbol}</span>
                      <span className="text-[10px] text-gray-500 ml-1.5">{ds.interval}</span>
                    </div>
                    <span className="text-xs font-mono text-gray-400">{(ds.bar_count / 1000).toFixed(1)}K</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Live Strategies */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3">
              <Activity className="h-4 w-4 inline mr-1" />
              Live Strategies
            </h3>
            {activeStrategies.length === 0 ? (
              <p className="text-xs text-gray-600">No active strategies</p>
            ) : (
              <div className="space-y-2.5">
                {activeStrategies.map((s: any) => {
                  const pnl = parseFloat(livePnl[s.name] || '0');
                  return (
                    <div key={s.id} className="flex items-center justify-between py-1">
                      <div className="flex items-center gap-2">
                        <StatusIndicator status="green" pulse />
                        <div>
                          <span className="text-xs text-gray-200">{s.name}</span>
                          <span className="text-[10px] text-gray-500 block">{s.strategy_type}</span>
                        </div>
                      </div>
                      <span className={`text-xs font-mono ${pnlColor(pnl)}`}>
                        {pnl >= 0 ? '+' : ''}{formatCurrency(pnl)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Risk Limits */}
          {risk && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-200 mb-3">Risk Limits</h3>
              <div className="space-y-3">
                <RiskBar label="Daily Loss" value={Math.abs(risk.daily_loss)} limit={risk.daily_loss_limit} />
                <RiskBar label="Open Orders" value={risk.open_orders_count} limit={risk.max_open_orders} />
                <RiskBar label="Margin" value={risk.margin_usage_percent} limit={risk.margin_limit_percent} suffix="%" />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Backtest Sharpe Chart */}
      {dashboard?.recent_backtests && dashboard.recent_backtests.length > 2 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-200 mb-3">Backtest Performance</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={dashboard.recent_backtests.slice(0, 10).map((bt: any) => ({
                name: `${bt.strategy_type.slice(0, 4)}_${bt.symbol.slice(0, 3)}`,
                sharpe: parseFloat(bt.sharpe_ratio),
                trustworthy: bt.is_trustworthy,
              }))}
              margin={{ top: 5, right: 20, left: 0, bottom: 5 }}
            >
              <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Bar dataKey="sharpe" name="Sharpe Ratio" radius={[4, 4, 0, 0]}>
                {dashboard.recent_backtests.slice(0, 10).map((bt: any, idx: number) => (
                  <Cell
                    key={idx}
                    fill={parseFloat(bt.sharpe_ratio) > 1 ? '#22c55e' : parseFloat(bt.sharpe_ratio) > 0 ? '#eab308' : '#ef4444'}
                    fillOpacity={bt.is_trustworthy ? 1 : 0.4}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-gray-600 mt-1 text-center">
            Faded bars = untrusted (insufficient data or suspicious metrics)
          </p>
        </div>
      )}
    </div>
  );
}

// --- Sub-Components ---

function MetricCard({ label, value, sub, icon, iconBg, valueColor }: {
  label: string; value: string; sub?: string; icon: React.ReactNode; iconBg: string; valueColor?: string;
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500 font-medium">{label}</span>
        <div className={`p-1.5 rounded-lg ${iconBg}`}>{icon}</div>
      </div>
      <p className={`text-lg font-bold font-mono ${valueColor || 'text-gray-100'}`}>{value}</p>
      {sub && <p className="text-[10px] text-gray-600 mt-0.5">{sub}</p>}
    </div>
  );
}

function RiskBar({ label, value, limit, suffix = '' }: {
  label: string; value: number; limit: number; suffix?: string;
}) {
  const pct = limit > 0 ? (value / limit) * 100 : 0;
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-[10px] text-gray-500">{label}</span>
        <span className="text-[10px] font-mono text-gray-400">
          {value.toFixed(suffix === '%' ? 1 : 0)}{suffix} / {limit}{suffix}
        </span>
      </div>
      <div className="h-1 bg-surface rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${pct > 90 ? 'bg-red-500' : pct > 70 ? 'bg-yellow-500' : 'bg-green-500'}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}
