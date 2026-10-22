/**
 * Ánh xạ sự kiện SSE thật -> view model cho giao diện. Hàm thuần, không phụ
 * thuộc React hay ngôn ngữ hiển thị, để mọi trạng thái (bước nào xong, config
 * hợp lệ không, job đang ở đâu) chỉ đến từ sự kiện / API - không bao giờ đoán
 * từ câu trả lời của LLM.
 */

import { JOB_CANCELLED, JOB_FAILED, JOB_RUNNING, JOB_SUCCESS, type AgentEvent, type Verification } from "./events";

// Tool có nhãn dịch sẵn trong messages (Agent.tools.*). Tool khác hiện nguyên tên.
export const KNOWN_TOOLS = new Set([
  "list_my_datasets",
  "get_dataset_info",
  "get_dataset_schema",
  "list_models",
  "list_metrics",
  "read_reference",
  "submit_config",
  "start_training",
  "list_my_jobs",
  "get_job_info",
  "watch_job",
  "activate_model",
  "predict",
]);

export const KNOWN_AGENTS = new Set(["manager", "prompt-agent", "data-agent", "model-agent", "operation-agent"]);

// ------------------------------------------------------------------ lượt chat

export type StepStatus = "running" | "success" | "failed" | "needs_input";

export interface ToolTrace {
  name: string;
  status: "running" | "success" | "failed";
  error?: string;
}

export interface ActivityStep {
  id: string;
  kind: "agent" | "validation";
  agent: string;
  task?: string;
  status: StepStatus;
  tools: ToolTrace[];
  errors: string[];
  missing: string[];
  startedAt?: number;
  endedAt?: number;
}

export interface ConfigView {
  /** null = chưa có kết quả kiểm định. */
  valid: boolean | null;
  errors: string[];
  configId?: string;
  config?: Record<string, any>;
  jobId?: string;
  /** dataset_id lúc tạo config - lấy từ tham số tool của lượt đó. */
  datasetId?: string;
}

export interface TurnTrace {
  steps: ActivityStep[];
  configs: ConfigView[];
  jobIds: string[];
  /** dataset_id mà sub-agent vừa thao tác (lấy từ tham số tool, không từ chữ). */
  datasetId?: string;
  error?: string;
}

export const emptyTrace = (): TurnTrace => ({ steps: [], configs: [], jobIds: [] });

function clip(text: unknown, max = 240): string | undefined {
  if (text === null || text === undefined || text === "") return undefined;
  const value = String(text);
  return value.length > max ? `${value.slice(0, max)}…` : value;
}

function asList(value: unknown): string[] {
  if (Array.isArray(value)) return value.map(String).filter(Boolean);
  if (typeof value === "string" && value.trim()) return [value.trim()];
  return [];
}

/** Bước gần nhất của agent này - sự kiện tool luôn thuộc lượt agent đang chạy. */
function lastStepIndex(steps: ActivityStep[], agent: string): number {
  for (let i = steps.length - 1; i >= 0; i--) {
    if (steps[i].kind === "agent" && steps[i].agent === agent) return i;
  }
  return -1;
}

function patchStep(trace: TurnTrace, index: number, patch: (step: ActivityStep) => ActivityStep): TurnTrace {
  return { ...trace, steps: trace.steps.map((step, i) => (i === index ? patch(step) : step)) };
}

function newAgentStep(event: AgentEvent, agent: string, task?: unknown): ActivityStep {
  return {
    id: `${agent}-${event.seq ?? Math.random()}`,
    kind: "agent",
    agent,
    task: clip(task, 300),
    status: "running",
    tools: [],
    errors: [],
    missing: [],
    startedAt: event.time,
  };
}

