import type {
  ModelScoreDetail,
  PipelineBaseNode,
  PipelineData,
  PipelineNodeStatus,
  PipelineRealtimeEvent,
} from "@automl/domain";
import {
  isJobTerminal,
  normalizeNodeStatus,
  STANDARD_V2_PIPELINE_NODES,
} from "./pipelineGraphBuilder";

const cloneData = <T,>(value: T): T => {
  if (typeof structuredClone === "function") {
    return structuredClone(value);
  }
  return JSON.parse(JSON.stringify(value));
};

const statusProgressRank = (status?: PipelineNodeStatus | string | number | null): number => {
  const normalized = normalizeNodeStatus(status);
  if (normalized === "done" || normalized === "failed" || normalized === "skipped") return 2;
  if (normalized === "running") return 1;
  return 0;
};

const createDefaultNode = (nodeKey: string): PipelineBaseNode => {
  const template = STANDARD_V2_PIPELINE_NODES[nodeKey];
  if (template) {
    return {
      name: template.name,
      kind: template.kind,
      depends_on: [...template.depends_on],
      status: "queued",
      started_at: null,
      finished_at: null,
      error: null,
      params: {},
      output: nodeKey === "train" ? { models: {} } : {},
    };
  }
  return {
    name: nodeKey.replace(/_/g, " "),
    kind: "step",
    depends_on: [],
    status: "queued",
    started_at: null,
    finished_at: null,
    error: null,
    params: {},
    output: {},
  };
};

const mergeModelDetail = (
  prev: ModelScoreDetail | undefined,
  incoming: ModelScoreDetail | undefined,
): ModelScoreDetail => {
  if (!prev) {
    return incoming ? cloneData(incoming) : { status: "queued" };
  }
  if (!incoming) {
    return cloneData(prev);
  }

  const prevRank = statusProgressRank(prev.status);
  const incomingRank = statusProgressRank(incoming.status);
  const keepIncomingStatus =
    incomingRank >= prevRank && incoming.status !== undefined && incoming.status !== null;

  return {
    ...prev,
    ...incoming,
    status: keepIncomingStatus ? incoming.status : prev.status,
    error: incoming.error !== undefined ? incoming.error : prev.error,
    trials:
      Array.isArray(incoming.trials) && incoming.trials.length > 0
        ? incoming.trials
        : prev.trials ?? incoming.trials ?? null,
    best_trial: incoming.best_trial ?? prev.best_trial ?? null,
    best_scores: incoming.best_scores ?? prev.best_scores ?? null,
    scores: incoming.scores ?? prev.scores ?? null,
    best_params: incoming.best_params ?? prev.best_params ?? null,
    holdout_scores: incoming.holdout_scores ?? prev.holdout_scores ?? null,
    n_trials: incoming.n_trials ?? prev.n_trials ?? null,
    n_pruned: incoming.n_pruned ?? prev.n_pruned ?? null,
  };
};

const mergeNodeOutput = (
  existingOutput: Record<string, unknown> | undefined,
  incomingOutput: Record<string, unknown> | null | undefined,
): Record<string, unknown> => {
  const merged: Record<string, unknown> = { ...(existingOutput ?? {}) };
  if (!incomingOutput || typeof incomingOutput !== "object") {
    return merged;
  }

  for (const [key, value] of Object.entries(incomingOutput)) {
    if (key === "models") {
      if (value === null || value === undefined) continue;
      if (typeof value === "object") {
        const currentModels =
          merged.models && typeof merged.models === "object"
            ? { ...(merged.models as Record<string, ModelScoreDetail>) }
            : {};
        for (const [modelName, modelDetail] of Object.entries(
          value as Record<string, ModelScoreDetail>,
        )) {
          currentModels[modelName] = mergeModelDetail(currentModels[modelName], modelDetail);
        }
        merged.models = currentModels;
      }
      continue;
    }

    if (value !== undefined) {
      merged[key] = value;
    }
  }

  return merged;
};

/**
 * Pure reducer that applies a single MQTT pipeline realtime event onto the current pipeline state.
 */
