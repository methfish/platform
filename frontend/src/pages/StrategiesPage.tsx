import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Zap,
  Play,
  Square,
  Plus,
  Loader2,
  AlertCircle,
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
  MARKET_MAKING: {
    label: 'Market Making',
    defaultConfig: {
      symbol: 'EURUSD',
      spread_bps: 10,
      order_quantity: '10000',
      num_levels: 2,
      max_inventory: '50000',
      inventory_skew_factor: 0.5,
    },
  },
  ARBITRAGE: {
    label: 'Cross-Exchange Arbitrage',
    defaultConfig: {
      symbol: 'EURUSD',
      exchange_a: 'paper',
      exchange_b: 'paper',
      min_spread_bps: 5,
      order_quantity: '10000',
      max_open_arbs: 3,
    },
  },
};

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
  const [createType, setCreateType] = useState('MARKET_MAKING');
  const [createName, setCreateName] = useState('');
  const [createConfig, setCreateConfig] = useState(
    JSON.stringify(STRATEGY_TEMPLATES.MARKET_MAKING.defaultConfig, null, 2)
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const {
    data: strategies,
    isLoading,
    error,
  } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
    refetchInterval: 10000,
  });

  // Status for the selected strategy
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
      addNotification({
        type: 'success',
        title: 'Strategy Created',
        message: `${data.name} created successfully`,
      });
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

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 className="h-6 w-6 text-accent animate-spin" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card text-center py-12">
        <AlertCircle className="h-8 w-8 text-red-400 mx-auto mb-2" />
        <p className="text-gray-400 text-sm">Failed to load strategies</p>
      </div>
    );
  }

  const isRunning = (s: StrategyEngineItem) =>
    s.status.toLowerCase() === 'running' || s.status.toLowerCase() === 'active';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
            <Zap className="h-6 w-6 text-accent" />
            Strategy Engine
          </h1>
          <p className="text-sm text-gray-500 mt-1">
            Forex &amp; stock trading strategies
          </p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-accent/15 text-accent hover:bg-accent/25 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Strategy
        </button>
      </div>

      {/* Create Form */}
      {showCreate && (
        <div className="card border border-accent/30">
          <h3 className="text-sm font-semibold text-gray-200 mb-4">Create Strategy</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            <div>
              <label className="text-xs text-gray-500 mb-1 block">Name</label>
              <input
                value={createName}
                onChange={(e) => setCreateName(e.target.value)}
                placeholder="EUR-MM-1"
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
                  <option key={k} value={k}>
                    {v.label}
                  </option>
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
            <button
              onClick={() => setShowCreate(false)}
              className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 transition-colors"
            >
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

      {/* Strategy Grid + Detail Panel */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Strategy Cards */}
        <div className="lg:col-span-2 space-y-3">
          {(strategies ?? []).map((strategy: StrategyEngineItem) => {
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
                      {' · '}
                      {strategy.trading_mode}
                    </p>
                  </div>
                  <StatusBadge status={strategy.status} />
                </div>

                {/* Config Summary */}
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-x-4 gap-y-1 mb-4 text-xs">
                  {Object.entries(strategy.config_json ?? {})
                    .slice(0, 6)
                    .map(([k, v]) => (
                      <div key={k} className="flex justify-between">
                        <span className="text-gray-500">{k.replace(/_/g, ' ')}</span>
                        <span className="text-gray-300 font-mono">{String(v)}</span>
                      </div>
                    ))}
                </div>

                {/* Actions */}
                <div className="flex gap-2">
                  {running ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        stopMut.mutate(strategy.id);
                      }}
                      disabled={stopMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors disabled:opacity-50"
                    >
                      <Square className="h-3 w-3" />
                      Stop
                    </button>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        startMut.mutate(strategy.id);
                      }}
                      disabled={startMut.isPending}
                      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors disabled:opacity-50"
                    >
                      <Play className="h-3 w-3" />
                      Start
                    </button>
                  )}
                </div>

                <div className="text-[10px] text-gray-600 mt-2">
                  Created{' '}
                  {new Date(strategy.created_at).toLocaleDateString()}
                </div>
              </div>
            );
          })}

          {(!strategies || strategies.length === 0) && (
            <div className="card text-center py-12">
              <Zap className="h-8 w-8 text-gray-600 mx-auto mb-2" />
              <p className="text-gray-500 text-sm">No strategies yet</p>
              <p className="text-gray-600 text-xs mt-1">
                Click &quot;New Strategy&quot; to create a market maker or arbitrage strategy
              </p>
            </div>
          )}
        </div>

        {/* Detail Panel */}
        <div className="card h-fit sticky top-4">
          {selectedId && runtimeStatus ? (
            <RuntimeStatusPanel status={runtimeStatus} />
          ) : selectedId ? (
            <div className="text-center py-8">
              <Loader2 className="h-5 w-5 text-accent animate-spin mx-auto mb-2" />
              <p className="text-gray-500 text-xs">Loading status…</p>
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
  const colorForPnl = (v: number) =>
    v > 0 ? 'text-green-400' : v < 0 ? 'text-red-400' : 'text-gray-400';

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
        {status.uptime_seconds != null && (
          <Row label="Uptime" value={formatUptime(status.uptime_seconds)} />
        )}
        <Row label="Ticks" value={status.ticks_processed.toLocaleString()} />
        <Row label="Orders Submitted" value={status.orders_submitted.toLocaleString()} />
        <Row label="Orders Filled" value={status.orders_filled.toLocaleString()} />
        <Row label="Active Orders" value={status.active_orders.toString()} />
      </div>

      {/* P&L Section */}
      {status.pnl && (
        <div className="border-t border-surface-border pt-3 space-y-2 text-xs">
          <h4 className="text-gray-400 font-medium">P&amp;L</h4>
          <Row
            label="Realized"
            value={`$${realizedNum.toFixed(2)}`}
            valueClass={colorForPnl(realizedNum)}
          />
          <Row
            label="Unrealized"
            value={`$${unrealizedNum.toFixed(2)}`}
            valueClass={colorForPnl(unrealizedNum)}
          />
          <Row
            label="Net"
            value={`$${netNum.toFixed(2)}`}
            valueClass={colorForPnl(netNum)}
          />
          <Row label="Total Trades" value={status.pnl.total_trades.toString()} />
          <Row label="Win Rate" value={`${(status.pnl.win_rate * 100).toFixed(1)}%`} />
          <Row label="Commission" value={`$${parseFloat(status.pnl.total_commission).toFixed(2)}`} />
        </div>
      )}

      {/* Inventory */}
      {status.current_inventory && Object.keys(status.current_inventory).length > 0 && (
        <div className="border-t border-surface-border pt-3 space-y-2 text-xs">
          <h4 className="text-gray-400 font-medium">Inventory</h4>
          {Object.entries(status.current_inventory).map(([symbol, qty]) => (
            <Row key={symbol} label={symbol} value={String(qty)} />
          ))}
        </div>
      )}
    </div>
  );
}

function Row({
  label,
  value,
  valueClass,
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className={`font-mono ${valueClass ?? 'text-gray-300'}`}>{value}</span>
    </div>
  );
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds.toFixed(0)}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}
