"use client";

import { useState, type ReactNode } from "react";
import { useTranslations } from "next-intl";
import { Database, Loader2 } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/shared/components/ui/popover";
import { useGetDatasetsByUserIdQuery } from "@/core/api/datasetApi";
import { cn } from "@/shared/lib/utils";

/**
 * Chọn dataset trong kho của người dùng (GET /api/v1/datasets). Chọn xong thì
 * báo cho agent bằng một tin nhắn hiển thị - agent không có kênh "dataset đang
 * chọn" nào khác, và người dùng thấy rõ điều gì được gửi đi.
 */
export default function DatasetPicker({
  trigger,
  disabled,
  onPick,
}: {
  trigger: (open: boolean) => ReactNode;
  disabled?: boolean;
  onPick: (dataset: { id: string; name: string }) => void;
}) {
  const t = useTranslations("Agent.dataset");
  const [open, setOpen] = useState(false);
  // Khác "0" là danh sách dataset của chính người dùng (xem datasetApi).
  const query = useGetDatasetsByUserIdQuery("mine", { skip: !open });
  const datasets = query.data ?? [];

  return (
    <Popover open={open} onOpenChange={(next) => !disabled && setOpen(next)}>
      <PopoverTrigger asChild disabled={disabled}>
        {trigger(open)}
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72 p-0">
        <p className="border-b border-automl-line px-3 py-2 text-xs font-semibold text-automl-ink">{t("pickTitle")}</p>
        <div className="max-h-64 overflow-y-auto p-1">
          {query.isFetching && !datasets.length ? (
            <p className="flex items-center gap-1.5 px-2 py-3 text-xs text-automl-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> {t("pickLoading")}
            </p>
          ) : query.isError ? (
            <p className="px-2 py-3 text-xs text-agent-error">{t("pickError")}</p>
          ) : !datasets.length ? (
            <p className="px-2 py-3 text-xs text-automl-muted">{t("pickEmpty")}</p>
          ) : (
            <ul>
              {datasets.map((dataset) => (
                <li key={dataset._id}>
                  <button
                    type="button"
                    onClick={() => {
                      setOpen(false);
                      onPick({ id: dataset._id, name: dataset.dataName });
                    }}
                    className={cn(
                      "agent-focus flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm text-automl-ink transition-colors",
                      "hover:bg-automl-surface-muted",
                    )}
                  >
                    <Database className="h-3.5 w-3.5 shrink-0 text-automl-muted" aria-hidden />
                    <span className="min-w-0 flex-1 truncate">{dataset.dataName}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