export function applyPipelineEvent(
  prev: PipelineData | undefined,
  ev: PipelineRealtimeEvent,
): PipelineData {
  if (ev.event === "snapshot" && ev.pipeline) {
    return mergePipelineWithSnapshot(prev, ev.pipeline) ?? cloneData(ev.pipeline);
  }

  const next: PipelineData = prev ? cloneData(prev) : { version: "2.0.0", job_id: ev.job_id };
  if (!next.job_id && ev.job_id) {
    next.job_id = ev.job_id;
  }
  if (typeof ev.seq === "number") {
    next.seq = ev.seq;
  }
  if (ev.at) {
    next.updated_at = ev.at;
  }

  if (ev.event === "node_started" || ev.event === "node_finished") {
    const existing = (next[ev.node] as PipelineBaseNode | undefined) ?? createDefaultNode(ev.node);
    const updatedNode: PipelineBaseNode = {
      ...existing,
      status: ev.status,
      ...(ev.event === "node_started"
        ? { started_at: ev.at ?? existing.started_at ?? new Date().toISOString() }
        : { finished_at: ev.at ?? existing.finished_at ?? new Date().toISOString() }),
      output:
        ev.event === "node_finished"
          ? mergeNodeOutput(existing.output, ev.output)
          : existing.output ?? {},
      ...(ev.event === "node_finished" && ev.error !== undefined ? { error: ev.error } : {}),
    };

    next[ev.node] = updatedNode;

    if (ev.event === "node_started" && !isJobTerminal(next.status)) {
      next.status = "running";
    }
    if (
      ev.event === "node_finished" &&
      ev.node === "select_best" &&
      ev.output &&
      typeof ev.output === "object"
    ) {
      next.select_best = updatedNode as PipelineData["select_best"];
    }
  }

  if (ev.event === "model_finished") {
    const trainNode =
      (next.train as
        | PipelineBaseNode<Record<string, unknown>, { models?: Record<string, ModelScoreDetail> }>
        | undefined) ??
      (createDefaultNode("train") as PipelineBaseNode<
        Record<string, unknown>,
        { models?: Record<string, ModelScoreDetail> }
      >);

    trainNode.output = trainNode.output ?? {};
    trainNode.output.models = trainNode.output.models ?? {};

    const existingModel = trainNode.output.models[ev.model_name];
    trainNode.output.models[ev.model_name] = {
      ...existingModel,
      status: ev.status,
      error: ev.error !== undefined ? ev.error : existingModel?.error ?? null,
      finished_at: ev.at ?? existingModel?.finished_at ?? new Date().toISOString(),
      best_trial: ev.best_trial !== undefined ? ev.best_trial : existingModel?.best_trial ?? null,
      best_scores:
        ev.best_scores !== undefined ? ev.best_scores : existingModel?.best_scores ?? null,
      best_params:
        ev.best_params !== undefined ? ev.best_params : existingModel?.best_params ?? null,
      holdout_scores:
        ev.holdout_scores !== undefined
          ? ev.holdout_scores
          : existingModel?.holdout_scores ?? null,
      n_trials: ev.n_trials !== undefined ? ev.n_trials : existingModel?.n_trials ?? null,
      n_pruned: ev.n_pruned !== undefined ? ev.n_pruned : existingModel?.n_pruned ?? null,
    };

    if (!isJobTerminal(trainNode.status)) {
      trainNode.status = "running";
    }
    next.train = trainNode;

    if (!isJobTerminal(next.status)) {
      next.status = "running";
    }
  }

  if (ev.event === "job_finished") {
    next.status = ev.status;
    next.finished_at = ev.at ?? next.finished_at ?? new Date().toISOString();
    if (ev.error !== undefined) {
      next.error = ev.error;
    }

    if (ev.best_model || ev.holdout_scores) {
      const selectBest =
        next.select_best ??
        (createDefaultNode("select_best") as NonNullable<PipelineData["select_best"]>);
      selectBest.output = {
        ...(selectBest.output ?? {}),
        ...(ev.best_model ? { best_model: ev.best_model } : {}),
        ...(ev.holdout_scores ? { holdout_scores: ev.holdout_scores } : {}),
      };
      next.select_best = selectBest;
    }
  }

  return next;
}

/**
 * Merge a freshly fetched API snapshot with the live in-memory pipeline state:
 * - If the API snapshot is terminal (succeeded/failed/cancelled), it is authoritative (contains full `trials` & `holdout_scores`).
 * - If non-terminal, hydrate structural metadata & params from snapshot without regressing live nodes already advanced via MQTT.
 */
export function mergePipelineWithSnapshot(
  current: PipelineData | undefined,
  snapshot: PipelineData | undefined,
): PipelineData | undefined {
  if (!snapshot) return current;
  if (!current) return cloneData(snapshot);
  if (current.job_id && snapshot.job_id && current.job_id !== snapshot.job_id) {
    return cloneData(snapshot);
  }
  if (isJobTerminal(snapshot.status)) {
    return cloneData(snapshot);
  }

  const merged: PipelineData = cloneData(snapshot);

  if (statusProgressRank(current.status) > statusProgressRank(merged.status)) {
    merged.status = current.status;
  }
  if (current.error && !merged.error) {
    merged.error = current.error;
  }
  if (
    typeof current.seq === "number" &&
    (typeof merged.seq !== "number" || current.seq > merged.seq)
  ) {
    merged.seq = current.seq;
  }

  const allNodeKeys = new Set([...Object.keys(merged), ...Object.keys(current)]);

  for (const key of allNodeKeys) {
    const snapNode = merged[key] as PipelineBaseNode | undefined;
    const liveNode = current[key] as PipelineBaseNode | undefined;

    const isSnapNode =
      snapNode &&
      typeof snapNode === "object" &&
      typeof snapNode.name === "string" &&
      Array.isArray(snapNode.depends_on);
    const isLiveNode =
      liveNode &&
      typeof liveNode === "object" &&
      typeof liveNode.name === "string" &&
      Array.isArray(liveNode.depends_on);

    if (!isSnapNode && !isLiveNode) continue;

    if (!isSnapNode && isLiveNode) {
      merged[key] = cloneData(liveNode);
      continue;
    }

    if (isSnapNode && isLiveNode) {
      const snapRank = statusProgressRank(snapNode.status);
      const liveRank = statusProgressRank(liveNode.status);

      merged[key] = {
        ...snapNode,
        status: liveRank > snapRank ? liveNode.status : snapNode.status,
        started_at: snapNode.started_at ?? liveNode.started_at ?? null,
        finished_at:
          liveRank > snapRank
            ? liveNode.finished_at ?? snapNode.finished_at ?? null
            : snapNode.finished_at ?? liveNode.finished_at ?? null,
        error:
          liveRank > snapRank
            ? liveNode.error ?? snapNode.error ?? null
            : snapNode.error ?? liveNode.error ?? null,
        params: {
          ...(liveNode.params ?? {}),
          ...(snapNode.params ?? {}),
        },
        output: mergeNodeOutput(
          liveRank >= snapRank ? snapNode.output : liveNode.output,
          liveRank >= snapRank ? liveNode.output : snapNode.output,
        ),
      };
    }
  }

  return merged;
}
