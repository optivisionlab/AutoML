/**
 * Ánh xạ sự kiện SSE thật -> view model cho giao diện. Hàm thuần, không phụ
 * thuộc React hay ngôn ngữ hiển thị, để mọi trạng thái (bước nào xong, config
 * hợp lệ không, job đang ở đâu) chỉ đến từ sự kiện / API - không bao giờ đoán
 * từ câu trả lời của LLM.
 */

import {
  JOB_CANCELLED,
  JOB_FAILED,
  JOB_RUNNING,
  JOB_SUCCESS,
  type Activation,
  type ActivationConstraint,
  type AgentEvent,
  type Verification,
} from "./events";

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
  /** Cảnh báo của validate_config.py (không chặn job), vd lưu ý time_series. */
  warnings?: string[];
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
  /**
   * dataset_id của tool gọi THÀNH CÔNG gần nhất - dùng để đổi dataset đang làm việc.
   * datasetId ở trên có cả lúc tool mới bắt đầu (cần để gắn thẻ cấu hình), nên một
   * lời gọi hỏng với id sai/bịa sẽ không được kéo dataset đang làm việc theo.
   */
  activeDatasetId?: string;
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
      if (datasetId && event.type === "tool_call" && event.ok === true) next = { ...next, activeDatasetId: datasetId };

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
      const warnings = asList(event.warnings).map((w) => clip(w, 400) as string);
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
      // Config hợp lệ đi kèm config_id và nội dung, để thẻ cấu hình hiện đủ cả khi job chưa chạy được.
      const view: ConfigView = { valid: Boolean(event.ok), errors, warnings, datasetId: trace.datasetId };
      if (event.ok && event.config_id) Object.assign(view, { configId: event.config_id, config: event.config });
      return { ...trace, steps: [...trace.steps, validation], configs: [...trace.configs, view] };
    }

    case "job_started": {
      const jobId = String(event.job_id);
      const datasetId = typeof event.dataset_id === "string" && event.dataset_id ? event.dataset_id : undefined;
      const view: ConfigView = { valid: true, errors: [], configId: event.config_id, config: event.config, jobId };
      if (datasetId) view.datasetId = datasetId;
      // Gắn vào đúng thẻ có config_id đó. Không khớp (vd config chốt ở lượt trước) thì
      // chỉ được gắn theo vị trí vào lần kiểm định hợp lệ gần nhất chưa có job VÀ chưa
      // mang config_id (sự kiện kiểu cũ) - không bao giờ ghi đè thẻ của một config khác;
      // không có thẻ như vậy thì thêm thẻ mới.
      const byId = event.config_id ? trace.configs.map((c) => c.configId === event.config_id).lastIndexOf(true) : -1;
      const index =
        byId >= 0
          ? byId
          : trace.configs.map((c) => c.valid === true && !c.jobId && (!event.config_id || !c.configId)).lastIndexOf(true);
      const configs =
        index >= 0
          ? trace.configs.map((c, i) => (i === index ? { ...c, ...view } : c))
          : [...trace.configs, { ...view, datasetId: datasetId ?? trace.datasetId }];
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
  /** Nguồn điểm (audit AG-02): "holdout" tập kiểm tra riêng, "cv" cross-validation lạc quan, null không rõ. */
  scoreSource?: "holdout" | "cv" | null;
  error?: string;
  warning?: string;
  /** Model đã được kích hoạt để dự đoán (theo API backend). */
  activated?: boolean;
  /** Watcher tự kích hoạt model khi job xong (người dùng yêu cầu "train xong kích hoạt luôn"). */
  activation?: Activation;
  /**
   * Agent server đã mất phiên đang theo dõi job này (khởi động lại / phiên quá
   * hạn): không còn sự kiện nào về job nữa. Trạng thái thật phải lấy lại từ API.
   */
  lost?: boolean;
  /**
   * Job vẫn chạy (theo API) nhưng KHÔNG còn watcher nào theo dõi - sẽ không có sự kiện
   * kết quả. Có sau khi "Làm mới" một job mất dấu / hết giờ chờ; hết khi agent theo dõi lại.
   */
  untracked?: boolean;
  /** problem_type của job khi chưa có config (job chỉ biết qua job_watch / job_done). */
  problemType?: string;
  /**
   * Hệ thống sẽ TỰ kích hoạt model khi job xong (người dùng dặn "train xong kích hoạt luôn").
   * Hiện trên thẻ kèm nút huỷ; false sau khi huỷ (autoActivateCancelled).
   */
  autoActivate?: boolean;
  autoActivateCancelled?: boolean;
  /** Lời hứa tự kích hoạt hết hiệu lực (hết giờ theo dõi / mất phiên): người dùng tự kích hoạt. */
  autoActivateSkipped?: boolean;
  /**
   * Điều kiện server sẽ kiểm trước khi tự kích hoạt: [] = kích hoạt bất kể điểm,
   * undefined = chưa biết (sự kiện cũ không mang trường này).
   */
  autoActivateConstraints?: ActivationConstraint[];
}

