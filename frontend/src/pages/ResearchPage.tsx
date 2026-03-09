import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  FlaskConical,
  Play,
  Database,
  Loader2,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Download,
  BarChart3,
  TrendingUp,
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  fetchBacktests,
  fetchBacktestDetail,
  fetchDataSummary,
  startCollection,
  fetchCollectionStatus,
  runBacktest,
} from '../api/research';
import { formatCurrency, formatDate, pnlColor } from '../utils/formatters';

// --- Demo Data ---

const DEMO_BACKTESTS = [
  { id: 'demo-1', strategy_type: 'sma_crossover', symbol: 'EURUSD', net_pnl: '1284.50', sharpe_ratio: '1.42', max_drawdown_pct: '3.8', win_rate: '0.56', total_trades: 87, is_trustworthy: true, created_at: '2026-02-15T10:30:00Z' },
  { id: 'demo-2', strategy_type: 'rsi', symbol: 'AAPL', net_pnl: '2105.30', sharpe_ratio: '1.85', max_drawdown_pct: '4.2', win_rate: '0.62', total_trades: 54, is_trustworthy: true, created_at: '2026-02-18T14:00:00Z' },
  { id: 'demo-3', strategy_type: 'bollinger', symbol: 'GBPUSD', net_pnl: '-432.10', sharpe_ratio: '0.38', max_drawdown_pct: '7.5', win_rate: '0.41', total_trades: 120, is_trustworthy: false, created_at: '2026-02-20T09:15:00Z' },
  { id: 'demo-4', strategy_type: 'macd', symbol: 'MSFT', net_pnl: '876.20', sharpe_ratio: '1.12', max_drawdown_pct: '5.1', win_rate: '0.53', total_trades: 42, is_trustworthy: true, created_at: '2026-02-22T16:45:00Z' },
  { id: 'demo-5', strategy_type: 'sma_crossover', symbol: 'SPY', net_pnl: '3210.80', sharpe_ratio: '2.05', max_drawdown_pct: '2.9', win_rate: '0.64', total_trades: 31, is_trustworthy: true, created_at: '2026-02-25T11:00:00Z' },
  { id: 'demo-6', strategy_type: 'rsi', symbol: 'USDJPY', net_pnl: '-125.40', sharpe_ratio: '0.22', max_drawdown_pct: '9.3', win_rate: '0.38', total_trades: 96, is_trustworthy: false, created_at: '2026-02-27T08:30:00Z' },
  { id: 'demo-7', strategy_type: 'macd', symbol: 'EURUSD', net_pnl: '547.60', sharpe_ratio: '0.95', max_drawdown_pct: '4.7', win_rate: '0.51', total_trades: 68, is_trustworthy: true, created_at: '2026-03-01T13:20:00Z' },
  { id: 'demo-8', strategy_type: 'bollinger', symbol: 'AAPL', net_pnl: '1892.10', sharpe_ratio: '1.68', max_drawdown_pct: '3.4', win_rate: '0.59', total_trades: 45, is_trustworthy: true, created_at: '2026-03-05T15:10:00Z' },
];

