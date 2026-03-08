import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import { SkillDefinition, SkillExecutionType, AgentType } from '../../types/agent';
import SkillCard from './SkillCard';

interface AgentSkillListProps {
  skills: SkillDefinition[];
  isLoading: boolean;
  onToggle: (skillId: string, enabled: boolean) => void;
  togglingId?: string | null;
}

const EXECUTION_FILTERS: { value: SkillExecutionType | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'All Types' },
  { value: 'DETERMINISTIC', label: 'Deterministic' },
  { value: 'MODEL_ASSISTED', label: 'Model Assisted' },
  { value: 'HYBRID', label: 'Hybrid' },
];

const AGENT_TABS: { value: AgentType | 'ALL'; label: string }[] = [
  { value: 'ALL', label: 'All Agents' },
  { value: 'TRADE_DECISION', label: 'Trade Decision' },
  { value: 'FAILURE_ANALYSIS', label: 'Failure Analysis' },
];

export default function AgentSkillList({
  skills,
  isLoading,
  onToggle,
  togglingId,
}: AgentSkillListProps) {
  const [executionFilter, setExecutionFilter] = useState<SkillExecutionType | 'ALL'>('ALL');
  const [agentTab, setAgentTab] = useState<AgentType | 'ALL'>('ALL');

  const filtered = skills.filter((skill) => {
    if (executionFilter !== 'ALL' && skill.execution_type !== executionFilter) return false;
    if (agentTab !== 'ALL' && skill.agent_type !== agentTab) return false;
    return true;
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 text-accent animate-spin" />
        <span className="ml-3 text-gray-400 text-sm">Loading skills...</span>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters bar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Agent type tabs */}
        <div className="flex items-center gap-1 bg-surface-base rounded-lg p-1">
          {AGENT_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setAgentTab(tab.value)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                agentTab === tab.value
                  ? 'bg-surface-raised text-gray-100 shadow-sm'
                  : 'text-gray-400 hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="flex items-center gap-3">
          {/* Execution type filter */}
          <select
            value={executionFilter}
            onChange={(e) => setExecutionFilter(e.target.value as SkillExecutionType | 'ALL')}
            className="bg-surface-base border border-surface-border rounded-lg px-3 py-1.5 text-xs text-gray-300 focus:outline-none focus:ring-1 focus:ring-accent"
          >
            {EXECUTION_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>

          {/* Count */}
          <span className="text-xs text-gray-500">
            {filtered.length} of {skills.length} skills
          </span>
        </div>
      </div>

      {/* Skills grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 text-sm">No skills match the current filters</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filtered.map((skill) => (
            <SkillCard
              key={skill.skill_id}
              skill={skill}
              onToggle={onToggle}
              isToggling={togglingId === skill.skill_id}
            />
          ))}
        </div>
      )}
    </div>
  );
}
