"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Bot, Cable, CheckCircle2, CirclePlus, Loader2, Search, ShieldCheck, XCircle } from "lucide-react";
import { Card, CardContent } from "@/shared/components/ui/card";
import { Button } from "@/shared/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/shared/components/ui/table";
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
import AppLoading from "@/shared/components/common/AppLoading";
import RowActionMenu from "@/shared/components/common/RowActionMenu";
import {
  DataWorkspaceControls,
  DataWorkspaceHeader,
  workspaceInputClass,
} from "@/shared/components/common/DataWorkspace";
import { useToast } from "@/shared/hooks/use-toast";
import { getApiErrorMessage } from "@/core/api/baseApi";
import {
  type DatabaseConnection,
  useDeleteDatabaseConnectionMutation,
  useGetDatabaseConnectionsQuery,
  useTestDatabaseConnectionMutation,
} from "@/core/api/databaseConnectionApi";
import { CONNECTION_TYPES, isConnectionType } from "../lib/connectionForm";
import ConnectionFormDialog, { type ConnectionSavedEvent } from "./ConnectionFormDialog";
import ConnectionExplorerDialog from "./ConnectionExplorerDialog";

type TestStatus =
  | { state: "testing" }
  | { state: "ok"; tableCount: number }
  | { state: "failed"; message: string };

const typeLabel = (dbType: string) => (isConnectionType(dbType) ? CONNECTION_TYPES[dbType].label : dbType);

const successToast = "bg-green-100 text-green-800 border border-green-300";

