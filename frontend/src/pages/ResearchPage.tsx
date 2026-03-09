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
  const { data: backtests, isLoading } = useQuery({
    queryKey: ['backtests'],
    queryFn: () => fetchBacktests({ limit: 50 }),
  });

  const { data: detail } = useQuery({
    queryKey: ['backtestDetail', selectedBt],
    queryFn: () => fetchBacktestDetail(selectedBt!),
    enabled: !!selectedBt,
  });

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
  const { data: summary, isLoading } = useQuery({
    queryKey: ['dataSummary'],
    queryFn: fetchDataSummary,
  });

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
