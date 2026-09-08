"use client";

import { useEffect } from "react";
import {
  BookOpen,
  Boxes,
  BrainCircuit,
  Code2,
  Cpu,
  Database,
  FileText,
  History,
  LineChart,
  PlayCircle,
  Rocket,
  ShieldCheck,
  Sliders,
  Sparkles,
  Users,
  Workflow,
  Zap,
  ExternalLink,
} from "lucide-react";

import { useTranslations } from "next-intl";
import { useLanguage } from "@/core/i18n/LanguageProvider";
import { getDocCategories, DocNavItem } from "../data/docs-content";

type DocsSidebarProps = {
  activeTopicId: string;
  onSelectTopic: (topicId: string) => void;
  isOpenMobile: boolean;
  onCloseMobile: () => void;
};

const iconMap: Record<string, React.ElementType> = {
  BookOpen,
  Rocket,
  PlayCircle,
  Boxes,
  Cpu,
  Workflow,
  Sliders,
  LineChart,
  Code2,
  ShieldCheck,
  Database,
  Zap,
  History,
  FileText,
  BrainCircuit,
  Sparkles,
  Users,
};

export default function DocsSidebar({
  activeTopicId,
  onSelectTopic,
  isOpenMobile,
  onCloseMobile,
}: DocsSidebarProps) {
  const t = useTranslations("Docs");
  const { locale } = useLanguage();
  const categories = getDocCategories(locale);

  useEffect(() => {
    // Automatically keep active sidebar item in view
    const activeEl = document.querySelector(`[data-topic-id="${activeTopicId}"]`);
    if (activeEl) {
      activeEl.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }, [activeTopicId]);

  const renderNavList = () => (
    <nav className="space-y-6">
      {categories.map((category) => (
        <div key={category.id} className="space-y-1">
          <h3 className="px-3 text-[11px] font-black uppercase tracking-wider text-slate-500 dark:text-slate-400">
            {category.title}
          </h3>

          <div className="space-y-0.5">
            {category.items.map((item: DocNavItem) => {
              const isActive = activeTopicId === item.id;
              const IconComponent = item.icon ? iconMap[item.icon] || BookOpen : BookOpen;

              return (
                <button
                  key={item.id}
                  data-topic-id={item.id}
                  type="button"
                  onClick={() => {
                    onSelectTopic(item.id);
                    onCloseMobile();
                  }}
                  className={`group flex w-full items-center justify-between rounded-xl px-3 py-2 text-left text-xs font-semibold transition-all ${
                    isActive
                      ? "bg-blue-600/10 text-blue-600 font-bold border-l-[3px] border-blue-600 pl-2.5 shadow-sm dark:bg-blue-500/15 dark:text-cyan-300 dark:border-cyan-400"
                      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/5 dark:hover:text-white"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <IconComponent
                      className={`h-4 w-4 shrink-0 transition-colors ${
                        isActive
                          ? "text-blue-600 dark:text-cyan-400"
                          : "text-slate-400 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300"
                      }`}
                    />
                    <span className="truncate">{item.title}</span>
                  </div>

                  {item.badge && (
                    <span
                      className={`shrink-0 rounded-md px-1.5 py-0.5 text-[10px] font-bold ${
                        isActive
                          ? "bg-blue-200/80 text-blue-800 dark:bg-blue-900 dark:text-blue-200"
                          : "bg-slate-100 text-slate-500 dark:bg-white/10 dark:text-slate-400"
                      }`}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>
      ))}

      <div className="border-t border-slate-200/80 pt-4 px-3 text-[11px] text-slate-500 dark:border-white/10 dark:text-slate-400 space-y-2">
        <div>
          <p className="font-bold text-slate-700 dark:text-slate-300">HAutoML Documentation</p>
          <p className="mt-0.5 text-[10px]">Phát triển bởi OptiVisionLab, HAUI</p>
        </div>
        <a
          href="https://optivisionlab.github.io/AutoML/docs/"
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-[11px] font-bold text-blue-600 hover:text-blue-700 dark:text-cyan-400 dark:hover:text-cyan-300 transition-colors"
        >
          <span>{t("mkdocsOnline")}</span>
          <ExternalLink className="h-3 w-3" />
        </a>
      </div>
    </nav>
  );

  return (
    <>
      {/* Desktop sidebar with modern rounded card look - Fixed alongside content */}
      <aside className="hidden h-full w-64 shrink-0 overflow-y-auto rounded-2xl border border-slate-200/80 bg-white/70 p-3.5 backdrop-blur-xl scrollbar-thin shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60 lg:block">
        {renderNavList()}
      </aside>

      {/* Mobile Drawer Overlay */}
      {isOpenMobile && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="fixed inset-0 bg-black/60 backdrop-blur-sm transition-opacity"
            onClick={onCloseMobile}
            aria-hidden="true"
          />
          <div className="fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-white p-4 shadow-2xl dark:bg-[#0B0F19] border-r border-slate-200 dark:border-white/10">
            <div className="flex items-center justify-between border-b border-slate-200 pb-3 dark:border-white/10">
              <span className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-blue-500" />
                {t("tableOfContents")}
              </span>
              <button
                type="button"
                onClick={onCloseMobile}
                className="rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-white/10"
              >
                ✕
              </button>
            </div>
            <div className="h-[calc(100vh-5rem)] overflow-y-auto pt-3">
              {renderNavList()}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
