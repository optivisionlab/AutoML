"use client";

import { useTranslations } from "next-intl";
import { History, RefreshCw, WifiOff } from "lucide-react";
import { cn } from "@/shared/lib/utils";
import type { HealthState, StreamState } from "../hooks/useAgentSession";

/** Trạng thái thật của agent server (GET /health) và kênh theo dõi job. */
export default function ConnectionStatus({
  health,
  stream,
  restoring,
}: {
  health: HealthState;
  stream: StreamState;
  restoring: boolean;
}) {
  const t = useTranslations("Agent.status");
  const [dot, label] =
    health.state === "offline"
      ? ["bg-agent-error", t("offline")]
      : health.state === "degraded"
        ? ["bg-agent-warning", t("degraded")]
        : health.state === "ok"
          ? ["bg-agent-success", t("ready")]
          : ["bg-automl-muted", t("checking")];
  const title =
    health.state === "degraded" ? health.info.configuration_error : health.state === "ok" ? `${health.info.provider} · ${health.info.model}` : undefined;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="inline-flex items-center gap-1.5 rounded-full border border-automl-line bg-automl-surface px-2.5 py-1 font-medium text-automl-muted-strong" title={title}>
        {health.state === "offline" ? (
          <WifiOff className="h-3 w-3 text-agent-error" aria-hidden />
        ) : (
          <span className={cn("h-2 w-2 rounded-full", dot)} aria-hidden />
        )}
        {label}
      </span>
      {restoring && (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-agent-info-soft px-2.5 py-1 font-medium text-agent-info">
          <History className="h-3 w-3" aria-hidden />
          {t("restoring")}
        </span>
      )}
      {stream === "reconnecting" && (
        <span role="status" className="inline-flex items-center gap-1.5 rounded-full bg-agent-warning-soft px-2.5 py-1 font-medium text-agent-warning">
          <RefreshCw className="h-3 w-3 animate-spin motion-reduce:animate-none" aria-hidden />
          {t("reconnecting")}
        </span>
      )}
    </div>
  );
}
