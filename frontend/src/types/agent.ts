// === Enums / Union Types ===

export type SkillExecutionType = 'DETERMINISTIC' | 'MODEL_ASSISTED' | 'HYBRID';
export type SkillStatus = 'SUCCESS' | 'FAILURE' | 'SKIPPED' | 'ERROR' | 'TIMEOUT';
export type SkillRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type AgentType = 'TRADE_DECISION' | 'FAILURE_ANALYSIS';

// === Skill Definition ===

export interface SkillDefinition {
  skill_id: string;
  name: string;
  description: string;
  version: string;
  execution_type: SkillExecutionType;
  risk_level: SkillRiskLevel;
  agent_type: AgentType;
  enabled: boolean;
  requires_human_review: boolean;
  timeout_seconds: number;
  created_at: string;
  updated_at: string;
}

export interface SkillDefinitionListResponse {
  skills: SkillDefinition[];
  total: number;
}

// === Skill Invocation ===

export interface SkillInvocation {
  invocation_id: string;
  skill_id: string;
  agent_run_id: string;
  agent_type: AgentType;
  status: SkillStatus;
  execution_time_ms: number;
  confidence: number | null;
  input_data: Record<string, unknown>;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  timestamp: string;
}

export interface SkillInvocationListResponse {
  invocations: SkillInvocation[];
  total: number;
}

// === Agent Run ===

export interface AgentRun {
  run_id: string;
  agent_type: AgentType;
  status: 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';
  skills_run: number;
  skills_failed: number;
  total_time_ms: number;
  trigger: string;
  symbol: string | null;
  started_at: string;
  completed_at: string | null;
  result_summary: Record<string, unknown> | null;
}

export interface AgentRunListResponse {
  runs: AgentRun[];
  total: number;
}

// === Learned Lesson ===

export interface LearnedLesson {
  lesson_id: string;
  title: string;
  description: string;
  category: string;
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  symbol: string | null;
  root_cause: string;
  recommendation: string;
  applied: boolean;
  agent_run_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface LearnedLessonListResponse {
  lessons: LearnedLesson[];
  total: number;
}

// === Query parameter types ===

export interface SkillQueryParams {
  agent_type?: AgentType;
  execution_type?: SkillExecutionType;
  enabled?: boolean;
}

export interface InvocationQueryParams {
  skill_id?: string;
  agent_type?: AgentType;
  status?: SkillStatus;
  limit?: number;
  offset?: number;
}

export interface AgentRunQueryParams {
  agent_type?: AgentType;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface LessonQueryParams {
  category?: string;
  severity?: string;
  applied?: boolean;
  limit?: number;
  offset?: number;
}
