import { useState } from 'react';
import { Bot, Loader2 } from 'lucide-react';
import { useSkills, useToggleSkill, useInvocations, useAgentRuns, useLessons } from '../hooks/useAgents';
import AgentDashboard from '../components/agents/AgentDashboard';
import AgentSkillList from '../components/agents/AgentSkillList';
import SkillInvocationTable from '../components/agents/SkillInvocationTable';
import LessonsTable from '../components/agents/LessonsTable';

type TabKey = 'dashboard' | 'skills' | 'invocations' | 'lessons';

const TABS: { key: TabKey; label: string }[] = [
  { key: 'dashboard', label: 'Dashboard' },
  { key: 'skills', label: 'Skills' },
  { key: 'invocations', label: 'Invocations' },
  { key: 'lessons', label: 'Lessons' },
];

export default function AgentsPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('dashboard');

  const { data: skillsData, isLoading: skillsLoading } = useSkills();
  const { data: invocationsData, isLoading: invocationsLoading } = useInvocations({
    limit: 100,
  });
  const { data: runsData, isLoading: runsLoading } = useAgentRuns({ limit: 50 });
  const { data: lessonsData, isLoading: lessonsLoading } = useLessons({ limit: 100 });

  const toggleSkill = useToggleSkill();
  const [togglingSkillId, setTogglingSkillId] = useState<string | null>(null);

  const handleToggleSkill = (skillId: string, enabled: boolean) => {
    setTogglingSkillId(skillId);
    toggleSkill.mutate(
      { skillId, enabled },
      {
        onSettled: () => setTogglingSkillId(null),
      },
    );
  };

  const skills = skillsData?.skills ?? [];
  const invocations = invocationsData?.invocations ?? [];
  const agentRuns = runsData?.runs ?? [];
  const lessons = lessonsData?.lessons ?? [];

  const isInitialLoading = skillsLoading && invocationsLoading && runsLoading;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-100 flex items-center gap-2">
          <Bot className="h-6 w-6 text-accent" />
          Agent Skill System
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Monitor and manage agent skills, invocations, and learned lessons
        </p>
      </div>

      {/* Tab navigation */}
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

      {/* Tab content */}
      {isInitialLoading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 text-accent animate-spin" />
          <span className="ml-3 text-gray-400 text-sm">Loading agent data...</span>
        </div>
      ) : (
        <>
          {activeTab === 'dashboard' && (
            <AgentDashboard
              skills={skills}
              invocations={invocations}
              agentRuns={agentRuns}
              isLoading={skillsLoading || invocationsLoading || runsLoading}
            />
          )}

          {activeTab === 'skills' && (
            <AgentSkillList
              skills={skills}
              isLoading={skillsLoading}
              onToggle={handleToggleSkill}
              togglingId={togglingSkillId}
            />
          )}

          {activeTab === 'invocations' && (
            <SkillInvocationTable
              invocations={invocations}
              isLoading={invocationsLoading}
            />
          )}

          {activeTab === 'lessons' && (
            <LessonsTable lessons={lessons} isLoading={lessonsLoading} />
          )}
        </>
      )}
    </div>
  );
}
