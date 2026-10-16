"use client";

import { useEffect, useState } from "react";
import { ArrowRight, Search, X } from "lucide-react";
import { useTranslations } from "next-intl";

import { useLanguage } from "@/core/i18n/LanguageProvider";
import { API_ENDPOINTS, getDocCategories, getFeatureCards } from "../data/docs-content";

type DocsSearchModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSelectTopic: (topicId: string) => void;
};

type SearchResult = {
  id: string;
  title: string;
  desc: string;
  category: string;
  topicId: string;
};

export default function DocsSearchModal({
  isOpen,
  onClose,
  onSelectTopic,
}: DocsSearchModalProps) {
  const t = useTranslations("Docs");
  const { locale } = useLanguage();
  const [query, setQuery] = useState("");

  const categories = getDocCategories(locale);
  const featureCards = getFeatureCards(locale);

  // Keyboard shortcut ⌘K / Ctrl+K
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        if (isOpen) {
          onClose();
        }
      }
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  // Build searchable index based on current locale
  const allSearchItems: SearchResult[] = [
    // Categories and nav items
    ...categories.flatMap((cat) =>
      cat.items.map((it) => ({
        id: it.id,
        title: it.title,
        desc: `${cat.title}`,
        category: cat.title,
        topicId: it.id,
      }))
    ),
    // Feature cards
    ...featureCards.map((card) => ({
      id: card.id,
      title: card.title,
      desc: card.desc,
      category: t("overview.keyFeatures"),
      topicId: card.topicId,
    })),
    // API endpoints
    ...API_ENDPOINTS.map((ep) => ({
      id: `${ep.method}-${ep.path}`,
      title: `${ep.method} ${ep.path}`,
      desc: ep.desc,
      category: `API: ${ep.group}`,
      topicId:
        ep.group === "Auth"
          ? "api-auth"
          : ep.group === "Datasets"
          ? "api-datasets"
          : ep.group === "v2 AutoML"
          ? "backend-api"
          : "api-training-inference",
    })),
  ];

  const filtered = query.trim()
    ? allSearchItems.filter(
        (item) =>
          item.title.toLowerCase().includes(query.toLowerCase()) ||
          item.desc.toLowerCase().includes(query.toLowerCase()) ||
          item.category.toLowerCase().includes(query.toLowerCase())
      )
    : allSearchItems.slice(0, 8);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-24 p-4">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-md transition-opacity"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Modal Dialog */}
      <div className="relative w-full max-w-xl overflow-hidden rounded-3xl border border-slate-200/80 bg-white shadow-2xl dark:border-white/15 dark:bg-[#0B0F19]/95 backdrop-blur-2xl">
        {/* Search input bar */}
        <div className="flex items-center gap-3 border-b border-slate-200/80 px-4 py-3.5 dark:border-white/10">
          <Search className="h-5 w-5 text-blue-500 dark:text-cyan-400" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t("searchPlaceholder")}
            autoFocus
            className="flex-1 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 dark:text-white"
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              className="rounded-lg p-1 text-slate-400 hover:text-slate-600 dark:hover:text-white"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <kbd className="rounded-lg border border-slate-200 bg-slate-100 px-2 py-0.5 text-[10px] font-semibold text-slate-500 dark:border-white/15 dark:bg-white/10 dark:text-slate-300">
            ESC
          </kbd>
        </div>

        {/* Search results */}
        <div className="max-h-96 overflow-y-auto p-2 scrollbar-thin">
          {filtered.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500 dark:text-slate-400">
              {t("searchNoResults")} &quot;{query}&quot;
            </div>
          ) : (
            <div className="space-y-1">
              {filtered.map((item) => (
                <button
                  key={`${item.id}-${item.category}`}
                  type="button"
                  onClick={() => {
                    onSelectTopic(item.topicId);
                    onClose();
                  }}
                  className="group flex w-full items-center justify-between rounded-2xl px-3.5 py-2.5 text-left transition-colors hover:bg-blue-50/80 dark:hover:bg-blue-950/40"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-900 group-hover:text-blue-600 dark:text-white dark:group-hover:text-cyan-300">
                        {item.title}
                      </span>
                      <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-medium text-slate-500 dark:bg-white/10 dark:text-slate-300">
                        {item.category}
                      </span>
                    </div>
                    <p className="line-clamp-1 text-[11px] text-slate-500 dark:text-slate-400">
                      {item.desc}
                    </p>
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-400 opacity-0 group-hover:opacity-100 group-hover:text-blue-600 dark:group-hover:text-cyan-400 transition-opacity" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Modal footer tip */}
        <div className="border-t border-slate-100 bg-slate-50/80 px-4 py-2 text-[11px] text-slate-500 dark:border-white/10 dark:bg-[#060D1A]/80 dark:text-slate-400">
          <span>{t("popularSuggestions")} </span>
          <span className="font-semibold text-blue-600 dark:text-cyan-400">
            &quot;docker&quot;, &quot;api&quot;, &quot;kafka&quot;, &quot;imputation&quot;, &quot;bayes&quot;
          </span>
        </div>
      </div>
    </div>
  );
}
