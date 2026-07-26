"use client";

import { Languages } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/i18n/LanguageProvider";

export default function LanguageToggle() {
  const t = useTranslations("Header");
  const { locale, setLocale } = useLanguage();
  const nextLocale = locale === "en" ? "vi" : "en";

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={() => setLocale(nextLocale)}
      title={locale === "en" ? t("switchToVietnamese") : t("switchToEnglish")}
      aria-label={t("language")}
      className="h-11 w-[58px] rounded-2xl border-automl-line bg-automl-surface text-automl-ink shadow-none transition hover:bg-automl-blue-soft hover:text-automl-blue dark:bg-white/10 dark:hover:bg-white/15"
    >
      <span className="flex items-center gap-1.5 leading-none">
        <Languages className="h-4 w-4" />
        <span className="text-[11px] font-black">{locale.toUpperCase()}</span>
      </span>
    </Button>
  );
}