/** auto_activate_constraints của sự kiện -> danh sách hợp lệ; không phải mảng thì undefined. */
export function parseConstraints(raw: unknown): ActivationConstraint[] | undefined {
  if (!Array.isArray(raw)) return undefined;
  return raw
    .filter((c): c is Record<string, unknown> => !!c && typeof c === "object")
    .filter((c) => typeof c.metric === "string" && typeof c.op === "string" && typeof c.value === "number")
    .map((c) => ({ metric: c.metric as string, op: c.op as string, value: c.value as number }));
}

function sameConstraints(a: ActivationConstraint[] | undefined, b: ActivationConstraint[] | undefined): boolean {
  if (a === b) return true;
  if (!a || !b || a.length !== b.length) return false;
  return a.every((c, i) => c.metric === b[i].metric && c.op === b[i].op && c.value === b[i].value);
}

export const JOB_EVENT_TYPES = new Set([
  "job_started",
  "job_watch",
  "job_status",
  "job_done",
  "job_failed",
  "job_watch_timeout",
  "job_watch_warning",
  "job_watch_resumed",
  "auto_activate_changed",
  "model_activation",
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
  // Bật / tắt model của một job cũ không có thẻ trong phiên: không dựng thẻ job "đã gửi" giả.
  if (event.type === "model_activation" && !jobs[String(event.job_id)]) return jobs;

  const jobId = String(event.job_id);
  const at = typeof event.time === "number" ? event.time * 1000 : Date.now();
  const current: JobView = jobs[jobId] ?? { jobId, status: "submitted" };
  // Job đã kết thúc thì sự kiện tới muộn (trùng hoặc lệch thứ tự) không được kéo nó lùi lại.
  const finished = JOB_TERMINAL.includes(current.status);
  // "unknown" (watcher hết giờ chờ, hoặc mất phiên) không phải kết thúc thật: job được
  // theo dõi lại (watch_job) thì sống lại và nhận tiếp trạng thái tới khi xong.
  const revivable = current.status === "unknown";
  let next: JobView = { ...current, lastUpdated: at, source: "stream" };
  // job_started / job_watch / job_done / job_failed mang dataset_id và problem_type: form dự đoán
  // cần chúng kể cả khi job chỉ được biết qua watch_job, hoặc job_started đã trôi khỏi bộ đệm.
  if (typeof event.dataset_id === "string" && event.dataset_id) next.datasetId = event.dataset_id;
  if (typeof event.problem_type === "string" && event.problem_type) next.problemType = event.problem_type;
  // job_started / job_watch mang cờ tự kích hoạt; auto_activate_changed khi người dùng đổi ý.
  if (typeof event.auto_activate === "boolean" && event.type !== "auto_activate_changed") next.autoActivate = event.auto_activate;
  // Lời hứa đang chờ trở lại (theo dõi lại rồi người dùng yêu cầu lại): lời nhắc "hết hiệu lực" cũ hết đúng.
  if (event.auto_activate === true && event.type !== "auto_activate_changed") next.autoActivateSkipped = undefined;
  // job_watch / job_status / auto_activate_changed: điều kiện THẬT sẽ được kiểm (thẻ không hứa
  // "nếu đạt ràng buộc" khi không có ràng buộc nào).
  const constraints = parseConstraints(event.auto_activate_constraints);
  if (constraints) next.autoActivateConstraints = constraints;
  const revive = () => {
    next = { ...next, status: "running", error: undefined, lost: undefined, untracked: undefined, finishedAt: undefined };
  };

  switch (event.type) {
    case "job_started":
      next = { ...next, configId: event.config_id, config: event.config, metric: event.config?.metric_sort, submittedAt: at };
      break;
    case "job_watch":
      // Có watcher theo dõi lại: sẽ có sự kiện kết quả.
      next.untracked = undefined;
      if (revivable) revive();
      break;
    case "job_status":
      if (finished && !(revivable && event.status === JOB_RUNNING)) return jobs;
      if (revivable) revive();
      if (typeof event.elapsed === "number") next.elapsed = event.elapsed;
      if (event.status === JOB_RUNNING) next.status = "running";
      next.untracked = undefined;
      // Watcher hỏi được backend nghĩa là cảnh báo cũ (vd phiên hết hạn) đã hết đúng.
      next.warning = undefined;
      break;
    case "job_done": {
      const activation = event.activation && typeof event.activation === "object" ? (event.activation as Activation) : undefined;
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
        scoreSource: event.score_source === "holdout" || event.score_source === "cv" ? event.score_source
          : "score_source" in event ? null : next.scoreSource,
        // job_done lặp (vd watch_job sau khi watcher đã báo) không mang activation: giữ kết quả cũ.
        activation: activation ?? next.activation,
        activated: activation?.ok ? true : next.activated,
        error: undefined,
        // Không đọc được kết quả chi tiết (bản ghi job dị dạng): đừng để thẻ trông như kết quả rỗng.
        warning: typeof event.summary_error === "string" ? clip(event.summary_error, 400) : undefined,
        lost: undefined,
        untracked: undefined,
        autoActivate: undefined,
        autoActivateSkipped: undefined,
      };
      break;
    }
    case "job_failed":
      next = {
        ...next,
        status: event.cancelled ? "cancelled" : "failed",
        finishedAt: at,
        dataset: event.dataset ?? next.dataset,
        error: clip(event.error, 400),
        warning: undefined,
        lost: undefined,
        untracked: undefined,
        autoActivate: undefined,
        autoActivateSkipped: undefined,
      };
      break;
    case "model_activation":
      // Người dùng bấm xác nhận bật / tắt model (thẻ hành động): chỉ đổi cờ kích hoạt, không đổi trạng thái job.
      next.activated = event.activated === true;
      break;
    case "auto_activate_changed":
      next.autoActivate = event.enabled === true;
      next.autoActivateCancelled = event.enabled === false ? true : undefined;
      if (event.enabled === true) next.autoActivateSkipped = undefined;
      break;
    case "job_watch_timeout":
      if (finished) {
        // Job đã "xong" theo nút Làm mới nhưng watcher hết giờ trước khi kịp kích hoạt: lời hứa
        // hết hiệu lực - thẻ không được tiếp tục hứa.
        if (!next.autoActivate && event.auto_activate_skipped !== true) return jobs;
        next = { ...next, autoActivate: undefined, autoActivateSkipped: event.auto_activate_skipped === true || next.autoActivateSkipped };
        break;
      }
      next = {
        ...next,
        status: "unknown",
        error: clip(event.error, 400),
        autoActivate: undefined,
        // Lần hết giờ sau (đã theo dõi lại) không mang cờ này: giữ lời nhắc "kích hoạt thủ công".
        autoActivateSkipped: event.auto_activate_skipped === true || next.autoActivateSkipped,
      };
      break;
    case "job_watch_warning":
      next.warning = clip(event.error);
      break;
    case "job_watch_resumed":
      next.warning = undefined;
      break;
  }
  return { ...jobs, [jobId]: next };
}

