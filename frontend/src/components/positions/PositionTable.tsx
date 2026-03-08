import DataTable, { Column } from '../common/DataTable';
import { Position } from '../../types/position';
import { formatCurrency, formatQuantity, pnlColor } from '../../utils/formatters';
import { SIDE_COLORS } from '../../utils/constants';

interface PositionTableProps {
  positions: Position[];
  isLoading?: boolean;
}

export default function PositionTable({ positions, isLoading }: PositionTableProps) {
  const columns: Column<Position>[] = [
    {
      key: 'symbol',
      header: 'Symbol',
      sortable: true,
      render: (row) => <span className="font-medium text-gray-200">{row.symbol}</span>,
    },
    {
      key: 'exchange',
      header: 'Exchange',
      sortable: true,
      render: (row) => <span className="text-gray-400 capitalize text-xs">{row.exchange}</span>,
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
      key: 'quantity',
      header: 'Size',
      sortable: true,
      render: (row) => <span className="font-mono">{formatQuantity(row.quantity)}</span>,
    },
    {
      key: 'entry_price',
      header: 'Entry',
      sortable: true,
      render: (row) => <span className="font-mono">{formatCurrency(row.entry_price)}</span>,
    },
    {
      key: 'current_price',
      header: 'Current',
      sortable: true,
      render: (row) => <span className="font-mono">{formatCurrency(row.current_price)}</span>,
    },
    {
      key: 'unrealized_pnl',
      header: 'Unrealized P&L',
      sortable: true,
      render: (row) => (
        <span className={`font-mono font-medium ${pnlColor(row.unrealized_pnl)}`}>
          {row.unrealized_pnl >= 0 ? '+' : ''}{formatCurrency(row.unrealized_pnl)}
        </span>
      ),
    },
    {
      key: 'realized_pnl',
      header: 'Realized P&L',
      sortable: true,
      render: (row) => (
        <span className={`font-mono font-medium ${pnlColor(row.realized_pnl)}`}>
          {row.realized_pnl >= 0 ? '+' : ''}{formatCurrency(row.realized_pnl)}
        </span>
      ),
    },
    {
      key: 'leverage',
      header: 'Leverage',
      render: (row) => (
        <span className="text-gray-400 text-xs">
          {row.leverage ? `${row.leverage}x` : '-'}
        </span>
      ),
    },
  ];

  return (
    <DataTable
      columns={columns}
      data={positions}
      isLoading={isLoading}
      rowKey={(r) => r.id}
      emptyMessage="No open positions"
    />
  );
}
