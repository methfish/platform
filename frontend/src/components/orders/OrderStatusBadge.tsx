import { ORDER_STATUS_COLORS, ORDER_STATUS_LABELS } from '../../utils/constants';

interface OrderStatusBadgeProps {
  status: string;
}

export default function OrderStatusBadge({ status }: OrderStatusBadgeProps) {
  const colors = ORDER_STATUS_COLORS[status] ?? ORDER_STATUS_COLORS.PENDING;
  const label = ORDER_STATUS_LABELS[status] ?? status;

  return (
    <span className={`badge ${colors.bg} ${colors.text}`}>
      {label}
    </span>
  );
}
