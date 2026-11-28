import {
  ProgressMapNode,
  ProgressMapNodeStatus,
  ProgressMapPipeline,
} from "../constants/progressMapSample";
import {
  JobDetailPayload,
  ModelScoreDetail,
  ModelTrialDetail,
  PipelineBaseNode,
  PipelineData,
  PipelineNodeStatus,
  TrainingJob,
} from "@automl/domain";

export type GraphViewMode = "detailed" | "expanded" | "compact";

export const STANDARD_V2_PIPELINE_NODES: Record<
  string,
  { name: string; kind: string; depends_on: string[] }
> = {
  read_dataset: {
    name: "Read dataset",
    kind: "data_loading",
    depends_on: [],
  },
  split_holdout_data: {
    name: "Split holdout data",
    kind: "data_splitting",
    depends_on: ["read_dataset"],
  },
  read_training_data: {
    name: "Read training data",
    kind: "data_loading",
    depends_on: ["split_holdout_data"],
  },
  preprocessing: {
    name: "Preprocessing",
    kind: "preprocessing",
    depends_on: ["split_holdout_data"],
  },
  model_selection: {
    name: "Model selection",
    kind: "model_selection",
    depends_on: ["preprocessing"],
  },
  train: {
    name: "Train models",
    kind: "model_training",
    depends_on: ["model_selection"],
  },
  select_best: {
    name: "Select best model",
    kind: "model_selection",
    depends_on: ["train"],
  },
  save_result: {
    name: "Save result",
    kind: "result_storage",
    depends_on: ["select_best"],
  },
};

export const formatPipelineValue = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return "—";
    if (Number.isInteger(value)) return value.toLocaleString("en-US");
    return value.toFixed(4);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    return value
      .map((v) => (typeof v === "object" ? formatPipelineValue(v) : String(v)))
      .join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return "—";
    return entries.map(([k, v]) => `${k}: ${formatPipelineValue(v)}`).join(", ");
  }
  return String(value);
};

const normalizeRawStatus = (status?: PipelineNodeStatus | string | number | null): string => {
  if (status === null || status === undefined) return "";
  return String(status).trim().toLowerCase();
};

export const normalizeNodeStatus = (
  status?: PipelineNodeStatus | string | number | null,
): ProgressMapNodeStatus => {
  const s = normalizeRawStatus(status);
  if (["succeeded", "done", "success", "completed", "1"].includes(s)) {
    return "done";
  }
  if (["running", "0"].includes(s)) {
    return "running";
  }
  if (["failed", "error", "cancelled", "canceled", "-1", "-2"].includes(s)) {
    return "failed";
  }
  if (s === "skipped") {
    return "skipped";
  }
  return "pending"; // queued / pending / null
};

export const isJobCompleted = (status?: PipelineNodeStatus | string | number | null): boolean => {
  const s = normalizeRawStatus(status);
  return ["succeeded", "done", "success", "completed", "1"].includes(s);
};

export const isJobRunning = (status?: PipelineNodeStatus | string | number | null): boolean => {
  const s = normalizeRawStatus(status);
  return ["running", "0"].includes(s);
};

export const isJobQueued = (status?: PipelineNodeStatus | string | number | null): boolean => {
  const s = normalizeRawStatus(status);
  return ["queued", "pending"].includes(s);
};

export const isJobCancelled = (status?: PipelineNodeStatus | string | number | null): boolean => {
  const s = normalizeRawStatus(status);
  return ["cancelled", "canceled", "-2"].includes(s);
};

export const isJobFailed = (status?: PipelineNodeStatus | string | number | null): boolean => {
  const s = normalizeRawStatus(status);
  return ["failed", "error", "-1"].includes(s);
};

export const isJobTerminal = (status?: PipelineNodeStatus | string | number | null): boolean =>
  isJobCompleted(status) || isJobFailed(status) || isJobCancelled(status);

export const isJobActive = (status?: PipelineNodeStatus | string | number | null): boolean =>
  isJobRunning(status) || isJobQueued(status);

/**
 * Resolve the best trial object from v2.0.0 ModelScoreDetail (`trials[best_trial]`).
 */
export const resolveBestTrial = (model?: ModelScoreDetail | null): ModelTrialDetail | null => {
  if (!model || !Array.isArray(model.trials) || model.trials.length === 0) {
    return null;
  }

  if (typeof model.best_trial === "number") {
    const direct = model.trials[model.best_trial];
    if (direct) return direct;
    const matched = model.trials.find(
      (trial) => trial.trial_id === model.best_trial || trial.number === model.best_trial,
    );
    if (matched) return matched;
  }

  return (
    model.trials.find((trial) => normalizeNodeStatus(trial.status) === "done") ??
    model.trials[0] ??
    null
  );
};

/**
 * Resolve model evaluation scores supporting both v2.0.0 (`trials[best_trial].scores`, `best_scores`)
 * and v1.0.0 (`scores`).
 */
export const resolveModelScores = (
  model?: ModelScoreDetail | null,
): Record<string, number | null> => {
  if (!model) return {};
  const bestTrial = resolveBestTrial(model);
  const candidate =
    bestTrial?.scores ??
    bestTrial?.cv_scores ??
    model.best_scores ??
    model.scores ??
    null;

  if (!candidate || typeof candidate !== "object") return {};
  return candidate;
};

/**
 * Resolve model best hyperparameters supporting both v2.0.0 (`trials[best_trial].params`)
 * and v1.0.0 (`best_params`).
 */
