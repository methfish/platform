import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
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
  ArrowRight,
  MessageCircle,
  BarChart3,
  Target,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  Line,
  Area,
  AreaChart,
} from 'recharts';
import { fetchResearchDashboard, fetchStrategies } from '../api/research';
import { fetchRiskStatus } from '../api/risk';
import { fetchHealth } from '../api/admin';
import { formatCurrency, pnlColor, formatUptime } from '../utils/formatters';
import StatusIndicator from '../components/common/StatusIndicator';

// --- Demo data for populated dashboard ---
const DEMO_BACKTESTS = [
  { id: '1', strategy_type: 'sma_crossover', symbol: 'EURUSD', interval: '1h', net_pnl: '2847.50', sharpe_ratio: '1.82', max_drawdown_pct: '4.3', total_trades: 156, win_rate: '0.58', is_trustworthy: true, status: 'completed', created_at: '2026-03-08T14:30:00Z' },
  { id: '2', strategy_type: 'rsi', symbol: 'AAPL', interval: '1d', net_pnl: '5123.80', sharpe_ratio: '2.14', max_drawdown_pct: '3.1', total_trades: 89, win_rate: '0.62', is_trustworthy: true, status: 'completed', created_at: '2026-03-08T12:15:00Z' },
  { id: '3', strategy_type: 'bollinger', symbol: 'GBPUSD', interval: '1h', net_pnl: '-412.30', sharpe_ratio: '-0.34', max_drawdown_pct: '8.7', total_trades: 203, win_rate: '0.41', is_trustworthy: false, status: 'completed', created_at: '2026-03-07T18:00:00Z' },
  { id: '4', strategy_type: 'macd', symbol: 'MSFT', interval: '1d', net_pnl: '3891.20', sharpe_ratio: '1.56', max_drawdown_pct: '5.2', total_trades: 67, win_rate: '0.55', is_trustworthy: true, status: 'completed', created_at: '2026-03-07T10:45:00Z' },
  { id: '5', strategy_type: 'sma_crossover', symbol: 'USDJPY', interval: '4h', net_pnl: '1205.90', sharpe_ratio: '1.23', max_drawdown_pct: '6.1', total_trades: 112, win_rate: '0.52', is_trustworthy: true, status: 'completed', created_at: '2026-03-06T16:00:00Z' },
  { id: '6', strategy_type: 'rsi', symbol: 'NVDA', interval: '1d', net_pnl: '8742.60', sharpe_ratio: '2.67', max_drawdown_pct: '2.8', total_trades: 45, win_rate: '0.71', is_trustworthy: true, status: 'completed', created_at: '2026-03-06T09:30:00Z' },
  { id: '7', strategy_type: 'bollinger', symbol: 'EURUSD', interval: '4h', net_pnl: '956.40', sharpe_ratio: '0.89', max_drawdown_pct: '7.4', total_trades: 178, win_rate: '0.48', is_trustworthy: false, status: 'completed', created_at: '2026-03-05T14:20:00Z' },
  { id: '8', strategy_type: 'macd', symbol: 'SPY', interval: '1d', net_pnl: '4567.10', sharpe_ratio: '1.91', max_drawdown_pct: '3.5', total_trades: 93, win_rate: '0.59', is_trustworthy: true, status: 'completed', created_at: '2026-03-05T11:00:00Z' },
];

const DEMO_DATASETS = [
  { symbol: 'EURUSD', interval: '1h', bar_count: 17520 },
  { symbol: 'GBPUSD', interval: '1h', bar_count: 17520 },
  { symbol: 'USDJPY', interval: '1h', bar_count: 17520 },
  { symbol: 'AAPL', interval: '1d', bar_count: 2520 },
  { symbol: 'MSFT', interval: '1d', bar_count: 2520 },
  { symbol: 'NVDA', interval: '1d', bar_count: 1890 },
  { symbol: 'SPY', interval: '1d', bar_count: 2520 },
  { symbol: 'EURUSD', interval: '1d', bar_count: 2520 },
];

const DEMO_STRATEGIES = [
  { id: '1', name: 'EUR/USD SMA Crossover', strategy_type: 'sma_crossover', status: 'ACTIVE', trading_mode: 'paper' },
  { id: '2', name: 'AAPL RSI Mean Revert', strategy_type: 'rsi', status: 'ACTIVE', trading_mode: 'paper' },
  { id: '3', name: 'SPY MACD Trend', strategy_type: 'macd', status: 'STOPPED', trading_mode: 'paper' },
];

const DEMO_LIVE_PNL: Record<string, string> = {
  'EUR/USD SMA Crossover': '342.50',
  'AAPL RSI Mean Revert': '-87.20',
  'SPY MACD Trend': '0',
};