const DEMO_DETAIL: Record<string, any> = {
  'demo-1': {
    id: 'demo-1', strategy_type: 'sma_crossover', symbol: 'EURUSD', is_trustworthy: true, trust_issues: [],
    metrics: {
      total_net_pnl: '1284.50', total_return_pct: 12.85, sharpe_ratio: 1.42, sortino_ratio: 1.98,
      max_drawdown_pct: 3.8, win_rate: 0.56, profit_factor: 1.72, expectancy: '14.76',
      total_trades: 87, total_commission: '43.50', fee_drag_pct: 0.4, avg_holding_time_minutes: 240,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 + i * 22 + Math.sin(i / 5) * 150).toFixed(2),
    })),
  },
  'demo-2': {
    id: 'demo-2', strategy_type: 'rsi', symbol: 'AAPL', is_trustworthy: true, trust_issues: [],
    metrics: {
      total_net_pnl: '2105.30', total_return_pct: 21.05, sharpe_ratio: 1.85, sortino_ratio: 2.41,
      max_drawdown_pct: 4.2, win_rate: 0.62, profit_factor: 2.15, expectancy: '38.99',
      total_trades: 54, total_commission: '27.00', fee_drag_pct: 0.3, avg_holding_time_minutes: 480,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 + i * 35 + Math.sin(i / 4) * 200).toFixed(2),
    })),
  },
  'demo-3': {
    id: 'demo-3', strategy_type: 'bollinger', symbol: 'GBPUSD', is_trustworthy: false,
    trust_issues: ['Sharpe ratio below 0.5', 'Max drawdown exceeds 7%', 'Win rate below 45%'],
    metrics: {
      total_net_pnl: '-432.10', total_return_pct: -4.32, sharpe_ratio: 0.38, sortino_ratio: 0.29,
      max_drawdown_pct: 7.5, win_rate: 0.41, profit_factor: 0.82, expectancy: '-3.60',
      total_trades: 120, total_commission: '60.00', fee_drag_pct: 0.6, avg_holding_time_minutes: 180,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 - i * 7.2 + Math.sin(i / 6) * 120).toFixed(2),
    })),
  },
  'demo-4': {
    id: 'demo-4', strategy_type: 'macd', symbol: 'MSFT', is_trustworthy: true, trust_issues: [],
    metrics: {
      total_net_pnl: '876.20', total_return_pct: 8.76, sharpe_ratio: 1.12, sortino_ratio: 1.54,
      max_drawdown_pct: 5.1, win_rate: 0.53, profit_factor: 1.48, expectancy: '20.86',
      total_trades: 42, total_commission: '21.00', fee_drag_pct: 0.2, avg_holding_time_minutes: 360,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 + i * 14.6 + Math.sin(i / 4) * 100).toFixed(2),
    })),
  },
  'demo-5': {
    id: 'demo-5', strategy_type: 'sma_crossover', symbol: 'SPY', is_trustworthy: true, trust_issues: [],
    metrics: {
      total_net_pnl: '3210.80', total_return_pct: 32.11, sharpe_ratio: 2.05, sortino_ratio: 2.87,
      max_drawdown_pct: 2.9, win_rate: 0.64, profit_factor: 2.45, expectancy: '103.57',
      total_trades: 31, total_commission: '15.50', fee_drag_pct: 0.2, avg_holding_time_minutes: 720,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 + i * 54 + Math.sin(i / 3) * 180).toFixed(2),
    })),
  },
  'demo-6': {
    id: 'demo-6', strategy_type: 'rsi', symbol: 'USDJPY', is_trustworthy: false,
    trust_issues: ['Sharpe ratio below 0.5', 'Max drawdown exceeds 9%'],
    metrics: {
      total_net_pnl: '-125.40', total_return_pct: -1.25, sharpe_ratio: 0.22, sortino_ratio: 0.15,
      max_drawdown_pct: 9.3, win_rate: 0.38, profit_factor: 0.91, expectancy: '-1.31',
      total_trades: 96, total_commission: '48.00', fee_drag_pct: 0.5, avg_holding_time_minutes: 120,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 - i * 2.1 + Math.sin(i / 7) * 90).toFixed(2),
    })),
  },
  'demo-7': {
    id: 'demo-7', strategy_type: 'macd', symbol: 'EURUSD', is_trustworthy: true, trust_issues: [],
    metrics: {
      total_net_pnl: '547.60', total_return_pct: 5.48, sharpe_ratio: 0.95, sortino_ratio: 1.22,
      max_drawdown_pct: 4.7, win_rate: 0.51, profit_factor: 1.35, expectancy: '8.05',
      total_trades: 68, total_commission: '34.00', fee_drag_pct: 0.3, avg_holding_time_minutes: 300,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 + i * 9.1 + Math.sin(i / 5) * 80).toFixed(2),
    })),
  },
  'demo-8': {
    id: 'demo-8', strategy_type: 'bollinger', symbol: 'AAPL', is_trustworthy: true, trust_issues: [],
    metrics: {
      total_net_pnl: '1892.10', total_return_pct: 18.92, sharpe_ratio: 1.68, sortino_ratio: 2.15,
      max_drawdown_pct: 3.4, win_rate: 0.59, profit_factor: 1.95, expectancy: '42.05',
      total_trades: 45, total_commission: '22.50', fee_drag_pct: 0.2, avg_holding_time_minutes: 540,
    },
    equity_curve: Array.from({ length: 60 }, (_, i) => ({
      t: new Date(2026, 0, 1 + i).toISOString(),
      eq: (10000 + i * 31.5 + Math.sin(i / 4) * 160).toFixed(2),
    })),
  },
};

