"use client";

import { DragEvent, useRef, useState } from "react";
import { signIn, useSession } from "next-auth/react";
import { useTranslations } from "next-intl";
import { Bot, PanelRight, PanelRightClose, SquarePen, UploadCloud } from "lucide-react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/shared/components/ui/sheet";
import { cn } from "@/shared/lib/utils";
import AppLoading from "@/shared/components/common/AppLoading";
import { useGetDatasetInfoQuery } from "@/core/api/datasetApi";
import { MAX_UPLOAD_MB } from "../lib/agentApi";
import { useAgentSession, type PendingUpload } from "../hooks/useAgentSession";
import { useActivityText } from "./AgentActivityTimeline";
import AgentWelcome from "./AgentWelcome";
import ConnectionStatus from "./ConnectionStatus";
import ContextPanel, { type PanelTab } from "./ContextPanel";
import ConversationThread from "./ConversationThread";
import PromptComposer, { pickFile, type ComposerError, type PromptComposerHandle } from "./PromptComposer";

/**
 * Trang Agent. Chỉ dựng khi đã đăng nhập: agent thao tác trên dữ liệu của chính
 * tài khoản đó.
 *
 * `key` theo id người dùng: đăng xuất rồi người khác đăng nhập trên cùng tab thì
 * trang được dựng lại từ đầu - không dùng tiếp session_id của người trước.
 */
export default function AgentWorkspace() {
  const t = useTranslations("Agent");
  const { data: session, status } = useSession();
  const user = session?.user;
  if (status === "loading") return <AppLoading variant="page" label={t("authLoading")} />;
  // Refresh token hết hạn: access_token trong session đã chết, mọi lời gọi agent sẽ 401.
  const expired = (session as { error?: string } | null)?.error === "RefreshAccessTokenError";
  if (!user?.access_token || expired) {
    return (
      <div className="flex flex-col items-center gap-3 py-20 text-center">
        <p className="text-sm text-automl-muted">{expired ? t("sessionExpired") : t("authRequired")}</p>
        <button type="button" onClick={() => signIn()} className="agent-focus rounded-xl bg-agent-primary px-4 py-2 text-sm font-semibold text-agent-primary-fg hover:bg-agent-primary/90">
          {t("signIn")}
        </button>
      </div>
    );
  }
  const userKey = String(user.id ?? user.email ?? "user");
  return <Workspace key={userKey} token={user.access_token} userKey={userKey} />;
}

const iconButton =
  "agent-focus inline-flex rounded-xl border border-automl-line bg-automl-surface p-2 text-automl-muted-strong transition-colors duration-200 hover:bg-automl-surface-muted";

