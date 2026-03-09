import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Zap,
  Play,
  Square,
  Plus,
  Loader2,
  Activity,
  Settings2,
} from 'lucide-react';
import {
  fetchStrategies,
  createStrategy,
  startStrategy,
  stopStrategy,
  fetchStrategyStatus,
} from '../api/strategies';
import type { StrategyEngineItem, StrategyRuntimeStatus } from '../types/research';
import { STRATEGY_STATUS_COLORS } from '../utils/constants';
import { useAppStore } from '../store';

const STRATEGY_TEMPLATES: Record<
  string,
  { label: string; defaultConfig: Record<string, unknown> }
> = {
  sma_crossover: {
    label: 'SMA Crossover',
    defaultConfig: {
      symbol: 'EURUSD', fast_period: 10, slow_period: 30,
      order_quantity: '10000', interval: '1h',
    },
  },
  rsi: {
    label: 'RSI Mean Reversion',
    defaultConfig: {
      symbol: 'AAPL', rsi_period: 14, oversold: 30, overbought: 70,
      order_quantity: '50', interval: '1d',
    },
  },
  bollinger: {
    label: 'Bollinger Bands',
    defaultConfig: {
      symbol: 'GBPUSD', bb_period: 20, num_std: 2.0,
      order_quantity: '10000', interval: '1h',
    },
  },
  macd: {
    label: 'MACD Trend Following',
    defaultConfig: {
      symbol: 'SPY', fast_ema: 12, slow_ema: 26, signal_period: 9,
      order_quantity: '100', interval: '1d',
    },
  },
};

const DEMO_STRATEGIES: StrategyEngineItem[] = [
  {
    id: '1', name: 'EUR/USD SMA Crossover', description: 'Fast/slow SMA crossover on EUR/USD hourly',
    strategy_type: 'sma_crossover', status: 'ACTIVE', trading_mode: 'paper',
    config_json: { symbol: 'EURUSD', fast_period: 10, slow_period: 30, order_quantity: '10000', interval: '1h' },
    created_at: '2026-03-05T09:00:00Z', updated_at: '2026-03-09T14:00:00Z',
  },
  {
    id: '2', name: 'AAPL RSI Mean Revert', description: 'RSI oversold/overbought on Apple daily',
    strategy_type: 'rsi', status: 'ACTIVE', trading_mode: 'paper',
    config_json: { symbol: 'AAPL', rsi_period: 14, oversold: 30, overbought: 70, order_quantity: '50', interval: '1d' },
    created_at: '2026-03-06T10:30:00Z', updated_at: '2026-03-09T14:00:00Z',
  },
  {
    id: '3', name: 'SPY MACD Trend', description: 'MACD trend following on S&P 500 ETF',
    strategy_type: 'macd', status: 'STOPPED', trading_mode: 'paper',
    config_json: { symbol: 'SPY', fast_ema: 12, slow_ema: 26, signal_period: 9, order_quantity: '100', interval: '1d' },
    created_at: '2026-03-04T14:00:00Z', updated_at: '2026-03-08T16:00:00Z',
  },
  {
    id: '4', name: 'GBP/USD Bollinger', description: 'Bollinger band breakout on GBP/USD',
    strategy_type: 'bollinger', status: 'STOPPED', trading_mode: 'paper',
    config_json: { symbol: 'GBPUSD', bb_period: 20, num_std: 2.0, order_quantity: '10000', interval: '1h' },
    created_at: '2026-03-03T11:00:00Z', updated_at: '2026-03-07T09:00:00Z',
  },
];

function StatusBadge({ status }: { status: string }) {
  const s = status.toLowerCase();
  const config = STRATEGY_STATUS_COLORS[s] ?? STRATEGY_STATUS_COLORS.stopped;
  return (
    <span className={`badge ${config.bg} ${config.text} text-[10px]`}>
      <span className={`w-1.5 h-1.5 rounded-full ${config.dot} mr-1.5`} />
      {status.toUpperCase()}
    </span>
  );
}

