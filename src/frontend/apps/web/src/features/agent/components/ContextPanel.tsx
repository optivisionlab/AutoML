"use client";

import { KeyboardEvent, useId, useMemo, useRef, type ReactNode } from "react";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { ArrowRightLeft, Database, ExternalLink, LayoutDashboard, Loader2, Settings2, Trophy, Workflow } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import {
  useGetDatasetFeaturesQuery,
  useGetDatasetInfoQuery,
  useLazyGetDatasetDataPreviewQuery,
} from "@/core/api/datasetApi";
import type { ActiveDataset, ChatItem, ProblemType } from "../hooks/useAgentSession";
import { isJobActive, type ConfigView, type JobView } from "../lib/eventAdapter";
import { formatScore, shortId } from "../lib/format";
import { card, pillButton } from "../lib/ui";
import ConfigSummaryCard, { ValidationBadge } from "./ConfigSummaryCard";
import DatasetPicker from "./DatasetPicker";
import TrainingJobCard, { JobStatusBadge } from "./TrainingJobCard";

export type PanelTab = "overview" | "dataset" | "config" | "job" | "results";

const TABS: { id: PanelTab; icon: typeof Database }[] = [
  { id: "overview", icon: LayoutDashboard },
  { id: "dataset", icon: Database },
  { id: "config", icon: Settings2 },
  { id: "job", icon: Workflow },
  { id: "results", icon: Trophy },
];

function Empty({ children }: { children: ReactNode }) {
  return <p className="rounded-2xl border border-dashed border-automl-line px-4 py-6 text-center text-xs text-automl-muted">{children}</p>;
}