export const resolveModelBestParams = (
  model?: ModelScoreDetail | null,
): Record<string, unknown> | null => {
  if (!model) return null;
  const bestTrial = resolveBestTrial(model);
  const candidate = bestTrial?.params ?? model.best_params ?? null;
  if (!candidate || typeof candidate !== "object") return null;
  return candidate;
};

/**
 * Resolve holdout scores for a specific model.
 */
export const resolveModelHoldoutScores = (
  model?: ModelScoreDetail | null,
): Record<string, number | null> | null => {
  if (!model?.holdout_scores || typeof model.holdout_scores !== "object") {
    return null;
  }
  return Object.keys(model.holdout_scores).length > 0 ? model.holdout_scores : null;
};

export const resolvePipelineHoldoutScores = (
  pipeline?: PipelineData | null,
  fallbackJob?: JobDetailPayload | TrainingJob | null,
): Record<string, number | null> | null => {
  const selectBestHoldout = pipeline?.select_best?.output?.holdout_scores;
  if (
    selectBestHoldout &&
    typeof selectBestHoldout === "object" &&
    Object.keys(selectBestHoldout).length > 0
  ) {
    return selectBestHoldout;
  }
  const bestModelName =
    pipeline?.select_best?.output?.best_model || fallbackJob?.best_model || null;
  if (bestModelName) {
    const modelHoldout = resolveModelHoldoutScores(
      pipeline?.train?.output?.models?.[bestModelName],
    );
    if (modelHoldout) return modelHoldout;
  }
  if (
    fallbackJob?.holdout_scores &&
    typeof fallbackJob.holdout_scores === "object" &&
    Object.keys(fallbackJob.holdout_scores).length > 0
  ) {
    return fallbackJob.holdout_scores;
  }
  return null;
};

export const resolveModelTrialStats = (
  model?: ModelScoreDetail | null,
): { nTrials: number | null; nPruned: number | null; bestTrial: number | null } => {
  if (!model) return { nTrials: null, nPruned: null, bestTrial: null };
  const trials = Array.isArray(model.trials) ? model.trials : null;
  const nTrials =
    typeof model.n_trials === "number"
      ? model.n_trials
      : trials
        ? trials.length
        : null;
  const nPruned =
    typeof model.n_pruned === "number"
      ? model.n_pruned
      : trials
        ? trials.filter((t) => normalizeRawStatus(t.status) === "pruned").length
        : null;
  const bestTrial = typeof model.best_trial === "number" ? model.best_trial : null;
  return { nTrials, nPruned, bestTrial };
};

