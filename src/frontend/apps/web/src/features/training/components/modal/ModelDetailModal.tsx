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
  Gauge,
  Sliders,
  XCircle,
} from "lucide-react";
import toTitleLabel from "@/shared/utils/toTitleLable";
import { formatPipelineValue } from "@/features/training/utils/pipelineGraphBuilder";
import { cn } from "@/shared/lib/utils";

export interface ModelDetailData {
  model_name: string;
  status?: string | number | null;
  error?: string | null;
  scores?: Record<string, number | null> | null;
  best_params?: Record<string, unknown> | null;
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

export const ModelDetailModal: React.FC<ModelDetailModalProps> = ({
  open,
  onOpenChange,
  model,
  isBestModel = false,
  metricSort = "r2",
  metricsConfig = {},
}) => {
  const [copied, setCopied] = useState(false);

  if (!model) return null;

  const handleCopyParams = () => {
    if (!model.best_params) return;
    navigator.clipboard.writeText(JSON.stringify(model.best_params, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const paramEntries = model.best_params && typeof model.best_params === "object"
    ? Object.entries(model.best_params)
    : [];

  const scoreEntries = model.scores && typeof model.scores === "object"
    ? Object.entries(model.scores)
    : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto rounded-[24px] border border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] p-6 text-[var(--automl-data-text)] shadow-2xl">
        <DialogHeader className="border-b border-[var(--automl-data-card-border)] pb-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-500/10 text-automl-blue dark:bg-cyan-500/10 dark:text-cyan-400">
                <Cpu className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <DialogTitle className="text-xl font-extrabold tracking-tight text-[var(--automl-data-text)]">
                    {model.model_name}
                  </DialogTitle>
                  {isBestModel && (
                    <Badge className="bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30 text-xs py-0.5 px-2">
                      <Award className="mr-1 h-3.5 w-3.5" /> Best Model 🥇
                    </Badge>
                  )}
                </div>
                <p className="mt-0.5 text-xs font-semibold text-[var(--automl-data-muted)]">
                  {model.rank !== undefined ? `Hạng ${model.rank} trong bảng xếp hạng · ` : ""}
                  Chi tiết cấu hình và kết quả huấn luyện
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {model.status === "done" ? (
                <Badge variant="outline" className="automl-status-success rounded-full px-3 py-1 text-xs font-bold">
                  <CheckCircle2 className="mr-1 h-3.5 w-3.5" /> Hoàn tất
                </Badge>
              ) : model.status === "running" ? (
                <Badge variant="secondary" className="automl-status-warning rounded-full px-3 py-1 text-xs font-bold">
                  <Clock3 className="mr-1 h-3.5 w-3.5 animate-spin" /> Đang chạy
                </Badge>
              ) : model.status === "failed" ? (
                <Badge variant="default" className="automl-status-error rounded-full px-3 py-1 text-xs font-bold">
                  <XCircle className="mr-1 h-3.5 w-3.5" /> Lỗi
                </Badge>
              ) : (
                <Badge variant="outline" className="rounded-full px-3 py-1 text-xs font-bold text-slate-500">
                  Đang chờ
                </Badge>
              )}
            </div>
          </div>
        </DialogHeader>

        <div className="mt-4 space-y-6">
          {/* Lỗi nếu có */}
          {model.error && (
            <div className="rounded-2xl border border-red-500/30 bg-red-500/10 p-4 text-xs text-red-600 dark:text-red-400">
              <div className="flex items-center gap-2 font-bold text-red-700 dark:text-red-300">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                <span>Lỗi trong quá trình huấn luyện mô hình</span>
              </div>
              <p className="mt-1.5 font-mono text-xs leading-relaxed break-words">
                {model.error}
              </p>
            </div>
          )}

          {/* Section 1: Điểm số đo lường (Evaluation Metrics) */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Gauge className="h-4 w-4 text-automl-blue dark:text-cyan-400" />
                <h3 className="text-xs font-black uppercase tracking-wider text-[var(--automl-data-muted)]">
                  Kết quả đo lường & Điểm số (Scores)
                </h3>
              </div>
              <span className="text-[11px] font-bold text-[var(--automl-data-muted)]">
                Tối ưu theo: <span className="text-automl-blue dark:text-cyan-300 uppercase">{metricSort}</span>
              </span>
            </div>

            {scoreEntries.length > 0 ? (
              <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {scoreEntries.map(([sKey, sVal]) => {
                  const isPrimary = sKey.toLowerCase() === metricSort.toLowerCase();
                  const goal = metricsConfig[sKey] || (sKey === "r2" ? "maximize" : "minimize");

                  return (
                    <div
                      key={sKey}
                      className={cn(
                        "rounded-2xl border p-3.5 transition-all",
                        isPrimary
                          ? "border-blue-500/40 bg-blue-50/50 dark:border-cyan-500/40 dark:bg-cyan-950/30 shadow-xs"
                          : "border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)]",
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-xs font-black uppercase text-[var(--automl-data-muted)]">
                          {sKey}
                        </span>
                        {isPrimary && (
                          <Badge className="bg-blue-600 text-white dark:bg-cyan-500 dark:text-slate-950 text-[9px] py-0 px-1 font-bold">
                            Chính
                          </Badge>
                        )}
                      </div>
                      <p className="mt-1.5 font-mono text-lg font-extrabold text-[var(--automl-data-text)]">
                        {formatPipelineValue(sVal)}
                      </p>
                      <p className="mt-0.5 text-[10px] font-medium text-[var(--automl-data-muted)]">
                        {goal === "minimize" ? "Mục tiêu: Tối thiểu" : "Mục tiêu: Tối đa"}
                      </p>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4 text-center text-xs font-semibold text-[var(--automl-data-muted)]">
                Chưa có dữ liệu điểm số (—)
              </div>
            )}
          </div>

          {/* Section 2: Tham số tối ưu (Hyperparameters) */}
          <div>
            <div className="mb-3 flex items-center justify-between">
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
                      <Copy className="mr-1.5 h-3.5 w-3.5" /> Sao chép tham số
                    </>
                  )}
                </Button>
              )}
            </div>

            {paramEntries.length > 0 ? (
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {paramEntries.map(([pKey, pVal]) => (
                  <div
                    key={pKey}
                    className="flex items-center justify-between gap-3 rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-3.5 py-2.5 text-xs shadow-2xs"
                  >
                    <div className="min-w-0">
                      <p className="font-mono text-xs font-bold text-slate-700 dark:text-slate-300">
                        {pKey}
                      </p>
                      <span className="text-[10px] font-semibold text-[var(--automl-data-muted)] uppercase">
                        {typeof pVal}
                      </span>
                    </div>

                    <div className="text-right">
                      <span className="rounded-lg bg-blue-50 px-2 py-1 font-mono text-xs font-extrabold text-automl-blue dark:bg-cyan-950/80 dark:text-cyan-300 border border-blue-200/60 dark:border-cyan-800/50">
                        {formatPipelineValue(pVal)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] p-4 text-center text-xs font-semibold text-[var(--automl-data-muted)]">
                Chưa có tham số tối ưu (—)
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 flex justify-end border-t border-[var(--automl-data-card-border)] pt-4">
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
