"use client";

import {
  createContext,
  ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { AbstractIntlMessages, NextIntlClientProvider } from "next-intl";
import {
  AppLocale,
  defaultLocale,
  isAppLocale,
  localeCookieName,
  localeStorageKey,
} from "@/core/i18n/config";

type LanguageContextValue = {
  locale: AppLocale;
  setLocale: (locale: AppLocale) => void;
};

const messagesCache: Partial<Record<AppLocale, AbstractIntlMessages>> = {};

async function loadLocaleMessages(
  targetLocale: AppLocale,
): Promise<AbstractIntlMessages> {
  const cached = messagesCache[targetLocale];
  if (cached) return cached;

  const mod =
    targetLocale === "en"
      ? await import("@/messages/en.json")
      : await import("@/messages/vi.json");
  const loaded = mod.default as AbstractIntlMessages;
  messagesCache[targetLocale] = loaded;
  return loaded;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

function persistLocale(locale: AppLocale) {
  localStorage.setItem(localeStorageKey, locale);
  document.cookie = `${localeCookieName}=${locale}; path=/; max-age=31536000; SameSite=Lax`;
  document.documentElement.lang = locale;
}

export function LanguageProvider({
  children,
  initialLocale = defaultLocale,
  initialMessages,
}: {
  children: ReactNode;
  initialLocale?: AppLocale;
  initialMessages: AbstractIntlMessages;
}) {
  const resolvedInitialLocale: AppLocale = isAppLocale(initialLocale)
    ? initialLocale
    : defaultLocale;

  if (!messagesCache[resolvedInitialLocale]) {
    messagesCache[resolvedInitialLocale] = initialMessages;
  }

  const [locale, setLocaleState] = useState<AppLocale>(resolvedInitialLocale);
  const [messages, setMessages] = useState<AbstractIntlMessages>(initialMessages);

  const switchLocale = useCallback(async (nextLocale: AppLocale) => {
    try {
      const nextMessages = await loadLocaleMessages(nextLocale);
      setMessages(nextMessages);
      setLocaleState(nextLocale);
      persistLocale(nextLocale);
    } catch (error) {
      console.error("Failed to load locale messages:", error);
    }
  }, []);

  useEffect(() => {
    const savedLocale = localStorage.getItem(localeStorageKey);

    if (isAppLocale(savedLocale) && savedLocale !== resolvedInitialLocale) {
      void switchLocale(savedLocale);
      return;
    }

    persistLocale(resolvedInitialLocale);
  }, [resolvedInitialLocale, switchLocale]);

  const value = useMemo<LanguageContextValue>(
    () => ({
      locale,
      setLocale: (nextLocale) => {
        if (nextLocale === locale) return;
        void switchLocale(nextLocale);
      },
    }),
    [locale, switchLocale],
  );

  return (
    <LanguageContext.Provider value={value}>
      <NextIntlClientProvider
        locale={locale}
        messages={messages}
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
