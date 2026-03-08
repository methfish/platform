import { Zap, Brain, Layers, ShieldCheck } from 'lucide-react';
import { SkillDefinition, SkillExecutionType, SkillRiskLevel } from '../../types/agent';

interface SkillCardProps {
  skill: SkillDefinition;
  onToggle: (skillId: string, enabled: boolean) => void;
  isToggling?: boolean;
}

const EXECUTION_TYPE_CONFIG: Record<
  SkillExecutionType,
  { icon: typeof Zap; label: string; color: string }
> = {
  DETERMINISTIC: {
    icon: Zap,
    label: 'Deterministic',
    color: 'bg-blue-500/15 text-blue-400 border-blue-500/30',
  },
  MODEL_ASSISTED: {
    icon: Brain,
    label: 'Model Assisted',
    color: 'bg-purple-500/15 text-purple-400 border-purple-500/30',
  },
  HYBRID: {
    icon: Layers,
    label: 'Hybrid',
    color: 'bg-orange-500/15 text-orange-400 border-orange-500/30',
  },
};

const RISK_LEVEL_CONFIG: Record<SkillRiskLevel, { color: string; dot: string }> = {
  LOW: { color: 'text-green-400', dot: 'bg-green-400' },
  MEDIUM: { color: 'text-yellow-400', dot: 'bg-yellow-400' },
  HIGH: { color: 'text-orange-400', dot: 'bg-orange-400' },
  CRITICAL: { color: 'text-red-400', dot: 'bg-red-400' },
};

export default function SkillCard({ skill, onToggle, isToggling }: SkillCardProps) {
  const execConfig = EXECUTION_TYPE_CONFIG[skill.execution_type];
  const riskConfig = RISK_LEVEL_CONFIG[skill.risk_level];
  const ExecIcon = execConfig.icon;

  return (
    <div className="card flex flex-col gap-3">
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-gray-100 truncate">{skill.name}</h3>
            <span className="badge text-[10px] bg-surface-overlay text-gray-400">
              v{skill.version}
            </span>
          </div>
        </div>

        {/* Toggle switch */}
        <button
          onClick={() => onToggle(skill.skill_id, !skill.enabled)}
          disabled={isToggling}
          className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed ${
            skill.enabled ? 'bg-accent' : 'bg-gray-600'
          }`}
          role="switch"
          aria-checked={skill.enabled}
          aria-label={`Toggle ${skill.name}`}
        >
          <span
            className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-sm ring-0 transition duration-200 ease-in-out ${
              skill.enabled ? 'translate-x-4' : 'translate-x-0'
            }`}
          />
        </button>
      </div>

      {/* Badges row */}
      <div className="flex items-center gap-2 flex-wrap">
        {/* Execution type badge */}
        <span
          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-[11px] font-medium border ${execConfig.color}`}
        >
          <ExecIcon className="h-3 w-3" />
          {execConfig.label}
        </span>

        {/* Risk level */}
        <span className={`inline-flex items-center gap-1.5 text-[11px] font-medium ${riskConfig.color}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${riskConfig.dot}`} />
          {skill.risk_level}
        </span>

        {/* Human review indicator */}
        {skill.requires_human_review && (
          <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400">
            <ShieldCheck className="h-3 w-3" />
            Review
          </span>
        )}
      </div>

      {/* Description */}
      <p className="text-xs text-gray-400 leading-relaxed line-clamp-2">
        {skill.description}
      </p>

      {/* Footer info */}
      <div className="flex items-center justify-between text-[10px] text-gray-500 pt-1 border-t border-surface-border/50">
        <span>Timeout: {skill.timeout_seconds}s</span>
        <span className="uppercase tracking-wide">
          {skill.agent_type.replace('_', ' ')}
        </span>
      </div>
    </div>
  );
}
