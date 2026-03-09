import { BarChart3 } from 'lucide-react';
import { usePositions } from '../hooks/usePositions';
import PositionTable from '../components/positions/PositionTable';
import PnLDisplay from '../components/positions/PnLDisplay';
import type { Position } from '../types/position';

const DEMO_POSITIONS: Position[] = [
  {
    id: '1', exchange: 'paper', symbol: 'EURUSD', side: 'long', quantity: 10000,
    entry_price: 1.0842, current_price: 1.0871, unrealized_pnl: 290.00, realized_pnl: 0,
    margin_used: null, leverage: null, liquidation_price: null, strategy_id: 'strat-1',
    opened_at: '2026-03-08T09:15:00Z', updated_at: '2026-03-09T14:30:00Z',
  },
  {
    id: '2', exchange: 'paper', symbol: 'AAPL', side: 'long', quantity: 50,
    entry_price: 178.25, current_price: 181.40, unrealized_pnl: 157.50, realized_pnl: 342.80,
    margin_used: null, leverage: null, liquidation_price: null, strategy_id: 'strat-2',
    opened_at: '2026-03-07T14:30:00Z', updated_at: '2026-03-09T14:30:00Z',
  },
  {
    id: '3', exchange: 'paper', symbol: 'GBPUSD', side: 'short', quantity: 5000,
    entry_price: 1.2695, current_price: 1.2712, unrealized_pnl: -85.00, realized_pnl: 124.50,
    margin_used: null, leverage: null, liquidation_price: null, strategy_id: 'strat-1',
    opened_at: '2026-03-08T11:00:00Z', updated_at: '2026-03-09T14:30:00Z',
  },
  {
    id: '4', exchange: 'paper', symbol: 'MSFT', side: 'long', quantity: 30,
    entry_price: 412.50, current_price: 418.75, unrealized_pnl: 187.50, realized_pnl: 0,
    margin_used: null, leverage: null, liquidation_price: null, strategy_id: 'strat-3',
    opened_at: '2026-03-09T10:00:00Z', updated_at: '2026-03-09T14:30:00Z',
  },
  {
    id: '5', exchange: 'paper', symbol: 'USDJPY', side: 'short', quantity: 8000,
    entry_price: 149.82, current_price: 149.45, unrealized_pnl: 198.00, realized_pnl: 67.20,
    margin_used: null, leverage: null, liquidation_price: null, strategy_id: 'strat-1',
    opened_at: '2026-03-06T08:45:00Z', updated_at: '2026-03-09T14:30:00Z',
  },
];

export default function PositionsPage() {
  const { data, isLoading } = usePositions();

  const positions = data?.positions?.length ? data.positions : DEMO_POSITIONS;
  const totalUnrealized = data?.total_unrealized_pnl ?? DEMO_POSITIONS.reduce((s, p) => s + p.unrealized_pnl, 0);
  const totalRealized = data?.total_realized_pnl ?? DEMO_POSITIONS.reduce((s, p) => s + p.realized_pnl, 0);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <BarChart3 className="h-6 w-6 text-accent" />
          Positions
        </h1>
        <p className="text-sm text-gray-500 mt-1">Open positions and profit/loss tracking</p>
      </div>

      <PnLDisplay
        totalUnrealizedPnl={totalUnrealized}
        totalRealizedPnl={totalRealized}
        positionCount={positions.length}
      />

      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-200">Open Positions</h3>
          <span className="text-xs text-gray-500">{positions.length} positions</span>
        </div>
        <PositionTable positions={positions} isLoading={isLoading && !data} />
      </div>
    </div>
  );
}
