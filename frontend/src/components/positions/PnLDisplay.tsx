import { TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react';
import { formatCurrency, pnlColor, pnlBgColor } from '../../utils/formatters';

interface PnLDisplayProps {
  totalUnrealizedPnl: number;
  totalRealizedPnl: number;
  positionCount: number;
}

export default function PnLDisplay({
  totalUnrealizedPnl,
  totalRealizedPnl,
  positionCount,
}: PnLDisplayProps) {
  const totalPnl = totalUnrealizedPnl + totalRealizedPnl;

  const cards = [
    {
      label: 'Total P&L',
      value: totalPnl,
      icon: DollarSign,
      formatted: formatCurrency(totalPnl),
    },
    {
      label: 'Unrealized P&L',
      value: totalUnrealizedPnl,
      icon: TrendingUp,
      formatted: formatCurrency(totalUnrealizedPnl),
    },
    {
      label: 'Realized P&L',
      value: totalRealizedPnl,
      icon: TrendingDown,
      formatted: formatCurrency(totalRealizedPnl),
    },
    {
      label: 'Open Positions',
      value: 0,
      icon: Activity,
      formatted: String(positionCount),
      isCount: true,
    },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="card">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-500 font-medium">{card.label}</span>
            <div className={`p-1.5 rounded-lg ${card.isCount ? 'bg-accent/15 text-accent' : pnlBgColor(card.value)}`}>
              <card.icon className="h-4 w-4" />
            </div>
          </div>
          <p
            className={`text-xl font-bold font-mono ${
              card.isCount ? 'text-gray-100' : pnlColor(card.value)
            }`}
          >
            {card.isCount ? card.formatted : (card.value >= 0 ? '+' : '') + card.formatted}
          </p>
        </div>
      ))}
    </div>
  );
}