export default function StrategiesPage() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((s) => s.addNotification);
  const [showCreate, setShowCreate] = useState(false);
  const [createType, setCreateType] = useState('sma_crossover');
  const [createName, setCreateName] = useState('');
  const [createConfig, setCreateConfig] = useState(
    JSON.stringify(STRATEGY_TEMPLATES.sma_crossover.defaultConfig, null, 2)
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: strategies } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
    refetchInterval: 10000,
  });

  const { data: runtimeStatus } = useQuery({
    queryKey: ['strategy-status', selectedId],
    queryFn: () => fetchStrategyStatus(selectedId!),
    enabled: !!selectedId,
    refetchInterval: 5000,
  });

  const createMut = useMutation({
    mutationFn: createStrategy,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      addNotification({ type: 'success', title: 'Strategy Created', message: `${data.name} created successfully` });
      setShowCreate(false);
      setCreateName('');
    },
    onError: (err: Error) => {
      addNotification({ type: 'error', title: 'Create Failed', message: err.message });
    },
  });

  const startMut = useMutation({
    mutationFn: startStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      queryClient.invalidateQueries({ queryKey: ['strategy-status'] });
      addNotification({ type: 'success', title: 'Strategy Started', message: 'Strategy is now running' });
    },
    onError: (err: Error) => {
      addNotification({ type: 'error', title: 'Start Failed', message: err.message });
    },
  });

  const stopMut = useMutation({
    mutationFn: stopStrategy,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      queryClient.invalidateQueries({ queryKey: ['strategy-status'] });
      addNotification({ type: 'warning', title: 'Strategy Stopped', message: 'Strategy has been stopped' });
    },
    onError: (err: Error) => {
      addNotification({ type: 'error', title: 'Stop Failed', message: err.message });
    },
  });

  const handleCreate = () => {
    try {
      const config = JSON.parse(createConfig);
      createMut.mutate({
        name: createName || `${createType}-${Date.now().toString(36)}`,
        strategy_type: createType,
        config_json: config,
      });
    } catch {
      addNotification({ type: 'error', title: 'Invalid JSON', message: 'Check config syntax' });
    }
  };

  const displayStrategies = strategies?.length ? strategies : DEMO_STRATEGIES;

  const isRunning = (s: StrategyEngineItem) =>
    s.status.toLowerCase() === 'running' || s.status.toLowerCase() === 'active';

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Zap className="h-6 w-6 text-accent" />
            Strategy Engine
          </h1>
          <p className="text-sm text-gray-500 mt-1">Forex &amp; stock quantitative strategies</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-accent/15 text-accent hover:bg-accent/25 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Strategy
        </button>
      </div>

      {showCreate && (
        <div className="card border border-accent/30">
          <h3 className="text-sm font-semibold text-gray-200 mb-4">Create Strategy</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Name</label>
              <input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="My SMA Strategy"
                className="input-field w-full"
              />
            </div>
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Strategy Type</label>
              <select
                value={createType}
                onChange={(e) => {
                  setCreateType(e.target.value);
                  const t = STRATEGY_TEMPLATES[e.target.value];
                  if (t) setCreateConfig(JSON.stringify(t.defaultConfig, null, 2));
                }}
                className="input-field w-full"
              >
                {Object.entries(STRATEGY_TEMPLATES).map(([k, v]) => (
                  <option key={k} value={k}>{v.label}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="mb-4">
            <label className="text-xs text-gray-500 mb-1 block">Config JSON</label>
            <textarea
              value={createConfig}
              onChange={(e) => setCreateConfig(e.target.value)}
              rows={6}
              className="input-field w-full font-mono text-xs"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors">
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={createMut.isPending}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-accent text-white hover:bg-accent-hover transition-colors disabled:opacity-50"
            >
              {createMut.isPending && <Loader2 className="h-3 w-3 animate-spin" />}
              Create
            </button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-3">
          {displayStrategies.map((strategy: StrategyEngineItem) => {
            const running = isRunning(strategy);
            const selected = selectedId === strategy.id;
            return (
              <div
                key={strategy.id}
                onClick={() => setSelectedId(strategy.id)}
                className={`card cursor-pointer transition-colors ${
                  selected ? 'border-accent/40 bg-accent/5' : 'hover:border-surface-border/80'
                }`}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold text-gray-200">{strategy.name}</h3>
                    <p className="text-xs text-gray-500 mt-0.5">
                      {STRATEGY_TEMPLATES[strategy.strategy_type]?.label ?? strategy.strategy_type}
                      {' · '}{strategy.trading_mode}
                    </p>
                  </div>
                  <StatusBadge status={strategy.status} />
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 mb-4 text-xs">
                  {Object.entries(strategy.config_json ?? {}).slice(0, 6).map(([k, v]) => (
                    <div key={k} className="flex justify-between">
                      <span className="text-gray-500">{k.replace(/_/g, ' ')}</span>
                      <span className="text-gray-300 font-mono">{String(v)}</span>
                    </div>
                  ))}
                </div>
                <div className="flex gap-2">
                  {running ? (
                    <button
                      onClick={(e) => { e.stopPropagation(); stopMut.mutate(strategy.id); }}
                      disabled={stopMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors disabled:opacity-50"
                    >
                      <Square className="h-3 w-3" /> Stop
                    </button>
                  ) : (
                    <button
                      onClick={(e) => { e.stopPropagation(); startMut.mutate(strategy.id); }}
                      disabled={startMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors disabled:opacity-50"
                    >
                      <Play className="h-3 w-3" /> Start
                    </button>
                  )}
                </div>
                <div className="text-[10px] text-gray-600 mt-2">
                  Created {new Date(strategy.created_at).toLocaleDateString()}
                </div>
              </div>
            );
          })}
        </div>

        <div className="card h-fit sticky top-4">
          {selectedId && runtimeStatus ? (
            <RuntimeStatusPanel status={runtimeStatus} />
          ) : selectedId ? (
            <div className="text-center py-8">
              <Loader2 className="h-5 w-5 text-accent animate-spin mx-auto mb-2" />
              <p className="text-gray-500 text-xs">Loading status...</p>
            </div>
          ) : (
            <div className="text-center py-8">
              <Settings2 className="h-6 w-6 text-gray-600 mx-auto mb-2" />
              <p className="text-gray-500 text-xs">Select a strategy to view runtime details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function RuntimeStatusPanel({ status }: { status: StrategyRuntimeStatus }) {
  const colorForPnl = (v: number) => v > 0 ? 'text-green-400' : v < 0 ? 'text-red-400' : 'text-gray-400';
  const realizedNum = parseFloat(status.pnl?.realized_pnl ?? '0');
  const unrealizedNum = parseFloat(status.pnl?.unrealized_pnl ?? '0');
  const netNum = realizedNum + unrealizedNum;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Activity className="h-4 w-4 text-accent" />
        <h3 className="text-sm font-semibold text-gray-200">Runtime Status</h3>
      </div>
      <StatusBadge status={status.status} />
      <div className="space-y-2 text-xs">
        {status.uptime_seconds != null && <Row label="Uptime" value={fmtUp(status.uptime_seconds)} />}
        <Row label="Ticks" value={status.ticks_processed.toLocaleString()} />
        <Row label="Orders Submitted" value={status.orders_submitted.toLocaleString()} />
        <Row label="Orders Filled" value={status.orders_filled.toLocaleString()} />
        <Row label="Active Orders" value={status.active_orders.toString()} />
      </div>
      {status.pnl && (
        <div className="border-t border-surface-border pt-3 space-y-2 text-xs">
          <h4 className="text-gray-400 font-medium">P&amp;L</h4>
          <Row label="Realized" value={`$${realizedNum.toFixed(2)}`} vc={colorForPnl(realizedNum)} />
          <Row label="Unrealized" value={`$${unrealizedNum.toFixed(2)}`} vc={colorForPnl(unrealizedNum)} />
          <Row label="Net" value={`$${netNum.toFixed(2)}`} vc={colorForPnl(netNum)} />
          <Row label="Total Trades" value={status.pnl.total_trades.toString()} />
          <Row label="Win Rate" value={`${(status.pnl.win_rate * 100).toFixed(1)}%`} />
          <Row label="Commission" value={`$${parseFloat(status.pnl.total_commission).toFixed(2)}`} />
        </div>
      )}
      {status.current_inventory && Object.keys(status.current_inventory).length > 0 && (
        <div className="border-t border-surface-border pt-3 space-y-2 text-xs">
          <h4 className="text-gray-400 font-medium">Inventory</h4>
          {Object.entries(status.current_inventory).map(([sym, qty]) => (
            <Row key={sym} label={sym} value={String(qty)} />
          ))}
        </div>
      )}
    </div>
  );
}

function Row({ label, value, vc }: { label: string; value: string; vc?: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className={`font-mono ${vc ?? 'text-gray-300'}`}>{value}</span>
    </div>
  );
}

function fmtUp(s: number): string {
  if (s < 60) return `${s.toFixed(0)}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}
