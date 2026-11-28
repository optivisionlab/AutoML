"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { useTranslations } from "next-intl";

import { useLanguage } from "@/core/i18n/LanguageProvider";
import DocsHeader from "@/features/docs/components/DocsHeader";
import DocsSidebar from "@/features/docs/components/DocsSidebar";
import DocsOverview from "@/features/docs/components/DocsOverview";
import { getDocCategories, getTopNavTabs } from "@/features/docs/data/docs-content";
import BreadcrumbNav from "@/shared/components/common/BreadcrumbNav";
import { cn } from "@/shared/lib/utils";

const DocsArticle = dynamic(
  () => import("@/features/docs/components/DocsArticle"),
  {
    loading: () => (
      <div className="space-y-4 rounded-3xl border border-slate-200/80 bg-white/70 p-6 sm:p-8 dark:border-white/10 dark:bg-[#0B0F19]/60">
        <div className="h-6 w-48 animate-pulse rounded-lg bg-slate-200 dark:bg-white/10" />
        <div className="h-4 w-full animate-pulse rounded bg-slate-200/80 dark:bg-white/5" />
        <div className="h-4 w-5/6 animate-pulse rounded bg-slate-200/80 dark:bg-white/5" />
        <div className="h-40 w-full animate-pulse rounded-2xl bg-slate-200/70 dark:bg-white/5" />
      </div>
    ),
  },
);

const DocsSearchModal = dynamic(
  () => import("@/features/docs/components/DocsSearchModal"),
  { ssr: false },
);

// Helper to map sub-topic IDs to their parent top navigation tab
function getParentTabId(topicId: string): string {
  if (topicId === "first-training") return "getting-started";
  if (topicId === "distributed-computing") return "architecture";
  if (topicId === "hpo-tuning" || topicId === "evaluation-metrics") return "scientific-approach";
  if (
    topicId === "api-auth" ||
    topicId === "api-datasets" ||
    topicId === "api-training-inference"
  ) {
    return "backend-api";
  }
  return topicId;
}

export default function DocsPage() {
  const t = useTranslations("Docs");
  const { locale } = useLanguage();

  const [activeTopicId, setActiveTopicId] = useState<string>("overview");
  const [activeTab, setActiveTab] = useState<string>("overview");
  const [isSearchOpen, setIsSearchOpen] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const contentRef = useRef<HTMLElement>(null);

  const topNavTabs = getTopNavTabs(locale);
  const categories = getDocCategories(locale);

  // Sync with URL query parameter on mount and popstate
  useEffect(() => {
    const syncFromUrl = () => {
      if (typeof window === "undefined") return;
      const params = new URLSearchParams(window.location.search);
      const topicFromUrl = params.get("topic");
      if (topicFromUrl) {
        setActiveTopicId(topicFromUrl);
        setActiveTab(getParentTabId(topicFromUrl));
      } else {
        setActiveTopicId("overview");
        setActiveTab("overview");
      }
      contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    };

    syncFromUrl();
    window.addEventListener("popstate", syncFromUrl);

    const handleGlobalSearchShortcut = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setIsSearchOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleGlobalSearchShortcut);

    return () => {
      window.removeEventListener("popstate", syncFromUrl);
      window.removeEventListener("keydown", handleGlobalSearchShortcut);
    };
  }, []);

  const handleSelectTopic = (topicId: string) => {
    setActiveTopicId(topicId);
    setActiveTab(getParentTabId(topicId));
    window.history.pushState(null, "", topicId === "overview" ? "/docs" : `/docs?topic=${topicId}`);
    contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const handleSelectTab = (tabId: string) => {
    setActiveTab(tabId);
    setActiveTopicId(tabId);
    window.history.pushState(null, "", tabId === "overview" ? "/docs" : `/docs?topic=${tabId}`);
    contentRef.current?.scrollTo({ top: 0, behavior: "smooth" });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const currentTopic = useMemo(() => {
    for (const cat of categories) {
      const found = cat.items.find((item) => item.id === activeTopicId);
      if (found) return found;
    }
    return null;
  }, [activeTopicId, categories]);

  return (
    <div className="relative h-screen h-[100dvh] flex flex-col overflow-hidden bg-slate-50/70 text-slate-900 transition-colors dark:bg-[#020817] dark:text-slate-100">
      {/* Background ambient glow matching HAutoML hero */}
      <div className="pointer-events-none absolute -top-40 right-10 h-[500px] w-[500px] rounded-full bg-blue-600/10 blur-[120px] dark:bg-blue-500/15" />
      <div className="pointer-events-none absolute top-[400px] -left-20 h-[450px] w-[450px] rounded-full bg-cyan-500/10 blur-[100px] dark:bg-cyan-500/10" />

      {/* 1. Header: Same floating shell as app header, but with center search bar */}
      <div className="shrink-0">
        <DocsHeader
          onOpenSearch={() => setIsSearchOpen(true)}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen((prev) => !prev)}
          isMobileSidebarOpen={isMobileSidebarOpen}
        />
      </div>

      {/* 2. Sub-nav Category Tabs & Breadcrumb (aligned with exact same max-w-[1360px] margins) */}
      <div className="mx-auto w-full max-w-[1360px] px-3 sm:px-6 pt-1 pb-3 space-y-2.5 shrink-0">
        <BreadcrumbNav
          items={[
            {
              label: t("breadcrumb"),
              href: activeTopicId !== "overview" ? "/docs" : undefined,
            },
            ...(activeTopicId !== "overview" && currentTopic
              ? [{ label: currentTopic.title }]
              : activeTopicId !== "overview"
                ? [{ label: activeTopicId }]
                : []),
          ]}
        />

        <div className="flex items-center gap-1.5 overflow-x-auto rounded-2xl border border-slate-200/80 bg-white/70 p-1.5 backdrop-blur-xl scrollbar-none dark:border-white/10 dark:bg-[#0B0F19]/60 shadow-sm">
          {topNavTabs.map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => handleSelectTab(tab.id)}
                className={cn(
                  "rounded-xl px-4 py-2 text-xs font-bold transition-all whitespace-nowrap",
                  isActive
                    ? "bg-blue-600 text-white shadow-[0_0_16px_rgba(37,99,255,0.35)]"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-white/5"
                )}
              >
                {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. Main layout container (aligned with exact same max-w-[1360px] margins) */}
      <div className="mx-auto flex w-full max-w-[1360px] flex-1 min-h-0 gap-5 sm:gap-6 px-3 sm:px-6 pb-4">
        {/* Left Sidebar - Fixed in position */}
        <DocsSidebar
          activeTopicId={activeTopicId}
          onSelectTopic={handleSelectTopic}
          isOpenMobile={isMobileSidebarOpen}
          onCloseMobile={() => setIsMobileSidebarOpen(false)}
        />

        {/* Center / Right Content Area - Independent vertical scroll */}
        <main
          ref={contentRef}
          className="min-w-0 flex-1 h-full overflow-y-auto pr-1 sm:pr-2 scrollbar-thin pb-8"
        >
          {activeTopicId === "overview" ? (
            <DocsOverview onSelectTopic={handleSelectTopic} />
          ) : (
            <DocsArticle topicId={activeTopicId} onNavigate={handleSelectTopic} />
          )}
        </main>
      </div>

      {/* Search Modal (⌘K) - lazy-loaded only when opened */}
      {isSearchOpen && (
        <DocsSearchModal
          isOpen={isSearchOpen}
          onClose={() => setIsSearchOpen(false)}
          onSelectTopic={handleSelectTopic}
        />
      )}
    </div>
  );
}
