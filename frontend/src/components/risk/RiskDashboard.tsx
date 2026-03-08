import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Loader2 } from 'lucide-react';
import { fetchRiskStatus } from '../../api/risk';
import RiskCheckStatus from './RiskCheckStatus';
import { formatCurrency } from '../../utils/formatters';

export default function RiskDashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['riskStatus'],
    queryFn: fetchRiskStatus,
    refetchInterval: 5000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 text-accent animate-spin" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="card text-center py-8">
        <ShieldAlert className="h-8 w-8 text-red-400 mx-auto mb-2" />
        <p className="text-gray-400 text-sm">Failed to load risk status</p>
      </div>
    );
  }

  return (
    <div>
      {/* Kill Switch Banner */}
      {data.kill_switch_active && (
        <div className="mb-4 p-3 bg-red-600/20 border border-red-500/40 rounded-lg flex items-center gap-3">
          <ShieldAlert className="h-5 w-5 text-red-400 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-300">Kill Switch Active</p>
            <p className="text-xs text-red-400/80">All trading is halted. Deactivate to resume.</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <RiskCheckStatus
          label="Daily Loss"
          current={Math.abs(data.daily_loss)}
          limit={data.daily_loss_limit}
          format={(v) => formatCurrency(v)}
        />
        <RiskCheckStatus
          label="Max Position Size"
          current={data.current_max_position}
          limit={data.max_position_size}
          format={(v) => formatCurrency(v)}
        />
        <RiskCheckStatus
          label="Open Orders"
          current={data.open_orders_count}
          limit={data.max_open_orders}
        />
        <RiskCheckStatus
          label="Margin Usage"
          current={data.margin_usage_percent}
          limit={data.margin_limit_percent}
          unit="%"
        />
        <RiskCheckStatus
          label="Daily Volume"
          current={data.daily_volume}
          limit={data.daily_volume_limit}
          format={(v) => formatCurrency(v)}
        />
      </div>
    </div>
  );
}
