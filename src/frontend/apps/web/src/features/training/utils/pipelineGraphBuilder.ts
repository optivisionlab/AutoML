import {
  ProgressMapNode,
  ProgressMapPipeline,
} from "@/features/training/constants/progressMapSample";
import { ModelScoreDetail, PipelineData, PipelineNodeStatus } from "@automl/domain";


export type GraphViewMode = "expanded" | "compact";

export const formatPipelineValue = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (Number.isInteger(value)) return value.toLocaleString("en-US");
    return value.toFixed(4);
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return "—";
    return value.map((v) => (typeof v === "object" ? formatPipelineValue(v) : String(v))).join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return "—";
    return entries.map(([k, v]) => `${k}: ${formatPipelineValue(v)}`).join(", ");
  }
  return String(value);
};


export const normalizeNodeStatus = (
  status?: PipelineNodeStatus | string | number | null,
): "done" | "running" | "pending" | "failed" => {
  if (status === "done" || status === "success" || status === "completed" || status === 1 || status === "1") {
    return "done";
  }
  if (status === "running" || status === 0 || status === "0") {
    return "running";
  }
  if (status === "failed" || status === "error" || status === -1 || status === "-1") {
    return "failed";
  }
  return "pending";
};

export const calculateElapsed = (
  startedAt?: string | number | null,
  finishedAt?: string | number | null,
): string => {
  if (!startedAt) return "—";
  const start = typeof startedAt === "number" ? startedAt * 1000 : new Date(startedAt).getTime();
  const end = finishedAt
    ? typeof finishedAt === "number"
      ? finishedAt * 1000
      : new Date(finishedAt).getTime()
    : Date.now();

  if (isNaN(start) || isNaN(end) || end < start) return "—";
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
    case "model_selection":
      return "Chọn mô hình";
    case "model_training":
      return "Huấn luyện";
    case "result_storage":
      return "Lưu kết quả";
    default:
      return kind ? kind.replace(/_/g, " ") : "Giai đoạn";
  }
};

interface BuildGraphOptions {
  mode?: GraphViewMode;
}

