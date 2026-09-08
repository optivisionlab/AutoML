export const locales = ["en", "vi"] as const;

export type AppLocale = (typeof locales)[number];

export const defaultLocale: AppLocale = "en";
export const localeCookieName = "NEXT_LOCALE";
export const localeStorageKey = "hautoml-locale";

export function isAppLocale(locale: unknown): locale is AppLocale {
  return typeof locale === "string" && locales.includes(locale as AppLocale);
}
