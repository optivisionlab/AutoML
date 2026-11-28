"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useDispatch } from "react-redux";
import {
  AlertCircle,
  AlertTriangle,
  Award,
  Ban,
  BarChart3,
  CheckCircle2,
  Clock3,
  Eye,
  FlaskConical,
  Radio,
  RefreshCw,
  Rocket,
  ShieldCheck,
  SkipForward,
  StopCircle,
  Table as TableIcon,
  Upload,
  WifiOff,
  XCircle,
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";
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
import { usePipelineRealtime } from "@/features/training/hooks/usePipelineRealtime";
import {
  buildProgressMapFromPipeline,
  formatPipelineValue,
  getMetricDirection,
  GraphViewMode,
  isJobActive,
  isJobCancelled,
  isJobCompleted,
  isJobFailed,
  isJobQueued,
  isJobRunning,
  isJobTerminal,
  normalizeNodeStatus,
  normalizePipelineFromJob,
  resolveModelBestParams,
  resolveModelHoldoutScores,
  resolveModelScores,
  resolveModelTrialStats,
  resolvePipelineHoldoutScores,
} from "@/features/training/utils/pipelineGraphBuilder";
import {
  useCancelTrainingJobMutation,
  useGetJobDetailQuery,
} from "@/core/api/jobApi";
import { baseApi, getApiErrorMessage } from "@/core/api/baseApi";
import { useToast } from "@/shared/hooks/use-toast";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
import type { ModelTrialDetail, PipelineData } from "@automl/domain";
import { cn } from "@/shared/lib/utils";

const CHART_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#8b5cf6", "#ef4444", "#06b6d4"];

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

interface LeaderboardItem {
  model_name: string;
  status: string | number | null;
  error?: string | null;
  scores: Record<string, number | null>;
  best_params: Record<string, unknown> | null;
  holdout_scores: Record<string, number | null> | null;
  trials: ModelTrialDetail[] | null;
  best_trial: number | null;
  n_trials: number | null;
  n_pruned: number | null;
}

const TrainingHistoryDetailPage = ({ params }: Props) => {
  const dispatch = useDispatch();
  const { toast } = useToast();

  const [jobId, setJobId] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [openUpload, setOpenUpload] = useState(false);
  const [confirmCancelOpen, setConfirmCancelOpen] = useState(false);
  const [graphViewMode, setGraphViewMode] = useState<GraphViewMode>("detailed");
  const [selectedModalModel, setSelectedModalModel] = useState<ModelDetailData | null>(null);
  const [enableFallbackPolling, setEnableFallbackPolling] = useState(false);

  useEffect(() => {
    const unwrapParams = async () => {
      const unwrappedParams = await params;
      setJobId(unwrappedParams.datasetID);
    };

    unwrapParams();
  }, [params]);

  // 1. Fetch real job & pipeline snapshot via GET /api/v1/inference/jobs/{id}
  //    Slow fallback polling (5s) activates ONLY when job is active & MQTT broker is unavailable
  const {
    data: jobDetail,
    isLoading,
    isFetching,
    isError,
    error,
    refetch,
  } = useGetJobDetailQuery(jobId ?? "", {
    skip: !jobId,
    pollingInterval: enableFallbackPolling ? 5000 : 0,
  });

  const [cancelTrainingJob, { isLoading: isCancelling }] = useCancelTrainingJobMutation();

  // Derive normalized initial pipeline snapshot from real API response (hydrating missing branch/model metadata from jobDetail)
  const initialPipeline: PipelineData | undefined = useMemo(() => {
    if (!jobDetail) return undefined;
    return normalizePipelineFromJob(jobDetail);
  }, [jobDetail]);

  const isApiTerminal = useMemo(() => {
    if (!jobDetail) return false;
    return isJobTerminal(jobDetail.pipeline?.status ?? jobDetail.status);
  }, [jobDetail]);

  const handleMqttReconnect = useCallback(() => {
    if (jobId) {
      refetch();
    }
  }, [jobId, refetch]);

  const handleJobFinished = useCallback(() => {
    if (jobId) {
      refetch();
      dispatch(baseApi.util.invalidateTags(["Job", { type: "Job", id: jobId }]));
    }
  }, [dispatch, jobId, refetch]);

  // 2. Subscribe MQTT topic `jobs/{job_id}/pipeline` ONLY when job is not yet finished (Section 4 Step 5)
  const {
    pipeline: realtimePipeline,
    mqttStatus,
    shouldPollFallback,
    lastSeq,
  } = usePipelineRealtime(jobId, initialPipeline, {
    enabled: Boolean(jobDetail) && !isApiTerminal,
    onReconnect: handleMqttReconnect,
    onJobFinished: handleJobFinished,
  });

  useEffect(() => {
    setEnableFallbackPolling(shouldPollFallback);
  }, [shouldPollFallback]);

  const activePipeline: PipelineData | undefined = realtimePipeline ?? initialPipeline;

  const effectiveStatus = activePipeline?.status ?? jobDetail?.status ?? null;
  const jobCompleted = isJobCompleted(effectiveStatus);
  const jobRunning = isJobRunning(effectiveStatus);
  const jobQueued = isJobQueued(effectiveStatus);
  const jobCancelled = isJobCancelled(effectiveStatus);
  const jobFailed = isJobFailed(effectiveStatus);
  const jobActive = isJobActive(effectiveStatus);
  const jobTerminal = isJobTerminal(effectiveStatus);

  // Build ProgressMap DAG directly from activePipeline (based on depends_on)
  const progressMapPipeline = useMemo(() => {
    if (!activePipeline) return undefined;
    return buildProgressMapFromPipeline(activePipeline, { mode: graphViewMode });
  }, [activePipeline, graphViewMode]);

  const bestModelName =
    activePipeline?.select_best?.output?.best_model || jobDetail?.best_model || null;

  const metricSort =
    activePipeline?.model_selection?.params?.metric_sort ||
    jobDetail?.config?.metric_sort ||
    (jobDetail?.config?.problem_type === "classification" ? "accuracy" : "r2");

  const targetColumn =
    activePipeline?.preprocessing?.params?.target || jobDetail?.config?.target || null;

  const featureList =
    activePipeline?.preprocessing?.params?.list_feature || jobDetail?.config?.list_feature || [];

  const problemType = useMemo(() => {
    const explicit =
      activePipeline?.model_selection?.params?.problem_type ||
      jobDetail?.config?.problem_type;
    if (explicit) return explicit;
    const metricKeys = [
      metricSort,
      ...Object.keys(activePipeline?.model_selection?.params?.metrics || {}),
    ].map((k) => k.toLowerCase());
    if (
      metricKeys.some((k) =>
        ["accuracy", "balanced_accuracy", "f1", "f1_macro", "f1_weighted", "precision", "recall", "roc_auc"].includes(k),
      )
    ) {
      return "classification";
    }
    return "regression";
  }, [activePipeline?.model_selection?.params?.problem_type, activePipeline?.model_selection?.params?.metrics, jobDetail?.config?.problem_type, metricSort]);

  const metricsConfig: Record<string, string> = useMemo(() => {
    if (
      activePipeline?.model_selection?.params?.metrics &&
      Object.keys(activePipeline.model_selection.params.metrics).length > 0
    ) {
      return activePipeline.model_selection.params.metrics;
    }
    if (problemType === "classification") {
      return { accuracy: "maximize", f1: "maximize", precision: "maximize", recall: "maximize" };
    }
    return { r2: "maximize", mse: "minimize", mae: "minimize", mape: "minimize" };
  }, [activePipeline?.model_selection?.params?.metrics, problemType]);

  // Holdout scores (v2.0.0)
  const pipelineHoldoutScores = useMemo(
    () => resolvePipelineHoldoutScores(activePipeline, jobDetail),
    [activePipeline, jobDetail],
  );

  // Best CV score using v2.0.0 resolver (trials[best_trial].scores -> best_scores -> scores -> jobDetail.best_score)
  const bestScoreVal = useMemo(() => {
    if (bestModelName) {
      const modelDetail = activePipeline?.train?.output?.models?.[bestModelName];
      const resolvedScores = resolveModelScores(modelDetail);
      if (resolvedScores[metricSort] !== undefined && resolvedScores[metricSort] !== null) {
        return resolvedScores[metricSort];
      }
      const selectBestScores = activePipeline?.select_best?.output?.best_scores;
      if (selectBestScores && selectBestScores[metricSort] !== undefined && selectBestScores[metricSort] !== null) {
        return selectBestScores[metricSort];
      }
    }
    return jobDetail?.best_score ?? null;
  }, [bestModelName, activePipeline, metricSort, jobDetail?.best_score]);

  // Leaderboard models supporting v2.0.0 (trials[best_trial], best_scores, holdout_scores) & legacy orther_model_scores
  const leaderboardModels: LeaderboardItem[] = useMemo(() => {
    const modelsObj = activePipeline?.train?.output?.models;
    const modelNamesFromSelection = Array.isArray(
      activePipeline?.model_selection?.params?.model_names,
    )
      ? activePipeline.model_selection.params.model_names
      : [];

    if ((modelsObj && Object.keys(modelsObj).length > 0) || modelNamesFromSelection.length > 0) {
      const allModelNames = Array.from(
        new Set([...modelNamesFromSelection, ...Object.keys(modelsObj || {})]),
      );

      const list: LeaderboardItem[] = allModelNames.map((modelName) => {
        const info = modelsObj?.[modelName];
        const scores = resolveModelScores(info);
        const bestParams = resolveModelBestParams(info);
        const holdoutScores = resolveModelHoldoutScores(info);
        const stats = resolveModelTrialStats(info);

        return {
          model_name: modelName,
          status: info?.status ?? activePipeline?.train?.status ?? null,
          error: info?.error ?? null,
          scores,
          best_params: bestParams,
          holdout_scores: holdoutScores,
          trials: info?.trials ?? null,
          best_trial: stats.bestTrial,
          n_trials: stats.nTrials,
          n_pruned: stats.nPruned,
        };
      });

      const direction = getMetricDirection(metricSort, metricsConfig);
      return list.sort((a, b) => {
        const scoreA = a.scores[metricSort];
        const scoreB = b.scores[metricSort];
        if (scoreA === null || scoreA === undefined) return 1;
        if (scoreB === null || scoreB === undefined) return -1;
        return direction === "minimize" ? scoreA - scoreB : scoreB - scoreA;
      });
    }

    if (Array.isArray(jobDetail?.orther_model_scores) && jobDetail.orther_model_scores.length > 0) {
      const direction = getMetricDirection(metricSort, metricsConfig);
      return jobDetail.orther_model_scores
        .map((m) => ({
          model_name: m.model_name || m.model || "Unknown",
          status: jobCompleted ? "succeeded" : effectiveStatus,
          error: null,
          scores: m.scores || (typeof m.score === "number" ? { [metricSort]: m.score } : {}),
          best_params: m.model_name === jobDetail.best_model ? jobDetail.best_params ?? null : null,
          holdout_scores: null,
          trials: null,
          best_trial: null,
          n_trials: null,
          n_pruned: null,
        }))
        .sort((a, b) => {
          const scoreA = a.scores[metricSort];
          const scoreB = b.scores[metricSort];
          if (scoreA === null || scoreA === undefined) return 1;
          if (scoreB === null || scoreB === undefined) return -1;
          return direction === "minimize" ? scoreA - scoreB : scoreB - scoreA;
        });
    }

    return [];
  }, [activePipeline, jobDetail, metricSort, metricsConfig, jobCompleted, effectiveStatus]);

  // Recharts BarChart config
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
<<<<<<< HEAD
    return leaderboardModels.map((m) => {
      const row: Record<string, string | number> = { name: m.model_name };
      Object.keys(metricsConfig).forEach((mKey) => {
        const val = m.scores[mKey] ?? (m.scores as any)?.[`${mKey}_macro`];
        if (typeof val === "number") {
          row[mKey] = parseFloat(val.toFixed(4));
        }
=======
    return leaderboardModels
      .filter((m) => Object.keys(m.scores).length > 0)
      .map((m) => {
        const row: Record<string, string | number> = { name: m.model_name };
        Object.keys(metricsConfig).forEach((mKey) => {
          const val = m.scores[mKey] ?? (m.scores as Record<string, number | null>)?.[`${mKey}_macro`];
          if (typeof val === "number" && Number.isFinite(val)) {
            row[mKey] = parseFloat(val.toFixed(4));
          }
        });
        return row;
>>>>>>> 74d7c7dad45c7c2b084c2a84f048936d3ec164fe
      });
  }, [leaderboardModels, metricsConfig]);

  const handleCancelJob = async () => {
    if (!jobId) return;
    try {
      await cancelTrainingJob(jobId).unwrap();
      toast({
        title: "Đã gửi yêu cầu hủy huấn luyện",
        description: "Tác vụ đang dừng lại và sẽ cập nhật trạng thái ngay.",
      });
      refetch();
    } catch (err) {
      toast({
        title: "Không thể hủy tác vụ",
        description: getApiErrorMessage(err, "Vui lòng thử lại sau."),
        variant: "destructive",
      });
    } finally {
      setConfirmCancelOpen(false);
    }
  };

  const realtimeBadge = useMemo(() => {
    if (jobTerminal) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-bold text-emerald-700 dark:text-emerald-300">
          <CheckCircle2 className="h-3 w-3" />
          Snapshot cuối (API)
        </span>
      );
    }
    if (mqttStatus === "connected") {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-blue-500/30 bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-bold text-blue-700 dark:text-cyan-300">
          <Radio className="h-3 w-3 animate-pulse" />
          Realtime MQTT{lastSeq > 0 ? ` · seq #${lastSeq}` : ""}
        </span>
      );
    }
    if (mqttStatus === "connecting" || mqttStatus === "reconnecting") {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-bold text-amber-700 dark:text-amber-300">
          <Clock3 className="h-3 w-3 animate-spin" />
          Đang kết nối MQTT...
        </span>
      );
    }
    if (enableFallbackPolling) {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-bold text-amber-700 dark:text-amber-300">
          <WifiOff className="h-3 w-3" />
          Polling dự phòng (5s)
        </span>
      );
    }
    return null;
  }, [jobTerminal, mqttStatus, lastSeq, enableFallbackPolling]);

  const jobErrorMessage = activePipeline?.error || jobDetail?.error || (jobFailed || jobCancelled ? jobDetail?.infor : null);
  const datasetFromUrl = activePipeline?.read_dataset?.output?.data_url
    ? String(activePipeline.read_dataset.output.data_url).split("/").pop() || null
    : null;
  const datasetTitle =
    jobDetail?.data?.name ||
    datasetFromUrl ||
    jobId ||
    "Chi tiết tiến trình pipeline";

  // Loading initial snapshot
  if (!jobId || (isLoading && !jobDetail)) {
    return (
      <div className="-mt-3 min-h-[calc(100vh-96px)] space-y-4 rounded-[20px] bg-[var(--automl-workspace-bg)] px-3 pt-2.5 pb-4 sm:px-4 sm:pt-3 sm:pb-5">
        <div className="flex items-center justify-between">
          <BreadcrumbNav
            showHome={false}
            items={[
              { label: "Lịch sử huấn luyện", href: "/training-history" },
              { label: jobId || "Đang tải..." },
            ]}
          />
          <BackButton fallbackHref="/training-history" />
        </div>
        <AppLoading variant="page" label="Đang tải snapshot pipeline từ máy chủ..." />
      </div>
    );
  }

  // Error fetching job detail
  if (isError && !jobDetail) {
    return (
      <div className="-mt-3 min-h-[calc(100vh-96px)] space-y-4 rounded-[20px] bg-[var(--automl-workspace-bg)] px-3 pt-2.5 pb-4 text-[var(--automl-data-text)] sm:px-4 sm:pt-3 sm:pb-5">
        <div className="flex items-center justify-between">
          <BreadcrumbNav
            showHome={false}
            items={[
              { label: "Lịch sử huấn luyện", href: "/training-history" },
              { label: jobId },
            ]}
          />
          <BackButton fallbackHref="/training-history" />
        </div>
        <div className="mx-auto max-w-lg rounded-3xl border border-red-500/30 bg-[var(--automl-data-card-bg)] p-6 text-center shadow-sm space-y-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-red-500/10 text-red-500">
            <AlertCircle className="h-6 w-6" />
          </div>
          <div className="space-y-1">
            <h2 className="text-lg font-extrabold">Không thể tải thông tin tác vụ</h2>
            <p className="text-xs text-[var(--automl-data-muted)]">
              {getApiErrorMessage(error, `Không tìm thấy hoặc không thể truy cập job ${jobId}.`)}
            </p>
          </div>
          <div className="flex items-center justify-center gap-3">
            <Button
              type="button"
              variant="outline"
              className="rounded-xl font-bold"
              onClick={() => refetch()}
            >
              <RefreshCw className={cn("mr-1.5 h-4 w-4", isFetching && "animate-spin")} />
              Thử lại
            </Button>
            <Link href="/training-history">
              <Button type="button" className="rounded-xl bg-automl-blue font-bold text-white">
                Về lịch sử huấn luyện
              </Button>
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="-mt-3 min-h-[calc(100vh-96px)] space-y-4 rounded-[20px] bg-[var(--automl-workspace-bg)] px-3 pt-2.5 pb-4 text-[var(--automl-data-text)] sm:px-4 sm:pt-3 sm:pb-5">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <BreadcrumbNav
          showHome={false}
          items={[
            { label: "Lịch sử huấn luyện", href: "/training-history" },
            { label: datasetTitle },
          ]}
        />
        <div className="flex flex-wrap items-center gap-2.5">
          {realtimeBadge}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => refetch()}
            disabled={isFetching}
            className="h-9 rounded-xl border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] px-3 text-xs font-bold"
          >
            <RefreshCw className={cn("mr-1.5 h-3.5 w-3.5", isFetching && "animate-spin")} />
            Làm mới
          </Button>
          {jobActive && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setConfirmCancelOpen(true)}
              disabled={isCancelling}
              className="h-9 rounded-xl border-red-500/30 bg-red-500/10 px-3 text-xs font-bold text-red-600 hover:bg-red-500/20 dark:text-red-400"
            >
              <StopCircle className="mr-1.5 h-3.5 w-3.5" />
              Hủy huấn luyện
            </Button>
          )}
          <BackButton fallbackHref="/training-history" />
        </div>
      </div>

      {/* Hero Result Banner */}
      <section className="rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-black uppercase tracking-wider text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
                Pipeline AutoML · Job {activePipeline?.job_id || jobId}
              </span>
              <span className="rounded-full border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-2 py-0.5 text-[10px] font-bold text-[var(--automl-data-muted)]">
                v{activePipeline?.version || "2.0.0"}
                {activePipeline?.source ? ` · ${activePipeline.source}` : ""}
              </span>
              {(jobDetail?.data?.name || datasetFromUrl) && (
                <span className="rounded-full border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-2.5 py-0.5 text-[11px] font-bold text-[var(--automl-data-text)]">
                  {jobDetail?.data?.name || datasetFromUrl}
                </span>
              )}
            </div>

            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h1 className="truncate text-2xl font-extrabold tracking-tight text-[var(--automl-data-text)] sm:text-3xl">
                {bestModelName || (jobActive ? "Đang tìm mô hình tối ưu..." : "—")}
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
                getMetricDirection(metricSort, metricsConfig) === "minimize"
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
                jobCompleted
                  ? "Hoàn tất"
                  : jobRunning
                    ? "Đang chạy"
                    : jobQueued
                      ? "Đang chờ"
                      : jobCancelled
                        ? "Đã hủy"
                        : jobFailed
                          ? "Lỗi"
                          : "Đang chờ"
              }
              detail={`Chế độ: ${activePipeline?.mode || jobDetail?.config?.choose || "AutoML"}`}
              tone={
                jobCompleted
                  ? "text-emerald-600 dark:text-emerald-400"
                  : jobRunning
                    ? "text-blue-600 dark:text-cyan-400"
                    : jobFailed
                      ? "text-red-600 dark:text-red-400"
                      : "text-slate-500"
              }
            />
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            {jobCompleted && (
              <Link href={`/implement-project/${jobId}`}>
                <Button
                  type="button"
                  variant="outline"
                  className="h-11 rounded-xl border-blue-500/30 bg-blue-500/10 px-4 font-bold text-automl-blue hover:bg-blue-500/20 dark:text-cyan-300"
                >
                  <Rocket className="mr-2 h-4 w-4" />
                  Triển khai
                </Button>
              </Link>
            )}
            <Button
              type="button"
              disabled={!jobCompleted}
              className={cn(
                "h-11 shrink-0 rounded-xl px-5 font-bold shadow-sm transition-all",
                openUpload
                  ? "bg-slate-700 text-white hover:bg-slate-800"
                  : "bg-emerald-600 text-white hover:bg-emerald-700 shadow-emerald-600/20",
              )}
              onClick={() => setOpenUpload((v) => !v)}
            >
              <Upload className="mr-2 h-4 w-4" />
              {openUpload ? "Đóng kiểm thử" : "Upload kiểm thử"}
            </Button>
          </div>
        </div>
      </section>

      {/* Job Error / Cancelled Banner */}
      {jobErrorMessage && (
        <div className="flex items-start gap-3 rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-xs text-red-700 dark:text-red-300">
          {jobCancelled ? (
            <Ban className="mt-0.5 h-4 w-4 shrink-0" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          )}
          <div className="min-w-0 space-y-1">
            <p className="font-extrabold">
              {jobCancelled ? "Tác vụ huấn luyện đã bị hủy" : "Tác vụ huấn luyện gặp lỗi"}
            </p>
            <p className="font-mono text-[11px] break-words">{jobErrorMessage}</p>
          </div>
        </div>
      )}

      {/* Holdout Scores Strip (v2.0.0) */}
      {pipelineHoldoutScores && Object.keys(pipelineHoldoutScores).length > 0 && (
        <section className="rounded-[22px] border border-emerald-500/25 bg-emerald-500/5 p-4 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
              <h2 className="text-xs font-black uppercase tracking-wider text-emerald-700 dark:text-emerald-300">
                Đánh giá độc lập trên tập Holdout ({bestModelName || "Best Model"})
              </h2>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {Object.entries(pipelineHoldoutScores).map(([hKey, hVal]) => (
                <div
                  key={hKey}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/25 bg-[var(--automl-data-card-bg)] px-3 py-1 text-xs"
                >
                  <span className="font-mono text-[11px] font-black uppercase text-emerald-700 dark:text-emerald-300">
                    {hKey}:
                  </span>
                  <span className="font-mono font-extrabold text-[var(--automl-data-text)]">
                    {formatPipelineValue(hVal)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* Progress Map Visualizer */}
      {progressMapPipeline && (
        <section className="space-y-2">
          <ProgressMap
            pipeline={progressMapPipeline}
            viewMode={graphViewMode}
            onViewModeChange={setGraphViewMode}
            statusBadge={realtimeBadge}
          />
        </section>
      )}

      {/* Upload Predict Modal/Box */}
      {openUpload && jobCompleted && (
        <section className="rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 shadow-sm animate-in fade-in slide-in-from-top-3">
          <div className="mb-4 flex items-center justify-between border-b border-[var(--automl-data-card-border)] pb-3">
            <div>
              <h2 className="text-base font-extrabold text-[var(--automl-data-text)]">
                Dự đoán thử nghiệm với mô hình tốt nhất
              </h2>
              <p className="text-xs text-[var(--automl-data-muted)]">
                Tải lên tập dữ liệu mẫu để chạy inference trực tiếp với mô hình{" "}
                {bestModelName || "được chọn"}.
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
          <UploadPredictBox jobId={jobId} />
        </section>
      )}

      {/* Leaderboard Table & Metric Comparison Chart */}
      <section className="automl-data-card">
        <div className="automl-data-toolbar">
          <div>
            <h2 className="automl-data-title">Bảng xếp hạng mô hình & Điểm số</h2>
            <p className="automl-data-subtitle">
              So sánh toàn bộ mô hình trong pipeline huấn luyện (hỗ trợ schema v2.0.0: trials, best_trial, holdout_scores).
            </p>
          </div>
          <div className="automl-data-actions">
            <span className="automl-data-chip">
              Sắp xếp theo {toTitleLabel(metricSort)} (
              {getMetricDirection(metricSort, metricsConfig)})
            </span>
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
          </div>
        </div>

        <div className="automl-table-wrap pt-5">
          {showChart ? (
            chartData.length > 0 ? (
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
              <div className="rounded-[16px] border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-8 text-center text-xs font-semibold text-[var(--automl-data-muted)]">
                Chưa có đủ dữ liệu điểm số để vẽ biểu đồ so sánh.
              </div>
            )
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
                        ({getMetricDirection(metricKey, metricsConfig) === "minimize" ? "min" : "max"})
                      </span>
                    </TableHead>
                  ))}
                  <TableHead>Tham số tối ưu (Best Params)</TableHead>
                  <TableHead className="text-center w-28">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {leaderboardModels.length > 0 ? (
                  leaderboardModels.map((model, index) => {
                    const isBest =
                      bestModelName !== null
                        ? model.model_name === bestModelName
                        : index === 0 && Object.keys(model.scores).length > 0;
                    const normalizedStatus = normalizeNodeStatus(model.status);

                    const openModal = () =>
                      setSelectedModalModel({
                        model_name: model.model_name,
                        status: model.status,
                        error: model.error,
                        scores: model.scores,
                        best_params: model.best_params,
                        holdout_scores: model.holdout_scores,
                        trials: model.trials,
                        best_trial: model.best_trial,
                        n_trials: model.n_trials,
                        n_pruned: model.n_pruned,
                        rank: index + 1,
                      });

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
                              #1
                            </span>
                          ) : (
                            index + 1
                          )}
                        </TableCell>
                        <TableCell className="font-extrabold text-[var(--automl-data-text)]">
                          <div className="flex flex-wrap items-center gap-2">
                            <span>{model.model_name}</span>
                            {isBest && (
                              <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 text-[10px] py-0 px-1.5">
                                Best
                              </Badge>
                            )}
                            {model.n_trials !== null && (
                              <span className="inline-flex items-center gap-1 rounded-md border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-1.5 py-0.5 text-[10px] font-bold text-[var(--automl-data-muted)]">
                                <FlaskConical className="h-2.5 w-2.5" />
                                {model.n_trials} trials
                                {model.best_trial !== null ? ` · #${model.best_trial}` : ""}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {normalizedStatus === "done" ? (
                            <Badge variant="outline" className="automl-status-success rounded-full text-[11px] font-bold">
                              Hoàn tất
                            </Badge>
                          ) : normalizedStatus === "running" ? (
                            <Badge variant="secondary" className="automl-status-warning rounded-full text-[11px] font-bold">
                              <Clock3 className="mr-1 h-3 w-3 animate-spin" />
                              Đang chạy
                            </Badge>
                          ) : normalizedStatus === "failed" ? (
                            <Badge variant="default" className="automl-status-error rounded-full text-[11px] font-bold">
                              <XCircle className="mr-1 h-3 w-3" />
                              Lỗi
                            </Badge>
                          ) : normalizedStatus === "skipped" ? (
                            <Badge variant="outline" className="rounded-full border-slate-300 bg-slate-100 text-[11px] font-bold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                              <SkipForward className="mr-1 h-3 w-3" />
                              Bỏ qua
                            </Badge>
                          ) : (
                            <span className="text-xs font-semibold text-[var(--automl-data-muted)]">
                              Đang chờ
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
                            onViewDetails={openModal}
                          />
                        </TableCell>
                        <TableCell className="text-center">
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            className="h-8 rounded-xl px-2.5 text-xs font-bold border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] hover:bg-blue-50 hover:text-automl-blue dark:hover:bg-cyan-950/50 dark:hover:text-cyan-300"
                            onClick={openModal}
                          >
                            <Eye className="mr-1.5 h-3.5 w-3.5" />
                            Chi tiết
                          </Button>
                        </TableCell>
                      </TableRow>
                    );
                  })
                ) : (
                  <TableRow>
                    <TableCell
                      colSpan={5 + Object.keys(metricsConfig).length}
                      className="py-8 text-center text-xs text-[var(--automl-data-muted)]"
                    >
                      {jobActive
                        ? "Đang chờ kết quả từng mô hình từ worker realtime..."
                        : "Chưa có dữ liệu mô hình (—)"}
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </div>
      </section>

      {/* Model Detail Modal (Scores, Holdout, Best Params, Trials) */}
      <ModelDetailModal
        open={Boolean(selectedModalModel)}
        onOpenChange={(open) => !open && setSelectedModalModel(null)}
        model={selectedModalModel}
        isBestModel={Boolean(
          selectedModalModel?.model_name && selectedModalModel.model_name === bestModelName,
        )}
        metricSort={metricSort}
        metricsConfig={metricsConfig}
        problemType={problemType}
      />

      {/* Cancel Job Confirmation Dialog */}
      <AlertDialog open={confirmCancelOpen} onOpenChange={setConfirmCancelOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Xác nhận hủy tác vụ huấn luyện?</AlertDialogTitle>
            <AlertDialogDescription>
              Tác vụ <span className="font-mono font-bold">{jobId}</span> sẽ được dừng và chuyển
              sang trạng thái đã hủy.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={isCancelling}>Quay lại</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleCancelJob}
              disabled={isCancelling}
              className="bg-red-600 text-white hover:bg-red-700"
            >
              Xác nhận hủy
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
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
    <p
      className={cn(
        "mt-1 truncate text-base font-extrabold text-[var(--automl-data-text)]",
        tone,
      )}
    >
      {value}
    </p>
    {detail && (
      <p className="mt-0.5 truncate text-[10px] font-semibold text-[var(--automl-data-muted)]">
        {detail}
      </p>
    )}
  </div>
);

export default TrainingHistoryDetailPage;
