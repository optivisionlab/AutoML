"use client";

import { useState } from "react";
import {
  ExternalLink,
  Copy,
  Check,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react";
import { useTranslations } from "next-intl";

import { useLanguage } from "@/core/i18n/LanguageProvider";
import { getDocsPage } from "../data/markdown-docs";
import MarkdownRenderer from "./MarkdownRenderer";

type DocsArticleProps = {
  topicId: string;
  onNavigate: (topicId: string) => void;
};

// Subpaths on the official MkDocs site https://optivisionlab.github.io/AutoML/docs/
const MKDOCS_PAGE_URLS: Record<string, string> = {
  overview: "https://optivisionlab.github.io/AutoML/docs/",
  "getting-started": "https://optivisionlab.github.io/AutoML/docs/getting_started/",
  "first-training": "https://optivisionlab.github.io/AutoML/docs/getting_started/#huan-luyen-mo-hinh-dau-tien",
  architecture: "https://optivisionlab.github.io/AutoML/docs/architecture/",
  "distributed-computing": "https://optivisionlab.github.io/AutoML/docs/architecture/#cac-thanh-phan-chinh",
  "scientific-approach": "https://optivisionlab.github.io/AutoML/docs/scientific_approach/",
  "hpo-tuning": "https://optivisionlab.github.io/AutoML/docs/scientific_approach/#giai-doan-2-lua-chon-mo-hinh-tinh-chinh-sieu-tham-so",
  "evaluation-metrics": "https://optivisionlab.github.io/AutoML/docs/scientific_approach/#c-chi-so-danh-gia-evaluation-metrics",
  "backend-api": "https://optivisionlab.github.io/AutoML/docs/backend_api/",
  "api-auth": "https://optivisionlab.github.io/AutoML/docs/backend_api/#1-api-xac-thuc-nguoi-dung-auth",
  "api-datasets": "https://optivisionlab.github.io/AutoML/docs/backend_api/#2-api-quan-ly-tap-du-lieu-dataset",
  "api-training-inference": "https://optivisionlab.github.io/AutoML/docs/backend_api/#3-api-tac-vu-automl-huan-luyen",
  releases: "https://optivisionlab.github.io/AutoML/docs/releases/",
  "citation-license": "https://optivisionlab.github.io/AutoML/docs/citation_license/",
};

export default function DocsArticle({ topicId, onNavigate }: DocsArticleProps) {
  const t = useTranslations("Docs");
  const { locale } = useLanguage();
  const [copiedRaw, setCopiedRaw] = useState(false);

  // Retrieve localized page from mirrored markdown docs
  const pageData = getDocsPage(topicId, locale);
  const mkdocsUrl =
    MKDOCS_PAGE_URLS[topicId] ||
    "https://optivisionlab.github.io/AutoML/docs/";

  // Reading sequence for Next/Prev pagination across all 14 topics
  const docFlow: { id: string; label: string }[] = [
    { id: "overview", label: t("tabs.overview") },
    { id: "getting-started", label: t("tabs.gettingStarted") },
    {
      id: "first-training",
      label: locale === "vi" ? "Huấn luyện mô hình đầu tiên" : "First Model Training",
    },
    { id: "architecture", label: t("tabs.architecture") },
    {
      id: "distributed-computing",
      label: locale === "vi" ? "Tính toán phân tán & Worker" : "Distributed Computing & Workers",
    },
    { id: "scientific-approach", label: t("tabs.scientificApproach") },
    {
      id: "hpo-tuning",
      label: locale === "vi" ? "Tìm kiếm siêu tham số (HPO)" : "Hyperparameter Search (HPO)",
    },
    {
      id: "evaluation-metrics",
      label: locale === "vi" ? "Đánh giá & Tiêu chí mô hình" : "Model Evaluation Metrics",
    },
    { id: "backend-api", label: t("tabs.backendApi") },
    {
      id: "api-auth",
      label: locale === "vi" ? "Xác thực & Người dùng (Auth)" : "User Management & Auth API",
    },
    {
      id: "api-datasets",
      label: locale === "vi" ? "Quản lý Dataset (Data API)" : "Dataset Management API",
    },
    {
      id: "api-training-inference",
      label: locale === "vi" ? "Training & Suy luận (Inference)" : "Training & Inference API",
    },
    { id: "releases", label: t("tabs.releases") },
    { id: "citation-license", label: t("tabs.citationLicense") },
  ];

  const currentIndex = docFlow.findIndex((item) => item.id === topicId);
  const prevDoc = currentIndex > 0 ? docFlow[currentIndex - 1] : null;
  const nextDoc =
    currentIndex >= 0 && currentIndex < docFlow.length - 1
      ? docFlow[currentIndex + 1]
      : null;

  const handleCopyMarkdown = () => {
    navigator.clipboard.writeText(pageData.markdown);
    setCopiedRaw(true);
    setTimeout(() => setCopiedRaw(false), 2000);
  };

  return (
    <article className="space-y-8 rounded-3xl border border-slate-200/80 bg-white/70 p-6 sm:p-8 backdrop-blur-xl shadow-sm dark:border-white/10 dark:bg-[#0B0F19]/60">
      {/* Header Toolbar: Mirror badge on left, actions on right (no duplicate BreadcrumbNav) */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-slate-200/70 pb-4 dark:border-white/10">
        <div className="flex items-center gap-2 text-xs font-medium text-emerald-800 dark:text-emerald-300">
          <Sparkles className="h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
          <span>{t("officialMirror")}</span>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Copy Markdown button */}
          <button
            type="button"
            onClick={handleCopyMarkdown}
            className="inline-flex items-center gap-1.5 rounded-xl border border-slate-200/80 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50 dark:border-white/10 dark:bg-[#061021] dark:text-slate-300 dark:hover:bg-white/5"
            title={t("copyMarkdown")}
          >
            {copiedRaw ? (
              <>
                <Check className="h-3.5 w-3.5 text-emerald-500" />
                <span className="text-emerald-600 dark:text-emerald-400 font-bold">
                  {t("copiedMarkdown")}
                </span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5 text-slate-500" />
                <span>{t("copyMarkdown")}</span>
              </>
            )}
          </button>

          {/* View on official MkDocs */}
          <a
            href={mkdocsUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200/70 bg-blue-50/60 px-3 py-1.5 text-xs font-bold text-blue-700 transition hover:bg-blue-100/70 dark:border-blue-900/40 dark:bg-blue-950/30 dark:text-cyan-400 dark:hover:bg-blue-900/50"
            title={t("mkdocsOnline")}
          >
            <span>{t("mkdocsOnline")}</span>
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      {/* 3. Full Verbatim Markdown Content */}
      <div className="min-w-0">
        <MarkdownRenderer content={pageData.markdown} />
      </div>

      {/* 4. Previous / Next Page Navigation */}
      <div className="grid gap-3 pt-6 sm:grid-cols-2 border-t border-slate-200/80 dark:border-white/10">
        {prevDoc ? (
          <button
            type="button"
            onClick={() => onNavigate(prevDoc.id)}
            className="group flex flex-col items-start rounded-2xl border border-slate-200/80 bg-white/60 p-4 text-left shadow-sm transition hover:border-blue-400/60 hover:bg-white dark:border-white/10 dark:bg-[#061021]/60 dark:hover:border-blue-500/50 dark:hover:bg-[#061021]"
          >
            <div className="flex items-center gap-1 text-[11px] font-bold text-slate-500 group-hover:text-blue-600 dark:text-slate-400 dark:group-hover:text-cyan-400">
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>{t("prevPage")}</span>
            </div>
            <div className="mt-1 text-sm font-bold text-slate-900 dark:text-white line-clamp-1">
              {prevDoc.label}
            </div>
          </button>
        ) : (
          <div />
        )}

        {nextDoc ? (
          <button
            type="button"
            onClick={() => onNavigate(nextDoc.id)}
            className="group flex flex-col items-end rounded-2xl border border-slate-200/80 bg-white/60 p-4 text-right shadow-sm transition hover:border-blue-400/60 hover:bg-white dark:border-white/10 dark:bg-[#061021]/60 dark:hover:border-blue-500/50 dark:hover:bg-[#061021]"
          >
            <div className="flex items-center gap-1 text-[11px] font-bold text-slate-500 group-hover:text-blue-600 dark:text-slate-400 dark:group-hover:text-cyan-400">
              <span>{t("nextPage")}</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </div>
            <div className="mt-1 text-sm font-bold text-slate-900 dark:text-white line-clamp-1">
              {nextDoc.label}
            </div>
          </button>
        ) : (
          <div />
        )}
      </div>
    </article>
  );
}
