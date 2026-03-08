import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchSkills,
  toggleSkill,
  fetchInvocations,
  fetchAgentRuns,
  fetchAgentRun,
  fetchLessons,
} from '../api/agents';
import {
  SkillQueryParams,
  InvocationQueryParams,
  AgentRunQueryParams,
  LessonQueryParams,
} from '../types/agent';
import { useAppStore } from '../store';

export function useSkills(params?: SkillQueryParams) {
  return useQuery({
    queryKey: ['skills', params],
    queryFn: () => fetchSkills(params),
    refetchInterval: 30000,
  });
}

export function useToggleSkill() {
  const queryClient = useQueryClient();
  const addNotification = useAppStore((s) => s.addNotification);

  return useMutation({
    mutationFn: ({ skillId, enabled }: { skillId: string; enabled: boolean }) =>
      toggleSkill(skillId, enabled),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['skills'] });
      addNotification({
        type: 'success',
        title: 'Skill Updated',
        message: `${data.name} has been ${data.enabled ? 'enabled' : 'disabled'}`,
      });
    },
    onError: (error: Error) => {
      addNotification({
        type: 'error',
        title: 'Skill Update Failed',
        message: error.message,
      });
    },
  });
}

export function useInvocations(params?: InvocationQueryParams) {
  return useQuery({
    queryKey: ['invocations', params],
    queryFn: () => fetchInvocations(params),
    refetchInterval: 10000,
  });
}

export function useAgentRuns(params?: AgentRunQueryParams) {
  return useQuery({
    queryKey: ['agentRuns', params],
    queryFn: () => fetchAgentRuns(params),
    refetchInterval: 10000,
  });
}

export function useAgentRun(runId: string | null) {
  return useQuery({
    queryKey: ['agentRun', runId],
    queryFn: () => fetchAgentRun(runId!),
    enabled: !!runId,
  });
}

export function useLessons(params?: LessonQueryParams) {
  return useQuery({
    queryKey: ['lessons', params],
    queryFn: () => fetchLessons(params),
    refetchInterval: 30000,
  });
}
