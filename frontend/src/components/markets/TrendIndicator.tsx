import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface TrendIndicatorProps {
  trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
}

const trendConfig = {
  BULLISH: {
    icon: TrendingUp,
    bg: 'bg-green-500/15',
    text: 'text-profit',
    label: 'Bullish',
  },
  BEARISH: {
    icon: TrendingDown,
    bg: 'bg-red-500/15',
    text: 'text-loss',
    label: 'Bearish',
  },
  NEUTRAL: {
    icon: Minus,
    bg: 'bg-gray-500/15',
    text: 'text-gray-400',
    label: 'Neutral',
  },
};

export default function TrendIndicator({ trend }: TrendIndicatorProps) {
  const config = trendConfig[trend];
  const Icon = config.icon;

  return (
    <span className={`badge ${config.bg} ${config.text}`}>
      <Icon className="h-3 w-3 mr-1" />
      {config.label}
    </span>
  );
}
