import { useState } from 'react';
import { X } from 'lucide-react';
import DataTable, { Column } from '../common/DataTable';
import OrderStatusBadge from './OrderStatusBadge';
import ConfirmDialog from '../common/ConfirmDialog';
import { Order } from '../../types/order';
import { useCancelOrder } from '../../hooks/useOrders';
import { formatDateTime, formatCurrency, formatQuantity } from '../../utils/formatters';
import { SIDE_COLORS } from '../../utils/constants';

interface OrderTableProps {
  orders: Order[];
  isLoading?: boolean;
}

export default function OrderTable({ orders, isLoading }: OrderTableProps) {
  const [cancelTarget, setCancelTarget] = useState<Order | null>(null);
  const cancelOrder = useCancelOrder();

  const handleCancelConfirm = () => {
    if (cancelTarget) {
      cancelOrder.mutate(cancelTarget.id);
      setCancelTarget(null);
    }
  };

  const columns: Column<Order>[] = [
    {
      key: 'created_at',
      header: 'Time',
      sortable: true,
      width: '140px',
      render: (row) => (
        <span className="text-gray-400 text-xs font-mono">{formatDateTime(row.created_at)}</span>
      ),
    },
    {
      key: 'symbol',
      header: 'Symbol',
      sortable: true,
      render: (row) => <span className="font-medium text-gray-200">{row.symbol}</span>,
    },
    {
      key: 'side',
      header: 'Side',
      sortable: true,
      render: (row) => {
        const colors = SIDE_COLORS[row.side];
        return (
          <span className={`badge ${colors.bg} ${colors.text} uppercase text-[10px] font-bold tracking-wider`}>
            {row.side}
          </span>
        );
      },
    },
    {
      key: 'type',
      header: 'Type',
      sortable: true,
      render: (row) => <span className="text-gray-400 capitalize">{row.type.replace('_', ' ')}</span>,
    },
    {
      key: 'quantity',
      header: 'Qty',
      sortable: true,
      render: (row) => (
        <span className="font-mono">
          {formatQuantity(row.filled_quantity)}/{formatQuantity(row.quantity)}
        </span>
      ),
    },
    {
      key: 'price',
      header: 'Price',
      sortable: true,
      render: (row) => (
        <span className="font-mono">
          {row.price ? formatCurrency(row.price) : row.type === 'market' ? 'MKT' : '-'}
        </span>
      ),
    },
    {
      key: 'average_fill_price',
      header: 'Avg Fill',
      sortable: true,
      render: (row) => (
        <span className="font-mono">
          {row.average_fill_price ? formatCurrency(row.average_fill_price) : '-'}
        </span>
      ),
    },
    {
      key: 'status',
      header: 'Status',
      sortable: true,
      render: (row) => <OrderStatusBadge status={row.status} />,
    },
    {
      key: 'exchange',
      header: 'Exchange',
      sortable: true,
      render: (row) => <span className="text-gray-500 capitalize text-xs">{row.exchange}</span>,
    },
    {
      key: 'actions',
      header: '',
      width: '60px',
      render: (row) =>
        ['pending', 'open', 'partially_filled'].includes(row.status) ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setCancelTarget(row);
            }}
            className="p-1 rounded text-gray-500 hover:text-red-400 hover:bg-red-500/10 transition-colors"
            title="Cancel order"
          >
            <X className="h-4 w-4" />
          </button>
        ) : null,
    },
  ];

  return (
    <>
      <DataTable columns={columns} data={orders} isLoading={isLoading} rowKey={(r) => r.id} emptyMessage="No orders found" />

      <ConfirmDialog
        open={!!cancelTarget}
        title="Cancel Order"
        message={
          cancelTarget
            ? `Cancel ${cancelTarget.side.toUpperCase()} ${formatQuantity(cancelTarget.quantity)} ${cancelTarget.symbol} order?`
            : ''
        }
        confirmLabel="Cancel Order"
        variant="warning"
        onConfirm={handleCancelConfirm}
        onCancel={() => setCancelTarget(null)}
      />
    </>
  );
}
