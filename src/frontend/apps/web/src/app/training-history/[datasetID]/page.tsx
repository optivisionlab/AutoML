"use client";

import React, { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  Award,
  BarChart3,
  CheckCircle2,
  Clock3,
  Cpu,
  Database,
  Eye,
  Layers,
  Sparkles,
  Table as TableIcon,
  Upload,
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
  MOCK_PIPELINE_COMPLETED,
  MOCK_PIPELINE_EMPTY,
  MOCK_PIPELINE_FAILED,
  MOCK_PIPELINE_RUNNING,
} from "@/features/training/constants/pipelineFixtures";
import {
  buildProgressMapFromPipeline,
  formatPipelineValue,
  GraphViewMode,
} from "@/features/training/utils/pipelineGraphBuilder";
import { useGetJobInfoQuery, useGetPipelineSampleQuery } from "@/core/api/jobApi";

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

type PresetKey = "live" | "completed" | "running" | "empty" | "failed";

const ResultPage = ({ params }: Props) => {
  const [datasetID, setDatasetID] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [openUpload, setOpenUpload] = useState(false);
  const [activePreset, setActivePreset] = useState<PresetKey>("live");
  const [graphViewMode, setGraphViewMode] = useState<GraphViewMode>("expanded");
  const [selectedModalModel, setSelectedModalModel] = useState<ModelDetailData | null>(null);

  useEffect(() => {
    const unwrapParams = async () => {
      const unwrappedParams = await params;
      setDatasetID(unwrappedParams.datasetID);
    };

    unwrapParams();
  }, [params]);


  // Query API Pipeline Mẫu từ backend / mock_api (/get-pipeline-sample)
  const {
    data: sampleApiRes,
    isLoading: isSampleLoading,
    isError: isSampleError,
  } = useGetPipelineSampleQuery(
    {
      problem_type: "regression",
      job_id: datasetID || "job-001",
    },
    {
      skip: !datasetID,
    },
  );

  // Query API Job truyền thống (nếu có)
  const {
    data: legacyJobResult,
    isLoading: isLegacyLoading,
  } = useGetJobInfoQuery(datasetID ?? "", {
    skip: !datasetID,
  });

  // Xác định dữ liệu Pipeline hiện tại dựa trên preset hoặc API
  const activePipeline: PipelineData = useMemo(() => {
    if (activePreset === "empty") return MOCK_PIPELINE_EMPTY;
    if (activePreset === "running") return MOCK_PIPELINE_RUNNING;
    if (activePreset === "completed") return MOCK_PIPELINE_COMPLETED;
    if (activePreset === "failed") return MOCK_PIPELINE_FAILED;

    // Chế độ "live"
    if (sampleApiRes?.pipeline) {
      return sampleApiRes.pipeline;
    }

    if (legacyJobResult?.pipeline) {
      return legacyJobResult.pipeline;
    }

    // Nếu API job truyền thống có dữ liệu model scores, biến đổi thành pipeline
    if (legacyJobResult && legacyJobResult.orther_model_scores) {
      const bestModel = legacyJobResult.best_model || "BestModel";
      const metricSort = legacyJobResult.config?.metric_sort || "accuracy";

      const modelsRecord: Record<string, any> = {};
      legacyJobResult.orther_model_scores.forEach((m) => {
        if (!m.model_name) return;
        modelsRecord[m.model_name] = {
          status: "done",
          error: null,
          best_params: m.model_name === bestModel ? legacyJobResult.best_params : null,
          scores: m.scores || {},
        };
      });

      return {
        job_id: legacyJobResult.job_id || datasetID,
        version: "1.0.0",
        mode: legacyJobResult.config?.choose || "automl",
        status: legacyJobResult.status === 1 ? "done" : legacyJobResult.status === 0 ? "running" : "failed",
        read_dataset: {
          name: "Read dataset",
          kind: "data_loading",
          depends_on: [],
          status: "done",
          params: { id_data: legacyJobResult.data?.name || datasetID, format: "csv" },
          output: { data_url: "loaded" },
        },
        preprocessing: {
          name: "Preprocessing",
          kind: "preprocessing",
          depends_on: ["read_dataset"],
          status: "done",
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
          status: "done",
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
          status: "done",
          params: {},
          output: {
            models: modelsRecord,
          },
        },
        select_best: {
          name: "Select best model",
          kind: "model_selection",
          depends_on: ["train"],
          status: "done",
          params: { dependency_policy: "all_terminal" },
          output: {
            best_model: bestModel,
          },
        },
      };
    }

    // Mặc định ban đầu nếu live chưa có phản hồi hoặc đang chạy mock_api
    return MOCK_PIPELINE_COMPLETED;
  }, [activePreset, sampleApiRes, legacyJobResult, datasetID]);

  // Xây dựng DAG pipeline trực tiếp từ activePipeline (dựa vào depends_on)
  const progressMapPipeline = useMemo(() => {
    return buildProgressMapFromPipeline(activePipeline, { mode: graphViewMode });
  }, [activePipeline, graphViewMode]);

  // Trích xuất thông tin chung về Pipeline
  const bestModelName =
    activePipeline.select_best?.output?.best_model ||
    legacyJobResult?.best_model ||
    null;

  const metricSort =
    activePipeline.model_selection?.params?.metric_sort ||
    legacyJobResult?.config?.metric_sort ||
    "r2";

  const targetColumn =
    activePipeline.preprocessing?.params?.target ||
    legacyJobResult?.config?.target ||
    null;

  const featureList =
    activePipeline.preprocessing?.params?.list_feature ||
    legacyJobResult?.config?.list_feature ||
    [];

  const problemType =
    activePipeline.model_selection?.params?.problem_type ||
    legacyJobResult?.config?.problem_type ||
    "regression";

  // Lấy danh sách metrics được cấu hình
  const metricsConfig: Record<string, string> = useMemo(() => {
    if (activePipeline.model_selection?.params?.metrics) {
      return activePipeline.model_selection.params.metrics;
    }
    if (problemType === "regression") {
      return { r2: "maximize", mse: "minimize", mae: "minimize", mape: "minimize" };
    }
    return { accuracy: "maximize", f1: "maximize", precision: "maximize", recall: "maximize" };
  }, [activePipeline.model_selection?.params?.metrics, problemType]);

  // Điểm số tốt nhất
  const bestScoreVal = useMemo(() => {
    if (!bestModelName) return null;
    const modelDetail = activePipeline.train?.output?.models?.[bestModelName];
    if (modelDetail?.scores && modelDetail.scores[metricSort] !== undefined) {
      return modelDetail.scores[metricSort];
    }
    return legacyJobResult?.best_score ?? null;
  }, [bestModelName, activePipeline.train?.output?.models, metricSort, legacyJobResult?.best_score]);

  // Trích xuất danh sách mô hình từ pipeline.train.output.models
  const leaderboardModels = useMemo(() => {
    const modelsObj = activePipeline.train?.output?.models;
    if (modelsObj && Object.keys(modelsObj).length > 0) {
      const list = Object.entries(modelsObj).map(([modelName, info]) => {
        return {
          model_name: modelName,
          status: info.status,
          error: info.error,
          scores: info.scores || {},
          best_params: info.best_params || null,
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
      return [...legacyJobResult.orther_model_scores].sort((a, b) => {
        const scoreA = a.scores?.[metricSort] ?? 0;
        const scoreB = b.scores?.[metricSort] ?? 0;
        return scoreB - scoreA;
      });
    }

    return [];
  }, [activePipeline.train?.output?.models, legacyJobResult?.orther_model_scores, metricSort, metricsConfig]);

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

  const isLoading = (isSampleLoading || isLegacyLoading) && activePreset === "live";

  return (
    <div className="min-h-[calc(100vh-96px)] space-y-6 rounded-[24px] bg-[var(--automl-workspace-bg)] p-4 text-[var(--automl-data-text)] sm:p-6">
      {/* Top Header & Breadcrumbs */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <BreadcrumbNav
          items={[
            { label: "Lịch sử huấn luyện", href: "/training-history" },
            { label: datasetID || "Chi tiết tiến trình pipeline" },
          ]}
        />
        <div className="flex items-center gap-3">
          <BackButton fallbackHref="/training-history" />
        </div>
      </div>

      {/* Preset & Data Source Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] px-4 py-3 shadow-xs">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)] mr-1">
            Nguồn dữ liệu thử nghiệm:
          </span>
          <Button
            type="button"
            size="sm"
            variant={activePreset === "live" ? "default" : "outline"}
            className={cn(
              "h-8 rounded-xl px-3 text-xs font-bold transition-all",
              activePreset === "live"
                ? "bg-automl-blue text-white shadow-xs"
                : "border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-text)]",
            )}
            onClick={() => setActivePreset("live")}
          >
            <Database className="mr-1.5 h-3.5 w-3.5" />
            Live API (/get-pipeline-sample)
          </Button>

          <Button
            type="button"
            size="sm"
            variant={activePreset === "completed" ? "default" : "outline"}
            className={cn(
              "h-8 rounded-xl px-3 text-xs font-bold transition-all",
              activePreset === "completed"
                ? "bg-emerald-600 text-white shadow-xs"
                : "border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-text)]",
            )}
            onClick={() => setActivePreset("completed")}
          >
            <CheckCircle2 className="mr-1.5 h-3.5 w-3.5 text-emerald-300" />
            Mẫu: Hoàn thành (Full Data)
          </Button>

          <Button
            type="button"
            size="sm"
            variant={activePreset === "running" ? "default" : "outline"}
            className={cn(
              "h-8 rounded-xl px-3 text-xs font-bold transition-all",
              activePreset === "running"
                ? "bg-cyan-600 text-white shadow-xs"
                : "border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-text)]",
            )}
            onClick={() => setActivePreset("running")}
          >
            <Clock3 className="mr-1.5 h-3.5 w-3.5 text-cyan-300 animate-spin" />
            Mẫu: Đang chạy (Running)
          </Button>

          <Button
            type="button"
            size="sm"
            variant={activePreset === "empty" ? "default" : "outline"}
            className={cn(
              "h-8 rounded-xl px-3 text-xs font-bold transition-all",
              activePreset === "empty"
                ? "bg-slate-700 text-white shadow-xs"
                : "border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-text)]",
            )}
            onClick={() => setActivePreset("empty")}
          >
            Mẫu: Rỗng (Toàn bộ null)
          </Button>

          <Button
            type="button"
            size="sm"
            variant={activePreset === "failed" ? "default" : "outline"}
            className={cn(
              "h-8 rounded-xl px-3 text-xs font-bold transition-all",
              activePreset === "failed"
                ? "bg-red-600 text-white shadow-xs"
                : "border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-text)]",
            )}
            onClick={() => setActivePreset("failed")}
          >
            <XCircle className="mr-1.5 h-3.5 w-3.5 text-red-300" />
            Mẫu: Bị lỗi (Failed)
          </Button>
        </div>

        {activePreset === "live" && isSampleError && (
          <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-amber-500 dark:text-amber-400">
            <AlertCircle className="h-3.5 w-3.5" />
            Chưa kết nối được mock_api (:8001), hiển thị mẫu dự phòng
          </span>
        )}
      </div>

      {isLoading && <AppLoading variant="overlay" label="Đang tải dữ liệu pipeline..." />}

      {/* Hero Result Banner */}
      <section className="rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5 shadow-sm">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 text-[11px] font-black uppercase tracking-wider text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
                Pipeline AutoML · Job {activePipeline.job_id || datasetID || "—"}
              </span>
              <span className="rounded-full border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-2 py-0.5 text-[10px] font-bold text-[var(--automl-data-muted)]">
                v{activePipeline.version || "1.0.0"}
              </span>
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
              Cột mục tiêu: <span className="font-bold text-[var(--automl-data-text)]">{formatPipelineValue(targetColumn)}</span> · Đặc trưng: <span className="font-bold text-[var(--automl-data-text)]">{featureList.length > 0 ? featureList.join(", ") : "—"}</span>
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 xl:w-[580px]">
            <MetricCard
              label={`Điểm (${metricSort.toUpperCase()})`}
              value={formatPipelineValue(bestScoreVal)}
              detail={metricsConfig[metricSort] === "minimize" ? "Mục tiêu: Tối thiểu" : "Mục tiêu: Tối đa"}
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
                activePipeline.status === "done"
                  ? "Hoàn tất"
                  : activePipeline.status === "running"
                    ? "Đang chạy"
                    : activePipeline.status === "failed"
                      ? "Lỗi"
                      : "Đang chờ"
              }
              detail={`Chế độ: ${activePipeline.mode || "AutoML"}`}
              tone={
                activePipeline.status === "done"
                  ? "text-emerald-600 dark:text-emerald-400"
                  : activePipeline.status === "running"
                    ? "text-cyan-600 dark:text-cyan-400"
                    : activePipeline.status === "failed"
                      ? "text-red-600 dark:text-red-400"
                      : "text-slate-500"
              }
            />
          </div>

          <Button
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
      </section>

      {/* Progress Map Visualizer */}
      <section className="space-y-2">
        <ProgressMap
          pipeline={progressMapPipeline}
          viewMode={graphViewMode}
          onViewModeChange={setGraphViewMode}
        />
      </section>

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
            <div className="flex items-center gap-2 text-[var(--automl-data-muted)]">
              <Label htmlFor="toggle-chart" className="flex items-center gap-1.5 text-xs font-bold cursor-pointer">
                {showChart ? <BarChart3 className="h-4 w-4 text-automl-blue" /> : <TableIcon className="h-4 w-4" />}
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
                {leaderboardModels.length > 0 ? (
                  leaderboardModels.map((model: any, index: number) => {
                    const isBest = model.model_name === bestModelName || index === 0;
                    return (
                      <TableRow
                        key={`${model.model_name}-${index}`}
                        className={cn(
                          isBest && "automl-row-highlight bg-blue-50/60 dark:bg-blue-950/20 font-bold",
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
                          {model.status === "done" ? (
                            <Badge variant="outline" className="automl-status-success rounded-full text-[11px] font-bold">
                              Hoàn tất
                            </Badge>
                          ) : model.status === "running" ? (
                            <Badge variant="secondary" className="automl-status-warning rounded-full text-[11px] font-bold">
                              Đang chạy
                            </Badge>
                          ) : model.status === "failed" ? (
                            <Badge variant="default" className="automl-status-error rounded-full text-[11px] font-bold">
                              Lỗi
                            </Badge>
                          ) : (
                            <span className="text-xs font-semibold text-[var(--automl-data-muted)]">—</span>
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
                  })
                ) : (
                  <TableRow>
                    <TableCell colSpan={4 + Object.keys(metricsConfig).length} className="py-8 text-center text-xs text-[var(--automl-data-muted)]">
                      Chưa có dữ liệu mô hình (—)
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </div>
      </section>

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
