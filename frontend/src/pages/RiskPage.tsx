import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, AlertTriangle, Info, Zap, Loader2 } from 'lucide-react';
import RiskDashboard from '../components/risk/RiskDashboard';
import { fetchRiskEvents } from '../api/risk';
import { RISK_EVENT_COLORS } from '../utils/constants';
import { formatDateTime } from '../utils/formatters';

const EVENT_ICONS: Record<string, typeof Info> = {
  info: Info,
  warning: AlertTriangle,
  breach: ShieldAlert,
  kill_switch: Zap,
};

export default function RiskPage() {
  const { data: events, isLoading: eventsLoading } = useQuery({
    queryKey: ['riskEvents'],
    queryFn: () => fetchRiskEvents({ limit: 50 }),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <ShieldAlert className="h-6 w-6 text-accent" />
          Risk Management
        </h1>
        <p className="text-sm text-gray-500 mt-1">Monitor risk limits and events</p>
      </div>

      {/* Risk Dashboard */}
      <RiskDashboard />

      {/* Risk Events */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-200">Risk Events</h3>
          <span className="text-xs text-gray-500">
            {events?.total ?? 0} total events
          </span>
        </div>

        {eventsLoading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-5 w-5 text-accent animate-spin" />
          </div>
        ) : (
          <div className="space-y-2">
            {(events?.events ?? []).map((event) => {
              const colors = RISK_EVENT_COLORS[event.type] ?? RISK_EVENT_COLORS.info;
              const Icon = EVENT_ICONS[event.type] ?? Info;

              return (
                <div
                  key={event.id}
                  className={`p-3 rounded-lg border ${colors.bg} ${colors.border}`}
                >
                  <div className="flex items-start gap-3">
                    <Icon className={`h-4 w-4 mt-0.5 shrink-0 ${colors.text}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <span className={`text-xs font-semibold uppercase ${colors.text}`}>
                            {event.type.replace('_', ' ')}
                          </span>
                          <span className="text-xs text-gray-500">{event.rule}</span>
                        </div>
                        <span className="text-[10px] text-gray-600 shrink-0">
                          {formatDateTime(event.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-300 mt-1">{event.message}</p>
                    </div>
                  </div>
                </div>
              );
            })}

            {(!events?.events || events.events.length === 0) && (
              <div className="text-center py-8">
                <ShieldAlert className="h-8 w-8 text-gray-600 mx-auto mb-2" />
                <p className="text-gray-500 text-sm">No risk events recorded</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
