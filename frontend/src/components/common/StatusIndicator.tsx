interface StatusIndicatorProps {
  status: 'green' | 'yellow' | 'red' | 'gray';
  label?: string;
  pulse?: boolean;
  size?: 'sm' | 'md';
}

const DOT_COLORS: Record<string, string> = {
  green: 'bg-green-400',
  yellow: 'bg-yellow-400',
  red: 'bg-red-400',
  gray: 'bg-gray-500',
};

const RING_COLORS: Record<string, string> = {
  green: 'bg-green-400/30',
  yellow: 'bg-yellow-400/30',
  red: 'bg-red-400/30',
  gray: 'bg-gray-500/30',
};

export default function StatusIndicator({
  status,
  label,
  pulse = false,
  size = 'sm',
}: StatusIndicatorProps) {
  const dotSize = size === 'sm' ? 'h-2 w-2' : 'h-3 w-3';
  const ringSize = size === 'sm' ? 'h-4 w-4' : 'h-5 w-5';

  return (
    <div className="flex items-center gap-2">
      <span className={`relative flex ${ringSize}`}>
        {pulse && (
          <span
            className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${RING_COLORS[status]}`}
          />
        )}
        <span
          className={`relative inline-flex rounded-full ${dotSize} ${DOT_COLORS[status]} m-auto`}
        />
      </span>
      {label && <span className="text-sm text-gray-300">{label}</span>}
    </div>
  );
}
