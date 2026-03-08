import { useMemo } from 'react';
import {
  Zap,
  CheckCircle,
  XCircle,
  Timer,
  Loader2,
  PlayCircle,
  AlertTriangle,
} from 'lucide-react';
import { SkillDefinition, SkillInvocation, AgentRun } from '../../types/agent';
import { formatDateTime, formatTimeAgo } from '../../utils/formatters';

interface AgentDashboardProps {
  skills: SkillDefinition[];
  invocations: SkillInvocation[];
  agentRuns: AgentRun[];
  isLoading: boolean;
}

interface MetricCardProps {
  label: string;
  value: string | number;
  icon: typeof Zap;
  iconColor: string;
  subtext?: string;
}

function MetricCard({ label, value, icon: Icon, iconColor, subtext }: MetricCardProps) {
  return (
    <div className="card flex items-start gap-3">
      <div className={`p-2 rounded-lg bg-surface-overlay ${iconColor}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 font-medium">{label}</p>
        <p className="text-xl font-bold text-gray-100 tabular-nums">{value}</p>
        {subtext && <p className="text-[10px] text-gray-500 mt-0.5">{subtext}</p>}
      </div>
    </div>
  );
}

const RUN_STATUS_COLORS: Record<string, string> = {
  RUNNING: 'text-blue-400',
  COMPLETED: 'text-green-400',
  FAILED: 'text-red-400',
  CANCELLED: 'text-gray-400',
};

const RUN_STATUS_BADGES: Record<string, string> = {
  RUNNING: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  COMPLETED: 'bg-green-500/15 text-green-400 border-green-500/30',
  FAILED: 'bg-red-500/15 text-red-400 border-red-500/30',
  CANCELLED: 'bg-gray-500/15 text-gray-400 border-gray-500/30',
};

export default function AgentDashboard({
  skills,
  invocations,
  agentRuns,
  isLoading,
}: AgentDashboardProps) {
  const metrics = useMemo(() => {
    const totalSkills = skills.length;
    const activeSkills = skills.filter((s) => s.enabled).length;
    const recentFailures = invocations.filter(
      (inv) => inv.status === 'FAILURE' || inv.status === 'ERROR',
    ).length;
    const avgLatency =
      invocations.length > 0
        ? Math.round(
            invocations.reduce((sum, inv) => sum + inv.execution_time_ms, 0) /
              invocations.length,
          )
        : 0;

    return { totalSkills, activeSkills, recentFailures, avgLatency };
  }, [skills, invocations]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 text-accent animate-spin" />
        <span className="ml-3 text-gray-400 text-sm">Loading dashboard...</span>
      </div>
    );
  }

  const latestRuns = agentRuns.slice(0, 8);

  return (
    <div className="space-y-6">
      {/* Metric cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Skills"
          value={metrics.totalSkills}
          icon={Zap}
          iconColor="text-accent"
        />
        <MetricCard
          label="Active Skills"
          value={metrics.activeSkills}
          icon={CheckCircle}
          iconColor="text-green-400"
          subtext={`${metrics.totalSkills > 0 ? Math.round((metrics.activeSkills / metrics.totalSkills) * 100) : 0}% enabled`}
        />
        <MetricCard
          label="Recent Failures"
          value={metrics.recentFailures}
          icon={XCircle}
          iconColor={metrics.recentFailures > 0 ? 'text-red-400' : 'text-gray-500'}
          subtext="From recent invocations"
        />
        <MetricCard
          label="Avg Latency"
          value={`${metrics.avgLatency}ms`}
          icon={Timer}
          iconColor="text-blue-400"
          subtext={`${invocations.length} invocations`}
        />
      </div>

      {/* Latest Agent Runs */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-200">Latest Agent Runs</h3>
          <span className="text-xs text-gray-500">{agentRuns.length} total runs</span>
        </div>

        {latestRuns.length === 0 ? (
          <div className="text-center py-8">
            <PlayCircle className="h-8 w-8 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-500 text-sm">No agent runs recorded yet</p>
          </div>
        ) : (
          <div className="space-y-2">
            {latestRuns.map((run) => (
              <div
                key={run.run_id}
                className="flex items-center gap-4 p-3 rounded-lg bg-surface-base hover:bg-surface-overlay/50 transition-colors"
              >
                {/* Status icon */}
                <div className={RUN_STATUS_COLORS[run.status] ?? 'text-gray-400'}>
                  {run.status === 'RUNNING' ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : run.status === 'FAILED' ? (
                    <AlertTriangle className="h-4 w-4" />
                  ) : (
                    <CheckCircle className="h-4 w-4" />
                  )}
                </div>

                {/* Agent type */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-gray-200">
                      {run.agent_type.replace('_', ' ')}
                    </span>
                    {run.symbol && (
                      <span className="text-[10px] text-gray-500 font-mono">{run.symbol}</span>
                    )}
                  </div>
                  <span className="text-[10px] text-gray-500">
                    {run.trigger} &middot; {formatTimeAgo(run.started_at)}
                  </span>
                </div>

                {/* Status badge */}
                <span
                  className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-medium border ${
                    RUN_STATUS_BADGES[run.status] ?? 'bg-gray-500/15 text-gray-400 border-gray-500/30'
                  }`}
                >
                  {run.status}
                </span>

                {/* Skills run / failed */}
                <div className="text-right shrink-0">
                  <p className="text-[11px] text-gray-300 tabular-nums">
                    {run.skills_run} run
                    {run.skills_failed > 0 && (
                      <span className="text-red-400 ml-1">/ {run.skills_failed} failed</span>
                    )}
                  </p>
                  <p className="text-[10px] text-gray-500 tabular-nums">
                    {run.total_time_ms.toLocaleString()}ms
                  </p>
                </div>

                {/* Timestamp */}
                <span className="text-[10px] text-gray-600 shrink-0 hidden lg:block">
                  {formatDateTime(run.started_at)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
