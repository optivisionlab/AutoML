"use client";

import { Spinner } from "@/shared/components/ui/spinner";
import { cn } from "@/shared/lib/utils";
import { useTranslations } from "next-intl";

type AppLoadingProps = {
  label?: string;
  variant?: "section" | "page" | "overlay";
  className?: string;
};

export default function AppLoading({
  label,
  variant = "section",
  className,
}: AppLoadingProps) {
  const t = useTranslations("Common");
  const loadingLabel = label ?? t("loadingData");
  const content = (
    <div className="flex flex-col items-center justify-center gap-3 text-center">
      <Spinner className="h-8 w-8 text-automl-blue" />
      {loadingLabel ? (
        <p className="text-sm font-bold text-automl-muted dark:text-white/60">
          {loadingLabel}
        </p>
      ) : null}
    </div>
  );

  if (variant === "overlay") {
    return (
      <div
        className={cn(
          "fixed inset-0 z-[9999] flex items-center justify-center bg-black/30 p-4 backdrop-blur-sm",
          className,
        )}
      >
        <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl dark:border-white/10 dark:bg-automl-navy">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white p-8 dark:border-white/10 dark:bg-white/5",
        variant === "page" ? "min-h-svh" : "min-h-48",
        className,
      )}
    >
      {content}
    </div>
  );
}
