"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Button } from "@/shared/components/ui/button";
import { cn } from "@/shared/lib/utils";

type BackButtonProps = {
  fallbackHref?: string;
  label?: string;
  variant?: "ghost" | "soft" | "primary";
  className?: string;
};

export default function BackButton({
  fallbackHref = "/dashboard",
  label,
  variant = "soft",
  className,
}: BackButtonProps) {
  const router = useRouter();
  const t = useTranslations("Common");

  const handleBack = () => {
    if (typeof window !== "undefined" && window.history.length > 1) {
      router.back();
      return;
    }

    router.push(fallbackHref);
  };

  return (
    <Button
      type="button"
      variant={variant === "primary" ? "default" : "outline"}
      onClick={handleBack}
      className={cn(
        "inline-flex h-10 items-center gap-2 rounded-2xl px-4 text-sm font-black shadow-none transition",
        variant === "ghost" &&
          "border-transparent bg-transparent text-automl-muted hover:bg-automl-blue-soft hover:text-automl-blue dark:text-white/60",
        variant === "soft" &&
          "border-[var(--automl-data-card-border)] bg-[var(--automl-data-card-bg)] text-[var(--automl-data-muted)] hover:bg-[var(--automl-table-header-bg)] hover:text-automl-blue",
        variant === "primary" &&
          "bg-automl-blue text-white hover:bg-automl-blue-hover",
        className,
      )}
    >
      <ArrowLeft className="h-4 w-4" />
      {label ?? t("back")}
    </Button>
  );
}