function Workspace({ token, userKey }: { token: string; userKey: string }) {
  const t = useTranslations("Agent");
  const agent = useAgentSession(token, userKey);
  const [pending, setPending] = useState<PendingUpload | null>(null);
  const [composerError, setComposerError] = useState<ComposerError | null>(null);
  const [dragging, setDragging] = useState(false);
  const [panelOpen, setPanelOpen] = useState(true);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [tab, setTab] = useState<PanelTab>("overview");
  const [datasetRows, setDatasetRows] = useState<Record<string, number>>({});
  const composerRef = useRef<PromptComposerHandle>(null);
  const activityText = useActivityText(agent.liveTrace);
  const datasetInfo = useGetDatasetInfoQuery(agent.activeDataset?.id ?? "", { skip: !agent.activeDataset });

  const empty = agent.items.length === 0 && !agent.liveTrace;

  const pickDataset = (dataset: { id: string; name: string }) => {
    agent.setActiveDataset({ id: dataset.id, name: dataset.name });
    // Agent chỉ biết dataset nào được chọn khi được nói - gửi thành tin nhắn hiển thị.
    agent.send(t("dataset.usePrompt", { name: dataset.name, id: dataset.id }));
    composerRef.current?.focus();
  };

  const openDetails = () => {
    setTab("job");
    setPanelOpen(true);
    // Màn hình nhỏ: panel nằm trong sheet.
    if (window.matchMedia?.("(max-width: 1279px)").matches) setSheetOpen(true);
  };

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    if (agent.busy) return;
    const picked = pickFile(event.dataTransfer.files?.[0]);
    setComposerError(picked.error);
    setPending(picked.pending);
  };

  const composer = (variant: "hero" | "docked") => (
    <PromptComposer
      ref={composerRef}
      variant={variant}
      busy={agent.busy}
      sending={agent.sending}
      activityText={activityText}
      uploadProgress={agent.uploadProgress}
      pending={pending}
      onPendingChange={setPending}
      onSend={agent.send}
      onUpload={agent.upload}
      error={composerError}
      onError={setComposerError}
      activeDataset={agent.activeDataset}
      activeDatasetName={datasetInfo.data?.data?.dataName}
      onClearDataset={() => agent.setActiveDataset(null)}
      onPickDataset={pickDataset}
    />
  );

  const actions = {
    busy: agent.busy,
    onSend: agent.send,
    onRefreshed: agent.applyJobFromApi,
    onActivated: (jobId: string) => agent.setJobActivated(jobId, true),
    onOpenDetails: openDetails,
  };

  const context = (
    <ContextPanel
      tab={tab}
      onTabChange={setTab}
      activeDataset={agent.activeDataset}
      onActiveDatasetChange={agent.setActiveDataset}
      onPickDataset={pickDataset}
      datasetRows={datasetRows}
      onDatasetRows={(id, rows) => setDatasetRows((prev) => ({ ...prev, [id]: rows }))}
      items={agent.items}
      jobs={agent.jobs}
      busy={agent.busy}
      onSend={agent.send}
      onRefreshed={agent.applyJobFromApi}
      onActivated={actions.onActivated}
    />
  );

  const announcement = agent.announcement;

  return (
    // Chiều cao = màn hình - topbar (3.5rem) - padding dọc của <main> trong AppShell (3rem).
    <div className="flex h-[calc(100svh-6.5rem)] min-h-[520px] flex-col gap-4">
      {/* Thông báo cho trình đọc màn hình: chỉ các mốc quan trọng, không đọc từng sự kiện. */}
      <p className="sr-only" aria-live="polite" aria-atomic="true">
        {announcement ? `${t(`announce.${announcement.code}`, announcement.values)}${"​".repeat(announcement.n % 2)}` : ""}
      </p>

      <header className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-agent-primary text-agent-primary-fg shadow-sm" aria-hidden>
            <Bot className="h-6 w-6" />
          </div>
          <div className="min-w-0">
            <h1 className="text-2xl font-black tracking-tight text-automl-ink">{t("title")}</h1>
            <p className="hidden truncate text-xs text-automl-muted md:block">{t("subtitle")}</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <ConnectionStatus health={agent.health} stream={agent.stream} restoring={agent.restoring} />
          <button
            type="button"
            onClick={async () => {
              await agent.reset();
              composerRef.current?.focus();
            }}
            disabled={agent.busy || empty}
            title={agent.busy ? t("header.waitBusy") : undefined}
            className="agent-focus inline-flex items-center gap-1.5 rounded-xl border border-automl-line bg-automl-surface px-3 py-2 text-sm font-semibold text-automl-ink transition-colors duration-200 hover:bg-automl-surface-muted disabled:opacity-40"
          >
            <SquarePen className="h-4 w-4" aria-hidden />
            <span className="hidden sm:inline">{t("header.newChat")}</span>
            <span className="sr-only sm:hidden">{t("header.newChat")}</span>
          </button>
          <button
            type="button"
            onClick={() => setPanelOpen((v) => !v)}
            aria-label={panelOpen ? t("header.hidePanel") : t("header.showPanel")}
            aria-pressed={panelOpen}
            className={cn(iconButton, "hidden xl:inline-flex")}
          >
            {panelOpen ? <PanelRightClose className="h-4 w-4" aria-hidden /> : <PanelRight className="h-4 w-4" aria-hidden />}
          </button>
          <button type="button" onClick={() => setSheetOpen(true)} aria-label={t("header.openPanel")} className={cn(iconButton, "xl:hidden")}>
            <PanelRight className="h-4 w-4" aria-hidden />
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 gap-4">
        <div
          onDragOver={(event) => {
            event.preventDefault();
            if (!agent.busy) setDragging(true);
          }}
          onDragLeave={(event) => {
            if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false);
          }}
          onDrop={onDrop}
          className="relative flex min-w-0 flex-1 flex-col overflow-hidden rounded-3xl border border-automl-line bg-automl-surface shadow-sm"
        >
          {empty ? (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <AgentWelcome composer={composer("hero")} busy={agent.busy} onSend={agent.send} />
            </div>
          ) : (
            <>
              <ConversationThread items={agent.items} liveTrace={agent.liveTrace} jobs={agent.jobs} actions={actions} />
              <div className="border-t border-automl-line bg-automl-surface/90 px-4 pb-[max(1rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur">
                <div className="mx-auto w-full max-w-[820px]">{composer("docked")}</div>
              </div>
            </>
          )}

          {dragging && (
            <div className="pointer-events-none absolute inset-3 flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-agent-primary bg-agent-primary-soft/95 text-agent-primary-strong">
              <UploadCloud className="mb-2 h-10 w-10" aria-hidden />
              <p className="font-semibold">{t("drop.title")}</p>
              <p className="text-xs opacity-80">{t("drop.hint", { mb: MAX_UPLOAD_MB })}</p>
            </div>
          )}
        </div>

        {panelOpen && (
          <aside aria-label={t("panel.label")} className="hidden w-[350px] shrink-0 overflow-hidden rounded-3xl border border-automl-line bg-automl-surface shadow-sm xl:block">
            {context}
          </aside>
        )}
      </div>

      <Sheet open={sheetOpen} onOpenChange={setSheetOpen}>
        <SheetContent side="right" className="w-full max-w-[380px] bg-automl-surface p-0 sm:max-w-[380px]">
          <SheetHeader className="sr-only">
            <SheetTitle>{t("panel.label")}</SheetTitle>
            <SheetDescription>{t("panel.description")}</SheetDescription>
          </SheetHeader>
          <div className="h-full pt-10">{context}</div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
