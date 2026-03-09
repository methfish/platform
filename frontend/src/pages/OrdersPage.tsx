import { useState } from 'react';
import { ClipboardList, Filter } from 'lucide-react';
import { useOrders } from '../hooks/useOrders';
import OrderTable from '../components/orders/OrderTable';

const STATUS_OPTIONS = [
  { value: '', label: 'All Statuses' },
  { value: 'PENDING', label: 'Pending' },
  { value: 'SUBMITTED', label: 'Submitted' },
  { value: 'PARTIALLY_FILLED', label: 'Partial Fill' },
  { value: 'FILLED', label: 'Filled' },
  { value: 'CANCELLED', label: 'Cancelled' },
  { value: 'REJECTED', label: 'Rejected' },
  { value: 'FAILED', label: 'Failed' },
];

export default function OrdersPage() {
  const [statusFilter, setStatusFilter] = useState('');
  const [symbolFilter, setSymbolFilter] = useState('');

  const params = {
    ...(statusFilter ? { status: statusFilter } : {}),
    ...(symbolFilter ? { symbol: symbolFilter.toUpperCase() } : {}),
    limit: 100,
  };

  const { data, isLoading } = useOrders(params);

  return (
    <div className="space-y-6">
      {/* Page Title */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <ClipboardList className="h-6 w-6 text-accent" />
          Order History
        </h1>
        <p className="text-sm text-gray-500 mt-1">Orders placed by strategies — read-only log</p>
      </div>

      {/* Filters + Table */}
      <div className="card">
        <div className="flex items-center gap-4 mb-4">
          <Filter className="h-4 w-4 text-gray-500" />
          <div className="flex gap-3 flex-1">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="select-field text-sm w-40"
            >
              {STATUS_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>

            <input
              type="text"
              value={symbolFilter}
              onChange={(e) => setSymbolFilter(e.target.value)}
              placeholder="Filter by symbol..."
              className="input-field text-sm w-48"
            />
          </div>

          <span className="text-xs text-gray-500">
            {data?.total ?? 0} total orders
          </span>
        </div>

        <OrderTable orders={data?.orders ?? []} isLoading={isLoading} />
      </div>
    </div>
  );
}