/**
 * Agent server mất phiên (khởi động lại, phiên quá hạn bị dọn): job đang chạy
 * không còn ai theo dõi, sẽ không có sự kiện nào nữa. Đánh dấu thay vì để thẻ
 * quay mãi - trạng thái thật lấy lại bằng nút "Làm mới" (API backend).
 */
export function markJobsLost(jobs: Record<string, JobView>): Record<string, JobView> {
  const affected = Object.values(jobs).filter((job) => isJobActive(job) || job.autoActivate);
  if (!affected.length) return jobs;
  const next = { ...jobs };
  for (const job of affected) {
    // Không còn watcher: không còn gì tự kích hoạt nữa (kể cả job "xong" theo Làm mới mà chưa kịp kích hoạt).
    const lostAuto = job.autoActivate ? { autoActivate: undefined, autoActivateSkipped: true } : {};
    next[job.jobId] = isJobActive(job)
      ? { ...job, ...lostAuto, status: "unknown", lost: true, warning: undefined }
      : { ...job, ...lostAuto };
  }
  return next;
}

/**
 * Job đang được theo dõi theo server (sự kiện hello / reconnect), kèm lời hứa tự kích hoạt.
 * Phiên dài thì sự kiện của job có thể đã trôi khỏi bộ đệm (500 sự kiện): tải lại trang vẫn
 * phải dựng lại được thẻ job đang chạy và nút huỷ tự kích hoạt.
 */
