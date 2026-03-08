import { useState } from 'react';
import { Power, ShieldAlert } from 'lucide-react';
import { useAppStore } from '../../store';
import { toggleKillSwitch } from '../../api/risk';
import ConfirmDialog from '../common/ConfirmDialog';

export default function KillSwitch() {
  const { killSwitchActive, setKillSwitchActive, addNotification } = useAppStore();
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleToggle = async () => {
    setLoading(true);
    try {
      const result = await toggleKillSwitch(!killSwitchActive);
      setKillSwitchActive(result.kill_switch_active);
      addNotification({
        type: result.kill_switch_active ? 'warning' : 'success',
        title: 'Kill Switch',
        message: result.kill_switch_active
          ? 'Kill switch activated - all trading halted'
          : 'Kill switch deactivated - trading resumed',
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Kill Switch Error',
        message: 'Failed to toggle kill switch',
      });
    } finally {
      setLoading(false);
      setShowConfirm(false);
    }
  };

  return (
    <>
      <div
        className={`card border-2 ${
          killSwitchActive ? 'border-red-500/50 bg-red-500/5' : 'border-surface-border'
        }`}
      >
        <div className="flex items-center gap-3 mb-4">
          <ShieldAlert
            className={`h-6 w-6 ${killSwitchActive ? 'text-red-400' : 'text-gray-400'}`}
          />
          <div>
            <h3 className="font-semibold text-gray-200">Emergency Kill Switch</h3>
            <p className="text-xs text-gray-500">
              {killSwitchActive
                ? 'Trading is currently HALTED'
                : 'Immediately halt all trading activity'}
            </p>
          </div>
        </div>

        <button
          onClick={() => setShowConfirm(true)}
          disabled={loading}
          className={`w-full py-4 rounded-xl text-lg font-bold flex items-center justify-center gap-3 transition-all duration-200 ${
            killSwitchActive
              ? 'bg-yellow-600 hover:bg-yellow-700 text-white shadow-lg shadow-yellow-600/20'
              : 'bg-red-600 hover:bg-red-700 text-white shadow-lg shadow-red-600/30 hover:shadow-red-600/50'
          } disabled:opacity-50`}
        >
          <Power className={`h-6 w-6 ${killSwitchActive ? '' : 'animate-pulse'}`} />
          {loading
            ? 'Processing...'
            : killSwitchActive
            ? 'DEACTIVATE KILL SWITCH'
            : 'ACTIVATE KILL SWITCH'}
        </button>

        {killSwitchActive && (
          <p className="text-xs text-red-400/70 mt-3 text-center">
            All open orders have been cancelled. No new orders will be accepted.
          </p>
        )}
      </div>

      <ConfirmDialog
        open={showConfirm}
        title={killSwitchActive ? 'Deactivate Kill Switch' : 'Activate Kill Switch'}
        message={
          killSwitchActive
            ? 'This will re-enable all trading activity and allow strategies to place new orders. Proceed?'
            : 'WARNING: This will IMMEDIATELY cancel all open orders and halt ALL trading activity across all exchanges and strategies. This is an emergency action. Are you absolutely sure?'
        }
        confirmLabel={killSwitchActive ? 'Deactivate' : 'YES, HALT ALL TRADING'}
        variant={killSwitchActive ? 'warning' : 'danger'}
        onConfirm={handleToggle}
        onCancel={() => setShowConfirm(false)}
      />
    </>
  );
}