const DEMO_DATA_SUMMARY = {
  total_bars: 64250,
  datasets: [
    { symbol: 'EURUSD', interval: '1h', bar_count: 8760, earliest: '2025-01-01T00:00:00Z', latest: '2026-03-09T00:00:00Z' },
    { symbol: 'EURUSD', interval: '1d', bar_count: 365, earliest: '2025-01-01T00:00:00Z', latest: '2026-03-09T00:00:00Z' },
    { symbol: 'GBPUSD', interval: '1h', bar_count: 8760, earliest: '2025-01-01T00:00:00Z', latest: '2026-03-09T00:00:00Z' },
    { symbol: 'GBPUSD', interval: '1d', bar_count: 365, earliest: '2025-01-01T00:00:00Z', latest: '2026-03-09T00:00:00Z' },
    { symbol: 'USDJPY', interval: '1h', bar_count: 8760, earliest: '2025-01-01T00:00:00Z', latest: '2026-03-09T00:00:00Z' },
    { symbol: 'AAPL', interval: '1h', bar_count: 6500, earliest: '2025-01-02T14:30:00Z', latest: '2026-03-07T21:00:00Z' },
    { symbol: 'AAPL', interval: '1d', bar_count: 252, earliest: '2025-01-02T00:00:00Z', latest: '2026-03-07T00:00:00Z' },
    { symbol: 'MSFT', interval: '1h', bar_count: 6500, earliest: '2025-01-02T14:30:00Z', latest: '2026-03-07T21:00:00Z' },
    { symbol: 'MSFT', interval: '1d', bar_count: 252, earliest: '2025-01-02T00:00:00Z', latest: '2026-03-07T00:00:00Z' },
    { symbol: 'SPY', interval: '1h', bar_count: 6500, earliest: '2025-01-02T14:30:00Z', latest: '2026-03-07T21:00:00Z' },
    { symbol: 'SPY', interval: '1d', bar_count: 252, earliest: '2025-01-02T00:00:00Z', latest: '2026-03-07T00:00:00Z' },
  ],
};

type Tab = 'backtests' | 'data' | 'run';

export default function ResearchPage() {
  const [tab, setTab] = useState<Tab>('backtests');
  const [selectedBt, setSelectedBt] = useState<string | null>(null);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100">Research</h1>
        <p className="text-sm text-gray-500 mt-1">Backtest strategies, collect data, compare results</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-surface-raised p-1 rounded-lg w-fit">
        {([
          { id: 'backtests', label: 'Backtests', icon: FlaskConical },
          { id: 'run', label: 'Run Backtest', icon: Play },
          { id: 'data', label: 'Data', icon: Database },
        ] as const).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              tab === t.id ? 'bg-accent/15 text-accent' : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            <t.icon className="h-3.5 w-3.5" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'backtests' && <BacktestsTab selectedBt={selectedBt} onSelect={setSelectedBt} />}
      {tab === 'run' && <RunBacktestTab />}
      {tab === 'data' && <DataTab />}
    </div>
  );
}

// --- Backtests Tab ---

