import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, FileText, Zap } from 'lucide-react';
import { fetchTradingMode, confirmLiveMode } from '../../api/admin';
import { useAppStore } from '../../store';
import ConfirmDialog from '../common/ConfirmDialog';

export default function TradingModeSwitch() {
  const queryClient = useQueryClient();
  const { addNotification } = useAppStore();
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['tradingMode'],
    queryFn: fetchTradingMode,
    refetchInterval: 10000,
  });

  const isLive = data?.mode === 'live';
  const isLiveEnabled = data?.live_enabled ?? false;

  const handleConfirmLive = async () => {
    setLoading(true);
    try {
      await confirmLiveMode();
      queryClient.invalidateQueries({ queryKey: ['tradingMode'] });
      addNotification({
        type: 'warning',
        title: 'Live Mode Confirmed',
        message: 'Trading mode confirmed for LIVE trading with real funds',
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Mode Switch Failed',
        message: 'Failed to confirm live mode',
      });
    } finally {
      setLoading(false);
      setShowConfirm(false);
    }
  };

  if (isLoading) {
    return <div className="card animate-pulse h-32" />;
  }

  return (
    <>
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-semibold text-gray-200">Trading Mode</h3>
          <div
            className={`badge font-bold ${
              isLive
                ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                : 'bg-green-500/20 text-green-400 border border-green-500/40'
            }`}
          >
            {isLive ? (
              <>
                <Zap className="h-3 w-3 mr-1" />
                LIVE
              </>
            ) : (
              <>
                <FileText className="h-3 w-3 mr-1" />
                PAPER
              </>
            )}
          </div>
        </div>

        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Current Mode</span>
            <span className={`font-medium ${isLive ? 'text-red-400' : 'text-green-400'}`}>
              {isLive ? 'Live Trading' : 'Paper Trading'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Live Enabled</span>
            <span className={isLiveEnabled ? 'text-yellow-400' : 'text-gray-500'}>
              {isLiveEnabled ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Operator Confirmed</span>
            <span className={data?.operator_confirmed ? 'text-green-400' : 'text-gray-500'}>
              {data?.operator_confirmed ? 'Yes' : 'No'}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-400">Kill Switch</span>
            <span className={data?.kill_switch ? 'text-red-400' : 'text-gray-500'}>
              {data?.kill_switch ? 'Active' : 'Inactive'}
            </span>
          </div>
        </div>

        {isLiveEnabled && !data?.operator_confirmed && (
          <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
            <div className="flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 text-yellow-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs text-yellow-300 font-medium">
                  Live mode is enabled but requires operator confirmation
                </p>
                <button
                  onClick={() => setShowConfirm(true)}
                  disabled={loading}
                  className="mt-2 px-4 py-1.5 bg-yellow-600 hover:bg-yellow-700 text-white text-xs font-semibold rounded-lg transition-colors disabled:opacity-50"
                >
                  {loading ? 'Confirming...' : 'Confirm Live Mode'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={showConfirm}
        title="Confirm Live Trading Mode"
        message="You are about to confirm LIVE trading mode. This means real orders will be placed on real exchanges with real funds. This is a critical action that cannot be undone without administrator intervention. Are you absolutely sure?"
        confirmLabel="I CONFIRM LIVE TRADING"
        variant="danger"
        onConfirm={handleConfirmLive}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}
