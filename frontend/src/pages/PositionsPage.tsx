import { BarChart3 } from 'lucide-react';
import { usePositions } from '../hooks/usePositions';
import PositionTable from '../components/positions/PositionTable';
import PnLDisplay from '../components/positions/PnLDisplay';

export default function PositionsPage() {
  const { data, isLoading } = usePositions();

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-accent" />
          Positions
        </h1>
        <p className="text-sm text-gray-500 mt-1">Open positions and profit/loss tracking</p>
      </div>

      {/* PnL Summary */}
      <PnLDisplay
        totalUnrealizedPnl={data?.total_unrealized_pnl ?? 0}
        totalRealizedPnl={data?.total_realized_pnl ?? 0}
        positionCount={data?.positions?.length ?? 0}
      />

      {/* Positions Table */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-200">Open Positions</h3>
          <span className="text-xs text-gray-500">
            {data?.positions?.length ?? 0} positions
          </span>
        </div>
        <PositionTable positions={data?.positions ?? []} isLoading={isLoading} />
      </div>
    </div>
  );
}
