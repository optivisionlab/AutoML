/** Hàm dịch rút gọn từ next-intl - để format không phụ thuộc React. */
type Translate = (key: string, values?: Record<string, string | number>) => string;

export function formatTime(ms: number | undefined, locale: string): string {
  if (!ms) return "—";
  return new Date(ms).toLocaleTimeString(locale, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

/** t: useTranslations("Agent.duration"). */
export function formatDuration(seconds: number, t: Translate): string {
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return t("seconds", { n: s });
  const m = Math.floor(s / 60);
  if (m < 60) return t("minutes", { n: m });
  return t("hours", { h: Math.floor(m / 60), m: m % 60 });
}

export function formatScore(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "—";
  return Math.abs(value) >= 1000 ? value.toFixed(1) : value.toFixed(4);
}

export function shortId(id: string, size = 8): string {
  return id.length > size ? id.slice(0, size) : id;
}