/** Áp một sự kiện vào timeline của lượt chat đang chạy. Trả về object mới (immutable). */
export function applyTurnEvent(trace: TurnTrace, event: AgentEvent): TurnTrace {
  const agent = event.agent ?? "";

  switch (event.type) {
    case "agent_start": {
      if (agent === "manager") return trace;
      return { ...trace, steps: [...trace.steps, newAgentStep(event, agent, event.task)] };
    }

    case "agent_done": {
      const index = lastStepIndex(trace.steps, agent);
      if (index < 0) return trace;
      const missing = asList(event.missing);
      const status: StepStatus = !event.ok ? "failed" : missing.length ? "needs_input" : "success";
      const error = clip(event.error);
      return patchStep(trace, index, (step) => ({
        ...step,
        status,
        missing,
        errors: error ? [...step.errors, error] : step.errors,
        endedAt: event.time,
      }));
    }

    case "tool_start":
    case "tool_call": {
      const name = String(event.name ?? "");
      // ask_* là Manager giao việc - đã hiện thành bước của sub-agent rồi.
      if (!name || name.startsWith("ask_")) return trace;

      const datasetId = typeof event.arguments?.dataset_id === "string" ? event.arguments.dataset_id : undefined;
      let next: TurnTrace = datasetId ? { ...trace, datasetId } : trace;

      let index = lastStepIndex(next.steps, agent);
      if (index < 0) {
        // Tool gọi thẳng từ Manager (không qua sub-agent).
        next = { ...next, steps: [...next.steps, newAgentStep(event, agent)] };
        index = next.steps.length - 1;
      }

      if (event.type === "tool_start") {
        return patchStep(next, index, (step) => ({ ...step, tools: [...step.tools, { name, status: "running" }] }));
      }

      const done: ToolTrace = { name, status: event.ok ? "success" : "failed", error: event.ok ? undefined : clip(event.error) };
      next = patchStep(next, index, (step) => {
        const running = step.tools.map((t) => t.name === name && t.status === "running").lastIndexOf(true);
        const tools = running >= 0 ? step.tools.map((t, i) => (i === running ? done : t)) : [...step.tools, done];
        return { ...step, tools };
      });
      // Bước Manager tự gọi tool không có agent_done - coi như xong khi tool trả về.
      if (agent === "manager") {
        next = patchStep(next, index, (step) => ({
          ...step,
          status: step.tools.some((t) => t.status === "running") ? "running" : "success",
          endedAt: event.time,
        }));
      }
      return next;
    }

    case "config_checked": {
      const errors = asList(event.errors).map((e) => clip(e, 400) as string);
      const validation: ActivityStep = {
        id: `validation-${event.seq ?? Math.random()}`,
        kind: "validation",
        agent,
        status: event.ok ? "success" : "failed",
        tools: [],
        errors,
        missing: [],
        startedAt: event.time,
        endedAt: event.time,
      };
      return {
        ...trace,
        steps: [...trace.steps, validation],
        configs: [...trace.configs, { valid: Boolean(event.ok), errors, datasetId: trace.datasetId }],
      };
    }

    case "job_started": {
      const jobId = String(event.job_id);
      const view: ConfigView = { valid: true, errors: [], configId: event.config_id, config: event.config, jobId };
      // Gắn vào lần kiểm định hợp lệ gần nhất chưa có job.
      const index = trace.configs.map((c) => c.valid === true && !c.jobId).lastIndexOf(true);
      const configs =
        index >= 0
          ? trace.configs.map((c, i) => (i === index ? { ...c, ...view } : c))
          : [...trace.configs, { ...view, datasetId: trace.datasetId }];
      return { ...trace, configs, jobIds: [...trace.jobIds, jobId] };
    }

    case "turn_budget_exceeded":
      return { ...trace, error: clip(event.error) ?? "budget" };

    default:
      return trace;
  }
}

/** Bước đang chạy gần nhất và tool đang chạy của nó - để báo "đang làm gì". */
export function currentActivity(trace: TurnTrace | null): { agent: string; tool?: string } | null {
  if (!trace) return null;
  for (let i = trace.steps.length - 1; i >= 0; i--) {
    const step = trace.steps[i];
    if (step.status !== "running") continue;
    const tool = [...step.tools].reverse().find((t) => t.status === "running");
    return { agent: step.agent, tool: tool?.name };
  }
  return null;
}

// ------------------------------------------------------------------ lỗi cấu hình

export type ConfigField = "problem_type" | "target" | "features" | "metric" | "algorithm" | "max_time" | "general";

/**
 * Gắn mỗi lỗi kiểm định với trường liên quan. Lỗi do validate_config.py sinh
 * (văn bản cố định trong code, không phải chữ của LLM) và luôn nêu tên trường.
 */
