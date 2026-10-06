"use client";

import React from "react";
import { formatPipelineValue } from "@/features/training/utils/pipelineGraphBuilder";
import { Button } from "@/shared/components/ui/button";
import { Eye } from "lucide-react";

interface ModelParamsChipsProps {
  params?: Record<string, unknown> | null;
  onViewDetails?: () => void;
  maxItems?: number;
}

export const ModelParamsChips: React.FC<ModelParamsChipsProps> = ({
  params,
  onViewDetails,
  maxItems = 3,
}) => {
  if (!params || typeof params !== "object" || Object.keys(params).length === 0) {
    return <span className="text-xs font-semibold text-[var(--automl-data-muted)]">—</span>;
  }

  const entries = Object.entries(params);
  const visibleEntries = entries.slice(0, maxItems);
  const remainingCount = entries.length - maxItems;

  return (
    <div className="flex flex-wrap items-center gap-1.5 py-0.5">
      {visibleEntries.map(([key, value]) => (
        <span
          key={key}
          className="inline-flex items-center gap-1 rounded-lg border border-[var(--automl-data-card-border)] bg-[var(--automl-table-header-bg)] px-2 py-0.5 font-mono text-[11px] shadow-2xs"
          title={`${key}: ${formatPipelineValue(value)}`}
        >
          <span className="font-semibold text-[var(--automl-data-muted)]">{key}:</span>
          <span className="font-bold text-[var(--automl-data-text)]">
            {formatPipelineValue(value)}
          </span>
        </span>
      ))}

      {remainingCount > 0 && (
        <button
          type="button"
          onClick={onViewDetails}
          className="inline-flex items-center rounded-lg border border-blue-200/80 bg-blue-50/80 px-2 py-0.5 text-[11px] font-bold text-automl-blue hover:bg-blue-100 dark:border-cyan-800/60 dark:bg-cyan-950/60 dark:text-cyan-300 dark:hover:bg-cyan-900/60 transition-colors cursor-pointer"
        >
          +{remainingCount} tham số
        </button>
      )}

      {onViewDetails && (
        <Button
          type="button"
          size="sm"
          variant="ghost"
          className="h-6 w-6 p-0 rounded-md text-[var(--automl-data-muted)] hover:text-automl-blue dark:hover:text-cyan-300"
          onClick={onViewDetails}
          title="Xem đầy đủ tham số & kết quả"
        >
          <Eye className="h-3.5 w-3.5" />
        </Button>
      )}
    </div>
  );
};
