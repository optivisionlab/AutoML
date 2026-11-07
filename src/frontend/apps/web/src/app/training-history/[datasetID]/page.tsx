"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Award,
  BarChart3,
  Clock3,
  Eye,
  Loader2,
  RefreshCw,
  Table as TableIcon,
  Upload,
} from "lucide-react";
import { Switch } from "@/shared/components/ui/switch";
import { Label } from "@/shared/components/ui/label";
import { ChartContainer, type ChartConfig } from "@/shared/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartTooltip, ChartTooltipContent } from "@/shared/components/ui/chart";
import { ChartLegend, ChartLegendContent } from "@/shared/components/ui/chart";
import toTitleLabel from "@/shared/utils/toTitleLable";
import { Button } from "@/shared/components/ui/button";
import { Badge } from "@/shared/components/ui/badge";
import UploadPredictBox from "@/shared/components/common/UploadPredictBox";
import AppLoading from "@/shared/components/common/AppLoading";
import BackButton from "@/shared/components/common/BackButton";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import ProgressMap from "@/features/training/components/progress-map/ProgressMap";
import { ModelParamsChips } from "@/features/training/components/cards/ModelParamsChips";
import {
  ModelDetailModal,
  type ModelDetailData,
} from "@/features/training/components/modal/ModelDetailModal";
import {
  buildProgressMapFromPipeline,
  formatPipelineValue,
  GraphViewMode,
  normalizeErrorMessage,
  resolveModelSummary,
} from "@/features/training/utils/pipelineGraphBuilder";
import { useGetJobInfoQuery, useGetJobPipelineQuery } from "@/core/api/jobApi";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import { PipelineData } from "@automl/domain";
import { cn } from "@/shared/lib/utils";

const CHART_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4"];

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