export const buildProgressMapFromPipeline = (
  pipeline: PipelineData,
  options: BuildGraphOptions = { mode: "expanded" },
): ProgressMapPipeline => {
  const mode = options.mode || "expanded";
  const bestModelName = pipeline.select_best?.output?.best_model;
  const targetCol =
    pipeline.preprocessing?.params?.target ||
    (pipeline as any).config?.target ||
    "target";
  const metricSort =
    pipeline.model_selection?.params?.metric_sort ||
    (pipeline as any).config?.metric_sort ||
    "r2";

  // Thu thập các node từ pipeline
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

  // Lấy danh sách tất cả các key là node hợp lệ trong pipeline
  const nodeKeys = Object.keys(pipeline).filter((k) => {
    const val = (pipeline as any)[k];
    return val && typeof val === "object" && typeof val.name === "string" && Array.isArray(val.depends_on);
  });

  // Đảm bảo thứ tự ưu tiên chuẩn nếu có
  const orderedKeys = Array.from(new Set([...standardKeys.filter((k) => nodeKeys.includes(k)), ...nodeKeys]));

  type InternalNode = {
    id: string;
    originalKey?: string;
    name: string;
    kind: string;
    status: "done" | "running" | "pending" | "failed";
    depends_on: string[];
    started_at?: string | number | null;
    finished_at?: string | number | null;
    error?: string | null;
    params?: Record<string, unknown>;
    output?: Record<string, unknown>;
    result?: Record<string, string | number | boolean>;
    subtitle?: string;
    branch?: string;
    isBestModel?: boolean;
    modelsList?: Record<string, ModelScoreDetail>;
  };

  const intermediateNodes: InternalNode[] = [];
  const modelSubNodeIds: string[] = [];

  for (const key of orderedKeys) {
    const raw = (pipeline as any)[key];
    if (!raw) continue;

    if (key === "train" && mode === "expanded") {
      const modelsMap: Record<string, ModelScoreDetail> = raw.output?.models || {};
      const modelNames =
        pipeline.model_selection?.params?.model_names || Object.keys(modelsMap);

      if (modelNames.length > 0) {
        // Tạo các parallel sub-nodes cho từng model
        for (const modelName of modelNames) {
          const detail: ModelScoreDetail = modelsMap[modelName] || {
            status: raw.status || null,
            error: null,
            best_params: null,
            scores: null,
          };

          const subId = `model_${modelName}`;
          modelSubNodeIds.push(subId);

          const resultFormatted: Record<string, string | number | boolean> = {};
          if (detail.scores) {
            Object.entries(detail.scores).forEach(([scoreKey, scoreVal]) => {
              resultFormatted[scoreKey] =
                typeof scoreVal === "number" ? Number(scoreVal.toFixed(4)) : String(scoreVal);
            });
          }

          const paramsFormatted: Record<string, unknown> = detail.best_params || {};

          intermediateNodes.push({
            id: subId,
            originalKey: "train",
            name: modelName,
            kind: "model_training",
            status: normalizeNodeStatus(detail.status || raw.status),
            depends_on: raw.depends_on || ["model_selection"],
            started_at: raw.started_at,
            finished_at: raw.finished_at,
            error: detail.error || null,
            params: paramsFormatted,
            output: detail.scores || {},
            result: resultFormatted,
            subtitle: "Model",
            branch: "Mô hình song song",
            isBestModel: bestModelName === modelName,
          });
        }
        continue;
      }
    }

    // Node thông thường
    const resultObj: Record<string, string | number | boolean> = {};
    if (raw.output && typeof raw.output === "object") {
      Object.entries(raw.output).forEach(([k, v]) => {
        if (v !== null && v !== undefined && typeof v !== "object") {
          resultObj[k] = typeof v === "number" ? Number(v.toFixed(4)) : String(v);
        }
      });
    }

    // Nếu là select_best và ở expanded mode, depends_on trỏ về các model sub nodes
    let depends = raw.depends_on || [];
    if (key === "select_best" && mode === "expanded" && modelSubNodeIds.length > 0) {
      depends = modelSubNodeIds;
    }

    intermediateNodes.push({
      id: key,
      originalKey: key,
      name: raw.name || key,
      kind: raw.kind || "step",
      status: normalizeNodeStatus(raw.status),
      depends_on: depends,
      started_at: raw.started_at,
      finished_at: raw.finished_at,
      error: raw.error,
      params: raw.params || {},
      output: raw.output || {},
      result: resultObj,
      subtitle: getKindBadgeLabel(raw.kind),
      modelsList: key === "train" ? raw.output?.models : undefined,
    });
  }

  // Thuật toán Topological Layering (Xếp tầng DAG dựa trên depends_on)
  const nodeMap = new Map<string, InternalNode>(intermediateNodes.map((n) => [n.id, n]));
  const rankMap = new Map<string, number>();

  const computeRank = (nodeId: string, visited = new Set<string>()): number => {
    if (rankMap.has(nodeId)) return rankMap.get(nodeId)!;
    if (visited.has(nodeId)) return 0; // Tránh cycle
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

  // Gom các node theo rank/level
  const maxRank = Math.max(0, ...Array.from(rankMap.values()));
  const levels: InternalNode[][] = Array.from({ length: maxRank + 1 }, () => []);

  intermediateNodes.forEach((node) => {
    const r = rankMap.get(node.id) || 0;
    levels[r].push(node);
  });

  // Tính toán tọa độ (x, y) % cho mỗi node
  const finalNodes: ProgressMapNode[] = [];

  levels.forEach((levelNodes, levelIndex) => {
    const count = levelNodes.length;
    // x phân bổ đều từ 6% đến 94%
    const x = maxRank === 0 ? 50 : 6 + (levelIndex / maxRank) * 88;

    levelNodes.forEach((node, nodeIndex) => {
      let y = 50;
      if (count > 1) {
        // Trải đều theo trục dọc quanh tâm 50%
        const ySpacing = count >= 5 ? 15 : count >= 3 ? 20 : 28;
        y = 50 + (nodeIndex - (count - 1) / 2) * ySpacing;
      }

      finalNodes.push({
        id: node.id,
        label: node.name,
        subtitle: node.subtitle,
        status: node.status,
        x: Math.round(x),
        y: Math.max(12, Math.min(88, Math.round(y))),
        parentIds: node.depends_on.filter((p) => nodeMap.has(p)),
        branch: node.branch,
        startedAt: node.started_at ? String(node.started_at) : undefined,
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
      } as any);
    });
  });

  return {
    id: pipeline.job_id || "pipeline-job",
    title: `Tiến trình Pipeline (${pipeline.mode || "AutoML"})`,
    predictionColumn: targetCol,
    rankBy: metricSort.toUpperCase(),
    scoreMode: pipeline.mode || "AutoML",
    nodes: finalNodes,
  };
};
