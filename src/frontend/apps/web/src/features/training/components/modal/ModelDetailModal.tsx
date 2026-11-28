"use client";

import React, { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Badge } from "@/shared/components/ui/badge";
import { Button } from "@/shared/components/ui/button";
import {
  AlertTriangle,
  Award,
  Check,
  CheckCircle2,
  Clock3,
  Copy,
  Cpu,
  FlaskConical,
  Gauge,
  LayoutGrid,
  ShieldCheck,
  SkipForward,
  Sliders,
  XCircle,
} from "lucide-react";
import type { ModelTrialDetail } from "@automl/domain";
import {
  formatPipelineValue,
  getMetricDirection,
  normalizeNodeStatus,
} from "@/features/training/utils/pipelineGraphBuilder";
import { cn } from "@/shared/lib/utils";

export interface ModelDetailData {
  model_name: string;
  status?: string | number | null;
  error?: string | null;
  scores?: Record<string, number | null> | null;
  best_params?: Record<string, unknown> | null;
  holdout_scores?: Record<string, number | null> | null;
  trials?: ModelTrialDetail[] | null;
  best_trial?: number | null;
  n_trials?: number | null;
  n_pruned?: number | null;
  rank?: number;
}

interface ModelDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  model: ModelDetailData | null;
  isBestModel?: boolean;
  metricSort?: string;
  metricsConfig?: Record<string, string>;
  problemType?: string;
}

type ModalTab = "all" | "overview" | "trials";

