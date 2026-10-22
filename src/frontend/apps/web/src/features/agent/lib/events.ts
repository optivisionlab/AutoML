/**
 * Sự kiện agent server đẩy qua SSE - khớp với src/backend/agent (events.py,
 * team.py, agent_openai.py, watcher.py, server.py). Mọi sự kiện từ EventBus đều
 * có seq/type/time/agent; các trường còn lại tuỳ loại.
 */

export interface AgentEvent {
  seq?: number;
  type?: string;
  /** Unix time (giây), do EventBus gắn. */
  time?: number;
  agent?: string;
  [key: string]: any;
}

/** Trạng thái job ở backend v1 (src/core/constants.py). */
export const JOB_RUNNING = 0;
export const JOB_SUCCESS = 1;
export const JOB_FAILED = -1;
export const JOB_CANCELLED = -2;

export interface VerificationCheck {
  metric: string;
  op: string;
  value: number;
  score: number | null;
}

export interface Verification {
  passed: boolean | null;
  checks: VerificationCheck[];
}

/** Payload `reply` của /agent/chat/stream (ChatResponse ở server.py). */
export interface ChatReply {
  session_id: string;
  reply: string;
  tools: string[];
  agents: string[];
  total_tokens: number;
  watching: string[];
}

/** Response của /agent/upload. */
export interface UploadedDataset {
  id: string;
  name: string;
  type: "classification" | "regression";
  filename: string;
  size_bytes: number;
}

export interface HealthInfo {
  status: "ok" | "degraded";
  llm_ready: boolean;
  provider: string | null;
  model: string | null;
  configuration_error?: string;
}