export function configErrorField(error: string): ConfigField {
  const text = error.toLowerCase();
  if (text.includes("list_feature") || text.includes("đặc trưng")) return "features";
  if (text.startsWith("problem_type")) return "problem_type";
  if (text.includes("'target'") || text.includes("mục tiêu")) return "target";
  if (text.includes("metric_sort")) return "metric";
  if (text.includes("search_algorithm")) return "algorithm";
  if (text.includes("max_time")) return "max_time";
  return "general";
}

export function groupConfigErrors(errors: string[]): [ConfigField, string[]][] {
  const groups = new Map<ConfigField, string[]>();
  for (const error of errors) {
    const field = configErrorField(error);
    groups.set(field, [...(groups.get(field) ?? []), error]);
  }
  return [...groups.entries()];
}

// ------------------------------------------------------------------ job

export type JobStatus = "submitted" | "running" | "completed" | "failed" | "cancelled" | "unknown";

export interface LeaderboardRow {
  model: string;
  score: number | null;
}

export interface JobView {
  jobId: string;
  status: JobStatus;
  configId?: string;
  config?: Record<string, any>;
  dataset?: string;
  datasetId?: string;
  metric?: string;
  /** Giây job đã chạy, theo lần đổi trạng thái gần nhất watcher thấy. */
  elapsed?: number;
  submittedAt?: number;
  finishedAt?: number;
  /** Unix ms của thông tin mới nhất về job này (sự kiện hoặc lần làm mới từ API). */
  lastUpdated?: number;
  /** Thông tin mới nhất đến từ đâu - để người dùng biết dữ liệu có "live" không. */
  source?: "stream" | "api";
  bestModel?: string;
  bestScore?: number | null;
  bestScores?: Record<string, number>;
  leaderboard?: LeaderboardRow[];
  modelsScored?: number;
  verification?: Verification;
  error?: string;
  warning?: string;
  /** Model đã được kích hoạt để dự đoán (theo API backend). */
  activated?: boolean;
}

export const JOB_EVENT_TYPES = new Set([
  "job_started",
  "job_watch",
  "job_status",
  "job_done",
  "job_failed",
  "job_watch_timeout",
  "job_watch_warning",
]);

export const JOB_TERMINAL: JobStatus[] = ["completed", "failed", "cancelled", "unknown"];

export function isJobActive(job: JobView | undefined): boolean {
  return !!job && (job.status === "submitted" || job.status === "running");
}

function toLeaderboard(rows: unknown, metric: string | undefined): LeaderboardRow[] | undefined {
  if (!Array.isArray(rows)) return undefined;
  const key = (metric ?? "").trim().toLowerCase();
  return rows.map((row: any) => {
    const raw = row?.[key] ?? Object.entries(row ?? {}).find(([k]) => k !== "model")?.[1];
    return { model: String(row?.model ?? "?"), score: typeof raw === "number" ? raw : null };
  });
}

/** Áp một sự kiện job vào danh sách job. Trả về chính `jobs` nếu sự kiện không liên quan. */
export function applyJobEvent(jobs: Record<string, JobView>, event: AgentEvent): Record<string, JobView> {
  if (!event.type || !JOB_EVENT_TYPES.has(event.type) || !event.job_id) return jobs;

  const jobId = String(event.job_id);
  const at = typeof event.time === "number" ? event.time * 1000 : Date.now();
  const current: JobView = jobs[jobId] ?? { jobId, status: "submitted" };
  // Job đã kết thúc thì sự kiện tới muộn (trùng hoặc lệch thứ tự) không được kéo nó lùi lại.
  const finished = JOB_TERMINAL.includes(current.status);
  let next: JobView = { ...current, lastUpdated: at, source: "stream" };

  switch (event.type) {
    case "job_started":
      next = { ...next, configId: event.config_id, config: event.config, metric: event.config?.metric_sort, submittedAt: at };
      break;
    case "job_watch":
      break;
    case "job_status":
      if (finished) return jobs;
      if (typeof event.elapsed === "number") next.elapsed = event.elapsed;
      if (event.status === JOB_RUNNING) next.status = "running";
      break;
    case "job_done":
      next = {
        ...next,
        status: "completed",
        finishedAt: at,
        dataset: event.dataset ?? next.dataset,
        metric: event.metric_sort ?? next.metric,
        bestModel: event.best_model,
        bestScore: typeof event.best_score === "number" ? event.best_score : null,
        bestScores: event.best_model_scores ?? undefined,
        leaderboard: toLeaderboard(event.leaderboard, event.metric_sort ?? next.metric),
        modelsScored: event.models_scored,
        verification: event.verification,
        error: undefined,
        warning: undefined,
      };
      break;
    case "job_failed":
      next = {
        ...next,
        status: event.cancelled ? "cancelled" : "failed",
        finishedAt: at,
        dataset: event.dataset ?? next.dataset,
        error: clip(event.error, 400),
        warning: undefined,
      };
      break;
    case "job_watch_timeout":
      if (finished) return jobs;
      next = { ...next, status: "unknown", error: clip(event.error, 400) };
      break;
    case "job_watch_warning":
      next.warning = clip(event.error);
      break;
  }
  return { ...jobs, [jobId]: next };
}