const renderTrialStatusBadge = (status?: string | null) => {
  const raw = (status || "").toLowerCase();
  if (raw === "pruned") {
    return (
      <Badge
        variant="outline"
        className="rounded-full border-amber-400/50 bg-amber-500/10 px-2 py-0 text-[10px] font-bold text-amber-700 dark:text-amber-300"
      >
        Pruned
      </Badge>
    );
  }
  const normalized = normalizeNodeStatus(status);
  if (normalized === "done") {
    return (
      <Badge
        variant="outline"
        className="automl-status-success rounded-full px-2 py-0 text-[10px] font-bold"
      >
        Hoàn tất
      </Badge>
    );
  }
  if (normalized === "running") {
    return (
      <Badge
        variant="secondary"
        className="automl-status-warning rounded-full px-2 py-0 text-[10px] font-bold"
      >
        Đang chạy
      </Badge>
    );
  }
  if (normalized === "failed") {
    return (
      <Badge
        variant="default"
        className="automl-status-error rounded-full px-2 py-0 text-[10px] font-bold"
      >
        Lỗi
      </Badge>
    );
  }
  if (normalized === "skipped") {
    return (
      <Badge
        variant="outline"
        className="rounded-full border-slate-300 bg-slate-100 px-2 py-0 text-[10px] font-bold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300"
      >
        Bỏ qua
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="rounded-full px-2 py-0 text-[10px] font-bold text-slate-500">
      Đang chờ
    </Badge>
  );
};

export const ModelDetailModal: React.FC<ModelDetailModalProps> = ({
  open,
  onOpenChange,
  model,
  isBestModel = false,
  metricSort = "r2",
  metricsConfig = {},
}) => {
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<ModalTab>("all");

  if (!model) return null;

  const normalizedStatus = normalizeNodeStatus(model.status);

  const handleCopyParams = () => {
    if (!model.best_params) return;
    navigator.clipboard.writeText(JSON.stringify(model.best_params, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const paramEntries =
    model.best_params && typeof model.best_params === "object"
      ? Object.entries(model.best_params)
      : [];

  const scoreEntries =
    model.scores && typeof model.scores === "object"
      ? Object.entries(model.scores)
      : [];

  const holdoutEntries =
    model.holdout_scores && typeof model.holdout_scores === "object"
      ? Object.entries(model.holdout_scores)
      : [];

  const trials = Array.isArray(model.trials) ? model.trials : null;
  const totalTrials =
    typeof model.n_trials === "number" ? model.n_trials : trials ? trials.length : null;
  const prunedTrials =
    typeof model.n_pruned === "number"
      ? model.n_pruned
      : trials
        ? trials.filter((t) => String(t.status || "").toLowerCase() === "pruned").length
        : null;

  const hasTrialsSection =
    trials !== null || totalTrials !== null || model.best_trial !== null;

  const trialMetricKeys = (() => {
    if (!trials || trials.length === 0) return Object.keys(metricsConfig);
    const keySet = new Set<string>(Object.keys(metricsConfig));
    for (const trial of trials) {
      const s = trial.scores ?? trial.cv_scores;
      if (s && typeof s === "object") {
        Object.keys(s).forEach((k) => keySet.add(k));
      }
    }
    return Array.from(keySet);
  })();

  const showOverview = activeTab === "all" || activeTab === "overview";
  const showTrials = (activeTab === "all" || activeTab === "trials") && hasTrialsSection;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex w-[95vw] max-w-[1440px] max-h-[92vh] flex-col gap-0 overflow-hidden rounded-[24px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-0 text-[var(--automl-data-text)] shadow-2xl">
        {/* Sticky Header */}
        <DialogHeader className="shrink-0 border-b border-[var(--automl-data-card-border)] px-6 py-4 pr-12">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-500/10 text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <DialogTitle className="text-xl font-extrabold tracking-tight text-[var(--automl-data-text)]">
                    {model.model_name}
                  </DialogTitle>
                  {isBestModel && (
                    <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 text-xs py-0.5 px-2">
                      <Award className="mr-1 h-3.5 w-3.5" /> Best Model
                    </Badge>
                  )}
                  {normalizedStatus === "done" ? (
                    <Badge variant="outline" className="automl-status-success rounded-full px-2.5 py-0.5 text-xs font-bold">
                      <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Hoàn tất
                    </Badge>
                  ) : normalizedStatus === "running" ? (
                    <Badge variant="secondary" className="automl-status-warning rounded-full px-2.5 py-0.5 text-xs font-bold">
                      <Clock3 className="mr-1 h-3.5 w-3.5 animate-spin" /> Đang chạy
                    </Badge>
                  ) : normalizedStatus === "failed" ? (
                    <Badge variant="default" className="automl-status-error rounded-full px-2.5 py-0.5 text-xs font-bold">
                      <XCircle className="mr-1 h-3.5 w-3.5" /> Lỗi
                    </Badge>
                  ) : normalizedStatus === "skipped" ? (
                    <Badge variant="outline" className="rounded-full border-slate-300 bg-slate-100 px-2.5 py-0.5 text-xs font-bold text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      <SkipForward className="mr-1 h-3.5 w-3.5" /> Bỏ qua
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="rounded-full px-2.5 py-0.5 text-xs font-bold text-slate-500">
                      Đang chờ
                    </Badge>
                  )}
                </div>
                <p className="mt-0.5 text-xs font-semibold text-[var(--automl-data-muted)]">
                  {model.rank !== undefined ? `Hạng ${model.rank} trong bảng xếp hạng · ` : ""}
                  Tối ưu theo <span className="uppercase text-automl-blue dark:text-cyan-300">{metricSort}</span>
                  {totalTrials !== null ? ` · ${totalTrials} trials` : ""}
                  {typeof model.best_trial === "number" ? ` · Best #${model.best_trial}` : ""}
                </p>
              </div>
            </div>

            {/* Quick Tab Switcher */}
            {hasTrialsSection && (
              <div className="flex items-center rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setActiveTab("all")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-bold transition-all",
                    activeTab === "all"
                      ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-cyan-300"
                      : "text-[var(--automl-data-muted)] hover:text-[var(--automl-data-text)]",
                  )}
                >
                  <LayoutGrid className="h-3.5 w-3.5" />
                  Tất cả
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("overview")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-bold transition-all",
                    activeTab === "overview"
                      ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-cyan-300"
                      : "text-[var(--automl-data-muted)] hover:text-[var(--automl-data-text)]",
                  )}
                >
                  <Sliders className="h-3.5 w-3.5" />
                  Điểm số & Tham số
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("trials")}
                  className={cn(
                    "flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-bold transition-all",
                    activeTab === "trials"
                      ? "bg-white text-automl-blue shadow-xs dark:bg-slate-800 dark:text-cyan-300"
                      : "text-[var(--automl-data-muted)] hover:text-[var(--automl-data-text)]",
                  )}
                >
                  <FlaskConical className="h-3.5 w-3.5" />
                  Bảng Trials{totalTrials !== null ? ` (${totalTrials})` : ""}
                </button>
              </div>
            )}
          </div>
        </DialogHeader>

        {/* Scrollable Content Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
          {/* Error Banner */}
          {model.error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-3.5 text-xs text-red-600 dark:text-red-400">
              <div className="flex items-center gap-2 font-bold text-red-700 dark:text-red-300">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>Lỗi trong quá trình huấn luyện mô hình</span>
              </div>
              <p className="mt-1 font-mono text-xs leading-relaxed break-words">
                {model.error}
              </p>
            </div>
          )}

          {showOverview && (
            <>
              {/* Section 1: CV / Best Trial Scores — wide compact grid */}
              <div>
                <div className="mb-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Gauge className="h-4 w-4 text-automl-blue dark:text-cyan-400" />
                    <h3 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                      Kết quả đo lường & Điểm số (Best Scores)
                    </h3>
                  </div>
                  <span className="text-[11px] font-bold text-[var(--automl-data-muted)]">
                    Tối ưu theo:{" "}
                    <span className="text-automl-blue dark:text-cyan-300 uppercase">
                      {metricSort}
                    </span>
                  </span>
                </div>

                {scoreEntries.length > 0 ? (
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-4 xl:grid-cols-8">
                    {scoreEntries.map(([sKey, sVal]) => {
                      const isPrimary = sKey.toLowerCase() === metricSort.toLowerCase();
                      const goal = getMetricDirection(sKey, metricsConfig);

                      return (
                        <div
                          key={sKey}
                          className={cn(
                            "rounded-xl border px-3 py-2.5 transition-all",
                            isPrimary
                              ? "border-blue-500/40 bg-blue-50/50 dark:border-cyan-500/40 dark:bg-cyan-950/30 shadow-xs"
                              : "border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)]",
                          )}
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span
                              className="truncate font-mono text-[11px] font-black uppercase text-[var(--automl-data-muted)]"
                              title={sKey}
                            >
                              {sKey}
                            </span>
                            {isPrimary && (
                              <Badge className="shrink-0 bg-blue-600 text-white dark:bg-cyan-500 dark:text-slate-950 text-[9px] py-0 px-1 font-bold">
                                Chính
                              </Badge>
                            )}
                          </div>
                          <p className="mt-1 font-mono text-base font-extrabold tabular-nums text-[var(--automl-data-text)]">
                            {formatPipelineValue(sVal)}
                          </p>
                          <p className="mt-0.5 text-[10px] font-medium text-[var(--automl-data-muted)]">
                            {goal === "minimize" ? "Tối thiểu" : "Tối đa"}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-3.5 text-center text-xs font-semibold text-[var(--automl-data-muted)]">
                    Chưa có dữ liệu điểm số (—)
                  </div>
                )}
              </div>

              {/* Section 1.5: Holdout Evaluation Scores (v2.0.0) */}
              {holdoutEntries.length > 0 && (
                <div>
                  <div className="mb-2.5 flex items-center gap-2">
                    <ShieldCheck className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
                    <h3 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                      Điểm đánh giá tập Holdout (Holdout Scores)
                    </h3>
                  </div>
                  <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-4 xl:grid-cols-8">
                    {holdoutEntries.map(([hKey, hVal]) => (
                      <div
                        key={hKey}
                        className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 px-3 py-2"
                      >
                        <span
                          className="block truncate font-mono text-[11px] font-black uppercase text-emerald-700 dark:text-emerald-300"
                          title={hKey}
                        >
                          {hKey}
                        </span>
                        <p className="mt-0.5 font-mono text-base font-extrabold tabular-nums text-[var(--automl-data-text)]">
                          {formatPipelineValue(hVal)}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Section 2: Best Hyperparameters — wide multi-column grid */}
              <div>
                <div className="mb-2.5 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sliders className="h-4 w-4 text-automl-blue dark:text-cyan-400" />
                    <h3 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                      Tham số tối ưu (Best Hyperparameters)
                    </h3>
                  </div>
                  {paramEntries.length > 0 && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      className="h-7 text-xs font-bold rounded-lg border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)]"
                      onClick={handleCopyParams}
                    >
                      {copied ? (
                        <>
                          <Check className="mr-1.5 h-3.5 w-3.5 text-emerald-500" /> Đã sao chép
                        </>
                      ) : (
                        <>
                          <Copy className="mr-1.5 h-3.5 w-3.5" /> Sao chép JSON
                        </>
                      )}
                    </Button>
                  )}
                </div>

                {paramEntries.length > 0 ? (
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                    {paramEntries.map(([pKey, pVal]) => (
                      <div
                        key={pKey}
                        className="flex items-center justify-between gap-3 rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-3 py-2 text-xs shadow-2xs"
                      >
                        <div className="min-w-0">
                          <p className="font-mono text-xs font-bold text-slate-700 dark:text-slate-300 break-all">
                            {pKey}
                          </p>
                          <span className="text-[10px] font-semibold text-[var(--automl-data-muted)] uppercase">
                            {typeof pVal}
                          </span>
                        </div>

                        <span className="shrink-0 rounded-lg bg-blue-50 px-2 py-1 font-mono text-xs font-extrabold text-automl-blue dark:bg-cyan-950/80 dark:text-cyan-300 border border-blue-200/60 dark:border-cyan-800/50">
                          {formatPipelineValue(pVal)}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-3.5 text-center text-xs font-semibold text-[var(--automl-data-muted)]">
                    Chưa có tham số tối ưu (—)
                  </div>
                )}
              </div>
            </>
          )}

          {/* Section 3: Trials History (v2.0.0) — wide, spacious, zero double-scroll */}
          {showTrials && (
            <div>
              <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <FlaskConical className="h-4 w-4 text-automl-blue dark:text-cyan-400" />
                  <h3 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                    Lịch sử tối ưu hóa (Trials)
                  </h3>
                </div>
                <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-bold">
                  {totalTrials !== null && (
                    <span className="rounded-lg border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-2.5 py-0.5">
                      Tổng: {totalTrials}
                    </span>
                  )}
                  {typeof model.best_trial === "number" && (
                    <span className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-2.5 py-0.5 text-amber-700 dark:text-amber-300">
                      Best trial: #{model.best_trial}
                    </span>
                  )}
                  {typeof prunedTrials === "number" && prunedTrials > 0 && (
                    <span className="rounded-lg border border-slate-300/60 bg-slate-100 px-2.5 py-0.5 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300">
                      Pruned: {prunedTrials}
                    </span>
                  )}
                </div>
              </div>

              {trials && trials.length > 0 ? (
                <div className="overflow-x-auto rounded-2xl border border-[var(--automl-data-card-border)]">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-[var(--automl-table-header-bg)] text-[10px] font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                      <tr>
                        <th className="px-3 py-2.5 whitespace-nowrap">Trial</th>
                        <th className="px-3 py-2.5 whitespace-nowrap">Trạng thái</th>
                        {trialMetricKeys.map((mKey) => {
                          const isPrimary = mKey.toLowerCase() === metricSort.toLowerCase();
                          return (
                            <th
                              key={mKey}
                              className={cn(
                                "px-2.5 py-2.5 font-mono whitespace-nowrap",
                                isPrimary && "text-automl-blue dark:text-cyan-300",
                              )}
                            >
                              {mKey}
                            </th>
                          );
                        })}
                        <th className="px-3 py-2.5 min-w-[260px]">Tham số</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[var(--automl-data-card-border)]">
                      {trials.map((trial, idx) => {
                        const trialIndex = trial.trial_id ?? trial.number ?? idx;
                        const isBestTrial =
                          typeof model.best_trial === "number" &&
                          (idx === model.best_trial || trialIndex === model.best_trial);
                        const trialScores = trial.scores ?? trial.cv_scores ?? {};
                        const trialParamEntries =
                          trial.params && typeof trial.params === "object"
                            ? Object.entries(trial.params)
                            : [];

                        return (
                          <tr
                            key={`trial-${idx}-${trialIndex}`}
                            className={cn(
                              "transition-colors hover:bg-slate-50/60 dark:hover:bg-white/5",
                              isBestTrial && "bg-amber-500/5 font-semibold",
                            )}
                          >
                            <td className="px-3 py-2.5 font-mono font-bold whitespace-nowrap">
                              #{trialIndex}
                              {isBestTrial && (
                                <span className="ml-1.5 rounded bg-amber-500/20 px-1.5 py-0.5 text-[9px] font-black text-amber-700 dark:text-amber-300">
                                  BEST
                                </span>
                              )}
                            </td>
                            <td className="px-3 py-2.5 whitespace-nowrap">
                              {renderTrialStatusBadge(trial.status)}
                            </td>
                            {trialMetricKeys.map((mKey) => {
                              const isPrimary = mKey.toLowerCase() === metricSort.toLowerCase();
                              return (
                                <td
                                  key={mKey}
                                  className={cn(
                                    "px-2.5 py-2.5 font-mono tabular-nums whitespace-nowrap",
                                    isPrimary && "font-extrabold text-automl-blue dark:text-cyan-300",
                                  )}
                                >
                                  {formatPipelineValue(trialScores?.[mKey])}
                                </td>
                              );
                            })}
                            <td className="px-3 py-2">
                              {trialParamEntries.length > 0 ? (
                                <div className="flex flex-wrap gap-1">
                                  {trialParamEntries.map(([pk, pv]) => (
                                    <span
                                      key={pk}
                                      className="inline-flex items-center gap-1 rounded-md border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-1.5 py-0.5 font-mono text-[11px]"
                                    >
                                      <span className="text-[var(--automl-data-muted)]">{pk}:</span>
                                      <span className="font-bold text-[var(--automl-data-text)]">
                                        {formatPipelineValue(pv)}
                                      </span>
                                    </span>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-[var(--automl-data-muted)]">—</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-3.5 text-center text-xs font-medium text-[var(--automl-data-muted)]">
                  Chi tiết mảng trials sẽ được tải đầy đủ từ snapshot cuối sau khi job hoàn tất.
                </div>
              )}
            </div>
          )}
        </div>

        {/* Sticky Footer */}
        <div className="shrink-0 flex justify-end border-t border-[var(--automl-data-card-border)] px-6 py-3">
          <Button
            type="button"
            className="rounded-xl font-bold bg-slate-800 text-white hover:bg-slate-900 dark:bg-slate-700 dark:hover:bg-slate-600"
            onClick={() => onOpenChange(false)}
          >
            Đóng
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
