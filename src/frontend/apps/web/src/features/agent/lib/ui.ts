/**
 * Class dùng chung của trang Agent. Màu ngữ nghĩa lấy từ token --agent-*,
 * trung tính từ --automl-* (globals.css) - cả hai đã có bản dark mode, nên
 * component không cần class dark: riêng.
 */
export const card = "rounded-2xl border border-automl-line bg-automl-surface";

export const pillButton =
  "agent-focus inline-flex items-center gap-1 rounded-full border border-automl-line px-3 py-1.5 text-xs font-semibold text-automl-ink transition-colors duration-200 hover:bg-automl-surface-muted disabled:cursor-not-allowed disabled:opacity-50";

export const primaryPill =
  "agent-focus inline-flex items-center gap-1 rounded-full bg-agent-primary px-3 py-1.5 text-xs font-semibold text-agent-primary-fg transition-colors duration-200 hover:bg-agent-primary/90 disabled:cursor-not-allowed disabled:opacity-50";

export const ghostButton =
  "agent-focus inline-flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-automl-muted-strong transition-colors duration-200 hover:bg-automl-surface-muted";

export const input =
  "agent-focus min-w-0 rounded-lg border border-automl-line bg-automl-surface px-2.5 py-1.5 text-sm text-automl-ink placeholder:text-automl-muted focus:border-agent-primary";