/** Bảng xem trước: chỉ tải khi người dùng bấm, giới hạn vài dòng. */
function PreviewTable({ datasetId, onRows }: { datasetId: string; onRows?: (rows: number) => void }) {
  const t = useTranslations("Agent.dataset");
  const [load, { data, isFetching, isError }] = useLazyGetDatasetDataPreviewQuery();
  // transformResponse ở datasetApi trả { rows, data: [...] } chứ không bọc BaseResponse.
  const payload = data as unknown as { rows?: number; data?: Record<string, unknown>[] } | undefined;
  const rows = (payload?.data ?? []).slice(0, 10);
  const columns = rows.length ? Object.keys(rows[0]) : [];

  if (!data && !isFetching && !isError) {
    return (
      <button
        type="button"
        onClick={async () => {
          const result = await load({ datasetId, numRows: 10 }).unwrap().catch(() => null);
          const total = (result as unknown as { rows?: number } | null)?.rows;
          if (typeof total === "number") onRows?.(total);
        }}
        className={cn(pillButton, "mt-3 w-full justify-center rounded-xl")}
      >
        {t("preview")}
      </button>
    );
  }
  if (isFetching) {
    return (
      <p className="mt-3 flex items-center gap-1.5 text-xs text-automl-muted">
        <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> {t("previewLoading")}
      </p>
    );
  }
  if (isError) return <p className="mt-3 text-xs text-agent-error">{t("previewError")}</p>;
  if (!rows.length) return <p className="mt-3 text-xs text-automl-muted">{t("previewEmpty")}</p>;

  return (
    <div className="mt-3 max-h-64 overflow-auto rounded-xl border border-automl-line" tabIndex={0}>
      <table className="text-left text-[11.5px]">
        <thead className="sticky top-0 bg-automl-surface-muted">
          <tr>
            {columns.map((c) => (
              <th key={c} scope="col" className="whitespace-nowrap px-2 py-1 font-semibold text-automl-ink">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className="border-t border-automl-line">
              {columns.map((c) => (
                <td key={c} className="max-w-[160px] truncate whitespace-nowrap px-2 py-1 text-automl-muted-strong">{String(row[c] ?? "")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function DatasetContextCard({
  dataset,
  config,
  busy,
  onProblemTypeChange,
  onPickDataset,
  rows,
  onRows,
}: {
  dataset: ActiveDataset;
  config: ConfigView | null;
  busy: boolean;
  onProblemTypeChange: (type: ProblemType) => void;
  onPickDataset: (dataset: { id: string; name: string }) => void;
  rows?: number;
  onRows: (rows: number) => void;
}) {
  const t = useTranslations("Agent.dataset");
  const tTypes = useTranslations("Agent.problemTypes");
  // Loại bài toán: người dùng chọn lúc tải lên, hoặc lấy từ cấu hình đã kiểm định.
  const problemType: ProblemType =
    dataset.problemType ?? (config?.config?.problem_type === "regression" ? "regression" : "classification");
  const info = useGetDatasetInfoQuery(dataset.id);
  const features = useGetDatasetFeaturesQuery({ datasetId: dataset.id, problemType });

  const name = info.data?.data?.dataName ?? dataset.name;
  // Backend trả thẳng { cột: có-làm-target-được } trong data.
  const columns = useMemo(() => {
    const raw = features.data?.data as unknown as Record<string, unknown> | undefined;
    const map = (raw && typeof raw.features === "object" ? raw.features : raw) as Record<string, boolean> | undefined;
    return map ? Object.entries(map) : null;
  }, [features.data]);
  const targets = columns?.filter(([, ok]) => ok).map(([c]) => c) ?? [];
  const target = config?.config?.target as string | undefined;
  const featureCount = Array.isArray(config?.config?.list_feature) ? config!.config!.list_feature.length : undefined;

  const infoStatus = (info.error as { status?: unknown } | undefined)?.status;
  const featureStatus = (features.error as { status?: unknown } | undefined)?.status;
  const denied = infoStatus === 401 || infoStatus === 403 || featureStatus === 401 || featureStatus === 403;
  const missing = infoStatus === 404;

  return (
    <section className={cn(card, "p-3.5")}>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[11px] font-medium uppercase tracking-wide text-automl-muted">{t("inUse")}</p>
          <p className="mt-0.5 truncate text-sm font-bold text-automl-ink">{name ?? (info.isLoading ? t("loading") : "—")}</p>
          <p className="font-mono text-[11px] text-automl-muted" title={dataset.id}>#{shortId(dataset.id, 10)}</p>
        </div>
        <DatasetPicker
          disabled={busy}
          onPick={onPickDataset}
          trigger={() => (
            <button type="button" disabled={busy} className={cn(pillButton, "shrink-0")}>
              <ArrowRightLeft className="h-3.5 w-3.5" aria-hidden /> {t("change")}
            </button>
          )}
        />
      </div>

      {denied ? (
        <p className="mt-3 text-xs text-agent-error">{t("noPermission")}</p>
      ) : missing ? (
        <p className="mt-3 text-xs text-agent-error">{t("notFound")}</p>
      ) : (
        <>
          <fieldset className="mt-3">
            <legend className="text-[11px] font-medium uppercase tracking-wide text-automl-muted">{t("problemType")}</legend>
            <div className="mt-1 inline-flex rounded-lg border border-automl-line p-0.5">
              {(["classification", "regression"] as const).map((type) => (
                <button
                  key={type}
                  type="button"
                  aria-pressed={problemType === type}
                  onClick={() => onProblemTypeChange(type)}
                  className={cn(
                    "agent-focus rounded-md px-2.5 py-1 text-xs font-semibold transition-colors",
                    problemType === type ? "bg-agent-primary-soft text-agent-primary-strong" : "text-automl-muted hover:text-automl-ink",
                  )}
                >
                  {tTypes(type)}
                </button>
              ))}
            </div>
          </fieldset>

          <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
            <div>
              <dt className="text-automl-muted">{t("currentTarget")}</dt>
              <dd className="truncate font-semibold text-automl-ink">{target ?? t("notSet")}</dd>
            </div>
            <div>
              <dt className="text-automl-muted">{t("featureCount")}</dt>
              <dd className="font-semibold text-automl-ink">{featureCount ?? t("notSet")}</dd>
            </div>
            {columns && (
              <>
                <div>
                  <dt className="text-automl-muted">{t("columns")}</dt>
                  <dd className="font-semibold text-automl-ink">{columns.length}</dd>
                </div>
                <div>
                  <dt className="text-automl-muted">{t("targets")}</dt>
                  <dd className="font-semibold text-automl-ink">{targets.length}</dd>
                </div>
              </>
            )}
            {typeof rows === "number" && (
              <div>
                <dt className="text-automl-muted">{t("rows")}</dt>
                <dd className="font-semibold text-automl-ink">{rows.toLocaleString()}</dd>
              </div>
            )}
          </dl>

          {features.isFetching && !columns ? (
            <p className="mt-3 flex items-center gap-1.5 text-xs text-automl-muted">
              <Loader2 className="h-3.5 w-3.5 animate-spin motion-reduce:animate-none" aria-hidden /> {t("readingSchema")}
            </p>
          ) : !columns ? (
            <p className="mt-3 text-xs text-automl-muted">{t("noSchema")}</p>
          ) : (
            <>
              <ul className="mt-3 flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
                {columns.map(([column, canBeTarget]) => (
                  <li
                    key={column}
                    className={cn(
                      "rounded-md px-1.5 py-0.5 font-mono text-[11px]",
                      column === target && "outline outline-2 outline-agent-primary",
                      canBeTarget
                        ? "bg-agent-primary-soft text-agent-primary-strong"
                        : "bg-automl-surface-muted text-automl-muted-strong",
                    )}
                  >
                    {column}
                    {canBeTarget && <span className="sr-only"> ({t("targets")})</span>}
                  </li>
                ))}
              </ul>
              <p className="mt-1.5 text-[11px] text-automl-muted">{t("legend")}</p>
              <PreviewTable key={dataset.id} datasetId={dataset.id} onRows={onRows} />
            </>
          )}
        </>
      )}

      <Link href={`/my-datasets/${dataset.id}`} className="agent-focus mt-3 inline-flex items-center gap-1 rounded text-xs font-semibold text-agent-primary-strong hover:underline">
        {t("openPage")} <ExternalLink className="h-3 w-3" aria-hidden />
      </Link>
    </section>
  );
}

// Khai báo ở cấp module: khai báo bên trong Overview thì mỗi lần render là một
// component mới, React dựng lại nút và người dùng bàn phím mất focus.
function OverviewRow({
  tab,
  label,
  onSelect,
  children,
}: {
  tab: PanelTab;
  label: string;
  onSelect: (tab: PanelTab) => void;
  children: ReactNode;
}) {
  const tTabs = useTranslations("Agent.panel.tabs");
  return (
    <button type="button" onClick={() => onSelect(tab)} className={cn(card, "agent-focus block w-full p-3 text-left transition-colors hover:bg-automl-surface-muted")}>
      <span className="text-[11px] font-medium uppercase tracking-wide text-automl-muted">{label}</span>
      <span className="mt-1 block text-sm text-automl-ink">{children}</span>
      <span className="sr-only"> - {tTabs(tab)}</span>
    </button>
  );
}

function Overview({
  dataset,
  datasetName,
  config,
  jobs,
  onSelect,
}: {
  dataset: ActiveDataset | null;
  datasetName?: string;
  config: ConfigView | null;
  jobs: JobView[];
  onSelect: (tab: PanelTab) => void;
}) {
  const t = useTranslations("Agent.panel.overview");
  const active = jobs.filter(isJobActive).length;
  const latestDone = jobs.find((job) => job.status === "completed");

  return (
    <div className="space-y-2.5">
      <OverviewRow tab="dataset" onSelect={onSelect} label={t("dataset")}>
        {dataset ? <span className="font-semibold">{datasetName ?? dataset.name ?? `#${shortId(dataset.id)}`}</span> : t("none")}
      </OverviewRow>
      <OverviewRow tab="config" onSelect={onSelect} label={t("config")}>
        {config ? (
          <span className="flex flex-wrap items-center gap-2">
            <ValidationBadge valid={config.valid} />
            {config.config?.target && <span className="font-mono text-xs">{config.config.target} · {config.config.metric_sort}</span>}
          </span>
        ) : (
          t("none")
        )}
      </OverviewRow>
      <OverviewRow tab="job" onSelect={onSelect} label={t("jobs")}>
        {jobs.length ? t("jobsSummary", { active, done: jobs.length - active }) : t("none")}
      </OverviewRow>
      <OverviewRow tab="results" onSelect={onSelect} label={t("latestResult")}>
        {latestDone ? (
          <span className="flex flex-wrap items-center gap-2">
            <JobStatusBadge status={latestDone.status} />
            <span className="font-semibold">{latestDone.bestModel ?? "—"}</span>
            <span className="font-mono text-xs">
              {latestDone.metric} {formatScore(latestDone.bestScore)}
            </span>
          </span>
        ) : (
          t("none")
        )}
      </OverviewRow>
    </div>
  );
}

interface Props {
  tab: PanelTab;
  onTabChange: (tab: PanelTab) => void;
  activeDataset: ActiveDataset | null;
  onActiveDatasetChange: (dataset: ActiveDataset) => void;
  onPickDataset: (dataset: { id: string; name: string }) => void;
  datasetRows: Record<string, number>;
  onDatasetRows: (datasetId: string, rows: number) => void;
  items: ChatItem[];
  jobs: Record<string, JobView>;
  busy: boolean;
  onSend: (text: string) => void;
  onRefreshed: (jobId: string, raw: Record<string, any>) => void;
  onActivated: (jobId: string) => void;
}

export default function ContextPanel({
  tab,
  onTabChange,
  activeDataset,
  onActiveDatasetChange,
  onPickDataset,
  datasetRows,
  onDatasetRows,
  items,
  jobs,
  busy,
  onSend,
  onRefreshed,
  onActivated,
}: Props) {
  const t = useTranslations("Agent.panel");
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({});
  // Panel dựng ở hai nơi (cột phải và sheet trên màn hình nhỏ) - id phải riêng.
  const uid = useId();
  const datasetInfo = useGetDatasetInfoQuery(activeDataset?.id ?? "", { skip: !activeDataset });

  const latestConfig = useMemo<ConfigView | null>(() => {
    for (let i = items.length - 1; i >= 0; i--) {
      const item = items[i];
      if (item.kind === "agent" && item.trace.configs.length) return item.trace.configs[item.trace.configs.length - 1];
    }
    return null;
  }, [items]);
  // Cấu hình gần nhất của CHÍNH dataset đang xem (target / số feature).
  const datasetConfig = latestConfig && activeDataset && latestConfig.datasetId === activeDataset.id ? latestConfig : null;

  const jobList = Object.values(jobs).sort((a, b) => (b.submittedAt ?? 0) - (a.submittedAt ?? 0));
  const completed = jobList.filter((job) => job.status === "completed");

  // Tab theo mẫu WAI-ARIA: mũi tên trái/phải, Home/End chuyển tab.
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const index = TABS.findIndex((x) => x.id === tab);
    const next =
      event.key === "ArrowRight" ? (index + 1) % TABS.length
        : event.key === "ArrowLeft" ? (index - 1 + TABS.length) % TABS.length
          : event.key === "Home" ? 0
            : event.key === "End" ? TABS.length - 1
              : -1;
    if (next < 0) return;
    event.preventDefault();
    onTabChange(TABS[next].id);
    tabRefs.current[TABS[next].id]?.focus();
  };

  return (
    <div className="flex h-full flex-col">
      <div role="tablist" aria-label={t("label")} onKeyDown={onKeyDown} className="flex gap-0.5 border-b border-automl-line p-1.5">
        {TABS.map(({ id, icon: Icon }) => (
          <button
            key={id}
            ref={(el) => {
              tabRefs.current[id] = el;
            }}
            id={`${uid}-tab-${id}`}
            role="tab"
            type="button"
            aria-selected={tab === id}
            aria-controls={`${uid}-panel`}
            tabIndex={tab === id ? 0 : -1}
            onClick={() => onTabChange(id)}
            className={cn(
              "agent-focus flex min-w-0 flex-1 flex-col items-center gap-0.5 rounded-lg px-1 py-1.5 text-[11px] font-semibold transition-colors duration-200",
              tab === id ? "bg-agent-primary-soft text-agent-primary-strong" : "text-automl-muted hover:bg-automl-surface-muted",
            )}
          >
            <span className="relative">
              <Icon className="h-4 w-4" aria-hidden />
              {id === "job" && jobList.some(isJobActive) && (
                <span className="absolute -right-1 -top-1 h-2 w-2 rounded-full bg-agent-primary" aria-hidden />
              )}
            </span>
            <span className="max-w-full truncate">{t(`tabs.${id}`)}</span>
          </button>
        ))}
      </div>

      <div id={`${uid}-panel`} role="tabpanel" aria-labelledby={`${uid}-tab-${tab}`} tabIndex={0} className="agent-focus min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {tab === "overview" && (
          <Overview dataset={activeDataset} datasetName={datasetInfo.data?.data?.dataName} config={latestConfig} jobs={jobList} onSelect={onTabChange} />
        )}

        {tab === "dataset" &&
          (activeDataset ? (
            <DatasetContextCard
              key={activeDataset.id}
              dataset={activeDataset}
              config={datasetConfig}
              busy={busy}
              onProblemTypeChange={(problemType) => onActiveDatasetChange({ ...activeDataset, problemType })}
              onPickDataset={onPickDataset}
              rows={datasetRows[activeDataset.id]}
              onRows={(rows) => onDatasetRows(activeDataset.id, rows)}
            />
          ) : (
            <div className="space-y-3">
              <Empty>{t("empty.dataset")}</Empty>
              <DatasetPicker
                disabled={busy}
                onPick={onPickDataset}
                trigger={() => (
                  <button type="button" disabled={busy} className={cn(pillButton, "w-full justify-center rounded-xl py-2")}>
                    <Database className="h-3.5 w-3.5" aria-hidden />
                    <ChooseLabel />
                  </button>
                )}
              />
            </div>
          ))}

        {tab === "config" &&
          (latestConfig ? (
            <>
              <ConfigSummaryCard view={latestConfig} />
              <p className="text-[11px] text-automl-muted">
                <ReadOnlyLabel />
              </p>
            </>
          ) : (
            <Empty>{t("empty.config")}</Empty>
          ))}

        {tab === "job" &&
          (jobList.length ? (
            jobList.map((job) => <TrainingJobCard key={job.jobId} job={job} variant="compact" onRefreshed={onRefreshed} />)
          ) : (
            <Empty>
              {t.rich("empty.job", {
                link: (chunks) => (
                  <Link href="/training-history" className="agent-focus rounded font-semibold text-agent-primary-strong hover:underline">
                    {chunks}
                  </Link>
                ),
              })}
            </Empty>
          ))}

        {tab === "results" &&
          (completed.length ? (
            completed.map((job) => (
              <TrainingJobCard key={job.jobId} job={job} busy={busy} onAsk={onSend} onRefreshed={onRefreshed} onActivated={onActivated} />
            ))
          ) : (
            <Empty>{t("empty.results")}</Empty>
          ))}
      </div>
    </div>
  );
}

function ChooseLabel() {
  const t = useTranslations("Agent.dataset");
  return <>{t("choose")}</>;
}

function ReadOnlyLabel() {
  const t = useTranslations("Agent.config");
  return <>{t("readOnly")}</>;
}
