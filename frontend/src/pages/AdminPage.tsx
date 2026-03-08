import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Settings,
  Server,
  Clock,
  FileSearch,
  Loader2,
  CheckCircle,
  XCircle,
  RefreshCw,
  Shield,
} from 'lucide-react';
import {
  fetchHealth,
  fetchExchangeStatus,
  fetchAuditLogs,
  fetchReconciliationRuns,
  triggerReconciliation,
} from '../api/admin';
import KillSwitch from '../components/admin/KillSwitch';
import TradingModeSwitch from '../components/admin/TradingModeSwitch';
import StatusIndicator from '../components/common/StatusIndicator';
import { formatDateTime, formatUptime } from '../utils/formatters';
import { useAppStore } from '../store';

export default function AdminPage() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((s) => s.addNotification);

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

  const { data: auditLogs, isLoading: logsLoading } = useQuery({
    queryKey: ['auditLogs'],
    queryFn: () => fetchAuditLogs({ limit: 30 }),
    refetchInterval: 15000,
  });

  const { data: reconRuns, isLoading: reconLoading } = useQuery({
    queryKey: ['reconciliation'],
    queryFn: fetchReconciliationRuns,
    refetchInterval: 15000,
  });

  const reconMut = useMutation({
    mutationFn: triggerReconciliation,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation'] });
      addNotification({
        type: 'info',
        title: 'Reconciliation',
        message: 'Reconciliation run triggered',
      });
    },
    onError: (err: Error) => {
      addNotification({
        type: 'error',
        title: 'Reconciliation Failed',
        message: err.message,
      });
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <Settings className="h-6 w-6 text-accent" />
          Administration
        </h1>
        <p className="text-sm text-gray-500 mt-1">System management and monitoring</p>
      </div>

      {/* Top Row: Kill Switch + Trading Mode */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <KillSwitch />
        <TradingModeSwitch />
      </div>

      {/* System Health + Exchange Status */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* System Health */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Server className="h-4 w-4 text-gray-400" />
            <h3 className="text-sm font-semibold text-gray-200">System Health</h3>
          </div>

          {health ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Overall Status</span>
                <StatusIndicator
                  status={health.status === 'healthy' ? 'green' : 'red'}
                  label={health.status}
                  pulse={health.status === 'healthy'}
                  size="md"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Version</span>
                <span className="text-sm text-gray-300 font-mono">{health.version}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Uptime</span>
                <span className="text-sm text-gray-300 font-mono">{formatUptime(health.uptime)}</span>
              </div>

              {health.components && Object.entries(health.components).length > 0 && (
                <div className="pt-3 mt-3 border-t border-surface-border">
                  <p className="text-xs text-gray-500 mb-2">Components</p>
                  <div className="space-y-2">
                    {Object.entries(health.components).map(([name, comp]) => (
                      <div key={name} className="flex items-center justify-between">
                        <span className="text-xs text-gray-400 capitalize">{name}</span>
                        <div className="flex items-center gap-2">
                          {comp.latency_ms !== undefined && (
                            <span className="text-[10px] text-gray-600 font-mono">
                              {comp.latency_ms}ms
                            </span>
                          )}
                          <StatusIndicator
                            status={comp.status === 'healthy' || comp.status === 'ok' ? 'green' : 'red'}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-5 w-5 text-accent animate-spin" />
            </div>
          )}
        </div>

        {/* Exchange Status */}
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Shield className="h-4 w-4 text-gray-400" />
            <h3 className="text-sm font-semibold text-gray-200">Exchange Connections</h3>
          </div>

          <div className="space-y-3">
            {(exchanges ?? []).map((ex) => (
              <div
                key={ex.exchange}
                className={`p-3 rounded-lg border ${
                  ex.connected
                    ? 'bg-green-500/5 border-green-500/20'
                    : 'bg-red-500/5 border-red-500/20'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <StatusIndicator status={ex.connected ? 'green' : 'red'} pulse={ex.connected} />
                    <span className="text-sm font-medium text-gray-200 capitalize">
                      {ex.exchange}
                    </span>
                  </div>
                  <span className={`text-xs ${ex.connected ? 'text-green-400' : 'text-red-400'}`}>
                    {ex.connected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
                <div className="flex items-center gap-4 mt-2 ml-6 text-[10px] text-gray-500">
                  <span>Latency: {ex.latency_ms}ms</span>
                  <span>Rate Limit: {ex.rate_limit_remaining} remaining</span>
                  <span>Last HB: {formatDateTime(ex.last_heartbeat)}</span>
                </div>
              </div>
            ))}
            {(!exchanges || exchanges.length === 0) && (
              <p className="text-sm text-gray-600 text-center py-4">No exchange connections</p>
            )}
          </div>
        </div>
      </div>

      {/* Reconciliation */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <FileSearch className="h-4 w-4 text-gray-400" />
            <h3 className="text-sm font-semibold text-gray-200">Reconciliation</h3>
          </div>
          <button
            onClick={() => reconMut.mutate()}
            disabled={reconMut.isPending}
            className="btn-secondary text-xs flex items-center gap-1.5"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${reconMut.isPending ? 'animate-spin' : ''}`} />
            {reconMut.isPending ? 'Running...' : 'Run Reconciliation'}
          </button>
        </div>

        {reconLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 text-accent animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="table-header">ID</th>
                  <th className="table-header">Exchange</th>
                  <th className="table-header">Status</th>
                  <th className="table-header">Started</th>
                  <th className="table-header">Completed</th>
                  <th className="table-header">Discrepancies</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {(reconRuns ?? []).map((run) => (
                  <tr key={run.id} className="hover:bg-surface-overlay/30">
                    <td className="table-cell font-mono text-xs text-gray-500">
                      {run.id.slice(0, 8)}
                    </td>
                    <td className="table-cell text-gray-300 capitalize text-xs">{run.exchange}</td>
                    <td className="table-cell">
                      <span
                        className={`badge text-[10px] ${
                          run.status === 'completed'
                            ? 'bg-green-500/15 text-green-400'
                            : run.status === 'failed'
                            ? 'bg-red-500/15 text-red-400'
                            : run.status === 'running'
                            ? 'bg-blue-500/15 text-blue-400'
                            : 'bg-yellow-500/15 text-yellow-400'
                        }`}
                      >
                        {run.status === 'completed' && <CheckCircle className="h-3 w-3 mr-1" />}
                        {run.status === 'failed' && <XCircle className="h-3 w-3 mr-1" />}
                        {run.status}
                      </span>
                    </td>
                    <td className="table-cell text-xs text-gray-400">
                      {formatDateTime(run.started_at)}
                    </td>
                    <td className="table-cell text-xs text-gray-400">
                      {run.completed_at ? formatDateTime(run.completed_at) : '-'}
                    </td>
                    <td className="table-cell">
                      <span
                        className={`font-mono text-xs ${
                          run.discrepancies > 0 ? 'text-red-400 font-medium' : 'text-gray-500'
                        }`}
                      >
                        {run.discrepancies}
                      </span>
                    </td>
                  </tr>
                ))}
                {(!reconRuns || reconRuns.length === 0) && (
                  <tr>
                    <td colSpan={6} className="table-cell text-center text-gray-600 py-6">
                      No reconciliation runs
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Audit Logs */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Clock className="h-4 w-4 text-gray-400" />
          <h3 className="text-sm font-semibold text-gray-200">Audit Log</h3>
        </div>

        {logsLoading ? (
          <div className="flex items-center justify-center py-6">
            <Loader2 className="h-5 w-5 text-accent animate-spin" />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-surface-border">
                  <th className="table-header">Timestamp</th>
                  <th className="table-header">Actor</th>
                  <th className="table-header">Action</th>
                  <th className="table-header">IP Address</th>
                  <th className="table-header">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-border/50">
                {(auditLogs ?? []).map((log) => (
                  <tr key={log.id} className="hover:bg-surface-overlay/30">
                    <td className="table-cell text-xs text-gray-400 font-mono">
                      {formatDateTime(log.timestamp)}
                    </td>
                    <td className="table-cell text-xs text-gray-300">{log.actor}</td>
                    <td className="table-cell">
                      <span className="badge bg-surface-overlay text-gray-300 text-[10px]">
                        {log.action}
                      </span>
                    </td>
                    <td className="table-cell text-xs text-gray-500 font-mono">
                      {log.ip_address}
                    </td>
                    <td className="table-cell text-xs text-gray-500 max-w-xs truncate">
                      {JSON.stringify(log.details)}
                    </td>
                  </tr>
                ))}
                {(!auditLogs || auditLogs.length === 0) && (
                  <tr>
                    <td colSpan={5} className="table-cell text-center text-gray-600 py-6">
                      No audit logs
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
