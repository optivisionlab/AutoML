"use client";

import { useTranslations } from "next-intl";
import { getApiErrorMessage } from "@/core/api/baseApi";

/** Lỗi backend v1 -> câu cụ thể theo mã HTTP (403/404/409), không nuốt thành "lỗi chung". */
export function useApiErrorText() {
  const t = useTranslations("Agent.job.apiError");
  return (error: unknown): string => {
    const status = (error as { status?: unknown } | null)?.status;
    if (status === 403 || status === 404 || status === 409) return t(String(status));
    return t("other", { detail: getApiErrorMessage(error, String(status ?? "?")) });
  };
}
