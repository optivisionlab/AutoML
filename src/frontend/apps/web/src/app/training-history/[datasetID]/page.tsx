"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Switch } from "@/shared/components/ui/switch";
import { Label } from "@/shared/components/ui/label";
import { ChartContainer } from "@/shared/components/ui/chart";
import { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
import { ChartTooltip, ChartTooltipContent } from "@/shared/components/ui/chart";
import { ChartLegend, ChartLegendContent } from "@/shared/components/ui/chart";
import { type ChartConfig } from "@/shared/components/ui/chart";
import React from "react";
import toTitleLabel from "@/shared/utils/toTitleLable";
import { Button } from "@/shared/components/ui/button";
import UploadPredictBox from "@/shared/components/common/UploadPredictBox";
import AppLoading from "@/shared/components/common/AppLoading";
import BackButton from "@/shared/components/common/BackButton";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import ProgressMap from "@/features/training/components/progress-map/ProgressMap";
import { progressMapSample } from "@/features/training/constants/progressMapSample";
import { useGetMetricsQuery } from "@/core/api/automlApi";
import { useGetJobInfoQuery } from "@/core/api/jobApi";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";

const CHART_COLORS = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed"];

type Props = {
  params: Promise<{
    datasetID: string;
  }>;
};

const formatMetric = (value?: number) => {
  if (typeof value !== "number") return "-";
  return value.toFixed(6);
};

const formatPercent = (value?: number) => {
  if (typeof value !== "number") return "-";
  return `${(value * 100).toFixed(2)}%`;
};

const ResultPage = ({ params }: Props) => {
  const [datasetID, setDatasetID] = useState<string | null>(null);
  const [showChart, setShowChart] = useState(false);
  const [openRow, setOpenRow] = useState<string | null>(null);

  useEffect(() => {
    const unwrapParams = async () => {
      const unwrappedParams = await params;
      setDatasetID(unwrappedParams.datasetID);
    };

    unwrapParams();
  }, [params]);

  const {
    data: result,
    isError,
    isLoading,
  } = useGetJobInfoQuery(datasetID ?? "", {
    skip: !datasetID,
  });

  const problemType = result?.config?.problem_type || "classification";
  const hasClassificationMetrics = Boolean(
    result?.orther_model_scores?.[0]?.scores?.f1,
  );

  const { data: metricsData } = useGetMetricsQuery(problemType, {
    skip: !result || hasClassificationMetrics,
  });

  const metrics = useMemo(
    () =>
      hasClassificationMetrics
        ? {
            0: "accuracy",
            1: "f1",
            2: "precision",
            3: "recall",
          }
        : metricsData?.metrics ?? {},
    [hasClassificationMetrics, metricsData?.metrics],
  );

  const chartConfig = useMemo(
    () =>
      Object.entries(metrics).reduce((config: ChartConfig, [key, value], index) => {
        const itemConfig = {
          label: value,
          value,
          color: CHART_COLORS[index % CHART_COLORS.length],
        };
        config[key] = itemConfig;
        return config;
      }, {}) satisfies ChartConfig,
    [metrics],
  );

  const chartData = useMemo(() => {
    if (!result?.orther_model_scores) return [];

    return result.orther_model_scores
      .filter((model: any) => {
        const r2 = model.scores?.r2;
        if (r2 !== undefined && r2 < -1) return false;

        const mse = model.scores?.mse;
        if (mse !== undefined && mse > 1000000) return false;

        return true;
      })
      .map((model: any) => {
        const row: Record<string, string | number> = { name: model.model_name };
        Object.entries(chartConfig).forEach(([key, metric]: any) => {
          let val = model.scores?.[metric.value] || 0;
          if (metric.value === "r2" && val < 0) val = 0;
          row[key] = parseFloat(val.toFixed(4));
        });
        return row;
      });
  }, [result, chartConfig]);

  const sortedModels = useMemo(() => {
    if (!result?.orther_model_scores) return [];
    const metricSort = result.config?.metric_sort || "accuracy";

    return [...result.orther_model_scores].sort((a: any, b: any) => {
      const scoreA = a.scores?.[metricSort] ?? 0;
      const scoreB = b.scores?.[metricSort] ?? 0;
      return scoreB - scoreA;
    });
  }, [result]);

  const features = result?.config?.list_feature?.join(", ") || "Không có dữ liệu";
  const metricSort = result?.config?.metric_sort || "accuracy";
  const progressMapPipeline = useMemo(() => {
    if (!result) return progressMapSample;

    return {
      ...progressMapSample,
      predictionColumn: result.config?.target || progressMapSample.predictionColumn,
      rankBy: toTitleLabel(metricSort),
      nodes: progressMapSample.nodes.map((node) => {
        if (node.id === "xgb") {
          return {
            ...node,
            label: result.best_model || node.label,
            params: {
              ...node.params,
              ...(typeof result.best_params === "object" && result.best_params
                ? (result.best_params as Record<string, string | number | boolean>)
                : {}),
            },
            result: {
              ...node.result,
              [metricSort]: formatMetric(result.best_score),
            },
          };
        }

        if (node.id === "model-selection") {
          return {
            ...node,
            params: {
              ...node.params,
              metric: metricSort,
              problem_type: result.config?.problem_type || problemType,
            },
            result: {
              ...node.result,
              best_model: result.best_model || "Không rõ",
            },
          };
        }

        return node;
      }),
    };
  }, [metricSort, problemType, result]);

  if (isError) {
    return (
      <div className="space-y-4 bg-[var(--automl-workspace-bg)] px-4">
        <BackButton fallbackHref="/training-history" />
        <div className="flex min-h-[70vh] items-center justify-center">
        <div className="w-full max-w-md rounded-[18px] border border-red-900/70 bg-[var(--automl-data-card-bg)] p-6 text-[var(--automl-data-text)]">
          <div className="mb-4 flex items-center gap-3">
            <AlertCircle className="text-red-400" />
            <h2 className="text-lg font-bold text-red-300">Đã xảy ra lỗi</h2>
          </div>
          <p className="text-sm leading-relaxed text-[var(--automl-data-muted)]">
            Có lỗi xảy ra trong quá trình tải kết quả huấn luyện.
          </p>
        </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-96px)] rounded-[24px] bg-[var(--automl-workspace-bg)] p-4 text-[var(--automl-data-text)] sm:p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <BreadcrumbNav
          items={[
            { label: "Lịch sử huấn luyện", href: "/training-history" },
            { label: datasetID || "Chi tiết kết quả" },
          ]}
        />
        <BackButton fallbackHref="/training-history" />
      </div>
      {isLoading && (
        <AppLoading variant="overlay" label="Đang tải kết quả..." />
      )}

      {result && (
        <div className="flex w-full flex-col gap-6">
          <section className="rounded-[20px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-4">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-black uppercase tracking-wide text-automl-blue">
                  Kết quả huấn luyện · Model ID {result.best_model_id || "-"}
                </p>
                <h1 className="mt-1 truncate text-2xl font-extrabold tracking-tight text-[var(--automl-data-text)]">
                  {result.best_model || "Không rõ"}
                </h1>
                <p className="mt-1 truncate text-sm font-semibold text-[var(--automl-data-muted)]">
                  Cột dự đoán {result.config?.target || "Không rõ"} · {features}
                </p>
              </div>

              <div className="grid gap-2 sm:grid-cols-3 xl:w-[520px]">
                <CompactSummary label="Điểm" value={formatPercent(result.best_score)} />
                <CompactSummary label="Chỉ số" value={toTitleLabel(metricSort)} />
                <CompactSummary label="Chế độ" value={result.config?.choose || "Không rõ"} />
              </div>

              <Button
                className={`h-10 shrink-0 px-4 font-bold rounded-xl shadow-sm ${openRow === datasetID ? "automl-action-danger" : "bg-emerald-600 text-white hover:bg-emerald-700"}`}
                onClick={() => setOpenRow(openRow === datasetID ? null : datasetID)}
              >
                {openRow === datasetID ? "Đóng upload" : "Upload kiểm thử"}
              </Button>
            </div>
          </section>

          <ProgressMap pipeline={progressMapPipeline} />

          {openRow === datasetID && (
            <section className="rounded-[22px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-5">
              <UploadPredictBox jobId={datasetID || ""} />
            </section>
          )}

          <section className="automl-data-card">
            <div className="automl-data-toolbar">
              <div>
                <h2 className="automl-data-title">Bảng xếp hạng pipeline</h2>
                <p className="automl-data-subtitle">Các pipeline được sắp xếp theo chỉ số đang tối ưu.</p>
              </div>
              <div className="automl-data-actions">
                <span className="automl-data-chip">Sắp xếp theo {toTitleLabel(metricSort)}</span>
                <div className="flex items-center gap-2 text-[var(--automl-data-muted)]">
                  <Label htmlFor="toggle-chart" className="text-sm font-bold">Biểu đồ</Label>
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
                <div className="rounded-[14px] border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4">
                  <ChartContainer config={chartConfig} className="max-h-[450px] w-full">
                    <BarChart accessibilityLayer data={chartData}>
                      <CartesianGrid vertical={false} stroke="var(--automl-data-card-border)" />
                      <XAxis
                        dataKey="name"
                        tickLine={false}
                        tickMargin={10}
                        axisLine={false}
                        tickFormatter={(value) => value.replace(/([a-z])([A-Z])/g, "$1 $2")}
                      />
                      <YAxis domain={[0, 1]} tickLine={false} axisLine={false} />
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
                      <TableHead>Hạng</TableHead>
                      <TableHead>Mô hình</TableHead>
                      <TableHead>Thuật toán</TableHead>
                      {Object.entries(metrics).map(([metric, value]) => (
                        <TableHead key={metric}>{toTitleLabel(value)}</TableHead>
                      ))}
                      <TableHead>Thao tác</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {sortedModels.map((model: any, index: number) => (
                      <TableRow key={`${model.model_name}-${index}`} className={index === 0 ? "automl-row-highlight" : undefined}>
                        <TableCell className="font-extrabold">{index + 1}</TableCell>
                        <TableCell className="font-extrabold text-[var(--automl-data-text)]">Pipeline {index + 1}</TableCell>
                        <TableCell>{model.model_name}</TableCell>
                        {Object.values(metrics).map((metricKey: string) => (
                          <TableCell key={metricKey}>{formatMetric(model.scores?.[metricKey])}</TableCell>
                        ))}
                        <TableCell>{index === 0 ? "Lưu" : "Mô hình"}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
};

const CompactSummary = ({
  label,
  value,
}: {
  label: string;
  value: string;
}) => (
  <div className="min-w-0 rounded-2xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-3 py-2">
    <p className="text-[11px] font-black uppercase tracking-wide text-[var(--automl-data-muted)]">
      {label}
    </p>
    <p className="mt-0.5 truncate text-sm font-extrabold text-[var(--automl-data-text)]">
      {value}
    </p>
  </div>
);

export default ResultPage;