export const calculateElapsed = (
  startedAt?: string | number | null,
  finishedAt?: string | number | null,
): string => {
  if (!startedAt) return "—";
  const start =
    typeof startedAt === "number"
      ? startedAt > 1e12
        ? startedAt
        : startedAt * 1000
      : new Date(startedAt).getTime();
  const end = finishedAt
    ? typeof finishedAt === "number"
      ? finishedAt > 1e12
        ? finishedAt
        : finishedAt * 1000
      : new Date(finishedAt).getTime()
    : Date.now();

  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "—";
  const diffSec = Math.round((end - start) / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return `${mins}m ${secs}s`;
};

export const getKindBadgeLabel = (kind?: string): string => {
  switch (kind) {
    case "data_loading":
      return "Tải dữ liệu";
    case "data_splitting":
      return "Chia dữ liệu";
    case "preprocessing":
      return "Tiền xử lý";
    case "preprocessing_branch":
      return "Nhánh tiền xử lý";
    case "model_selection":
      return "Chọn mô hình";
    case "model_training":
      return "Huấn luyện";
    case "hpo_tuning":
      return "Tối ưu HPO";
    case "holdout_evaluation":
      return "Đánh giá Holdout";
    case "result_storage":
      return "Lưu kết quả";
    default:
      return kind ? kind.replace(/_/g, " ") : "Giai đoạn";
  }
};

const LOWER_IS_BETTER_METRICS = new Set(["mse", "mae", "mape", "rmse", "log_loss", "loss"]);

export const getMetricDirection = (
  metricKey: string,
  metricsConfig?: Record<string, string>,
): "minimize" | "maximize" => {
  const configured = metricsConfig?.[metricKey];
  if (configured === "minimize" || configured === "maximize") {
    return configured;
  }
  return LOWER_IS_BETTER_METRICS.has(metricKey.trim().toLowerCase())
    ? "minimize"
    : "maximize";
};

/**
 * Normalize a `models` structure that could be a Record<string, ModelScoreDetail> OR an Array.
 */
const normalizeModelsRecord = (rawModels: unknown): Record<string, ModelScoreDetail> => {
  if (!rawModels) return {};
  if (Array.isArray(rawModels)) {
    const record: Record<string, ModelScoreDetail> = {};
    for (const item of rawModels) {
      if (!item || typeof item !== "object") continue;
      const entry = item as Record<string, unknown>;
      const name = String(entry.model_name || entry.model || entry.name || "").trim();
      if (!name) continue;
      record[name] = {
        status: (entry.status as PipelineNodeStatus) ?? "succeeded",
        error: (entry.error as string | null) ?? null,
        trials: Array.isArray(entry.trials) ? (entry.trials as ModelTrialDetail[]) : null,
        best_trial: typeof entry.best_trial === "number" ? entry.best_trial : null,
        best_scores:
          entry.best_scores && typeof entry.best_scores === "object"
            ? (entry.best_scores as Record<string, number | null>)
            : null,
        holdout_scores:
          entry.holdout_scores && typeof entry.holdout_scores === "object"
            ? (entry.holdout_scores as Record<string, number | null>)
            : null,
        scores:
          entry.scores && typeof entry.scores === "object"
            ? (entry.scores as Record<string, number | null>)
            : null,
        best_params:
          entry.best_params && typeof entry.best_params === "object"
            ? (entry.best_params as Record<string, unknown>)
            : null,
        n_trials: typeof entry.n_trials === "number" ? entry.n_trials : null,
        n_pruned: typeof entry.n_pruned === "number" ? entry.n_pruned : null,
      };
    }
    return record;
  }
  if (typeof rawModels === "object") {
    return rawModels as Record<string, ModelScoreDetail>;
  }
  return {};
};

const extractCandidateModelNames = (pipeline: PipelineData): string[] => {
  const names: string[] = [];
  const pushList = (val: unknown) => {
    if (!Array.isArray(val)) return;
    for (const item of val) {
      if (typeof item === "string" && item.trim()) {
        names.push(item.trim());
      } else if (item && typeof item === "object") {
        const obj = item as Record<string, unknown>;
        const n = obj.model_name || obj.model || obj.name;
        if (typeof n === "string" && n.trim()) names.push(n.trim());
      }
    }
  };

  const ms = pipeline.model_selection as any;
  const tr = pipeline.train as any;
  pushList(ms?.params?.model_names);
  pushList(ms?.params?.models);
  pushList(ms?.output?.model_names);
  pushList(ms?.output?.models);
  pushList(tr?.params?.model_names);
  pushList(tr?.params?.models);

  const rawModels = tr?.output?.models ?? tr?.models;
  const normalizedModels = normalizeModelsRecord(rawModels);
  names.push(...Object.keys(normalizedModels));

  return Array.from(new Set(names));
};

/**
 * Build a fallback v2.0.0 PipelineData structure from a TrainingJob record when `job.pipeline`
 * has not been persisted yet (e.g. freshly queued job or legacy job before pipeline v2.0.0).
 */
export const buildFallbackPipelineFromJob = (job: TrainingJob): PipelineData => {
  const jobId = job.job_id || job._id || job.id || null;
  const completed = isJobCompleted(job.status);
  const failed = isJobFailed(job.status);
  const cancelled = isJobCancelled(job.status);
  const running = isJobRunning(job.status);

  const rootStatus: PipelineNodeStatus = completed
    ? "succeeded"
    : cancelled
      ? "cancelled"
      : failed
        ? "failed"
        : running
          ? "running"
          : "queued";

  const problemType = job.config?.problem_type || "regression";
  const metricSort =
    job.config?.metric_sort || (problemType === "classification" ? "accuracy" : "r2");

  const defaultMetrics: Record<string, string> =
    problemType === "classification"
      ? { accuracy: "maximize", f1: "maximize", precision: "maximize", recall: "maximize" }
      : { r2: "maximize", mse: "minimize", mae: "minimize", mape: "minimize" };

  if (!defaultMetrics[metricSort]) {
    defaultMetrics[metricSort] = getMetricDirection(metricSort);
  }

  const modelsRecord: Record<string, ModelScoreDetail> = {};
  const modelNames: string[] = [];

  if (Array.isArray(job.orther_model_scores)) {
    for (const entry of job.orther_model_scores) {
      const mName = entry.model_name || entry.model;
      if (!mName) continue;
      modelNames.push(mName);
      modelsRecord[mName] = {
        status: completed ? "succeeded" : rootStatus,
        error: null,
        best_params: mName === job.best_model ? job.best_params ?? null : null,
        scores:
          entry.scores ?? (typeof entry.score === "number" ? { [metricSort]: entry.score } : {}),
        best_scores:
          entry.scores ?? (typeof entry.score === "number" ? { [metricSort]: entry.score } : {}),
      };
    }
  } else if (job.best_model && completed) {
    modelNames.push(job.best_model);
    modelsRecord[job.best_model] = {
      status: "succeeded",
      error: null,
      best_params: job.best_params ?? null,
      scores: typeof job.best_score === "number" ? { [metricSort]: job.best_score } : {},
      best_scores: typeof job.best_score === "number" ? { [metricSort]: job.best_score } : {},
    };
  }

  const stepStatus = (step: keyof typeof STANDARD_V2_PIPELINE_NODES): PipelineNodeStatus => {
    if (completed) return "succeeded";
    if (cancelled) return step === "read_dataset" ? "cancelled" : "queued";
    if (failed)
      return step === "train"
        ? "failed"
        : step === "select_best" || step === "save_result"
          ? "queued"
          : "succeeded";
    if (running) return step === "read_dataset" ? "running" : "queued";
    return "queued";
  };

  return {
    job_id: jobId,
    version: "2.0.0",
    mode: job.config?.choose || "automl",
    status: rootStatus,
    error: job.error ?? (failed || cancelled ? job.infor ?? null : null),
    read_dataset: {
      ...STANDARD_V2_PIPELINE_NODES.read_dataset,
      status: stepStatus("read_dataset"),
      params: { id_data: job.data?.name || job.data?.id || jobId },
      output: {},
    },
    split_holdout_data: {
      ...STANDARD_V2_PIPELINE_NODES.split_holdout_data,
      status: stepStatus("split_holdout_data"),
      params: {},
      output: {},
    },
    preprocessing: {
      ...STANDARD_V2_PIPELINE_NODES.preprocessing,
      status: stepStatus("preprocessing"),
      params: {
        list_feature: job.config?.list_feature || [],
        target: job.config?.target || null,
      },
      output: {},
    },
    model_selection: {
      ...STANDARD_V2_PIPELINE_NODES.model_selection,
      status: stepStatus("model_selection"),
      params: {
        problem_type: problemType,
        model_names: modelNames,
        search_algorithm: job.config?.search_algorithm || null,
        metric_sort: metricSort,
        metrics: defaultMetrics,
      },
      output: {},
    },
    train: {
      ...STANDARD_V2_PIPELINE_NODES.train,
      status: stepStatus("train"),
      error: failed ? job.error ?? job.infor ?? null : null,
      params: {},
      output: {
        models: modelsRecord,
      },
    },
    select_best: {
      ...STANDARD_V2_PIPELINE_NODES.select_best,
      status: stepStatus("select_best"),
      params: { dependency_policy: "all_terminal" },
      output: {
        best_model: job.best_model || null,
        holdout_scores: job.holdout_scores ?? null,
      },
    },
    save_result: {
      ...STANDARD_V2_PIPELINE_NODES.save_result,
      status: stepStatus("save_result"),
      params: {},
      output: {},
    },
  };
};

const isDirectPipelineObject = (obj: Record<string, unknown>): boolean => {
  const standardKeys = Object.keys(STANDARD_V2_PIPELINE_NODES);
  return standardKeys.some((k) => {
    const val = obj[k];
    return val !== null && val !== undefined && typeof val === "object" && !Array.isArray(val);
  });
};

/**
 * Normalize a job detail payload into a complete `PipelineData` object.
 * Supports:
 * 1. Direct `PipelineData` returned inside `GET /api/v1/inference/jobs/{id}` (`response.data`)
 * 2. A `TrainingJob` object with a nested `.pipeline` field
 * 3. A legacy `TrainingJob` without `.pipeline` (synthesized via `buildFallbackPipelineFromJob`)
 */
export const normalizePipelineFromJob = (
  input: JobDetailPayload | TrainingJob | PipelineData,
): PipelineData => {
  const job = input as JobDetailPayload;
  const inputObj = input as Record<string, unknown>;

  const nestedPipeline =
    inputObj?.pipeline && typeof inputObj.pipeline === "object"
      ? (inputObj.pipeline as Record<string, unknown>)
      : null;

  const rawPipeline: Record<string, unknown> | null =
    nestedPipeline && Object.keys(nestedPipeline).length > 0
      ? nestedPipeline
      : inputObj && isDirectPipelineObject(inputObj)
        ? inputObj
        : null;

  if (!rawPipeline || Object.keys(rawPipeline).length === 0) {
    return buildFallbackPipelineFromJob(job as TrainingJob);
  }

  // Unwrap if backend ever nests nodes under `pipeline.nodes`
  const source: Record<string, unknown> =
    rawPipeline.nodes && typeof rawPipeline.nodes === "object" && !Array.isArray(rawPipeline.nodes)
      ? { ...rawPipeline, ...(rawPipeline.nodes as Record<string, unknown>) }
      : { ...rawPipeline };

  const fallback = buildFallbackPipelineFromJob(job as TrainingJob);
  const result: PipelineData = {
    ...(source as PipelineData),
    job_id: (source.job_id as string | null) ?? fallback.job_id,
    version: (source.version as string) ?? fallback.version,
    mode: (source.mode as string) ?? fallback.mode,
    status: (source.status as PipelineNodeStatus) ?? fallback.status,
  };

  // Check whether any node key exists in source
  const standardKeys = Object.keys(STANDARD_V2_PIPELINE_NODES);
  const hasAnyNode = Object.keys(source).some((k) => {
    const val = source[k] as Record<string, unknown> | null;
    return (
      val &&
      typeof val === "object" &&
      !Array.isArray(val) &&
      (standardKeys.includes(k) || (typeof val.name === "string" && Array.isArray(val.depends_on)))
    );
  });

  if (!hasAnyNode) {
    return fallback;
  }

  // Ensure standard nodes have required name/kind/depends_on defaults
  for (const key of standardKeys) {
    const rawNode = source[key] as Partial<PipelineBaseNode> | undefined;
    if (!rawNode || typeof rawNode !== "object" || Array.isArray(rawNode)) continue;
    const defaults = STANDARD_V2_PIPELINE_NODES[key];
    result[key] = {
      name: typeof rawNode.name === "string" ? rawNode.name : defaults.name,
      kind: typeof rawNode.kind === "string" ? rawNode.kind : defaults.kind,
      depends_on: Array.isArray(rawNode.depends_on) ? rawNode.depends_on : [...defaults.depends_on],
      status: rawNode.status ?? null,
      started_at: rawNode.started_at ?? null,
      finished_at: rawNode.finished_at ?? null,
      error: rawNode.error ?? null,
      params: rawNode.params && typeof rawNode.params === "object" ? { ...rawNode.params } : {},
      output: rawNode.output && typeof rawNode.output === "object" ? { ...rawNode.output } : {},
    };
  }

  // Normalize & enrich `train.output.models` from `train.models` or `job.orther_model_scores` if empty
  if (result.train) {
    const existingModels = normalizeModelsRecord(
      result.train.output?.models ?? (result.train as any).models,
    );
    const fallbackModels = fallback.train?.output?.models ?? {};
    const mergedModels: Record<string, ModelScoreDetail> =
      Object.keys(existingModels).length > 0 ? { ...existingModels } : { ...fallbackModels };

    // Hydrate best_params from job if best_model is missing it
    if (
      job.best_model &&
      mergedModels[job.best_model] &&
      !resolveModelBestParams(mergedModels[job.best_model]) &&
      job.best_params
    ) {
      mergedModels[job.best_model] = {
        ...mergedModels[job.best_model],
        best_params: job.best_params,
      };
    }

    result.train = {
      ...result.train,
      output: {
        ...(result.train.output ?? {}),
        models: mergedModels,
      },
    };
  }

  // Enrich `model_selection.params.model_names` if missing
  if (result.model_selection) {
    const candidateNames = extractCandidateModelNames(result);
    result.model_selection = {
      ...result.model_selection,
      params: {
        ...(fallback.model_selection?.params ?? {}),
        ...(result.model_selection.params ?? {}),
        model_names:
          candidateNames.length > 0
            ? candidateNames
            : fallback.model_selection?.params?.model_names ?? [],
      },
    };
  }

  // Enrich `preprocessing.params` with job.config fallback
  if (result.preprocessing && job.config) {
    result.preprocessing = {
      ...result.preprocessing,
      params: {
        list_feature: job.config.list_feature ?? [],
        target: job.config.target ?? null,
        ...(result.preprocessing.params ?? {}),
      },
    };
  }

  // Enrich `select_best.output` with job.best_model / job.holdout_scores if missing
  if (result.select_best) {
    result.select_best = {
      ...result.select_best,
      output: {
        ...(result.select_best.output ?? {}),
        best_model: result.select_best.output?.best_model ?? job.best_model ?? null,
        holdout_scores:
          result.select_best.output?.holdout_scores ?? job.holdout_scores ?? null,
      },
    };
  }

  return result;
};

interface BuildGraphOptions {
  mode?: GraphViewMode;
}

export const buildProgressMapFromPipeline = (
  pipeline: PipelineData,
  options: BuildGraphOptions = { mode: "detailed" },
): ProgressMapPipeline => {
  const mode = options.mode || "detailed";
  const bestModelName = pipeline.select_best?.output?.best_model;
  const targetCol =
    pipeline.preprocessing?.params?.target ||
    (pipeline as any).config?.target ||
    "target";
  const metricSort =
    pipeline.model_selection?.params?.metric_sort ||
    (pipeline as any).config?.metric_sort ||
    "r2";
  const searchAlgorithm =
    pipeline.model_selection?.params?.search_algorithm ||
    (pipeline as any).config?.search_algorithm ||
    null;

  const standardKeys = [
    "read_dataset",
    "split_holdout_data",
    "read_training_data",
    "preprocessing",
    "model_selection",
    "train",
    "select_best",
    "save_result",
  ];

  // Collect all valid pipeline node objects (accept both standard node keys and custom DAG nodes)
  const nodeKeys = Object.keys(pipeline).filter((k) => {
    const val = (pipeline as any)[k];
    if (!val || typeof val !== "object" || Array.isArray(val)) return false;
    if (standardKeys.includes(k)) return true;
    return typeof val.name === "string" && Array.isArray(val.depends_on);
  });

  const orderedKeys = Array.from(
    new Set([...standardKeys.filter((k) => nodeKeys.includes(k)), ...nodeKeys]),
  );

  type InternalNode = {
    id: string;
    originalKey?: string;
    name: string;
    kind: string;
    status: ProgressMapNodeStatus;
    depends_on: string[];
    dashed_depends_on?: string[];
    started_at?: string | number | null;
    finished_at?: string | number | null;
    error?: string | null;
    params?: Record<string, unknown>;
    output?: Record<string, unknown>;
    result?: Record<string, string | number | boolean>;
    subtitle?: string;
    metricBadge?: string;
    branch?: string;
    modelName?: string;
    isBestModel?: boolean;
    modelsList?: Record<string, ModelScoreDetail>;
    trials?: ModelTrialDetail[] | null;
    bestTrial?: number | null;
    holdoutScores?: Record<string, number | null> | null;
    nTrials?: number | null;
    nPruned?: number | null;
  };

  const intermediateNodes: InternalNode[] = [];
  const prepSubNodeIds: string[] = [];
  const trainTerminalBranchIds: string[] = [];

  const splitSkipped = normalizeNodeStatus(pipeline.split_holdout_data?.status) === "skipped";
  const resolvedHoldoutForBest = resolvePipelineHoldoutScores(pipeline);
  const hasHoldoutPath =
    mode === "detailed" &&
    Boolean(pipeline.split_holdout_data) &&
    !splitSkipped &&
    (Boolean(pipeline.split_holdout_data?.output?.holdout_rows) ||
      Boolean(resolvedHoldoutForBest) ||
      pipeline.select_best?.output?.score_source === "holdout");

  for (const key of orderedKeys) {
    const raw = (pipeline as any)[key];
    if (!raw) continue;
    const defaultMeta = STANDARD_V2_PIPELINE_NODES[key];
    const nodeDependsOn: string[] = Array.isArray(raw.depends_on)
      ? raw.depends_on
      : defaultMeta
        ? [...defaultMeta.depends_on]
        : [];
    const nodeName = typeof raw.name === "string" ? raw.name : defaultMeta?.name || key;
    const nodeKind = typeof raw.kind === "string" ? raw.kind : defaultMeta?.kind || "step";

    // Detailed mode: Expand preprocessing column-type sub-branches (numeric / categorical / text)
    if (key === "preprocessing") {
      const resultObj: Record<string, string | number | boolean> = {};
      if (raw.output && typeof raw.output === "object") {
        Object.entries(raw.output).forEach(([k, v]) => {
          if (v !== null && v !== undefined && typeof v !== "object") {
            resultObj[k] = typeof v === "number" ? Number(v.toFixed(4)) : String(v);
          }
        });
      }

      const featureCount = Array.isArray(raw.params?.list_feature)
        ? raw.params.list_feature.length
        : null;
      const nFeaturesOut =
        typeof raw.output?.n_features === "number" ? raw.output.n_features : null;

      intermediateNodes.push({
        id: key,
        originalKey: key,
        name: nodeName,
        kind: nodeKind,
        status: normalizeNodeStatus(raw.status),
        depends_on: nodeDependsOn,
        started_at: raw.started_at,
        finished_at: raw.finished_at,
        error: raw.error,
        params: raw.params || {},
        output: raw.output || {},
        result: resultObj,
        subtitle: getKindBadgeLabel(nodeKind),
        metricBadge:
          nFeaturesOut !== null
            ? `${nFeaturesOut} đặc trưng`
            : featureCount !== null && featureCount > 0
              ? `${featureCount} đầu vào`
              : undefined,
      });

      if (mode === "detailed") {
        const transformers = raw.params?.transformers as Record<string, string[]> | undefined;
        const columnTypes = raw.output?.column_types as Record<string, string[]> | null | undefined;
        const branchDefs: Array<{
          branchKey: "numeric" | "categorical" | "text";
          label: string;
        }> = [
          { branchKey: "numeric", label: "Numeric Pipeline" },
          { branchKey: "categorical", label: "Categorical Pipeline" },
          { branchKey: "text", label: "Text Pipeline" },
        ];

        const activeBranches = branchDefs.filter(({ branchKey }) => {
          const cols = columnTypes?.[branchKey];
          const steps = transformers?.[branchKey];
          return (Array.isArray(cols) && cols.length > 0) || (Array.isArray(steps) && steps.length > 0);
        });

        // Only branch preprocessing when there are at least 2 active column-type pipelines
        if (activeBranches.length >= 2) {
          for (const { branchKey, label } of activeBranches) {
            const cols = Array.isArray(columnTypes?.[branchKey]) ? columnTypes![branchKey] : [];
            const steps = Array.isArray(transformers?.[branchKey]) ? transformers![branchKey] : [];
            const hasColsInfo = columnTypes !== null && columnTypes !== undefined;
            const branchStatus: ProgressMapNodeStatus =
              hasColsInfo && cols.length === 0
                ? "skipped"
                : normalizeNodeStatus(raw.status);
            const subId = `prep_${branchKey}`;
            prepSubNodeIds.push(subId);

            intermediateNodes.push({
              id: subId,
              originalKey: "preprocessing",
              name: label,
              kind: "preprocessing_branch",
              status: branchStatus,
              depends_on: ["preprocessing"],
              started_at: raw.started_at,
              finished_at: raw.finished_at,
              params: {
                transformers: steps,
              },
              output: {
                columns: cols,
                column_count: cols.length,
              },
              subtitle: steps.length > 0 ? steps.join(" → ") : "Biến đổi cột",
              metricBadge: hasColsInfo ? `${cols.length} cột` : `${steps.length} bước`,
              branch: `Tiền xử lý · ${branchKey}`,
            });
          }
        }
      }
      continue;
    }

    // Expanded & Detailed mode: Branch `train` into parallel model nodes (+ HPO sub-nodes in detailed mode)
    if (key === "train" && (mode === "expanded" || mode === "detailed")) {
      const modelsMap = normalizeModelsRecord(raw.output?.models ?? raw.models);
      const modelNames = extractCandidateModelNames(pipeline);

      if (modelNames.length > 0) {
        for (const modelName of modelNames) {
          const detail: ModelScoreDetail = modelsMap[modelName] || {
            status: raw.status ?? null,
            error: null,
            trials: null,
            best_trial: null,
            best_scores: null,
            best_params: null,
            scores: null,
          };

          const resolvedScores = resolveModelScores(detail);
          const resolvedParams = resolveModelBestParams(detail) || {};
          const resolvedHoldout = resolveModelHoldoutScores(detail);
          const trialStats = resolveModelTrialStats(detail);

          const subId = `model_${modelName}`;
          const resultFormatted: Record<string, string | number | boolean> = {};
          Object.entries(resolvedScores).forEach(([scoreKey, scoreVal]) => {
            if (scoreVal !== null && scoreVal !== undefined) {
              resultFormatted[scoreKey] =
                typeof scoreVal === "number" ? Number(scoreVal.toFixed(4)) : String(scoreVal);
            }
          });
          if (trialStats.nTrials !== null) {
            resultFormatted.n_trials = trialStats.nTrials;
          }
          if (trialStats.bestTrial !== null) {
            resultFormatted.best_trial = trialStats.bestTrial;
          }

          const effectiveStatus =
            detail.status !== undefined && detail.status !== null
              ? normalizeNodeStatus(detail.status)
              : normalizeNodeStatus(raw.status);

          const primaryScore =
            resolvedScores[metricSort] ??
            Object.values(resolvedScores).find((v) => typeof v === "number") ??
            null;
          const primaryScoreKey =
            resolvedScores[metricSort] !== undefined
              ? metricSort
              : Object.keys(resolvedScores)[0] || metricSort;

          const metricBadge =
            typeof primaryScore === "number"
              ? `${primaryScoreKey.toUpperCase()}: ${formatPipelineValue(primaryScore)}`
              : effectiveStatus === "running"
                ? "Đang huấn luyện..."
                : undefined;

          const rawOutputForInspector: Record<string, unknown> = {
            ...resolvedScores,
          };
          if (resolvedHoldout) {
            rawOutputForInspector.holdout_scores = resolvedHoldout;
          }
          if (trialStats.bestTrial !== null) {
            rawOutputForInspector.best_trial = trialStats.bestTrial;
          }
          if (trialStats.nTrials !== null) {
            rawOutputForInspector.n_trials = trialStats.nTrials;
          }
          if (trialStats.nPruned !== null) {
            rawOutputForInspector.n_pruned = trialStats.nPruned;
          }

          const hasHpoDetails =
            mode === "detailed" &&
            (trialStats.nTrials !== null ||
              (Array.isArray(detail.trials) && detail.trials.length > 0) ||
              Object.keys(resolvedParams).length > 0 ||
              Boolean(searchAlgorithm));

          intermediateNodes.push({
            id: subId,
            originalKey: "train",
            modelName,
            name: modelName,
            kind: "model_training",
            status: effectiveStatus,
            depends_on: nodeDependsOn.length > 0 ? nodeDependsOn : ["model_selection"],
            started_at: detail.started_at ?? raw.started_at,
            finished_at: detail.finished_at ?? raw.finished_at,
            error: detail.error || null,
            params: resolvedParams,
            output: rawOutputForInspector,
            result: resultFormatted,
            subtitle:
              trialStats.nTrials !== null
                ? `${trialStats.nTrials} trials${trialStats.bestTrial !== null ? ` · Best #${trialStats.bestTrial}` : ""}`
                : "Mô hình song song",
            metricBadge,
            branch: `Nhánh ${modelName}`,
            isBestModel: bestModelName === modelName,
            trials: detail.trials ?? null,
            bestTrial: trialStats.bestTrial,
            holdoutScores: resolvedHoldout,
            nTrials: trialStats.nTrials,
            nPruned: trialStats.nPruned,
          });

          if (hasHpoDetails) {
            const hpoId = `hpo_${modelName}`;
            trainTerminalBranchIds.push(hpoId);

            const hpoTitle = searchAlgorithm
              ? `HPO (${searchAlgorithm})`
              : "Tối ưu HPO";
            const hpoBadge =
              trialStats.nTrials !== null
                ? `${trialStats.nTrials} trials${trialStats.nPruned ? ` · ${trialStats.nPruned} pruned` : ""}`
                : Object.keys(resolvedParams).length > 0
                  ? `${Object.keys(resolvedParams).length} tham số`
                  : undefined;

            intermediateNodes.push({
              id: hpoId,
              originalKey: "train",
              modelName,
              name: hpoTitle,
              kind: "hpo_tuning",
              status: effectiveStatus,
              depends_on: [subId],
              started_at: detail.started_at ?? raw.started_at,
              finished_at: detail.finished_at ?? raw.finished_at,
              error: detail.error || null,
              params: resolvedParams,
              output: rawOutputForInspector,
              result: resultFormatted,
              subtitle:
                trialStats.bestTrial !== null
                  ? `Best trial #${trialStats.bestTrial}`
                  : modelName,
              metricBadge: hpoBadge ?? metricBadge,
              branch: `Nhánh ${modelName} · HPO`,
              isBestModel: bestModelName === modelName,
              trials: detail.trials ?? null,
              bestTrial: trialStats.bestTrial,
              holdoutScores: resolvedHoldout,
              nTrials: trialStats.nTrials,
              nPruned: trialStats.nPruned,
            });
          } else {
            trainTerminalBranchIds.push(subId);
          }
        }
        continue;
      }
    }

    // Normal pipeline stage node
    const resultObj: Record<string, string | number | boolean> = {};
    if (raw.output && typeof raw.output === "object") {
      Object.entries(raw.output).forEach(([k, v]) => {
        if (v !== null && v !== undefined && typeof v !== "object") {
          resultObj[k] = typeof v === "number" ? Number(v.toFixed(4)) : String(v);
        }
      });
    }

    let depends: string[] = [...nodeDependsOn];
    const dashedDepends: string[] = [];

    if (key === "model_selection" && prepSubNodeIds.length > 0) {
      depends = prepSubNodeIds;
    }

    if (key === "select_best") {
      if ((mode === "expanded" || mode === "detailed") && trainTerminalBranchIds.length > 0) {
        depends = trainTerminalBranchIds;
      }
      if (hasHoldoutPath) {
        dashedDepends.push("split_holdout_data");
      }
    }

    let stageMetricBadge: string | undefined;
    if (key === "read_dataset") {
      if (raw.output?.n_rows != null && raw.output?.n_columns != null) {
        stageMetricBadge = `${formatPipelineValue(raw.output.n_rows)} × ${raw.output.n_columns} cột`;
      }
    } else if (key === "split_holdout_data") {
      if (splitSkipped) {
        stageMetricBadge = "Bỏ qua (≤ 10k dòng)";
      } else if (raw.output?.train_rows != null && raw.output?.holdout_rows != null) {
        stageMetricBadge = `${formatPipelineValue(raw.output.train_rows)} / ${formatPipelineValue(raw.output.holdout_rows)}`;
      }
    } else if (key === "model_selection") {
      const mCount = extractCandidateModelNames(pipeline).length;
      if (mCount > 0) stageMetricBadge = `${mCount} mô hình`;
    } else if (key === "select_best" && raw.output?.best_model) {
      stageMetricBadge = `Best: ${raw.output.best_model}`;
    } else if (key === "train") {
      const mCount = Object.keys(normalizeModelsRecord(raw.output?.models ?? raw.models)).length;
      if (mCount > 0) stageMetricBadge = `${mCount} mô hình`;
    }

    intermediateNodes.push({
      id: key,
      originalKey: key,
      name: nodeName,
      kind: nodeKind,
      status: normalizeNodeStatus(raw.status),
      depends_on: depends,
      dashed_depends_on: dashedDepends.length > 0 ? dashedDepends : undefined,
      started_at: raw.started_at,
      finished_at: raw.finished_at,
      error: raw.error,
      params: raw.params || {},
      output: raw.output || {},
      result: resultObj,
      subtitle: getKindBadgeLabel(nodeKind),
      metricBadge: stageMetricBadge,
      modelsList: key === "train" ? normalizeModelsRecord(raw.output?.models ?? raw.models) : undefined,
      holdoutScores: key === "select_best" ? resolvedHoldoutForBest : null,
    });
  }

  // Topological Layering based on depends_on
  const nodeMap = new Map<string, InternalNode>(intermediateNodes.map((n) => [n.id, n]));
  const rankMap = new Map<string, number>();

  const computeRank = (nodeId: string, visited = new Set<string>()): number => {
    if (rankMap.has(nodeId)) return rankMap.get(nodeId)!;
    if (visited.has(nodeId)) return 0;
    visited.add(nodeId);

    const node = nodeMap.get(nodeId);
    if (!node || !node.depends_on || node.depends_on.length === 0) {
      rankMap.set(nodeId, 0);
      return 0;
    }

    let maxParentRank = 0;
    for (const parentId of node.depends_on) {
      if (nodeMap.has(parentId)) {
        maxParentRank = Math.max(maxParentRank, computeRank(parentId, visited) + 1);
      }
    }

    rankMap.set(nodeId, maxParentRank);
    return maxParentRank;
  };

  intermediateNodes.forEach((node) => computeRank(node.id));

  const maxRank = Math.max(0, ...Array.from(rankMap.values()));
  const levels: InternalNode[][] = Array.from({ length: maxRank + 1 }, () => []);

  intermediateNodes.forEach((node) => {
    const r = rankMap.get(node.id) || 0;
    levels[r].push(node);
  });

  // Dynamic collision-free canvas sizing based on layer count and max vertical branch count
  const maxNodesInAnyLevel = Math.max(1, ...levels.map((lvl) => lvl.length));
  const colSpacing = 215;
  const xPadding = 110;
  const rowSpacing = 116;
  const yPadding = 82;

  const canvasWidth = Math.max(1120, maxRank * colSpacing + xPadding * 2);
  const canvasHeight = Math.max(480, (maxNodesInAnyLevel - 1) * rowSpacing + yPadding * 2);

  const finalNodes: ProgressMapNode[] = [];

  levels.forEach((levelNodes, levelIndex) => {
    const count = levelNodes.length;
    const px =
      maxRank === 0
        ? canvasWidth / 2
        : xPadding + (levelIndex / maxRank) * (canvasWidth - xPadding * 2);

    const totalColumnSpan = (count - 1) * rowSpacing;
    const startY = canvasHeight / 2 - totalColumnSpan / 2;

    levelNodes.forEach((node, nodeIndex) => {
      const py = count === 1 ? canvasHeight / 2 : startY + nodeIndex * rowSpacing;
      const xPct = Number(((px / canvasWidth) * 100).toFixed(2));
      const yPct = Number(((py / canvasHeight) * 100).toFixed(2));

      finalNodes.push({
        id: node.id,
        label: node.name,
        subtitle: node.subtitle,
        metricBadge: node.metricBadge,
        status: node.status,
        x: xPct,
        y: yPct,
        px: Math.round(px),
        py: Math.round(py),
        parentIds: node.depends_on.filter((p) => nodeMap.has(p)),
        dashedParentIds: node.dashed_depends_on?.filter((p) => nodeMap.has(p)),
        branch: node.branch,
        modelName: node.modelName,
        startedAt: node.started_at ? String(node.started_at) : undefined,
        finishedAt: node.finished_at ? String(node.finished_at) : undefined,
        elapsed: calculateElapsed(node.started_at, node.finished_at),
        params: node.params as Record<string, string | number | boolean>,
        result: node.result,
        log: node.error ? [`Lỗi: ${node.error}`] : undefined,
        error: node.error || undefined,
        kind: node.kind,
        isBestModel: node.isBestModel,
        rawParams: node.params,
        rawOutput: node.output,
        modelsList: node.modelsList,
        trials: node.trials,
        bestTrial: node.bestTrial,
        holdoutScores: node.holdoutScores,
        nTrials: node.nTrials,
        nPruned: node.nPruned,
      });
    });
  });

  return {
    id: pipeline.job_id || "pipeline-job",
    title: `Tiến trình Pipeline (${pipeline.mode || "AutoML"})`,
    predictionColumn: targetCol,
    rankBy: metricSort.toUpperCase(),
    scoreMode: pipeline.mode || "AutoML",
    canvasWidth,
    canvasHeight,
    nodes: finalNodes,
    rawPipeline: pipeline,
  };
};