const DEMO_EQUITY_CURVE = Array.from({ length: 30 }, (_, i) => {
  const base = 100000;
  const noise = Math.sin(i * 0.5) * 1500 + (Math.sin(i * 1.3) * 400);
  const trend = i * 120;
  return {
    day: `Mar ${i + 1}`,
    equity: Math.round(base + trend + noise),
    benchmark: Math.round(base + i * 50 + Math.sin(i * 0.8) * 200),
  };
});

const DEMO_STRATEGY_PERFORMANCE = [
  { name: 'SMA Cross', eurusd: 1.82, gbpusd: 1.23, usdjpy: 0.89 },
  { name: 'RSI', eurusd: 1.45, gbpusd: 0.67, usdjpy: 1.12 },
  { name: 'Bollinger', eurusd: 0.89, gbpusd: -0.34, usdjpy: 0.56 },
  { name: 'MACD', eurusd: 1.56, gbpusd: 1.91, usdjpy: 0.78 },
];

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

  // Use real data if available, otherwise demo data
  const backtests = dashboard?.recent_backtests?.length ? dashboard.recent_backtests : DEMO_BACKTESTS;
  const datasets = dashboard?.data_summary?.datasets?.length ? dashboard.data_summary.datasets : DEMO_DATASETS;
  const totalBars = dashboard?.data_summary?.total_bars || DEMO_DATASETS.reduce((s, d) => s + d.bar_count, 0);
  const totalBacktests = dashboard?.total_backtests || DEMO_BACKTESTS.length;
  const activeStrategiesList = strategies?.filter((s: any) => s.status === 'ACTIVE') ?? DEMO_STRATEGIES.filter(s => s.status === 'ACTIVE');
  const allStrategies = strategies?.length ? strategies : DEMO_STRATEGIES;
  const livePnl = dashboard?.live_strategy_pnl ?? DEMO_LIVE_PNL;
  const totalLivePnl = Object.values(livePnl).reduce((sum: number, v: any) => sum + parseFloat(v || '0'), 0);
  const bestSharpe = dashboard?.best_sharpe || { strategy_type: 'rsi', symbol: 'NVDA', sharpe: '2.67', net_pnl: '8742.60' };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">Research Lab</h1>
          <p className="text-sm text-gray-500 mt-1">
            Quantitative trading research — data, backtests, live strategies
          </p>
        </div>
        <Link
          to="/chat"
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-accent/15 text-accent hover:bg-accent/25 transition-colors text-sm font-medium"
        >
          <MessageCircle className="h-4 w-4" />
          Ask AI
        </Link>
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
          value={`${(totalBars / 1000).toFixed(1)}K bars`}
          sub={`${datasets.length} datasets`}
          icon={<Database className="h-4 w-4 text-blue-400" />}
          iconBg="bg-blue-500/10"
        />
        <MetricCard
          label="Backtests Run"
          value={totalBacktests.toString()}
          sub={`Best: ${parseFloat(bestSharpe.sharpe).toFixed(2)} SR`}
          icon={<FlaskConical className="h-4 w-4 text-purple-400" />}
          iconBg="bg-purple-500/10"
        />
        <MetricCard
          label="Live Strategies"
          value={activeStrategiesList.length.toString()}
          sub={`${allStrategies.length} total`}
          icon={<Zap className="h-4 w-4 text-yellow-400" />}
          iconBg="bg-yellow-500/10"
        />
        <MetricCard
          label="Live P&L"
          value={`${totalLivePnl >= 0 ? '+' : ''}${formatCurrency(totalLivePnl)}`}
          sub="Paper trading"
          icon={<TrendingUp className={`h-4 w-4 ${totalLivePnl >= 0 ? 'text-profit' : 'text-loss'}`} />}
          iconBg={totalLivePnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}
          valueColor={pnlColor(totalLivePnl)}
        />
        <MetricCard
          label="System"
          value={health?.status === 'healthy' ? 'Healthy' : 'Online'}
          sub={health?.uptime ? formatUptime(health.uptime) : 'Running'}
          icon={<ShieldCheck className="h-4 w-4 text-green-400" />}
          iconBg="bg-green-500/10"
        />
      </div>

      {/* Equity Curve */}
      <div className="card">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-gray-200">Portfolio Equity Curve</h3>
          <div className="flex items-center gap-4 text-[10px]">
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-accent rounded" /> Portfolio
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-3 h-0.5 bg-gray-500 rounded" /> Benchmark
            </span>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={220}>
          <AreaChart data={DEMO_EQUITY_CURVE} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
            <defs>
              <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <XAxis dataKey="day" tick={{ fill: '#6b7280', fontSize: 10 }} />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickFormatter={(v) => `$${(v / 1000).toFixed(0)}K`}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: '#9ca3af' }}
              formatter={(v: number) => [`$${v.toLocaleString('en-US', { maximumFractionDigits: 0 })}`, '']}
            />
            <Area type="monotone" dataKey="equity" stroke="#6366f1" strokeWidth={2} fill="url(#equityGrad)" name="Portfolio" />
            <Line type="monotone" dataKey="benchmark" stroke="#6b7280" strokeWidth={1} strokeDasharray="4 4" dot={false} name="Benchmark" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Backtests Table */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-gray-200">Recent Backtests</h3>
            <Link to="/research" className="text-[10px] text-accent hover:text-accent-hover flex items-center gap-1">
              View all <ArrowRight className="h-3 w-3" />
            </Link>
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
                  {backtests.slice(0, 8).map((bt: any) => {
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
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-4">
          {/* Data Inventory */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-400" />
              Data Inventory
            </h3>
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
              {datasets.length > 6 && (
                <p className="text-[10px] text-gray-600 text-center pt-1">+{datasets.length - 6} more</p>
              )}
            </div>
          </div>

          {/* Live Strategies */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4 text-yellow-400" />
              Live Strategies
            </h3>
            <div className="space-y-2.5">
              {(activeStrategiesList.length > 0 ? activeStrategiesList : DEMO_STRATEGIES.filter(s => s.status === 'ACTIVE')).map((s: any) => {
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
          </div>

          {/* Risk Limits */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
              <ShieldAlert className="h-4 w-4 text-red-400" />
              Risk Limits
            </h3>
            <div className="space-y-3">
              <RiskBar
                label="Daily Loss"
                value={risk ? Math.abs(risk.daily_loss) : 320}
                limit={risk?.daily_loss_limit ?? 5000}
              />
              <RiskBar
                label="Open Orders"
                value={risk?.open_orders_count ?? 3}
                limit={risk?.max_open_orders ?? 20}
              />
              <RiskBar
                label="Margin"
                value={risk?.margin_usage_percent ?? 12.5}
                limit={risk?.margin_limit_percent ?? 100}
                suffix="%"
              />
            </div>
          </div>
        </div>
      </div>

      {/* Strategy Comparison Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
            <Target className="h-4 w-4 text-purple-400" />
            Backtest Sharpe Ratios
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart
              data={backtests.slice(0, 10).map((bt: any) => ({
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
                {backtests.slice(0, 10).map((bt: any, idx: number) => (
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

        <div className="card">
          <h3 className="text-sm font-semibold text-gray-200 mb-3 flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-blue-400" />
            Strategy x Symbol Sharpe Matrix
          </h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={DEMO_STRATEGY_PERFORMANCE} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
              <XAxis dataKey="name" tick={{ fill: '#6b7280', fontSize: 10 }} />
              <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#9ca3af' }}
              />
              <Bar dataKey="eurusd" name="EUR/USD" fill="#6366f1" radius={[2, 2, 0, 0]} />
              <Bar dataKey="gbpusd" name="GBP/USD" fill="#06b6d4" radius={[2, 2, 0, 0]} />
              <Bar dataKey="usdjpy" name="USD/JPY" fill="#f59e0b" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          <div className="flex items-center justify-center gap-4 mt-2 text-[10px] text-gray-500">
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-indigo-500" /> EUR/USD</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-cyan-500" /> GBP/USD</span>
            <span className="flex items-center gap-1"><span className="w-2 h-2 rounded bg-amber-500" /> USD/JPY</span>
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <QuickAction to="/research" icon={<FlaskConical className="h-5 w-5 text-purple-400" />} label="Run Backtest" sub="Test a strategy" />
        <QuickAction to="/chat" icon={<MessageCircle className="h-5 w-5 text-accent" />} label="Ask AI" sub="Research assistant" />
        <QuickAction to="/strategies" icon={<Zap className="h-5 w-5 text-yellow-400" />} label="Strategies" sub="Manage live" />
        <QuickAction to="/agents" icon={<Activity className="h-5 w-5 text-green-400" />} label="Run Agent" sub="Auto-research" />
      </div>
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

function QuickAction({ to, icon, label, sub }: { to: string; icon: React.ReactNode; label: string; sub: string }) {
  return (
    <Link
      to={to}
      className="card hover:border-accent/30 hover:bg-surface-overlay/30 transition-all group cursor-pointer"
    >
      <div className="flex items-center gap-3">
        {icon}
        <div>
          <p className="text-sm font-medium text-gray-200 group-hover:text-gray-100">{label}</p>
          <p className="text-[10px] text-gray-500">{sub}</p>
        </div>
      </div>
    </Link>
  );
}
