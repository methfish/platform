import { useState } from 'react';
import { Bot, Loader2 } from 'lucide-react';
import { useSkills, useToggleSkill, useInvocations, useAgentRuns, useLessons } from '../hooks/useAgents';
import AgentDashboard from '../components/agents/AgentDashboard';
import AgentSkillList from '../components/agents/AgentSkillList';
import SkillInvocationTable from '../components/agents/SkillInvocationTable';
import LessonsTable from '../components/agents/LessonsTable';
import type { SkillDefinition, SkillInvocation, AgentRun, LearnedLesson } from '../types/agent';

type TabKey = 'dashboard' | 'skills' | 'invocations' | 'lessons';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'skills', label: 'Skills' },
  { key: 'invocations', label: 'Invocations' },
  { key: 'lessons', label: 'Lessons' },
];

const DEMO_SKILLS: SkillDefinition[] = [
  { skill_id: '1', name: 'data_inventory', description: 'Query OHLCV data summary and identify gaps', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'LOW', agent_type: 'TRADE_DECISION', enabled: true, requires_human_review: false, timeout_seconds: 30, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '2', name: 'data_collection', description: 'Trigger yfinance collection for missing data', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'LOW', agent_type: 'TRADE_DECISION', enabled: true, requires_human_review: false, timeout_seconds: 60, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '3', name: 'backtest_execution', description: 'Run backtests across strategies and symbols', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'MEDIUM', agent_type: 'TRADE_DECISION', enabled: true, requires_human_review: false, timeout_seconds: 120, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '4', name: 'result_analysis', description: 'Rank strategies by Sharpe, flag trust issues', version: '1.0.0', execution_type: 'HYBRID', risk_level: 'LOW', agent_type: 'TRADE_DECISION', enabled: true, requires_human_review: false, timeout_seconds: 30, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '5', name: 'parameter_optimization', description: 'Run parameter sweeps on top strategies', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'MEDIUM', agent_type: 'TRADE_DECISION', enabled: true, requires_human_review: false, timeout_seconds: 120, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '6', name: 'report_generation', description: 'Compile structured research report', version: '1.0.0', execution_type: 'MODEL_ASSISTED', risk_level: 'LOW', agent_type: 'TRADE_DECISION', enabled: true, requires_human_review: true, timeout_seconds: 30, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '7', name: 'strategy_analysis', description: 'Read existing strategy code, extract patterns', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'LOW', agent_type: 'FAILURE_ANALYSIS', enabled: true, requires_human_review: false, timeout_seconds: 30, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '8', name: 'code_generation', description: 'Generate Python signal function from spec', version: '1.0.0', execution_type: 'HYBRID', risk_level: 'HIGH', agent_type: 'FAILURE_ANALYSIS', enabled: true, requires_human_review: true, timeout_seconds: 60, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '9', name: 'code_validation', description: 'AST parse + forbidden import check', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'LOW', agent_type: 'FAILURE_ANALYSIS', enabled: true, requires_human_review: false, timeout_seconds: 10, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '10', name: 'backtest_verification', description: 'Run 100-bar test to confirm no crashes', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'MEDIUM', agent_type: 'FAILURE_ANALYSIS', enabled: true, requires_human_review: false, timeout_seconds: 30, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
  { skill_id: '11', name: 'code_registration', description: 'Register generated strategy at runtime', version: '1.0.0', execution_type: 'DETERMINISTIC', risk_level: 'HIGH', agent_type: 'FAILURE_ANALYSIS', enabled: false, requires_human_review: true, timeout_seconds: 10, created_at: '2026-03-01T00:00:00Z', updated_at: '2026-03-01T00:00:00Z' },
];

const DEMO_INVOCATIONS: SkillInvocation[] = [
  { invocation_id: '1', skill_id: '1', agent_run_id: 'r1', agent_type: 'TRADE_DECISION', status: 'SUCCESS', execution_time_ms: 45, confidence: null, input_data: { symbols: ['EURUSD'] }, output_data: { datasets: 8, total_bars: 64530 }, error_message: null, timestamp: '2026-03-09T13:00:00Z' },
  { invocation_id: '2', skill_id: '3', agent_run_id: 'r1', agent_type: 'TRADE_DECISION', status: 'SUCCESS', execution_time_ms: 3200, confidence: null, input_data: { strategy: 'sma_crossover', symbol: 'EURUSD' }, output_data: { sharpe: 1.82, net_pnl: 2847.5 }, error_message: null, timestamp: '2026-03-09T13:01:00Z' },
  { invocation_id: '3', skill_id: '4', agent_run_id: 'r1', agent_type: 'TRADE_DECISION', status: 'SUCCESS', execution_time_ms: 890, confidence: 0.85, input_data: { backtest_id: 'bt1' }, output_data: { rank: 1, trustworthy: true }, error_message: null, timestamp: '2026-03-09T13:02:00Z' },
  { invocation_id: '4', skill_id: '5', agent_run_id: 'r1', agent_type: 'TRADE_DECISION', status: 'SUCCESS', execution_time_ms: 12400, confidence: null, input_data: { strategy: 'sma_crossover' }, output_data: { best_sharpe: 2.14 }, error_message: null, timestamp: '2026-03-09T13:03:00Z' },
  { invocation_id: '5', skill_id: '7', agent_run_id: 'r2', agent_type: 'FAILURE_ANALYSIS', status: 'SUCCESS', execution_time_ms: 120, confidence: null, input_data: { strategy: 'sma_crossover' }, output_data: { patterns: ['crossover'] }, error_message: null, timestamp: '2026-03-09T12:00:00Z' },
  { invocation_id: '6', skill_id: '8', agent_run_id: 'r2', agent_type: 'FAILURE_ANALYSIS', status: 'SUCCESS', execution_time_ms: 4500, confidence: 0.92, input_data: { spec: 'momentum_breakout' }, output_data: { source_chars: 2340 }, error_message: null, timestamp: '2026-03-09T12:01:00Z' },
  { invocation_id: '7', skill_id: '9', agent_run_id: 'r2', agent_type: 'FAILURE_ANALYSIS', status: 'SUCCESS', execution_time_ms: 35, confidence: null, input_data: {}, output_data: { valid: true }, error_message: null, timestamp: '2026-03-09T12:02:00Z' },
  { invocation_id: '8', skill_id: '10', agent_run_id: 'r2', agent_type: 'FAILURE_ANALYSIS', status: 'FAILURE', execution_time_ms: 1800, confidence: null, input_data: {}, output_data: null, error_message: 'Backtest produced 0 trades', timestamp: '2026-03-09T12:03:00Z' },
];

const DEMO_RUNS: AgentRun[] = [
  { run_id: 'r1', agent_type: 'TRADE_DECISION', status: 'COMPLETED', skills_run: 6, skills_failed: 0, total_time_ms: 16535, trigger: 'manual', symbol: 'EURUSD', started_at: '2026-03-09T13:00:00Z', completed_at: '2026-03-09T13:04:00Z', result_summary: { best_strategy: 'sma_crossover' } },
  { run_id: 'r2', agent_type: 'FAILURE_ANALYSIS', status: 'COMPLETED', skills_run: 5, skills_failed: 1, total_time_ms: 6455, trigger: 'manual', symbol: null, started_at: '2026-03-09T12:00:00Z', completed_at: '2026-03-09T12:04:00Z', result_summary: { generated: 'momentum_breakout' } },
  { run_id: 'r3', agent_type: 'TRADE_DECISION', status: 'COMPLETED', skills_run: 4, skills_failed: 0, total_time_ms: 8200, trigger: 'scheduled', symbol: 'AAPL', started_at: '2026-03-08T09:00:00Z', completed_at: '2026-03-08T09:02:00Z', result_summary: { best_strategy: 'rsi' } },
  { run_id: 'r4', agent_type: 'TRADE_DECISION', status: 'COMPLETED', skills_run: 6, skills_failed: 0, total_time_ms: 21000, trigger: 'manual', symbol: 'GBPUSD', started_at: '2026-03-07T15:00:00Z', completed_at: '2026-03-07T15:05:00Z', result_summary: { best_strategy: 'macd' } },
];

const DEMO_LESSONS: LearnedLesson[] = [
  { lesson_id: '1', title: 'RSI oversold threshold too aggressive', description: 'RSI < 25 generates too few trades on daily forex', category: 'parameter_tuning', severity: 'MEDIUM', symbol: 'EURUSD', root_cause: 'Oversold threshold at 25 only triggers 3 times in 2 years', recommendation: 'Use RSI oversold=30 for forex daily', applied: true, agent_run_id: 'r1', created_at: '2026-03-09T13:04:00Z', updated_at: '2026-03-09T13:04:00Z' },
  { lesson_id: '2', title: 'Bollinger unreliable in trending markets', description: 'Bollinger mean-reversion produces negative Sharpe on GBP/USD trends', category: 'strategy_selection', severity: 'HIGH', symbol: 'GBPUSD', root_cause: 'Mean-reversion signals fight the trend', recommendation: 'Add 200-SMA trend filter before Bollinger signals', applied: false, agent_run_id: 'r4', created_at: '2026-03-07T15:05:00Z', updated_at: '2026-03-07T15:05:00Z' },
  { lesson_id: '3', title: 'SMA crossover fast_period=5 overfits', description: 'Very short fast SMA overfits on hourly data', category: 'overfitting', severity: 'HIGH', symbol: null, root_cause: 'fast_period=5 captures noise not signal', recommendation: 'Use fast_period >= 10 for hourly', applied: true, agent_run_id: 'r1', created_at: '2026-03-09T13:04:00Z', updated_at: '2026-03-09T13:04:00Z' },
  { lesson_id: '4', title: 'Stock data gaps on weekends', description: 'Weekend gaps skew SMA calculations', category: 'data_quality', severity: 'LOW', symbol: 'AAPL', root_cause: 'NaN values propagate through rolling windows', recommendation: 'Use dropna() before indicator calculation', applied: true, agent_run_id: 'r3', created_at: '2026-03-08T09:02:00Z', updated_at: '2026-03-08T09:02:00Z' },
];

export default function AgentsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');

  const { data: skillsData, isLoading: skillsLoading } = useSkills();
  const { data: invocationsData, isLoading: invocationsLoading } = useInvocations({ limit: 100 });
  const { data: runsData, isLoading: runsLoading } = useAgentRuns({ limit: 50 });
  const { data: lessonsData, isLoading: lessonsLoading } = useLessons({ limit: 100 });

  const toggleSkill = useToggleSkill();
  const [togglingSkillId, setTogglingSkillId] = useState<string | null>(null);

  const handleToggleSkill = (skillId: string, enabled: boolean) => {
    setTogglingSkillId(skillId);
    toggleSkill.mutate(
      { skillId, enabled },
      { onSettled: () => setTogglingSkillId(null) },
    );
  };

  const skills = skillsData?.skills?.length ? skillsData.skills : DEMO_SKILLS;
  const invocations = invocationsData?.invocations?.length ? invocationsData.invocations : DEMO_INVOCATIONS;
  const agentRuns = runsData?.runs?.length ? runsData.runs : DEMO_RUNS;
  const lessons = lessonsData?.lessons?.length ? lessonsData.lessons : DEMO_LESSONS;

  const isInitialLoading = skillsLoading && invocationsLoading && runsLoading;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <Bot className="h-6 w-6 text-accent" />
          Agent Skill System
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Monitor and manage agent skills, invocations, and learned lessons
        </p>
      </div>

      <div className="flex items-center gap-1 border-b border-surface-border">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
              activeTab === tab.key
                ? 'border-accent text-accent'
                : 'border-transparent text-gray-400 hover:text-gray-300 hover:border-gray-600'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isInitialLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 text-accent animate-spin" />
          <span className="ml-3 text-gray-400 text-sm">Loading agent data...</span>
        </div>
      ) : (
        <>
          {activeTab === 'dashboard' && (
            <AgentDashboard skills={skills} invocations={invocations} agentRuns={agentRuns} isLoading={false} />
          )}
          {activeTab === 'skills' && (
            <AgentSkillList skills={skills} isLoading={false} onToggle={handleToggleSkill} togglingId={togglingSkillId} />
          )}
          {activeTab === 'invocations' && (
            <SkillInvocationTable invocations={invocations} isLoading={false} />
          )}
          {activeTab === 'lessons' && (
            <LessonsTable lessons={lessons} isLoading={false} />
          )}
        </>
      )}
    </div>
  );
}
