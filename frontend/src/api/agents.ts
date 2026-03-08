import client from './client';
import {
  SkillDefinition,
  SkillDefinitionListResponse,
  SkillInvocationListResponse,
  AgentRun,
  AgentRunListResponse,
  LearnedLessonListResponse,
  SkillQueryParams,
  InvocationQueryParams,
  AgentRunQueryParams,
  LessonQueryParams,
} from '../types/agent';

// --- Skills ---

export async function fetchSkills(params?: SkillQueryParams): Promise<SkillDefinitionListResponse> {
  const { data } = await client.get<SkillDefinitionListResponse>('/api/v1/agents/skills', {
    params,
  });
  return data;
}

export async function toggleSkill(
  skillId: string,
  enabled: boolean,
): Promise<SkillDefinition> {
  const { data } = await client.patch<SkillDefinition>(
    `/api/v1/agents/skills/${skillId}`,
    { enabled },
  );
  return data;
}

// --- Invocations ---

export async function fetchInvocations(
  params?: InvocationQueryParams,
): Promise<SkillInvocationListResponse> {
  const { data } = await client.get<SkillInvocationListResponse>(
    '/api/v1/agents/invocations',
    { params },
  );
  return data;
}

// --- Agent Runs ---

export async function fetchAgentRuns(
  params?: AgentRunQueryParams,
): Promise<AgentRunListResponse> {
  const { data } = await client.get<AgentRunListResponse>('/api/v1/agents/runs', {
    params,
  });
  return data;
}

export async function fetchAgentRun(runId: string): Promise<AgentRun> {
  const { data } = await client.get<AgentRun>(`/api/v1/agents/runs/${runId}`);
  return data;
}

// --- Lessons ---

export async function fetchLessons(
  params?: LessonQueryParams,
): Promise<LearnedLessonListResponse> {
  const { data } = await client.get<LearnedLessonListResponse>('/api/v1/agents/lessons', {
    params,
  });
  return data;
}