const ResultPage = ({ params }: Props) => {
  const [datasetID, setDatasetID] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [openUpload, setOpenUpload] = useState(false);
  const [graphViewMode, setGraphViewMode] = useState<GraphViewMode>("expanded");
  const [selectedModalModel, setSelectedModalModel] = useState<ModelDetailData | null>(null);

  useEffect(() => {
    const unwrapParams = async () => {
      const unwrappedParams = await params;
      setDatasetID(unwrappedParams.datasetID);
    };

    unwrapParams();
  }, [params]);

  const [isPollingStopped, setIsPollingStopped] = useState(false);

  // Query API Pipeline chính thức từ backend: GET /api/v1/inference/jobs/{job_id}/pipeline
  const {
    data: livePipeline,
    isLoading: isPipelineLoading,
    isError: isPipelineError,
    error: pipelineError,
    refetch: refetchPipeline,
  } = useGetJobPipelineQuery(datasetID ?? "", {
    skip: !datasetID,
    // Polling tự động mỗi 3 giây khi job đang chạy hoặc đang chờ, tự ngắt khi kết thúc
    pollingInterval: isPollingStopped ? 0 : 3000,
  });

  // Query API Job dự phòng (nếu cần tương thích ngược với job cũ)
  const {
    data: legacyJobResult,
    isLoading: isLegacyLoading,
  } = useGetJobInfoQuery(datasetID ?? "", {
    skip: !datasetID,
  });

  const isJobFinished = useMemo(() => {
    if (!livePipeline?.status) return false;
    const s = String(livePipeline.status).toLowerCase();
    return ["succeeded", "failed", "cancelled", "done", "error"].includes(s);
  }, [livePipeline?.status]);

  useEffect(() => {
    if (isJobFinished) {
      setIsPollingStopped(true);
    }
  }, [isJobFinished]);

  // Xác định dữ liệu Pipeline hiện tại từ live API hoặc fallback sang legacy job
  const activePipeline: PipelineData | null = useMemo(() => {
    if (livePipeline) {
      return livePipeline;
    }

    if (legacyJobResult?.pipeline) {
      return legacyJobResult.pipeline;
    }

    // Nếu API job truyền thống có dữ liệu model scores, biến đổi tương thích thành pipeline
    if (legacyJobResult && legacyJobResult.orther_model_scores) {
      const bestModel = legacyJobResult.best_model || "BestModel";
      const metricSort = legacyJobResult.config?.metric_sort || "accuracy";

      const modelsRecord: Record<string, any> = {};
      legacyJobResult.orther_model_scores.forEach((m) => {
        if (!m.model_name) return;
        modelsRecord[m.model_name] = {
          status: "succeeded",
          error: null,
          best_params: m.model_name === bestModel ? legacyJobResult.best_params : null,
          scores: m.scores || {},
        };
      });

      return {
        job_id: legacyJobResult.job_id || datasetID,
        version: "2.0.0",
        mode: legacyJobResult.config?.choose || "automl",
        source: "legacy",
        status:
          legacyJobResult.status === 1
            ? "succeeded"
            : legacyJobResult.status === 0
              ? "running"
              : "failed",
        read_dataset: {
          name: "Read dataset",
          kind: "data_loading",
          depends_on: [],
          status: "succeeded",
          params: { id_data: legacyJobResult.data?.name || datasetID, format: "csv" },
          output: { data_url: "loaded" },
        },
        split_holdout_data: {
          name: "Split holdout data",
          kind: "data_splitting",
          depends_on: ["read_dataset"],
          status: "skipped",
          params: {},
          output: { train_rows: 0, holdout_rows: 0 },
        },
        preprocessing: {
          name: "Preprocessing",
          kind: "preprocessing",
          depends_on: ["read_dataset"],
          status: "succeeded",
          params: {
            list_feature: legacyJobResult.config?.list_feature || [],
            target: legacyJobResult.config?.target || null,
          },
          output: {},
        },
        model_selection: {
          name: "Model selection",
          kind: "model_selection",
          depends_on: ["preprocessing"],
          status: "succeeded",
          params: {
            problem_type: legacyJobResult.config?.problem_type || "regression",
            model_names: legacyJobResult.orther_model_scores
              .map((m) => m.model_name)
              .filter((name): name is string => Boolean(name)),
            metric_sort: metricSort,
            metrics: { [metricSort]: "maximize" },
          },
          output: {},
        },
        train: {
          name: "Train models",
          kind: "model_training",
          depends_on: ["model_selection"],
          status: "succeeded",
          params: {},
          output: {
            models: modelsRecord,
          },
        },
        select_best: {
          name: "Select best model",
          kind: "model_selection",
          depends_on: ["train"],
          status: "succeeded",
          params: { dependency_policy: "all_terminal" },
          output: {
            best_model: bestModel,
            score_source: "cv",
          },
        },
        save_result: {
          name: "Save result",
          kind: "result_storage",
          depends_on: ["select_best"],
          status: "succeeded",
          params: {},
          output: {},
        },
      };
    }

    return null;
  }, [livePipeline, legacyJobResult, datasetID]);

  // Xây dựng DAG pipeline trực tiếp từ activePipeline (dựa vào depends_on)
  const progressMapPipeline = useMemo(() => {
    if (!activePipeline) return null;
    return buildProgressMapFromPipeline(activePipeline, { mode: graphViewMode });
  }, [activePipeline, graphViewMode]);

  // Trích xuất thông tin chung về Pipeline
  const bestModelName =
    activePipeline?.select_best?.output?.best_model ||
    legacyJobResult?.best_model ||
    null;

  const scoreSource = activePipeline?.select_best?.output?.score_source || "cv";

  const metricSort =
    activePipeline?.model_selection?.params?.metric_sort ||
    legacyJobResult?.config?.metric_sort ||
    "r2";

  const targetColumn =
    activePipeline?.preprocessing?.params?.target ||
    legacyJobResult?.config?.target ||
    null;

  const featureList =
    activePipeline?.preprocessing?.params?.list_feature ||
    legacyJobResult?.config?.list_feature ||
    [];

  const problemType =
    activePipeline?.model_selection?.params?.problem_type ||
    legacyJobResult?.config?.problem_type ||
    "regression";

  // Lấy danh sách metrics được cấu hình
  const metricsConfig: Record<string, string> = useMemo(() => {
    if (activePipeline?.model_selection?.params?.metrics) {
      return activePipeline.model_selection.params.metrics;
    }
    if (problemType === "regression") {
      return { r2: "maximize", mse: "minimize", mae: "minimize", mape: "minimize" };
    }
    return { accuracy: "maximize", f1: "maximize", precision: "maximize", recall: "maximize" };
  }, [activePipeline?.model_selection?.params?.metrics, problemType]);

  // Điểm số tốt nhất
  const bestScoreVal = useMemo(() => {
    if (!bestModelName || !activePipeline) return legacyJobResult?.best_score ?? null;
    const modelDetail = activePipeline.train?.output?.models?.[bestModelName];
    if (modelDetail) {
      const { scores } = resolveModelSummary(modelDetail, scoreSource);
      if (scores && scores[metricSort] !== undefined && scores[metricSort] !== null) {
        return scores[metricSort];
      }
    }
    return legacyJobResult?.best_score ?? null;
  }, [bestModelName, activePipeline, scoreSource, metricSort, legacyJobResult?.best_score]);

  // Trích xuất danh sách mô hình từ pipeline.train.output.models
  const leaderboardModels = useMemo(() => {
    if (!activePipeline) return [];
    const modelsObj = activePipeline.train?.output?.models;
    if (modelsObj && Object.keys(modelsObj).length > 0) {
      const list = Object.entries(modelsObj).map(([modelName, info]) => {
        const { bestParams, scores, trials, bestTrialIdx } = resolveModelSummary(
          info,
          scoreSource,
        );

        return {
          model_name: modelName,
          status: info.status,
          error: normalizeErrorMessage(info.error),
          scores: scores || {},
          best_params: bestParams,
          trials: trials,
          best_trial: bestTrialIdx,
          holdout_scores: info.holdout_scores || null,
        };
      });

      // Sắp xếp theo metricSort
      const direction = metricsConfig[metricSort] === "minimize" ? "min" : "max";
      return list.sort((a, b) => {
        const scoreA = a.scores[metricSort];
        const scoreB = b.scores[metricSort];
        if (scoreA === null || scoreA === undefined) return 1;
        if (scoreB === null || scoreB === undefined) return -1;
        return direction === "min" ? scoreA - scoreB : scoreB - scoreA;
      });
    }

    // Fallback sang orther_model_scores nếu có
    if (legacyJobResult?.orther_model_scores) {
      return [...legacyJobResult.orther_model_scores].map((item) => ({
        model_name: item.model_name || item.model || "Unknown",
        status: "succeeded",
        error: null,
        scores: item.scores || (item.score !== undefined ? { [metricSort]: item.score } : {}),
        best_params: item.best_params || null,
        trials: [],
        best_trial: null,
        holdout_scores: null,
      })).sort((a, b) => {
        const scoreA = a.scores?.[metricSort] ?? 0;
        const scoreB = b.scores?.[metricSort] ?? 0;
        return scoreB - scoreA;
      });
    }

    return [];
  }, [
    activePipeline,
    scoreSource,
    legacyJobResult?.orther_model_scores,
    metricSort,
    metricsConfig,
  ]);

  // Cấu hình Recharts BarChart
  const chartConfig = useMemo(() => {
    const keys = Object.keys(metricsConfig);
    return keys.reduce((cfg: ChartConfig, mKey, index) => {
      cfg[mKey] = {
        label: toTitleLabel(mKey),
        color: CHART_COLORS[index % CHART_COLORS.length],
      };
      return cfg;
    }, {}) as ChartConfig;
  }, [metricsConfig]);

  const chartData = useMemo(() => {
    if (leaderboardModels.length === 0) return [];
    return leaderboardModels.map((m) => {
      const row: Record<string, string | number> = { name: m.model_name };
      Object.keys(metricsConfig).forEach((mKey) => {
        const val = m.scores[mKey];
        if (typeof val === "number") {
          row[mKey] = parseFloat(val.toFixed(4));
        }
      });
      return row;
    });
  }, [leaderboardModels, metricsConfig]);

  const isInitialLoading = !activePipeline && (isPipelineLoading || isLegacyLoading);

  const isJobCompleted =
    activePipeline?.status === "succeeded" || activePipeline?.status === "done";

  const isTrainingInProgress =
    activePipeline?.status === "running" ||
    activePipeline?.status === "queued" ||
    activePipeline?.train?.status === "running" ||
    activePipeline?.train?.status === "queued";

  const currentRunningStep = useMemo(() => {
    if (!activePipeline) return null;
    const stepDefs = [
      { key: "read_dataset", label: "Đang đọc tập dữ liệu (Read Dataset)" },
      { key: "split_holdout_data", label: "Đang phân chia tập kiểm thử (Holdout Split)" },
      { key: "preprocessing", label: "Đang tiền xử lý đặc trưng (Preprocessing)" },
      { key: "model_selection", label: "Đang thiết lập mô hình ứng viên (Model Selection)" },
      { key: "train", label: "Đang huấn luyện & tối ưu siêu tham số (Model Training)" },
      { key: "select_best", label: "Đang đánh giá chọn mô hình tốt nhất (Select Best)" },
      { key: "save_result", label: "Đang lưu trữ kết quả (Save Result)" },
    ];
    const running = stepDefs.find((s) => (activePipeline as any)[s.key]?.status === "running");
    if (running) return running;
    const queued = stepDefs.find((s) => (activePipeline as any)[s.key]?.status === "queued");
    if (queued) return queued;
    return null;
  }, [activePipeline]);

  return (
    <div className="min-h-[calc(100vh-96px)] space-y-6 rounded-[24px] bg-[var(--automl-workspace-bg)] p-4 text-[var(--automl-data-text)] sm:p-6">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <BreadcrumbNav
          items={[
            { label: "Lịch sử huấn luyện", href: "/training-history" },
            { label: activePipeline?.job_id || datasetID || "Chi tiết tiến trình pipeline" },
          ]}
        />
        <div className="flex items-center gap-2">
          {/* Status Badge */}
          {activePipeline && (
            <Badge
              variant="outline"
              className={cn(
                "rounded-full px-3 py-1 text-xs font-bold transition-all",
                activePipeline.status === "succeeded" || activePipeline.status === "done"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : activePipeline.status === "running"
                    ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-600 dark:text-cyan-400"
                    : activePipeline.status === "cancelled"
                      ? "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                      : activePipeline.status === "failed" || activePipeline.status === "error"
                        ? "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400"
                        : "border-slate-300 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-400",
              )}
            >
              {activePipeline.status === "running" && (
                <Clock3 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
              )}
              {activePipeline.status === "succeeded" || activePipeline.status === "done"
                ? "Hoàn tất"
                : activePipeline.status === "running"
                  ? "Đang huấn luyện..."
                  : activePipeline.status === "queued"
                    ? "Đang chờ worker"
                    : activePipeline.status === "cancelled"
                      ? "Đã hủy"
                      : activePipeline.status === "failed" || activePipeline.status === "error"
                        ? "Thất bại"
                        : "Đang chờ"}
            </Badge>
          )}

          {/* Refresh / Polling Button */}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-9 rounded-xl px-3 text-xs font-bold border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)]"
            onClick={() => refetchPipeline()}
            title="Làm mới dữ liệu từ server"
          >
            <RefreshCw
              className={cn(
                "h-3.5 w-3.5 mr-1.5",
                isPipelineLoading && "animate-spin text-automl-blue",
              )}
            />
            {isJobFinished ? "Làm mới" : "Đang cập nhật..."}
          </Button>

          <BackButton fallbackHref="/training-history" />
        </div>
      </div>

      {isInitialLoading && (
        <AppLoading variant="overlay" label="Đang tải dữ liệu tiến trình huấn luyện..." />
      )}

      {/* Thông báo lỗi khi không load được pipeline */}
      {isPipelineError && !activePipeline && (
        <div className="rounded-[22px] border border-red-500/30 bg-red-500/10 p-8 text-center text-[var(--automl-data-text)] shadow-xs">
          <AlertCircle className="mx-auto h-10 w-10 text-red-500" />
          <h2 className="mt-3 text-lg font-bold">Không thể tải dữ liệu tiến trình huấn luyện</h2>
          <p className="mt-1 text-xs text-[var(--automl-data-muted)] max-w-md mx-auto">
            {normalizeErrorMessage(pipelineError) ||
              "Không tìm thấy job hoặc không thể kết nối đến máy chủ API. Vui lòng kiểm tra lại ID."}
          </p>
          <Button
            onClick={() => refetchPipeline()}
            className="mt-4 rounded-xl bg-automl-blue text-white"
          >
            Thử lại
          </Button>
        </div>
      )}

      {/* Hiển thị lỗi gốc của Job nếu có */}
      {activePipeline?.error && (
        <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-xs text-red-600 dark:text-red-400 shadow-xs">
          <div className="flex items-center gap-2 font-bold text-red-700 dark:text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0" />
            <span>Lỗi trong quá trình thực thi pipeline:</span>
          </div>
          <p className="mt-1 font-mono text-xs leading-relaxed">
            {normalizeErrorMessage(activePipeline.error)}
          </p>
        </div>
      )}

      {activePipeline && (
        <>
          {/* Hero Result Banner */}
          <section className="rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 shadow-sm">
            <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-black uppercase tracking-wider text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
                    Pipeline AutoML · Job {activePipeline.job_id || datasetID || "—"}
                  </span>
                  <span className="rounded-full border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-2 py-0.5 text-[10px] font-bold text-[var(--automl-data-muted)]">
                    v{activePipeline.version || "2.0.0"}
                  </span>
                  {activePipeline.source && (
                    <span className="rounded-full border border-slate-300 dark:border-slate-700 bg-[var(--automl-table-header-bg)] px-2 py-0.5 text-[10px] font-medium text-[var(--automl-data-muted)]">
                      {activePipeline.source === "tracked" ? "Đo thời gian thực" : "Dữ liệu cũ"}
                    </span>
                  )}
                </div>

                <div className="mt-2 flex items-center gap-3">
                  <h1 className="truncate text-2xl font-extrabold tracking-tight text-[var(--automl-data-text)] sm:text-3xl">
                    {bestModelName || "—"}
                  </h1>
                  {bestModelName && (
                    <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30">
                      <Award className="mr-1 h-3.5 w-3.5" /> Mô hình tối ưu
                    </Badge>
                  )}
                </div>

                <p className="mt-1 text-xs font-semibold text-[var(--automl-data-muted)]">
                  Cột mục tiêu:{" "}
                  <span className="font-bold text-[var(--automl-data-text)]">
                    {formatPipelineValue(targetColumn)}
                  </span>{" "}
                  · Đặc trưng:{" "}
                  <span className="font-bold text-[var(--automl-data-text)]">
                    {featureList.length > 0 ? featureList.join(", ") : "—"}
                  </span>
                </p>
              </div>

              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 xl:w-[580px]">
                <MetricCard
                  label={`Điểm (${metricSort.toUpperCase()})`}
                  value={formatPipelineValue(bestScoreVal)}
                  detail={
                    metricsConfig[metricSort] === "minimize"
                      ? "Mục tiêu: Tối thiểu"
                      : "Mục tiêu: Tối đa"
                  }
                />
                <MetricCard
                  label="Chỉ số chính"
                  value={toTitleLabel(metricSort)}
                  detail="Tối ưu hóa"
                />
                <MetricCard
                  label="Bài toán"
                  value={toTitleLabel(problemType)}
                  detail="Tự động hóa"
                />
                <MetricCard
                  label="Trạng thái"
                  value={
                    activePipeline.status === "succeeded" || activePipeline.status === "done"
                      ? "Hoàn tất"
                      : activePipeline.status === "running"
                        ? "Đang chạy"
                        : activePipeline.status === "queued"
                          ? "Đang chờ"
                          : activePipeline.status === "cancelled"
                            ? "Đã hủy"
                            : activePipeline.status === "failed" || activePipeline.status === "error"
                              ? "Lỗi"
                              : "Đang chờ"
                  }
                  detail={`Chế độ: ${activePipeline.mode || "AutoML"}`}
                  tone={
                    activePipeline.status === "succeeded" || activePipeline.status === "done"
                      ? "text-emerald-600 dark:text-emerald-400"
                      : activePipeline.status === "running"
                        ? "text-cyan-600 dark:text-cyan-400"
                        : activePipeline.status === "cancelled"
                          ? "text-amber-600 dark:text-amber-400"
                          : activePipeline.status === "failed" || activePipeline.status === "error"
                            ? "text-red-600 dark:text-red-400"
                            : "text-slate-500"
                  }
                />
              </div>

              <Button
                disabled={!isJobCompleted || !bestModelName}
                className={cn(
                  "h-11 shrink-0 rounded-xl px-5 font-bold shadow-sm transition-all",
                  openUpload
                    ? "bg-slate-700 text-white hover:bg-slate-800"
                    : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-emerald-600/20",
                  (!isJobCompleted || !bestModelName) &&
                    "cursor-not-allowed opacity-50 hover:bg-emerald-600",
                )}
                onClick={() => isJobCompleted && bestModelName && setOpenUpload((v) => !v)}
                title={
                  !isJobCompleted
                    ? "Chờ quá trình huấn luyện hoàn tất để kiểm thử"
                    : undefined
                }
              >
                <Upload className="mr-2 h-4 w-4" />
                {openUpload ? "Đóng kiểm thử" : "Upload kiểm thử"}
              </Button>
            </div>
          </section>

          {/* Progress Map Visualizer (DAG) */}
          {progressMapPipeline && (
            <section className="space-y-2">
              <ProgressMap
                pipeline={progressMapPipeline}
                viewMode={graphViewMode}
                onViewModeChange={setGraphViewMode}
              />
            </section>
          )}

          {/* Upload Predict Modal/Box */}
          {openUpload && (
            <section className="rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 shadow-sm animate-in fade-in slide-in-from-top-3">
              <div className="mb-4 flex items-center justify-between border-b border-[var(--automl-data-card-border)] pb-3">
                <div>
                  <h2 className="text-base font-extrabold text-[var(--automl-data-text)]">
                    Dự đoán thử nghiệm với mô hình tốt nhất
                  </h2>
                  <p className="text-xs text-[var(--automl-data-muted)]">
                    Tải lên tập dữ liệu mẫu để chạy inference trực tiếp với mô hình {bestModelName || "được chọn"}.
                  </p>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-8 rounded-lg"
                  onClick={() => setOpenUpload(false)}
                >
                  Đóng
                </Button>
              </div>
              <UploadPredictBox jobId={datasetID || "job-001"} />
            </section>
          )}

          {/* Leaderboard Table & Metric Comparison Chart */}
          <section className="automl-data-card">
            <div className="automl-data-toolbar">
              <div>
                <h2 className="automl-data-title">Bảng xếp hạng mô hình & Điểm số</h2>
                <p className="automl-data-subtitle">
                  So sánh toàn bộ mô hình trong pipeline huấn luyện theo các chỉ số đo lường.
                </p>
              </div>
              <div className="automl-data-actions">
                <span className="automl-data-chip">
                  Sắp xếp theo {toTitleLabel(metricSort)} ({metricsConfig[metricSort] || "maximize"})
                </span>
                {leaderboardModels.length > 0 && (
                  <div className="flex items-center gap-2 text-[var(--automl-data-muted)]">
                    <Label
                      htmlFor="toggle-chart"
                      className="flex items-center gap-1.5 text-xs font-bold cursor-pointer"
                    >
                      {showChart ? (
                        <BarChart3 className="h-4 w-4 text-automl-blue" />
                      ) : (
                        <TableIcon className="h-4 w-4" />
                      )}
                      Biểu đồ so sánh
                    </Label>
                    <Switch
                      id="toggle-chart"
                      checked={showChart}
                      onCheckedChange={setShowChart}
                    />
                  </div>
                )}
              </div>
            </div>

            <div className="automl-table-wrap pt-5">
              {leaderboardModels.length === 0 ? (
                <div className="flex flex-col items-center justify-center p-12 text-center rounded-[18px] border border-dashed border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)]">
                  {isTrainingInProgress ? (
                    <>
                      <div className="relative mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-500/10 text-cyan-600 dark:text-cyan-400">
                        <Loader2 className="h-6 w-6 animate-spin" />
                      </div>
                      <h3 className="text-sm font-bold text-[var(--automl-data-text)] mb-1">
                        {currentRunningStep
                          ? currentRunningStep.label
                          : "Đang trong tiến trình huấn luyện"}
                      </h3>
                      <p className="max-w-md text-xs text-[var(--automl-data-muted)] leading-relaxed">
                        {activePipeline?.train?.status === "running"
                          ? "Các mô hình đang được huấn luyện và tìm kiếm siêu tham số tối ưu (Hyperparameter Tuning). Bảng xếp hạng và điểm số sẽ hiển thị tự động ngay khi bước Huấn luyện hoàn thành."
                          : "Job đang ở các bước chuẩn bị dữ liệu ban đầu. Bảng xếp hạng và các chỉ số đo lường (R², MSE, MAE...) sẽ tự động cập nhật ngay sau khi bước Huấn luyện (Train) kết thúc."}
                      </p>
                    </>
                  ) : activePipeline?.status === "failed" || activePipeline?.status === "cancelled" ? (
                    <>
                      <div className="relative mb-3 flex h-12 w-12 items-center justify-center rounded-2xl bg-red-500/10 text-red-600 dark:text-red-400">
                        <AlertCircle className="h-6 w-6" />
                      </div>
                      <h3 className="text-sm font-bold text-red-600 dark:text-red-400 mb-1">
                        Không có kết quả mô hình
                      </h3>
                      <p className="max-w-md text-xs text-[var(--automl-data-muted)] leading-relaxed">
                        Quá trình huấn luyện đã kết thúc hoặc gặp sự cố trước khi bước huấn luyện hoàn tất. Vui lòng xem thông báo lỗi chi tiết ở tiến trình pipeline phía trên.
                      </p>
                    </>
                  ) : (
                    <p className="text-xs text-[var(--automl-data-muted)]">
                      Chưa có dữ liệu mô hình để xếp hạng.
                    </p>
                  )}
                </div>
              ) : showChart ? (
                <div className="rounded-[16px] border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-5">
                  <ChartContainer config={chartConfig} className="max-h-[420px] w-full">
                    <BarChart accessibilityLayer data={chartData}>
                      <CartesianGrid vertical={false} stroke="var(--automl-data-card-border)" />
                      <XAxis
                        dataKey="name"
                        tickLine={false}
                        tickMargin={10}
                        axisLine={false}
                        tickFormatter={(value) => value.replace(/([a-z])([A-Z])/g, "$1 $2")}
                      />
                      <YAxis tickLine={false} axisLine={false} />
                      <ChartTooltip content={<ChartTooltipContent />} />
                      <ChartLegend content={<ChartLegendContent />} />
                      {Object.entries(chartConfig).map(([key]) => (
                        <Bar key={key} dataKey={key} fill={`var(--color-${key})`} radius={4} />
                      ))}
                    </BarChart>
                  </ChartContainer>
                </div>
              ) : (
                <Table className="automl-data-table">
                  <TableHeader>
                    <TableRow>
                      <TableHead className="w-16">Hạng</TableHead>
                      <TableHead>Mô hình (Model)</TableHead>
                      <TableHead>Trạng thái</TableHead>
                      {Object.keys(metricsConfig).map((metricKey) => (
                        <TableHead key={metricKey}>
                          {toTitleLabel(metricKey)}
                          <span className="ml-1 text-[10px] font-normal text-[var(--automl-data-muted)]">
                            ({metricsConfig[metricKey] === "minimize" ? "min" : "max"})
                          </span>
                        </TableHead>
                      ))}
                      <TableHead>Tham số tối ưu (Best Params)</TableHead>
                      <TableHead className="text-center w-28">Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {leaderboardModels.map((model: any, index: number) => {
                      const isBest = model.model_name === bestModelName || index === 0;
                      return (
                        <TableRow
                          key={`${model.model_name}-${index}`}
                          className={cn(
                            isBest &&
                              "automl-row-highlight bg-blue-50/60 dark:bg-blue-950/20 font-bold",
                          )}
                        >
                          <TableCell className="font-extrabold">
                            {isBest ? (
                              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500/20 text-xs font-black text-amber-600 dark:text-amber-400">
                                🥇
                              </span>
                            ) : (
                              index + 1
                            )}
                          </TableCell>
                          <TableCell className="font-extrabold text-[var(--automl-data-text)]">
                            <div className="flex items-center gap-2">
                              <span>{model.model_name}</span>
                              {isBest && (
                                <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 text-[10px] py-0 px-1.5">
                                  Best
                                </Badge>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            {model.status === "succeeded" || model.status === "done" ? (
                              <Badge
                                variant="outline"
                                className="automl-status-success rounded-full text-[11px] font-bold"
                              >
                                Hoàn tất
                              </Badge>
                            ) : model.status === "running" ? (
                              <Badge
                                variant="secondary"
                                className="automl-status-warning rounded-full text-[11px] font-bold"
                              >
                                Đang chạy
                              </Badge>
                            ) : model.status === "failed" ? (
                              <Badge
                                variant="default"
                                className="automl-status-error rounded-full text-[11px] font-bold"
                              >
                                Lỗi
                              </Badge>
                            ) : model.status === "skipped" ? (
                              <Badge
                                variant="outline"
                                className="rounded-full text-[11px] font-bold text-slate-500"
                              >
                                Bỏ qua
                              </Badge>
                            ) : (
                              <span className="text-xs font-semibold text-[var(--automl-data-muted)]">
                                —
                              </span>
                            )}
                          </TableCell>
                          {Object.keys(metricsConfig).map((metricKey: string) => {
                            const val = model.scores?.[metricKey];
                            return (
                              <TableCell key={metricKey} className="font-mono font-bold">
                                {formatPipelineValue(val)}
                              </TableCell>
                            );
                          })}
                          <TableCell className="max-w-md">
                            <ModelParamsChips
                              params={model.best_params}
                              onViewDetails={() =>
                                setSelectedModalModel({
                                  model_name: model.model_name,
                                  status: model.status,
                                  error: model.error,
                                  scores: model.scores,
                                  best_params: model.best_params,
                                  trials: model.trials,
                                  best_trial: model.best_trial,
                                  holdout_scores: model.holdout_scores,
                                  rank: index + 1,
                                })
                              }
                            />
                          </TableCell>
                          <TableCell className="text-center">
                            <Button
                              type="button"
                              size="sm"
                              variant="outline"
                              className="h-8 rounded-xl px-2.5 text-xs font-bold border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] hover:bg-blue-50 hover:text-automl-blue dark:hover:bg-cyan-950/50 dark:hover:text-cyan-300"
                              onClick={() =>
                                setSelectedModalModel({
                                  model_name: model.model_name,
                                  status: model.status,
                                  error: model.error,
                                  scores: model.scores,
                                  best_params: model.best_params,
                                  trials: model.trials,
                                  best_trial: model.best_trial,
                                  holdout_scores: model.holdout_scores,
                                  rank: index + 1,
                                })
                              }
                            >
                              <Eye className="mr-1.5 h-3.5 w-3.5" />
                              Chi tiết
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </div>
          </section>
        </>
      )}

      {/* Modal chi tiết mô hình & tham số tối ưu */}
      <ModelDetailModal
        open={Boolean(selectedModalModel)}
        onOpenChange={(open) => !open && setSelectedModalModel(null)}
        model={selectedModalModel}
        isBestModel={selectedModalModel?.model_name === bestModelName}
        metricSort={metricSort}
        metricsConfig={metricsConfig}
        problemType={problemType}
      />
    </div>
  );
};

const MetricCard = ({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail?: string;
  tone?: string;
}) => (
  <div className="min-w-0 rounded-2xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-3.5 py-2.5">
    <p className="text-[10px] font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
      {label}
    </p>
    <p className={cn("mt-1 truncate text-base font-extrabold text-[var(--automl-data-text)]", tone)}>
      {value}
    </p>
    {detail && (
      <p className="mt-0.5 truncate text-[10px] font-semibold text-[var(--automl-data-muted)]">
        {detail}
      </p>
    )}
  </div>
);

export default ResultPage;
