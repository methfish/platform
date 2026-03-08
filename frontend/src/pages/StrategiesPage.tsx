import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Brain, Play, Square, Loader2, AlertCircle } from 'lucide-react';
import { fetchStrategies, enableStrategy, disableStrategy } from '../api/strategies';
import { Strategy } from '../types/risk';
import { STRATEGY_STATUS_COLORS } from '../utils/constants';
import { formatCurrency, formatDateTime, pnlColor } from '../utils/formatters';
import { useAppStore } from '../store';
import StatusIndicator from '../components/common/StatusIndicator';

export default function StrategiesPage() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((s) => s.addNotification);

  const { data: strategies, isLoading, error } = useQuery({
    queryKey: ['strategies'],
    queryFn: fetchStrategies,
    refetchInterval: 10000,
  });

  const enableMut = useMutation({
    mutationFn: enableStrategy,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      addNotification({ type: 'success', title: 'Strategy Enabled', message: `${data.name} is now running` });
    },
    onError: (err: Error) => {
      addNotification({ type: 'error', title: 'Enable Failed', message: err.message });
    },
  });

  const disableMut = useMutation({
    mutationFn: disableStrategy,
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['strategies'] });
      addNotification({ type: 'warning', title: 'Strategy Disabled', message: `${data.name} has been stopped` });
    },
    onError: (err: Error) => {
      addNotification({ type: 'error', title: 'Disable Failed', message: err.message });
    },
  });

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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <Brain className="h-6 w-6 text-accent" />
          Strategies
        </h1>
        <p className="text-sm text-gray-500 mt-1">Manage automated trading strategies</p>
      </div>

      {/* Strategy Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {(strategies ?? []).map((strategy: Strategy) => {
          const statusConfig = STRATEGY_STATUS_COLORS[strategy.status] ?? STRATEGY_STATUS_COLORS.stopped;
          const isRunning = strategy.status === 'running';
          const isToggling = enableMut.isPending || disableMut.isPending;

          return (
            <div key={strategy.id} className="card hover:border-surface-border/80 transition-colors">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-semibold text-gray-200">{strategy.name}</h3>
                  <p className="text-xs text-gray-500 mt-0.5">{strategy.description}</p>
                </div>
                <span className={`badge ${statusConfig.bg} ${statusConfig.text} text-[10px]`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${statusConfig.dot} mr-1.5`} />
                  {strategy.status.toUpperCase()}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-x-4 gap-y-2 mb-4 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">Exchange</span>
                  <span className="text-gray-300 capitalize">{strategy.exchange}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Symbols</span>
                  <span className="text-gray-300">{strategy.symbols.join(', ')}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">P&L</span>
                  <span className={`font-mono font-medium ${pnlColor(strategy.pnl)}`}>
                    {strategy.pnl >= 0 ? '+' : ''}{formatCurrency(strategy.pnl)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Trades</span>
                  <span className="text-gray-300">{strategy.trade_count}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Last Trade</span>
                  <span className="text-gray-400">
                    {strategy.last_trade_at ? formatDateTime(strategy.last_trade_at) : 'Never'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Enabled</span>
                  <StatusIndicator
                    status={strategy.enabled ? 'green' : 'gray'}
                    label={strategy.enabled ? 'Yes' : 'No'}
                  />
                </div>
              </div>

              <div className="flex gap-2">
                {strategy.enabled ? (
                  <button
                    onClick={() => disableMut.mutate(strategy.id)}
                    disabled={isToggling}
                    className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 border border-red-500/20 transition-colors disabled:opacity-50"
                  >
                    <Square className="h-3.5 w-3.5" />
                    Disable
                  </button>
                ) : (
                  <button
                    onClick={() => enableMut.mutate(strategy.id)}
                    disabled={isToggling}
                    className="flex-1 flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-medium bg-green-500/10 text-green-400 hover:bg-green-500/20 border border-green-500/20 transition-colors disabled:opacity-50"
                  >
                    <Play className="h-3.5 w-3.5" />
                    Enable
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {(!strategies || strategies.length === 0) && (
          <div className="col-span-2 card text-center py-12">
            <Brain className="h-8 w-8 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">No strategies configured</p>
          </div>
        )}
      </div>
    </div>
  );
}