export default function DatabaseConnectionsPage() {
  const t = useTranslations("DatabaseConnections");
  const common = useTranslations("Common");
  const locale = useLocale();
  const router = useRouter();
  const { toast } = useToast();

  const { data: connections = [], isLoading, error, refetch } = useGetDatabaseConnectionsQuery();
  const [testConnection] = useTestDatabaseConnectionMutation();
  const [deleteConnection, { isLoading: deleting }] = useDeleteDatabaseConnectionMutation();

  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<DatabaseConnection | null>(null);
  const [exploring, setExploring] = useState<DatabaseConnection | null>(null);
  const [toDelete, setToDelete] = useState<DatabaseConnection | null>(null);
  const [statuses, setStatuses] = useState<Record<string, TestStatus>>({});
  // Số thứ tự lượt kiểm tra theo kết nối: lượt cũ (vd host cũ đang timeout) về sau không được ghi đè
  // kết quả của lượt mới (sau khi sửa kết nối).
  const testSeq = useRef<Record<string, number>>({});

  const dateFormatter = useMemo(
    () =>
      new Intl.DateTimeFormat(locale === "vi" ? "vi-VN" : "en-US", {
        dateStyle: "short",
        timeStyle: "short",
      }),
    [locale],
  );

  const filtered = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return connections;
    return connections.filter((c) =>
      [c.name, c.description, c.database_label, typeLabel(c.db_type)]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(keyword),
    );
  }, [connections, search]);

  const askAgent = (prompt?: string) => {
    router.push(prompt ? `/agent?prompt=${encodeURIComponent(prompt)}` : "/agent");
  };

  /** Kiểm tra kết nối; `context` chọn lời báo (vừa tạo / vừa sửa / bấm tay). */
  const runTest = async (connection: DatabaseConnection, context: "created" | "updated" | "manual" = "manual") => {
    const seq = (testSeq.current[connection.id] ?? 0) + 1;
    testSeq.current[connection.id] = seq;
    const isLatest = () => testSeq.current[connection.id] === seq;
    setStatuses((prev) => ({ ...prev, [connection.id]: { state: "testing" } }));
    const savedTitle =
      context === "created"
        ? t("toast.created", { name: connection.name })
        : context === "updated"
          ? t("toast.updated", { name: connection.name })
          : null;
    try {
      const result = await testConnection(connection.id).unwrap();
      if (!isLatest()) return;
      setStatuses((prev) => ({ ...prev, [connection.id]: { state: "ok", tableCount: result.table_count } }));
      toast({
        title: savedTitle ?? t("toast.testOk", { name: connection.name, count: result.table_count }),
        description:
          context === "created"
            ? t("toast.createdTestOk", { count: result.table_count })
            : context === "updated"
              ? t("status.ok", { count: result.table_count })
              : undefined,
        className: successToast,
        duration: 4000,
      });
    } catch (err) {
      if (!isLatest()) return;
      const message = getApiErrorMessage(err, t("toast.unknownError"));
      setStatuses((prev) => ({ ...prev, [connection.id]: { state: "failed", message } }));
      toast({
        title: savedTitle ?? t("toast.testFailed", { name: connection.name }),
        description: savedTitle ? `${t("toast.createdTestFailed")} ${message}` : message,
        variant: "destructive",
        duration: 8000,
      });
    }
  };

  const handleSaved = ({ connection, created, connectionChanged }: ConnectionSavedEvent) => {
    if (created || connectionChanged) {
      // Kết nối đã được lưu: kiểm tra là bước riêng, thất bại thì chỉ cần sửa / kiểm tra lại, không tạo trùng.
      void runTest(connection, created ? "created" : "updated");
      return;
    }
    toast({ title: t("toast.updated", { name: connection.name }), className: successToast, duration: 3000 });
  };

  const confirmDelete = async () => {
    if (!toDelete) return;
    const target = toDelete;
    try {
      await deleteConnection(target.id).unwrap();
      delete testSeq.current[target.id];
      setStatuses((prev) => {
        const next = { ...prev };
        delete next[target.id];
        return next;
      });
      toast({ title: t("toast.deleted"), className: successToast, duration: 3000 });
    } catch (err) {
      toast({
        title: t("toast.deleteFailed"),
        description: getApiErrorMessage(err, t("toast.unknownError")),
        variant: "destructive",
        duration: 5000,
      });
    } finally {
      setToDelete(null);
    }
  };

  const openCreate = () => {
    setEditing(null);
    setFormOpen(true);
  };

  const statusChip = (connection: DatabaseConnection) => {
    const status = statuses[connection.id];
    if (!status) {
      return <span className="text-xs font-semibold text-[var(--automl-data-muted)]">{t("status.unknown")}</span>;
    }
    if (status.state === "testing") {
      return (
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-[var(--automl-data-muted)]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> {t("status.testing")}
        </span>
      );
    }
    if (status.state === "ok") {
      return (
        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:text-emerald-400">
          <CheckCircle2 className="h-3.5 w-3.5" /> {t("status.ok", { count: status.tableCount })}
        </span>
      );
    }
    return (
      <span
        className="inline-flex max-w-[16rem] items-center gap-1 rounded-full bg-red-500/10 px-2.5 py-0.5 text-xs font-bold text-red-700 dark:text-red-400"
        title={status.message}
      >
        <XCircle className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">{t("status.failed")}</span>
      </span>
    );
  };

  return (
    <>
      <div className="space-y-6">
        <DataWorkspaceHeader eyebrow={t("title")} title={t("title")} subtitle={t("subtitle")}>
          <Button
            variant="outline"
            className="h-11 gap-2 rounded-2xl border border-slate-200 bg-white px-4 font-bold text-slate-700 shadow-sm hover:bg-slate-50 dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/15"
            onClick={() => askAgent()}
          >
            <Bot className="h-4 w-4" /> {t("openAgent")}
          </Button>
          <Button className="automl-action-primary h-11 gap-2 rounded-2xl px-4 font-bold shadow-sm" onClick={openCreate}>
            <CirclePlus className="h-4 w-4" /> {t("add")}
          </Button>
        </DataWorkspaceHeader>

        <section className="rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#0b121e]">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-automl-blue" />
            <h2 className="text-sm font-black text-automl-ink dark:text-white">{t("howItWorks.title")}</h2>
          </div>
          <ol className="mt-3 grid gap-3 md:grid-cols-3">
            {(["step1", "step2", "step3"] as const).map((step, index) => (
              <li key={step} className="flex gap-3 rounded-2xl bg-slate-50 p-3 text-sm text-slate-600 dark:bg-white/5 dark:text-white/70">
                <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-automl-blue-soft text-xs font-black text-automl-blue">
                  {index + 1}
                </span>
                <span>{t(`howItWorks.${step}`)}</span>
              </li>
            ))}
          </ol>
        </section>

        <DataWorkspaceControls summary={t("summary", { shown: filtered.length, total: connections.length })}>
          <label className="relative min-w-0 sm:w-80">
            <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder={t("searchPlaceholder")}
              aria-label={t("searchPlaceholder")}
              className={`${workspaceInputClass} w-full pl-11`}
            />
          </label>
        </DataWorkspaceControls>

        {isLoading ? (
          <Card className="automl-data-card w-full">
            <CardContent className="pt-8">
              <AppLoading />
            </CardContent>
          </Card>
        ) : error ? (
          <Card className="automl-data-card w-full">
            <CardContent className="space-y-3 pt-8">
              <div className="automl-state-panel">
                <p className="font-bold">{t("loadFailed")}</p>
                <p className="mt-1 break-words text-sm">{getApiErrorMessage(error, t("toast.unknownError"))}</p>
              </div>
              <Button variant="outline" onClick={() => refetch()}>
                {t("retry")}
              </Button>
            </CardContent>
          </Card>
        ) : connections.length === 0 ? (
          <Card className="automl-data-card w-full">
            <CardContent className="flex flex-col items-center gap-3 py-12 text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-automl-blue-soft text-automl-blue">
                <Cable className="h-6 w-6" />
              </span>
              <p className="text-lg font-black">{t("empty.title")}</p>
              <p className="max-w-xl text-sm text-[var(--automl-data-muted)]">{t("empty.body")}</p>
              <Button className="automl-action-primary mt-2 gap-2" onClick={openCreate}>
                <CirclePlus className="h-4 w-4" /> {t("add")}
              </Button>
            </CardContent>
          </Card>
        ) : filtered.length === 0 ? (
          <Card className="automl-data-card w-full">
            <CardContent className="pt-8">
              <div className="automl-state-panel">{t("noMatch")}</div>
            </CardContent>
          </Card>
        ) : (
          <Card className="automl-data-card w-full">
            <CardContent className="automl-table-wrap pt-5">
              <Table className="automl-data-table">
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("table.name")}</TableHead>
                    <TableHead>{t("table.type")}</TableHead>
                    <TableHead>{t("table.database")}</TableHead>
                    <TableHead>{t("table.status")}</TableHead>
                    <TableHead>{t("table.updatedAt")}</TableHead>
                    <TableHead className="text-center">{common("actions")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((connection) => (
                    <TableRow key={connection.id}>
                      <TableCell className="font-bold text-[var(--automl-data-text)]">
                        <div className="flex items-center gap-2.5">
                          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-automl-blue-soft text-[11px] font-black text-automl-blue">
                            {(connection.name || "DB").slice(0, 2).toUpperCase()}
                          </span>
                          <span className="min-w-0">
                            <span className="block max-w-[16rem] truncate" title={connection.name}>
                              {connection.name}
                            </span>
                            {connection.description && (
                              <span
                                className="block max-w-[16rem] truncate text-xs font-medium text-[var(--automl-data-muted)]"
                                title={connection.description}
                              >
                                {connection.description}
                              </span>
                            )}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <span className="automl-data-chip automl-data-chip-secondary">{typeLabel(connection.db_type)}</span>
                      </TableCell>
                      <TableCell className="font-mono text-sm">
                        <span className="block max-w-[14rem] truncate" title={connection.database_label}>
                          {connection.database_label}
                        </span>
                      </TableCell>
                      <TableCell>{statusChip(connection)}</TableCell>
                      <TableCell className="whitespace-nowrap">
                        {dateFormatter.format(new Date(connection.updated_at * 1000))}
                      </TableCell>
                      <TableCell className="text-center">
                        <div className="flex justify-center">
                          <RowActionMenu
                            label={t("actions.open", { name: connection.name })}
                            items={[
                              {
                                label: t("actions.test"),
                                disabled: statuses[connection.id]?.state === "testing",
                                onClick: () => void runTest(connection),
                              },
                              { label: t("actions.browse"), onClick: () => setExploring(connection) },
                              {
                                label: t("actions.askAgent"),
                                onClick: () => askAgent(t("agentPrompt.tables", { name: connection.name })),
                              },
                              {
                                label: t("actions.edit"),
                                onClick: () => {
                                  setEditing(connection);
                                  setFormOpen(true);
                                },
                              },
                              { label: t("actions.delete"), destructive: true, onClick: () => setToDelete(connection) },
                            ]}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>

      <ConnectionFormDialog
        open={formOpen}
        onOpenChange={(open) => {
          setFormOpen(open);
          if (!open) setEditing(null);
        }}
        connection={editing}
        onSaved={handleSaved}
      />

      <ConnectionExplorerDialog
        open={!!exploring}
        onOpenChange={(open) => !open && setExploring(null)}
        connection={exploring}
        onAskAgent={askAgent}
      />

      <AlertDialog open={!!toDelete} onOpenChange={(open) => !open && !deleting && setToDelete(null)}>
        <AlertDialogContent className="automl-dialog-content max-w-md">
          <AlertDialogHeader className="automl-dialog-header">
            <AlertDialogTitle className="automl-dialog-title">{t("deleteDialog.title")}</AlertDialogTitle>
            <AlertDialogDescription className="automl-dialog-description break-words">
              {t("deleteDialog.description", { name: toDelete?.name ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="automl-dialog-footer">
            <AlertDialogCancel className="automl-dialog-button-muted mt-0" disabled={deleting}>
              {t("deleteDialog.cancel")}
            </AlertDialogCancel>
            <AlertDialogAction
              className="automl-action-danger"
              disabled={deleting}
              onClick={(event) => {
                event.preventDefault();
                void confirmDelete();
              }}
            >
              {t("deleteDialog.confirm")}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
