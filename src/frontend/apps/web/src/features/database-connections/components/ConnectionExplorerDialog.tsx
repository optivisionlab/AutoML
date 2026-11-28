"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslations } from "next-intl";
import { AlertCircle, Bot, Loader2, Search, Table2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/components/ui/dialog";
import { Button } from "@/shared/components/ui/button";
import AppLoading from "@/shared/components/common/AppLoading";
import { cn } from "@/shared/lib/utils";
import { getApiErrorMessage } from "@/core/api/baseApi";
import {
  type DatabaseConnection,
  useDescribeDatabaseTableMutation,
  useGetDatabaseConnectionTablesQuery,
} from "@/core/api/databaseConnectionApi";
import { columnLabel, formatCell } from "../lib/connectionForm";

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connection: DatabaseConnection | null;
  /** Mở Agent với câu hỏi điền sẵn (người dùng tự bấm gửi). */
  onAskAgent: (prompt: string) => void;
};

/**
 * Xem bảng của một kết nối (chỉ đọc): danh sách bảng -> cột + vài dòng mẫu. Mọi dữ liệu từ database
 * được hiển thị dạng văn bản (React escape), không render HTML.
 */
export default function ConnectionExplorerDialog({ open, onOpenChange, connection, onAskAgent }: Props) {
  const t = useTranslations("DatabaseConnections");
  const [filter, setFilter] = useState("");
  const [selected, setSelected] = useState<string | null>(null);

  const connectionId = connection?.id ?? "";
  const {
    data: tables = [],
    isFetching: tablesLoading,
    error: tablesError,
    refetch: refetchTables,
  } = useGetDatabaseConnectionTablesQuery(connectionId, {
    skip: !open || !connectionId,
    refetchOnMountOrArgChange: true,
  });
  const [describe, describeState] = useDescribeDatabaseTableMutation();
  // `reset` của RTK đổi tham chiếu sau MỖI lần gọi describe: không đưa vào deps (effect sẽ chạy lại
  // ngay sau khi bấm bảng và xoá lựa chọn). Chỉ dọn khi mở / đổi kết nối, dùng reset mới nhất qua ref.
  const resetDescribeRef = useRef(describeState.reset);
  resetDescribeRef.current = describeState.reset;
  useEffect(() => {
    setFilter("");
    setSelected(null);
    resetDescribeRef.current();
  }, [open, connectionId]);

  const visibleTables = useMemo(() => {
    const keyword = filter.trim().toLowerCase();
    return keyword ? tables.filter((tbl) => tbl.name.toLowerCase().includes(keyword)) : tables;
  }, [tables, filter]);

  const pickTable = (table: string) => {
    if (!connectionId || table === selected) return;
    setSelected(table);
    // Hook chỉ giữ kết quả của lần gọi MỚI NHẤT: bấm nhanh qua nhiều bảng không bị lẫn kết quả cũ.
    describe({ id: connectionId, table, sample_rows: 5 });
  };

  const description = describeState.data?.table === selected ? describeState.data : undefined;
  const columns = useMemo(() => description?.columns ?? [], [description]);
  const rows = useMemo(() => description?.rows ?? [], [description]);
  const rowKeys = useMemo(() => {
    const names = columns.map((c) => columnLabel(c).name);
    return names.length > 0 ? names : Object.keys(rows[0] ?? {});
  }, [columns, rows]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="automl-dialog-content flex max-h-[calc(100dvh-2rem)] max-w-5xl flex-col gap-0">
        <DialogHeader className="automl-dialog-header shrink-0">
          <div className="automl-dialog-kicker">
            <Table2 className="h-5 w-5" />
          </div>
          <DialogTitle className="automl-dialog-title mt-2 break-words">
            {t("explorer.title", { name: connection?.name ?? "" })}
          </DialogTitle>
          <DialogDescription className="automl-dialog-description">
            {connection?.database_label} · {t("explorer.description")}
          </DialogDescription>
        </DialogHeader>

        <div className="automl-dialog-body grid min-h-0 flex-1 gap-4 overflow-y-auto md:grid-cols-[minmax(0,15rem)_minmax(0,1fr)] md:grid-rows-[minmax(0,1fr)] md:overflow-hidden">
          {/* Danh sách bảng */}
          <div className="flex min-h-0 flex-col gap-2">
            <label className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                placeholder={t("explorer.filter")}
                aria-label={t("explorer.filter")}
                className="automl-dialog-input h-10 w-full pl-9"
              />
            </label>
            <p className="text-xs font-semibold text-[var(--automl-data-muted)]">
              {t("explorer.tableCount", { count: tables.length })}
            </p>
            <div className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-[var(--automl-data-card-border)] max-md:max-h-48">
              {tablesLoading ? (
                <div className="p-4">
                  <AppLoading />
                </div>
              ) : tablesError ? (
                <div className="space-y-2 p-3 text-sm text-red-600 dark:text-red-400">
                  <p className="font-bold">{t("explorer.loadFailed")}</p>
                  <p className="break-words text-xs">{getApiErrorMessage(tablesError, "")}</p>
                  <Button type="button" size="sm" variant="outline" onClick={() => refetchTables()}>
                    {t("retry")}
                  </Button>
                </div>
              ) : tables.length === 0 ? (
                <p className="p-3 text-sm text-[var(--automl-data-muted)]">{t("explorer.noTables")}</p>
              ) : (
                <ul className="p-1">
                  {visibleTables.map((tbl) => (
                    <li key={tbl.name}>
                      <button
                        type="button"
                        onClick={() => pickTable(tbl.name)}
                        aria-current={selected === tbl.name}
                        className={cn(
                          "flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm font-semibold transition",
                          selected === tbl.name
                            ? "bg-automl-blue-soft text-automl-blue"
                            : "hover:bg-[var(--automl-table-row-hover)]",
                        )}
                      >
                        <Table2 className="h-3.5 w-3.5 shrink-0" />
                        <span className="min-w-0 truncate" title={tbl.name}>
                          {tbl.name}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>

          {/* Chi tiết bảng */}
          <div className="min-h-0 min-w-0 space-y-4 overflow-y-auto">
            {!selected ? (
              <div className="automl-state-panel">{t("explorer.pickTable")}</div>
            ) : describeState.isLoading ? (
              <div className="flex items-center gap-2 p-4 text-sm text-[var(--automl-data-muted)]">
                <Loader2 className="h-4 w-4 animate-spin" />
                {selected}
              </div>
            ) : describeState.error ? (
              <div
                role="alert"
                className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
              >
                <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                <div>
                  <p className="font-bold">{t("explorer.describeFailed")}</p>
                  <p className="break-words">{getApiErrorMessage(describeState.error, "")}</p>
                </div>
              </div>
            ) : description ? (
              <>
                <section className="space-y-2">
                  <h3 className="text-sm font-black">
                    {t("explorer.columns")} · <span className="font-mono">{description.table}</span>
                  </h3>
                  <div className="overflow-x-auto rounded-xl border border-[var(--automl-data-card-border)]">
                    <table className="w-full text-left text-sm">
                      <thead className="bg-[var(--automl-table-header-bg)] text-xs uppercase tracking-wide text-[var(--automl-data-muted)]">
                        <tr>
                          <th className="px-3 py-2">{t("explorer.columnName")}</th>
                          <th className="px-3 py-2">{t("explorer.columnType")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {columns.map((column, index) => {
                          const { name, type } = columnLabel(column);
                          return (
                            <tr key={`${name}-${index}`} className="border-t border-[var(--automl-data-card-border)]">
                              <td className="px-3 py-1.5 font-mono font-semibold">{name}</td>
                              <td className="px-3 py-1.5 font-mono text-[var(--automl-data-muted)]">{type}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                  {description.omitted_columns ? (
                    <p className="text-xs text-[var(--automl-data-muted)]">
                      {t("explorer.omitted", { count: description.omitted_columns })}
                    </p>
                  ) : null}
                </section>

                <section className="space-y-2">
                  <h3 className="text-sm font-black">{t("explorer.sampleRows")}</h3>
                  {rows.length === 0 ? (
                    <p className="text-sm text-[var(--automl-data-muted)]">{t("explorer.noRows")}</p>
                  ) : (
                    <div className="overflow-x-auto rounded-xl border border-[var(--automl-data-card-border)]">
                      <table className="w-full text-left text-xs">
                        <thead className="bg-[var(--automl-table-header-bg)] text-[var(--automl-data-muted)]">
                          <tr>
                            {rowKeys.map((key) => (
                              <th key={key} className="whitespace-nowrap px-3 py-2 font-mono">
                                {key}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {rows.map((row, index) => (
                            <tr key={index} className="border-t border-[var(--automl-data-card-border)]">
                              {rowKeys.map((key) => {
                                const value = row[key];
                                return (
                                  <td
                                    key={key}
                                    className={cn(
                                      "max-w-[16rem] truncate whitespace-nowrap px-3 py-1.5 font-mono",
                                      (value === null || value === undefined) && "italic text-[var(--automl-data-muted)]",
                                    )}
                                    title={formatCell(value, 1000)}
                                  >
                                    {formatCell(value)}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </section>
              </>
            ) : null}
          </div>
        </div>

        <DialogFooter className="automl-dialog-footer shrink-0">
          <Button type="button" variant="outline" className="automl-dialog-button-muted" onClick={() => onOpenChange(false)}>
            {t("explorer.close")}
          </Button>
          {connection && (
            <Button
              type="button"
              className="automl-action-primary gap-2"
              onClick={() =>
                onAskAgent(
                  selected
                    ? t("agentPrompt.table", { name: connection.name, table: selected })
                    : t("agentPrompt.tables", { name: connection.name }),
                )
              }
            >
              <Bot className="h-4 w-4" />
              {selected ? t("explorer.askAgent") : t("actions.askAgent")}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
