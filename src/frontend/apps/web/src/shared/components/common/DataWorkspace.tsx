"use client";

import { ReactNode } from "react";
import { LucideIcon } from "lucide-react";
import { cn } from "@/shared/lib/utils";

type DataWorkspaceHeaderProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
  children?: ReactNode;
};

type DataWorkspaceMetric = {
  label: string;
  value: string;
  detail: string;
  icon: LucideIcon;
  tone: string;
};

export function DataWorkspaceHeader({
  title,
  subtitle,
  children,
}: DataWorkspaceHeaderProps) {
  return (
    <section className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
      <div>
        <h1 className="text-4xl font-black tracking-tight text-automl-ink dark:text-white">
          {title}
        </h1>
        <p className="mt-2 text-sm font-medium text-automl-muted dark:text-white/60">
          {subtitle}
        </p>
      </div>
      {children && (
        <div className="flex shrink-0 flex-wrap items-center gap-3">
          {children}
        </div>
      )}
    </section>
  );
}

export function DataWorkspaceMetrics({
  metrics,
}: {
  metrics: DataWorkspaceMetric[];
}) {
  return (
    <section className="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
      {metrics.map((metric) => {
        const Icon = metric.icon;

        return (
          <article
            key={metric.label}
            className="group relative overflow-hidden rounded-3xl border border-slate-200/80 bg-white p-5 shadow-sm transition-all hover:shadow-md dark:border-white/10 dark:bg-[#0b121e]"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                  {metric.label}
                </p>
                <p className="mt-3 text-3xl font-black tracking-tight text-slate-900 dark:text-white">
                  {metric.value}
                </p>
                <p className="mt-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400">
                  {metric.detail}
                </p>
              </div>
              <div
                className={cn(
                  "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl shadow-xs transition-transform group-hover:scale-105",
                  metric.tone,
                )}
              >
                <Icon className="h-5 w-5" />
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}

export function DataWorkspaceControls({
  summary,
  children,
}: {
  summary: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm dark:border-white/10 dark:bg-white/10">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <p className="text-sm font-black text-automl-ink dark:text-white">
          {summary}
        </p>
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-end">
          {children}
        </div>
      </div>
    </section>
  );
}

export const workspaceInputClass =
  "h-11 rounded-2xl border border-slate-200 bg-slate-50 px-4 text-sm font-bold text-automl-ink outline-none transition placeholder:text-slate-400 focus:border-automl-blue focus:bg-white focus:ring-4 focus:ring-automl-blue/10 dark:border-white/10 dark:bg-white/10 dark:text-white";

