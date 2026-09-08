"use client";

import React from "react";
import { Check, ChevronDown } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/shared/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/shared/components/ui/dropdown-menu";
import { useLanguage } from "@/core/i18n/LanguageProvider";
import { cn } from "@/shared/lib/utils";

/**
 * Cờ Việt Nam SVG chuẩn vector sắc nét
 */
export function VietnamFlag({ className = "h-3.5 w-5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 30 20"
      className={cn("shrink-0 rounded-[2px] overflow-hidden shadow-xs ring-1 ring-black/10 dark:ring-white/20", className)}
      aria-hidden="true"
    >
      <rect width="30" height="20" fill="#da251d" />
      <polygon
        points="15,4 16.5,8.5 21,8.5 17.5,11.2 19,15.5 15,13 11,15.5 12.5,11.2 9,8.5 13.5,8.5"
        fill="#ffff00"
      />
    </svg>
  );
}

/**
 * Cờ Anh (English / UK) SVG chuẩn vector sắc nét
 */
export function EnglishFlag({ className = "h-3.5 w-5" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 60 30"
      className={cn("shrink-0 rounded-[2px] overflow-hidden shadow-xs ring-1 ring-black/10 dark:ring-white/20", className)}
      aria-hidden="true"
    >
      <clipPath id="uk-flag-clip">
        <path d="M0,0 v30 h60 v-30 z" />
      </clipPath>
      <g clipPath="url(#uk-flag-clip)">
        <path d="M0,0 v30 h60 v-30 z" fill="#012169" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#fff" strokeWidth="6" />
        <path d="M0,0 L60,30 M60,0 L0,30" stroke="#C8102E" strokeWidth="4" />
        <path d="M30,0 v30 M0,15 h60" stroke="#fff" strokeWidth="10" />
        <path d="M30,0 v30 M0,15 h60" stroke="#C8102E" strokeWidth="6" />
      </g>
    </svg>
  );
}

export default function LanguageToggle({ className }: { className?: string }) {
  const t = useTranslations("Header");
  const { locale, setLocale } = useLanguage();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "h-10 px-3 rounded-xl border-slate-200/80 bg-white gap-2 shadow-none hover:bg-slate-50 text-slate-700 dark:border-white/10 dark:bg-white/10 dark:text-white dark:hover:bg-white/15 transition-all active:scale-95",
            className
          )}
          aria-label={t("language")}
          title={locale === "en" ? t("switchToVietnamese") : t("switchToEnglish")}
        >
          {locale === "vi" ? (
            <VietnamFlag className="h-3.5 w-5" />
          ) : (
            <EnglishFlag className="h-3.5 w-5" />
          )}
          <span className="text-[11px] font-black uppercase tracking-wider">
            {locale}
          </span>
          <ChevronDown className="h-3 w-3 opacity-50 transition-transform" />
        </Button>
      </DropdownMenuTrigger>

      <DropdownMenuContent
        align="end"
        className="min-w-[145px] rounded-2xl border-slate-200/80 bg-white p-1.5 shadow-xl dark:border-white/10 dark:bg-slate-950 backdrop-blur-xl"
      >
        <DropdownMenuItem
          onClick={() => setLocale("vi")}
          className={cn(
            "flex items-center justify-between gap-2.5 rounded-xl px-2.5 py-2 text-xs font-bold cursor-pointer transition-colors",
            locale === "vi"
              ? "bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-cyan-300"
              : "hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200"
          )}
        >
          <span className="flex items-center gap-2">
            <VietnamFlag className="h-3.5 w-5" />
            <span>Tiếng Việt</span>
          </span>
          {locale === "vi" && (
            <Check className="h-3.5 w-3.5 text-blue-600 dark:text-cyan-300" />
          )}
        </DropdownMenuItem>

        <DropdownMenuItem
          onClick={() => setLocale("en")}
          className={cn(
            "flex items-center justify-between gap-2.5 rounded-xl px-2.5 py-2 text-xs font-bold cursor-pointer transition-colors",
            locale === "en"
              ? "bg-blue-50 text-blue-600 dark:bg-blue-500/20 dark:text-cyan-300"
              : "hover:bg-slate-100 dark:hover:bg-white/10 text-slate-700 dark:text-slate-200"
          )}
        >
          <span className="flex items-center gap-2">
            <EnglishFlag className="h-3.5 w-5" />
            <span>English</span>
          </span>
          {locale === "en" && (
            <Check className="h-3.5 w-3.5 text-blue-600 dark:text-cyan-300" />
          )}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