function BacktestsTab({ selectedBt, onSelect }: { selectedBt: string | null; onSelect: (id: string | null) => void }) {
  const { data: rawBacktests, isLoading } = useQuery({
    queryKey: ['backtests'],
    queryFn: () => fetchBacktests({ limit: 50 }),
  });

  const backtests = rawBacktests && rawBacktests.length > 0 ? rawBacktests : DEMO_BACKTESTS;
  const isDemo = !rawBacktests || rawBacktests.length === 0;

  const { data: apiDetail } = useQuery({
    queryKey: ['backtestDetail', selectedBt],
    queryFn: () => fetchBacktestDetail(selectedBt!),
    enabled: !!selectedBt && !selectedBt.startsWith('demo-'),
  });

  const detail = selectedBt?.startsWith('demo-') ? DEMO_DETAIL[selectedBt] : apiDetail;

  if (isLoading) return <LoadingSpinner />;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* List */}
      <div className="lg:col-span-2 card">
        <h3 className="text-sm font-semibold text-gray-200 mb-3">All Backtests</h3>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-surface-border">
                <th className="table-header">Strategy</th>
                <th className="table-header">Symbol</th>
                <th className="table-header">Net P&L</th>
                <th className="table-header">Sharpe</th>
                <th className="table-header">DD</th>
                <th className="table-header">Win%</th>
                <th className="table-header">Trades</th>
                <th className="table-header">Trust</th>
                <th className="table-header">Date</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-border/50">
              {(backtests ?? []).map((bt: any) => {
                const pnl = parseFloat(bt.net_pnl);
                const sharpe = parseFloat(bt.sharpe_ratio);
                const dd = parseFloat(bt.max_drawdown_pct);
                const wr = parseFloat(bt.win_rate) * 100;
                return (
                  <tr
                    key={bt.id}
                    onClick={() => onSelect(bt.id)}
                    className={`hover:bg-surface-overlay/30 cursor-pointer ${selectedBt === bt.id ? 'bg-accent/5' : ''}`}
                  >
                    <td className="table-cell">
                      <span className="badge bg-purple-500/15 text-purple-300 text-[10px]">{bt.strategy_type}</span>
                    </td>
                    <td className="table-cell font-mono text-xs">{bt.symbol}</td>
                    <td className={`table-cell font-mono text-xs ${pnlColor(pnl)}`}>
                      {pnl >= 0 ? '+' : ''}{formatCurrency(pnl)}
                    </td>
                    <td className={`table-cell font-mono text-xs ${sharpe > 1 ? 'text-profit' : 'text-yellow-400'}`}>{sharpe.toFixed(2)}</td>
                    <td className="table-cell font-mono text-xs text-loss">-{dd.toFixed(1)}%</td>
                    <td className="table-cell font-mono text-xs text-gray-400">{wr.toFixed(0)}%</td>
                    <td className="table-cell font-mono text-xs text-gray-400">{bt.total_trades}</td>
                    <td className="table-cell">
                      {bt.is_trustworthy
                        ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />
                        : <XCircle className="h-3.5 w-3.5 text-yellow-500" />}
                    </td>
                    <td className="table-cell text-[10px] text-gray-500">{formatDate(bt.created_at)}</td>
                  </tr>
                );
              })}
              {(!backtests || backtests.length === 0) && (
                <tr><td colSpan={9} className="table-cell text-center text-gray-600 py-8">No backtests yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Panel */}
      <div className="space-y-4">
        {detail ? (
          <>
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-200 mb-2">
                {detail.strategy_type} — {detail.symbol}
              </h3>
              {detail.metrics && (
                <div className="grid grid-cols-2 gap-2">
                  <MiniStat label="Net P&L" value={formatCurrency(parseFloat(detail.metrics.total_net_pnl))} color={pnlColor(parseFloat(detail.metrics.total_net_pnl))} />
                  <MiniStat label="Return" value={`${detail.metrics.total_return_pct.toFixed(2)}%`} color={pnlColor(detail.metrics.total_return_pct)} />
                  <MiniStat label="Sharpe" value={detail.metrics.sharpe_ratio.toFixed(3)} />
                  <MiniStat label="Sortino" value={detail.metrics.sortino_ratio.toFixed(3)} />
                  <MiniStat label="Max DD" value={`-${detail.metrics.max_drawdown_pct.toFixed(2)}%`} color="text-loss" />
                  <MiniStat label="Win Rate" value={`${(detail.metrics.win_rate * 100).toFixed(1)}%`} />
                  <MiniStat label="Profit Factor" value={detail.metrics.profit_factor.toFixed(2)} />
                  <MiniStat label="Expectancy" value={formatCurrency(parseFloat(detail.metrics.expectancy))} />
                  <MiniStat label="Trades" value={detail.metrics.total_trades.toString()} />
                  <MiniStat label="Fees" value={formatCurrency(parseFloat(detail.metrics.total_commission))} />
                  <MiniStat label="Fee Drag" value={`${detail.metrics.fee_drag_pct.toFixed(1)}%`} />
                  <MiniStat label="Avg Hold" value={`${detail.metrics.avg_holding_time_minutes.toFixed(0)}m`} />
                </div>
              )}
              {/* Trust status */}
              {detail.is_trustworthy ? (
                <div className="mt-3 flex items-center gap-1.5 text-green-400 text-xs">
                  <CheckCircle2 className="h-3.5 w-3.5" /> Trustworthy
                </div>
              ) : (
                <div className="mt-3 space-y-1">
                  {(detail.trust_issues ?? []).map((issue: string, i: number) => (
                    <div key={i} className="flex items-center gap-1.5 text-yellow-500 text-[10px]">
                      <AlertTriangle className="h-3 w-3 shrink-0" /> {issue}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Equity Curve */}
            {detail.equity_curve && detail.equity_curve.length > 1 && (
              <div className="card">
                <h3 className="text-sm font-semibold text-gray-200 mb-2">Equity Curve</h3>
                <ResponsiveContainer width="100%" height={150}>
                  <AreaChart data={detail.equity_curve.map((p: any) => ({
                    time: new Date(p.t).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
                    equity: parseFloat(p.eq),
                  }))}>
                    <defs>
                      <linearGradient id="eqGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" tick={{ fill: '#6b7280', fontSize: 9 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fill: '#6b7280', fontSize: 9 }} domain={['auto', 'auto']} />
                    <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151', borderRadius: 8, fontSize: 11 }} />
                    <Area type="monotone" dataKey="equity" stroke="#3b82f6" fill="url(#eqGrad)" strokeWidth={1.5} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            )}
          </>
        ) : (
          <div className="card text-center py-8">
            <BarChart3 className="h-8 w-8 text-gray-600 mx-auto mb-2" />
            <p className="text-xs text-gray-500">Select a backtest to view details</p>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Run Backtest Tab ---

function RunBacktestTab() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({
    strategy_type: 'sma_crossover',
    symbol: 'EURUSD',
    interval: '1h',
    initial_capital: 10000,
    cost_model: 'forex',
    max_position_size: 10000,
    stop_loss_pct: 5,
    params: '{"fast_period": 10, "slow_period": 30}',
  });

  const mutation = useMutation({
    mutationFn: () =>
      runBacktest({
        strategy_type: form.strategy_type,
        symbol: form.symbol,
        interval: form.interval,
        initial_capital: form.initial_capital,
        cost_model: form.cost_model,
        strategy_params: JSON.parse(form.params || '{}'),
        max_position_size: form.max_position_size,
        stop_loss_pct: form.stop_loss_pct || null,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['backtests'] });
      queryClient.invalidateQueries({ queryKey: ['researchDashboard'] });
    },
  });

  const presets: Record<string, string> = {
    sma_crossover: '{"fast_period": 10, "slow_period": 30}',
    rsi: '{"rsi_period": 14, "oversold": 30, "overbought": 70}',
    bollinger: '{"bb_period": 20, "num_std": 2.0}',
    macd: '{"fast_ema": 12, "slow_ema": 26, "signal_period": 9}',
    grid: '{"grid_size_pct": 1.0}',
    mean_reversion: '{"sma_period": 20, "entry_std": 2.0}',
    market_making: '{"spread_bps": 10, "inventory_limit": 5}',
    breakout: '{"lookback": 20}',
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-200 mb-4">Configure Backtest</h3>
        <div className="space-y-3">
          <Field label="Strategy Type">
            <select
              value={form.strategy_type}
              onChange={(e) => setForm({ ...form, strategy_type: e.target.value, params: presets[e.target.value] || '{}' })}
              className="input-field"
            >
              <option value="sma_crossover">SMA Crossover</option>
              <option value="rsi">RSI</option>
              <option value="bollinger">Bollinger Bands</option>
              <option value="macd">MACD</option>
              <option value="grid">Grid Trading</option>
              <option value="mean_reversion">Mean Reversion</option>
              <option value="market_making">Market Making</option>
              <option value="breakout">Breakout</option>
            </select>
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Symbol">
              <input value={form.symbol} onChange={(e) => setForm({ ...form, symbol: e.target.value })} className="input-field" />
            </Field>
            <Field label="Interval">
              <select value={form.interval} onChange={(e) => setForm({ ...form, interval: e.target.value })} className="input-field">
                <option value="1h">1h</option>
                <option value="1d">1d</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
              </select>
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Capital ($)">
              <input type="number" value={form.initial_capital} onChange={(e) => setForm({ ...form, initial_capital: +e.target.value })} className="input-field" />
            </Field>
            <Field label="Max Position">
              <input type="number" step="0.001" value={form.max_position_size} onChange={(e) => setForm({ ...form, max_position_size: +e.target.value })} className="input-field" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Cost Model">
              <select value={form.cost_model} onChange={(e) => setForm({ ...form, cost_model: e.target.value })} className="input-field">
                <option value="forex">Forex Retail</option>
                <option value="forex_ecn">Forex ECN</option>
                <option value="stock">Stock Retail</option>
                <option value="stock_ib">Stock IB</option>
                <option value="zero">Zero (naive)</option>
              </select>
            </Field>
            <Field label="Stop Loss %">
              <input type="number" step="0.5" value={form.stop_loss_pct} onChange={(e) => setForm({ ...form, stop_loss_pct: +e.target.value })} className="input-field" />
            </Field>
          </div>
          <Field label="Strategy Params (JSON)">
            <textarea
              value={form.params}
              onChange={(e) => setForm({ ...form, params: e.target.value })}
              className="input-field font-mono text-[11px] h-20"
            />
          </Field>
          <button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            className="w-full py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {mutation.isPending ? 'Running...' : 'Run Backtest'}
          </button>
        </div>
      </div>

      {/* Result */}
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-200 mb-3">Result</h3>
        {mutation.isSuccess && mutation.data?.metrics ? (
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-2">
              <MiniStat label="Net P&L" value={formatCurrency(parseFloat(mutation.data.metrics.total_net_pnl))} color={pnlColor(parseFloat(mutation.data.metrics.total_net_pnl))} />
              <MiniStat label="Return" value={`${mutation.data.metrics.total_return_pct.toFixed(2)}%`} color={pnlColor(mutation.data.metrics.total_return_pct)} />
              <MiniStat label="Sharpe" value={mutation.data.metrics.sharpe_ratio.toFixed(3)} />
              <MiniStat label="Max DD" value={`-${mutation.data.metrics.max_drawdown_pct.toFixed(2)}%`} color="text-loss" />
              <MiniStat label="Win Rate" value={`${(mutation.data.metrics.win_rate * 100).toFixed(1)}%`} />
              <MiniStat label="Trades" value={mutation.data.metrics.total_trades.toString()} />
            </div>
            {mutation.data.metrics.is_trustworthy ? (
              <div className="flex items-center gap-1.5 text-green-400 text-xs"><CheckCircle2 className="h-3.5 w-3.5" /> Trustworthy</div>
            ) : (
              <div className="space-y-1">
                {mutation.data.metrics.trust_issues.map((issue: string, i: number) => (
                  <div key={i} className="flex items-center gap-1.5 text-yellow-500 text-[10px]">
                    <AlertTriangle className="h-3 w-3 shrink-0" /> {issue}
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : mutation.isError ? (
          <div className="text-xs text-red-400">Error: {(mutation.error as any)?.message}</div>
        ) : (
          <div className="text-center py-12">
            <FlaskConical className="h-8 w-8 text-gray-600 mx-auto mb-2" />
            <p className="text-xs text-gray-500">Configure and run a backtest to see results</p>
          </div>
        )}
      </div>
    </div>
  );
}

// --- Data Tab ---

function DataTab() {
  const queryClient = useQueryClient();
  const { data: rawSummary, isLoading } = useQuery({
    queryKey: ['dataSummary'],
    queryFn: fetchDataSummary,
  });

  const summary = rawSummary && rawSummary.total_bars > 0 ? rawSummary : DEMO_DATA_SUMMARY;

  const { data: status } = useQuery({
    queryKey: ['collectionStatus'],
    queryFn: fetchCollectionStatus,
    refetchInterval: 2000,
  });

  const collectMutation = useMutation({
    mutationFn: () => startCollection({ exchange: 'yfinance', symbols: ['EURUSD', 'GBPUSD', 'USDJPY', 'AAPL', 'MSFT', 'SPY'], intervals: ['1h', '1d'], limit: 500 }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['collectionStatus'] }),
  });

  const isCollecting = status?.status === 'running';

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <div className="card">
        <h3 className="text-sm font-semibold text-gray-200 mb-3">Data Collection</h3>
        <button
          onClick={() => collectMutation.mutate()}
          disabled={isCollecting || collectMutation.isPending}
          className="w-full py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2 mb-4"
        >
          {isCollecting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
          {isCollecting ? `Collecting... ${status?.progress_pct?.toFixed(0)}%` : 'Collect Forex & Stock Data'}
        </button>
        {isCollecting && status && (
          <div className="space-y-2">
            <div className="h-2 bg-surface rounded-full overflow-hidden">
              <div className="h-full bg-blue-500 rounded-full transition-all" style={{ width: `${status.progress_pct}%` }} />
            </div>
            <p className="text-[10px] text-gray-500">
              {status.bars_inserted} bars inserted, {status.bars_skipped} skipped
            </p>
          </div>
        )}
        {status?.status === 'completed' && (
          <p className="text-xs text-green-400">Collection complete: {status.bars_inserted} bars inserted</p>
        )}
      </div>

      <div className="card">
        <h3 className="text-sm font-semibold text-gray-200 mb-3">Stored Data</h3>
        {isLoading ? (
          <LoadingSpinner />
        ) : (
          <>
            <p className="text-lg font-bold font-mono text-gray-100 mb-3">
              {((summary?.total_bars ?? 0) / 1000).toFixed(1)}K <span className="text-xs text-gray-500 font-normal">total bars</span>
            </p>
            <div className="space-y-2">
              {(summary?.datasets ?? []).map((ds: any) => (
                <div key={`${ds.symbol}-${ds.interval}`} className="flex items-center justify-between py-1 border-b border-surface-border/30">
                  <div>
                    <span className="text-xs text-gray-200 font-medium">{ds.symbol}</span>
                    <span className="text-[10px] text-gray-500 ml-1.5 badge bg-gray-700/50 text-gray-400">{ds.interval}</span>
                  </div>
                  <div className="text-right">
                    <span className="text-xs font-mono text-gray-300">{ds.bar_count.toLocaleString()}</span>
                    <span className="text-[10px] text-gray-600 block">
                      {ds.earliest ? formatDate(ds.earliest) : '-'} → {ds.latest ? formatDate(ds.latest) : '-'}
                    </span>
                  </div>
                </div>
              ))}
              {(!summary?.datasets || summary.datasets.length === 0) && (
                <p className="text-xs text-gray-600 py-4 text-center">No data collected yet</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// --- Shared Components ---

function MiniStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="bg-surface/50 rounded-lg p-2">
      <p className="text-[10px] text-gray-500">{label}</p>
      <p className={`text-xs font-mono font-bold ${color || 'text-gray-200'}`}>{value}</p>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[10px] text-gray-500 mb-1 block">{label}</label>
      {children}
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-8">
      <Loader2 className="h-5 w-5 text-accent animate-spin" />
    </div>
  );
}
