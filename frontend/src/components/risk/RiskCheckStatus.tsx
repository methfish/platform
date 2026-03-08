import { CheckCircle, AlertTriangle, XCircle } from 'lucide-react';

interface RiskCheckStatusProps {
  label: string;
  current: number;
  limit: number;
  unit?: string;
  format?: (val: number) => string;
  inverted?: boolean; // true if lower current = worse
}

export default function RiskCheckStatus({
  label,
  current,
  limit,
  unit = '',
  format,
  inverted = false,
}: RiskCheckStatusProps) {
  const ratio = limit > 0 ? current / limit : 0;
  const percentage = Math.min(ratio * 100, 100);

  let severity: 'ok' | 'warning' | 'danger';
  if (inverted) {
    severity = ratio < 0.5 ? 'danger' : ratio < 0.75 ? 'warning' : 'ok';
  } else {
    severity = ratio > 0.9 ? 'danger' : ratio > 0.7 ? 'warning' : 'ok';
  }

  const barColor =
    severity === 'danger'
      ? 'bg-red-500'
      : severity === 'warning'
      ? 'bg-yellow-500'
      : 'bg-green-500';

  const Icon =
    severity === 'danger' ? XCircle : severity === 'warning' ? AlertTriangle : CheckCircle;

  const iconColor =
    severity === 'danger'
      ? 'text-red-400'
      : severity === 'warning'
      ? 'text-yellow-400'
      : 'text-green-400';

  const fmt = format ?? ((v: number) => `${v.toLocaleString()}${unit}`);

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-300 font-medium">{label}</span>
        <Icon className={`h-4 w-4 ${iconColor}`} />
      </div>

      <div className="flex items-baseline gap-2 mb-2">
        <span className="text-lg font-bold font-mono text-gray-100">{fmt(current)}</span>
        <span className="text-xs text-gray-500">/ {fmt(limit)}</span>
      </div>

      <div className="h-1.5 bg-surface rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${barColor}`}
          style={{ width: `${percentage}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-[10px] text-gray-600">{percentage.toFixed(0)}% utilized</span>
      </div>
    </div>
  );
}