export function applyWatchState(
  jobs: Record<string, JobView>,
  watching: unknown,
  auto: unknown,
  autoConstraints?: unknown,
): Record<string, JobView> {
  const ids = Array.isArray(watching) ? watching.map(String) : [];
  const flags = auto && typeof auto === "object" ? (auto as Record<string, unknown>) : {};
  const conditions = autoConstraints && typeof autoConstraints === "object" ? (autoConstraints as Record<string, unknown>) : {};
  let next = jobs;
  for (const id of ids) {
    const current: JobView = next[id] ?? { jobId: id, status: "running" };
    const flag = flags[id];
    // Ảnh chụp có thể cũ hơn job_done vừa tới: không hứa lại trên job đã kết thúc.
    const ended = current.status === "completed" || current.status === "failed" || current.status === "cancelled";
    const autoActivate = flag === true ? (ended ? current.autoActivate : true) : flag === false ? undefined : current.autoActivate;
    const autoActivateConstraints =
      flag === true && !ended ? (parseConstraints(conditions[id]) ?? current.autoActivateConstraints) : current.autoActivateConstraints;
    const autoActivateSkipped = flag === true && !ended ? undefined : current.autoActivateSkipped;
    if (
      next[id] &&
      current.autoActivate === autoActivate &&
      current.autoActivateSkipped === autoActivateSkipped &&
      sameConstraints(current.autoActivateConstraints, autoActivateConstraints)
    )
      continue;
    next = { ...next, [id]: { ...current, autoActivate, autoActivateConstraints, autoActivateSkipped } };
  }
  return next;
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
  // Phản hồi "Làm mới" tới muộn hơn sự kiện kết thúc (đọc lúc job còn chạy): không kéo job đã
  // kết thúc lùi về "đang chạy" - sẽ không còn sự kiện nào sửa lại.
  const ended = current.status === "completed" || current.status === "failed" || current.status === "cancelled";
  if (ended && raw.status === JOB_RUNNING) return current;
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
  // Có trạng thái thật từ API thì không còn "mất dấu" nữa.
  const known = [JOB_SUCCESS, JOB_FAILED, JOB_CANCELLED, JOB_RUNNING].includes(raw.status);
  const next: JobView = {
    ...current,
    status,
    lost: known ? undefined : current.lost,
    // Job mất dấu / hết giờ chờ mà API báo vẫn chạy: không watcher nào còn theo dõi nó -
    // không được hiện như đang được theo dõi trực tiếp (sẽ không có kết quả tự về).
    untracked: status === "running" && (current.lost || current.status === "unknown" || current.untracked) ? true : undefined,
    // Không watcher nào theo dõi (mất dấu / hết giờ) thì không có gì tự kích hoạt; job xong thì lời hứa đã xử lý.
    // Job xong theo API nhưng watcher chưa kịp hỏi (tới ~20 giây): việc tự kích hoạt sắp diễn ra,
    // vẫn huỷ được - đừng giấu đi.
    autoActivate:
      (status === "running" || (status === "completed" && raw.activate !== 1)) &&
      !(current.lost || current.status === "unknown" || current.untracked)
        ? current.autoActivate
        : undefined,
    problemType: current.problemType ?? raw.config?.problem_type ?? undefined,
    error: known && status === "running" ? undefined : current.error,
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
