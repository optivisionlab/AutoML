"use client";

import React from "react";
import {
  Database,
  FileSpreadsheet,
  FileText,
  Image as ImageIcon,
  Zap,
} from "lucide-react";
import RowActionMenu from "@/shared/components/common/RowActionMenu";
import { Button } from "@/shared/components/ui/button";
import { Dataset } from "@/core/api/datasetApi";
import { cn } from "@/shared/lib/utils";

export interface DatasetCardProps {
  dataset: Dataset;
  focused?: boolean;
  flashing?: boolean;
  onSelect?: () => void;
  onTrain: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  trainLabel: string;
  editLabel?: string;
  deleteLabel?: string;
  openActionsLabel: string;
  formattedDate: string;
  formattedUpdate: string;
  descriptionText?: string;
}

const getDataTypeIcon = (type?: string) => {
  const normalized = (type || "").toLowerCase();
  if (
    normalized.includes("tabular") ||
    normalized.includes("table") ||
    normalized.includes("csv") ||
    normalized.includes("bảng")
  ) {
    return <FileSpreadsheet className="h-6 w-6 text-indigo-600 dark:text-indigo-400" />;
  }
  if (
    normalized.includes("image") ||
    normalized.includes("vision") ||
    normalized.includes("ảnh") ||
    normalized.includes("segment")
  ) {
    return <ImageIcon className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />;
  }
  if (
    normalized.includes("text") ||
    normalized.includes("nlp") ||
    normalized.includes("chữ") ||
    normalized.includes("doc")
  ) {
    return <FileText className="h-6 w-6 text-amber-600 dark:text-amber-400" />;
  }
  return <Database className="h-6 w-6 text-blue-600 dark:text-blue-400" />;
};

export default function DatasetCard({
  dataset,
  focused = false,
  flashing = false,
  onSelect,
  onTrain,
  onEdit,
  onDelete,
  trainLabel,
  editLabel = "Sửa",
  deleteLabel = "Xóa",
  openActionsLabel,
  formattedDate,
  formattedUpdate,
  descriptionText,
}: DatasetCardProps) {
  const initials = (dataset.dataName || "DS").slice(0, 2).toUpperCase();

  return (
    <div
      id={`dataset-card-${dataset._id}`}
      tabIndex={0}
      onClick={onSelect}
      onFocus={onSelect}
      className={cn(
        "group relative flex flex-col justify-between rounded-2xl border border-slate-200/90 bg-white p-5 shadow-xs transition-all duration-200 hover:border-slate-300 hover:shadow-md dark:border-white/10 dark:bg-[#0f172a]/60 outline-none",
        focused && "ring-2 ring-purple-500 shadow-md shadow-purple-500/10 dark:ring-purple-400",
        flashing && "automl-row-flash",
      )}
      data-focused={focused}
    >
      <div>
        {/* Hàng trên cùng: Icon + Tên + Badge kiểu dữ liệu */}
        <div className="flex items-start gap-3">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border border-slate-200/80 bg-slate-50/80 shadow-xs dark:border-white/10 dark:bg-white/5">
            {dataset.dataType ? (
              getDataTypeIcon(dataset.dataType)
            ) : (
              <span className="text-xs font-black tracking-wider text-slate-700 dark:text-slate-200">
                {initials}
              </span>
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h3
              className="truncate text-base font-bold text-slate-900 transition group-hover:text-purple-600 dark:text-white dark:group-hover:text-purple-400"
              title={dataset.dataName}
            >
              {dataset.dataName || "Bộ dữ liệu"}
            </h3>
            <p className="mt-0.5 truncate text-xs font-medium text-slate-500 dark:text-slate-400">
              {dataset.username || "HAutoML"}
            </p>
          </div>

          <div className="shrink-0">
            <span className="inline-flex items-center rounded-lg bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-600 dark:bg-white/10 dark:text-slate-300">
              {dataset.dataType || "General"}
            </span>
          </div>
        </div>

        {/* Nội dung mô tả & metadata */}
        <p className="mt-3.5 line-clamp-2 min-h-[2.5rem] text-xs leading-relaxed text-slate-600 dark:text-slate-400">
          {descriptionText ||
            `Tập dữ liệu ${dataset.dataType || ""} chuẩn hóa sẵn sàng cho pipeline tự động huấn luyện.`}
        </p>

        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] font-medium text-slate-400 dark:text-slate-500">
          <span>Cập nhật: {formattedUpdate}</span>
          <span>•</span>
          <span>Tạo: {formattedDate}</span>
        </div>
      </div>

      {/* Chân thẻ: Nút Huấn luyện & Menu tác vụ */}
      <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3 dark:border-white/5">
        <Button
          type="button"
          variant="outline"
          onClick={(e) => {
            e.stopPropagation();
            onTrain();
          }}
          className="flex-1 h-10 rounded-xl border border-purple-500/80 bg-white font-bold text-purple-600 hover:bg-purple-50 hover:border-purple-600 dark:bg-transparent dark:border-purple-400 dark:text-purple-300 dark:hover:bg-purple-950/30 gap-1.5 transition shadow-xs text-xs sm:text-sm"
        >
          <Zap className="h-4 w-4 fill-purple-500 text-purple-500" />
          <span>{trainLabel}</span>
        </Button>

        {onEdit && onDelete && (
          <div onClick={(e) => e.stopPropagation()}>
            <RowActionMenu
              label={openActionsLabel}
              items={[
                { label: trainLabel, onClick: onTrain },
                { label: editLabel, onClick: onEdit },
                { label: deleteLabel, destructive: true, onClick: onDelete },
              ]}
            />
          </div>
        )}
      </div>
    </div>
  );
}
