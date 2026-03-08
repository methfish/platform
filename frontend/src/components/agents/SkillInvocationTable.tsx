import { SkillInvocation, SkillStatus } from '../../types/agent';
import DataTable, { Column } from '../common/DataTable';
import { formatDateTime } from '../../utils/formatters';

interface SkillInvocationTableProps {
  invocations: SkillInvocation[];
  isLoading: boolean;
}

const STATUS_COLORS: Record<SkillStatus, string> = {
  SUCCESS: 'bg-green-500/15 text-green-400 border-green-500/30',
  FAILURE: 'bg-red-500/15 text-red-400 border-red-500/30',
  SKIPPED: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
  ERROR: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  TIMEOUT: 'bg-yellow-500/15 text-yellow-400 border-yellow-500/30',
};

const columns: Column<SkillInvocation>[] = [
  {
    key: 'skill_id',
    header: 'Skill ID',
    sortable: true,
    render: (row) => (
      <span className="text-gray-200 text-xs font-mono">{row.skill_id}</span>
    ),
  },
  {
    key: 'agent_type',
    header: 'Agent',
    sortable: true,
    render: (row) => (
      <span className="text-gray-300 text-xs">
        {row.agent_type.replace('_', ' ')}
      </span>
    ),
  },
  {
    key: 'status',
    header: 'Status',
    sortable: true,
    render: (row) => (
      <span
        className={`inline-flex items-center px-2 py-0.5 rounded-md text-[11px] font-medium border ${STATUS_COLORS[row.status]}`}
      >
        {row.status}
      </span>
    ),
  },
  {
    key: 'execution_time_ms',
    header: 'Exec Time',
    sortable: true,
    render: (row) => (
      <span className="text-gray-300 text-xs tabular-nums">
        {row.execution_time_ms.toLocaleString()}ms
      </span>
    ),
  },
  {
    key: 'confidence',
    header: 'Confidence',
    sortable: true,
    render: (row) =>
      row.confidence != null ? (
        <span className="text-gray-300 text-xs tabular-nums">
          {(row.confidence * 100).toFixed(1)}%
        </span>
      ) : (
        <span className="text-gray-600 text-xs">--</span>
      ),
  },
  {
    key: 'timestamp',
    header: 'Timestamp',
    sortable: true,
    render: (row) => (
      <span className="text-gray-400 text-[11px]">{formatDateTime(row.timestamp)}</span>
    ),
  },
];

export default function SkillInvocationTable({
  invocations,
  isLoading,
}: SkillInvocationTableProps) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-gray-200">Skill Invocations</h3>
        <span className="text-xs text-gray-500">{invocations.length} invocations</span>
      </div>
      <DataTable<SkillInvocation>
        columns={columns}
        data={invocations}
        isLoading={isLoading}
        emptyMessage="No skill invocations recorded"
        rowKey={(row) => row.invocation_id}
      />
    </div>
  );
}
