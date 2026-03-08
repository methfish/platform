import { useQuery } from '@tanstack/react-query';
import { AlertTriangle, Bell, LogOut, Power, User } from 'lucide-react';
import { useState } from 'react';
import { useAppStore } from '../../store';
import { useAuth } from '../../hooks/useAuth';
import { fetchRiskStatus } from '../../api/risk';
import { fetchTradingMode } from '../../api/admin';
import ConfirmDialog from '../common/ConfirmDialog';
import { toggleKillSwitch } from '../../api/risk';

export default function Header() {
  const { username } = useAuth();
  const { killSwitchActive, setKillSwitchActive, setTradingMode, notifications } = useAppStore();
  const { logout } = useAuth();
  const [showKillConfirm, setShowKillConfirm] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);

  const { data: tradingModeData } = useQuery({
    queryKey: ['tradingMode'],
    queryFn: fetchTradingMode,
    refetchInterval: 10000,
  });

  useQuery({
    queryKey: ['riskStatusHeader'],
    queryFn: fetchRiskStatus,
    refetchInterval: 5000,
    select: (data) => {
      setKillSwitchActive(data.kill_switch_active);
      setTradingMode(data.trading_mode);
      return data;
    },
  });

  const mode = tradingModeData?.mode ?? 'paper';
  const isLive = mode === 'live';
  const unreadCount = notifications.filter((n) => n.type === 'error' || n.type === 'warning').length;

  const handleKillSwitch = async () => {
    try {
      const result = await toggleKillSwitch(!killSwitchActive);
      setKillSwitchActive(result.kill_switch_active);
    } catch {
      // Error handled by interceptor
    }
    setShowKillConfirm(false);
  };

  return (
    <>
      <header className="h-14 bg-surface-raised border-b border-surface-border flex items-center justify-between px-6 shrink-0">
        <div className="flex items-center gap-4">
          {/* Environment Badge - ALWAYS VISIBLE */}
          <div
            className={`badge font-bold text-xs tracking-wider ${
              isLive
                ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                : 'bg-green-500/20 text-green-400 border border-green-500/40'
            }`}
          >
            {isLive && <AlertTriangle className="h-3 w-3 mr-1" />}
            {isLive ? 'LIVE' : 'PAPER'}
          </div>

          {/* Kill switch indicator */}
          {killSwitchActive && (
            <div className="badge bg-red-600/30 text-red-300 border border-red-500/50 animate-pulse">
              <Power className="h-3 w-3 mr-1" />
              KILL SWITCH ACTIVE
            </div>
          )}
        </div>

        <div className="flex items-center gap-3">
          {/* Kill Switch Button */}
          <button
            onClick={() => setShowKillConfirm(true)}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-semibold transition-all duration-150 ${
              killSwitchActive
                ? 'bg-yellow-600 hover:bg-yellow-700 text-white'
                : 'bg-red-600 hover:bg-red-700 text-white'
            }`}
          >
            <Power className="h-4 w-4" />
            {killSwitchActive ? 'Deactivate Kill Switch' : 'Kill Switch'}
          </button>

          {/* Notifications */}
          <div className="relative">
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-surface-overlay transition-colors"
            >
              <Bell className="h-5 w-5" />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 h-4 w-4 bg-red-500 rounded-full text-[10px] font-bold text-white flex items-center justify-center">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </button>

            {showNotifications && (
              <div className="absolute right-0 top-full mt-2 w-80 bg-surface-raised border border-surface-border rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto">
                <div className="p-3 border-b border-surface-border">
                  <h3 className="text-sm font-semibold text-gray-200">Notifications</h3>
                </div>
                {notifications.length === 0 ? (
                  <div className="p-4 text-center text-gray-500 text-sm">No notifications</div>
                ) : (
                  <div className="divide-y divide-surface-border">
                    {notifications
                      .slice()
                      .reverse()
                      .slice(0, 20)
                      .map((n) => (
                        <div key={n.id} className="p-3">
                          <div className="flex items-center gap-2 mb-1">
                            <span
                              className={`w-2 h-2 rounded-full ${
                                n.type === 'error'
                                  ? 'bg-red-400'
                                  : n.type === 'warning'
                                  ? 'bg-yellow-400'
                                  : n.type === 'success'
                                  ? 'bg-green-400'
                                  : 'bg-blue-400'
                              }`}
                            />
                            <span className="text-xs font-medium text-gray-300">{n.title}</span>
                          </div>
                          <p className="text-xs text-gray-500 ml-4">{n.message}</p>
                        </div>
                      ))}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* User */}
          <div className="flex items-center gap-2 pl-3 border-l border-surface-border">
            <User className="h-4 w-4 text-gray-400" />
            <span className="text-sm text-gray-300">{username ?? 'Operator'}</span>
            <button
              onClick={logout}
              className="p-1.5 rounded-lg text-gray-400 hover:text-gray-200 hover:bg-surface-overlay transition-colors"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </header>

      <ConfirmDialog
        open={showKillConfirm}
        title={killSwitchActive ? 'Deactivate Kill Switch' : 'Activate Kill Switch'}
        message={
          killSwitchActive
            ? 'This will re-enable all trading activity. Are you sure?'
            : 'This will IMMEDIATELY halt all trading activity and cancel all open orders. This action is critical. Are you sure?'
        }
        confirmLabel={killSwitchActive ? 'Deactivate' : 'ACTIVATE KILL SWITCH'}
        variant={killSwitchActive ? 'warning' : 'danger'}
        onConfirm={handleKillSwitch}
        onCancel={() => setShowKillConfirm(false)}
      />
    </>
  );
}
