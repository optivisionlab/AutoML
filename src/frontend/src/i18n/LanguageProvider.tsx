"use client";

import { createContext, ReactNode, useContext, useEffect, useMemo, useState } from "react";
import { AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import enMessages from "@/messages/en.json";
import viMessages from "@/messages/vi.json";
import {
  AppLocale,
  defaultLocale,
  isAppLocale,
  localeCookieName,
  localeStorageKey,
} from "@/i18n/config";

type LanguageContextValue = {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
};

const messagesByLocale: Record<AppLocale, AbstractIntlMessages> = {
  en: enMessages,
  vi: viMessages,
};

const LanguageContext = createContext<LanguageContextValue | null>(null);

function persistLocale(locale: AppLocale) {
  localStorage.setItem(localeStorageKey, locale);
  document.cookie = `${localeCookieName}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
  document.documentElement.lang = locale;
}

export function LanguageProvider({
  children,
  initialLocale = defaultLocale,
}: {
  children: ReactNode;
  initialLocale?: AppLocale;
}) {
  const [locale, setLocaleState] = useState<AppLocale>(
    isAppLocale(initialLocale) ? initialLocale : defaultLocale,
  );

  useEffect(() => {
    const savedLocale = localStorage.getItem(localeStorageKey);

    if (isAppLocale(savedLocale) && savedLocale !== locale) {
      setLocaleState(savedLocale);
      persistLocale(savedLocale);
      return;
    }

    persistLocale(locale);
  }, [locale]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      locale,
      setLocale: (nextLocale) => {
        setLocaleState(nextLocale);
        persistLocale(nextLocale);
      },
    }),
    [locale],
  );

  return (
    <LanguageContext.Provider value={value}>
      <NextIntlClientProvider
        locale={locale}
        messages={messagesByLocale[locale]}
        timeZone="Asia/Ho_Chi_Minh"
      >
        {children}
      </NextIntlClientProvider>
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const context = useContext(LanguageContext);

  if (!context) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }

  return context;
}