// Metric sai số: nhỏ hơn là tốt hơn (khớp LOWER_IS_BETTER ở agent/watcher.py).
const LOWER_IS_BETTER = new Set(["mse", "mae", "mape", "rmse"]);

export function metricDirection(metric: string | undefined): "higher" | "lower" | null {
  if (!metric) return null;
  return LOWER_IS_BETTER.has(metric.trim().toLowerCase()) ? "lower" : "higher";
}

/**
 * Ghép bản ghi job từ GET /api/v1/inference/jobs (nút "Làm mới") vào view.
 * Cùng cách tính như summarize_job ở agent/watcher.py.
 */
export function mergeJobFromApi(current: JobView, raw: Record<string, any>, now: number): JobView {
  const status: JobStatus =
    raw.status === JOB_SUCCESS
      ? "completed"
      : raw.status === JOB_FAILED
        ? "failed"
        : raw.status === JOB_CANCELLED
          ? "cancelled"
          : raw.status === JOB_RUNNING
            ? "running"
            : current.status;

  const metric: string | undefined = raw.config?.metric_sort ?? current.metric;
  const next: JobView = {
    ...current,
    status,
    metric,
    config: current.config ?? raw.config ?? undefined,
    dataset: raw.data?.name ?? current.dataset,
    datasetId: raw.data?.id ?? current.datasetId,
    activated: raw.activate === 1,
    lastUpdated: now,
    source: "api",
    warning: undefined,
  };

  if (status === "completed") {
    const key = (metric ?? "").trim().toLowerCase();
    const entries: any[] = Array.isArray(raw.orther_model_scores) ? raw.orther_model_scores : [];
    const scored = entries.filter((e) => typeof e?.scores?.[key] === "number");
    const lower = metricDirection(metric) === "lower";
    scored.sort((a, b) => (lower ? a.scores[key] - b.scores[key] : b.scores[key] - a.scores[key]));
    const best = entries.find((e) => e?.model_name === raw.best_model);
    next.bestModel = raw.best_model ?? current.bestModel;
    next.bestScore = typeof raw.best_score === "number" ? raw.best_score : current.bestScore ?? null;
    next.bestScores = best?.scores ?? current.bestScores;
    next.leaderboard = scored.length
      ? scored.map((e) => ({ model: String(e.model_name), score: e.scores[key] }))
      : current.leaderboard;
    next.modelsScored = entries.length || current.modelsScored;
    next.error = undefined;
  } else if (status === "failed" || status === "cancelled") {
    next.error = clip(raw.infor, 400) ?? current.error;
  }
  // Không đặt finishedAt ở đây: API không cho biết job xong lúc nào, chỉ biết đã xong.
  return next;
}

// ------------------------------------------------------------------ chống trùng

/**
 * Hai luồng SSE (lượt chat và kênh nền) cùng đọc một EventBus, và kênh nền mở
 * lại với `after=last` - một sự kiện có thể tới hai lần. Mỗi seq chỉ nhận một lần.
 */
export function createSeqTracker() {
  const seen = new Set<number>();
  let last = 0;
  return {
    /** true nếu là sự kiện mới (chưa xử lý). */
    accept(seq: unknown): boolean {
      if (typeof seq !== "number" || seen.has(seq)) return false;
      seen.add(seq);
      if (seq > last) last = seq;
      return true;
    },
    get last() {
      return last;
    },
    reset() {
      seen.clear();
      last = 0;
    },
  };
}
