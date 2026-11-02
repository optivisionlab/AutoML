import { ModelScoreDetail, PipelineData, PipelineNodeStatus } from "@automl/domain";

/**
 * Chuyển JSON từ GET /api/v1/inference/jobs/{id}/pipeline (backend v2) sang dạng các component đang dùng:
 * - status: succeeded/queued/cancelled/skipped -> done/pending/failed
 * - error: { message } -> string
 * - mỗi model: điền best_params/scores từ trials[best_trial] (hoặc holdout_scores nếu chọn mô hình theo holdout),
 *   vẫn giữ nguyên trials/best_trial để hiển thị các nhánh tham số.
 */

const toUiStatus = (status: unknown, finishedAt?: unknown): PipelineNodeStatus => {
  switch (status) {
    case "succeeded":
      return "done";
    case "queued":
      return "pending";
    case "cancelled":
      return "failed";
    case "skipped":
      // Node bị bỏ qua sau khi đã chạy (vd. không tách holdout) coi như xong; node chưa chạy do job lỗi thì là pending
      return finishedAt ? "done" : "pending";
    default:
      return (status as PipelineNodeStatus) ?? null;
  }
};

const toErrorMessage = (error: unknown): string | null => {
  if (!error) return null;
  if (typeof error === "string") return error;
  if (typeof error === "object" && "message" in error) return String((error as { message: unknown }).message);
  return String(error);
};

const adaptModel = (model: Record<string, any>, useHoldout: boolean): ModelScoreDetail => {
  const bestTrial =
    Array.isArray(model.trials) && typeof model.best_trial === "number"
      ? model.trials[model.best_trial]
      : null;

  return {
    ...model,
    status: toUiStatus(model.status),
    error: toErrorMessage(model.error),
    best_params: model.best_params ?? bestTrial?.params ?? null,
    scores: model.scores ?? ((useHoldout && model.holdout_scores) || bestTrial?.scores || null),
  };
};

export const adaptJobPipeline = (raw: PipelineData): PipelineData => {
  const pipeline: Record<string, any> = { ...raw, status: toUiStatus(raw.status) };

  for (const [key, value] of Object.entries(raw)) {
    if (!value || typeof value !== "object" || !("depends_on" in value)) continue;
    const node = value as Record<string, any>;
    pipeline[key] = {
      ...node,
      status: toUiStatus(node.status, node.finished_at),
      error: toErrorMessage(node.error),
    };
  }

  const models: Record<string, any> | undefined = raw.train?.output?.models;
  if (models) {
    const useHoldout = raw.select_best?.output?.score_source === "holdout";
    pipeline.train.output = {
      ...pipeline.train.output,
      models: Object.fromEntries(
        Object.entries(models).map(([name, model]) => [name, adaptModel(model, useHoldout)]),
      ),
    };
  }

  return pipeline as PipelineData;
};
